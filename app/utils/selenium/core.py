"""Core Selenium automation for the AIS portal.

`SeleniumUtils` remains the public entrypoint and is re-exported from
`app.utils.selenium_utils` for backward compatibility.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from . import constants
from .dates import date_string_candidates, parse_date_maybe_ptbr
from .debug import try_save_screenshot
from .dom import js_click, safe_click
from .env import env_flag, env_int
from .http_json import fetch_available_days_json

logger = logging.getLogger(__name__)


class SeleniumUtils:
    """Automates the AIS visa portal to check for earlier appointment slots."""

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.driver: Optional[WebDriver] = None
        self._group_id: Optional[str] = None
        self._schedule_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Driver lifecycle
    # ------------------------------------------------------------------

    def setup_driver(self) -> WebDriver:
        """Initialise a Chrome WebDriver with appropriate options."""
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        if chromedriver_path:
            service = Service(executable_path=chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(0)  # rely on explicit waits only
        logger.info("Chrome WebDriver initialised (headless=%s)", self.headless)
        return driver

    def close(self) -> None:
        """Quit the WebDriver and release resources."""
        if self.driver is not None:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except WebDriverException as exc:
                logger.warning("Error while closing WebDriver: %s", exc)
            finally:
                self.driver = None

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def _try_save_screenshot(self, name: str) -> Optional[str]:
        return try_save_screenshot(self.driver, name)

    def _js_click(self, element) -> bool:
        return js_click(self.driver, element)

    def _safe_click(self, element) -> bool:
        return safe_click(self.driver, element)

    # ------------------------------------------------------------------
    # Privacy / terms
    # ------------------------------------------------------------------

    def _accept_privacy_terms(self, wait: WebDriverWait) -> bool:
        """Ensure the 'privacy policy / terms of use' checkbox is accepted."""
        if self.driver is None:
            return False

        label_xpaths = [
            "//label[contains(., 'Política de Privacidade')]",
            "//label[contains(., 'Termos de Uso')]",
            "//label[contains(., 'Política') and contains(., 'Privacidade')]",
        ]

        input_xpaths = [
            "//input[@type='checkbox' and (contains(@id,'policy') or contains(@name,'policy'))]",
            "//input[@type='checkbox' and (contains(@id,'privacy') or contains(@name,'privacy'))]",
            "//input[@type='checkbox' and (contains(@id,'terms') or contains(@name,'terms'))]",
            "(//label[contains(., 'Política de Privacidade') or contains(., 'Termos de Uso')]//ancestor-or-self::*[1]//input[@type='checkbox'])[1]",
        ]

        def _try_select_checkbox(el) -> bool:
            try:
                if el.is_selected():
                    return True
            except Exception:
                pass

            try:
                if el.is_displayed() and el.is_enabled():
                    el.click()
                else:
                    self._js_click(el)
            except Exception:
                self._js_click(el)

            try:
                return bool(el.is_selected())
            except Exception:
                return False

        for xp in label_xpaths:
            try:
                label = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                try:
                    label.click()
                except Exception:
                    self._js_click(label)

                try:
                    candidate_input = label.find_element(
                        By.XPATH,
                        ".//preceding::input[@type='checkbox'][1] | .//following::input[@type='checkbox'][1]",
                    )
                    if _try_select_checkbox(candidate_input):
                        return True
                except Exception:
                    pass

                try:
                    selected = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']:checked")
                    if selected:
                        return True
                except Exception:
                    pass
            except TimeoutException:
                continue

        for xp in input_xpaths:
            try:
                checkbox = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                if _try_select_checkbox(checkbox):
                    return True
            except TimeoutException:
                continue

        return False

    # ------------------------------------------------------------------
    # CAPTCHA detection (no bypass/solving)
    # ------------------------------------------------------------------

    def _detect_captcha_present(self) -> Optional[str]:
        if self.driver is None:
            return None

        checks = [
            (By.CSS_SELECTOR, "iframe[title*='reCAPTCHA']", "recaptcha"),
            (By.CSS_SELECTOR, "iframe[src*='recaptcha']", "recaptcha"),
            (By.CSS_SELECTOR, ".g-recaptcha", "recaptcha"),
            (By.CSS_SELECTOR, "textarea[name='g-recaptcha-response']", "recaptcha"),
            (By.CSS_SELECTOR, "iframe[src*='hcaptcha.com']", "hcaptcha"),
            (By.CSS_SELECTOR, ".h-captcha", "hcaptcha"),
            (By.CSS_SELECTOR, "textarea[name='h-captcha-response']", "hcaptcha"),
            (By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']", "turnstile"),
            (By.CSS_SELECTOR, ".cf-turnstile", "turnstile"),
            (By.CSS_SELECTOR, "input[name='cf-turnstile-response']", "turnstile"),
        ]

        for by, sel, hint in checks:
            try:
                els = self.driver.find_elements(by, sel)
                if els:
                    return hint
            except Exception:
                continue
        return None

    def _captcha_token_present(self) -> bool:
        if self.driver is None:
            return False

        token_selectors = [
            (By.CSS_SELECTOR, "textarea[name='g-recaptcha-response']"),
            (By.CSS_SELECTOR, "textarea[name='h-captcha-response']"),
            (By.CSS_SELECTOR, "input[name='cf-turnstile-response']"),
        ]

        for by, sel in token_selectors:
            try:
                for el in self.driver.find_elements(by, sel):
                    value = (el.get_attribute("value") or "").strip()
                    if value:
                        return True
            except Exception:
                continue
        return False

    def _wait_for_captcha_cleared(self, timeout_seconds: int) -> bool:
        if self.driver is None:
            return False

        if timeout_seconds <= 0:
            return self._captcha_token_present() or self._detect_captcha_present() is None

        wait = WebDriverWait(self.driver, timeout_seconds, poll_frequency=0.5)
        try:
            wait.until(lambda _d: self._captcha_token_present() or self._detect_captcha_present() is None)
            return True
        except TimeoutException:
            return False

    def _find_login_error_message(self) -> Optional[str]:
        if self.driver is None:
            return None

        try:
            alerts = self.driver.find_elements(By.CSS_SELECTOR, ".alert, .flash, .error")
        except Exception:
            return None

        for alert in alerts:
            text = (alert.text or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if "invál" in lowered or "invalid" in lowered or "senha" in lowered or "email" in lowered:
                return text

        return None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> bool:
        """Log in to the AIS portal."""
        if self.driver is None:
            self.driver = self.setup_driver()

        logger.info("Navigating to login page: %s", constants.LOGIN_URL)
        try:
            self.driver.get(constants.LOGIN_URL)
            wait = WebDriverWait(self.driver, constants.DEFAULT_TIMEOUT)

            email_field = wait.until(EC.presence_of_element_located((By.ID, "user_email")))
            email_field.clear()
            email_field.send_keys(email)

            password_field = self.driver.find_element(By.ID, "user_password")
            password_field.clear()
            password_field.send_keys(password)

            captcha_hint = self._detect_captcha_present()
            if captcha_hint is not None:
                manual_wait = env_flag("SELENIUM_CAPTCHA_MANUAL_WAIT", default=not self.headless)
                wait_seconds = env_int(
                    "SELENIUM_CAPTCHA_WAIT_SECONDS",
                    default=180 if not self.headless else 0,
                )

                logger.warning(
                    "CAPTCHA detected on login page (%s). headless=%s manual_wait=%s wait_seconds=%s",
                    captcha_hint,
                    self.headless,
                    manual_wait,
                    wait_seconds,
                )

                if self.headless or not manual_wait or wait_seconds <= 0:
                    self._try_save_screenshot("login_captcha_detected")
                    logger.error(
                        "Login blocked by CAPTCHA in headless/auto mode. "
                        "Run with SELENIUM_HEADLESS=false and solve the CAPTCHA manually, "
                        "or try again later from a different IP/session.")
                    return False

                logger.info(
                    "Please complete the CAPTCHA in the opened browser window. Waiting up to %d seconds...",
                    wait_seconds,
                )
                if not self._wait_for_captcha_cleared(wait_seconds):
                    self._try_save_screenshot("login_captcha_timeout")
                    logger.error("Timed out waiting for CAPTCHA to be completed")
                    return False

            if not self._accept_privacy_terms(wait):
                self._try_save_screenshot("login_privacy_checkbox_not_selected")
                logger.error(
                    "Could not accept the privacy/terms checkbox; login will not proceed. "
                    "Selectors may need an update if the portal HTML changed.")
                return False

            submit_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//input[@value='Acessar'] | //button[contains(., 'Acessar')]")
                )
            )
            submit_btn.click()

            def _post_login_state(_d):
                if "/groups/" in (self.driver.current_url or ""):
                    return ("success", None)

                error_message = self._find_login_error_message()
                if error_message:
                    return ("error", error_message)

                captcha_hint_after = self._detect_captcha_present()
                if captcha_hint_after is not None:
                    return ("captcha", captcha_hint_after)

                return None

            try:
                state, payload = wait.until(_post_login_state)
            except TimeoutException:
                self._try_save_screenshot("login_timeout_no_redirect")
                logger.error("Login did not redirect to /groups/ within timeout")
                return False

            if state == "error":
                self._try_save_screenshot("login_error_banner")
                logger.error("Login failed due to portal error message: %s", payload)
                return False

            if state == "captcha":
                manual_wait = env_flag("SELENIUM_CAPTCHA_MANUAL_WAIT", default=not self.headless)
                wait_seconds = env_int(
                    "SELENIUM_CAPTCHA_WAIT_SECONDS",
                    default=180 if not self.headless else 0,
                )
                logger.warning(
                    "CAPTCHA detected after submit (%s). headless=%s manual_wait=%s wait_seconds=%s",
                    payload,
                    self.headless,
                    manual_wait,
                    wait_seconds,
                )

                if self.headless or not manual_wait or wait_seconds <= 0:
                    self._try_save_screenshot("login_captcha_detected_post_submit")
                    logger.error(
                        "Login blocked by CAPTCHA after submit in headless/auto mode. "
                        "Run with SELENIUM_HEADLESS=false and solve the CAPTCHA manually.")
                    return False

                logger.info(
                    "Please complete the CAPTCHA in the opened browser window. Waiting up to %d seconds...",
                    wait_seconds,
                )
                if not self._wait_for_captcha_cleared(wait_seconds):
                    self._try_save_screenshot("login_captcha_timeout_post_submit")
                    logger.error("Timed out waiting for CAPTCHA to be completed")
                    return False

                try:
                    submit_btn = self.driver.find_element(
                        By.XPATH,
                        "//input[@value='Acessar'] | //button[contains(., 'Acessar')]",
                    )
                    submit_btn.click()
                except Exception:
                    pass

                try:
                    wait.until(EC.url_contains("/groups/"))
                except TimeoutException:
                    self._try_save_screenshot("login_timeout_after_captcha")
                    logger.error("Login did not redirect to /groups/ after CAPTCHA completion")
                    return False

            current_url = self.driver.current_url
            logger.info("Login successful; redirected to %s", current_url)

            parts = current_url.rstrip("/").split("/")
            if "groups" in parts:
                idx = parts.index("groups")
                if idx + 1 < len(parts):
                    self._group_id = parts[idx + 1]
                    logger.info("Detected group_id=%s", self._group_id)
            return True

        except TimeoutException:
            self._try_save_screenshot("login_timeout_exception")
            logger.error("Login timed out – possible CAPTCHA, slow portal, or invalid credentials")
            return False
        except WebDriverException as exc:
            logger.exception("WebDriver error during login: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _navigate_to_appointment_page(self) -> bool:
        """Navigate through the portal flow to reach /schedule/<id>/appointment."""
        if self.driver is None or self._group_id is None:
            logger.error("Driver or group_id not initialised before navigation")
            return False

        wait = WebDriverWait(self.driver, constants.DEFAULT_TIMEOUT)

        def _extract_schedule_id_from_url(url: str) -> Optional[str]:
            parts = (url or "").rstrip("/").split("/")
            if "schedule" in parts:
                idx = parts.index("schedule")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
            return None

        def _appointment_base_url() -> Optional[str]:
            if not self._schedule_id:
                return None
            return f"{constants.BASE_URL}/schedule/{self._schedule_id}/appointment"

        def _ensure_not_print_instructions() -> None:
            if self.driver is None:
                return
            current = self.driver.current_url or ""
            if "appointment/print_instructions" in current:
                base = _appointment_base_url()
                if base:
                    logger.info("Redirecting from print_instructions to appointment: %s", base)
                    self.driver.get(base)

        def _click_reagendar_entrevista() -> bool:
            if self.driver is None:
                return False

            direct_xpaths = [
                "//a[contains(@href, '/appointment') and contains(normalize-space(.), 'Reagendar entrevista') and not(contains(@href,'print')) and not(contains(@href,'instructions'))]",
                "//a[contains(@href, '/appointment') and contains(@href, '/schedule/') and not(contains(@href,'print')) and not(contains(@href,'instructions')) and contains(normalize-space(.), 'Reagendar')]",
                "//button[contains(@onclick, '/appointment') and not(contains(@onclick,'print')) and contains(normalize-space(.), 'Reagendar')]",
            ]
            for xp in direct_xpaths:
                try:
                    el = WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp)))
                    if self._safe_click(el):
                        return True
                except TimeoutException:
                    continue
                except Exception:
                    continue

            try:
                accordion_title = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "//li[contains(@class,'accordion-item')][.//h5[contains(normalize-space(.), 'Reagendar entrevista')]]//a[contains(@class,'accordion-title')]",
                        )
                    )
                )
                expanded = (accordion_title.get_attribute("aria-expanded") or "").lower() == "true"
                if not expanded:
                    self._safe_click(accordion_title)
                    WebDriverWait(self.driver, 5).until(
                        lambda _d: (accordion_title.get_attribute("aria-expanded") or "").lower() == "true"
                    )
            except TimeoutException:
                pass
            except Exception:
                pass

            inner_xpaths = [
                "//li[contains(@class,'accordion-item')][.//h5[contains(normalize-space(.), 'Reagendar entrevista')]]//div[contains(@class,'accordion-content')]//a[contains(@href, '/appointment') and not(contains(@href,'print')) and not(contains(@href,'instructions'))]",
                "//div[contains(@class,'accordion-content')]//a[contains(@href, '/appointment') and contains(normalize-space(.), 'Reagendar entrevista') and not(contains(@href,'print')) and not(contains(@href,'instructions'))]",
            ]
            for xp in inner_xpaths:
                try:
                    link = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, xp)))
                    if self._safe_click(link):
                        return True
                except TimeoutException:
                    continue
                except Exception:
                    continue

            return False

        try:
            group_url = f"{constants.BASE_URL}/groups/{self._group_id}"
            logger.info("Navigating to group page: %s", group_url)
            self.driver.get(group_url)

            if _click_reagendar_entrevista():
                wait.until(
                    lambda _d: ("/schedule/" in (self.driver.current_url or ""))
                    and (
                        "continue_actions" in (self.driver.current_url or "")
                        or "appointment" in (self.driver.current_url or "")
                    )
                )
                current_url = self.driver.current_url
                self._schedule_id = _extract_schedule_id_from_url(current_url)
                if self._schedule_id:
                    logger.info("Detected schedule_id=%s", self._schedule_id)

                if "continue_actions" in (current_url or ""):
                    if self._schedule_id:
                        appointment_url = f"{constants.BASE_URL}/schedule/{self._schedule_id}/appointment"
                        logger.info("Navigating directly to appointment URL: %s", appointment_url)
                        self.driver.get(appointment_url)

                    if "appointment" not in (self.driver.current_url or ""):
                        if not _click_reagendar_entrevista() and self._schedule_id:
                            appointment_url = f"{constants.BASE_URL}/schedule/{self._schedule_id}/appointment"
                            logger.info("Falling back to direct appointment URL: %s", appointment_url)
                            self.driver.get(appointment_url)

                wait.until(lambda _d: "appointment" in (self.driver.current_url or ""))
                _ensure_not_print_instructions()
                wait.until(
                    lambda _d: "/appointment" in (self.driver.current_url or "")
                    and "print_instructions" not in (self.driver.current_url or "")
                )
                logger.info("Reached appointment page: %s", self.driver.current_url)
                return True

            continue_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(., 'Continuar')] | //button[contains(., 'Continuar')]")
                )
            )
            continue_btn.click()

            wait.until(EC.url_contains("continue_actions"))
            current_url = self.driver.current_url
            logger.info("Reached continue_actions: %s", current_url)

            self._schedule_id = _extract_schedule_id_from_url(current_url)
            if self._schedule_id:
                logger.info("Detected schedule_id=%s", self._schedule_id)

            if self._schedule_id:
                appointment_url = f"{constants.BASE_URL}/schedule/{self._schedule_id}/appointment"
                logger.info("Navigating directly to appointment URL: %s", appointment_url)
                self.driver.get(appointment_url)

            clicked = "appointment" in (self.driver.current_url or "")
            if not clicked:
                clicked = _click_reagendar_entrevista()

            if not clicked and self._schedule_id:
                appointment_url = f"{constants.BASE_URL}/schedule/{self._schedule_id}/appointment"
                logger.info("Falling back to direct appointment URL: %s", appointment_url)
                self.driver.get(appointment_url)

            wait.until(lambda _d: "appointment" in (self.driver.current_url or ""))
            _ensure_not_print_instructions()
            wait.until(
                lambda _d: "/appointment" in (self.driver.current_url or "")
                and "print_instructions" not in (self.driver.current_url or "")
            )
            logger.info("Reached appointment page: %s", self.driver.current_url)
            return True

        except TimeoutException as exc:
            self._try_save_screenshot("navigate_to_appointment_timeout")
            logger.error("Timeout while navigating to appointment page: %s", exc)
            return False
        except WebDriverException as exc:
            logger.exception("WebDriver error during navigation: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Appointment page helpers
    # ------------------------------------------------------------------

    def _select_facility_if_needed(self, select_el, preferred_text: str = "São Paulo") -> bool:
        try:
            select = Select(select_el)
        except Exception:
            return False

        try:
            current_value = (select_el.get_attribute("value") or "").strip()
        except Exception:
            current_value = ""

        if current_value and current_value.lower() not in ("0", "none"):
            return True

        preferred_lower = preferred_text.strip().lower()
        preferred_value: Optional[str] = None
        first_value: Optional[str] = None
        for opt in select.options:
            try:
                value = (opt.get_attribute("value") or "").strip()
                text = (opt.text or "").strip()
                disabled = (opt.get_attribute("disabled") is not None)
            except Exception:
                continue

            if disabled or not value:
                continue

            if first_value is None:
                first_value = value

            if preferred_lower and preferred_lower in text.lower():
                preferred_value = value
                break

        target_value = preferred_value or first_value
        if not target_value:
            return False

        try:
            select.select_by_value(target_value)
            return True
        except Exception:
            return False

    def _select_first_available_option(self, select_el) -> bool:
        try:
            select = Select(select_el)
        except Exception:
            return False

        try:
            current_value = (select_el.get_attribute("value") or "").strip()
        except Exception:
            current_value = ""

        if current_value and current_value.lower() not in ("0", "none"):
            return True

        first_value: Optional[str] = None
        for opt in select.options:
            try:
                value = (opt.get_attribute("value") or "").strip()
                text = (opt.text or "").strip().lower()
                disabled = (opt.get_attribute("disabled") is not None)
            except Exception:
                continue

            if disabled or not value:
                continue

            if text in ("", "selecionar", "selecione", "select"):
                continue

            first_value = value
            break

        if not first_value:
            return False

        try:
            select.select_by_value(first_value)
            return True
        except Exception:
            if self.driver is None:
                return False
            try:
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    select_el,
                    first_value,
                )
                return True
            except Exception:
                return False

    def _ensure_default_times_selected(self) -> None:
        if self.driver is None:
            return

        wait = WebDriverWait(self.driver, constants.DEFAULT_TIMEOUT)
        time_ids = [
            "appointments_consulate_appointment_time",
            "appointments_asc_appointment_time",
        ]

        for tid in time_ids:
            try:
                select_el = wait.until(EC.presence_of_element_located((By.ID, tid)))
                self._select_first_available_option(select_el)
            except TimeoutException:
                continue

        label_texts = ["Horário do agendamento", "Horário"]
        for label_text in label_texts:
            try:
                label = self.driver.find_element(By.XPATH, f"//label[contains(normalize-space(.), '{label_text}')]"
                )
                select_el = label.find_element(By.XPATH, "./following::select[1]")
                self._select_first_available_option(select_el)
            except Exception:
                continue

    def _ensure_default_facilities_selected(self) -> None:
        if self.driver is None:
            return

        wait = WebDriverWait(self.driver, constants.DEFAULT_TIMEOUT)
        facility_ids = [
            "appointments_consulate_appointment_facility_id",
            "appointments_asc_appointment_facility_id",
            "appointments_consulate_facility_id",
            "appointments_asc_facility_id",
        ]

        for fid in facility_ids:
            try:
                select_el = wait.until(EC.presence_of_element_located((By.ID, fid)))
                self._select_facility_if_needed(select_el, preferred_text="São Paulo")
            except TimeoutException:
                continue

        label_select_pairs = [
            ("Local da Seção Consular", "São Paulo"),
            ("Local do CASV", "São Paulo"),
        ]
        for label_text, preferred in label_select_pairs:
            try:
                label = self.driver.find_element(
                    By.XPATH,
                    f"//label[contains(normalize-space(.), '{label_text}')]",
                )
                select_el = label.find_element(By.XPATH, "./following::select[1]")
                self._select_facility_if_needed(select_el, preferred_text=preferred)
            except Exception:
                continue

    def _set_date_value(self, date_el, date_str: str) -> bool:
        if not date_el or not date_str:
            return False

        try:
            tag = (getattr(date_el, "tag_name", "") or "").lower()
        except Exception:
            tag = ""

        if tag == "select":
            try:
                Select(date_el).select_by_value(date_str)
                return True
            except Exception:
                return False

        target_dt = None
        try:
            target_dt = parse_date_maybe_ptbr(date_str)
        except Exception:
            target_dt = None

        if self.driver is None:
            return False

        if target_dt is not None:
            try:
                if self._pick_date_from_datepicker(date_el, target_dt):
                    return True
            except Exception:
                pass

        # Fallback: set via JS (works in some portal variants, but may not
        # trigger the same Ajax flows as clicking a day cell).

        for candidate in date_string_candidates(date_str):
            try:
                self.driver.execute_script(
                    r"""
                    const el = arguments[0];
                    const val = arguments[1];
                    if (!el) return;

                    const triggerEvents = () => {
                      try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (e) {}
                      try { el.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
                    };

                    const setRaw = () => {
                      try { el.removeAttribute('readonly'); } catch (e) {}
                      el.value = val;
                      triggerEvents();
                    };

                    const setViaDatepicker = () => {
                      if (!window.jQuery) return false;
                      const $el = window.jQuery(el);
                      if (!$el || !$el.datepicker) return false;

                      let d = null;
                      const iso = /^\d{4}-\d{2}-\d{2}$/;
                      const br = /^\d{2}\/\d{2}\/\d{4}$/;
                      if (iso.test(val)) {
                        const parts = val.split('-').map(x => parseInt(x, 10));
                        d = new Date(parts[0], parts[1] - 1, parts[2]);
                      } else if (br.test(val)) {
                        const parts = val.split('/').map(x => parseInt(x, 10));
                        d = new Date(parts[2], parts[1] - 1, parts[0]);
                      }

                      if (!d || isNaN(d.getTime())) return false;
                      try { $el.datepicker('setDate', d); } catch (e) { return false; }
                      triggerEvents();
                      return true;
                    };

                    if (!setViaDatepicker()) {
                      setRaw();
                    }
                                        """,
                    date_el,
                    candidate,
                )

                actual = (date_el.get_attribute("value") or "").strip()
                if actual:
                    return True
            except Exception:
                continue

        return False

    def _pick_date_from_datepicker(self, input_el, target_dt) -> bool:
        """Select a date by clicking the enabled day in the jQuery UI datepicker.

        This is important for AIS because simply setting the input value can fail
        to trigger the portal's dependent updates (e.g. loading available times).
        """

        if self.driver is None:
            return False

        # Month index in jQuery UI datepicker is 0-based.
        target_year = int(getattr(target_dt, "year"))
        target_month_index = int(getattr(target_dt, "month")) - 1
        target_day = int(getattr(target_dt, "day"))

        def _month_name_to_number(name: str) -> Optional[int]:
            n = (name or "").strip().lower()
            mapping = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
                "janeiro": 1,
                "fevereiro": 2,
                "março": 3,
                "marco": 3,
                "abril": 4,
                "maio": 5,
                "junho": 6,
                "julho": 7,
                "agosto": 8,
                "setembro": 9,
                "outubro": 10,
                "novembro": 11,
                "dezembro": 12,
            }
            return mapping.get(n)

        def _ym_key(year: int, month: int) -> int:
            return year * 12 + month

        def _get_displayed_months() -> list[tuple[int, int]]:
            # Returns list of (year, month) shown in the multi-month datepicker.
            if self.driver is None:
                return []
            try:
                container = self.driver.find_element(By.ID, "ui-datepicker-div")
            except Exception:
                return []

            out: list[tuple[int, int]] = []
            for title in container.find_elements(By.CSS_SELECTOR, ".ui-datepicker-title"):
                try:
                    month_text = (title.find_element(By.CSS_SELECTOR, ".ui-datepicker-month").text or "").strip()
                    year_text = (title.find_element(By.CSS_SELECTOR, ".ui-datepicker-year").text or "").strip()
                    month_num = _month_name_to_number(month_text)
                    year_num = int(year_text)
                    if month_num:
                        out.append((year_num, month_num))
                except Exception:
                    continue
            return out

        try:
            self._safe_click(input_el)
        except Exception:
            try:
                self._js_click(input_el)
            except Exception:
                return False

        wait = WebDriverWait(self.driver, constants.DEFAULT_TIMEOUT)
        try:
            wait.until(EC.visibility_of_element_located((By.ID, "ui-datepicker-div")))
        except TimeoutException:
            return False

        # Try a bounded number of month navigations.
        for _ in range(24):
            try:
                container = self.driver.find_element(By.ID, "ui-datepicker-div")
            except Exception:
                return False

            # If the target month is currently displayed, attempt to click the day.
            day_cells = container.find_elements(
                By.CSS_SELECTOR,
                f"td[data-handler='selectDay'][data-year='{target_year}'][data-month='{target_month_index}']",
            )
            for cell in day_cells:
                try:
                    classes = (cell.get_attribute("class") or "").lower()
                    if "ui-state-disabled" in classes or "ui-datepicker-unselectable" in classes:
                        continue
                    link = cell.find_element(By.CSS_SELECTOR, "a.ui-state-default")
                    if (link.text or "").strip() != str(target_day):
                        continue
                    if self._safe_click(link):
                        # Wait for the input value to update and/or picker to close.
                        try:
                            wait.until(lambda _d: (input_el.get_attribute("value") or "").strip() != "")
                        except TimeoutException:
                            pass
                        return True
                except Exception:
                    continue

            # Not found in current view: decide whether to go prev or next.
            displayed = _get_displayed_months()
            if not displayed:
                break

            displayed_keys = [_ym_key(y, m) for (y, m) in displayed]
            target_key = _ym_key(target_year, target_month_index + 1)
            min_key = min(displayed_keys)
            max_key = max(displayed_keys)

            nav_selector = None
            if target_key > max_key:
                nav_selector = "a.ui-datepicker-next"
            elif target_key < min_key:
                nav_selector = "a.ui-datepicker-prev"
            else:
                # Target month is within the displayed range, but the day isn't selectable.
                return False

            try:
                nav = container.find_element(By.CSS_SELECTOR, nav_selector)
                if not self._safe_click(nav):
                    return False
                # Wait until the month titles change.
                old = displayed_keys
                wait.until(lambda _d: [_ym_key(y, m) for (y, m) in _get_displayed_months()] != old)
            except TimeoutException:
                continue
            except Exception:
                continue

        return False

    def _select_first_earlier_date_on_page(self, date_str: str) -> bool:
        if self.driver is None or not date_str:
            return False

        candidate_ids = [
            "appointments_consulate_appointment_date",
            "appointments_asc_appointment_date",
        ]

        for cid in candidate_ids:
            try:
                el = self.driver.find_element(By.ID, cid)
            except NoSuchElementException:
                continue
            except Exception:
                continue

            if self._set_date_value(el, date_str):
                logger.info("Selected appointment date %s in field id=%s", date_str, cid)
                return True

        return False

    def _fetch_available_days_json(self, facility_id: str) -> list[str]:
        if not facility_id or not self._schedule_id:
            return []

        return fetch_available_days_json(
            constants.BASE_URL,
            self._schedule_id,
            facility_id,
            self.driver,
        )

    # ------------------------------------------------------------------
    # Date checking
    # ------------------------------------------------------------------

    def get_available_dates(self, current_appointment_date: str) -> List[str]:
        if self.driver is None:
            logger.error("Driver not initialised; call login() first")
            return []

        wait = WebDriverWait(self.driver, constants.DEFAULT_TIMEOUT)
        earlier_dates: List[str] = []

        try:
            current_dt = parse_date_maybe_ptbr(current_appointment_date)
        except (ValueError, OverflowError) as exc:
            logger.error("Cannot parse current_appointment_date=%s: %s", current_appointment_date, exc)
            return []

        try:
            wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//fieldset[.//legend[contains(normalize-space(.), 'Agendamento Consular')]]"
                        " | //legend[contains(normalize-space(.), 'Agendamento Consular')]"
                        " | //*[@id='consulate-appointment-fields']"
                        " | //*[@id='appointments_consulate_appointment_date']"
                        " | //*[@id='appointments_consulate_appointment_facility_id']",
                    )
                )
            )
        except TimeoutException:
            logger.warning("Appointment form not found within timeout")
            self._try_save_screenshot("appointment_form_not_found")
            return []

        self._ensure_default_facilities_selected()
        self._ensure_default_times_selected()

        date_selectors = [
            "appointments_consulate_appointment_date",
            "appointments_asc_appointment_date",
        ]

        for selector_id in date_selectors:
            try:
                select_el = self.driver.find_element(By.ID, selector_id)
                if (select_el.tag_name or "").lower() != "select":
                    logger.debug("Date element is not a <select>: id=%s tag=%s", selector_id, select_el.tag_name)
                    continue

                options = select_el.find_elements(By.TAG_NAME, "option")
                for option in options:
                    date_str = option.get_attribute("value")
                    if not date_str:
                        continue
                    try:
                        option_dt = parse_date_maybe_ptbr(date_str)
                        if option_dt < current_dt:
                            earlier_dates.append(date_str)
                    except (ValueError, OverflowError):
                        logger.debug("Skipping unparseable date option: %s", date_str)
            except NoSuchElementException:
                logger.debug("Date selector not found: id=%s", selector_id)

        if not earlier_dates and self._schedule_id:
            try:
                facility_ids = [
                    "appointments_consulate_appointment_facility_id",
                    "appointments_asc_appointment_facility_id",
                    "appointments_consulate_facility_id",
                    "appointments_asc_facility_id",
                ]

                for fid in facility_ids:
                    facility_value = ""
                    try:
                        facility_value = (
                            self.driver.find_element(By.ID, fid).get_attribute("value") or ""
                        ).strip()
                    except Exception:
                        facility_value = ""

                    if not facility_value:
                        continue

                    days = self._fetch_available_days_json(facility_value)
                    for date_str in days:
                        try:
                            option_dt = parse_date_maybe_ptbr(date_str)
                            if option_dt < current_dt:
                                earlier_dates.append(date_str)
                        except (ValueError, OverflowError):
                            logger.debug("Skipping unparseable day JSON date: %s", date_str)
            except Exception as exc:
                logger.debug("Days JSON fallback failed: %s", exc)

        seen: set[str] = set()
        unique_dates: List[str] = []
        for d in earlier_dates:
            if d not in seen:
                seen.add(d)
                unique_dates.append(d)

        if unique_dates:
            try:
                earliest = min(unique_dates, key=parse_date_maybe_ptbr)
                if not self._select_first_earlier_date_on_page(earliest):
                    logger.debug("Could not set earliest date on page: %s", earliest)
            except Exception:
                pass

        logger.info("Found %d earlier date(s) than %s", len(unique_dates), current_appointment_date)
        return unique_dates

    # ------------------------------------------------------------------
    # High-level orchestration
    # ------------------------------------------------------------------

    def check_dates_for_user(self, user_id: str, email: str, password: str, appointment_date: str) -> List[str]:
        if not email or not password or not appointment_date:
            logger.error("check_dates_for_user: missing required fields for user_id=%s", user_id)
            return []

        logger.info(
            "Starting date check for user_id=%s appointment_date=%s",
            user_id,
            appointment_date,
        )

        try:
            if self.driver is None:
                self.driver = self.setup_driver()

            login_ok = self.login(email, password)
            del password

            if not login_ok:
                logger.error("Login failed for user_id=%s; aborting date check", user_id)
                return []

            nav_ok = self._navigate_to_appointment_page()
            if not nav_ok:
                logger.error("Navigation failed for user_id=%s; aborting date check", user_id)
                return []

            return self.get_available_dates(appointment_date)

        except Exception as exc:
            logger.exception(
                "Unexpected error in check_dates_for_user for user_id=%s: %s",
                user_id,
                exc,
            )
            return []

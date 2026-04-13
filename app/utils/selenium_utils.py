"""
Selenium automation utilities for the USA visa scheduling website.
Navigates the AIS portal to retrieve available appointment dates.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from dateutil import parser as date_parser
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

BASE_URL = "https://ais.usvisa-info.com/pt-br/niv"
LOGIN_URL = f"{BASE_URL}/users/sign_in"
DEFAULT_TIMEOUT = 20  # seconds


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes", "y")


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _resolve_debug_dir() -> Path:
    configured = os.environ.get("SELENIUM_DEBUG_DIR", "").strip()
    if configured:
        return Path(configured)

    # Lambda typically only allows writing to /tmp.
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp") / "selenium"

    return Path.cwd() / "artifacts" / "selenium"


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
        """Best-effort screenshot saving for debugging (no secrets logged)."""
        if self.driver is None:
            return None

        try:
            out_dir = _resolve_debug_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name)
            path = out_dir / safe_name
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                path = path.with_suffix(".png")

            ok = self.driver.save_screenshot(str(path))
            if ok:
                logger.info("Saved Selenium screenshot: %s", path)
                return str(path)
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Failed to save screenshot: %s", exc)
        return None

    def _js_click(self, element) -> bool:
        """Best-effort click using JS (handles hidden/styled checkboxes)."""
        if self.driver is None:
            return False
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:  # pylint: disable=broad-except
            return False

    def _accept_privacy_terms(self, wait: WebDriverWait) -> bool:
        """Ensure the 'privacy policy / terms of use' checkbox is accepted."""
        if self.driver is None:
            return False

        # The portal often uses a styled checkbox where the underlying <input>
        # is hidden; clicking the <label> is usually the most reliable.
        label_xpaths = [
            "//label[contains(., 'Política de Privacidade')]",
            "//label[contains(., 'Termos de Uso')]",
            "//label[contains(., 'Política') and contains(., 'Privacidade')]",
        ]

        input_xpaths = [
            "//input[@type='checkbox' and (contains(@id,'policy') or contains(@name,'policy'))]",
            "//input[@type='checkbox' and (contains(@id,'privacy') or contains(@name,'privacy'))]",
            "//input[@type='checkbox' and (contains(@id,'terms') or contains(@name,'terms'))]",
            # Fallback: any checkbox near the privacy/terms label
            "(//label[contains(., 'Política de Privacidade') or contains(., 'Termos de Uso')]//ancestor-or-self::*[1]//input[@type='checkbox'])[1]",
        ]

        def _try_select_checkbox(el) -> bool:
            try:
                if el.is_selected():
                    return True
            except Exception:  # pylint: disable=broad-except
                pass

            try:
                if el.is_displayed() and el.is_enabled():
                    el.click()
                else:
                    self._js_click(el)
            except Exception:  # pylint: disable=broad-except
                self._js_click(el)

            try:
                return bool(el.is_selected())
            except Exception:  # pylint: disable=broad-except
                return False

        # 1) Prefer clicking the label (works for hidden inputs)
        for xp in label_xpaths:
            try:
                label = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                try:
                    label.click()
                except Exception:  # pylint: disable=broad-except
                    self._js_click(label)

                # After clicking the label, try to find the paired input and verify selected.
                try:
                    candidate_input = label.find_element(By.XPATH, ".//preceding::input[@type='checkbox'][1] | .//following::input[@type='checkbox'][1]")
                    if _try_select_checkbox(candidate_input):
                        return True
                except Exception:  # pylint: disable=broad-except
                    # Some implementations don't place input near label; continue.
                    pass

                # If we can't verify, try a broader search for any checkbox already selected.
                try:
                    selected = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']:checked")
                    if selected:
                        return True
                except Exception:  # pylint: disable=broad-except
                    pass
            except TimeoutException:
                continue

        # 2) Try clicking the input directly
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
        """Return a short CAPTCHA hint string if a CAPTCHA widget is detected."""
        if self.driver is None:
            return None

        # Common providers/widgets: reCAPTCHA, hCaptcha, Cloudflare Turnstile.
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
            except Exception:  # pylint: disable=broad-except
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
            except Exception:  # pylint: disable=broad-except
                continue
        return False

    def _wait_for_captcha_cleared(self, timeout_seconds: int) -> bool:
        """Wait until CAPTCHA is no longer present or has a token value."""
        if self.driver is None:
            return False

        if timeout_seconds <= 0:
            return self._captcha_token_present() or self._detect_captcha_present() is None

        wait = WebDriverWait(self.driver, timeout_seconds, poll_frequency=0.5)
        try:
            wait.until(
                lambda _d: self._captcha_token_present()
                or self._detect_captcha_present() is None
            )
            return True
        except TimeoutException:
            return False

    def _find_login_error_message(self) -> Optional[str]:
        if self.driver is None:
            return None

        try:
            alerts = self.driver.find_elements(By.CSS_SELECTOR, ".alert, .flash, .error")
        except Exception:  # pylint: disable=broad-except
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
        """
        Log in to the AIS portal.

        Returns True on success, False on credential failure.
        Password is never written to logs.
        """
        if self.driver is None:
            self.driver = self.setup_driver()

        logger.info("Navigating to login page: %s", LOGIN_URL)
        try:
            self.driver.get(LOGIN_URL)
            wait = WebDriverWait(self.driver, DEFAULT_TIMEOUT)

            # Fill email
            email_field = wait.until(
                EC.presence_of_element_located((By.ID, "user_email"))
            )
            email_field.clear()
            email_field.send_keys(email)

            # Fill password
            password_field = self.driver.find_element(By.ID, "user_password")
            password_field.clear()
            password_field.send_keys(password)

            # If a CAPTCHA is present, we must not attempt to bypass it.
            # In visible mode, allow the user to solve it manually.
            captcha_hint = self._detect_captcha_present()
            if captcha_hint is not None:
                manual_wait = _env_flag("SELENIUM_CAPTCHA_MANUAL_WAIT", default=not self.headless)
                wait_seconds = _env_int("SELENIUM_CAPTCHA_WAIT_SECONDS", default=180 if not self.headless else 0)

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
                        "or try again later from a different IP/session."
                    )
                    return False

                logger.info(
                    "Please complete the CAPTCHA in the opened browser window. "
                    "Waiting up to %d seconds...",
                    wait_seconds,
                )
                if not self._wait_for_captcha_cleared(wait_seconds):
                    self._try_save_screenshot("login_captcha_timeout")
                    logger.error("Timed out waiting for CAPTCHA to be completed")
                    return False

            # Accept privacy/terms checkbox (required by the portal)
            if not self._accept_privacy_terms(wait):
                self._try_save_screenshot("login_privacy_checkbox_not_selected")
                logger.error(
                    "Could not accept the privacy/terms checkbox; login will not proceed. "
                    "Selectors may need an update if the portal HTML changed."
                )
                return False

            # Click submit button
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
                manual_wait = _env_flag("SELENIUM_CAPTCHA_MANUAL_WAIT", default=not self.headless)
                wait_seconds = _env_int("SELENIUM_CAPTCHA_WAIT_SECONDS", default=180 if not self.headless else 0)
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
                        "Run with SELENIUM_HEADLESS=false and solve the CAPTCHA manually."
                    )
                    return False

                logger.info(
                    "Please complete the CAPTCHA in the opened browser window. "
                    "Waiting up to %d seconds...",
                    wait_seconds,
                )
                if not self._wait_for_captcha_cleared(wait_seconds):
                    self._try_save_screenshot("login_captcha_timeout_post_submit")
                    logger.error("Timed out waiting for CAPTCHA to be completed")
                    return False

                # Sometimes the form doesn't auto-submit after CAPTCHA completion.
                try:
                    submit_btn = self.driver.find_element(
                        By.XPATH,
                        "//input[@value='Acessar'] | //button[contains(., 'Acessar')]",
                    )
                    submit_btn.click()
                except Exception:  # pylint: disable=broad-except
                    pass

                try:
                    wait.until(EC.url_contains("/groups/"))
                except TimeoutException:
                    self._try_save_screenshot("login_timeout_after_captcha")
                    logger.error("Login did not redirect to /groups/ after CAPTCHA completion")
                    return False

            current_url = self.driver.current_url
            logger.info("Login successful; redirected to %s", current_url)

            # Extract group_id from URL
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
        """
        Navigate through the portal flow to reach the appointment scheduling page.

        Steps:
          1. /groups/<group_id>          -> click "Continuar"
          2. /schedule/<id>/continue_actions -> click "Reagendar entrevista"
          3. /schedule/<id>/appointment  -> scrape available dates
        """
        if self.driver is None or self._group_id is None:
            logger.error("Driver or group_id not initialised before navigation")
            return False

        wait = WebDriverWait(self.driver, DEFAULT_TIMEOUT)

        def _extract_schedule_id_from_url(url: str) -> Optional[str]:
            parts = (url or "").rstrip("/").split("/")
            if "schedule" in parts:
                idx = parts.index("schedule")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
            return None

        def _click_reagendar_entrevista() -> bool:
            """Try clicking the 'Reagendar entrevista' action (button/link)."""
            if self.driver is None:
                return False

            # Some pages show an accordion header + a green button inside.
            # Try to click a real <a>/<button> first; if not found, click any header then retry.
            candidates_xpaths = [
                "//button[contains(normalize-space(.), 'Reagendar entrevista')]",
                "//a[contains(normalize-space(.), 'Reagendar entrevista')]",
            ]

            for xp in candidates_xpaths:
                try:
                    el = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xp))
                    )
                    el.click()
                    return True
                except TimeoutException:
                    continue
                except Exception:  # pylint: disable=broad-except
                    continue

            # Fallback: click the accordion/header text, then retry button/link.
            try:
                header = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//*[contains(normalize-space(.), 'Reagendar entrevista')][1]")
                    )
                )
                try:
                    header.click()
                except Exception:  # pylint: disable=broad-except
                    self._js_click(header)

                for xp in candidates_xpaths:
                    try:
                        el = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, xp))
                        )
                        el.click()
                        return True
                    except TimeoutException:
                        continue
                    except Exception:  # pylint: disable=broad-except
                        continue
            except TimeoutException:
                return False
            except Exception:  # pylint: disable=broad-except
                return False

            return False

        try:
            # Step 1 – groups page
            group_url = f"{BASE_URL}/groups/{self._group_id}"
            logger.info("Navigating to group page: %s", group_url)
            self.driver.get(group_url)

            # Variant A: group page already exposes the 'Reagendar entrevista' action.
            # Click it and accept redirect to either continue_actions or appointment.
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

                # If we landed on continue_actions, click reschedule again.
                if "continue_actions" in (current_url or ""):
                    reschedule_btn = wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//a[contains(., 'Reagendar entrevista')] | //button[contains(., 'Reagendar entrevista')]")
                        )
                    )
                    reschedule_btn.click()

                wait.until(EC.url_contains("appointment"))
                logger.info("Reached appointment page: %s", self.driver.current_url)
                return True

            # Variant B: classic flow uses a 'Continuar' step.
            continue_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(., 'Continuar')] | //button[contains(., 'Continuar')]")
                )
            )
            continue_btn.click()

            # Step 2 – continue_actions
            wait.until(EC.url_contains("continue_actions"))
            current_url = self.driver.current_url
            logger.info("Reached continue_actions: %s", current_url)

            self._schedule_id = _extract_schedule_id_from_url(current_url)
            if self._schedule_id:
                logger.info("Detected schedule_id=%s", self._schedule_id)

            reschedule_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(., 'Reagendar entrevista')] | //button[contains(., 'Reagendar entrevista')]")
                )
            )
            reschedule_btn.click()

            # Step 3 – appointment page
            wait.until(EC.url_contains("appointment"))
            logger.info("Reached appointment page: %s", self.driver.current_url)
            return True

        except TimeoutException as exc:
            logger.error("Timeout while navigating to appointment page: %s", exc)
            return False
        except WebDriverException as exc:
            logger.exception("WebDriver error during navigation: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Date checking
    # ------------------------------------------------------------------

    def get_available_dates(self, current_appointment_date: str) -> List[str]:
        """
        Scrape available dates from the appointment page.

        Returns dates that are strictly earlier than *current_appointment_date*.
        Checks both "Agendamento Consular" and "Agendamento do CASV" sections.
        """
        if self.driver is None:
            logger.error("Driver not initialised; call login() first")
            return []

        wait = WebDriverWait(self.driver, DEFAULT_TIMEOUT)
        earlier_dates: List[str] = []

        try:
            current_dt = date_parser.parse(current_appointment_date)
        except (ValueError, OverflowError) as exc:
            logger.error(
                "Cannot parse current_appointment_date=%s: %s",
                current_appointment_date,
                exc,
            )
            return []

        # Wait for the date picker / calendar to load
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//h2[contains(., 'Agendamento Consular')] | //select[@id='appointments_consulate_appointment_date']")
                )
            )
        except TimeoutException:
            logger.warning("Appointment form not found within timeout")
            return []

        # Gather all date option elements from select dropdowns
        date_selectors = [
            "appointments_consulate_appointment_date",
            "appointments_asc_appointment_date",
        ]

        for selector_id in date_selectors:
            try:
                select_el = self.driver.find_element(By.ID, selector_id)
                options = select_el.find_elements(By.TAG_NAME, "option")
                for option in options:
                    date_str = option.get_attribute("value")
                    if not date_str:
                        continue
                    try:
                        option_dt = date_parser.parse(date_str)
                        if option_dt < current_dt:
                            earlier_dates.append(date_str)
                    except (ValueError, OverflowError):
                        logger.debug("Skipping unparseable date option: %s", date_str)
            except NoSuchElementException:
                logger.debug("Date selector not found: id=%s", selector_id)

        # De-duplicate while preserving order
        seen: set[str] = set()
        unique_dates: List[str] = []
        for d in earlier_dates:
            if d not in seen:
                seen.add(d)
                unique_dates.append(d)

        logger.info(
            "Found %d earlier date(s) than %s",
            len(unique_dates),
            current_appointment_date,
        )
        return unique_dates

    # ------------------------------------------------------------------
    # High-level orchestration
    # ------------------------------------------------------------------

    def check_dates_for_user(
        self,
        user_id: str,
        email: str,
        password: str,
        appointment_date: str,
    ) -> List[str]:
        """
        Full automation flow for a single user.

        Accepts explicit parameters so that only `password` is tainted;
        `user_id` and `appointment_date` are clean variables that are safe to log.
        Never logs the password itself.
        """
        if not email or not password or not appointment_date:
            logger.error(
                "check_dates_for_user: missing required fields for user_id=%s",
                user_id,
            )
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
            # Clear password from local scope immediately after use
            del password

            if not login_ok:
                logger.error(
                    "Login failed for user_id=%s; aborting date check",
                    user_id,
                )
                return []

            nav_ok = self._navigate_to_appointment_page()
            if not nav_ok:
                logger.error(
                    "Navigation failed for user_id=%s; aborting date check",
                    user_id,
                )
                return []

            return self.get_available_dates(appointment_date)

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error in check_dates_for_user for user_id=%s: %s",
                user_id,
                exc,
            )
            return []

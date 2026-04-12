"""
Selenium automation utilities for the USA visa scheduling website.
Navigates the AIS portal to retrieve available appointment dates.
"""

from __future__ import annotations

import logging
import os
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

            # Accept privacy policy checkbox
            try:
                checkbox = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//label[contains(., 'Política de Privacidade')]/..//input[@type='checkbox']")
                    )
                )
                if not checkbox.is_selected():
                    checkbox.click()
            except TimeoutException:
                logger.warning("Privacy policy checkbox not found; skipping")

            # Click submit button
            submit_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//input[@value='Acessar'] | //button[contains(., 'Acessar')]")
                )
            )
            submit_btn.click()

            # Verify login succeeded by waiting for post-login indicator
            wait.until(EC.url_contains("/groups/"))
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
            logger.error("Login timed out – possible CAPTCHA or invalid credentials")
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

        try:
            # Step 1 – groups page
            group_url = f"{BASE_URL}/groups/{self._group_id}"
            logger.info("Navigating to group page: %s", group_url)
            self.driver.get(group_url)

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

            # Extract schedule_id
            parts = current_url.rstrip("/").split("/")
            if "schedule" in parts:
                idx = parts.index("schedule")
                if idx + 1 < len(parts):
                    self._schedule_id = parts[idx + 1]
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

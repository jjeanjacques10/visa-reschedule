from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def get_requests_session_from_driver(driver) -> Optional[requests.Session]:
    if driver is None:
        return None

    session = requests.Session()
    try:
        for cookie in driver.get_cookies():
            session.cookies.set(
                cookie.get("name"),
                cookie.get("value"),
                domain=cookie.get("domain"),
                path=cookie.get("path"),
            )
    except Exception as exc:
        logger.debug("Failed to copy cookies to requests session: %s", exc)

    try:
        ua = driver.execute_script("return navigator.userAgent")
        if ua:
            session.headers.update({"User-Agent": str(ua)})
    except Exception:
        pass

    session.headers.update({"Accept": "application/json, text/javascript, */*; q=0.01"})
    return session


def fetch_available_days_json(base_url: str, schedule_id: str, facility_id: str, driver) -> list[str]:
    """Fetch available days via AIS JSON endpoint (if enabled in current portal version)."""
    if not facility_id or not schedule_id:
        return []

    session = get_requests_session_from_driver(driver)
    if session is None:
        return []

    url = f"{base_url}/schedule/{schedule_id}/appointment/days/{facility_id}.json"
    params = {"appointments[expedite]": "false"}

    try:
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            logger.debug("Days JSON request failed: %s status=%s", resp.url, resp.status_code)
            return []
        data = resp.json()
    except Exception as exc:
        logger.debug("Days JSON request error for facility_id=%s: %s", facility_id, exc)
        return []

    days: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("date"):
                days.append(str(item["date"]))
    return days

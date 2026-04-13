from __future__ import annotations

from selenium.common.exceptions import WebDriverException


def js_click(driver, element) -> bool:
    """Best-effort click using JS (handles hidden/styled elements)."""
    if driver is None:
        return False
    try:
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        return False


def safe_click(driver, element) -> bool:
    """Click with scroll-into-view + JS fallback."""
    if driver is None:
        return False

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            element,
        )
    except WebDriverException:
        pass
    except Exception:
        pass

    try:
        element.click()
        return True
    except Exception:
        return js_click(driver, element)

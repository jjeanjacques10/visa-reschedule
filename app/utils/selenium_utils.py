"""Backward-compatible wrapper for Selenium automation.

The implementation has been split into multiple modules under `app.utils.selenium`.
This file remains as a stable import path for the rest of the codebase.
"""

from app.utils.selenium import SeleniumUtils

__all__ = ["SeleniumUtils"]

"""Constants for the Octa EV Charger integration."""

from __future__ import annotations

import logging

DOMAIN = "octa_ev_charger"
LOGGER = logging.getLogger(__package__)

CONF_STATION_ID = "station_id"
CONF_TOKEN = "token"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10

# Shown in the setup form. Kept out of translations: hassfest rejects URLs there.
EXAMPLE_URL = "https://ev.example.com"

MIN_CURRENT_A = 6
DEFAULT_MAX_CURRENT_A = 32

# Delay before re-polling after a start/stop command so the station can react.
COMMAND_REFRESH_DELAY = 2

# OCPP-style connector statuses (compared lower-case).
PLUGGED_IN_STATUSES = {
    "preparing",
    "charging",
    "suspendedev",
    "suspendedevse",
    "finishing",
}
PROBLEM_STATUSES = {"faulted", "unavailable"}

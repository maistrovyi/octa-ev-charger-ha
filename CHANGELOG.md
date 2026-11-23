# Changelog

Release notes for every version are generated automatically on the
[GitHub Releases](https://github.com/maistrovyi/octa-ev-charger-ha/releases) page.

## 26.11.0

First public release.

- UI setup with server URL, station ID and token; re-authentication when the token is rejected.
- One device per station: per-port charging switch, current-limit slider, status, plugged-in and
  problem sensors, power/current/voltage/temperature/battery readings, session and lifetime energy.
- Station online sensor and total power.
- Configurable polling interval (default 30 s).
- Diagnostics download with server URL, station ID and token redacted.
- English and Ukrainian translations for setup, entity names and error messages.

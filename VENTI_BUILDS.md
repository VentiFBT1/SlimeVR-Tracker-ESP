# Venti v0.7.4 firmware variants

`test/venti-v074-battery-protection` contains both sensor builds. They share the same ESP32-C3 board settings and battery-protection code; select the firmware that matches the installed sensor.

| Tracker sensor | PlatformIO environment | CI binary |
| --- | --- | --- |
| Regular Venti / LSM6DSV | `esp32c3` (default) | `esp32c3-firmware.bin` |
| ICM-45686 | `esp32c3_icm45686` | `esp32c3_icm45686-firmware.bin` |

Build locally:

```sh
pio run -e esp32c3
pio run -e esp32c3_icm45686
```

Local outputs are `.pio/build/<environment>/firmware.bin`. Running `python ci/build.py` builds both and copies the named binaries into `build/`. GitHub Actions uploads them together in its `binaries` artifact when this branch is pushed or the workflow runs manually.

The ICM environment inherits the regular build's board, packages and flags, then overrides `IMU` at compile time. These are two firmware files, rather than one binary that detects the sensor automatically.

The existing experimental 3.50 V battery warning/sleep thresholds and 30-second sleep delay are unchanged. This branch consolidation does not establish hardware validation of those thresholds.

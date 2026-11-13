# Venti ESP-NOW one-tracker test

Branch: `test/venti-espnow`, based on
`test/venti-v074-battery-protection` at `6f208e35f272a04b1429befce96fc25304a5f793`.

Build the tracker with `pio run -e esp32c3_espnow`. The original
`pio run -e esp32c3` remains Wi-Fi/UDP. Build the receiver using
`tools/espnow-receiver/README.md`. These are two different firmware images
for two different processors; they are not interchangeable.

The tracker retains its LSM6DSV sensor, 90-degree rotation, SDA6/SCL4,
active-low GPIO0 status LED, GPIO3 battery ADC and 150k/150k divider,
and the existing 3.50 V filtered low-battery cutoff with 30-second dwell.
Start the test with a charged tracker. Saved pairing uses a separate NVS
namespace, leaving the existing DeviceConfig and calibration file formats intact.

## First hardware test

1. Confirm the exact SlimeVR Server beta version and the flash sizes reported by
   esptool for both devices. Back up each device's current flash before writing.
2. Flash the receiver image to the ESP32-S3 dongle, and the ESP-NOW tracker image
   to just one ESP32-C3 tracker. Use the build's bootloader/partition addresses;
   `firmware.bin` is an application image, not a merged image for address zero.
   Do not erase the tracker filesystem as part of an ordinary application update.
3. Open receiver serial at 115200 baud. Wait for its initial channel scan to end.
   Press its GPIO0 button once, or send `pair` followed by Enter.
4. Start the tracker. With no saved receiver it enters pairing mode automatically.
   To request it manually, open the tracker's serial console at 115200 and send
   `PAIR`. Its physical boot button is not a pairing button.
5. Look for successful pairing, assigned tracker ID, and connected-to-gateway
   messages. Confirm that the tracker appears in SlimeVR and rotates correctly.
6. Check battery voltage, then power-cycle tracker and receiver to confirm
   automatic reconnection. Test a short session before adding more trackers.

Tracker `UNPAIR` removes its saved receiver without deleting sensor calibration.
USB is the update method for this first test; network OTA is not enabled in the
ESP-NOW build. Receiver long-press unpairs trackers, so use a short press to pair.

Compile success establishes build compatibility. Pairing, radio reliability,
motion axes, and low-battery behavior still require physical testing.

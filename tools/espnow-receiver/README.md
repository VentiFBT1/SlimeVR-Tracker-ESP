# Receiver for the Venti ESP-NOW tracker test

Uses mitzey234/SlimeVR-Receiver-ESP-Now at commit
`439c73d5cfe334b529f2d30e90b7b087fae5f9fe`. No additional GitHub repository
or receiver branch is required. The matching tracker transport was ported from
mitzey234/SlimeVR-Tracker-ESP `f91a1ffa2a7b55b3b2be6c45bf4798f08323083a`.
The upstream MIT/Apache notices and licenses apply to the ported source.

```
python tools/espnow-receiver/prepare.py .receiver-build
pio run -d .receiver-build -e venti_s3fn8
```

Hardware: supplied ESP32-S3-Dongle v1.0g schematic, ESP32-S3FN8,
8 MB flash, no PSRAM, button GPIO0 active low, blue LED GPIO1 active high.
USB uses the S3 native OTG port, HID VID 0x1209/PID 0x7690.
Arduino 3.0.1 and PlatformIO's espressif32 6.7.0 are pinned to match the tracker.

The small upstream patch uses the ESP32 esp_wifi_set_channel() API with its
ESP_OK (zero) success result; Arduino 3.0.1's WiFi.setChannel also returns an
integer error code, not bool. It checks channel storage writes and prevents
an unsuccessful save from automatically restarting environment scans.
The CI host regression executes the real channel-save method against successful
and failed radio/storage cases. Other fixes include filename casing for Linux, explicitly
includes USB CDC declarations, initializes the radio rate configuration, and
validates tracker data frame length before forwarding it. It also checks wire
structure sizes at compile time.

The vendor's wireless-SD test binary is not used.

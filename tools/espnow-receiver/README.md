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

Receiver test4 defers received frames through a bounded, zero-wait FreeRTOS
queue. Only the main loop processes messages, sends responses, updates tracker
lists, writes saved pairings, and touches HID report FIFOs. This removes the
Wi-Fi-callback/main-loop send-mutex cycle and concurrent vector/FIFO mutation.
Disconnect-all and timeout cleanup do not reuse invalidated vector iterators.
The `health` command reports queue drops and per-tracker motion PPS, last-motion
age, and missed heartbeats. It does not enable streaming.

CI runs the actual queue, callback, drain, and disconnect methods with ten
simulated 100-Hz senders, checks copied callback buffers and zero-wait overload,
and enables checked STL iterators. This is a software regression, not proof of
ten-tracker RF/USB capacity. First validate sustained motion and repeated tracker
power-cycle reconnection with one physical tracker; then increase tracker count.

Receiver test5 addresses USB failure modes observed after test4. CDC and HID
state are initialized before USB enumeration. CDC TX calls TinyUSB's bounded
write directly instead of the SDK's retry loop, and console opens cannot trigger
the SDK's automatic reboot sequence (use the hardware BOOT button for flashing).
HID reports are submitted without waiting for completion on the main-loop task;
reports remain queued if submission fails. Empty receiver keep-alives every
50 ms avoid SlimeVR's idle-device reopen path without fabricating tracker data.
Console input is bounded to 64 bytes per loop and 256 bytes per command.

These changes address concrete USB scheduling hazards and protocol mismatch;
they do not establish the root cause of Windows Code 43. Hardware validation is
still required, including idle, motion, reconnect and opening/closing diagnostics.

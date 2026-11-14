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
Receiver Test7 pins pioarduino 55.03.312-1 (Arduino 3.3.12, IDF 5.5.5)
and PlatformIO Core 6.2.0. The tracker keeps its existing framework and Test2
firmware; matching wire formats do not require matching SDK versions.

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

Receiver Test6 paces HID submissions to at most one attempt per millisecond and
yields the main loop for one RTOS tick. Test5's hardware diagnostics showed
millions of unsuccessful submissions during a short run; spinning on a busy
endpoint is unnecessary CPU load. The host regression now calls the real tick
method 100,000 times with a busy endpoint at one timestamp and requires only one
submission attempt. Queued reports are retained. Health adds internal chip
temperature, and the standalone temperature command uses the hybrid USB stream.
These are targeted scheduling fixes; no hardware-stability claim is made.

Receiver Test7 changes the receiver framework bundle only. The upstream receiver
master still matches our pinned source revision; the donor tracker `esp-now`
branch also still matches our pinned revision. The separate `espnow` branch is
an older divergent implementation, not a later update to the donor.

The upstream receiver uses a moving pioarduino stable bundle; our previous
overlay instead pinned Arduino 3.0.1. Espressif issue #10307 documents S2/S3
CDC + HID stalls, and both the maintainer and reporter confirmed their reproducer
worked on Arduino 3.3.8. This is a closely related failure mode, not proof that
it caused our Windows USB descriptor errors. Later TinyUSB CDC stream races
also received fixes (TinyUSB #3465). Test7 uses a coherent, pinned current
bundle rather than adding more application-level workarounds.

References checked 2026-11-13:
- https://github.com/espressif/arduino-esp32/issues/10307#issuecomment-4527082826
- https://github.com/espressif/arduino-esp32/issues/10307#issuecomment-4527235640
- https://github.com/hathach/tinyusb/pull/3465
- https://github.com/pioarduino/platform-espressif32/releases/tag/55.03.312-1

Hardware acceptance remains pending: keep the tracker unchanged, test sustained
idle and moving operation, then repeated tracker and receiver power cycles.
If USB still fails, isolate HID/CDC with the receiver radio disabled before
changing tracker firmware or concluding that the dongle hardware is defective.

## Blank tracker provisioning

An application-only tracker update at 0x10000 cannot provision a blank chip.
Use `scripts/package_espnow_tracker.py BUILD --boot-app0 PATH --output FILE`
to merge the C3 bootloader at 0x0, partition table at 0x8000, matching Arduino
OTA initializer at 0xe000, and application at 0x10000. The script validates
C3 image checksums/digests, the partition MD5/capacity, and all merged offsets.
Use the boot components from the same tracker build and its matching framework.

The blank-board Test2 package uses the original Test2 CI artifact from commit
263d5bc5cbf2d0e5a9e704707cb02e46cc9d541b / run 43521817190. Its application is
identical to the tracker already paired with receiver Test7. The full image
is 1,253,680 bytes, SHA-256
`d1bddbf78a6c5114e4dac544255c360b60bc0bed6a1d599ca0cf9fdffa5f3de2`.
It is intended for blank test boards and can overwrite settings if used on an
existing tracker. The flasher exposes a separate blank-tracker selection.

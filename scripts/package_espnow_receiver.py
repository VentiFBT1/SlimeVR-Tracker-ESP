"""Validate and merge the receiver build for programming at address 0x0."""
from pathlib import Path
import hashlib
import os
import struct
import subprocess
import sys

build = Path(sys.argv[1]).resolve()
core = Path(os.environ.get("PLATFORMIO_CORE_DIR", Path.home() / ".platformio"))
frameworks = list((core / "packages").glob("framework-arduinoespressif32*"))
boot_apps = [p / "tools/partitions/boot_app0.bin" for p in frameworks
             if (p / "tools/partitions/boot_app0.bin").is_file()]
if not boot_apps:
    raise SystemExit("Missing Arduino boot_app0.bin")

image = (build / "firmware.bin").read_bytes()
if image[0] != 0xE9 or struct.unpack_from("<H", image, 12)[0] != 9:
    raise SystemExit("Expected an ESP32-S3 application image")

partitions = (build / "partitions.bin").read_bytes()
apps = []
for pos in range(0, len(partitions) - 31, 32):
    magic, kind, subtype, offset, size = struct.unpack_from("<HBBII", partitions, pos)
    if magic == 0x50AA and kind == 0:
        apps.append((offset, size))
if not apps or apps[0][0] != 0x10000 or len(image) > apps[0][1]:
    raise SystemExit("Unexpected app partition layout or oversized image")

output = build / "receiver-full-at-0x0.bin"
subprocess.run([
    sys.executable, "-m", "esptool", "--chip", "esp32s3", "merge_bin",
    "--flash_mode", "dio", "--flash_freq", "80m", "--flash_size", "8MB",
    "-o", str(output),
    "0x0", str(build / "bootloader.bin"),
    "0x8000", str(build / "partitions.bin"),
    "0xe000", str(boot_apps[0]),
    "0x10000", str(build / "firmware.bin"),
], check=True)
files = [build / x for x in ["firmware.bin", "receiver-full-at-0x0.bin",
                            "bootloader.bin", "partitions.bin"]]
(build / "SHA256SUMS.txt").write_text("".join(
    f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files
), encoding="utf-8")
print(f"Validated S3 image; merged file {output.name} is for address 0x0")

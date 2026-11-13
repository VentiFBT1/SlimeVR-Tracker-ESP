"""Prepare the pinned receiver project without creating another GitHub repository."""
from pathlib import Path
import shutil
import subprocess
import sys

UPSTREAM = "https://github.com/mitzey234/SlimeVR-Receiver-ESP-Now.git"
REVISION = "439c73d5cfe334b529f2d30e90b7b087fae5f9fe"
overlay = Path(__file__).resolve().parent
target = Path(sys.argv[1] if len(sys.argv) > 1 else ".receiver-build").resolve()
if target.exists():
    raise SystemExit(f"Choose an empty output path; {target} already exists")
subprocess.run(["git", "clone", "--no-checkout", UPSTREAM, str(target)], check=True)
subprocess.run(["git", "-C", str(target), "checkout", "--detach", REVISION], check=True)
subprocess.run(["git", "-C", str(target), "apply", str(overlay / "upstream-fixes.patch")], check=True)
shutil.copy2(overlay / "platformio-venti.ini", target / "platformio-venti.ini")
shutil.copy2(overlay / "boards/venti_s3fn8.json", target / "boards/venti_s3fn8.json")
shutil.copytree(overlay / "variants/venti_s3fn8", target / "variants/venti_s3fn8")
print(f"Prepared {target}; build with: pio run -d {target} -c platformio-venti.ini")

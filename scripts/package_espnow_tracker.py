"""Package a built ESP32-C3 tracker for blank boards; never access hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('build', type=Path)
parser.add_argument('--boot-app0', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
components = [(0, args.build / 'bootloader.bin'),
              (0x8000, args.build / 'partitions.bin'),
              (0xe000, args.boot_app0), (0x10000, args.build / 'firmware.bin')]
for name in ('bootloader.bin', 'firmware.bin'):
    path = args.build / name
    data = path.read_bytes()
    if data[0] != 0xe9 or struct.unpack_from('<H', data, 12)[0] != 5:
        raise SystemExit('Expected ESP32-C3 bootloader and application')
    result = subprocess.run([sys.executable, '-m', 'esptool', '--chip', 'esp32c3',
                             'image_info', '--version', '2', str(path)],
                            check=True, capture_output=True, text=True)
    if result.stdout.count('(valid)') < 2:
        raise SystemExit('Invalid image checksum/digest: ' + name)

table = components[1][1].read_bytes()
parts = []
for pos in range(0, len(table) - 31, 32):
    entry = table[pos:pos + 32]
    if entry[:2] == b'\xeb\xeb':
        if hashlib.md5(table[:pos]).digest() != entry[16:32]:
            raise SystemExit('Invalid partition MD5')
        break
    magic, kind, subtype, offset, size, label, flags = struct.unpack('<HBBII16sI', entry)
    if magic != 0x50aa or offset + size > 0x400000:
        raise SystemExit('Unexpected 4MB partition layout')
    parts.append(dict(type=kind, subtype=subtype, offset=offset, size=size,
                      label=label.split(b'\0')[0].decode()))
else:
    raise SystemExit('Missing partition MD5')
apps = [p for p in parts if p['type'] == 0]
if not apps or apps[0]['offset'] != 0x10000 or components[-1][1].stat().st_size > apps[0]['size']:
    raise SystemExit('Application does not fit the first partition at 0x10000')
ordered = sorted(parts, key=lambda p: p['offset'])
if any(a['offset'] + a['size'] > b['offset'] for a, b in zip(ordered, ordered[1:])):
    raise SystemExit('Overlapping partitions')
if args.boot_app0.stat().st_size != 8192:
    raise SystemExit('Unexpected OTA initializer size')
args.output.parent.mkdir(parents=True, exist_ok=True)
command = [sys.executable, '-m', 'esptool', '--chip', 'esp32c3', 'merge_bin',
           '--flash_mode', 'keep', '--flash_freq', 'keep', '--flash_size', 'keep',
           '-o', str(args.output)]
for offset, path in components:
    command.extend([hex(offset), str(path)])
subprocess.run(command, check=True)
merged = args.output.read_bytes()
end = 0
for offset, path in components:
    data = path.read_bytes()
    if offset < end or merged[end:offset] != b'\xff' * (offset - end) or merged[offset:offset + len(data)] != data:
        raise SystemExit('Merged image offsets, component bytes, or padding differ')
    end = offset + len(data)
if len(merged) != end:
    raise SystemExit('Unexpected merged image length')
manifest = dict(chip='esp32c3', flash_size='4MB', image_kind='merged', flash_offset='0x0',
                filename=args.output.name, bytes=len(merged),
                sha256=hashlib.sha256(merged).hexdigest(), partitions=parts,
                components=[dict(offset=hex(offset), filename=path.name,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                            for offset, path in components])
args.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: manifest[k] for k in ('filename', 'bytes', 'sha256', 'flash_offset')}))

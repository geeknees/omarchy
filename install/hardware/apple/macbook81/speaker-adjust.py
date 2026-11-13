#!/usr/bin/env python3
"""Adapt the pinned third-party speaker install to preserve Bluetooth preference.

Never patches arbitrary versions. If upstream code changes, fail for review
instead of blindly rewriting a root-executed script.
"""
from pathlib import Path
import sys


def patch_text(filename, text):
    if filename == "resume_recover.sh":
        before = "run_user pactl set-default-sink input.MacBook_Speaker 2>/dev/null || true"
        after = '''# Allow WirePlumber to restore a remembered Bluetooth sink after reconnect.
user_home=$(getent passwd "$U" | cut -d: -f6)
if ! grep -q '^default.configured.audio.sink=bluez_' \\
    "$user_home/.local/state/wireplumber/default-nodes" 2>/dev/null; then
    run_user pactl set-default-sink input.MacBook_Speaker 2>/dev/null || true
fi'''
    elif filename == "mb81-jack-switch.sh":
        before = 'set_default "$startup_sink"'
        after = '''# Avoid replacing a remembered Bluetooth default when starting the monitor.
if [[ "$last" == on ]] || ! pw-metadata -n default 0 default.configured.audio.sink 2>/dev/null | grep -q 'bluez_'; then
    set_default "$startup_sink"
fi'''
    else:
        raise ValueError("Unexpected speaker file")
    if after in text:
        return text
    if text.count(before) != 1:
        raise ValueError(f"{filename}: expected one known anchor (found {text.count(before)})")
    return text.replace(before, after, 1)


def main(argv):
    if len(argv) != 2:
        print("usage: speaker-adjust.py PINNED_CHECKOUT", file=sys.stderr)
        return 2
    root = Path(argv[1])
    patches = {}
    for name in ("resume_recover.sh", "mb81-jack-switch.sh"):
        file = root / name
        patches[file] = patch_text(name, file.read_text())
    for file, content in patches.items():
        file.write_text(content)
    print("Speaker startup adjusted to preserve Bluetooth default")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

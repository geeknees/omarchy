#!/usr/bin/env python3
"""MacBook8,1 Intel LPSS S3 state save/restore.

Only the two Wildcat Point-LP controllers used by the Apple SPI keyboard and
Bluetooth UART are accepted. The calling systemd-sleep hook ensures model match.
Offsets match the Intel LPSS private context (also saved by Linux acpi_lpss.c).

References: https://github.com/tvpittner/macbook8-1-fedora (GPL-2.0-or-later
project; this is a separate implementation using public register descriptions).
"""
import mmap
import os
import pathlib
import struct
import sys

ALLOWED = {"0000:00:15.4", "0000:00:15.5"}
OFFSETS = tuple(range(0x800, 0x824, 4))


def read_snapshot(blob):
    if not blob.exists():
        raise ValueError(f"missing register snapshot: {blob}")
    values = [int(v, 16) for v in blob.read_text().strip().split()]
    if len(values) != len(OFFSETS) or any(not 0 <= v <= 0xFFFFFFFF for v in values):
        raise ValueError("invalid LPSS register snapshot")
    if values[1] != 0x3:
        raise ValueError("snapshot does not contain an active controller")
    return values


def process(mode, pci, file, resource_root="/sys/bus/pci/devices"):
    if pci not in ALLOWED:
        raise ValueError(f"unrecognized LPSS controller: {pci}")
    if mode not in ("save", "restore"):
        raise ValueError(f"unrecognized command: {mode}")

    target = pathlib.Path(file)
    if mode == "restore":
        values = read_snapshot(target)

    # resource0 mmap is available when the SPI driver is unbound. The UART
    # remains bound and needs explicit iomem=relaxed; see setup's opt-in command.
    fd = os.open(f"{resource_root}/{pci}/resource0", os.O_RDWR | os.O_SYNC)
    try:
        with mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE) as mm:
            def get(offset):
                return struct.unpack_from("<I", mm, offset)[0]

            def put(offset, value):
                struct.pack_into("<I", mm, offset, value)

            if mode == "save":
                values = [get(off) for off in OFFSETS]
                if values[1] != 0x3 or not values[0] & 1:
                    raise ValueError(f"controller not active: reset={values[1]:08x} clock={values[0]:08x}")
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(".new")
                tmp.write_text(" ".join(f"{v:08x}" for v in values) + "\n")
                tmp.replace(target)
            else:
                # Reset before restoring private state. Clock is programmed last
                # so reset+chip select/interrupt mask registers are ready first.
                put(0x804, 0)
                put(0x804, 3)
                for off, value in zip(OFFSETS, values):
                    if off not in (0x800, 0x804):
                        put(off, value)
                put(0x800, values[0])
    finally:
        os.close(fd)
    return values


def main(argv):
    if len(argv) != 4:
        print("usage: lpss.py save|restore PCI-BDF SNAPSHOT", file=sys.stderr)
        return 2
    try:
        vals = process(*argv[1:])
    except (OSError, ValueError) as exc:
        print(f"LPSS {argv[1]} {argv[2]} FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"LPSS {argv[1]} {argv[2]}: " + " ".join(f"{v:08x}" for v in vals))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

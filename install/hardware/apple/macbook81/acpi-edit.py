#!/usr/bin/env python3
"""Patch a decompiled MacBook8,1 DSDT: remove conflicting SSDC UART child.

The Broadcom BLTH and SSDC ACPI devices share one UART; Linux serdev can only
attach to one child at a time. Operates only on a freshly extracted local DSDT.
Does not distribute copyrighted firmware tables.
"""
import pathlib
import re
import sys


class DSDTError(ValueError):
    pass


def patch(source):
    if not re.search(r"\bDevice\s*\(BLTH\)", source):
        raise DSDTError("Expected Bluetooth child BLTH is missing")
    found = list(re.finditer(r"^[ \t]*Device\s*\(SSDC\)\s*\n[ \t]*\{", source, re.M))
    if len(found) != 1:
        raise DSDTError(f"Expected exactly one SSDC device (found {len(found)})")
    match = found[0]
    begin = source.index("{", match.start(), match.end())
    depth = 0
    end = None
    for idx in range(begin, len(source)):
        if source[idx] == "{":
            depth += 1
        elif source[idx] == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        raise DSDTError("Unbalanced braces in SSDC device")
    while end < len(source) and source[end] in " \t":
        end += 1
    if end < len(source) and source[end] == "\n":
        end += 1
    source = source[:match.start()] + source[end:]

    # Increase the OEM revision so Linux accepts this DSDT as newer than EFI's.
    # iasl DefinitionBlock: (output, signature, revision, OEMID, OEMTableID, OEMRevision)
    pat = re.compile(r'(DefinitionBlock\s*\(\s*"[^"]*"\s*,\s*"DSDT"\s*,[^)]*,\s*)(0x[0-9a-fA-F]+)(\s*\))')
    m = pat.search(source)
    if not m:
        raise DSDTError("Could not identify the DSDT OEM revision")
    rev = int(m.group(2), 16)
    if rev == 0xFFFFFFFF:
        raise DSDTError("OEM revision cannot be incremented")
    source = source[:m.start(2)] + f"0x{rev + 1:08X}" + source[m.end(2):]
    return source


def main(argv):
    if len(argv) != 3:
        print("usage: acpi-edit.py INPUT.dsl OUTPUT.dsl", file=sys.stderr)
        return 2
    try:
        src = pathlib.Path(argv[1]).read_text()
        patched = patch(src)
        pathlib.Path(argv[2]).write_text(patched)
    except (OSError, DSDTError) as exc:
        print(f"DSDT patch failed: {exc}", file=sys.stderr)
        return 1
    print("Removed SSDC child, bumped DSDT OEM revision")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

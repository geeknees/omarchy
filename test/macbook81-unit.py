#!/usr/bin/env python3
"""Hardware-free tests for the MacBook8,1 integration patch."""
import importlib.util
import mmap
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "install/hardware/apple/macbook81"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acpi = load("macbook81_acpi", SRC / "acpi-edit.py")
lpss = load("macbook81_lpss", SRC / "lpss.py")
speaker = load("macbook81_speaker", SRC / "speaker-adjust.py")

FIXTURE = '''DefinitionBlock ("", "DSDT", 2, "APPLE ", "MacBook8", 0x00080001)
{
    Scope (\\_SB.PCI0.URT0)
    {
        Device (BLTH)
        {
            Name (_STA, 0x0F)
        }
        Device (SSDC)
        {
            Method (_STA, 0)
            {
                If (One)
                {
                    Return (0x0F)
                }
            }
        }
    }
}
'''


class ACPITests(unittest.TestCase):
    def test_remove_ssdc_but_keep_bluetooth_and_increment_revision(self):
        result = acpi.patch(FIXTURE)
        self.assertIn("Device (BLTH)", result)
        self.assertNotIn("Device (SSDC)", result)
        self.assertNotIn("Return (0x0F)", result)
        self.assertIn("0x00080002", result)
        self.assertIn("Scope (\\_SB.PCI0.URT0)", result)

    def test_reject_missing_ssdc(self):
        with self.assertRaises(acpi.DSDTError):
            acpi.patch(FIXTURE.replace("SSDC", "XYZ0"))

    def test_reject_missing_bluetooth(self):
        with self.assertRaises(acpi.DSDTError):
            acpi.patch(FIXTURE.replace("BLTH", "XYZ0"))

    def test_reject_duplicate_ssdc(self):
        with self.assertRaises(acpi.DSDTError):
            acpi.patch(FIXTURE.replace("Device (BLTH)", "Device (SSDC)"))

    def test_reject_invalid_revision(self):
        with self.assertRaises(acpi.DSDTError):
            acpi.patch(FIXTURE.replace("0x00080001", "0xFFFFFFFF"))


class LPSSTests(unittest.TestCase):
    def test_save_restore_full_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dev = root / "0000:00:15.4"
            dev.mkdir()
            regs = dev / "resource0"
            regs.write_bytes(b"\x00" * 4096)
            vals = [0x80190005, 3, 0x11223344, 7, 8, 9, 3, 0, 2]
            with regs.open("r+b") as f:
                for off, val in zip(lpss.OFFSETS, vals):
                    f.seek(off)
                    f.write(struct.pack("<I", val))
            snap = root / "spi.regs"
            self.assertEqual(lpss.process("save", "0000:00:15.4", snap, root), vals)
            with regs.open("r+b") as f:
                f.seek(0x800)
                f.write(b"\x00" * 36)
            self.assertEqual(lpss.process("restore", "0000:00:15.4", snap, root), vals)
            with regs.open("rb") as f:
                f.seek(0x800)
                actual = struct.unpack("<9I", f.read(36))
            self.assertEqual(actual, tuple(vals))

    def test_reject_non_whitelisted_pci_device(self):
        with self.assertRaises(ValueError):
            lpss.process("restore", "0000:01:00.0", "/tmp/nonexistent")

    def test_reject_malformed_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "regs"
            path.write_text("00000000\n")
            with self.assertRaises(ValueError):
                lpss.read_snapshot(path)


class AudioAdaptationTests(unittest.TestCase):
    def test_bluetooth_preference_preserved(self):
        for name, original in (
            ("resume_recover.sh", "run_user pactl set-default-sink input.MacBook_Speaker 2>/dev/null || true"),
            ("mb81-jack-switch.sh", 'set_default "$startup_sink"'),
        ):
            updated = speaker.patch_text(name, original)
            self.assertIn("bluez_", updated)
            self.assertEqual(speaker.patch_text(name, updated), updated)

    def test_do_not_modify_unknown_speaker_sources(self):
        with self.assertRaises(ValueError):
            speaker.patch_text("resume_recover.sh", "new upstream version")


if __name__ == "__main__":
    unittest.main(verbosity=2)

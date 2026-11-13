# MacBook8,1 (12-inch Early 2015) — Omarchy integration proposal

This is **an untested-on-hardware integration patch**, not a claim that all of
its components work together. It adapts observed Fedora and Arch fixes to
Omarchy's Arch Linux / Limine / mkinitcpio / UKI setup. Its **automatic path** is
model-gated; external drivers are explicitly opt-in.

## Installation behavior

For a fresh Omarchy install on `MacBook8,1`, `fix-macbook81.sh` installs:

- PIO-only Apple SPI keyboard/trackpad by disabling the faulty DesignWare DMA
  initcall (`initcall_blacklist=dw_pci_driver_init`). The existing Omarchy initramfs
  module file is made additive and the obsolete `macbook12-spi-driver-dkms` install
  is skipped **for this model only**. A USB keyboard is needed during initial ISO
  setup; the built-in keyboard should then work at LUKS unlock.
- `mem_sleep_default=s2idle` for a conservative first boot, plus the S3 LPSS
  register preservation/recovery hook. The hook only acts when `[deep]` is active;
  it restores all nine 32-bit private registers, including the Bluetooth UART
  `TX_INT_MASK` if Bluetooth S3 support is explicitly enabled.
- Broadcom BCM43602 firmware check and NetworkManager Wi-Fi power-save disable.
  The existing Omarchy brcmfmac WPA2/WPA3 workaround is not overwritten.
- `HibernateMode=shutdown`, addressing the reported S4 platform hibernation hang.

Omarchy's final boot-image rebuild handles newly installed core settings. The
installed management CLI remains available for incremental updates.

## Once Omarchy is booted

```
sudo omarchy-macbook81 status
sudo omarchy-macbook81 speakers
sudo omarchy-macbook81 camera
sudo omarchy-macbook81 bluetooth
```

Or, **after reviewing all third-party sources and making a backup**:

```
sudo omarchy-macbook81 all
```

`all` installs the base setup, then the pinned speaker DKMS project, FaceTime
HD DKMS + firmware extracted from Apple's update, and the local DSDT override
that hides `SSDC` so Broadcom Bluetooth can attach to the UART. These steps
are **not** safe for unattended first installs and can fail individually when
an external driver doesn't build on the running kernel. If that happens, fix
that component and rerun its specific command; `all` is not transactional.

### Test S3 before making it the default

Keep an external USB keyboard (or SSH) ready. After the hook is installed,
verify `/sys/power/mem_sleep` contains `deep`, then from an interactive terminal:

```
echo deep | sudo tee /sys/power/mem_sleep
sudo systemctl suspend
# After manually resuming, inspect:
journalctl -t omarchy-macbook81-s3 -b --no-pager
cat /proc/bus/input/devices | grep -A5 'Apple SPI'
```

If keyboard/trackpad recover consistently, you can opt into the lower-power
sleep state:

```
sudo omarchy-macbook81 s3-enable
sudo reboot
```

To return to safer idle sleep:

```
sudo omarchy-macbook81 s3-disable
sudo reboot
```

The S3 hook snapshots LPSS registers before sleep. Fedora's reference machine
reported ~0.3%/h of drain over about 38 hours (approximate, one device). Do not
assume that rate on other batteries or kernels.

### Bluetooth and S3

`bluetooth` modifies **only a DSDT extracted from the current machine**; it
compiles and injects the AML through mkinitcpio's `add_file_early`. It does **not**
flash or modify the Mac's actual firmware. Verify after reboot:

```
sudo dmesg | grep -i 'ACPI: Table Upgrade'
ls /sys/class/bluetooth/hci*
```

**Bluetooth recovery from deep S3 requires `iomem=relaxed`**, an extra opt-in
because it weakens MMIO access restrictions for privileged processes. Only after
confirming ordinary Bluetooth works, consider:

```
sudo omarchy-macbook81 bluetooth-s3-enable
sudo reboot
```

Undo with `bluetooth-s3-disable` or `bluetooth-remove`. The S3 hook restores
UART private registers, rebinds hci_bcm, and schedules a delayed reconnect of
Bluetooth devices (for example headphones), waiting for PipeWire recovery.

### Internal speakers and camera

- Speakers: pin `omnidecker/macbook8.1-speaker-driver` at `e4134fb272ba...`;
  installs three patched HDA DKMS modules plus PipeWire/WirePlumber routing.
  The upstream installer assumes Ubuntu's `update-initramfs`, so this wrapper
  rebuilds Omarchy's boot image after installation. The pinned scripts are
  locally adjusted to keep a remembered Bluetooth audio preference.
- Camera: pin `patjak/facetimehd` and `patjak/facetimehd-firmware`; compile with
  kernel headers via DKMS. Firmware 5.60.0 is extracted by the official upstream
  scripts from an Apple update, SHA-256-checked, **not redistributed** here.
  `bdc_pci` is blacklisted only when the DKMS driver installs successfully.

Third-party source is downloaded and executed as root for the speaker/camera
setup. A pinned Git commit makes the code auditable but does not make it
inherently safe. Inspect the upstream scripts and licences before running.

## Recovery, logging, removal

| Problem | Action |
| --- | --- |
| Keyboard fails after S3 | Use USB keyboard/SSH; `sudo omarchy-macbook81 s3-disable` and reboot |
| Repeated SPI timeouts | `journalctl -k -b | grep -E 'applespi|pxa2xx'`; check `cat /proc/cmdline` |
| Bluetooth does not register | `sudo omarchy-macbook81 bluetooth-remove`; rebuild/reboot |
| Audio goes silent | `sudo /usr/local/bin/mb81-resume-recover`; check DKMS modules and `wpctl status` |
| Camera breaks after kernel update | Check `dkms status` and matching kernel headers; remove with `camera-remove` |
| Restore base | `sudo omarchy-macbook81 remove-base` (leaves third-party options alone) |

Commands: `speakers-remove`, `camera-remove`, `bluetooth-remove`,
`bluetooth-s3-disable`, `s3-disable`, `remove-base`. Reboot after rollback.
Do not remove `base` before separately disabling S3; the core hook would vanish.

**Caution:** Omarchy installation normally wipes the disk. This patch does not
change the disk layout and cannot protect existing macOS installations.

## Verification and upstreaming

Run `bash test/shell.d/macbook81-test.sh` for software-only syntax and
DSDT/LPSS state unit checks. Still required on actual hardware:

1. Fresh install and encrypted LUKS boot without an external keyboard.
2. SPI PIO kernel log, keyboard, touchpad, Wi-Fi and suspend in s2idle.
3. A dozen manual S3 cycles with IRQ counters, UART and speaker checks.
4. Camera video capture, speaker sound and jack routing, Bluetooth pairing
   plus 30-minute A2DP streaming over multiple wake cycles.
5. Kernel updates, DKMS rebuilds, remove/reinstall idempotence, recovery.

We recommend review as **separate upstream PRs**: (1) SPI + conservative sleep
base, (2) S3 LPSS hook, (3) optional drivers + ACPI. The full patch is a proof
of concept for testing those boundaries together.

### Source credit

- [tvpittner/macbook8-1-fedora](https://github.com/tvpittner/macbook8-1-fedora) — S3 register-root-cause analysis, audio recovery, Bluetooth UART mapping.
- [projectmushroom/macbook81-linux-fixes](https://github.com/projectmushroom/macbook81-linux-fixes) — Arch/Omarchy field results, speaker validation.
- [channelramble/macbook81-linux](https://github.com/channelramble/macbook81-linux) — cross-distro camera/BT/PIO diagnostics and Apple firmware extraction path.
- [thomas-shirley/macbook8.1-speaker-driver](https://github.com/thomas-shirley/macbook8.1-speaker-driver) and [omnidecker fork](https://github.com/omnidecker/macbook8.1-speaker-driver) — speaker driver.
- [patjak/facetimehd](https://github.com/patjak/facetimehd) and [facetimehd-firmware](https://github.com/patjak/facetimehd-firmware) — camera driver and extractor.

Integration glue written independently under Omarchy's MIT licence. External
kernel sources, original documentation, and generated DSDT/Apple firmware have
separate licences and are not included in this patch.

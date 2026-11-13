# MacBook8,1 (2015 12-inch MacBook) hardware preparation for Omarchy.
# Keep experimental features out of the unattended installer. The user can
# install speakers/camera/Bluetooth with `sudo omarchy-macbook81 all` later.
macbook81_model="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
if [[ "$macbook81_model" == "MacBook8,1" ]]; then
  echo "Installing MacBook8,1 support (SPI, Wi-Fi, suspend hook)"
  mb81_source="$OMARCHY_INSTALL/hardware/apple/macbook81"
  sudo install -d -m 0755 /usr/local/lib/omarchy/macbook81
  for name in s3-sleep lpss.py acpi-edit.py initcpio-acpi speaker-adjust.py bt-reconnect; do
    sudo install -m 0755 "$mb81_source/$name" "/usr/local/lib/omarchy/macbook81/$name"
  done
  sudo install -Dm755 "$mb81_source/setup" /usr/local/sbin/omarchy-macbook81
  # The installer's final limine-update creates the UKI after all hardware setup.
  sudo env MB81_DEFER_REBUILD="${MB81_DEFER_REBUILD:-1}" /usr/local/sbin/omarchy-macbook81 base
fi

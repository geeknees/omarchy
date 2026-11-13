echo 'Set up integrated MacBook8,1 input, Wi-Fi and conservative suspend support'

# A fresh install already ran the hardware leaf and rebuilds UKIs at the end.
# For an existing installation, provide the same patch via the migration path.
[[ $(cat /sys/class/dmi/id/product_name 2>/dev/null || true) == MacBook8,1 ]] || exit 0
if [[ -x /usr/local/sbin/omarchy-macbook81 && -f /etc/limine-entry-tool.d/macbook81.conf ]]; then
  exit 0
fi
source_dir="${OMARCHY_PATH:-/usr/share/omarchy}/install"
[[ -f "$source_dir/hardware/apple/fix-macbook81.sh" ]] || {
  echo 'MacBook8,1 installer source unavailable; migration will retry' >&2
  exit 1
}
OMARCHY_INSTALL="$source_dir" MB81_DEFER_REBUILD=0 bash "$source_dir/hardware/apple/fix-macbook81.sh"

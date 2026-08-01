#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TVBOX_USER="${TVBOX_USER:-tvbox}"
TVBOX_HOME="${TVBOX_HOME:-/home/$TVBOX_USER}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this installer with sudo/root." >&2
  exit 1
fi

if ! id "$TVBOX_USER" >/dev/null 2>&1; then
  echo "ERROR: user '$TVBOX_USER' does not exist." >&2
  echo "Create the desktop user first, or rerun with TVBOX_USER=<user>." >&2
  exit 1
fi

if getent group input >/dev/null 2>&1 \
    && ! id -nG "$TVBOX_USER" | tr ' ' '\n' | grep -qx input; then
  usermod -a -G input "$TVBOX_USER"
  echo "Added $TVBOX_USER to input group for passive activity observation."
  echo "A new login session is required before that group is available."
fi

screensaver_packages=(
  gir1.2-gtk-3.0
  gir1.2-gtklayershell-0.1
  libgdk-pixbuf2.0-bin
  heif-gdk-pixbuf
)
missing_packages=()
for package in "${screensaver_packages[@]}"; do
  if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
    missing_packages+=("$package")
  fi
done
if [ "${#missing_packages[@]}" -gt 0 ]; then
  echo "Installing screensaver runtime packages: ${missing_packages[*]}"
  apt-get update
  apt-get install -y --no-install-recommends "${missing_packages[@]}"
fi

if ! python3 -c 'import gi; gi.require_version("Gtk", "3.0"); gi.require_version("GtkLayerShell", "0.1"); from gi.repository import Gtk, GtkLayerShell' >/dev/null 2>&1; then
  echo "ERROR: screensaver renderers require GTK 3 GI and gir1.2-gtklayershell-0.1." >&2
  exit 1
fi

if ! python3 - <<'PY'
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
available = {
    extension.lower()
    for image_format in GdkPixbuf.Pixbuf.get_formats()
    for extension in image_format.get_extensions()
}
required = {"jpg", "jpeg", "png", "webp", "heic", "heif", "avif"}
missing = sorted(required - available)
if missing:
    raise SystemExit("missing GdkPixbuf decoders: " + ", ".join(missing))
PY
then
  echo "ERROR: one or more required screensaver image decoders are unavailable." >&2
  exit 1
fi

backup_path() {
  local path="$1"
  if [ -e "$path" ] || [ -L "$path" ]; then
    local backup="${path}.bak.$(date +%Y%m%d-%H%M%S)"
    echo "Backing up $path -> $backup"
    mv "$path" "$backup"
  fi
}

install_file() {
  local src="$1"
  local dst="$2"
  local mode="$3"
  local owner="$4"

  install -D -m "$mode" -o "${owner%:*}" -g "${owner#*:}" "$src" "$dst"
}

link_bin() {
  local src="$1"
  local name
  name="$(basename "$src")"
  local dst="/usr/local/bin/$name"

  if [ -L "$dst" ] && [ "$(readlink -f "$dst")" = "$src" ]; then
    echo "Linked already: $dst -> $src"
    return 0
  fi

  backup_path "$dst"
  ln -s "$src" "$dst"
  echo "Linked: $dst -> $src"
}

echo "=== TVBox install from $REPO_DIR ==="

echo
echo "Installing /usr/local/bin links..."
find "$REPO_DIR/bin" -maxdepth 1 -type f -name 'tvbox*' ! -name '*.bak.*' | sort | while read -r script; do
  chmod 755 "$script"
  link_bin "$script"
done

echo
echo "Installing tvboxctl config..."
if [ ! -f /etc/tvboxctl.conf ]; then
  install_file "$REPO_DIR/config/tvboxctl.conf.example" /etc/tvboxctl.conf 0644 root:root
  echo "Installed /etc/tvboxctl.conf from example."
else
  echo "Keeping existing /etc/tvboxctl.conf."
fi

echo
echo "Installing passive diagnostic config..."
if [ ! -f "$TVBOX_HOME/.config/tvbox/tvbox-diag.conf" ]; then
  install_file "$REPO_DIR/config/tvbox-diag.conf.example" \
    "$TVBOX_HOME/.config/tvbox/tvbox-diag.conf" 0644 "$TVBOX_USER:$TVBOX_USER"
  echo "Installed user tvbox-diag config from example."
else
  echo "Keeping existing user tvbox-diag config."
fi

echo
echo "Installing screensaver configuration..."
screensaver_config="$TVBOX_HOME/.config/tvbox/screensaver.toml"
if [ ! -f "$screensaver_config" ]; then
  install_file "$REPO_DIR/config/screensaver.toml" \
    "$screensaver_config" 0644 "$TVBOX_USER:$TVBOX_USER"
  echo "Installed user screensaver configuration."
else
  echo "Keeping existing user screensaver configuration."
fi
if ! grep -q '^\[screensaver\.automatic\]$' "$screensaver_config"; then
  screensaver_backup="${screensaver_config}.bak.$(date +%Y%m%d-%H%M%S)"
  cp -a "$screensaver_config" "$screensaver_backup"
  {
    echo
    echo '[screensaver.automatic]'
    echo 'enabled = true'
    echo 'idle_state_stale_seconds = 5'
    echo 'reconcile_interval_seconds = 1'
    echo 'suppress_after_manual_stop = "until-next-idle-epoch"'
  } >> "$screensaver_config"
  chown "$TVBOX_USER:$TVBOX_USER" "$screensaver_config"
  chmod 0644 "$screensaver_config"
  echo "Added automatic idle policy; backup: $screensaver_backup"
fi

echo
echo "Installing canonical idle-state configuration..."
idle_config="$TVBOX_HOME/.config/tvbox/idle.toml"
if [ ! -f "$idle_config" ]; then
  install_file "$REPO_DIR/config/idle.toml" \
    "$idle_config" 0644 "$TVBOX_USER:$TVBOX_USER"
  echo "Installed user idle-state configuration."
else
  echo "Keeping existing user idle-state configuration."
fi
idle_candidate="$(mktemp)"
awk '
  BEGIN { in_kodi = 0; found = 0 }
  /^\[providers\.kodi\]$/ {
    found = 1
    in_kodi = 1
    print "[providers.kodi]"
    print "enabled = true"
    print "timeout_seconds = 600"
    print "required_sources = [\"flirc\", \"keyboard\", \"pointer\"]"
    print "observer_stale_seconds = 5"
    next
  }
  in_kodi && /^\[/ { in_kodi = 0 }
  !in_kodi { print }
  END {
    if (!found) {
      print ""
      print "[providers.kodi]"
      print "enabled = true"
      print "timeout_seconds = 600"
      print "required_sources = [\"flirc\", \"keyboard\", \"pointer\"]"
      print "observer_stale_seconds = 5"
    }
  }
' "$idle_config" > "$idle_candidate"
if ! cmp -s "$idle_candidate" "$idle_config"; then
  idle_backup="${idle_config}.bak.$(date +%Y%m%d-%H%M%S)"
  cp -a "$idle_config" "$idle_backup"
  install -m 0644 -o "$TVBOX_USER" -g "$TVBOX_USER" \
    "$idle_candidate" "$idle_config"
  echo "Enabled the safe Kodi idle provider; backup: $idle_backup"
fi
rm -f "$idle_candidate"

echo
echo "Installing labwc config..."
install_file "$REPO_DIR/config/labwc/rc.xml" "$TVBOX_HOME/.config/labwc/rc.xml" 0664 "$TVBOX_USER:$TVBOX_USER"
if [ -f "$REPO_DIR/config/labwc/environment" ]; then
  install_file "$REPO_DIR/config/labwc/environment" "$TVBOX_HOME/.config/labwc/environment" 0644 "$TVBOX_USER:$TVBOX_USER"
fi

echo
echo "Installing desktop autostart entries..."
if [ -d "$REPO_DIR/config/autostart" ]; then
  find "$REPO_DIR/config/autostart" -maxdepth 1 -type f -name '*.desktop' | sort | while read -r desktop_file; do
    install_file "$desktop_file" "$TVBOX_HOME/.config/autostart/$(basename "$desktop_file")" 0755 "$TVBOX_USER:$TVBOX_USER"
  done
fi

echo
echo "Installing user systemd units..."
if [ -d "$REPO_DIR/config/systemd-user" ]; then
  find "$REPO_DIR/config/systemd-user" -maxdepth 1 -type f -name '*.service' | sort | while read -r unit; do
    unit_dst="$TVBOX_HOME/.config/systemd/user/$(basename "$unit")"
    if [ -e "$unit_dst" ] && ! cmp -s "$unit" "$unit_dst"; then
      backup_path "$unit_dst"
    fi
    install_file "$unit" "$unit_dst" 0644 "$TVBOX_USER:$TVBOX_USER"
  done
fi
user_wants="$TVBOX_HOME/.config/systemd/user/default.target.wants"
install -d -m 0755 -o "$TVBOX_USER" -g "$TVBOX_USER" "$user_wants"
for unit_name in tvbox-overlay.service tvbox-screensaver-policy.service \
                 tvbox-activityd.service tvbox-idled.service \
                 tvbox-kodi-observer.service; do
  unit_path="$TVBOX_HOME/.config/systemd/user/$unit_name"
  wants_path="$user_wants/$unit_name"
  if [ -f "$unit_path" ] && [ ! -e "$wants_path" ] && [ ! -L "$wants_path" ]; then
    ln -s "$unit_path" "$wants_path"
    chown -h "$TVBOX_USER:$TVBOX_USER" "$wants_path"
    echo "Enabled user unit for next login: $unit_name"
  fi
done

echo
echo "Installing systemd drop-ins..."
if [ -d "$REPO_DIR/config/systemd-system" ]; then
  find "$REPO_DIR/config/systemd-system" -type f | sort | while read -r cfg; do
    rel="${cfg#"$REPO_DIR/config/systemd-system/"}"
    install_file "$cfg" "/etc/systemd/system/$rel" 0644 root:root
  done
fi

echo
echo "Installing Kodi TVBox addons..."
if [ -d "$REPO_DIR/kodi-addons" ]; then
  install -d -m 0775 -o "$TVBOX_USER" -g "$TVBOX_USER" "$TVBOX_HOME/.kodi/addons"
  find "$REPO_DIR/kodi-addons" -maxdepth 1 -mindepth 1 -type d | sort | while read -r addon; do
    dst="$TVBOX_HOME/.kodi/addons/$(basename "$addon")"
    rm -rf "$dst"
    cp -a "$addon" "$dst"
    find "$dst" -type d -name __pycache__ -prune -exec rm -rf {} +
    find "$dst" -type f -name '*.pyc' -delete
    chown -R "$TVBOX_USER:$TVBOX_USER" "$dst"
    echo "Installed Kodi addon: $(basename "$addon")"
  done
fi

echo
echo "Installing Kodi keymaps..."
if [ -d "$REPO_DIR/config/kodi/userdata/keymaps" ]; then
  install -d -m 0775 -o "$TVBOX_USER" -g "$TVBOX_USER" "$TVBOX_HOME/.kodi/userdata/keymaps"
  find "$REPO_DIR/config/kodi/userdata/keymaps" -maxdepth 1 -type f -name '*.xml' | sort | while read -r keymap; do
    install_file "$keymap" "$TVBOX_HOME/.kodi/userdata/keymaps/$(basename "$keymap")" 0644 "$TVBOX_USER:$TVBOX_USER"
  done
fi

echo
echo "Reloading systemd..."
systemctl daemon-reload || true

echo
echo "Install complete."
echo "Recommended next steps:"
echo "  1. Review /etc/tvboxctl.conf for local IPs/paths."
echo "  2. Reboot or restart the desktop session so labwc and autostart changes load."
echo "  3. Run: tvboxctl status"
echo "  4. Diagnostics are installed but not enabled. Start explicitly with:"
echo "     systemctl --user start tvbox-healthd.service"

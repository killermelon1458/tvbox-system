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

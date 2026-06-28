# TVBox System

This repo captures the current Raspberry Pi TVBox setup so it can be redeployed instead of living as one-off edits under `/usr/local/bin`, `/etc`, and `/home/tvbox`.

Current focus:

```text
1. Preserve the working system as it exists today.
2. Make the live scripts, config, and Kodi addons repo-owned.
3. Provide a practical install path for a replacement Pi.
```

Future architecture plans are in `docs/`, but many of those plans are not implemented yet. The current deployable baseline is documented here:

```text
docs/current-system-redeploy.md
```

## Quick Install

Expected clone location:

```bash
/opt/tvbox-system
```

Run:

```bash
sudo /opt/tvbox-system/install.sh
sudo reboot
```

Then verify:

```bash
tvboxctl status
readlink -f /usr/local/bin/tvbox-home
grep -n -A4 -B2 -E 'key="F12"|tvbox-home' /home/tvbox/.config/labwc/rc.xml
```

See `docs/current-system-redeploy.md` for required packages, manual setup, and known gaps.

# TVBox Boot, Storage, Service Cleanup, and Backup Notes

**Date:** 2026-06-30  
**Machine:** `tvbox`  
**User:** `tvbox`  
**Platform:** Raspberry Pi 5 / ARM64 / `aarch64`  
**Kernel observed during troubleshooting:** `6.12.47+rpt-rpi-2712`  
**Primary role:** Dedicated TVBox appliance for Kodi/Plex, YouTube TV mode, Spotify Connect, Moonlight/Sunshine, Steam/streaming clients, and remote/controller-driven living-room use.

---

## 1. Purpose

This document records the boot failure / slow boot troubleshooting session, the systemd service changes that were made, the storage-health concern that was discovered, and the emergency backup procedure started afterward.

The practical goals were:

```text
1. Understand why TVBox entered emergency mode / booted slowly.
2. Remove unnecessary boot blockers.
3. Fix services that failed because the user runtime directory was not ready.
4. Identify whether the SD card is trustworthy.
5. Create a full compressed image backup to the server before further writes or migration work.
```

---

## 2. Existing TVBox architecture relevant to this work

TVBox is intentionally built around Kodi as the home shell. Normal Kodi launch paths should use:

```bash
/usr/local/bin/tvbox-kodi
```

and not plain `kodi`, except when intentionally bypassing the TVBox wrapper for testing.

The existing design principle remains:

```text
All normal Kodi launches go through /usr/local/bin/tvbox-kodi.
All global Home behavior goes through /usr/local/bin/tvbox-home.
All external app handoffs should return through the TVBox wrapper layer.
```

Kodi is a GUI app and should launch inside the logged-in user desktop session, not as a root `Restart=always` service. This remains important because TVBox intentionally closes Kodi during external app handoff flows such as Moonlight, YouTube, and Spotify.

---

## 3. Initial symptoms

The TVBox booted into systemd emergency mode.

The screen showed a message like:

```text
You are in emergency mode.
Cannot open access to console, the root account is locked.
Press Enter to continue.
```

After pressing Enter, the system showed a TTY login and later eventually reached the desktop / Kodi. The user reported a black screen or flashing cursor before Kodi eventually appeared.

Important observation:

```text
The Pi was not fully dead.
The system could continue after interaction.
Kodi eventually launched.
This was a boot dependency / mount / device timeout problem, not simply a Kodi crash.
```

---

## 4. First diagnostic sweep

A boot diagnostic sweep was run to capture:

```text
systemctl --failed
systemd-analyze
systemd-analyze blame
systemd-analyze critical-chain
current boot warnings/errors
fstab and mount verification
lsblk / filesystem identity
power and thermal state
network state
HDMI / DRM state
Kodi logs
Raspotify logs
previous boot errors
TVBox wrapper/autostart state
```

The first useful findings were:

```text
Failed units:
  session-1.scope
  NetworkManager-wait-online.service

Boot timing:
  kernel: about 8.8s
  userspace: about 1m43s
  graphical.target appeared as about 5h32m only because the system sat in emergency mode until user interaction.
```

The biggest boot-time offenders in the initial diagnostic were:

```text
cloud-init-main.service                  ~1m41s
systemd-tmpfiles-clean.service           ~1m41s
NetworkManager.service                   ~1m08s
e2scrub_reap.service                     ~1m08s
raspotify-crash-report-generator.service  ~1m07s
ModemManager.service                     ~1m07s
user@1000.service                        ~1m07s
dev-mmcblk0p2.device                     ~1m07s
NetworkManager-wait-online.service       ~1m00s / failed
```

---

## 5. Actual emergency-mode cause

The emergency-mode boot was caused by a timeout waiting for the boot partition device:

```text
/dev/disk/by-partuuid/f7cde034-01
```

That device backs:

```text
/boot/firmware
```

The failure chain was:

```text
systemd waited for /dev/disk/by-partuuid/f7cde034-01
-> device timed out
-> fsck dependency failed
-> /boot/firmware mount dependency failed
-> local-fs.target failed
-> emergency mode started
```

After Enter was pressed from emergency mode, the same device appeared, `fsck.fat` ran on `/dev/mmcblk0p1`, and `/boot/firmware` mounted successfully.

Important conclusion:

```text
/etc/fstab was not obviously wrong.
The PARTUUID in fstab matched the live device.
The boot partition could mount once the device appeared.
The problem was more likely delayed/stalled SD-card/device readiness than a simple typo.
```

Relevant fstab state:

```fstab
proc /proc proc defaults 0 0
PARTUUID=f7cde034-01 /boot/firmware vfat defaults 0 2
PARTUUID=f7cde034-02 / ext4 defaults,noatime 0 1
```

Relevant live storage state:

```text
mmcblk0p1: vfat bootfs, mounted at /boot/firmware
mmcblk0p2: ext4 rootfs, mounted at /
root filesystem: rw,noatime
card size: about 239 GiB
root usage at the time: about 7%
```

---

## 6. Storage warning discovered

A later kernel log check showed this warning more than once in the same boot:

```text
mmc0: Card stuck being busy! __mmc_poll_for_busy
```

There were no confirmed lines like these at the time of the check:

```text
I/O error
Buffer I/O error
EXT4-fs error
```

but the warning is still significant.

Working interpretation:

```text
The SD card or SD-card interface is stalling.
This matches the earlier /boot/firmware device timeout.
The card is not proven dead today, but it is no longer trusted as long-term storage.
Further heavy writes should be avoided until a backup exists.
```

Decision:

```text
Make a full backup image immediately before deeper tuning or migration work.
```

---

## 7. Other hardware / boot observations

### 7.1 Power state

Power looked healthy during diagnostics:

```text
vcgencmd get_throttled: throttled=0x0
temperature: about 51 C
```

No undervoltage/throttling evidence was found in the diagnostic output.

### 7.2 HDMI state

The TV was detected on the second HDMI connector path during diagnostics:

```text
card1-HDMI-A-2 connected/enabled
Hisense Electric Co.
1920x1080 preferred/current, 60 Hz
```

No HDMI kernel-mode override was applied during this session.

### 7.3 USB warning

The logs also showed USB enumeration problems, including error `-71` on a USB path such as:

```text
usb 1-1.1.1: device descriptor read/64, error -71
Device not responding
unable to enumerate USB device
```

This was not treated as the direct cause of the emergency-mode boot, but it remains a separate reliability concern. It may be related to a USB receiver, hub, controller, or flaky USB device.

---

## 8. Raspotify boot race

Raspotify initially failed during boot with a namespace error similar to:

```text
Failed to set up mount namespacing: /run/user/1000: No such file or directory
Failed at step NAMESPACE spawning /usr/bin/librespot
```

Cause:

```text
The Raspotify system service tried to use /run/user/1000 before the tvbox user runtime directory existed.
```

Fix applied:

```bash
sudo mkdir -p /etc/systemd/system/raspotify.service.d

sudo tee /etc/systemd/system/raspotify.service.d/tvbox-user.conf >/dev/null <<'RASPOEOF'
[Unit]
Wants=user-runtime-dir@1000.service user@1000.service
After=user-runtime-dir@1000.service user@1000.service

[Service]
User=tvbox
Group=tvbox

Environment=HOME=/home/tvbox
Environment=USER=tvbox
Environment=LOGNAME=tvbox
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=DISPLAY=:0

ProtectHome=false
PrivateTmp=false

# Use /run/user instead of /run/user/1000 so systemd does not fail
# namespace setup if the user runtime dir is not created yet.
ReadWritePaths=/home/tvbox /run/user /tmp
RASPOEOF

sudo systemctl daemon-reload
sudo systemctl restart raspotify
```

Result:

```text
Raspotify restarted cleanly.
After reboot, raspotify.service was active/running with /usr/bin/librespot.
The namespace failure did not recur in the checked boot.
```

Note:

```text
This is a newer override than older Spotify documentation that used ReadWritePaths=/home/tvbox /run/user/1000 /tmp.
The safer boot-race-resistant version uses /run/user and orders after user-runtime-dir@1000/user@1000.
```

---

## 9. Boot-service cleanup performed

### 9.1 Reset failed units

```bash
sudo systemctl reset-failed
systemctl --failed --no-pager
```

Result:

```text
0 failed units listed
```

### 9.2 Disable and mask NetworkManager wait-online

`NetworkManager-wait-online.service` was failing and blocking boot without adding value for this TVBox appliance.

Commands:

```bash
sudo systemctl disable --now NetworkManager-wait-online.service
sudo systemctl mask NetworkManager-wait-online.service
```

Expected effect:

```text
Do not hold boot waiting for NetworkManager's online target.
Let TVBox continue to GUI/Kodi without requiring network-online success.
```

### 9.3 Disable cloud-init

Cloud-init was a major boot-time offender and is not needed for the current appliance role.

Commands:

```bash
sudo touch /etc/cloud/cloud-init.disabled
sudo systemctl disable --now cloud-init.service cloud-init-local.service cloud-config.service cloud-final.service cloud-init-main.service 2>/dev/null || true
```

Expected effect:

```text
Prevent cloud-init from running on boot.
Remove a ~1m40s boot offender.
```

### 9.4 Disable ModemManager

ModemManager was another significant boot offender and is not needed unless using cellular/modem hardware.

Command:

```bash
sudo systemctl disable --now ModemManager.service
```

### 9.5 Disable and mask CUPS

CUPS was not needed for this TVBox and still had active trigger units after the first disable.

Initial command:

```bash
sudo systemctl disable --now cups.service
```

System reported that these trigger units were still active:

```text
cups.path
cups.socket
```

Final cleanup:

```bash
sudo systemctl disable --now cups.service cups.socket cups.path cups-browsed.service 2>/dev/null || true
sudo systemctl mask cups.service cups.socket cups.path cups-browsed.service 2>/dev/null || true
sudo systemctl reset-failed
```

Expected effect:

```text
No CUPS scheduler/socket/path activation during boot.
```

### 9.6 Delay Tailscale startup

Tailscale was a major boot delay in one post-cleanup boot:

```text
tailscaled.service: about 41.5s
graphical.target: about 46.9s
```

Because Tailscale is useful for remote access but does not need to block Kodi startup, it was converted to delayed startup.

Commands used:

```bash
sudo systemctl disable --now tailscaled.service

sudo tee /etc/systemd/system/tailscaled-delayed.service >/dev/null <<'TSDELAYEOF'
[Unit]
Description=Delayed Tailscale startup

[Service]
Type=oneshot
ExecStart=/bin/systemctl start tailscaled.service
TSDELAYEOF

sudo tee /etc/systemd/system/tailscaled-delayed.timer >/dev/null <<'TSTIMEREOF'
[Unit]
Description=Start Tailscale after TVBox boot

[Timer]
OnBootSec=90s
Unit=tailscaled-delayed.service

[Install]
WantedBy=timers.target
TSTIMEREOF

sudo systemctl daemon-reload
sudo systemctl enable --now tailscaled-delayed.timer
```

Result:

```text
tailscaled.service became disabled but could still be started by the delayed timer.
tailscaled-delayed.timer became enabled.
tailscaled later started and connected successfully.
```

Note:

```text
A later boot still showed tailscaled-delayed.service in systemd-analyze blame because the system had other boot delay behavior before graphical.target. The timer itself worked, but further boot timing analysis may still be needed after the SD-card backup is complete.
```

---

## 10. Post-change boot results

After the first round of cleanup and reboot:

```text
Startup finished in about 8.5s kernel + 47.0s userspace = 55.5s total.
graphical.target reached after about 47.0s.
0 failed units.
/boot/firmware mounted normally.
Raspotify active/running.
NetworkManager-wait-online/cloud-init/ModemManager did not recur as failed boot blockers.
```

The boot-firmware flow looked healthy in that boot:

```text
Expecting device /dev/disk/by-partuuid/f7cde034-01
Found device after about 1 second
fsck.fat ran on /dev/mmcblk0p1
Mounted /boot/firmware
```

But the storage warning appeared afterward:

```text
mmc0: Card stuck being busy! __mmc_poll_for_busy
```

After the Tailscale delayed-timer change and reboot, another captured boot showed:

```text
Startup finished in about 8.5s kernel + 2m42.7s userspace = 2m51.1s total.
0 failed units.
/boot/firmware still mounted normally.
tailscaled eventually connected.
```

New/remaining boot-time suspects from that boot included:

```text
plymouth-read-write.service             ~1m55s
tailscaled-delayed.service              ~44s
accounts-daemon.service                 ~42s
udisks2.service                         ~42s
rpi-eeprom-update.service               ~42s
avahi-daemon.service                    ~42s
bluetooth.service                       ~42s
e2scrub_reap.service                    ~42s
dbus.service                            ~42s
rpcbind.service                         ~33s
nfs-blkmap.service                      ~32s
```

Interpretation:

```text
The original emergency-mode cause was fixed or did not recur in the checked boots.
The boot is still inconsistent.
Because storage stalls were observed, service tuning should pause until a full backup exists.
```

---

## 11. Tailscale observations

Tailscale later reached:

```text
Active: active/running
Status: Connected
TVBox Tailscale IP: 100.81.25.110
```

Some Tailscale log messages were observed:

```text
TPM: error opening /dev/tpmrm0: no such file or directory
System DNS config not ideal. /etc/resolv.conf overwritten.
resolv.conf changed from what we expected / trampled
```

Interpretation:

```text
The missing TPM device is expected on this Pi and is not a boot failure.
The DNS trample warnings are a NetworkManager/Tailscale DNS-management issue, but Tailscale still connected.
This is not the immediate storage emergency.
```

---

## 12. Backup decision

Because of:

```text
1. Earlier /boot/firmware device timeout.
2. Repeated mmc0 Card stuck being busy warnings.
3. Existing TVBox customization and repo/script work.
4. Risk of SD-card deterioration.
```

we decided to create a full compressed image of the entire SD card immediately.

Important decision:

```text
Do not zero-fill free space first.
```

Reason:

```text
Zero-filling free space would write heavily to a suspect SD card.
The backup should read the card with minimal additional writes.
```

Important decision:

```text
Do not write the full image to /home/tvbox/Documents/tvbox_image.
```

Reason:

```text
That path is on the same SD card being imaged.
Writing the full raw/compressed image there would back the card up onto itself, fill the root filesystem, distort the live image, and add heavy writes to the suspect storage.
```

---

## 13. SMB backup target

The intended server share is:

```text
smb://100.126.102.121/12tb/
```

Username:

```text
nathan
```

The target backup directory is:

```text
/malachi/tvbox
```

Because the Zorin laptop GVFS path was local to the laptop and not mounted on TVBox, the share was mounted directly on TVBox with CIFS.

Mount point:

```bash
/mnt/tvbox-backup
```

Mount command used:

```bash
command -v mount.cifs >/dev/null || sudo apt update && sudo apt install -y cifs-utils

sudo mkdir -p /mnt/tvbox-backup

sudo mount -t cifs '//100.126.102.121/12tb' /mnt/tvbox-backup \
  -o username=nathan,vers=3.0,iocharset=utf8,uid=tvbox,gid=tvbox,file_mode=0660,dir_mode=0770,noperm
```

The mount succeeded after entering Nathan's SMB password.

Write test:

```bash
mkdir -p /mnt/tvbox-backup/malachi/tvbox
touch /mnt/tvbox-backup/malachi/tvbox/.write-test
rm /mnt/tvbox-backup/malachi/tvbox/.write-test
df -h /mnt/tvbox-backup
```

Observed result:

```text
Filesystem: //100.126.102.121/12tb
Size: 11T
Used: 1.4T
Available: 9.5T
Use: 13%
Mounted on: /mnt/tvbox-backup
```

Conclusion:

```text
SMB share mounted successfully.
Write permission works.
Destination path exists.
There is enough space for a full compressed SD-card image.
```

---

## 14. Full SD-card image procedure

Because the backup could take a long time and should survive SSH disconnects, tmux was recommended:

```bash
command -v tmux >/dev/null || sudo apt install -y tmux
tmux new -s tvbox-backup
```

Inside tmux, the recommended imaging command was:

```bash
sudo systemctl stop lightdm 2>/dev/null || true
sudo systemctl stop raspotify 2>/dev/null || true
sync

cd /mnt/tvbox-backup/malachi/tvbox

STAMP="$(date +%Y%m%d-%H%M%S)"
IMAGE="tvbox-sd-${STAMP}.img.gz"

set -o pipefail

sudo dd if=/dev/mmcblk0 bs=16M iflag=fullblock conv=noerror,sync status=progress \
  | gzip -1 > "$IMAGE"

sync

ls -lh "$IMAGE"
sha256sum "$IMAGE" | tee "$IMAGE.sha256"
gzip -t "$IMAGE" && echo "gzip integrity check: OK"
```

Rationale for each part:

```text
stop lightdm: reduce GUI/Kodi writes while imaging live storage
stop raspotify: reduce audio/service writes while imaging
sync: flush pending writes before readout
dd if=/dev/mmcblk0: image the entire SD card, including partition table and both partitions
bs=16M: large block size for throughput
iflag=fullblock: make dd read full blocks
conv=noerror,sync: continue through read errors if possible and pad unreadable blocks
gzip -1: fast compression, lower CPU cost on Pi
sha256sum: record file integrity checksum
gzip -t: verify compressed stream integrity
```

Do not stop:

```text
NetworkManager
Tailscale
```

Reason:

```text
The SMB target is on a Tailscale IP / network path. Killing networking would break the mounted destination.
```

Tmux controls:

```text
Detach: Ctrl+B, then D
Reattach: tmux attach -t tvbox-backup
```

---

## 15. Expected backup size and duration

The SD card is about:

```text
239 GiB / 256 GB nominal
```

The backup reads the entire SD card, not just used files.

Expected compressed image size:

```text
Best case:   15-35 GB
Normal case: 25-80 GB
Bad case:    100-239 GB
```

The bad case happens if unused SD-card space contains old/random data that does not compress well.

Expected duration:

```text
Fast:      45-90 minutes
Normal:   1.5-3 hours
Slow:      3-6+ hours
Very slow: possible if SD stalls or network/SMB is slow
```

Rough timing by throughput:

```text
80 MB/s: about 50 minutes
50 MB/s: about 1 hour 25 minutes
30 MB/s: about 2 hours 25 minutes
20 MB/s: about 3 hours 35 minutes
10 MB/s: about 7 hours
```

Progress can be estimated from the `dd status=progress` output.

Compressed file size can be checked from another shell:

```bash
ls -lh /mnt/tvbox-backup/malachi/tvbox/tvbox-sd-*.img.gz
```

or watched periodically:

```bash
watch -n 30 'ls -lh /mnt/tvbox-backup/malachi/tvbox/tvbox-sd-*.img.gz 2>/dev/null'
```

---

## 16. After backup completes

After the image is written and verified:

```bash
sudo umount /mnt/tvbox-backup
sudo reboot
```

The backup directory should contain at least:

```text
tvbox-sd-YYYYMMDD-HHMMSS.img.gz
tvbox-sd-YYYYMMDD-HHMMSS.img.gz.sha256
```

Optional later config-only backup:

```bash
cd /mnt/tvbox-backup/malachi/tvbox
STAMP="$(date +%Y%m%d-%H%M%S)"

sudo tar --xattrs --acls -czf "tvbox-config-${STAMP}.tar.gz" \
  /opt/tvbox-system \
  /usr/local/bin \
  /etc/systemd/system/raspotify.service.d \
  /etc/raspotify \
  /etc/fstab \
  /boot/firmware \
  /home/tvbox/.config/autostart \
  /home/tvbox/.config/labwc \
  /home/tvbox/.config/systemd/user \
  /home/tvbox/.kodi/addons \
  /home/tvbox/.kodi/userdata/keymaps \
  /home/tvbox/.kodi/userdata/favourites.xml \
  2>"tvbox-config-${STAMP}.tar.stderr.log"

sha256sum "tvbox-config-${STAMP}.tar.gz" | tee "tvbox-config-${STAMP}.tar.gz.sha256"
```

Do the config-only backup after the full image if desired. The full image is the priority.

---

## 17. Restore notes

To restore the compressed image to a replacement SD card or other block device from a Linux machine:

```bash
gzip -dc tvbox-sd-YYYYMMDD-HHMMSS.img.gz | sudo dd of=/dev/sdX bs=16M status=progress conv=fsync
```

Replace:

```text
/dev/sdX
```

with the actual target replacement device.

Warning:

```text
Do not guess the target device.
Writing to the wrong /dev/sdX can destroy another disk.
```

After restoring to a larger device, the root filesystem may need expansion.

If migrating to USB SSD/NVMe, additional Pi boot-order and root-device validation may be needed.

---

## 18. Current working diagnosis

The best current diagnosis is:

```text
The emergency-mode boot was caused by delayed/unavailable boot partition device f7cde034-01.
The fstab entry itself appears valid.
The boot partition appeared and mounted later.
The SD card subsequently produced mmc0 busy/stall warnings.
Therefore the SD card/storage path is suspect.
```

Secondary issues fixed or reduced:

```text
NetworkManager-wait-online failure removed.
cloud-init disabled.
ModemManager disabled.
CUPS disabled/masked.
Raspotify user-runtime boot race fixed.
Tailscale moved to delayed startup.
```

Not yet fully solved:

```text
SD-card trustworthiness.
Long inconsistent boot after the Tailscale delayed timer change.
USB error -71 device enumeration issue.
Possible future boot delay from plymouth/rpcbind/nfs-blkmap/e2scrub/bluetooth/avahi/etc.
```

Main rule now:

```text
Do not keep tuning or write-heavily testing until the full SD-card image backup is complete and verified.
```

---

## 19. Recommended next steps

### Immediate

```text
1. Let the full SD image finish.
2. Verify sha256 file exists.
3. Verify gzip -t reports OK.
4. Unmount SMB share cleanly.
5. Reboot.
```

### After backup

Run:

```bash
systemd-analyze
systemctl --failed --no-pager
systemd-analyze blame | head -40
journalctl -b -k --no-pager | grep -Ei 'mmc|mmcblk|I/O error|Buffer I/O|timeout|busy|EXT4|filesystem|reset|failed'
```

If `mmc0: Card stuck being busy` repeats:

```text
Treat the card as unreliable.
Migrate to a fresh high-quality SD card or preferably USB SSD/NVMe.
```

### Later boot cleanup candidates

Only after backup:

```text
Inspect why plymouth-read-write.service took ~1m55s.
Evaluate whether rpcbind/nfs-blkmap are needed.
Evaluate whether Wi-Fi should autoconnect if Ethernet is primary.
Evaluate whether Bluetooth/Avahi/e2scrub should be delayed or disabled.
Rework Tailscale delayed start if timer still appears before graphical target in practice.
```

Possible future Tailscale alternative:

```text
Start Tailscale after graphical.target or after Kodi/user session is up, rather than strictly OnBootSec=90s.
```

Do not change this until the backup exists.

---

## 20. Key commands reference

### Check failed units

```bash
systemctl --failed --no-pager
```

### Boot timing

```bash
systemd-analyze
systemd-analyze blame | head -40
systemd-analyze critical-chain
```

### Storage warnings

```bash
sudo journalctl -k -b --no-pager | grep -Ei 'mmc|mmcblk|I/O error|Buffer I/O|timeout|busy|EXT4|filesystem|reset|failed'
```

### Boot firmware / emergency grep

```bash
journalctl -b --no-pager | grep -Ei 'boot-firmware|f7cde034-01|emergency|timed out|failed to mount|fsck|mmc0: Card stuck|I/O error|Buffer I/O|EXT4-fs error|cups|tailscaled|raspotify|cloud-init|NetworkManager-wait-online'
```

### Raspotify status

```bash
systemctl status raspotify --no-pager
journalctl -u raspotify -b -n 80 --no-pager
systemctl cat raspotify
```

### Tailscale delayed status

```bash
systemctl status tailscaled --no-pager
systemctl status tailscaled-delayed.timer --no-pager
systemctl status tailscaled-delayed.service --no-pager
```

### SMB mount status

```bash
mount | grep tvbox-backup
df -h /mnt/tvbox-backup
```

### Backup file check

```bash
ls -lh /mnt/tvbox-backup/malachi/tvbox/tvbox-sd-*.img.gz
ls -lh /mnt/tvbox-backup/malachi/tvbox/tvbox-sd-*.img.gz.sha256
```

---

## 21. Summary verdict

The service cleanup was useful and fixed several real boot/service issues.

The bigger concern is the SD-card/storage behavior:

```text
A boot partition timeout caused emergency mode.
Later mmc0 busy/stall warnings appeared.
No I/O errors were confirmed yet, but the storage is suspicious enough to back up immediately.
```

The correct current priority is:

```text
Backup first.
Then diagnose further.
Then migrate storage if mmc warnings repeat.
```

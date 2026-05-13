import os
import subprocess
import xbmc
import xbmcgui

launcher = "/usr/local/bin/tvbox-youtube"
log_file = "/tmp/tvbox-youtube.log"

xbmcgui.Dialog().notification(
    "YouTube TVBox",
    "Launching YouTube...",
    xbmcgui.NOTIFICATION_INFO,
    1500
)

# Launch detached so the script keeps running after Kodi closes.
with open(log_file, "a") as log:
    subprocess.Popen(
        [launcher],
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )

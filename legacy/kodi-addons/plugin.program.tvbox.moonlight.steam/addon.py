import subprocess
subprocess.Popen(
    ["/usr/local/bin/tvbox-moonlight", "steam"],
    start_new_session=True,
)

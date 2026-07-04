import subprocess

subprocess.Popen(
    ["/usr/local/bin/tvboxctl", "launch", "mariokart64"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

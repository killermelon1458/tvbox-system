import subprocess

subprocess.Popen(
    ["/usr/local/bin/tvboxctl", "launch", "steamlink"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

"""Stand-in for a GUI app: holds some memory, has a helper process, writes the ready file
after FAKE_READY_DELAY_MS (default 300), then sleeps until it is killed."""
import os
import subprocess
import sys
import time

delay_ms = int(os.environ.get("FAKE_READY_DELAY_MS", "300"))
helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
blob = bytearray(30 * 1024 * 1024)
for i in range(0, len(blob), 4096):  # touch every page so it counts toward RSS
    blob[i] = 1
time.sleep(delay_ms / 1000)
path = os.environ.get("BENCH_READY_FILE")
if path:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(int(time.time() * 1000)))
    os.replace(tmp, path)
time.sleep(600)

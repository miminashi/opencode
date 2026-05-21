#!/usr/bin/env python3
import subprocess
import sys
import time

OUT_PATH = sys.argv[1]
SERVER = "t120h-p100"
QUERY = "nvidia-smi --query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw --format=csv,noheader"
INTERVAL = 10


def main():
    with open(OUT_PATH, "a", buffering=1) as f:
        f.write("# timestamp,index,utilization.gpu,memory.used,power.draw (per-row)\n")
        while True:
            try:
                r = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", SERVER, QUERY],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if r.stdout:
                    f.write(r.stdout)
                if r.returncode != 0 and r.stderr:
                    f.write("# err rc=%d: %s\n" % (r.returncode, r.stderr.replace("\n", " | ").strip()))
            except subprocess.TimeoutExpired:
                f.write("# err: ssh timeout\n")
            except Exception as e:
                f.write("# err: %s: %s\n" % (type(e).__name__, e))
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

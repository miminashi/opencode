#!/usr/bin/env python3
import subprocess
import sys

OUT_PATH = sys.argv[1]
SERVER = "t120h-p100"
REMOTE_CMD = "tail -F /tmp/llama-server.log"


def main():
    with open(OUT_PATH, "a", buffering=1) as f:
        p = subprocess.Popen(
            ["ssh", "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3", SERVER, REMOTE_CMD],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
        p.wait()


if __name__ == "__main__":
    main()

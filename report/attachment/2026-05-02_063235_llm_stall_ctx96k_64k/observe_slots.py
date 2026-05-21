#!/usr/bin/env python3
import json
import sys
import time
import urllib.request
import urllib.error

OUT_PATH = sys.argv[1]
URL = "http://10.1.4.14:8000/slots"
INTERVAL = 10


def main():
    with open(OUT_PATH, "a", buffering=1) as f:
        while True:
            ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            entry = {"ts": ts, "ok": False}
            try:
                with urllib.request.urlopen(URL, timeout=5) as resp:
                    body = resp.read().decode("utf-8")
                entry["ok"] = True
                entry["body"] = json.loads(body)
            except urllib.error.URLError as e:
                entry["error"] = f"URLError: {e.reason}"
            except Exception as e:
                entry["error"] = f"{type(e).__name__}: {e}"
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

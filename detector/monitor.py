import json
import time
from datetime import datetime
from typing import Any, Callable, Dict


class LogMonitor:
    def __init__(self, log_file: str, on_event: Callable[[Dict[str, Any]], None]):
        self.log_file = log_file
        self.on_event = on_event

    def run_forever(self):
        while True:
            try:
                with open(self.log_file, "r", encoding="utf-8") as fp:
                    fp.seek(0, 2)
                    while True:
                        line = fp.readline()
                        if not line:
                            time.sleep(0.2)
                            continue
                        event = self._parse_line(line.strip())
                        if event:
                            self.on_event(event)
            except FileNotFoundError:
                time.sleep(1)
            except Exception:
                time.sleep(0.5)

    def _parse_line(self, line: str):
        try:
            payload = json.loads(line)
            ts = payload.get("timestamp")
            if ts is None:
                return None
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_epoch = int(dt.timestamp())
            else:
                ts_epoch = int(ts)
            return {
                "source_ip": payload.get("source_ip", "-"),
                "timestamp": ts_epoch,
                "method": payload.get("method", "GET"),
                "path": payload.get("path", "/"),
                "status": int(payload.get("status", 0)),
                "response_size": int(payload.get("response_size", 0)),
            }
        except Exception:
            return None

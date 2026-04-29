import threading
from datetime import datetime, timezone

import yaml

from baseline import BaselineWorker
from blocker import IPTablesBlocker
from dashboard import create_dashboard_app
from detector import DetectorEngine
from monitor import LogMonitor
from notifier import SlackNotifier
from unbanner import UnbannerWorker


class AuditLogger:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()

    def log(self, action: str, ip: str, condition: str, rate: float, baseline: float, duration: str):
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        line = f"[{ts}] {action} {ip} | {condition} | rate={rate:.2f} | baseline={baseline:.2f} | duration={duration}\n"
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as fp:
                fp.write(line)


def main():
    with open("config.yaml", "r", encoding="utf-8") as fp:
        config = yaml.safe_load(fp)

    blocker = IPTablesBlocker()
    notifier = SlackNotifier(config["slack"])
    audit = AuditLogger(config["audit_log_file"])
    engine = DetectorEngine(config, blocker, notifier, audit)

    baseline_worker = BaselineWorker(engine, config["baseline"]["recalc_interval_seconds"])
    baseline_worker.start()

    unbanner_worker = UnbannerWorker(engine)
    unbanner_worker.start()

    monitor = LogMonitor(config["log_file"], engine.process_event)
    monitor_thread = threading.Thread(target=monitor.run_forever, daemon=True)
    monitor_thread.start()

    app = create_dashboard_app(engine, config["dashboard"]["refresh_seconds"])
    app.run(host=config["dashboard"]["host"], port=config["dashboard"]["port"])


if __name__ == "__main__":
    main()

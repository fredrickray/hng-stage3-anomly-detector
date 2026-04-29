import threading
import time


class UnbannerWorker(threading.Thread):
    def __init__(self, engine, interval_seconds: int = 2):
        super().__init__(daemon=True)
        self.engine = engine
        self.interval_seconds = interval_seconds

    def run(self):
        while True:
            self.engine.check_unban()
            time.sleep(self.interval_seconds)

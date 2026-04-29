import threading
import time


class BaselineWorker(threading.Thread):
    def __init__(self, engine, interval_seconds: int):
        super().__init__(daemon=True)
        self.engine = engine
        self.interval_seconds = interval_seconds

    def run(self):
        while True:
            time.sleep(self.interval_seconds)
            self.engine.recalc_baseline()

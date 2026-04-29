import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class BaselineSnapshot:
    mean: float
    stddev: float
    error_rate: float
    source: str


class DetectorEngine:
    def __init__(self, config: Dict[str, Any], blocker, notifier, audit_logger):
        self.config = config
        self.blocker = blocker
        self.notifier = notifier
        self.audit_logger = audit_logger

        self.window_seconds = int(config["sliding_window_seconds"])
        self.start_time = time.time()
        self.lock = threading.RLock()

        self.global_window = deque()
        self.ip_windows = defaultdict(deque)

        self.current_second = None
        self.current_second_count = 0
        self.current_second_error_count = 0
        self.baseline_points = deque(maxlen=config["baseline"]["window_minutes"] * 60)
        self.hourly_slots = defaultdict(lambda: deque(maxlen=3600))

        self.top_counts = defaultdict(int)
        self.ban_attempts = defaultdict(int)
        self.banned_ips: Dict[str, Dict[str, Any]] = {}

        floor_mean = float(config["baseline"]["floor_mean"])
        floor_std = float(config["baseline"]["floor_stddev"])
        self.baseline = BaselineSnapshot(floor_mean, floor_std, 0.01, "startup")

    def process_event(self, event: Dict[str, Any]):
        now = event["timestamp"]
        ip = event["source_ip"]
        status = int(event["status"])

        with self.lock:
            self._roll_second(now)
            self.current_second_count += 1
            if status >= 400:
                self.current_second_error_count += 1

            self.global_window.append(now)
            ipq = self.ip_windows[ip]
            ipq.append(now)
            self.top_counts[ip] += 1

            self._evict_old(now)
            self._detect_global(now)
            self._detect_ip(ip, now)

    def _roll_second(self, timestamp: int):
        second = int(timestamp)
        if self.current_second is None:
            self.current_second = second
            return
        while self.current_second < second:
            error_rate = (
                self.current_second_error_count / self.current_second_count
                if self.current_second_count > 0
                else 0.0
            )
            point = (self.current_second, self.current_second_count, error_rate)
            self.baseline_points.append(point)
            hour_key = datetime.fromtimestamp(self.current_second, tz=timezone.utc).strftime("%Y-%m-%d-%H")
            self.hourly_slots[hour_key].append(point)
            self.current_second += 1
            self.current_second_count = 0
            self.current_second_error_count = 0

    def _evict_old(self, now: int):
        cutoff = now - self.window_seconds
        while self.global_window and self.global_window[0] <= cutoff:
            self.global_window.popleft()
        for ip, q in list(self.ip_windows.items()):
            while q and q[0] <= cutoff:
                q.popleft()
            if not q:
                del self.ip_windows[ip]

    def _zscore(self, value: float) -> float:
        return (value - self.baseline.mean) / max(self.baseline.stddev, 1e-9)

    def _detect_global(self, now: int):
        rate = len(self.global_window) / self.window_seconds
        zscore = self._zscore(rate)
        multiple = rate / max(self.baseline.mean, 1e-9)
        t = self.config["thresholds"]

        if zscore > t["zscore"] or multiple > t["multiple"]:
            condition = f"GLOBAL_ANOMALY z={zscore:.2f} x={multiple:.2f}"
            self.audit_logger.log("ALERT", "-", condition, rate, self.baseline.mean, "n/a")
            self.notifier.send_global_alert(condition, rate, self.baseline.mean, now)

    def _detect_ip(self, ip: str, now: int):
        if ip in self.banned_ips:
            return

        rate = len(self.ip_windows[ip]) / self.window_seconds
        zscore = self._zscore(rate)
        multiple = rate / max(self.baseline.mean, 1e-9)
        t = self.config["thresholds"]
        z_limit = t["zscore"]
        m_limit = t["multiple"]

        err_rate = self._ip_error_rate_estimate(ip)
        if err_rate > self.baseline.error_rate * t["error_surge_multiplier"]:
            z_limit = t["tightened_zscore"]
            m_limit = t["tightened_multiple"]

        if zscore > z_limit or multiple > m_limit:
            self._ban_ip(ip, now, f"IP_ANOMALY z={zscore:.2f} x={multiple:.2f}", rate)

    def _ip_error_rate_estimate(self, ip: str) -> float:
        # Approximate per-IP error pressure by comparing request pressure against global baseline error.
        if ip not in self.ip_windows:
            return 0.0
        ip_rate = len(self.ip_windows[ip]) / self.window_seconds
        return min(1.0, ip_rate * self.baseline.error_rate)

    def _ban_ip(self, ip: str, now: int, condition: str, rate: float):
        attempts = self.ban_attempts[ip]
        durations = self.config["blocking"]["durations_seconds"]
        is_permanent = attempts >= len(durations)
        duration = "permanent" if is_permanent else f"{durations[attempts]}s"
        expires_at = None if is_permanent else now + durations[attempts]

        if self.config["blocking"]["enabled"]:
            self.blocker.block_ip(ip)
        self.banned_ips[ip] = {
            "condition": condition,
            "banned_at": now,
            "expires_at": expires_at,
            "duration": duration,
        }
        self.ban_attempts[ip] += 1
        self.audit_logger.log("BAN", ip, condition, rate, self.baseline.mean, duration)
        self.notifier.send_ban_alert(ip, condition, rate, self.baseline.mean, now, duration)

    def recalc_baseline(self):
        with self.lock:
            points = list(self.baseline_points)
            if not points:
                return

            current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
            hour_points = list(self.hourly_slots[current_hour])
            min_points = self.config["baseline"]["min_points_for_hourly_slot"]
            candidate = hour_points if len(hour_points) >= min_points else points
            source = "current_hour" if candidate is hour_points else "rolling_30m"

            values = [count for _, count, _ in candidate]
            errs = [err for _, _, err in candidate]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = math.sqrt(variance)
            error_rate = sum(errs) / len(errs)

            mean = max(mean, self.config["baseline"]["floor_mean"])
            std = max(std, self.config["baseline"]["floor_stddev"])

            self.baseline = BaselineSnapshot(mean, std, error_rate, source)
            self.audit_logger.log("BASELINE", "-", source, mean, std, "n/a")

    def check_unban(self, now: Optional[int] = None):
        now = now or int(time.time())
        with self.lock:
            for ip, details in list(self.banned_ips.items()):
                exp = details["expires_at"]
                if exp is not None and now >= exp:
                    self.blocker.unblock_ip(ip)
                    self.audit_logger.log("UNBAN", ip, details["condition"], 0.0, self.baseline.mean, details["duration"])
                    self.notifier.send_unban_alert(ip, details["condition"], now, details["duration"])
                    del self.banned_ips[ip]

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            uptime = int(time.time() - self.start_time)
            top_10 = sorted(self.top_counts.items(), key=lambda i: i[1], reverse=True)[:10]
            return {
                "uptime_seconds": uptime,
                "global_rps": len(self.global_window) / self.window_seconds,
                "banned_ips": dict(self.banned_ips),
                "top_ips": top_10,
                "baseline_mean": self.baseline.mean,
                "baseline_stddev": self.baseline.stddev,
                "baseline_error_rate": self.baseline.error_rate,
                "baseline_source": self.baseline.source,
            }

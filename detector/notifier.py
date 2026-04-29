import datetime as dt
from typing import Dict

import requests


class SlackNotifier:
    def __init__(self, slack_config: Dict):
        self.webhook_url = slack_config.get("webhook_url", "")
        self.timeout = slack_config.get("timeout_seconds", 4)

    def _send(self, text: str):
        if not self.webhook_url:
            return
        try:
            requests.post(self.webhook_url, json={"text": text}, timeout=self.timeout)
        except Exception:
            return

    def send_ban_alert(self, ip, condition, rate, baseline, now, duration):
        ts = dt.datetime.utcfromtimestamp(now).isoformat() + "Z"
        self._send(
            f"[BAN] ip={ip} condition={condition} rate={rate:.2f} baseline={baseline:.2f} ts={ts} duration={duration}"
        )

    def send_unban_alert(self, ip, condition, now, duration):
        ts = dt.datetime.utcfromtimestamp(now).isoformat() + "Z"
        self._send(f"[UNBAN] ip={ip} condition={condition} ts={ts} previous_duration={duration}")

    def send_global_alert(self, condition, rate, baseline, now):
        ts = dt.datetime.utcfromtimestamp(now).isoformat() + "Z"
        self._send(
            f"[GLOBAL] condition={condition} current_rate={rate:.2f} baseline={baseline:.2f} ts={ts}"
        )

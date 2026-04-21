"""Slack alert sender for observability check results."""
from __future__ import annotations
import json
import logging
from typing import List
import urllib.request

logger = logging.getLogger(__name__)

STATUS_EMOJI = {"ok": ":white_check_mark:", "warn": ":warning:", "critical": ":red_circle:"}
STATUS_COLOR = {"ok": "#36a64f", "warn": "#ff9800", "critical": "#e74c3c"}


class SlackNotifier:
    def __init__(self, webhook_url: str, channel: str = "#data-alerts") -> None:
        self._url = webhook_url
        self._channel = channel

    def send(self, results: List, run_id: str = "") -> None:
        failures = [r for r in results if r.status != "ok"]
        if not failures:
            return

        attachments = []
        for r in failures:
            attachments.append({
                "color": STATUS_COLOR[r.status],
                "fields": [
                    {"title": "Table", "value": getattr(r, "table", ""), "short": True},
                    {"title": "Check", "value": type(r).__name__.replace("Result", ""), "short": True},
                    {"title": "Status", "value": f"{STATUS_EMOJI[r.status]} {r.status.upper()}", "short": True},
                    {"title": "Detail", "value": r.message, "short": False},
                ],
            })

        payload = {
            "channel": self._channel,
            "text": f":mag: *Data observability alert* — {len(failures)} check(s) failed" + (f" (run `{run_id}`)" if run_id else ""),
            "attachments": attachments,
        }

        req = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.error("Slack webhook returned %s", resp.status)
            else:
                logger.info("Slack alert sent for %d failures", len(failures))

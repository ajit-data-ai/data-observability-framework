"""Freshness monitor — checks when a table last received new rows."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from google.cloud import bigquery


@dataclass
class FreshnessResult:
    table: str
    last_updated: datetime
    age_hours: float
    sla_hours: float
    status: str
    message: str


class FreshnessMonitor:
    def __init__(self, bq_client: bigquery.Client) -> None:
        self._bq = bq_client

    def check(self, table_id: str, timestamp_column: str, sla_hours: float = 25.0) -> FreshnessResult:
        query = f"SELECT MAX({timestamp_column}) AS last_updated FROM `{table_id}`"
        rows = list(self._bq.query(query).result())
        last_updated = rows[0]["last_updated"] if rows else None

        if last_updated is None:
            return FreshnessResult(table_id, datetime.min, float("inf"), sla_hours, "critical", "Table is empty")

        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        age = (datetime.now(timezone.utc) - last_updated).total_seconds() / 3600

        if age > sla_hours:
            status = "critical" if age > sla_hours * 2 else "warn"
            msg = f"Last updated {age:.1f}h ago — SLA is {sla_hours}h"
        else:
            status, msg = "ok", f"Last updated {age:.1f}h ago"

        return FreshnessResult(table_id, last_updated, round(age, 2), sla_hours, status, msg)

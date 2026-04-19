"""Null-rate monitor — alerts when critical columns exceed expected null percentage."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from google.cloud import bigquery


@dataclass
class NullRateResult:
    table: str
    column: str
    null_count: int
    total_count: int
    null_rate_pct: float
    threshold_pct: float
    status: str
    message: str


class NullRateMonitor:
    def __init__(self, bq_client: bigquery.Client) -> None:
        self._bq = bq_client

    def check(self, table_id: str, columns: List[dict]) -> List[NullRateResult]:
        """
        columns: list of {"name": "col_name", "threshold_pct": 5.0}
        """
        results = []
        col_names = [c["name"] for c in columns]
        thresholds = {c["name"]: c["threshold_pct"] for c in columns}

        null_exprs = ", ".join(
            f"COUNTIF({col} IS NULL) AS null_{col}" for col in col_names
        )
        query = f"SELECT COUNT(*) AS total, {null_exprs} FROM `{table_id}`"
        row = next(iter(self._bq.query(query).result()))
        total = row["total"]

        for col in col_names:
            null_count = row[f"null_{col}"]
            rate = round(null_count / max(total, 1) * 100, 4)
            threshold = thresholds[col]

            if rate > threshold:
                status = "critical" if rate > threshold * 2 else "warn"
                msg = f"Null rate {rate:.2f}% exceeds threshold {threshold}%"
            else:
                status, msg = "ok", f"Null rate {rate:.2f}% within threshold"

            results.append(NullRateResult(table_id, col, null_count, total, rate, threshold, status, msg))

        return results

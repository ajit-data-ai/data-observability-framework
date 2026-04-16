"""Volume anomaly monitor — detects row count drops or spikes vs. rolling baseline."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from google.cloud import bigquery


@dataclass
class VolumeResult:
    table: str
    check_date: date
    row_count: int
    baseline_avg: float
    baseline_stddev: float
    z_score: float
    status: str         # "ok" | "warn" | "critical"
    message: str


class VolumeMonitor:
    def __init__(self, bq_client: bigquery.Client, warn_z: float = 2.0, critical_z: float = 3.5) -> None:
        self._bq = bq_client
        self._warn_z = warn_z
        self._critical_z = critical_z

    def check(self, table_id: str, partition_column: str = "_PARTITIONDATE", lookback_days: int = 28) -> VolumeResult:
        baseline_start = (date.today() - timedelta(days=lookback_days)).isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        query = f"""
            WITH daily_counts AS (
                SELECT
                    DATE({partition_column}) AS d,
                    COUNT(*) AS row_count
                FROM `{table_id}`
                WHERE DATE({partition_column}) BETWEEN @baseline_start AND @yesterday
                GROUP BY 1
            ),
            stats AS (
                SELECT
                    AVG(row_count) AS avg_count,
                    STDDEV(row_count) AS std_count
                FROM daily_counts
                WHERE d < @yesterday
            ),
            today AS (
                SELECT row_count FROM daily_counts WHERE d = @yesterday
            )
            SELECT
                today.row_count,
                stats.avg_count,
                COALESCE(stats.std_count, 1) AS std_count
            FROM today, stats
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("baseline_start", "DATE", baseline_start),
            bigquery.ScalarQueryParameter("yesterday", "DATE", yesterday),
        ])
        rows = list(self._bq.query(query, job_config=job_config).result())
        if not rows:
            return VolumeResult(table_id, date.today(), 0, 0, 0, 0, "critical", "No data for yesterday")

        row = rows[0]
        count, avg, std = row["row_count"], row["avg_count"], row["std_count"]
        z = (count - avg) / max(std, 1)

        if abs(z) >= self._critical_z:
            status, msg = "critical", f"Row count {count:,} is {z:+.1f} stddevs from baseline avg {avg:,.0f}"
        elif abs(z) >= self._warn_z:
            status, msg = "warn", f"Row count {count:,} is {z:+.1f} stddevs from baseline avg {avg:,.0f}"
        else:
            status, msg = "ok", f"Row count {count:,} within normal range"

        return VolumeResult(table_id, date.today(), count, avg, std, z, status, msg)

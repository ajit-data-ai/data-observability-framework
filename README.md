# Data Observability Framework

Lightweight, config-driven data quality monitoring for BigQuery. Detects volume anomalies, freshness SLA breaches, and null-rate drift — sends Slack alerts before downstream consumers notice the problem.

## Monitors

| Check | What it catches | Detection method |
|---|---|---|
| `freshness` | Table hasn't been updated within SLA window | `MAX(timestamp_col)` vs. current time |
| `volume` | Row count dropped or spiked vs. baseline | Z-score against 28-day rolling average |
| `null_rate` | Critical column null % exceeded threshold | `COUNTIF(col IS NULL) / COUNT(*)` |

## Quick Start

```bash
pip install google-cloud-bigquery pyyaml

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/sa.json"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."

python runner.py --config config/monitors.yaml
```

## Configuration

Add a monitor block per table in `config/monitors.yaml`:

```yaml
monitors:
  - table: "project.dataset.orders"
    checks:
      freshness:
        timestamp_column: updated_at
        sla_hours: 25
      volume:
        lookback_days: 28
        critical_z_score: 3.5
      null_rate:
        columns:
          - name: order_id
            threshold_pct: 0.0
```

## Airflow Integration

```python
from airflow.operators.bash import BashOperator

observe = BashOperator(
    task_id="run_observability_checks",
    bash_command="python /opt/runner.py --config /opt/config/monitors.yaml",
)
dbt_run >> observe  # run checks after every dbt build
```

## Alert Format

Slack alerts include table name, check type, status (warn/critical), and a human-readable message. Only failures are sent — successful checks are silent.

"""Entry point: loads config, runs all monitors, sends Slack alerts."""
from __future__ import annotations
import argparse, logging, os, uuid, yaml
from google.cloud import bigquery
from monitors.freshness import FreshnessMonitor
from monitors.volume import VolumeMonitor
from monitors.null_rate import NullRateMonitor
from alerts.slack_notifier import SlackNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(config_path: str) -> None:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    bq = bigquery.Client()
    slack_cfg = config.get("slack", {})
    webhook_url = os.path.expandvars(slack_cfg.get("webhook_url", ""))
    notifier = SlackNotifier(webhook_url, slack_cfg.get("channel", "#data-alerts")) if webhook_url else None

    run_id = str(uuid.uuid4())[:8]
    all_results = []

    for monitor_def in config.get("monitors", []):
        table = monitor_def["table"]
        checks = monitor_def.get("checks", {})

        if "freshness" in checks:
            cfg = checks["freshness"]
            result = FreshnessMonitor(bq).check(table, cfg["timestamp_column"], cfg.get("sla_hours", 25))
            all_results.append(result)
            logger.info("[freshness] %s → %s: %s", table, result.status, result.message)

        if "volume" in checks:
            cfg = checks["volume"]
            result = VolumeMonitor(bq, cfg.get("warn_z_score", 2.0), cfg.get("critical_z_score", 3.5)).check(
                table, cfg.get("partition_column", "_PARTITIONDATE"), cfg.get("lookback_days", 28)
            )
            all_results.append(result)
            logger.info("[volume] %s → %s: %s", table, result.status, result.message)

        if "null_rate" in checks:
            results = NullRateMonitor(bq).check(table, checks["null_rate"]["columns"])
            all_results.extend(results)
            for r in results:
                logger.info("[null_rate] %s.%s → %s: %s", table, r.column, r.status, r.message)

    failures = [r for r in all_results if r.status != "ok"]
    logger.info("Run %s complete — %d checks, %d failures", run_id, len(all_results), len(failures))

    if notifier and failures:
        notifier.send(all_results, run_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/monitors.yaml")
    run(parser.parse_args().config)

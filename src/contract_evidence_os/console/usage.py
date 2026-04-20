"""Usage aggregation and token/cost monitoring for the browser console."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.console._base import ConsoleSubservice
from contract_evidence_os.console.models import ProviderUsageTrend, TaskUsageSummary, TokenUsageAggregate, UsageAlertRecord
from contract_evidence_os.runtime.providers import ProviderUsageRecord


class ConsoleUsageService(ConsoleSubservice):
    """Own token and cost aggregation read models."""

    def _all_provider_usage_records(self) -> list[ProviderUsageRecord]:
        records: list[ProviderUsageRecord] = []
        for task in self.repository.list_tasks():
            records.extend(self.repository.list_provider_usage_records(str(task["task_id"])))
        records.sort(key=lambda item: item.created_at)
        return records

    def _parse_window_hours(self, window: str) -> int:
        normalized = window.strip().lower()
        if normalized.endswith("h"):
            return int(normalized[:-1])
        if normalized.endswith("d"):
            return int(normalized[:-1]) * 24
        return int(normalized)

    def _aggregate_usage(self, records: Iterable[ProviderUsageRecord], *, window_hours: int) -> dict[str, Any]:
        cutoff = utc_now() - timedelta(hours=window_hours)
        filtered = [item for item in records if item.created_at >= cutoff]
        provider_totals: dict[str, dict[str, Any]] = {}
        task_totals: dict[str, dict[str, Any]] = {}
        for item in filtered:
            provider_bucket = provider_totals.setdefault(
                item.provider_name,
                {"provider_name": item.provider_name, "total_tokens": 0, "estimated_cost": 0.0, "request_count": 0},
            )
            provider_bucket["total_tokens"] += item.total_tokens
            provider_bucket["estimated_cost"] += item.estimated_cost
            provider_bucket["request_count"] += 1
            task_bucket = task_totals.setdefault(
                item.task_id,
                {
                    "task_id": item.task_id,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                    "request_count": 0,
                    "fallback_count": 0,
                    "provider_names": set(),
                },
            )
            task_bucket["total_tokens"] += item.total_tokens
            task_bucket["estimated_cost"] += item.estimated_cost
            task_bucket["request_count"] += 1
            task_bucket["fallback_count"] += 1 if item.fallback_used else 0
            task_bucket["provider_names"].add(item.provider_name)
        totals = {
            "request_count": sum(item["request_count"] for item in provider_totals.values()),
            "total_tokens": sum(item["total_tokens"] for item in provider_totals.values()),
            "estimated_cost": round(sum(item["estimated_cost"] for item in provider_totals.values()), 6),
        }
        provider_rows = sorted(provider_totals.values(), key=lambda item: item["total_tokens"], reverse=True)
        task_rows = []
        for task_id, row in task_totals.items():
            summary = TaskUsageSummary(
                version="1.0",
                summary_id=f"task-usage-{uuid4().hex[:10]}",
                task_id=task_id,
                total_tokens=int(row["total_tokens"]),
                estimated_cost=float(round(row["estimated_cost"], 6)),
                request_count=int(row["request_count"]),
                fallback_count=int(row["fallback_count"]),
                provider_names=sorted(str(item) for item in row["provider_names"]),
            )
            self._save_model("console_task_usage_summary", summary.summary_id, task_id, summary.updated_at.isoformat(), summary)
            task_rows.append(summary.to_dict())
        for provider_name, row in provider_totals.items():
            aggregate = TokenUsageAggregate(
                version="1.0",
                aggregate_id=f"usage-aggregate-{uuid4().hex[:10]}",
                scope_key="global",
                window_hours=window_hours,
                provider_name=provider_name,
                task_id="",
                total_tokens=int(row["total_tokens"]),
                estimated_cost=float(round(row["estimated_cost"], 6)),
                request_count=int(row["request_count"]),
            )
            self._save_model("console_token_usage_aggregate", aggregate.aggregate_id, "global", aggregate.created_at.isoformat(), aggregate)
        trends = self._build_provider_trends(filtered, window_hours=window_hours)
        alerts = self._usage_alerts(provider_rows, totals)
        return {
            "window_hours": window_hours,
            "totals": totals,
            "providers": provider_rows,
            "tasks": sorted(task_rows, key=lambda item: item["total_tokens"], reverse=True),
            "trends": [item.to_dict() for item in trends],
            "alerts": [item.to_dict() for item in alerts],
        }

    def _build_provider_trends(self, records: list[ProviderUsageRecord], *, window_hours: int) -> list[ProviderUsageTrend]:
        buckets: dict[tuple[str, str], dict[str, Any]] = {}
        for item in records:
            hour_bucket = item.created_at.replace(minute=0, second=0, microsecond=0).isoformat()
            key = (item.provider_name, hour_bucket)
            bucket = buckets.setdefault(key, {"timestamp": hour_bucket, "total_tokens": 0, "estimated_cost": 0.0})
            bucket["total_tokens"] += item.total_tokens
            bucket["estimated_cost"] += item.estimated_cost
        by_provider: dict[str, list[dict[str, Any]]] = {}
        for (provider_name, _), payload in buckets.items():
            by_provider.setdefault(provider_name, []).append(payload)
        trends: list[ProviderUsageTrend] = []
        for provider_name, points in by_provider.items():
            trend = ProviderUsageTrend(
                version="1.0",
                trend_id=f"provider-trend-{uuid4().hex[:10]}",
                provider_name=provider_name,
                window_hours=window_hours,
                points=sorted(points, key=lambda item: item["timestamp"]),
            )
            self._save_model("console_provider_usage_trend", trend.trend_id, provider_name, trend.created_at.isoformat(), trend)
            trends.append(trend)
        return trends

    def _usage_alerts(self, provider_rows: list[dict[str, Any]], totals: dict[str, Any]) -> list[UsageAlertRecord]:
        alerts: list[UsageAlertRecord] = []
        if totals["total_tokens"] >= 100000:
            alerts.append(
                UsageAlertRecord(
                    version="1.0",
                    alert_id=f"usage-alert-{uuid4().hex[:10]}",
                    scope_key="global",
                    severity="warning",
                    summary="High token consumption in the current window.",
                    category="high-spend",
                )
            )
        if any(row["request_count"] >= 10 and row["total_tokens"] >= 10000 for row in provider_rows):
            alerts.append(
                UsageAlertRecord(
                    version="1.0",
                    alert_id=f"usage-alert-{uuid4().hex[:10]}",
                    scope_key="global",
                    severity="warning",
                    summary="One or more providers show elevated request volume.",
                    category="provider-spike",
                )
            )
        for alert in alerts:
            self._save_model("console_usage_alert", alert.alert_id, alert.scope_key, alert.created_at.isoformat(), alert)
        return alerts

    def usage_summary(self, *, window: str = "24h") -> dict[str, Any]:
        return self._aggregate_usage(self._all_provider_usage_records(), window_hours=self._parse_window_hours(window))

    def task_usage_summary(self, task_id: str, *, window: str = "24h") -> dict[str, Any]:
        records = [item for item in self.repository.list_provider_usage_records(task_id) if item.created_at >= utc_now() - timedelta(hours=self._parse_window_hours(window))]
        total_tokens = sum(item.total_tokens for item in records)
        total_cost = round(sum(item.estimated_cost for item in records), 6)
        return {
            "task_id": task_id,
            "request_count": len(records),
            "total_tokens": total_tokens,
            "estimated_cost": total_cost,
            "providers": sorted({item.provider_name for item in records}),
            "records": [item.to_dict() for item in records],
        }

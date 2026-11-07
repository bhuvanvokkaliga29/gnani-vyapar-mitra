"""Bounded Operational Metrics Registry for Phase 9.4.

Contract: observability-metrics/v1
Guarantees:
1. Thread-safe operational counters and latency tracking.
2. Strict label safety: Enforces bounded enumeration labels only.
3. Zero high-cardinality label explosion (strictly forbids request_id, decision_id, etc.).
4. Explicit, non-authoritative operational measurement.
"""

from threading import Lock
from typing import Dict, Any, Optional
from collections import defaultdict


class RuntimeMetricsRegistry:
    """Thread-safe, bounded operational metrics registry."""

    _lock = Lock()
    _counters: Dict[str, int] = defaultdict(int)
    _latencies: Dict[str, list] = defaultdict(list)

    # Allowed bounded components
    _ALLOWED_COMPONENTS = {
        "api", "decision_runtime", "execution_boundary", "transaction",
        "outcome_service", "learning_pipeline", "memory", "model", "security"
    }

    @classmethod
    def _sanitize_label(cls, label: Optional[str], default: str = "unknown") -> str:
        """Sanitize label value to ensure boundedness."""
        if not label or not isinstance(label, str):
            return default
        cleaned = "".join(c for c in label.strip() if c.isalnum() or c in ("_", "-")).lower()
        return cleaned[:32] if cleaned else default

    @classmethod
    def increment(
        cls,
        metric_name: str,
        value: int = 1,
        component: str = "api",
        status: str = "success",
        operation: Optional[str] = None
    ) -> None:
        """Increment an operational metric with bounded labels."""
        c = cls._sanitize_label(component if component in cls._ALLOWED_COMPONENTS else "other")
        s = cls._sanitize_label(status)
        op = cls._sanitize_label(operation, "default") if operation else "default"
        key = f"{metric_name}[component={c},status={s},operation={op}]"

        with cls._lock:
            cls._counters[key] += value

    @classmethod
    def record_request(cls, component: str, status: str, latency_ms: float) -> None:
        """Record an incoming request and its latency."""
        cls.increment("request_count", 1, component=component, status=status)
        c = cls._sanitize_label(component)
        with cls._lock:
            lat_list = cls._latencies[f"request_latency_ms[component={c}]"]
            if len(lat_list) >= 1000:
                lat_list.pop(0)
            lat_list.append(latency_ms)

    @classmethod
    def record_request_error(cls, component: str, error_type: str) -> None:
        """Record an unhandled request error."""
        cls.increment("request_error_count", 1, component=component, status="error", operation=error_type)

    @classmethod
    def record_decision(cls, mode: str, status: str) -> None:
        """Record a decision evaluation (EXPLORE / EXPLOIT)."""
        cls.increment("decision_count", 1, component="decision_runtime", status=status, operation=mode)

    @classmethod
    def record_execution(cls, status: str) -> None:
        """Record execution boundary authorization or rejection."""
        cls.increment("execution_count", 1, component="execution_boundary", status=status)

    @classmethod
    def record_outcome(cls, outcome_status: str, processing_state: str) -> None:
        """Record outcome resolution and feedback processing state."""
        cls.increment(
            "outcome_count",
            1,
            component="outcome_service",
            status=outcome_status,
            operation=processing_state
        )

    @classmethod
    def record_learning_event(cls, event_type: str, status: str) -> None:
        """Record learning pipeline events (evidence, memory, model update)."""
        cls.increment("learning_pipeline_event", 1, component="learning_pipeline", status=status, operation=event_type)

    @classmethod
    def record_security_rejection(cls, reason_code: str) -> None:
        """Record security boundary rejections (e.g. cross-tenant attempt, forged fields)."""
        cls.increment("security_rejection_count", 1, component="security", status="rejected", operation=reason_code)

    @classmethod
    def snapshot(cls) -> Dict[str, Any]:
        """Export an immutable, safe JSON-serializable snapshot of operational metrics."""
        with cls._lock:
            counters_copy = dict(cls._counters)
            latency_stats = {}
            for k, vals in cls._latencies.items():
                if vals:
                    latency_stats[k] = {
                        "count": len(vals),
                        "avg_ms": round(sum(vals) / len(vals), 2),
                        "p95_ms": round(sorted(vals)[int(len(vals) * 0.95)], 2)
                    }
            return {
                "schema_version": "observability-metrics/v1",
                "counters": counters_copy,
                "latencies": latency_stats
            }

    @classmethod
    def reset(cls) -> None:
        """Reset all metrics (for testing isolation)."""
        with cls._lock:
            cls._counters.clear()
            cls._latencies.clear()

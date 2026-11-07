"""Unit tests for Phase 9.4 Bounded Operational Metrics."""

from services.observability.metrics import RuntimeMetricsRegistry


def test_metrics_increment_bounded_labels():
    """Verify metrics increment correctly with bounded labels and zero high-cardinality leakage."""
    RuntimeMetricsRegistry.reset()

    RuntimeMetricsRegistry.increment("request_count", 1, component="api", status="200")
    RuntimeMetricsRegistry.increment("request_count", 1, component="api", status="200")
    RuntimeMetricsRegistry.increment("request_count", 1, component="api", status="500")

    snapshot = RuntimeMetricsRegistry.snapshot()
    assert snapshot["schema_version"] == "observability-metrics/v1"
    assert snapshot["counters"]["request_count[component=api,status=200,operation=default]"] == 2
    assert snapshot["counters"]["request_count[component=api,status=500,operation=default]"] == 1


def test_metrics_record_request_and_latency():
    """Verify request latency tracking computes count, average, and p95 correctly."""
    RuntimeMetricsRegistry.reset()

    for lat in [10.0, 20.0, 30.0, 40.0, 50.0]:
        RuntimeMetricsRegistry.record_request(component="api", status="200", latency_ms=lat)

    snapshot = RuntimeMetricsRegistry.snapshot()
    lat_stat = snapshot["latencies"]["request_latency_ms[component=api]"]
    assert lat_stat["count"] == 5
    assert lat_stat["avg_ms"] == 30.0
    assert lat_stat["p95_ms"] == 50.0


def test_metrics_domain_lifecycle_events():
    """Verify operational metrics record domain lifecycle stages accurately."""
    RuntimeMetricsRegistry.reset()

    RuntimeMetricsRegistry.record_decision(mode="EXPLORE", status="success")
    RuntimeMetricsRegistry.record_execution(status="authorized")
    RuntimeMetricsRegistry.record_outcome(outcome_status="PAYMENT_SUCCESS", processing_state="COMPLETED")
    RuntimeMetricsRegistry.record_learning_event(event_type="evidence_accepted", status="accepted")
    RuntimeMetricsRegistry.record_security_rejection(reason_code="cross_tenant_attempt")

    snapshot = RuntimeMetricsRegistry.snapshot()
    counters = snapshot["counters"]

    assert counters["decision_count[component=decision_runtime,status=success,operation=explore]"] == 1
    assert counters["execution_count[component=execution_boundary,status=authorized,operation=default]"] == 1
    assert counters["outcome_count[component=outcome_service,status=payment_success,operation=completed]"] == 1
    assert counters["learning_pipeline_event[component=learning_pipeline,status=accepted,operation=evidence_accepted]"] == 1
    assert counters["security_rejection_count[component=security,status=rejected,operation=cross_tenant_attempt]"] == 1

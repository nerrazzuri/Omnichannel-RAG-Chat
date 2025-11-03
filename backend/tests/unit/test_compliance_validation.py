import os


def test_compliance_report_handles_missing_metrics(monkeypatch):
    os.environ["ENV"] = "test"
    from ai_core.services.compliance_reporter import ComplianceReporter

    class DummyDB:
        def add(self, *_):
            pass

        def commit(self):
            pass

    # Should not raise even if Prometheus is unreachable
    rep = ComplianceReporter(DummyDB())
    try:
        _ = rep.generate_for_tenant("00000000-0000-0000-0000-000000000001")
    except Exception as e:
        assert False, f"ComplianceReporter raised unexpectedly: {e}"



from prometheus_client import Counter


class _ExceptionMetrics:
    def __init__(self) -> None:
        self._exceptions_total = Counter("ai_core_exceptions_logged_total", "Total exceptions captured in AI-Core")

    def inc(self) -> None:
        self._exceptions_total.inc()


exception_metrics = _ExceptionMetrics()



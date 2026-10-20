"""Business metrics exposed on /metrics next to the HTTP metrics (Prometheus)."""
from prometheus_client import Counter, Gauge

REPORTS_CREATED = Counter("ecoroute_reports_created_total", "Reports received", ["category", "merged"])
OPEN_REPORTS = Gauge("ecoroute_open_reports", "Open reports", ["priority"])
SLA_BREACHED = Gauge("ecoroute_sla_breached", "Open reports past their SLA")
ASSISTANT_CALLS = Counter("ecoroute_assistant_calls_total", "Assistant requests", ["provider"])

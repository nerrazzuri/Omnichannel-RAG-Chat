# Error Budget Breach

- Impact: Reliability SLO violated.
- Immediate: Inspect 5xx by route; rollback last deploy if correlated.
- Long-term: Add tests around failing endpoints; improve retries.
- Dashboards: AI-Core/Gateway Overview.

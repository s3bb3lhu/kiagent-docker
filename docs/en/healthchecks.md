# Healthchecks: heartbeats and alerts

Settings and connections · 1.3.0.0

1. Create separate server and bot checks in your Healthchecks account. Copy their UUID ping URLs and assign them in Settings → Healthchecks. Ping URLs are required, not a management API key.

2. Configure recipients or integrations in Healthchecks. Match period and grace time to actual heartbeat intervals. A controlled alert test must separately verify the check goes down and the recipient receives the warning.

3. Both fields are optional. Treat ping URLs like passwords and keep them out of the repository. Missing heartbeats are not a complete disk or application diagnosis.

- [Manage Healthchecks](https://healthchecks.io/checks/)
- [Healthchecks documentation](https://healthchecks.io/docs/)

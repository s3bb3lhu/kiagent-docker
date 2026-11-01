# SSH Console: reading activity

Features and control · 1.3.0.0

1. SSH Console is a read-only activity view, not an interactive shell. It shows fixed AI processing phases since the last bot restart and recent package/web jobs. Questions, answers and tokens are excluded.

2. APT progress is extracted only from known lines and package names in the actual plan. Raw installation script output is excluded. Creation times are labeled; steps without timestamps receive no invented time. Without an adapter the page remains with an explanation.


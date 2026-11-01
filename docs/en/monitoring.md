# RAID monitoring and automation

Settings and connections · 1.3.0.1

1. In Settings → Monitoring enter existing md device names such as md4. RAID members, partitions and synchronization are not changed. A resync with degraded=0 is not proof of disk failure.

2. Automation checks every 60 seconds. Only a fault persisting for at least 120 seconds in the tested RAID-monitor services permits repair. Limits: one hour between attempts, at most three in 24 hours and a shared 120-second cooldown.

3. /automatik_status shows state, recent attempts and lock times. /automatik_an and /automatik_aus persistently toggle automation. Telegram preannouncement is required before each automatic repair; results remain until delivered. Failure or uncertainty locks automation until successful manual /raid_monitor_start.

4. The approved repair only affects mdmonitor.service and mdmonitor-oneshot.service. A successfully inactive oneshot service is normal. This is not a SMART test or automatic disk repair.


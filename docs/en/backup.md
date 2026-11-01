# Backups and recovery

Operation and maintenance · 1.3.0.0

1. The managed Linux installation backs up daily at 03:15 Europe/Berlin to /var/backups/kiagent-daily. Archives contain private credentials and a consistent SQLite snapshot and are root-only. Old archives are not automatically deleted; monitor free space.

2. Isolated restore checks verify files and database consistency, not a complete new server. Backups on the same RAID do not protect against total array loss. Plan external backups separately. Never publish archives, volumes or auth files.

3. For recovery stop services deliberately, verify ownership/permissions and do not restore old history onto a system that has continued running. That could reuse consumed approvals. Web password state is separate and not part of the daily configuration backup; reset it administratively during recovery.


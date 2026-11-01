# Supervisión RAID y automatización

Ajustes y conexiones · 1.2.0.0

1. En Ajustes → Supervisión introduce dispositivos md existentes, por ejemplo md4. No cambia miembros RAID, particiones ni sincronización. Un resync con degraded=0 no prueba un fallo de disco.

2. La automatización revisa cada 60 segundos. Solo repara fallos de al menos 120 segundos en los servicios probados del monitor RAID. Límites: una hora entre intentos, máximo tres en 24 horas y espera compartida de 120 segundos.

3. /automatik_status muestra estado, intentos y bloqueos. /automatik_an y /automatik_aus guardan el cambio. Cada reparación automática requiere aviso previo por Telegram; el resultado se guarda hasta entregarlo. Fallos o resultados inciertos bloquean hasta un /raid_monitor_start manual exitoso.

4. La reparación permitida solo afecta a mdmonitor.service y mdmonitor-oneshot.service. Un oneshot inactivo tras éxito es normal. No es una prueba SMART ni reparación automática de discos.


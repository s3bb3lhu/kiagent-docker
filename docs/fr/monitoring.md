# Surveillance RAID et automatisation

Paramètres et connexions · 1.2.0.0

1. Dans Paramètres → Surveillance, saisissez des périphériques md existants, comme md4. Membres RAID, partitions et synchronisation restent inchangés. Un resync avec degraded=0 ne prouve pas une panne de disque.

2. L’automatisation vérifie toutes les 60 secondes. Seule une panne d’au moins 120 secondes des services RAID testés autorise une réparation. Limites : une heure entre essais, trois au maximum par 24 heures et délai partagé de 120 secondes.

3. /automatik_status affiche état, essais et délais. /automatik_an et /automatik_aus conservent le réglage. Chaque réparation automatique exige une annonce Telegram préalable ; les résultats restent jusqu’à livraison. Un échec ou doute bloque jusqu’à un /raid_monitor_start manuel réussi.

4. La réparation autorisée concerne uniquement mdmonitor.service et mdmonitor-oneshot.service. Un service oneshot inactif après réussite est normal. Il ne s’agit pas d’un test SMART ni d’une réparation automatique de disques.


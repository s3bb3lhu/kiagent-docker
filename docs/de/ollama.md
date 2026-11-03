# Ollama: lokale KI & Limits

Einstellungen & Verbindungen · 1.5.0.0

1. Unter Einstellungen → KI-Anbieter zwischen Ollama und OpenAI wählen. Ollama benötigt keinen API-Key. Es gibt keinen automatischen Anbieterwechsel bei Fehlern. Anfragen an Ollama bleiben auf dem Server; bei OpenAI werden Anfragen und Messwerte an OpenAI gesendet.

2. Vorhandene Ollama-Instanzen bleiben unverändert: keine Modell-Downloads, Updates, Neustarts oder Änderungen ihrer Limits. Nur vorhandene lokale Textmodelle werden angeboten. Bei fehlendem Modell oder gestopptem Dienst ist eine eigene administrative Einrichtung erforderlich.

3. Bei jeder Docker-Installation wird Ollama geprüft. Neue Instanzen erhalten höchstens 25 Prozent CPU, maximal zwei Kerne und 4 GiB RAM, zusätzlich verfügbarkeitsabhängige Reserven. Ein kleines Qwen3-Modell, eine parallele Anfrage, Kontext 2048 und kurze Speicherhaltezeit begrenzen Last. Zu wenig RAM oder freier Speicher führt zum Auslassen mit Statushinweis.

- [Ollama Docker](https://docs.ollama.com/docker)
- [Ollama FAQ](https://docs.ollama.com/faq)
- [Qwen3](https://ollama.com/library/qwen3)

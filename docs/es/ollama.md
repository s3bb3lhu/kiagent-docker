# Ollama: IA local y límites

Ajustes y conexiones · 1.4.0.0

1. Elige Ollama u OpenAI en Ajustes → Proveedor de IA. Ollama no necesita clave API. No se cambia de proveedor automáticamente. Ollama procesa en el servidor; OpenAI recibe solicitudes y mediciones.

2. Ollama existente queda intacto: sin descargas, actualizaciones, reinicios ni cambios de límites. Solo modelos de texto locales instalados. Modelos ausentes o servicios parados necesitan configuración administrativa.

3. Cada instalación Docker comprueba Ollama. Nuevas instancias usan como máximo 25 por ciento CPU, dos núcleos y 4 GiB RAM, con reservas adicionales. Modelo Qwen3 pequeño, una solicitud simultánea, contexto 2048 y permanencia corta limitan carga. Sin recursos suficientes se omite con aviso.

- [Ollama Docker](https://docs.ollama.com/docker)
- [Ollama FAQ](https://docs.ollama.com/faq)
- [Qwen3](https://ollama.com/library/qwen3)

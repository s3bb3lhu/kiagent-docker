# Ollama: local AI and limits

Settings and connections · 1.4.0.0

1. Choose Ollama or OpenAI under Settings → AI provider. Ollama needs no API key. Errors never switch providers automatically. Ollama processes requests on the server; OpenAI receives requests and measurements.

2. Existing Ollama stays unchanged: no model downloads, updates, restarts or changes to its limits. Only installed local text models are offered. Missing models or stopped services need separate administrative setup.

3. Every Docker installation checks Ollama. New instances receive at most 25 percent CPU, two cores and 4 GiB RAM, with additional available-memory reserves. A small Qwen3 model, one concurrent request, 2048 context and short keep-alive limit load. Insufficient RAM or disk skips installation with a status notice.

- [Ollama Docker](https://docs.ollama.com/docker)
- [Ollama FAQ](https://docs.ollama.com/faq)
- [Qwen3](https://ollama.com/library/qwen3)

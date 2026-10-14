# KoboKeeper — all-in-one image: app + Ollama + model baked in.
# The HOSTED DEMO runs gemma3:1b so it fits on a small (2GB) Render instance
# paid for with Hacktoberfest promo credits. Locally, users run `ollama pull
# gemma3:4b` for the full-quality model — that is the real product.
# MODEL_NAME is overridable at runtime: docker run -e MODEL_NAME=gemma3:4b ...

FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama via the official install script (tracks current URLs;
# standalone binary mode inside containers — no systemd needed).
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OLLAMA_HOST=http://localhost:11434
ENV MODEL_NAME=gemma3:1b
RUN ollama serve & sleep 12 && ollama pull gemma3:1b && sleep 2; pkill ollama || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD sh -c "ollama serve & sleep 10 && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
# KoboKeeper — all-in-one image: app + Ollama + gemma3:4b baked in.
# NOTE: the model pull at build time makes the image ~4GB and the first build
# slow (10-20 min). That is deliberate: the container is fully self-contained
# and needs no internet at runtime — which IS the product pitch.

FROM python:3.13-slim

# curl for Ollama download + container healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama (standalone binary, no systemd inside containers)
RUN curl -fsSL https://ollama.com/download/ollama-linux-amd64.tgz -o /tmp/ollama.tgz \
    && mkdir -p /opt/ollama \
    && tar -xzf /tmp/ollama.tgz -C /opt/ollama \
    && ln -s /opt/ollama/bin/ollama /usr/local/bin/ollama \
    && rm /tmp/ollama.tgz

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bake the model into the image at build time
ENV OLLAMA_HOST=http://localhost:11434
RUN ollama serve & sleep 12 && ollama pull gemma3:4b && sleep 2; pkill ollama || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start Ollama in the background, then the app in the foreground
CMD sh -c "ollama serve & sleep 10 && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

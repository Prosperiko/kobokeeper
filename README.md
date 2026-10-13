# KoboKeeper

KoboKeeper is an offline-first receipt bookkeeper for freelancers and small businesses.
It extracts structured receipt data locally with OCR + Gemma running through Ollama.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama pull gemma3:4b
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/dashboard.

# Perth Tradie Quote AI

Solo-founder MVP for Australian electricians and HVAC contractors in Perth. It records a voice memo, transcribes locally, asks local Ollama for structured quote data with a deterministic fallback parser, lets the tradie edit every number, and generates a branded PDF.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ollama setup

```bash
ollama pull llama3.1:70b
ollama serve
```

For fastest live demos on an RTX 4090, start Ollama before the demo and run one warm-up request:

```bash
curl http://localhost:11434/api/generate -d '{"model":"llama3.1:70b","prompt":"Return JSON {\"ok\":true}","stream":false,"format":"json"}'
```

If 70B is too slow for your quantization/VRAM setup, edit `OLLAMA_MODEL` in `llm_client.py` to a smaller local model you have pulled. The app still has a fast fallback parser for common demo jobs.

## Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. For phone testing on the same Wi-Fi, open `http://YOUR_LAN_IP:8000`.

## Demo via ngrok

```bash
ngrok http 8000
```

Open the HTTPS ngrok URL on iPhone Safari or Android Chrome. HTTPS is important for browser microphone permissions.

## Demo Mode

Tap **Demo Mode**, then choose one of:

- 2 downlights and a fan
- Full rewire 3-bedroom house
- Emergency callout switchboard

Demo Mode bypasses microphone nerves and loads pre-canned text through the full quote and PDF flow.

## Endpoint curl tests

```bash
curl http://localhost:8000/pricing-defaults
```

```bash
curl http://localhost:8000/demo-samples
```

```bash
curl -X POST http://localhost:8000/customers -H 'Content-Type: application/json' -d '{"name":"Jane Smith","phone":"0400000000","email":"jane@example.com","address":"Perth WA"}'
```

```bash
curl http://localhost:8000/customers
```

```bash
curl -X POST http://localhost:8000/generate-quote -H 'Content-Type: application/json' -d '{"text":"3 downlights in bedroom, 2 power points in garage, replace exhaust fan","profile":"Residential","customer":{"name":"Demo Customer"}}'
```

```bash
curl -X POST http://localhost:8000/update-quote -H 'Content-Type: application/json' -d '{"line_items":[{"description":"LED downlight supply and install","quantity":2,"material_unit_cost":22,"labor_hours":1,"hourly_rate":95,"material_markup_percent":20}]}'
```

```bash
curl -X POST http://localhost:8000/generate-pdf -H 'Content-Type: application/json' -o quote.pdf -d '{"quote_number":"Q-DEMO","customer":{"name":"Demo Customer"},"line_items":[{"description":"LED downlight supply and install","quantity":2,"material_unit_cost":22,"labor_hours":1,"hourly_rate":95,"material_markup_percent":20}]}'
```

For transcription, replace `sample.webm` with a real browser recording:

```bash
curl -X POST http://localhost:8000/transcribe -F audio=@sample.webm
```

## DEMO CHECKLIST

### Pre-demo steps

1. Plug laptop into power and confirm RTX 4090 drivers are available.
2. Start Ollama and warm up the chosen model.
3. Start FastAPI with `uvicorn main:app --host 0.0.0.0 --port 8000`.
4. Start ngrok and open the HTTPS URL on your phone.
5. Tap Demo Mode once and generate a PDF to prove the full path works.
6. Keep one fallback text prompt copied: `3 downlights in bedroom, 2 power points in garage, replace exhaust fan`.

### During-demo talking points

- “You speak the job exactly like a normal voice note.”
- “The AI drafts it, but you control every hour, rate, material cost and markup before sending.”
- “Perth defaults are built in: Residential $95/hr, Commercial $120/hr, FIFO $150/hr, Emergency $200/hr and GST.”
- “No cloud AI bill: the model is running locally on the GPU.”

### Fallback plans

- If microphone permission fails: type in the text box and tap **Build Quote**.
- If the LLM is cold: wait for **Warming up AI** or use Demo Mode; the fallback parser still creates common electrical quotes.
- If mobile signal is poor: demo on laptop localhost or phone on the same Wi-Fi.
- If PDF sharing is blocked by the browser: the PDF opens in a new tab and can be downloaded manually.

## Troubleshooting live demos

- **Microphone does not work:** use HTTPS via ngrok; Safari/Chrome often block mic on plain HTTP except localhost.
- **First request is slow:** Ollama is loading the model. Warm up before arriving.
- **Whisper dependency install is slow:** install once before the demo. Voice is optional because text fallback and Demo Mode are always available.
- **PDF does not open:** disable pop-up blocking for the site or tap Generate PDF again after interacting with the page.
- **Multiple people tap at once:** backend serializes quote generation with an in-process queue so the UI shows a clear waiting state.

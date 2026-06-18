from __future__ import annotations
import asyncio, tempfile, subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from models import *
from database import init_db, list_customers, add_customer, save_quote, get_pricing
from llm_client import generate_quote, recalc
from pdf_generator import build_pdf

app = FastAPI(title="Perth Tradie Quote AI", version="0.1.0")
queue = asyncio.Lock()
DEMO = [
    DemoSample(id="downlights-fan", title="2 downlights and a fan", text="Install 2 downlights in the lounge room and replace one ceiling fan in the main bedroom."),
    DemoSample(id="rewire", title="Full rewire 3-bedroom house", text="Full rewire of a three bedroom house in Perth, include new power points, light switches and RCD safety switches."),
    DemoSample(id="emergency", title="Emergency callout switchboard", text="Emergency callout for switchboard fault, replace one RCD safety switch and test power points."),
]

@app.on_event("startup")
def startup(): init_db()

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "memo.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(await audio.read()); src = f.name
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(src, fp16=False)
        return TranscriptionResponse(text=result.get("text", "").strip(), source="local-whisper")
    except Exception:
        try:
            out = subprocess.check_output(["whisper", src, "--model", "base", "--fp16", "False", "--output_format", "txt", "--output_dir", tempfile.gettempdir()], timeout=25, text=True)
            return TranscriptionResponse(text=out.strip(), source="whisper-cli")
        except Exception as exc:
            raise HTTPException(503, "Couldn't understand that — try speaking slower or type it in") from exc

@app.post("/generate-quote", response_model=Quote)
async def gen(req: QuoteRequest):
    async with queue:
        q = await asyncio.wait_for(generate_quote(req), timeout=30)
        return save_quote(q)

@app.get("/pricing-defaults", response_model=PricingSettings)
def pricing(): return get_pricing()

@app.post("/update-quote", response_model=Quote)
def update_quote(q: Quote): return recalc(q)

@app.post("/generate-pdf")
def generate_pdf(q: Quote):
    q = recalc(q)
    pdf = build_pdf(q)
    filename = f"quote-{q.quote_number or 'draft'}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={filename}"})

@app.get("/customers", response_model=list[Customer])
def customers(): return list_customers()

@app.post("/customers", response_model=Customer)
def create_customer(c: CustomerIn): return add_customer(c)

@app.get("/demo-samples", response_model=list[DemoSample])
def demo_samples(): return DEMO

app.mount("/", StaticFiles(directory=".", html=True), name="static")

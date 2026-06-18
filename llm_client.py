from __future__ import annotations
import json, re, asyncio, httpx
from models import LineItem, Quote, QuoteRequest
from database import get_pricing, get_customer

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:70b"

LABOR = {"downlight": .5, "power point": 1, "switch": .5, "rcd": 1.5, "fan": 2, "exhaust": 1.5, "rewire": 24, "callout": 1}
MATERIAL_MAP = {"downlight":"LED downlight", "power point":"Power point (double)", "switch":"Light switch", "rcd":"RCD safety switch", "ceiling fan":"Ceiling fan", "fan":"Ceiling fan", "exhaust":"Exhaust fan"}

def recalc(q: Quote) -> Quote:
    subtotal = 0.0
    for item in q.line_items:
        material = item.quantity * item.material_unit_cost * (1 + item.material_markup_percent / 100)
        labor = item.labor_hours * item.hourly_rate
        subtotal += material + labor
    q.subtotal = round(subtotal, 2); q.gst = round(subtotal * .10, 2); q.total = round(q.subtotal + q.gst, 2)
    return q

def fallback_quote(req: QuoteRequest) -> Quote:
    pricing = get_pricing(); rate = pricing.hourly_rates.get(req.profile, 95); text = req.text.lower(); items=[]
    patterns = [("downlight", r"(\d+)\s+downlights?"), ("power point", r"(\d+)\s+(?:power\s*)points?"), ("exhaust", r"(\d+)?\s*exhaust\s+fans?"), ("fan", r"(\d+)?\s*(?:ceiling\s*)?fans?"), ("rcd", r"(\d+)?\s*rcd"), ("switch", r"(\d+)?\s*(?:light\s*)?switch"), ("rewire", r"rewire"), ("callout", r"emergency|callout|switchboard")]
    for key, pat in patterns:
        for m in re.finditer(pat, text):
            qty = float(m.group(1) or 1) if m.groups() else 1
            mat_name = MATERIAL_MAP.get(key, key.title()); mat = pricing.materials.get(mat_name, 0)
            hours = LABOR.get(key, 1) * qty
            items.append(LineItem(description=f"{mat_name} supply and install" if mat else key.title(), quantity=qty, material_unit_cost=mat, labor_hours=hours, hourly_rate=rate, material_markup_percent=pricing.markup_percent))
    if not items:
        items.append(LineItem(description=req.text[:90] or "Custom electrical/HVAC work", quantity=1, labor_hours=2, hourly_rate=rate, material_markup_percent=pricing.markup_percent))
    customer = get_customer(req.customer_id) if req.customer_id else req.customer
    return recalc(Quote(customer=customer, customer_id=req.customer_id, profile=req.profile, line_items=items, terms=pricing.default_terms))

async def generate_quote(req: QuoteRequest) -> Quote:
    schema = '{"line_items":[{"description":"string","quantity":1,"location":"string","material_unit_cost":0,"labor_hours":0}]}'
    prompt = f"""You are an Australian electrical quoting assistant. Extract job details from the tradie's description and generate a structured quote. Use standard Australian electrical terminology. Estimate labor hours conservatively. Return ONLY valid JSON matching this schema: {schema}\nDescription: {req.text}"""
    try:
        async with httpx.AsyncClient(timeout=18) as client:
            r = await client.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"num_predict": 900}})
            r.raise_for_status(); data = json.loads(r.json().get("response", "{}"))
        q = fallback_quote(req); generated = data.get("line_items") or []
        if generated:
            base = fallback_quote(req)
            q.line_items = [LineItem(hourly_rate=base.line_items[0].hourly_rate if base.line_items else 95, material_markup_percent=get_pricing().markup_percent, **x) for x in generated]
            return recalc(q)
    except Exception:
        await asyncio.sleep(.1)
    return fallback_quote(req)

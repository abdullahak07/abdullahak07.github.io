from __future__ import annotations

import asyncio
import json
import os
import re

import httpx

from database import get_customer, get_pricing
from models import LineItem, Quote, QuoteRequest

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

LABOR_HOURS = {
    "downlight": 0.5,
    "power point": 1.0,
    "switch": 0.5,
    "rcd": 1.5,
    "ceiling fan": 2.0,
    "exhaust fan": 1.5,
    "rewire": 24.0,
    "callout": 1.0,
}

MATERIAL_NAME = {
    "downlight": "LED downlight",
    "power point": "Power point (double)",
    "switch": "Light switch",
    "rcd": "RCD safety switch",
    "ceiling fan": "Ceiling fan",
    "exhaust fan": "Exhaust fan",
}

PATTERNS = [
    ("downlight", r"(\d+)\s+downlights?"),
    ("power point", r"(\d+)\s+(?:power\s*)points?"),
    ("exhaust fan", r"(\d+)?\s*exhaust\s+fans?"),
    ("ceiling fan", r"(\d+)?\s*(?:ceiling\s*)?fans?"),
    ("rcd", r"(\d+)?\s*rcd"),
    ("switch", r"(\d+)?\s*(?:light\s*)?switch"),
    ("rewire", r"rewire"),
    ("callout", r"emergency|callout|switchboard"),
]


def recalc(quote: Quote) -> Quote:
    subtotal = 0.0
    for item in quote.line_items:
        materials = item.quantity * item.material_unit_cost * (1 + item.material_markup_percent / 100)
        labor = item.labor_hours * item.hourly_rate
        subtotal += materials + labor
    quote.subtotal = round(subtotal, 2)
    quote.gst = round(subtotal * 0.10, 2)
    quote.total = round(quote.subtotal + quote.gst, 2)
    return quote


def fallback_quote(req: QuoteRequest) -> Quote:
    pricing = get_pricing()
    hourly_rate = pricing.hourly_rates.get(req.profile, pricing.hourly_rates["Residential"])
    text = req.text.lower()
    line_items: list[LineItem] = []

    for key, pattern in PATTERNS:
        for match in re.finditer(pattern, text):
            quantity = float(match.group(1) or 1) if match.groups() else 1.0
            material = MATERIAL_NAME.get(key)
            unit_cost = pricing.materials.get(material, 0) if material else 0
            hours = LABOR_HOURS.get(key, 1.0) * quantity
            description = f"{material} supply and install" if material else key.title()
            line_items.append(
                LineItem(
                    description=description,
                    quantity=quantity,
                    material_unit_cost=unit_cost,
                    labor_hours=hours,
                    hourly_rate=hourly_rate,
                    material_markup_percent=pricing.markup_percent,
                )
            )

    if not line_items:
        line_items.append(
            LineItem(
                description=req.text[:90] or "Custom electrical/HVAC work",
                quantity=1,
                labor_hours=2,
                hourly_rate=hourly_rate,
                material_markup_percent=pricing.markup_percent,
            )
        )

    customer = get_customer(req.customer_id) if req.customer_id else req.customer
    return recalc(Quote(customer=customer, customer_id=req.customer_id, profile=req.profile, line_items=line_items, terms=pricing.default_terms))


async def generate_quote(req: QuoteRequest) -> Quote:
    schema = '{"line_items":[{"description":"string","quantity":1,"location":"string","material_unit_cost":0,"labor_hours":0}]}'
    prompt = f"""You are an Australian electrical quoting assistant. Extract job details from the tradie's description and generate a structured quote. Use standard Australian electrical terminology. Estimate labor hours conservatively — better to under-promise and over-deliver. Always include a 10% GST calculation. Return ONLY valid JSON matching this schema: {schema}
Description: {req.text}"""

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(18.0, connect=2.0)) as client:
            response = await client.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"num_predict": 700}},
            )
            response.raise_for_status()
            payload = json.loads(response.json().get("response", "{}"))

        quote = fallback_quote(req)
        generated_items = payload.get("line_items") or []
        if generated_items:
            pricing = get_pricing()
            rate = pricing.hourly_rates.get(req.profile, pricing.hourly_rates["Residential"])
            quote.line_items = [
                LineItem(hourly_rate=rate, material_markup_percent=pricing.markup_percent, **item)
                for item in generated_items
            ]
            return recalc(quote)
    except Exception:
        await asyncio.sleep(0.1)

    return fallback_quote(req)

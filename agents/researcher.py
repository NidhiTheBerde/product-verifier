"""
Product Researcher Agent
Agentic loop: autonomously searches the web to gather ingredients, claims,
molecular formulas, and sources for a given product.
Tools: web_search_20260209 + web_fetch_20260209
"""

import json
import re
import anthropic
from dataclasses import dataclass

THINKING_DIM  = "\033[2m"
THINKING_CYAN = "\033[2;36m"
RESET = "\033[0m"

SYSTEM_PROMPT = """You are a meticulous product researcher specializing in consumer goods — cosmetics, supplements, skincare, food products.

Given a product name, use web_search and web_fetch to find:
1. Full ingredient list (INCI names where available)
2. Product claims (what the manufacturer says it does)
3. Intended use and target tissue/area
4. Each key active ingredient with:
   - Common name and INCI name
   - Stated molecular formula (e.g. C18H36O2)
   - Stated concentration or % if disclosed
   - Role/function claimed
5. Any clinical studies or peer-reviewed research cited by the brand
6. Regulatory status (FDA, EU CosIng, etc.) if findable

Search strategy: start broad (product name + ingredients), then fetch specific ingredient pages, then look for clinical evidence. Do multiple searches until you have enough data to fill the schema.

Respond ONLY with a raw JSON object (no markdown, no fences):
{
  "product_name": "...",
  "brand": "...",
  "category": "skincare | supplement | food | haircare | other",
  "intended_use": "...",
  "claims": ["..."],
  "ingredient_list": ["..."],
  "key_actives": [
    {
      "name": "...",
      "inci_name": "...",
      "role": "...",
      "molecular_formula": "... or null",
      "concentration": "... or unknown"
    }
  ],
  "cited_studies": ["..."],
  "regulatory_notes": "...",
  "sources": ["..."]
}

If a field is unavailable, use null. Do not guess formulas — only include what you found via search."""


@dataclass
class ProductResearch:
    product_name: str
    brand: str
    category: str
    intended_use: str
    claims: list[str]
    ingredient_list: list[str]
    key_actives: list[dict]
    cited_studies: list[str]
    regulatory_notes: str
    sources: list[str]
    raw_response: str


def _stream_thinking_and_text(stream, label: str):
    """Stream events to stdout, showing thinking in dim cyan and text normally."""
    in_thinking = False
    for event in stream:
        if event.type == "content_block_start":
            block = event.content_block
            if block.type == "thinking":
                in_thinking = True
                print(f"\n{THINKING_CYAN}[{label} thinking...]{RESET}", flush=True)
            elif block.type == "text":
                if in_thinking:
                    print()
                    in_thinking = False
                print(f"\n[{label} response]", flush=True)
        elif event.type == "content_block_delta":
            delta = event.delta
            if delta.type == "thinking_delta":
                print(f"{THINKING_CYAN}{delta.thinking}{RESET}", end="", flush=True)
            elif delta.type == "text_delta":
                print(delta.text, end="", flush=True)
    print()


def research_product(
    product_name: str,
    client: anthropic.Anthropic,
    pdf_file_ids: list[str] | None = None,
) -> ProductResearch:
    """Run the Product Researcher agent. Optionally attach uploaded PDF file IDs."""
    print(f"\n[Researcher] Starting agentic research for: {product_name}")

    user_content: list = []

    # Attach any uploaded PDFs (e.g. clinical studies the user provided)
    for fid in (pdf_file_ids or []):
        user_content.append({
            "type": "document",
            "source": {"type": "file", "file_id": fid},
        })

    user_content.append({
        "type": "text",
        "text": f"Research this product thoroughly: {product_name}",
    })

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        tools=[
            {"type": "web_search_20260209", "name": "web_search"},
            {"type": "web_fetch_20260209",  "name": "web_fetch"},
        ],
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        _stream_thinking_and_text(stream, "Researcher")
        response = stream.get_final_message()

    raw_text = next((b.text for b in response.content if b.type == "text"), "{}")

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", raw_text)
        data = json.loads(match.group()) if match else {}

    return ProductResearch(
        product_name=data.get("product_name", product_name),
        brand=data.get("brand", "Unknown"),
        category=data.get("category", "unknown"),
        intended_use=data.get("intended_use", ""),
        claims=data.get("claims") or [],
        ingredient_list=data.get("ingredient_list") or [],
        key_actives=data.get("key_actives") or [],
        cited_studies=data.get("cited_studies") or [],
        regulatory_notes=data.get("regulatory_notes") or "",
        sources=data.get("sources") or [],
        raw_response=raw_text,
    )

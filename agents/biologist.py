"""
Biology Researcher Agent
Uses code_execution to query PubChem and verify molecular formulas, molecular weights,
skin penetration rules (Lipinski 500 Da, logP), and bioavailability.
Tools: code_execution_20260120
"""

import json
import re
import anthropic
from dataclasses import dataclass

THINKING_CYAN = "\033[2;36m"
RESET = "\033[0m"

SYSTEM_PROMPT = """You are a senior biochemist and dermatologist. You have deep expertise in:
- Human skin anatomy: stratum corneum, epidermis, dermis, skin barrier function
- Percutaneous absorption and topical bioavailability
- Molecular biology: receptor binding, enzyme pathways, cell signaling
- Nutritional biochemistry and gut absorption
- Cosmetic chemistry and formulation science
- Evidence-based dermatology and pharmacology

You receive structured product research. Your job is to scientifically verify it using code execution.

FOR EACH KEY ACTIVE INGREDIENT, you MUST:
1. Write and execute Python code to query PubChem REST API:
   https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{ingredient}/property/MolecularFormula,MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount/JSON
2. Compare the claimed molecular formula against PubChem's verified formula
3. Apply the Lipinski 500 Da rule: MW < 500 → can penetrate skin/membrane; MW > 500 → unlikely without enhancement
4. Apply logP rule: 1 ≤ XLogP ≤ 4 is optimal for transdermal/skin penetration
5. Apply TPSA rule: TPSA < 60 Ų for good skin penetration
6. Based on actual physico-chemical data, assess whether claims are scientifically plausible

Example code pattern for PubChem query:
```python
import urllib.request, json, urllib.parse

def query_pubchem(name):
    encoded = urllib.parse.quote(name)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/property/MolecularFormula,MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount/JSON"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

result = query_pubchem("niacinamide")
print(json.dumps(result, indent=2))
```

After running code for all actives, respond with raw JSON (no markdown fences):
{
  "product_name": "...",
  "overall_verdict": "scientifically_supported | partially_supported | unsupported | insufficient_data",
  "confidence": "high | medium | low",
  "summary": "2-3 sentence plain-language verdict for a non-scientist",
  "active_assessments": [
    {
      "ingredient": "...",
      "claimed_formula": "... or null",
      "pubchem_formula": "... or null",
      "formula_match": true | false | null,
      "molecular_weight_da": 0.0,
      "logP": 0.0,
      "tpsa_angstrom2": 0.0,
      "passes_500da_rule": true | false,
      "passes_logp_rule": true | false,
      "bioavailability_assessment": "high | medium | low | unknown",
      "mechanism_plausible": true | false,
      "mechanism_notes": "...",
      "claim_verdict": "supported | partially_supported | unsupported | insufficient_data"
    }
  ],
  "formulation_concerns": ["..."],
  "missing_evidence": ["..."],
  "scientific_references": ["relevant mechanism or paper you know"]
}"""


@dataclass
class BiologyVerdict:
    product_name: str
    overall_verdict: str
    confidence: str
    summary: str
    active_assessments: list[dict]
    formulation_concerns: list[str]
    missing_evidence: list[str]
    scientific_references: list[str]
    raw_response: str


def _stream_thinking_and_text(stream, label: str):
    THINKING_CYAN = "\033[2;36m"
    RESET = "\033[0m"
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


def verify_product(research_json: str, client: anthropic.Anthropic) -> BiologyVerdict:
    """Run Biology Researcher agent. Uses code_execution to query PubChem."""
    print("\n[Biologist] Starting molecular verification...")

    user_message = f"""Here is the product research. Verify each active ingredient scientifically using code execution to query PubChem:

{research_json}

Execute PubChem queries for each key active, then provide your full assessment."""

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
            {"type": "code_execution_20260120", "name": "code_execution"},
        ],
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        _stream_thinking_and_text(stream, "Biologist")
        response = stream.get_final_message()

    raw_text = next((b.text for b in response.content if b.type == "text"), "{}")

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", raw_text)
        data = json.loads(match.group()) if match else {}

    return BiologyVerdict(
        product_name=data.get("product_name", ""),
        overall_verdict=data.get("overall_verdict", "insufficient_data"),
        confidence=data.get("confidence", "low"),
        summary=data.get("summary", ""),
        active_assessments=data.get("active_assessments") or [],
        formulation_concerns=data.get("formulation_concerns") or [],
        missing_evidence=data.get("missing_evidence") or [],
        scientific_references=data.get("scientific_references") or [],
        raw_response=raw_text,
    )

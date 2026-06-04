# Product Verifier

A two-agent AI pipeline that scientifically evaluates consumer products — skincare, supplements, food, haircare — by cross-referencing manufacturer claims against real molecular data from PubChem and peer-reviewed evidence.

## How It Works

```
Product Name
     │
     ▼
┌─────────────────────────┐
│   Agent 1: Researcher   │  ← web search + web fetch
│                         │    gathers ingredients, claims,
│                         │    molecular formulas, studies
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Agent 2: Biologist    │  ← PubChem API via code execution
│                         │    verifies formulas, MW, logP, TPSA
│                         │    scores bioavailability & plausibility
└────────────┬────────────┘
             │
             ▼
     Scientific Verdict
```

**Agent 1 — Product Researcher** autonomously searches the web to extract the full ingredient list, key active compounds with molecular formulas and concentrations, brand claims, regulatory status, and cited clinical studies.

**Agent 2 — Biologist** takes that research and runs live Python code to query the PubChem REST API for every key active. It applies three penetration rules to each ingredient:

| Rule | Threshold | Meaning |
|------|-----------|---------|
| Lipinski 500 Da | MW < 500 Da | Can penetrate skin/membrane |
| logP | 1 ≤ logP ≤ 4 | Optimal transdermal absorption |
| TPSA | TPSA < 60 Ų | Good skin permeability |

The final verdict is one of: `SCIENTIFICALLY SUPPORTED` · `PARTIALLY SUPPORTED` · `UNSUPPORTED` · `INSUFFICIENT DATA`

## Features

- **Real-time thinking** — extended thinking streamed live as each agent reasons
- **Agentic research loop** — researcher keeps searching until it has enough data
- **PubChem molecular verification** — formula, molecular weight, logP, and TPSA checked against authoritative chemical database
- **PDF support** — attach clinical studies or ingredient sheets for deeper analysis
- **Session memory** — results cached for 7 days so repeat lookups are instant
- **JSON export** — full structured result saved per product

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/product-verifier.git
cd product-verifier
pip install -r requirements.txt
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

**Verify a product:**
```bash
python main.py "CeraVe Moisturizing Cream"
```

**Attach a clinical study PDF:**
```bash
python main.py "The Ordinary Niacinamide 10%" --pdf study.pdf
```

**Force a fresh analysis (bypass cache):**
```bash
python main.py "CeraVe Moisturizing Cream" --refresh
```

**List all cached products:**
```bash
python main.py --list
```

## Example Output

```
────────────────────────────────────────────────────────────
  RESEARCH SUMMARY
────────────────────────────────────────────────────────────
  Product:   CeraVe Moisturizing Cream
  Brand:     CeraVe
  Category:  skincare
  Use:       Daily moisturizer for face and body

  Key Actives:
    • Ceramide NP  [C34H67NO3]  1%
      Role: Restores skin barrier lipid matrix
    • Niacinamide  [C6H6N2O]   unknown
      Role: Anti-inflammatory, pore-minimizing

────────────────────────────────────────────────────────────
  SCIENTIFIC VERDICT
────────────────────────────────────────────────────────────
  Verdict:    SCIENTIFICALLY SUPPORTED
  Confidence: HIGH

  Active Ingredient Analysis (PubChem-verified):
    [✓] Niacinamide
         Formula claimed: C6H6N2O  |  PubChem: C6H6N2O  [✓ match]
         MW: 122.1 Da [✓ 500Da rule]  logP: -0.4  [✓ logP rule]  TPSA: 55.1 Ų
         Bioavailability: Good skin penetration expected
         Claim verdict: Plausible — well-supported by literature
```

## Requirements

- Python 3.10+
- `anthropic >= 0.50.0`
- Anthropic API key with access to Claude models and tool use

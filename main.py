#!/usr/bin/env python3
"""
Product Verifier — Enhanced Two-Agent Pipeline

Features:
  - Adaptive thinking displayed in real-time
  - Agentic researcher: multiple web searches until thorough
  - Biologist: queries PubChem via code execution for molecular verification
  - Session memory: caches results for 7 days
  - PDF support: attach clinical studies or ingredient sheets

Usage:
    python main.py "CeraVe Moisturizing Cream"
    python main.py "The Ordinary Niacinamide 10%" --pdf study.pdf
    python main.py "CeraVe Moisturizing Cream" --refresh
    python main.py --list
"""

import sys
import json
import argparse
import anthropic
from pathlib import Path

from agents.researcher import research_product
from agents.biologist import verify_product
from memory.store import get as mem_get, put as mem_put, list_cached

VERDICT_COLORS = {
    "scientifically_supported": "\033[92m",
    "partially_supported":       "\033[93m",
    "unsupported":               "\033[91m",
    "insufficient_data":         "\033[94m",
}
BOLD  = "\033[1m"
RESET = "\033[0m"


def upload_pdfs(client: anthropic.Anthropic, paths: list[str]) -> list[str]:
    ids = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"[Warning] PDF not found: {p}, skipping.")
            continue
        print(f"[Files] Uploading {path.name}...")
        with open(path, "rb") as f:
            result = client.beta.files.upload(file=(path.name, f, "application/pdf"))
        ids.append(result.id)
        print(f"[Files] Uploaded {path.name} → {result.id}")
    return ids


def sec(title: str):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")


def print_research(r):
    sec("RESEARCH SUMMARY")
    print(f"  Product:   {r.product_name}")
    print(f"  Brand:     {r.brand}")
    print(f"  Category:  {r.category}")
    print(f"  Use:       {r.intended_use}")
    if r.regulatory_notes:
        print(f"  Regulatory: {r.regulatory_notes}")
    if r.claims:
        print("\n  Claims:")
        for c in r.claims:
            print(f"    - {c}")
    if r.key_actives:
        print("\n  Key Actives (researcher found):")
        for a in r.key_actives:
            formula = a.get("molecular_formula") or "formula unknown"
            conc    = a.get("concentration") or "conc unknown"
            print(f"    • {a.get('name', '?')}  [{formula}]  {conc}")
            print(f"      Role: {a.get('role', '?')}")
    if r.cited_studies:
        print("\n  Cited Studies:")
        for s in r.cited_studies:
            print(f"    · {s}")


def print_verdict(v):
    color = VERDICT_COLORS.get(v.overall_verdict, "")
    sec("SCIENTIFIC VERDICT")
    print(f"  Product:    {v.product_name}")
    print(f"  Verdict:    {color}{BOLD}{v.overall_verdict.upper().replace('_', ' ')}{RESET}")
    print(f"  Confidence: {v.confidence.upper()}")
    print(f"\n  {v.summary}")

    if v.active_assessments:
        print("\n  Active Ingredient Analysis (PubChem-verified):")
        for a in v.active_assessments:
            ok = "✓" if a.get("mechanism_plausible") else "✗"
            print(f"\n    [{ok}] {a.get('ingredient', '?')}")

            claimed = a.get("claimed_formula") or "—"
            pubchem = a.get("pubchem_formula") or "—"
            match   = a.get("formula_match")
            match_s = ("✓ match" if match else "✗ mismatch") if match is not None else "n/a"
            print(f"         Formula claimed: {claimed}  |  PubChem: {pubchem}  [{match_s}]")

            mw = a.get("molecular_weight_da")
            logp = a.get("logP")
            tpsa = a.get("tpsa_angstrom2")
            da_ok   = a.get("passes_500da_rule")
            logp_ok = a.get("passes_logp_rule")
            if mw:
                da_mark   = "✓" if da_ok   else "✗"
                logp_mark = "✓" if logp_ok else "✗"
                print(f"         MW: {mw} Da [{da_mark} 500Da rule]  logP: {logp}  [{logp_mark} logP rule]  TPSA: {tpsa} Ų")

            print(f"         Bioavailability: {a.get('bioavailability_assessment', '?')}")
            print(f"         Claim verdict:   {a.get('claim_verdict', '?')}")
            if a.get("mechanism_notes"):
                print(f"         Notes: {a.get('mechanism_notes')}")

    if v.formulation_concerns:
        print("\n  Formulation Concerns:")
        for c in v.formulation_concerns:
            print(f"    ⚠  {c}")

    if v.missing_evidence:
        print("\n  Missing Evidence:")
        for e in v.missing_evidence:
            print(f"    - {e}")

    if v.scientific_references:
        print("\n  Scientific References:")
        for r in v.scientific_references:
            print(f"    · {r}")


def main():
    parser = argparse.ArgumentParser(description="Product Verifier")
    parser.add_argument("product", nargs="*", help="Product name to verify")
    parser.add_argument("--pdf",     nargs="+", metavar="FILE", help="PDF files to attach (clinical studies, ingredient sheets)")
    parser.add_argument("--refresh", action="store_true", help="Ignore memory cache, re-run from scratch")
    parser.add_argument("--list",    action="store_true", help="List cached products")
    args = parser.parse_args()

    if args.list:
        cached = list_cached()
        if not cached:
            print("No cached products.")
        else:
            print(f"\n{'Product':<40} {'Cached At':<25} {'Expires In'}")
            print("─" * 80)
            for c in cached:
                print(f"{c['product']:<40} {c['cached_at'][:19]:<25} {c['expires_in_days']} days")
        return

    if not args.product:
        parser.print_help()
        sys.exit(1)

    product_name = " ".join(args.product)
    client = anthropic.Anthropic()

    # Check memory first
    if not args.refresh:
        cached = mem_get(product_name)
        if cached:
            print(f"\n[Memory] Using cached result from {cached['cached_at'][:19]} (use --refresh to re-run)")
            # Reconstruct and display from cache
            from agents.researcher import ProductResearch
            from agents.biologist import BiologyVerdict

            r = cached["research"]
            v = cached["verdict"]

            class _R:
                pass
            research = _R()
            research.__dict__.update(r)

            class _V:
                pass
            verdict = _V()
            verdict.__dict__.update(v)

            print_research(research)
            print_verdict(verdict)
            return

    # Upload PDFs if provided
    pdf_ids = upload_pdfs(client, args.pdf or [])

    sec(f"RESEARCHING: {product_name}")

    # Agent 1: Product Researcher
    research = research_product(product_name, client, pdf_file_ids=pdf_ids)
    print_research(research)

    # Build research JSON for biologist
    research_json = json.dumps({
        "product_name": research.product_name,
        "brand": research.brand,
        "category": research.category,
        "intended_use": research.intended_use,
        "claims": research.claims,
        "ingredient_list": research.ingredient_list,
        "key_actives": research.key_actives,
        "cited_studies": research.cited_studies,
        "regulatory_notes": research.regulatory_notes,
    }, indent=2)

    # Agent 2: Biology Researcher
    verdict = verify_product(research_json, client)
    print_verdict(verdict)

    # Save to memory
    mem_put(product_name, {
        "product_name": research.product_name,
        "brand": research.brand,
        "category": research.category,
        "intended_use": research.intended_use,
        "claims": research.claims,
        "ingredient_list": research.ingredient_list,
        "key_actives": research.key_actives,
        "cited_studies": research.cited_studies,
        "regulatory_notes": research.regulatory_notes,
        "sources": research.sources,
    }, {
        "product_name": verdict.product_name,
        "overall_verdict": verdict.overall_verdict,
        "confidence": verdict.confidence,
        "summary": verdict.summary,
        "active_assessments": verdict.active_assessments,
        "formulation_concerns": verdict.formulation_concerns,
        "missing_evidence": verdict.missing_evidence,
        "scientific_references": verdict.scientific_references,
    })

    # Save full JSON result
    safe = product_name.lower().replace(" ", "_")[:40]
    out = Path(f"result_{safe}.json")
    out.write_text(json.dumps({
        "research": research.__dict__ | {"raw_response": None},
        "verdict":  verdict.__dict__  | {"raw_response": None},
    }, indent=2, default=str))
    print(f"\n  Full result saved to: {out}")


if __name__ == "__main__":
    main()

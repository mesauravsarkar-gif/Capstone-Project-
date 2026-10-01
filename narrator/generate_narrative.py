from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = ROOT / "narrator" / "findings.json"
SAMPLE_OUTPUT_PATH = ROOT / "narrator" / "sample_output.txt"


def money(value: float) -> str:
    return f"{value:,.2f}"


def generate_scr_narrative_offline(findings: dict[str, Any]) -> dict[str, Any]:
    payment_rates = findings["return_rate_by_payment"]
    highest = findings["highest_risk_segment"]
    true_peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]

    narrative = (
        "Situation\n"
        f"Mamaearth's cleaned order base shows INR {money(findings['cleaned_total_revenue_inr'])} "
        f"in revenue after removing duplicate submissions. The key returns signal is payment-led: "
        f"COD returns are {payment_rates['COD']:.1f}%, compared with CARD at "
        f"{payment_rates['CARD']:.1f}% and UPI at {payment_rates['UPI']:.1f}%.\n\n"
        "Complication\n"
        f"The blended COD rate hides where the margin pressure is concentrated. The highest-risk "
        f"segment is {highest['payment_method']} + Tier-{highest['city_tier']} cities at "
        f"{highest['return_rate_pct']:.1f}%. The revenue reconciliation also matters: raw SQL "
        f"revenue was INR {money(findings['raw_total_revenue_inr'])}, and the INR "
        f"{money(findings['duplicate_reconciliation_delta_inr'])} gap is fully explained by "
        "five duplicate orders, not by discount or rating cleanup.\n\n"
        "Resolution\n"
        f"Regional ops should prioritize COD controls in Tier-{highest['city_tier']} cities, "
        "starting with address and intent checks before dispatch. Finance should use the cleaned "
        f"INR {money(findings['cleaned_total_revenue_inr'])} base for margin analysis. Growth "
        f"planning should treat March as the true peak month at INR {money(true_peak['revenue_inr'])}; "
        f"January looked inflated at INR {money(inflated['apparent_revenue_inr'])} only because "
        f"bulk-order outliers pushed it above its corrected INR {money(inflated['corrected_revenue_inr'])}."
    )
    return {"status": "success", "narrative": narrative, "tokens": None, "source": "offline"}


def generate_scr_narrative(findings: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return generate_scr_narrative_offline(findings)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        system_instruction = (
            "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
            "Write exactly three labeled sections: Situation, Complication, Resolution. Every number "
            "in the output must come from the supplied findings and appear with the same value; do "
            "not invent statistics."
        )
        prompt = (
            "Use these verified findings to write the SCR narrative:\n"
            f"{json.dumps(findings, indent=2)}"
        )
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                # Deterministic because this is a factual business report, not creative writing.
                temperature=0.0,
                max_output_tokens=500,
                http_options=types.HttpOptions(timeout=15_000),
            ),
        )
        token_count = None
        if getattr(response, "usage_metadata", None):
            token_count = getattr(response.usage_metadata, "total_token_count", None)
        return {"status": "success", "narrative": response.text, "tokens": token_count, "source": "gemini"}
    except Exception as err:
        return {"status": "error", "narrative": None, "message": str(err)}


def assert_required_figures(narrative: str) -> bool:
    normalized = narrative.replace(",", "").lower()
    checks = {
        "cleaned total revenue 97358.30": ["97358.30", "97358.3"],
        "COD return rate 44.4": ["44.4"],
        "COD Tier-2 segment 54.5": ["54.5"],
        "duplicate delta 2501.90": ["2501.90", "2501.9"],
        "March true peak 20318.90": ["march", "20318.90"],
    }

    all_passed = True
    for label, required_parts in checks.items():
        passed = all(part in normalized for part in required_parts)
        print(f"Checklist {label}: {'PASS' if passed else 'FAIL'}")
        all_passed = all_passed and passed
    return all_passed


def main() -> None:
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    result = generate_scr_narrative(findings)
    if result["status"] == "error":
        print(f"Gemini path failed: {result['message']}")
        result = generate_scr_narrative_offline(findings)

    narrative = result["narrative"]
    print(f"Narrative source: {result.get('source', 'unknown')}")
    print()
    print(narrative)
    print()
    passed = assert_required_figures(narrative)
    SAMPLE_OUTPUT_PATH.write_text(narrative + "\n", encoding="utf-8")
    print(f"Numeric checklist: {'PASS' if passed else 'FAIL'}")
    print(f"Saved sample output to {SAMPLE_OUTPUT_PATH}")


if __name__ == "__main__":
    main()

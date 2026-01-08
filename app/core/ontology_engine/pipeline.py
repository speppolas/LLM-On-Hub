#pipeline.py# app/core/ontology_engine/pipeline.py

import os
import json
import time
import logging
from typing import Dict, Any, List

from app.core.ontology_engine.ontology_loader import (
    load_patient_ontology,
    load_trial_rules
)
from app.core.ontology_engine.ontology_reasoner import derive_ontology_facts
from app.core.ontology_engine.ground_patient_facts import ground_patient_facts
from app.core.ontology_engine.rule_evaluator import evaluate_rule
from app.core.ontology_engine.trace_builder import build_trace
from app.core.ontology_engine.explainer import explain_decision_with_llm

logger = logging.getLogger(__name__)

TRIAL_RULES_DIR = "app/core/ontology_engine/trial_rules"


# -------------------------
# Utility: debug dump
# -------------------------
def _dump_ns_debug(payload: dict, prefix: str = "ns_run") -> str:
    os.makedirs("logs", exist_ok=True)
    filename = f"logs/{prefix}_{int(time.time())}.json"
    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)
    return filename


# -------------------------
# Final decision logic
# -------------------------
def decide_overall(inclusions: List[dict], exclusions: List[dict]) -> str:
    """
    Clinical eligibility logic (deterministic).

    Rules:
    - Any exclusion MET -> NOT eligible
    - Any inclusion NOT_MET -> NOT eligible
    - Any inclusion UNKNOWN -> UNKNOWN
    - Any exclusion UNKNOWN -> UNKNOWN
    - Otherwise -> ELIGIBLE
    """

    # Guardrail: trial with no inclusion criteria is NOT evaluable
    if not inclusions:
        return "not_eligible"

    for exc in exclusions:
        if exc["status"] == "met":
            return "not_eligible"

    for exc in exclusions:
        if exc["status"] == "unknown":
            return "unknown"
        
    for inc in inclusions:
        if inc["status"] == "not_met":
            return "not_eligible"

    for inc in inclusions:
        if inc["status"] == "unknown":
            return "unknown"

    return "eligible"


# -------------------------
# Main pipeline
# -------------------------
def evaluate_patient_against_trials(
    patient: Dict[str, Any],
    with_explanations: bool = False
) -> List[Dict[str, Any]]:

    # 1️⃣ Load ontology & derive facts
    ontology = load_patient_ontology()
    derived_facts = derive_ontology_facts(patient, ontology)

    # 2️⃣ Ground patient facts → ontology concepts
    grounded = ground_patient_facts(patient, ontology)
    patient_facts = grounded["facts"]
    grounding_trace = grounded["grounding_trace"]

    results: List[Dict[str, Any]] = []

    run_debug = {
        "patient_input": patient,
        "derived_facts": derived_facts,
        "patient_facts": patient_facts,
        "grounding_trace": grounding_trace,
        "trials": []
    }

    # 3️⃣ Iterate trials
    for filename in sorted(os.listdir(TRIAL_RULES_DIR)):
        if not filename.endswith(".yaml"):
            continue

        trial_key = filename.replace(".yaml", "")
        trial_rules = load_trial_rules(trial_key)

        if not isinstance(trial_rules, dict):
            logger.error(f"Invalid trial rules for {trial_key}")
            continue

        trial_id = trial_rules.get("trial_id", trial_key)
        title = trial_rules.get("title", "Unknown Trial")

        inclusion_rules = trial_rules.get("inclusion", [])
        exclusion_rules = trial_rules.get("exclusion", [])

        inclusion_results: List[dict] = []
        exclusion_results: List[dict] = []

        # Guardrail: empty trial
        if not inclusion_rules and not exclusion_rules:
            trace = build_trace(
                trial_id=trial_id,
                inclusion=[],
                exclusion=[],
                overall="unknown"
            )
            results.append({
                "trial_id": trial_id,
                "title": title,
                "overall": "unknown",
                "trace": trace,
                "error": "trial_rules_empty"
            })
            continue

        # 4️⃣ Evaluate inclusion
        for rule in inclusion_rules:
            status = evaluate_rule(rule, patient, derived_facts)
            inclusion_results.append({
                "id": rule.get("id"),
                "field": rule.get("field"),
                "condition": rule.get("condition"),
                "value": rule.get("value"),
                "status": status,
                "patient_value": patient.get(rule.get("field")),
                "text": rule.get("text", "")
            })

        # 5️⃣ Evaluate exclusion
        for rule in exclusion_rules:
            status = evaluate_rule(rule, patient, derived_facts)
            exclusion_results.append({
                "id": rule.get("id"),
                "field": rule.get("field"),
                "condition": rule.get("condition"),
                "value": rule.get("value"),
                "status": status,
                "patient_value": patient.get(rule.get("field")),
                "text": rule.get("text", "")
            })

        # 6️⃣ Decide
        overall = decide_overall(inclusion_results, exclusion_results)

        trace = build_trace(
            trial_id=trial_id,
            inclusion=inclusion_results,
            exclusion=exclusion_results,
            overall=overall
        )

        item = {
            "trial_id": trial_id,
            "title": title,
            "overall": overall,
            "trace": trace
        }

        # 7️⃣ Optional: LLM explanation (post-decision)
        if with_explanations:
            try:
                explanation = explain_decision_with_llm(
                    patient_facts=patient_facts,
                    ontology_trace=grounding_trace,
                    decision_trace=trace,
                    final_decision=overall
                )
                item["explanation"] = explanation
            except Exception as e:
                logger.warning(f"LLM explanation failed for {trial_id}: {e}")

        results.append(item)

        run_debug["trials"].append({
            "trial_id": trial_id,
            "title": title,
            "overall": overall,
            "inclusion_results": inclusion_results,
            "exclusion_results": exclusion_results
        })

    debug_file = _dump_ns_debug(run_debug)
    logger.info(f"💾 Saved neuro-symbolic run debug to {debug_file}")

    return results

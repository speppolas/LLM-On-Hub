import os
from typing import Dict, Any, List

from app.core.ontology_engine.ontology_loader import (
    load_patient_ontology,
    load_trial_rules
)
from app.core.ontology_engine.ontology_reasoner import derive_ontology_facts
from app.core.ontology_engine.rule_evaluator import evaluate_rule
from app.core.ontology_engine.trace_builder import build_trace


TRIAL_RULES_DIR = "app/core/ontology_engine/trial_rules"


def evaluate_patient_against_trials(patient: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Core neuro-symbolic pipeline.
    Input: patient facts extracted by LLM
    Output: eligibility + full XAI trace per trial
    """

    ontology = load_patient_ontology()
    derived_facts = derive_ontology_facts(patient, ontology)

    results = []

    for filename in os.listdir(TRIAL_RULES_DIR):
        if not filename.endswith(".yaml"):
            continue

        trial_rules = load_trial_rules(filename.replace(".yaml", ""))
        trial_id = trial_rules["trial_id"]

        inclusion_results = []
        exclusion_results = []

        # ---------- INCLUSION ----------
        for rule in trial_rules.get("inclusion", []):
            status = evaluate_rule(rule, patient, derived_facts)

            inclusion_results.append({
                "id": rule["id"],
                "field": rule.get("field"),
                "status": status,
                "patient_value": patient.get(rule.get("field")),
                "text": rule.get("text", "")
            })

        # ---------- EXCLUSION ----------
        for rule in trial_rules.get("exclusion", []):
            status = evaluate_rule(rule, patient, derived_facts)

            exclusion_results.append({
                "id": rule["id"],
                "field": rule.get("field"),
                "status": status,
                "patient_value": patient.get(rule.get("field")),
                "text": rule.get("text", "")
            })

        # ---------- DECISION LOGIC ----------
        overall = decide_overall(inclusion_results, exclusion_results)

        trace = build_trace(
            trial_id=trial_id,
            inclusion=inclusion_results,
            exclusion=exclusion_results,
            overall=overall
        )

        results.append({
            "trial_id": trial_id,
            "title": trial_rules.get("title"),
            "overall": overall,
            "trace": trace
        })

    return results


def decide_overall(inclusions, exclusions) -> str:
    """
    Deterministic decision logic.
    """

    for exc in exclusions:
        if exc["status"] == "met":
            return "not_eligible"

    for inc in inclusions:
        if inc["status"] == "not_met":
            return "not_eligible"

    if any(inc["status"] == "unknown" for inc in inclusions):
        return "unknown"

    return "eligible"

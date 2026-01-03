#pipeline.py
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
from app.core.ontology_engine.rule_evaluator import evaluate_rule
from app.core.ontology_engine.trace_builder import build_trace

logger = logging.getLogger(__name__)



def _dump_ns_debug(payload: dict, prefix: str = "ns_debug") -> str:
    os.makedirs("logs", exist_ok=True)
    filename = f"logs/{prefix}_{int(time.time())}.json"
    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)
    return filename



TRIAL_RULES_DIR = "app/core/ontology_engine/trial_rules"
os.makedirs("logs", exist_ok=True)
def decide_overall(inclusions, exclusions) -> str:
    """
    Deterministic eligibility decision logic.
    """
    if not inclusions and not exclusions:
        return "unknown" 
    # Any exclusion met → NOT eligible
    for exc in exclusions:
        if exc["status"] == "met":
            return "not_eligible"

    # Any inclusion not met → NOT eligible
    for inc in inclusions:
        if inc["status"] == "not_met":
            return "not_eligible"

    # Any unknown inclusion → UNKNOWN
    for inc in inclusions:
        if inc["status"] == "unknown":
            return "unknown"

    return "eligible"




# app/core/ontology_engine/pipeline.py
import os
from typing import Dict, Any, List
import json
import time

from app import logger

from app.core.ontology_engine.ontology_loader import load_patient_ontology, load_trial_rules
from app.core.ontology_engine.ontology_reasoner import derive_ontology_facts
from app.core.ontology_engine.rule_evaluator import evaluate_rule
from app.core.ontology_engine.trace_builder import build_trace
from app.core.ontology_engine.ground_patient_facts import ground_patient_facts
from app.core.ontology_engine.explainer import explain_decision_with_llm

TRIAL_RULES_DIR = "app/core/ontology_engine/trial_rules"

def decide_overall(inclusions, exclusions) -> str:
    for exc in exclusions:
        if exc["status"] == "met":
            return "not_eligible"
    for inc in inclusions:
        if inc["status"] == "not_met":
            return "not_eligible"
    if any(inc["status"] == "unknown" for inc in inclusions):
        return "unknown"
    return "eligible"

def _dump_ns_debug(payload: dict, prefix: str = "ns_debug") -> str:
    os.makedirs("logs", exist_ok=True)
    filename = f"logs/{prefix}_{int(time.time())}.json"
    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)
    return filename

def evaluate_patient_against_trials(patient: Dict[str, Any], with_explanations: bool = False) -> List[Dict[str, Any]]:
    ontology = load_patient_ontology()
    derived_facts = derive_ontology_facts(patient, ontology)

    grounded = ground_patient_facts(patient, ontology)  # facts + grounding_trace :contentReference[oaicite:1]{index=1}
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

    for filename in sorted(os.listdir(TRIAL_RULES_DIR)):
        if not filename.endswith(".yaml"):
            continue

        trial_key = filename.replace(".yaml", "")
        trial_rules = load_trial_rules(trial_key)
        if not isinstance(trial_rules, dict):
            logger.error(f"Invalid trial rules for {trial_key}: {trial_rules}")
            continue

        trial_id = trial_rules.get("trial_id", trial_key)
        title = trial_rules.get("title", "Unknown Trial")

        inclusion_results = []
        exclusion_results = []

        for rule in trial_rules.get("inclusion", []):
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

        for rule in trial_rules.get("exclusion", []):
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

        if with_explanations:
            # LLM spiega SOLO dal trace (non cambia decision) :contentReference[oaicite:2]{index=2}
            try:
                explanation = explain_decision_with_llm(
                    patient_facts=patient_facts,
                    ontology_trace=grounding_trace,
                    decision_trace=trace,
                    final_decision=overall
                )
                item["explanation"] = explanation
            except Exception as e:
                logger.warning(f"Explanation failed for {trial_id}: {e}")

        results.append(item)

        run_debug["trials"].append({
            "trial_id": trial_id,
            "title": title,
            "overall": overall,
            "inclusion_results": inclusion_results,
            "exclusion_results": exclusion_results,
        })

    debug_file = _dump_ns_debug(run_debug, prefix="ns_run")
    logger.info(f"💾 Saved neuro-symbolic debug output to {debug_file}")

    return results

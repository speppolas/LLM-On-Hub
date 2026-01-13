#pipeline.py# app/core/ontology_engine/pipeline.py
# app/core/ontology_engine/pipeline.py

import os
import json
import time
import logging
from typing import Dict, Any, List

from app.core.ontology_engine.timing import TimingContext
from app.core.ontology_engine.ontology_loader import (
    load_patient_ontology,
    load_trial_rules
)
from app.core.ontology_engine.ontology_reasoner import derive_ontology_facts
from app.core.ontology_engine.ground_patient_facts import ground_patient_facts
from app.core.ontology_engine.rule_evaluator import evaluate_rule
from app.core.ontology_engine.trace_builder import build_trace
from app.core.ontology_engine.explainer import explain_decision_with_llm
from app.core.ontology_engine.uncertainty import compute_confidence_and_triage


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

    # 1️⃣ Inclusion failure dominates everything
    for inc in inclusions:
        if inc["status"] == "not_met":
            return "not_eligible"

    # 2️⃣ Exclusion met
    for exc in exclusions:
        if exc["status"] == "met":
            return "not_eligible"

    # 3️⃣ Inclusion unknown
    for inc in inclusions:
        if inc["status"] == "unknown":
            return "unknown"

    # 4️⃣ Exclusion unknown
    for exc in exclusions:
        if exc["status"] == "unknown":
            return "unknown"

    return "eligible"


# -------------------------
# Main pipeline
# -------------------------
def evaluate_patient_against_trials(
    patient: Dict[str, Any],
    with_explanations: bool = False
) -> Dict[str, Any]:

    timer = TimingContext()

    # 1) Load ontology
    timer.start("load_ontology")
    ontology = load_patient_ontology()
    timer.stop("load_ontology")

    # 2) Ground patient facts (canonical closed-world concepts)
    timer.start("grounding")
    grounded = ground_patient_facts(patient, ontology)
    timer.stop("grounding")

    patient_facts: List[str] = grounded.get("facts", []) or []
    grounding_trace = grounded.get("grounding_trace", []) or []

    grounded_biomarkers = [
        t["concept"]
        for t in grounding_trace
        if t["field"] == "biomarkers"
    ]

    # Make patient_facts available as a field for YAML rules (field: patient_facts)
    patient_ctx = dict(patient)
    patient_ctx["patient_facts"] = patient_facts
        
    # 3) Ontology reasoning / derived facts (must happen AFTER grounding)
    timer.start("ontology_reasoning")
    # ✅ Paper-grade: derived facts computed from canonical concepts
    # If you update derive_ontology_facts signature to accept patient_facts,
    # call it like: derive_ontology_facts(patient_ctx, ontology, patient_facts)
    derived_facts = derive_ontology_facts(patient_ctx, ontology, patient_facts)
    derived_facts["grounded_biomarkers"] = grounded_biomarkers
    
    timer.stop("ontology_reasoning")

    for k, v in derived_facts.items():
        patient_ctx[k] = v
        
    results: List[Dict[str, Any]] = []

    run_debug = {
        "patient_input": patient,
        "patient_facts": patient_facts,
        "grounding_trace": grounding_trace,
        "derived_facts": derived_facts,
        "trials": []
    }

    # 4) Iterate trials
    timer.start("trial_loop")

    for filename in sorted(os.listdir(TRIAL_RULES_DIR)):
        if not filename.endswith(".yaml"):
            continue

        trial_key = filename.replace(".yaml", "")

        timer.start("load_trial_rules")
        trial_rules = load_trial_rules(trial_key)
        timer.stop("load_trial_rules")

        if not isinstance(trial_rules, dict):
            logger.error(f"Invalid trial rules for {trial_key}")
            continue

        trial_id = trial_rules.get("trial_id", trial_key)
        title = trial_rules.get("title", "Unknown Trial")

        inclusion_rules = trial_rules.get("inclusion", []) or []
        exclusion_rules = trial_rules.get("exclusion", []) or []

        inclusion_rules = [r for r in inclusion_rules if isinstance(r, dict)]
        exclusion_rules = [r for r in exclusion_rules if isinstance(r, dict)]

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

        # 5) Evaluate inclusion
        timer.start("rule_eval_inclusion")
        for rule in inclusion_rules:
            status = evaluate_rule(rule, patient_ctx, derived_facts)
            inclusion_results.append({
                "id": rule.get("id"),
                "field": rule.get("field"),
                "condition": rule.get("condition"),
                "value": rule.get("value"),
                "status": status,
                "patient_value": patient_ctx.get(rule.get("field")),
                "text": rule.get("text", "")
            })
        timer.stop("rule_eval_inclusion")

        # 6) Evaluate exclusion
        timer.start("rule_eval_exclusion")
        for rule in exclusion_rules:
            status = evaluate_rule(rule, patient_ctx, derived_facts)
            exclusion_results.append({
                "id": rule.get("id"),
                "field": rule.get("field"),
                "condition": rule.get("condition"),
                "value": rule.get("value"),
                "status": status,
                "patient_value": patient_ctx.get(rule.get("field")),
                "text": rule.get("text", "")
            })
        timer.stop("rule_eval_exclusion")

        # 7) Decide
        timer.start("decision_logic")
        overall = decide_overall(inclusion_results, exclusion_results)
        timer.stop("decision_logic")
        uncertainty = compute_confidence_and_triage(
            inclusion_results=inclusion_results,
            exclusion_results=exclusion_results,
            overall=overall
        )

        
        
        trace = build_trace(
            trial_id=trial_id,
            inclusion=inclusion_results,
            exclusion=exclusion_results,
            overall=overall
        )

        item: Dict[str, Any] = {
            "trial_id": trial_id,
            "title": title,
            "overall": overall,
            "uncertainty": uncertainty,
            "trace": trace
        }


        # 8) Optional: LLM explanation (post-decision)
        if with_explanations:
            try:
                timer.start("llm_explanation")
                explanation = explain_decision_with_llm(
                    patient_facts={"facts": patient_facts},
                    ontology_trace=grounding_trace,
                    decision_trace=trace,
                    final_decision=overall
                )
                timer.stop("llm_explanation")
                item["explanation"] = explanation
            except Exception as e:
                logger.warning(f"LLM explanation failed for {trial_id}: {e}")

        results.append(item)

        run_debug["trials"].append({
            "trial_id": trial_id,
            "title": title,
            "overall": overall,
            "uncertainty": uncertainty,        
            "inclusion_results": inclusion_results,
            "exclusion_results": exclusion_results
        })

    timer.stop("trial_loop")

    debug_file = _dump_ns_debug(run_debug)
    logger.info(f"💾 Saved neuro-symbolic run debug to {debug_file}")

    return {
        "results": results,
        "timings": timer.summary()
    }



'''
def evaluate_patient_against_trials(
    patient: Dict[str, Any],
    with_explanations: bool = False
) -> Dict[str, Any]:

    timer = TimingContext()

    # 1) Load ontology & derive facts
    timer.start("load_ontology")
    ontology = load_patient_ontology()
    timer.stop("load_ontology")

    timer.start("ontology_reasoning")
    derived_facts = derive_ontology_facts(patient, ontology)
    timer.stop("ontology_reasoning")

    # 2) Ground patient facts → ontology concepts
    timer.start("grounding")
    grounded = ground_patient_facts(patient, ontology)
    timer.stop("grounding")

    patient_facts = grounded.get("facts", {})
    grounding_trace = grounded.get("grounding_trace", {})

    results: List[Dict[str, Any]] = []

    run_debug = {
        "patient_input": patient,
        "derived_facts": derived_facts,
        "patient_facts": patient_facts,
        "grounding_trace": grounding_trace,
        "trials": []
    }

    # 3) Iterate trials
    timer.start("trial_loop")

    for filename in sorted(os.listdir(TRIAL_RULES_DIR)):
        if not filename.endswith(".yaml"):
            continue

        trial_key = filename.replace(".yaml", "")

        timer.start("load_trial_rules")
        trial_rules = load_trial_rules(trial_key)
        timer.stop("load_trial_rules")

        if not isinstance(trial_rules, dict):
            logger.error(f"Invalid trial rules for {trial_key}")
            continue

        trial_id = trial_rules.get("trial_id", trial_key)
        title = trial_rules.get("title", "Unknown Trial")

        inclusion_rules = trial_rules.get("inclusion", []) or []
        exclusion_rules = trial_rules.get("exclusion", []) or []

        # ✅ define results lists (you had commented them out)
        inclusion_results: List[dict] = []
        exclusion_results: List[dict] = []

        # ✅ sanitize: skip malformed YAML rules (strings, ints, etc.)
        inclusion_rules = [r for r in inclusion_rules if isinstance(r, dict)]
        exclusion_rules = [r for r in exclusion_rules if isinstance(r, dict)]

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

        # 4) Evaluate inclusion
        timer.start("rule_eval_inclusion")
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
        timer.stop("rule_eval_inclusion")

        # 5) Evaluate exclusion
        timer.start("rule_eval_exclusion")
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
        timer.stop("rule_eval_exclusion")

        # 6) Decide
        timer.start("decision_logic")
        overall = decide_overall(inclusion_results, exclusion_results)
        timer.stop("decision_logic")

        trace = build_trace(
            trial_id=trial_id,
            inclusion=inclusion_results,
            exclusion=exclusion_results,
            overall=overall
        )

        item: Dict[str, Any] = {
            "trial_id": trial_id,
            "title": title,
            "overall": overall,
            "trace": trace
        }

        # 7) Optional: LLM explanation (post-decision)
        if with_explanations:
            try:
                timer.start("llm_explanation")
                explanation = explain_decision_with_llm(
                    patient_facts=patient_facts,
                    ontology_trace=grounding_trace,
                    decision_trace=trace,
                    final_decision=overall
                )
                timer.stop("llm_explanation")
                item["explanation"] = explanation
            except Exception as e:
                logger.warning(f"LLM explanation failed for {trial_id}: {e}")
                # non bloccare il run se explanation fallisce

        results.append(item)

        run_debug["trials"].append({
            "trial_id": trial_id,
            "title": title,
            "overall": overall,
            "inclusion_results": inclusion_results,
            "exclusion_results": exclusion_results
        })

    timer.stop("trial_loop")

    debug_file = _dump_ns_debug(run_debug)
    logger.info(f"💾 Saved neuro-symbolic run debug to {debug_file}")

    return {
        "results": results,
        "timings": timer.summary()
    }
'''
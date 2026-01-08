# app/core/ontology_engine/rule_evaluator.py

from typing import Any, Dict

def _normalize_list(v: Any):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def evaluate_rule(rule: Dict[str, Any], patient: Dict[str, Any], derived_facts: Dict[str, Any]) -> str:
    field = rule.get("field")
    condition = rule.get("condition")
    target = rule.get("value")

    patient_value = patient.get(field)

    # ---------------- Missing handling ----------------
    is_missing = (
        patient_value is None
        or patient_value == "not mentioned"
        or patient_value == ["not mentioned"]
        or patient_value == []
    )

    # ⭐ SPECIAL RULE: previous treatments are CLOSED-WORLD
    if is_missing and field == "prior_systemic_therapies":
        return "not_met"
    if is_missing and field == "comorbidities":
        return "not_met"
    # All other fields → unknown if missing
    if is_missing:
        return "unknown"

    # ---------------- Conditions ----------------
    if condition == "gte":
        try:
            return "met" if float(patient_value) >= float(target) else "not_met"
        except Exception:
            return "unknown"

    if condition == "lte":
        try:
            return "met" if float(patient_value) <= float(target) else "not_met"
        except Exception:
            return "unknown"

    if condition == "equals":
        return "met" if patient_value == target else "not_met"

    if condition == "not_equals":
        return "met" if patient_value != target else "not_met"

    if condition == "contains":
        values = _normalize_list(patient_value)
        return "met" if target in values else "not_met"

    if condition == "contains_any":
        values = _normalize_list(patient_value)
        return "met" if any(x in values for x in target) else "not_met"

    if condition == "contains_other_than":
        values = _normalize_list(patient_value)
        others = [x for x in values if x != "not mentioned" and x != target]
        return "met" if len(others) > 0 else "not_met"

    if condition == "ontology_is_a":
        if field == "current_stage":
            key = "stage_is_a"
        elif field == "histology":
            key = "histology_is_a"
        elif field == "ecog_ps":
            key = "ecog_is_a"
        elif field in ("brain_metastasis_status", "brain_metastasis"):
            key = "brain_cns_is_a"
        else:
            key = f"{field}_is_a"

        val = derived_facts.get(key)
        if val is None:
            return "unknown"
        return "met" if val == target else "not_met"

    return "unknown"

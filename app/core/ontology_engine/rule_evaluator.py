# app/core/ontology_engine/rule_evaluator.py

from typing import Any, Dict

def _normalize_list(v: Any):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]

def evaluate_rule(rule: Dict[str, Any], patient: Dict[str, Any], derived_facts: Dict[str, Any]) -> str:
    """
    Returns: "met" | "not_met" | "unknown"
    Deterministic. No LLM.
    """
    field = rule.get("field")
    condition = rule.get("condition")
    target = rule.get("value")

    patient_value = patient.get(field)

    # Missing handling
    if patient_value is None or patient_value == "not mentioned" or patient_value == ["not mentioned"]:
        return "unknown"

    # Conditions
    if condition == "gte":
        try:
            return "met" if float(patient_value) >= float(target) else "not_met"
        except Exception:
            return "unknown"

    if condition == "contains":
        values = _normalize_list(patient_value)
        return "met" if target in values else "not_met"

    if condition == "contains_other_than":
        # e.g. biomarkers contains a driver other than ROS1
        values = _normalize_list(patient_value)
        # if any biomarker not mentioned and != target => met exclusion
        others = [x for x in values if x != "not mentioned" and x != target]
        return "met" if len(others) > 0 else "not_met"

    if condition == "ontology_is_a":
        # compare derived "xxx_is_a" concept to target
        # convention: derived_facts has histology_is_a, stage_is_a, ecog_is_a, brain_cns_is_a
        key = f"{field}_is_a" if not field.endswith("_is_a") else field
        # special-case if rule uses field=histology/current_stage/ecog_ps/brain_metastasis_status
        if field == "current_stage":
            key = "stage_is_a"
        elif field == "histology":
            key = "histology_is_a"
        elif field == "ecog_ps":
            key = "ecog_is_a"
        elif field in ("brain_metastasis_status", "brain_metastasis"):
            key = "brain_cns_is_a"

        val = derived_facts.get(key)
        if val is None:
            return "unknown"
        return "met" if val == target else "not_met"

    # Unknown condition
    return "unknown"

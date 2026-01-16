# app/core/ontology_engine/rule_evaluator.py

from typing import Any, Dict

def _normalize_list(v: Any):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]

def _norm(v: Any):
    if isinstance(v, str):
        return v.strip().lower()
    return v

def evaluate_rule(rule: Dict[str, Any], patient: Dict[str, Any], derived_facts: Dict[str, Any]) -> str:
    """
    Returns: "met" | "not_met" | "unknown"
    Deterministic. No LLM.
    """

    # ==========================
    # OR LOGIC (NEW, OPTIONAL)
    # ==========================
    if "or" in rule:
        subrules = rule.get("or")
        if not isinstance(subrules, list) or len(subrules) == 0:
            # YAML malformato -> meglio unknown che crash
            return "unknown"

        for subrule in subrules:
            if not isinstance(subrule, dict):
                return "unknown"
            if "or" in subrule:
                raise ValueError("Nested OR not supported")

            # validazione minima: subrule deve avere field/condition/value
            if "field" not in subrule or "condition" not in subrule or "value" not in subrule:
                return "unknown"

        results = [evaluate_rule(sr, patient, derived_facts) for sr in subrules]

        if "met" in results:
            return "met"
        if all(r == "not_met" for r in results):
            return "not_met"
        return "unknown"


    # ==========================
    # AND LOGIC (NEW)
    # ==========================
    if "and" in rule:
        subrules = rule.get("and")
        if not isinstance(subrules, list) or len(subrules) == 0:
            return "unknown"

        for subrule in subrules:
            if not isinstance(subrule, dict):
                return "unknown"
            if "or" in subrule or "and" in subrule:
                raise ValueError("Nested AND/OR not supported")

            if "field" not in subrule or "condition" not in subrule or "value" not in subrule:
                return "unknown"

        results = [evaluate_rule(sr, patient, derived_facts) for sr in subrules]

        if all(r == "met" for r in results):
            return "met"
        if any(r == "not_met" for r in results):
            return "not_met"
        return "unknown"


    # ==========================
    # STANDARD RULES
    # ==========================
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

    # CLOSED-WORLD: prior therapies + comorbidities (come hai impostato tu)
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
        # Special-case: biomarkers are evaluated on grounded concepts when target is a DRIVER_*
        if field == "biomarkers" and isinstance(target, str) and target.startswith("DRIVER_"):
            concepts = derived_facts.get("grounded_biomarkers", [])
            return "met" if target in concepts else "not_met"

        values = [_norm(v) for v in _normalize_list(patient_value)]
        return "met" if _norm(target) in values else "not_met"


    if condition == "contains_any":
        # Special-case: biomarkers on grounded concepts when targets are DRIVER_*
        if field == "biomarkers":
            concepts = derived_facts.get("grounded_biomarkers", [])
            targets = _normalize_list(target)
            # se almeno uno dei target è DRIVER_*, trattiamo come concept matching
            if any(isinstance(t, str) and t.startswith("DRIVER_") for t in targets):
                return "met" if any(t in concepts for t in targets) else "not_met"

        values = [_norm(v) for v in _normalize_list(patient_value)]
        targets = [_norm(t) for t in _normalize_list(target)]
        return "met" if any(t in values for t in targets) else "not_met"

    if condition == "contains_other_than":
        values = _normalize_list(patient_value)

        if field == "biomarkers":
            drivers = derived_facts.get("targetable_drivers", [])
            others = [d for d in drivers if d != target]
            return "met" if len(others) > 0 else "not_met"

        others = [x for x in values if x != "not mentioned" and x != target]
        return "met" if len(others) > 0 else "not_met"

    if condition == "ontology_is_a":
        if field == "current_stage":
            key = "stage_is_a"
        elif field == "histology":
            key = "histology_is_a"
        elif field == "ecog_ps":
            key = "ecog_is_a"
        elif field == "pd_l1_tps":
            key = "pd_l1_is_a"

        elif field in ("brain_metastasis_status", "brain_metastasis"):
            key = "brain_cns_is_a"
        else:
            key = f"{field}_is_a"

        val = derived_facts.get(key)
        if val is None:
            return "unknown"
        return "met" if val == target else "not_met"

    return "unknown"


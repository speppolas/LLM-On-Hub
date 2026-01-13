#ground_patient_facts.py
def _normalize_value(field: str, v: str):
    # ECOG must match YAML int keys
    if field == "ecog_ps":
        try:
            return int(v)
        except Exception:
            return v

    if field == "biomarkers":
        return (
            v.lower()
             .replace(" ", "_")
             .replace("-", "_")
             .upper()
        )

    return v


def ground_patient_facts(patient_json: dict, ontology: dict) -> dict:
    facts = []
    trace = []

    for field, value in patient_json.items():

        if value in (None, "not mentioned", ["not mentioned"]):
            continue

        if field not in ontology:
            continue

        mapping = ontology[field]
        values = value if isinstance(value, list) else [value]

        for v in values:
            if not isinstance(v, str):
                continue
            if v == "not mentioned":
                continue

            key = _normalize_value(field, v)

            if key in mapping:
                concept = mapping[key]["concept"]
                facts.append(concept)
                trace.append({
                    "field": field,
                    "value": v,
                    "normalized": key,
                    "concept": concept
                })

    return {
        "facts": sorted(set(facts)),
        "grounding_trace": trace
    }

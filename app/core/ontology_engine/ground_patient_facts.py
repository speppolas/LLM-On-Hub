#ground_patient_facts.py
def ground_patient_facts(patient_json: dict, ontology: dict) -> dict:
    facts = []
    trace = []

    for field, value in patient_json.items():
        if value == "not mentioned":
            continue

        if field in ontology:
            mapping = ontology[field]

            # gestione liste
            values = value if isinstance(value, list) else [value]

            for v in values:
                if v in mapping:
                    concept = mapping[v]["concept"]
                    facts.append(concept)
                    trace.append({
                        "field": field,
                        "value": v,
                        "concept": concept
                    })

    return {
        "facts": list(set(facts)),
        "grounding_trace": trace
    }

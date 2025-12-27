def evaluate_rule(rule, patient, derived):
    field = rule["field"]
    condition = rule["condition"]
    value = rule["value"]

    patient_value = patient.get(field)

    if patient_value == "not mentioned":
        return "unknown"

    if condition == "gte":
        return "met" if patient_value >= value else "not_met"

    if condition == "contains":
        return "met" if value in patient_value else "not_met"

    if condition == "ontology_is_a":
        return "met" if derived.get(f"{field}_is_a") == value else "not_met"

    return "unknown"

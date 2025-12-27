def derive_ontology_facts(patient: dict, ontology: dict) -> dict:
    derived = {}

    # Histology
    hist = patient.get("histology")
    if hist in ontology["histology"]:
        derived["histology_is_a"] = ontology["histology"][hist]["is_a"]

    # Stage
    stage = patient.get("current_stage")
    if stage in ontology["stage"]:
        derived["stage_is_a"] = ontology["stage"][stage]["is_a"]

    # ECOG
    ecog = patient.get("ecog_ps")
    if ecog in ontology["ecog_ps"]:
        derived["ecog_is_a"] = ontology["ecog_ps"][ecog]["is_a"]

    return derived

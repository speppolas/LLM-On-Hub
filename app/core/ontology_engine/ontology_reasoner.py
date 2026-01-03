#ontology_reasoner.py
import logging

logger = logging.getLogger("ontology_reasoner")

# app/core/ontology_engine/ontology_reasoner.py

from typing import Dict, Any

def derive_ontology_facts(patient: Dict[str, Any], ontology: Dict[str, Any]) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}

    # Histology -> concept (e.g., NSCLC / SCLC)
    hist = patient.get("histology")
    if hist in ontology.get("histology", {}):
        derived["histology_is_a"] = ontology["histology"][hist]["concept"]

    # Stage -> concept (e.g., Stage_IV)
    stage = patient.get("current_stage")
    if stage in ontology.get("current_stage", {}):
        derived["stage_is_a"] = ontology["current_stage"][stage]["concept"]

    # ECOG -> concept (e.g., ECOG_0)
    ecog = patient.get("ecog_ps")
    if ecog in ontology.get("ecog_ps", {}):
        derived["ecog_is_a"] = ontology["ecog_ps"][ecog]["concept"]

    # Brain metastasis status -> concept (e.g., Active_CNS_disease)
    status = patient.get("brain_metastasis_status")
    if status and status != "not mentioned":
        mapping = ontology.get("brain_metastasis_status", {})
        if status in mapping:
            derived["brain_cns_is_a"] = mapping[status]["concept"]
    else:
        # Backward compatibility
        bm = patient.get("brain_metastasis")
        if bm == ["true"] or bm == "true":
            derived["brain_cns_is_a"] = "Active_CNS_disease"

    return derived

#ontology_reasoner.py

from typing import Dict, Any, List

TARGETABLE_APPROVED_DRIVERS = {
    "DRIVER_EGFR_SENSITIZING",
    "DRIVER_ALK",
    "DRIVER_KRAS_G12C",
    "DRIVER_MET",
    "DRIVER_HER2_ACTIVATING"
}

def derive_ontology_facts(
    patient: Dict[str, Any],
    ontology: Dict[str, Any],
    patient_facts: List[str]
) -> Dict[str, Any]:
    """
    Derive higher-order ontology facts from grounded patient facts.
    NO raw biomarker access. Closed-world.
    """

    derived: Dict[str, Any] = {}

    # -------------------------
    # Scalar abstractions
    # -------------------------
    hist = patient.get("histology")
    if hist in ontology.get("histology", {}):
        derived["histology_is_a"] = ontology["histology"][hist]["concept"]

    stage = patient.get("current_stage")
    if stage in ontology.get("current_stage", {}):
        derived["stage_is_a"] = ontology["current_stage"][stage]["concept"]

    ecog = patient.get("ecog_ps")
    try:
        ecog_norm = int(ecog)
    except Exception:
        ecog_norm = ecog

    if ecog_norm in ontology.get("ecog_ps", {}):
        derived["ecog_is_a"] = ontology["ecog_ps"][ecog_norm]["concept"]

    pdl1 = patient.get("pd_l1_tps")
    if isinstance(pdl1, str):
        mapping = ontology.get("pd_l1_tps", {})
        if pdl1 in mapping:
            derived["pd_l1_is_a"] = mapping[pdl1]["concept"]

    # -------------------------
    # Driver-level reasoning (SET-BASED)
    # -------------------------
    targetable_drivers = [
        f for f in patient_facts
        if f in TARGETABLE_APPROVED_DRIVERS
    ]

    if targetable_drivers:
        derived["targetable_drivers"] = sorted(set(targetable_drivers))

    # -------------------------
    # CNS abstraction
    # -------------------------
    status = patient.get("brain_metastasis_status")
    if status and status != "not mentioned":
        mapping = ontology.get("brain_metastasis_status", {})
        if status in mapping:
            derived["brain_cns_is_a"] = mapping[status]["concept"]
    else:
        bm = patient.get("brain_metastasis")
        if bm == ["true"] or bm == "true":
            derived["brain_cns_is_a"] = "Active_CNS_disease"

    return derived





'''
TARGETABLE_APPROVED_DRIVERS = {
    "DRIVER_EGFR_SENSITIZING",
    "DRIVER_ALK",
    "DRIVER_KRAS_G12C",
    "DRIVER_MET",
    "DRIVER_HER2_ACTIVATING"
}

def derive_ontology_facts(
    patient: Dict[str, Any],
    ontology: Dict[str, Any],
    patient_facts: list
) -> Dict[str, Any]:
    
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

        # PD-L1 TPS -> concept bucket (e.g., PDL1_negative/low/high)
    pdl1 = patient.get("pd_l1_tps")
    if isinstance(pdl1, str):
        mapping = ontology.get("pd_l1_tps", {})
        if pdl1 in mapping:
            derived["pd_l1_is_a"] = mapping[pdl1]["concept"]


    # Biomarkers / oncogenic drivers
    targetable = [
        f for f in patient_facts
        if f in TARGETABLE_APPROVED_DRIVERS
    ]

    if targetable:
        derived["targetable_drivers"] = targetable


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
    '''
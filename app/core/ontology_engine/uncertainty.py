# app/core/ontology_engine/uncertainty.py

def compute_confidence_and_triage(
    inclusion_results,
    exclusion_results,
    overall
):
    """
    Neuro-symbolic uncertainty & confidence computation.
    Deterministic, auditabile, paper-grade.
    """

    # -------------------------
    # Evidence Completeness (ECS)
    # -------------------------
    U_inc = sum(r["status"] == "unknown" for r in inclusion_results)
    U_exc = sum(r["status"] == "unknown" for r in exclusion_results)

    # -------------------------
    # Logical structure
    # -------------------------
    hard_fails = (
        sum(r["status"] == "not_met" for r in inclusion_results) +
        sum(r["status"] == "met" for r in exclusion_results)
    )

    support = (
        sum(r["status"] == "met" for r in inclusion_results) +
        sum(r["status"] == "not_met" for r in exclusion_results)
    )

    # -------------------------
    # Conflict Penalty (CP)
    # -------------------------
    conflict = int(hard_fails > 0 and (U_inc + U_exc) > 0)

    # -------------------------
    # Base Uncertainty
    # -------------------------
    uncertainty = (
        2 * U_inc +        # missing inclusion evidence
        1 * U_exc +        # missing exclusion evidence
        3 * conflict       # logical inconsistency
    )

    # -------------------------
    # Logical Margin Score (LMS)
    # -------------------------
    if overall == "eligible":
        # robust eligibility → lower uncertainty
        uncertainty -= min(2, support // 3)

    elif overall == "not_eligible":
        # strong exclusion → lower uncertainty
        uncertainty -= min(2, hard_fails // 2)

    uncertainty = max(0, uncertainty)

    # -------------------------
    # Confidence
    # -------------------------
    confidence = 1.0 / (1.0 + uncertainty)

    # -------------------------
    # Threshold-based triage
    # (non-quantile → no paper copying)
    # -------------------------
    if confidence >= 0.55:
        triage = "auto"
    elif confidence >= 0.35:
        triage = "review"
    else:
        triage = "human_required"

    return {
        "uncertainty_score": int(uncertainty),
        "confidence": round(confidence, 3),
        "triage": triage,
        "components": {
            "unknown_inclusion": int(U_inc),
            "unknown_exclusion": int(U_exc),
            "hard_fails": int(hard_fails),
            "support": int(support),
            "conflict": int(conflict)
        }
    }

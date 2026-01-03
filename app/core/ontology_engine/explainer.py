#explainer.py
import json
from app.core.llm_processor import get_llm_processor

def explain_decision_with_llm(
    patient_facts: dict,
    ontology_trace: dict,
    decision_trace: dict,
    final_decision: str
) -> str:
    """
    LLM-based explanation layer.
    MUST NOT change decision.
    MUST NOT add new facts.
    """

    llm = get_llm_processor()

    prompt = f"""
You are a clinical assistant.

Your task is to explain a trial eligibility decision.
You MUST strictly adhere to the provided reasoning trace.

DO NOT add new facts.
DO NOT infer missing information.
DO NOT change the decision.

---

FINAL DECISION:
{final_decision}

---

PATIENT ONTOLOGICAL FACTS:
{json.dumps(patient_facts, indent=2)}

---

ONTOLOGY GROUNDING TRACE:
{json.dumps(ontology_trace, indent=2)}

---

DECISION TRACE:
{json.dumps(decision_trace, indent=2)}

---

Explain clearly, in plain clinical English, why this decision was reached.
"""

    response = llm.generate_response(prompt)

    return response

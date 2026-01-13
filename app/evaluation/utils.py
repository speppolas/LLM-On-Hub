import csv
from collections import defaultdict


def load_csv(path: str) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group_by_patient(preds):
    patients = defaultdict(list)
    for p in preds:
        patients[p["patient_id"]].append({
            "trial_id": p["trial_id"],
            "prediction": p["prediction"],
            "confidence": float(p["confidence"]),
            "triage": p["triage"]
        })
    return patients

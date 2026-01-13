# app/evaluation/metrics.py

from typing import List, Dict


def classification_counts(pairs: List[tuple]) -> Dict[str, int]:
    TP = FP = TN = FN = 0
    for gt, pred in pairs:
        if gt == "eligible" and pred == "eligible":
            TP += 1
        elif gt == "not_eligible" and pred == "eligible":
            FP += 1
        elif gt == "not_eligible" and pred == "not_eligible":
            TN += 1
        elif gt == "eligible" and pred == "not_eligible":
            FN += 1
    return {"TP": TP, "FP": FP, "TN": TN, "FN": FN}


def compute_primary_metrics(counts: Dict[str, int]) -> Dict[str, float]:
    TP, FP, TN, FN = counts["TP"], counts["FP"], counts["TN"], counts["FN"]

    sensitivity = TP / (TP + FN) if TP + FN else 0.0
    specificity = TN / (TN + FP) if TN + FP else 0.0
    precision = TP / (TP + FP) if TP + FP else 0.0
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if precision + sensitivity else 0.0

    return {
        "TP": TP,
        "FP": FP,
        "TN": TN,
        "FN": FN,
        "sensitivity": round(sensitivity, 3),
        "specificity": round(specificity, 3),
        "precision": round(precision, 3),
        "f1": round(f1, 3),
    }

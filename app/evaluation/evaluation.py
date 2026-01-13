# app/evaluation/evaluation.pyimport os
from statistics import mean
import os
from app.evaluation.utils import load_csv, group_by_patient
from app.evaluation.ranking_metrics import rank_trials, top_k_hit, confidence_separation
from app.evaluation.triage_metrics import triage_distribution, false_positive_rate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRED_PATH = os.path.join(BASE_DIR, "predictions.csv")
GT_PATH = os.path.join(BASE_DIR, "ground_truth.csv")


def main():
    preds = load_csv(PRED_PATH)
    gt = load_csv(GT_PATH)

    gt_map = {}
    gt_unknown = set()
    for r in gt:
        if r["ground_truth"] == "eligible":
            gt_map[r["patient_id"]] = r["trial_id"]
        elif r["ground_truth"] == "unknown":
            gt_unknown.add((r["patient_id"], r["trial_id"]))
    patients = group_by_patient(preds)

    matchable = []
    non_matchable = []

    for pid, trials in patients.items():
        if pid in gt_map:
            matchable.append((pid, trials, gt_map[pid]))
        else:
            non_matchable.append((pid, trials))

    # =====================
    # MATCHABLE PATIENTS
    # =====================
    top1, top3, sep, triage_gt = [], [], [], []

    for pid, trials, gt_trial in matchable:
        ranked = rank_trials(trials)
        top1.append(top_k_hit(ranked, gt_trial, k=1))
        top3.append(top_k_hit(ranked, gt_trial, k=3))
        sep_val = confidence_separation(ranked, gt_trial)
        if sep_val is not None:
            sep.append(sep_val)
        triage_gt.append(next(t["triage"] for t in ranked if t["trial_id"] == gt_trial))

    print("\nMATCHABLE PATIENTS")
    print(f"N = {len(matchable)}")
    print(f"Top-1 accuracy: {round(mean(top1), 3)}")
    print(f"Recall@3: {round(mean(top3), 3)}")
    if sep:
        print(f"Mean confidence separation: {round(mean(sep), 3)}")
    else:
        print("Mean confidence separation: N/A")

    from collections import Counter
    print(f"Triage GT distribution: {dict(Counter(triage_gt))}")


    # =====================
    # NON-MATCHABLE PATIENTS
    # =====================
    print("\nNON-MATCHABLE PATIENTS")
    print(f"N = {len(non_matchable)}")

    fp_rates = []
    triage_all = []

    for _, trials in non_matchable:
        fp_rates.append(false_positive_rate(trials))
        triage_all.extend(trials)

    print(f"Mean false-positive rate: {round(mean(fp_rates), 3)}")
    print(f"Triage distribution: {dict(triage_distribution(triage_all))}")

    # =====================
    # INDETERMINATE CASES
    # =====================
    unknown_cases = []

    for pid, trials in patients.items():
        for t in trials:
            if (pid, t["trial_id"]) in gt_unknown:
                unknown_cases.append(t)

    if unknown_cases:
        print("\nINDETERMINATE CASES (GT = UNKNOWN)")
        safe = sum(
            1 for t in unknown_cases
            if t["triage"] in ("review", "human_required")
        )
        unsafe = sum(1 for t in unknown_cases if t["prediction"] == "eligible")

        print(f"Total unknown GT cases: {len(unknown_cases)}")
        print(f"Appropriate deferral rate: {round(safe / len(unknown_cases), 3)}")
        print(f"Unsafe automation rate: {round(unsafe / len(unknown_cases), 3)}")


if __name__ == "__main__":
    main()

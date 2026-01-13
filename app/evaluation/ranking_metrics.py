def rank_trials(trials):
    priority = {"eligible": 2, "unknown": 1, "not_eligible": 0}
    return sorted(
        trials,
        key=lambda t: (priority[t["prediction"]], t["confidence"]),
        reverse=True
    )


def top_k_hit(ranked_trials, gt_trial_id, k=1):
    top_k = ranked_trials[:k]
    return any(t["trial_id"] == gt_trial_id for t in top_k)


def confidence_separation(ranked_trials, gt_trial_id):
    gt = next(t for t in ranked_trials if t["trial_id"] == gt_trial_id)
    others = [t for t in ranked_trials if t["trial_id"] != gt_trial_id]
    if not others:
        return None
    return gt["confidence"] - max(t["confidence"] for t in others)

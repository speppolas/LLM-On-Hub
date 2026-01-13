from collections import Counter


def triage_distribution(trials):
    return Counter(t["triage"] for t in trials)


def false_positive_rate(trials):
    total = len(trials)
    fp = sum(1 for t in trials if t["prediction"] == "eligible")
    return fp / total if total else 0.0

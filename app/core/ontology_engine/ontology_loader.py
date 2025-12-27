import yaml
from pathlib import Path

def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_patient_ontology():
    return load_yaml("app/core/ontology_engine/patient_ontology.yaml")

def load_trial_rules(trial_id: str):
    return load_yaml(f"app/core/ontology_engine/trial_rules/{trial_id}.yaml")

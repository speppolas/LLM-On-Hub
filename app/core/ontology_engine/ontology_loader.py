#ontology_loader.py
import yaml
import os

def load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"YAML not found: {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"YAML is empty or invalid: {path}")

    if not isinstance(data, dict):
        raise ValueError(f"YAML root is not a dict: {path}")

    return data

def load_patient_ontology():
    return load_yaml("app/core/ontology_engine/patient_ontology.yaml")

def load_trial_rules(trial_id: str):
    return load_yaml(f"app/core/ontology_engine/trial_rules/{trial_id}.yaml")

import os
import time
import re
import json
import logging
import pdfplumber
import fitz  # PyMuPDF for PDF annotation
from typing import Dict, Any, Union, List, Optional, Tuple
from datetime import datetime, timedelta
from flask import current_app
from app.core.llm_processor import get_llm_processor, get_explainer_llm 
from app.utils import get_all_trials
from app import logger

# Ensure the logs folder exists
os.makedirs("logs", exist_ok=True)

# Clinical validation constants for safety
VALID_STAGES = {"I", "II", "III", "IV", "unknown", "not mentioned"}
VALID_ECOG = {0, 1, 2, 3, 4, None}
VALID_PD_L1 = {"<1%", "1-49%", ">=50%", "not mentioned"}
VALID_MUTATIONS = {"EGFR", "KRAS", "MET", "ALK", "ROS1", "BRAF", "HER2", "NTRK", "RET", "not mentioned"}
VALID_METASTASES = {"cns", "brain", "leptomeningeal", "bone", "liver", "lymph nodes", "adrenal", "pleural", "pericardial", "contralateral lung", "other", "not mentioned"}

def extract_text_with_coordinates(pdf_path: str) -> Tuple[str, List[Dict]]:
    """Extract text from PDF with page and coordinate information."""
    text = ""
    text_instances = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                    
                    # Extract words with their bounding boxes
                    words = page.extract_words()
                    for word in words:
                        text_instances.append({
                            'text': word['text'],
                            'page': page_num,
                            'x0': word['x0'],
                            'y0': word['top'],
                            'x1': word['x1'],
                            'y1': word['bottom']
                        })
    except Exception as e:
        logger.error(f"Error extracting text with coordinates: {str(e)}")
        raise
    
    return text.strip(), text_instances

def create_annotated_pdf(pdf_path: str, features_with_sources: Dict[str, Any], output_path: str = None) -> str:
    """Create a PDF with highlighted source text for extracted features."""
    
    # Color scheme for different feature types
    highlight_colors = {
        'age': (1.0, 0.92, 0.23, 0.3),  # Yellow
        'gender': (0.91, 0.12, 0.39, 0.3),  # Pink
        'diagnosis': (0.13, 0.59, 0.95, 0.3),  # Blue
        'stage': (0.30, 0.69, 0.31, 0.3),  # Green
        'ecog': (1.0, 0.60, 0.0, 0.3),  # Orange
        'mutations': (0.61, 0.15, 0.69, 0.3),  # Purple
        'metastases': (0.96, 0.26, 0.21, 0.3),  # Red
        'pd_l1': (0.0, 0.74, 0.83, 0.3),  # Cyan
        'comorbidities': (0.47, 0.33, 0.28, 0.3),  # Brown
        'treatments': (0.38, 0.49, 0.55, 0.3)  # Blue-gray
    }
    
    def get_feature_type(key: str) -> str:
        """Map feature keys to color categories."""
        key_lower = key.lower()
        if 'age' in key_lower:
            return 'age'
        elif 'gender' in key_lower:
            return 'gender'
        elif 'diagnosis' in key_lower:
            return 'diagnosis'
        elif 'stage' in key_lower:
            return 'stage'
        elif 'ecog' in key_lower:
            return 'ecog'
        elif 'mutation' in key_lower:
            return 'mutations'
        elif 'metastas' in key_lower:
            return 'metastases'
        elif 'pd_l1' in key_lower or 'PD_L1' in key:
            return 'pd_l1'
        elif 'comorbid' in key_lower:
            return 'comorbidities'
        elif 'treatment' in key_lower:
            return 'treatments'
        else:
            return 'age'
    
    try:
        pdf_document = fitz.open(pdf_path)

        # ðŸ” Itera su tutte le chiavi *_source_text e gestisci sia stringhe che liste
        for key, value in features_with_sources.items():
            if not key.endswith('_source_text') or value in (None, "", []):
                continue

            feature_type = get_feature_type(key)
            color = highlight_colors.get(feature_type, (1.0, 0.92, 0.23, 0.3))
            feature_name = key.replace('_source_text', '').replace('_', ' ').title()

            evidences: List[str] = []
            if isinstance(value, str):
                if value.strip():
                    evidences.append(value.strip())
            elif isinstance(value, list):
                evidences.extend([str(v).strip() for v in value if isinstance(v, (str, int, float)) and str(v).strip()])

            for ev in evidences:
                # cerca e annota in tutte le pagine
                for page_num in range(len(pdf_document)):
                    page = pdf_document[page_num]
                    rects = page.search_for(ev)
                    for r in rects:
                        annot = page.add_highlight_annot(r)
                        annot.set_colors(stroke=color[:3])
                        annot.set_opacity(color[3])
                        annot.set_info(content=f"Evidence for: {feature_name}")
                        annot.update()

        if output_path is None:
            timestamp = str(int(time.time()))
            output_path = os.path.join('uploads', f'annotated_{timestamp}.pdf')

        pdf_document.save(output_path)
        pdf_document.close()
        logger.info(f"Created annotated PDF: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error creating annotated PDF: {str(e)}")
        return pdf_path

def extract_text_from_pdf(pdf_file: Union[str, bytes]) -> str:
    """Extract text from PDF with enhanced error handling."""
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise Exception(f"Unable to extract text from PDF: {str(e)}")

def calculate_confidence_score(source_text: str, feature_type: str) -> int:
    """Calculate confidence score based on textual evidence strength."""
    if not source_text or source_text.strip() == "":
        return 0
    
    # Base confidence factors
    confidence = 50
    
    # Length and specificity
    if len(source_text.strip()) > 20:
        confidence += 10
    if len(source_text.strip()) > 50:
        confidence += 10
    
    # Medical terminology specificity
    medical_terms = {
        'age': ['years', 'age', 'anni', 'etÃ '],
        'diagnosis': ['adenocarcinoma', 'SCLC', 'squamous', 'NSCLC', 'carcinoma'],
        'stage': ['stage', 'stadio', 'T', 'N', 'M'],
        'ecog': ['ECOG', 'performance status', 'PS'],
        'mutations': ['EGFR', 'KRAS', 'MET', 'mutation', 'mutazione'],
        'pd_l1': ['PD-L1', 'PDL1', '%'],
        'metastases': ['metastasi', 'metastases', 'brain', 'liver', 'bone']
    }
    
    terms = medical_terms.get(feature_type, [])
    for term in terms:
        if term.lower() in source_text.lower():
            confidence += 15
            break
    
    # Numerical values add confidence
    if re.search(r'\d+', source_text):
        confidence += 10
    
    return min(confidence, 100)

def validate_extracted_feature(feature_name: str, feature_value: Any, source_text: str) -> Dict[str, Any]:
    """Validate extracted features against clinical guidelines and detect hallucinations."""
    result = {
        "value": feature_value,
        "confidence": 0,
        "uncertainty_flag": False,
        "validation_status": "valid",
        "clinical_notes": []
    }
    
    # Calculate base confidence
    result["confidence"] = calculate_confidence_score(source_text, feature_name)
    
    # Feature-specific validation
    if feature_name == "stage_at_diagnosis" or feature_name == "current_stage":
        if feature_value not in VALID_STAGES:
            result["validation_status"] = "invalid"
            result["uncertainty_flag"] = True
            result["clinical_notes"].append(f"Invalid stage value: {feature_value}")
            result["value"] = "unknown"
    
    elif feature_name == "ecog_ps":
        if feature_value not in VALID_ECOG:
            result["validation_status"] = "invalid"
            result["uncertainty_flag"] = True
            result["clinical_notes"].append(f"Invalid ECOG value: {feature_value}")
            result["value"] = None
    
    elif feature_name == "PD_L1":
        if feature_value not in VALID_PD_L1:
            result["validation_status"] = "invalid"
            result["uncertainty_flag"] = True
            result["clinical_notes"].append(f"Invalid PD-L1 value: {feature_value}")
            result["value"] = "not mentioned"
    
    elif feature_name == "mutations":
        if isinstance(feature_value, list):
            valid_mutations = [m for m in feature_value if m in VALID_MUTATIONS]
            if len(valid_mutations) != len(feature_value):
                result["validation_status"] = "partial"
                result["uncertainty_flag"] = True
                result["clinical_notes"].append("Some mutations not recognized")
                result["value"] = valid_mutations if valid_mutations else ["not mentioned"]
        elif feature_value not in VALID_MUTATIONS:
            result["validation_status"] = "invalid"
            result["uncertainty_flag"] = True
            result["clinical_notes"].append(f"Invalid mutation value: {feature_value}")
            result["value"] = "not mentioned"
    
    # Hallucination detection for missing source text
    if not source_text or source_text.strip() == "" or source_text.strip().lower() == "null":
        if feature_value != "not mentioned" and feature_value != [] and feature_value is not None:
            result["validation_status"] = "potential_hallucination"
            result["uncertainty_flag"] = True
            result["confidence"] = 0
            result["clinical_notes"].append("Feature extracted without source evidence - potential hallucination")
    
    return result

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    # ```json ... ``` or ``` ... ```
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", s, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else s

def _coerce_to_json_obj(raw: Any) -> dict:
    """
    Accepts:
      - dict already shaped per schema
      - string containing JSON (optionally wrapped in code fences)
      - wrapper dicts like {"response": "{...}"} or {"response": {...}}
    Returns a dict (schema object) or raises ValueError.
    """
    # If already a dict that looks like the patient-features object, accept it
    if isinstance(raw, dict):
        # Minimal sanity check: expect some known keys
        expected_keys = {"age", "gender", "ecog_ps", "histology",
                         "stage_at_diagnosis", "current_stage", "pd_l1_tps"}
        if expected_keys & set(raw.keys()):
            return raw
        # If it's a wrapper like {"response": ...}
        if "response" in raw:
            return _coerce_to_json_obj(raw["response"])

    # If it's a string, strip fences and load
    if isinstance(raw, str):
        text = _strip_code_fences(raw)
        text = text.strip()
        # If wrapper-as-string e.g. '{"response": {...}}'
        try:
            maybe = json.loads(text)
            return _coerce_to_json_obj(maybe)
        except json.JSONDecodeError:
            pass

    raise ValueError("Unable to coerce model output to schema JSON object.")

def extract_features_with_llm(text: str) -> Dict[str, Any]:
    """Extract features using LLM with robust parsing."""
    llm = get_llm_processor()
    prompt = f"""
Sei un modello NLP per l’assegnazione a studi clinici sul carcinoma polmonare.

Restituisci UNO e SOLO UNO oggetto JSON che rispetti ESATTAMENTE lo schema e le regole seguenti.
- Output: SOLO l’oggetto JSON. Nessun testo prima/dopo. Nessun markdown. Nessun commento. Nessun code fence.
- Se un valore non è ricavabile dal testo, scrivi esattamente "not mentioned" (per TUTTI i campi, inclusi i numerici).
- Compila SEMPRE ogni campo "*_source_text" con l’esatto frammento di testo di supporto; se non presente, usa "not mentioned".
- Quando sono richieste liste, restituisci un array JSON. Se non è menzionato nulla, restituisci ["not mentioned"].
- Normalizza i nomi in inglese quando possibile (es. carboplatino → carboplatin; linfonodali → lymph nodes).

Schema (senza commenti inline):
{{
  "age": int | "not mentioned",
  "age_source_text": "string",

  "gender": "male" | "female" | "not mentioned",
  "gender_source_text": "string",

  "ecog_ps": 0 | 1 | 2 | "not mentioned",
  "ecog_ps_source_text": "string",

  "histology": "squamous" | "adenocarcinoma" | "small_cell" | "not mentioned",
  "histology_source_text": "string",

  "current_stage": "II" | "III" | "IV" | "not mentioned",
  "current_stage_source_text": "string",

  "line_of_therapy": "1L" | "2L" | ">=3L" | "adjuvant" | "neoadjuvant" | "maintenance" | "not mentioned",
  "line_of_therapy_source_text": "string",

  "pd_l1_tps": "0%" | "<1%" | "1-49%" | ">=50%" | "not mentioned",
  "pd_l1_tps_source_text": "string",

  "biomarkers": "KRAS_G12C" | "EGFR_exon19_del" | "EGFR_L858R" | "EGFR_T790M" | "EGFR_L861Q" | "EGFR_P772R" | "MET_amplification" | "MET_exon14" | "HER2_exon20" | "ALK" | "ROS1" | "RET" | "NTRK" | "BRAF_V600E" | "STK11" | "TP53" | "DNMT3A" | "KRAS_Q61H" | "not mentioned",
  "biomarkers_source_text": "string",

  "brain_metastasis": ["true" | "false" | "not mentioned"],
  "brain_metastasis_source_text": "string",

  "prior_systemic_therapies": ["carboplatin" | "cisplatin" | "etoposide" | "pemetrexed" | "paclitaxel" | "docetaxel" | "pembrolizumab" | "nivolumab" | "atezolizumab" | "durvalumab" | "osimertinib" | "erlotinib" | "gefitinib" | "sotorasib" | "adagrasib" | "divarasib" | "savolitinib" | "alectinib" | "crizotinib" | "other"] | ["not mentioned"],
  "prior_systemic_therapies_source_text": "string",

  "comorbidities": ["string"] | ["not mentioned"],
  "comorbidities_source_text": "string",

  "concomitant_treatments": ["string"] | ["not mentioned"],
  "concomitant_treatments_source_text": "string"
}}

Linee guida operative (commenti fuori dallo schema):
- Per "line_of_therapy": se il testo dice "candidata a terapia sistemica di I linea" → line_of_therapy="1L"; line_of_therapy_source_text="candidata a terapia sistemica di I linea".
- Per "pd_l1_tps": usa i bucket esatti richiesti.
- Per "biomarkers": cerca preferibilmente nelle sezioni "Sintesi Clinica" e "Diagnosi Oncologica".
  Esempi:
    • "EGFR Exon 19 deletion rilevata" → "biomarkers": "EGFR_exon19_del"
    • "KRAS ... (Q61H) 34%" → "biomarkers": "KRAS_Q61H"
- Per "brain_metastasis": preferisci la TC/PET più recente.
  Esempi:
    • "CNS metastasis" → ["true"]
    • "secondarismi linfonodali, pleurici ed ossei." → ["false"]
- Per "prior_systemic_therapies": estrarre SOLO trattamenti oncologici già somministrati (non intenzioni future).
  Esempi:
    • "la terapia sarà carboplatino + pemetrexed" → "prior_systemic_therapies": ["not mentioned"]; "prior_systemic_therapies_source_text": "not mentioned"
    • "il paziente risulta candidabile a trattamento chemio-immunoterapico di 1° linea a base di sali di platino + etoposide + atezolizumab." → "prior_systemic_therapies": ["not mentioned"]
- Per "comorbidities": estrarre SOLO dalla sezione "COMORBIDITÀ".
- Per "concomitant_treatments": estrarre SOLO dalla sezione "terapie domiciliari" (solo nomi, senza dosi/date).
  Esempio: "Losaprex (losartan)... Omeprazolo..." → ["losartan","omeprazolo"]
- Per metastasi, preferire i reperti della TC/PET più recente.
- Qualsiasi informazione assente → "not mentioned" (mai null).

Ora elabora la seguente cartella clinica STRUTTURATA usando l’estrazione BASATA SU SEZIONI:

Testo:
{text}
"""

    logger.info(f"Prompt sent to LLM:\n{prompt[:2000]}")
    try:
        response = llm.generate_response(prompt)
        logger.info(f"LLM Raw Response: {str(response)[:1000]}")

        # Persist raw for debugging
        try:
            os.makedirs("logs", exist_ok=True)
            filename = f"logs/llm_raw_debug_{int(time.time())}.json"
            with open(filename, "w") as f:
                json.dump({"prompt": prompt, "response": response}, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved LLM debug output to {filename}")
        except Exception as e:
            logger.warning(f"Failed to write raw debug log: {e}")

        # Robust coercion
        llm_obj = _coerce_to_json_obj(response)

        if not isinstance(llm_obj, dict):
            logger.error(f"LLM response is not a JSON object: {type(llm_obj)}")
            return {}

        logger.info(f"Extracted Features (with source text): {json.dumps(llm_obj, indent=2, ensure_ascii=False)}")
        return llm_obj

    except Exception as e:
        logger.error(f"Unexpected error in feature extraction: {e}")
        return {}

def strip_source_fields(obj):
    """Remove all source text, confidence, and validation metadata for trial matching."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            # Remove source text, confidence scores, validation flags, and clinical notes
            if not any(suffix in k for suffix in ['_source_text', '_confidence', '_uncertainty_flag', 
                                                 '_validation_status', '_clinical_notes', '_confidence_score']):
                out[k] = strip_source_fields(v)
        return out
    elif isinstance(obj, list):
        return [strip_source_fields(x) for x in obj]
    else:
        return obj

def _it_label(key: str) -> str:
    """Mappa chiavi canoniche -> etichette italiane per display."""
    mapping = {
        # Localized
        "neoadjuvant_chemotherapy": "Chemioterapia neoadiuvante",
        "adjuvant_chemotherapy": "Chemioterapia adiuvante",
        "adjuvant_radiotherapy": "Radioterapia adiuvante",
        "adjuvant_immunotherapy": "Immunoterapia adiuvante",
        "adjuvant_targeted_therapy": "Terapia target adiuvante",
        "perioperative_adjuvant_chemotherapy": "Chemioterapia perioperatoria (adiuvante)",
        # Metastatic lines
        "line_1": "I linea (metastatico)",
        "line_2": "II linea (metastatico)",
        "line_3": "III linea (metastatico)",
        "chemotherapy": "Chemioterapia",
        "immunotherapy": "Immunoterapia",
        "targeted_therapy": "Terapia target",
    }
    return mapping.get(key, key.replace("_", " ").title())


def _clean_str(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None


def _format_radiotherapy(item: dict) -> Optional[str]:
    site = _clean_str(item.get("site"))
    dose = _clean_str(item.get("dose_fractionation"))
    if site and dose:
        return f"{site} ({dose})"
    if site:
        return site
    if dose:
        return dose
    return None


def _format_drug_item(item: dict, key_order: List[str]) -> Optional[str]:
    """Estrae il primo campo non vuoto tra quelli indicati (es. regimen/agent)."""
    for k in key_order:
        v = _clean_str(item.get(k))
        if v:
            return v
    return None

'''
def build_previous_treatments_display(previous_treatments: dict) -> List[str]:
    """
    Converte la struttura annidata 'previous_treatments' in una lista di righe testo
    pulite e pronte per il frontend. Le liste vuote o stringhe vuote vengono eliminate.
    """
    if not isinstance(previous_treatments, dict):
        return []

    out: List[str] = []

    # --- Localized ---
    localized = previous_treatments.get("localized", {})
    if isinstance(localized, dict):
        for bucket_key, items in localized.items():
            if not isinstance(items, list) or not items:
                continue

            label = _it_label(bucket_key)
            parts: List[str] = []

            if bucket_key == "adjuvant_radiotherapy":
                for it in items:
                    if isinstance(it, dict):
                        txt = _format_radiotherapy(it)
                        if txt:
                            parts.append(txt)
            elif bucket_key in {"neoadjuvant_chemotherapy", "adjuvant_chemotherapy",
                                "perioperative_adjuvant_chemotherapy"}:
                for it in items:
                    if isinstance(it, dict):
                        txt = _format_drug_item(it, ["regimen"])
                        if txt:
                            parts.append(txt)
            elif bucket_key in {"adjuvant_immunotherapy", "adjuvant_targeted_therapy"}:
                for it in items:
                    if isinstance(it, dict):
                        txt = _format_drug_item(it, ["agent"])
                        if txt:
                            parts.append(txt)

            if parts:
                out.append(f"Localized â€” {label}: " + "; ".join(parts))

    # --- Metastatic ---
    metastatic = previous_treatments.get("metastatic", {})
    if isinstance(metastatic, dict):
        for line_key, line_obj in metastatic.items():
            if not isinstance(line_obj, dict):
                continue
            line_label = _it_label(line_key)

            # Ogni sotto-categoria (chemotherapy / immunotherapy / targeted_therapy)
            for cat_key in ["chemotherapy", "immunotherapy", "targeted_therapy"]:
                items = line_obj.get(cat_key, [])
                if not isinstance(items, list) or not items:
                    continue

                cat_label = _it_label(cat_key)
                parts: List[str] = []
                key_order = ["regimen"] if cat_key == "chemotherapy" else ["agent"]

                for it in items:
                    if isinstance(it, dict):
                        txt = _format_drug_item(it, key_order)
                        if txt:
                            parts.append(txt)

                if parts:
                    out.append(f"{line_label} â€” {cat_label}: " + "; ".join(parts))

    return out
'''


def match_trials_llm(llm_text: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Match trials using LLM with YOUR provided matching prompt."""
    logger.info("Starting LLM Trial Matching (Batched)...")
    print("Starting LLM Trial Matching (Batched)...")

    llm = get_explainer_llm()
    trials = get_all_trials()
    logger.info(f"Trials loaded: {len(trials)}")
    print(f"Trials loaded: {len(trials)}")

    if not trials:
        logger.error("No trials found in database")
        print("No trials found in database")
        return []

    matched_trials: List[Dict[str, Any]] = []
    batch_size = 3
    logger.info(f"Matching Trials using LLM with Batching ({batch_size} Trials per Batch)...")
    print(f"Matching Trials using LLM with Batching ({batch_size} Trials per Batch)...")

    # Strip *_source_text ecc. per il matching
    sanitized = strip_source_fields(llm_text)
    logger.info(f"Sanitized features for trial matching: {json.dumps(sanitized, indent=2)}")

    trial_batches = [trials[i:i + batch_size] for i in range(0, len(trials), batch_size)]
    debug_filename = f"logs/llm_match_debug_{int(time.time())}.json"
    debug_data = {"llm_text": sanitized, "batch_responses": []}
    logger.info(f"Debug file initialized: {debug_filename}")

    def safe_for_json(x):
        try:
            json.dumps(x)
            return x
        except TypeError:
            if hasattr(x, "__dict__"):
                try:
                    return {k: safe_for_json(v) for k, v in x.__dict__.items()}
                except Exception:
                    return str(x)
            return str(x)

    for batch_index, batch in enumerate(trial_batches):
        logger.info(f"Processing batch {batch_index + 1} of {len(trial_batches)}...")
        trials_payload = [safe_for_json(trial) for trial in batch]

        # === PROMPT #1 (Trial Matching) — EXACT content you provided ===
        prompt = f"""
You are a clinical trial matching assistant for lung cancer.

INPUTS:

PATIENT FEATURES:
{json.dumps(sanitized, indent=2)}

### TRIALS:
{json.dumps([trial for trial in batch], indent=2)}

TASK

SCORING (strict):
- Start from 100.
- For EACH INCLUSION not met: −10 points.
- For EACH EXCLUSION violated: write already "Not Eligible" and reduce to ≤50 immediately.
- "Eligible" if final score ≥ 70, else "Not Eligible".

OUTPUT
Return ONLY a JSON array (no prose, no markdown), one object per trial, in this exact format:
[
  {{
    "trial_id": "<trial.id>",
    "title": "<trial.title>",
    "description": "<trial.description>",
    "match_score": <integer 0-100>,
    "overall_recommendation": "Eligible"|"Not Eligible",
    "criteria_analysis": "Short bullet-style rationale: which inclusions were met/not met and which exclusions were violated (quote concise fragments).",
    "summary": "One-sentence clinical rationale linking the patient features to the decision."
  }}
]

IMPORTANT
- If any single exclusion is clearly violated, you may reduce to ≤50 immediately and set "Not Eligible".
- Be conservative with ambiguous/absent data: do NOT assume eligibility; mark the corresponding inclusion as “not met”.
"""
        try:
            response = llm.generate_response(prompt)
            logger.info(f"LLM Raw Response (Batch {batch_index + 1}) first 1k:\n{str(response)[:1000]}")

            if not response:
                logger.error(f"Empty response from LLM for Batch {batch_index + 1}")
                debug_data["batch_responses"].append({
                    "batch_index": batch_index + 1,
                    "response": "EMPTY RESPONSE"
                })
                continue

            debug_data["batch_responses"].append({
                "batch_index": batch_index + 1,
                "raw_response": response
            })

            match_results = parse_llm_response(response)

            if isinstance(match_results, list):
                for idx, match_result in enumerate(match_results):
                    if idx >= len(batch):
                        break
                    trial = batch[idx]
                    t_id = trial.get("id") if isinstance(trial, dict) else getattr(trial, "id", None)
                    t_title = trial.get("title", "Unknown Trial") if isinstance(trial, dict) else getattr(trial, "title", "Unknown Trial")
                    t_desc = trial.get("description", "No description provided.") if isinstance(trial, dict) else getattr(trial, "description", "No description provided.")

                    matched_trials.append({
                        "trial_id": t_id,
                        "title": t_title,
                        "description": t_desc,
                        "match_score": match_result.get("match_score", 0),
                        "recommendation": match_result.get("overall_recommendation", "UNKNOWN"),
                        "criteria_analysis": match_result.get("criteria_analysis"),
                        "summary": match_result.get("summary", "No summary available.")
                    })
            else:
                logger.error(f"Invalid JSON structure for Batch {batch_index + 1}")

        except Exception as e:
            logger.error(f"Error in LLM matching for batch {batch_index + 1}: {str(e)}")
            debug_data["batch_responses"].append({
                "batch_index": batch_index + 1,
                "error": str(e)
            })

    with open(debug_filename, "w") as f:
        json.dump(debug_data, f, indent=2)
    logger.info(f"Saved LLM trial matching debug output to {debug_filename}")
    print(f"Saved LLM trial matching debug output to {debug_filename}")

    matched_trials.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    logger.info(f"Trial matching completed. {len(matched_trials)} trials matched.")

    matched_trials_filename = f"logs/matched_trials_{int(time.time())}.json"
    with open(matched_trials_filename, "w") as f:
        json.dump(matched_trials, f, indent=2)
    logger.info(f"Matched trials saved to {matched_trials_filename}")

    return matched_trials

def parse_llm_response(raw_response: str) -> list:
    """Parse LLM response for trial matching with enhanced error handling."""
    try:
        # Try direct JSON first
        try:
            direct = json.loads(raw_response)
            # Accept either array directly, or wrapper with "response"
            if isinstance(direct, list):
                return direct
            if isinstance(direct, dict) and "response" in direct:
                inner = direct["response"]
                if isinstance(inner, list):
                    return inner
                if isinstance(inner, str):
                    # Strip code fences and load
                    inner = _strip_code_fences(inner)
                    return json.loads(inner) if inner.strip().startswith("[") else []
        except json.JSONDecodeError:
            pass

        # If it's a string with code fences or array
        text = _strip_code_fences(raw_response)
        # Try to find JSON array anywhere
        m = re.search(r"(\[.*\])", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))

        logger.error("No JSON array found in LLM response.")
        return []
    except Exception as e:
        logger.error(f"Error parsing LLM trial matching response: {str(e)}")
        return []

def clean_expired_files(upload_folder: str = 'uploads', max_age_minutes: int = 30) -> None:
    """Clean expired upload files with enhanced logging."""
    try:
        expiration_time = datetime.now() - timedelta(minutes=max_age_minutes)
        if not os.path.exists(upload_folder):
            logger.warning(f"Upload folder does not exist: {upload_folder}")
            return

        cleaned_count = 0
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            if os.path.isfile(file_path) and (filename.endswith('.pdf') or filename.startswith('annotated_')):
                file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if file_creation_time < expiration_time:
                    os.remove(file_path)
                    cleaned_count += 1
                    logger.info(f"Removed expired file: {filename}")
                    
        logger.info(f"Cleanup completed: {cleaned_count} expired files removed")
    except Exception as e:
        logger.error(f"Error cleaning expired files: {str(e)}")

def process_patient_document(text_or_file: Union[str, bytes], is_file: bool = False) -> Dict[str, Any]:
    """Main processing pipeline with PDF annotation support."""
    try:
        pdf_path = None
        if is_file:
            pdf_path = text_or_file
            text_content = extract_text_from_pdf(text_or_file)
        else:
            text_content = str(text_or_file)

        features_with_sources = extract_features_with_llm(text_content)
        if not features_with_sources:
            return {
                "success": False,
                "error": "Failed to extract clinical features",
                "features": {},
                "highlighted_text": "",
                "annotated_pdf_url": None,
                "matched_trials": []
            }

        annotated_pdf_url = None
        if pdf_path and is_file:
            try:
                annotated_pdf_path = create_annotated_pdf(pdf_path, features_with_sources)
                annotated_pdf_url = f"/view-pdf/{os.path.basename(annotated_pdf_path)}"
            except Exception as e:
                logger.error(f"Failed to create annotated PDF: {e}")

        highlighted_text = highlight_sources(text_content, features_with_sources)

        # Clean for frontend (senza _source_text ecc.)
        clean_features = strip_source_fields(features_with_sources)

        # >>> AGGIUNTA: display friendly for previous_treatments
        pt = clean_features.get("previous_treatments")
        clean_features["previous_treatments_display"] = build_previous_treatments_display(pt) if pt else []

        # Matching (usa la versione completa; internamente si fa lo strip)
        matched_trials = match_trials_llm(features_with_sources)

        return {
            "success": True,
            "features": clean_features,
            "highlighted_text": highlighted_text,
            "annotated_pdf_url": annotated_pdf_url,
            "matched_trials": matched_trials,
            "original_text": text_content
        }

    except Exception as e:
        logger.error(f"Error in processing pipeline: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "features": {},
            "highlighted_text": "",
            "annotated_pdf_url": None,
            "matched_trials": []
        }

def highlight_sources(text: str, features: Dict[str, Any]) -> str:
    """
    Evidenzia nel testo le occorrenze riportate nei campi *_source_text (string o list[str]).
    Restituisce HTML semplice con <mark style="background:...">...</mark>.
    """
    try:
        highlighted = text

        highlight_colors = {
            'age': '#ffeb3b',
            'gender': '#e91e63',
            'diagnosis': '#2196f3',
            'stage': '#4caf50',
            'ecog': '#ff9800',
            'mutations': '#9c27b0',
            'metastases': '#f44336',
            'pd_l1': '#00bcd4',
            'comorbidities': '#795548',
            'treatments': '#607d8b'
        }

        def get_feature_type(key: str) -> str:
            k = key.lower()
            if 'age' in k: return 'age'
            if 'gender' in k: return 'gender'
            if 'diagnosis' in k: return 'diagnosis'
            if 'stage' in k: return 'stage'
            if 'ecog' in k: return 'ecog'
            if 'mutation' in k: return 'mutations'
            if 'metastas' in k: return 'metastases'
            if 'pd_l1' in k: return 'pd_l1'
            if 'comorbid' in k: return 'comorbidities'
            if 'treatment' in k: return 'treatments'
            return 'age'

        # Per evitare rimpiazzi che si sovrappongono, ordina le evidenze per lunghezza desc.
        evidences: List[Tuple[str,str]] = []  # (snippet, color)

        for key, value in (features or {}).items():
            if not key.endswith('_source_text') or value in (None, "", []):
                continue

            color = highlight_colors.get(get_feature_type(key), '#ffeb3b')

            if isinstance(value, str):
                v = value.strip()
                if v:
                    evidences.append((v, color))
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, (str, int, float)):
                        sv = str(v).strip()
                        if sv:
                            evidences.append((sv, color))

        # Ordina per lunghezza (prima le frasi piÃ¹ lunghe)
        evidences.sort(key=lambda t: len(t[0]), reverse=True)

        # Rimpiazzo safe (case-sensitive, ma puoi cambiare a tua scelta)
        for snippet, color in evidences:
            # Escapa snippet per uso in regex letterale
            pattern = re.escape(snippet)
            repl = rf'<mark style="background:{color}">{snippet}</mark>'
            # usa limit alto per evidenziare tutte le occorrenze
            highlighted = re.sub(pattern, repl, highlighted)

        return highlighted

    except Exception as e:
        logger.error(f"highlight_sources failed: {e}")
        return text
      
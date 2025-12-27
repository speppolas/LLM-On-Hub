import os
import time
import re
import json
import logging
import re
import pdfplumber
from typing import Dict, Any, Union, List
from datetime import datetime, timedelta
from flask import current_app
from app.core.llm_processor import get_llm_processor
from app.utils import get_all_trials
from app import logger

# Ensure the logs folder exists
os.makedirs("logs", exist_ok=True)
 
def extract_text_from_pdf(pdf_file: Union[str, bytes]) -> str:
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "")
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise Exception(f"Unable to extract text from PDF: {str(e)}")

def extract_features_with_llm(text: str) -> Dict[str, Any]:
    from app.core.llm_processor import get_llm_processor
    llm = get_llm_processor()
    prompt = f"""
Sei un modello NLP per l’assegnazione a studi clinici sul carcinoma polmonare.

Data la seguente cartella clinica STRUTTURATA usando l’estrazione BASATA SU SEZIONI:

Testo:
{text}

Restituisci UNO e SOLO UNO oggetto JSON che rispetti ESATTAMENTE lo schema e le regole seguenti.
- Output: SOLO l’oggetto JSON. Nessun testo prima/dopo. Nessun markdown. Nessun commento. Nessun code fence.
- Se un valore non è ricavabile dal testo, scrivi esattamente "not mentioned" (per TUTTI i campi, inclusi i numerici).
- Quando sono richieste liste, restituisci un array JSON. Se non è menzionato nulla, restituisci ["not mentioned"].
- Normalizza i nomi in inglese quando possibile (es. carboplatino → carboplatin; linfonodali → lymph nodes).

Schema (senza commenti inline):
{{
  "age": int | "not mentioned",
  "gender": "male" | "female" | "not mentioned",
  "ecog_ps": 0 | 1 | 2 | "not mentioned",
  "histology": "squamous" | "adenocarcinoma" | "small_cell" | "not mentioned",
  "current_stage": "II" | "III" | "IV" | "not mentioned",
  "line_of_therapy": "1L" | "2L" | ">=3L" | "adjuvant" | "neoadjuvant" | "maintenance" | "not mentioned",
  "pd_l1_tps": "0%" | "<1%" | "1-49%" | ">=50%" | "not mentioned",
  "biomarkers": "KRAS_G12C" | "EGFR_exon19_del" | "EGFR_L858R" | "EGFR_T790M" | "EGFR_L861Q" | "EGFR_P772R" | "MET_amplification" | "MET_exon14" | "HER2_exon20" | "ALK" | "ROS1" | "RET" | "NTRK" | "BRAF_V600E" | "STK11" | "TP53" | "DNMT3A" | "KRAS_Q61H" | "not mentioned",
  "brain_metastasis": ["true" | "false" | "not mentioned"],
  "prior_systemic_therapies": ["carboplatin" | "cisplatin" | "etoposide" | "pemetrexed" | "paclitaxel" | "docetaxel" | "pembrolizumab" | "nivolumab" | "atezolizumab" | "durvalumab" | "osimertinib" | "erlotinib" | "gefitinib" | "sotorasib" | "adagrasib" | "divarasib" | "savolitinib" | "alectinib" | "crizotinib" | "other"] | ["not mentioned"],
  "comorbidities": ["string"] | ["not mentioned"],
  "concomitant_treatments": ["string"] | ["not mentioned"],
}}

Linee guida operative (commenti fuori dallo schema):
- Per "line_of_therapy": se il testo dice "candidata a terapia sistemica di I linea" → line_of_therapy="1L".
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
    • "la terapia sarà carboplatino + pemetrexed" → "prior_systemic_therapies": ["not mentioned"]
    • "il paziente risulta candidabile a trattamento chemio-immunoterapico di 1° linea a base di sali di platino + etoposide + atezolizumab." → "prior_systemic_therapies": ["not mentioned"]
- Per "comorbidities": estrarre SOLO dalla sezione "COMORBIDITÀ".
- Per "concomitant_treatments": estrarre SOLO dalla sezione "terapie domiciliari" (solo nomi, senza dosi/date).
  Esempio: "Losaprex (losartan)... Omeprazolo..." → ["losartan","omeprazolo"]
- Per metastasi, preferire i reperti della TC/PET più recente.
- Qualsiasi informazione assente → "not mentioned" (mai null).
"""

    logger.info(f"Prompt sent to LLM:\n{prompt[:2000]}")  # Log the prompt snippet
    
    try:
        # Send prompt to LLM and receive response
        response = llm.generate_response(prompt)
        logger.info(f"🧠 LLM Raw Response: {response[:1000]}")

        try:
            os.makedirs("logs", exist_ok=True)
            filename = f"logs/llm_raw_debug_{int(time.time())}.json"
            with open(filename, "w") as f:
                json.dump({"prompt": prompt, "response": response}, f, indent=2)
            logger.info(f"💾 Saved LLM debug output to {filename}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to write raw debug log: {e}")
        
        
        # Parse the LLM response to get 'llm_text'
        parsed = json.loads(response)      
        
        if isinstance(parsed, dict) and "response" in parsed:
            llm_text = parsed["response"]
            if isinstance(llm_text, str):
                llm_text = json.loads(llm_text)
        else:
            llm_text = parsed
        
        if not isinstance(llm_text, dict):
            logger.error(f"❌ LLM response is not a valid JSON object: {llm_text}")
            return {}

        logger.info(f"✅ Extracted Features (llm_text): {json.dumps(llm_text, indent=2)}")
        return llm_text
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decoding error: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Unexpected error in feature extraction: {e}")
        return {}
    
def safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        # fallback: tenta di estrarre il primo JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        logger.error(f"❌ Invalid JSON from LLM:\n{text[:500]}")
        return {}
   

def normalize_llm_criteria_output(raw: Any) -> Dict[str, Dict[str, Any]]:
    normalized = {}

    if isinstance(raw, dict):
        # Caso: dict indicizzato
        for k, v in raw.items():
            if isinstance(v, dict):
                # mappa possibili nomi di decision
                if "decision" in v:
                    v["decision"] = v["decision"].lower()
                    normalized[str(k)] = v
                elif "eligibility" in v:
                    v["decision"] = v["eligibility"].lower()
                    normalized[str(k)] = v
                elif "status" in v:
                    # mapping semplice
                    status = v["status"].lower()
                    if status in ["met", "yes", "true"]:
                        v["decision"] = "included"
                    elif status in ["not met", "no", "false"]:
                        v["decision"] = "not included"
                    normalized[str(k)] = v

        # Caso: dict singolo
        if "decision" in raw:
            raw["decision"] = raw["decision"].lower()
            normalized["0"] = raw

    elif isinstance(raw, list):
        for idx, item in enumerate(raw):
            if isinstance(item, dict):
                if "decision" in item:
                    item["decision"] = item["decision"].lower()
                    normalized[str(idx)] = item
                elif "eligibility" in item:
                    item["decision"] = item["eligibility"].lower()
                    normalized[str(idx)] = item

    return normalized

def normalize_criteria(criteria: List[str]) -> List[str]:
    return [
        c.strip()
        for c in criteria
        if c.strip()
        and not c.lower().startswith("inclusion")
        and not c.lower().startswith("exclusion")
    ]


def build_inclusion_prompt(trial, patient_features):
    return f"""
You are a clinical trial eligibility engine.

Your task is to evaluate EACH inclusion criterion of the trial ONE BY ONE
against the structured patient data.

PATIENT DATA (ground truth, do not hallucinate):
{json.dumps(patient_features, indent=2)}

TRIAL INCLUSION CRITERIA:
{json.dumps(normalize_criteria(trial["inclusion_criteria"]), indent=2)}

Rules:
- Use ONLY the provided patient data
- If a criterion requires information that is "not mentioned":
  → label = "not enough information"
- Do NOT infer positive findings
- Be strict and literal

Output EXACTLY this JSON format:
{{
  "criterion_index": {{
    "criterion_text": "...",
    "decision": "included" | "not included" | "not enough information",
    "reason": "short clinical reasoning"
  }}
}}
"""

def build_exclusion_prompt(trial, patient_features):
    return f"""
You are a clinical trial eligibility engine.

Evaluate EACH exclusion criterion ONE BY ONE.

PATIENT DATA:
{json.dumps(patient_features, indent=2)}

TRIAL EXCLUSION CRITERIA:
{json.dumps(normalize_criteria(trial["exclusion_criteria"]), indent=2)}

Rules:
- If exclusion criterion is MET → decision = "excluded"
- If explicitly NOT met → "not excluded"
- If info missing → assume NOT TRUE unless biologically impossible

Output EXACT JSON:
{{
  "criterion_index": {{
    "criterion_text": "...",
    "decision": "excluded" | "not excluded",
    "reason": "short clinical reasoning"
  }}
}}
"""

def compute_match_score(inclusions, exclusions):
    score = 100

    for c in inclusions.values():
        decision = c.get("decision")
        if decision == "not included":
            score -= 10
        elif decision == "not enough information":
            score -= 5

    for c in exclusions.values():
        if c.get("decision") == "excluded":
            score -= 50


    return max(score, 0)

def match_trials_llm(patient_features: Dict[str, Any]) -> List[Dict[str, Any]]:
    logger.info("🔍 Starting TrialGPT-style trial matching")
    llm = get_llm_processor()
    trials = get_all_trials()

    results = []

    for trial in trials:
        trial_id = trial.get("id")
        title = trial.get("title", "Unknown title")

        logger.info(f"➡️ Matching trial {trial_id}")

        inc_prompt = build_inclusion_prompt(trial, patient_features)
        inc_raw = llm.generate_response(inc_prompt)
        logger.info(f"INC RAW ({trial_id}): {inc_raw}")
        inc_json_raw = safe_json_loads(inc_raw)
        inc_json = normalize_llm_criteria_output(inc_json_raw)

        logger.info(f"INC NORM ({trial_id}): {inc_json}")

        if not inc_json:
            logger.warning(f"⚠️ No inclusion criteria parsed for {trial_id}")
            inc_json = {}

        exc_prompt = build_exclusion_prompt(trial, patient_features)
        exc_raw = llm.generate_response(exc_prompt)
        logger.info(f"EXC RAW ({trial_id}): {exc_raw}")
        exc_json_raw = safe_json_loads(exc_raw)
        exc_json = normalize_llm_criteria_output(exc_json_raw)
        logger.info(f"EXC NORM ({trial_id}): {exc_json}")
        if not exc_json:
            logger.warning(f"⚠️ No exclusion criteria parsed for {trial_id}")
            exc_json = {}

        score = compute_match_score(inc_json, exc_json)

        excluded = any(
            c["decision"] == "excluded"
            for c in exc_json.values()
        )

        if excluded:
            score = -1

        results.append({
            "trial_id": trial_id,
            "title": title,
            "match_score": score,
            "excluded": excluded,
            "inclusion_criteria": inc_json,
            "exclusion_criteria": exc_json,
            "summary": (
                "Excluded due to exclusion criteria"
                if excluded
                    else "Potentially eligible based on available data"
            )
        })

    results.sort(key=lambda x: (x["excluded"], -x["match_score"]))

    filename = f"logs/matched_trials_{int(time.time())}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"✅ Trial matching completed: {len(results)} trials")
    logger.info(f"💾 Results saved to {filename}")

    return results

def clean_expired_files(upload_folder: str = 'uploads', max_age_minutes: int = 30) -> None:
    try:
        expiration_time = datetime.now() - timedelta(minutes=max_age_minutes)
        if not os.path.exists(upload_folder):
            logger.warning(f"⚠️ Upload folder does not exist: {upload_folder}")
            return

        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            if os.path.isfile(file_path) and filename.endswith('.pdf'):
                file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if file_creation_time < expiration_time:
                    os.remove(file_path)
                    logger.info(f"🗑️ Removed expired file: {filename}")
    except Exception as e:
        logger.error(f"❌ Error cleaning expired files: {str(e)}")
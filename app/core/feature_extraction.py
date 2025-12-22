import os
import time
import re
import json
import logging
import pdfplumber
from typing import Dict, Any, Union, List
from datetime import datetime, timedelta
from flask import current_app
from app.core.llm_processor import get_llm_processor
from app.core.schema_validation import ClinicalFeatures, ValidationError
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
    # prompt = f"""
    # You are a medical AI assistant. Extract clinical features from the clinical text below. For each field, return:
    # - The extracted value
    # - And the corresponding *_source_text used to infer it

    # Return ONLY a valid JSON object with this structure:

    # {{
    # "age": integer or null,
    # "age_source_text": string or null,
    # "gender": "male" | "female" | "not mentioned",
    # "gender_source_text": string or null,
    # "diagnosis": string or null,
    # "diagnosis_source_text": string or null,
    # "stage": string or null,
    # "stage_source_text": string or null,
    # "ecog": string or null,
    # "ecog_source_text": string or null,
    # "mutations": list of strings,
    # "mutations_source_text": list of strings,
    # "metastases": list of strings,
    # "metastases_source_text": list of strings,
    # "previous_treatments": list of strings,
    # "previous_treatments_source_text": list of strings,
    # "lab_values": dict,
    # "lab_values_source_text": dict
    # }}

    # TEXT:
    # {text}

    # JSON ONLY OUTPUT:
    # """
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
        resp_json = json.loads(response)      
        llm_text_str = resp_json['response']
        llm_text = json.loads(llm_text_str)  if isinstance(llm_text_str, str) else llm_text_str

        if not isinstance(llm_text, dict):
            logger.error(f"❌ LLM response is not a valid JSON object: {llm_text}")
            return {}

        logger.info(f"✅ Extracted Features (llm_text): {json.dumps(llm_text, indent=2)}")
        return llm_text

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decoding error: {str(e)} - Raw response: {response}")
        return {}
    except Exception as e:
        logger.error(f"❌ Unexpected error in feature extraction: {e}")
        return {}

def highlight_sources(text: str, features: Dict[str, Any]) -> str:
    for key, value in features.items():
        if key.endswith('_source_text') and isinstance(value, str) and value.strip():
            try:
                escaped = re.escape(value.strip())
                text = re.sub(f"({escaped})", r'<mark>\1</mark>', text, flags=re.IGNORECASE)
            except Exception as e:
                logger.warning(f"⚠️ Failed to highlight '{value}': {e}")
    return text



# import json
# import time
# import re
# import os
# from typing import Dict, Any, List
# from datetime import datetime, timedelta

# def parse_llm_response(raw_response: str) -> list:
#     """
#     Estrae e parsifica il JSON dei trial dalla chiave 'response' all'interno di raw_response.
#     """
#     try:
#         response_data = json.loads(raw_response)
#         llm_text_response = response_data.get("response", "")
#         if not llm_text_response:
#             raise ValueError("❌ Nessuna risposta trovata nella chiave 'response'.")

#         json_match = re.search(r"```json\s*(\[.*?\])\s*```", llm_text_response, re.DOTALL)
#         if not json_match:
#             json_match = re.search(r"```(.*?)```", llm_text_response, re.DOTALL)

#         if json_match:
#             json_text = json_match.group(1).strip()
#             parsed_json = json.loads(json_text)
#             return parsed_json if isinstance(parsed_json, list) else []
#         else:
#             raise ValueError("❌ Nessun blocco JSON trovato nella risposta LLM.")
#     except (json.JSONDecodeError, ValueError) as e:
#         logger.error(f"❌ Errore durante il parsing della risposta LLM: {str(e)}")
#         return []

# def match_trials_llm(llm_text: Dict[str, Any]) -> List[Dict[str, Any]]:
#     logger.info("✅ Starting LLM Trial Matching (Single Request)...")
#     print("✅ Starting LLM Trial Matching (Single Request)...")

#     llm = get_llm_processor()
#     trials = get_all_trials()
#     logger.info(f"✅ Trials loaded: {len(trials)}")
#     print(f"✅ Trials loaded: {len(trials)}")

#     if not trials:
#         logger.error("❌ No trials found in database")
#         print("❌ No trials found in database")
#         return []

#     prompt = f"""
# You are a clinical AI assistant. Is the following patient eligible for this trials? 

# PATIENT FEATURES:
# {json.dumps(llm_text, indent=2)}

# ### TRIALS:
# {json.dumps(trials, indent=2)}

# Explain me why you decided the eligibility or not through a JSON list where each object is in the following strict format :
# [
#   {{
#     "trial_id": string,
#     "title": string,
#     "description": string,
#     "match_score": integer (0 to 100),
#     "overall_recommendation": string,
#     "criteria_analysis": {{
#       "inclusion_criteria": list,
#       "exclusion_criteria": list
#     }},
#     "summary": string
#   }}
# ]
# """
#     debug_filename = f"logs/llm_match_debug_{int(time.time())}.json"
#     debug_data = {"llm_text": llm_text, "raw_response": None}

#     try:
#         response = llm.generate_response(prompt)
#         logger.info(f"🔧 LLM Raw Response: {response[:1000]}")
#         if not response:
#             logger.error("❌ Empty response from LLM")
#             debug_data["raw_response"] = "EMPTY RESPONSE"
#             return []

#         debug_data["raw_response"] = response

#         match_results = parse_llm_response(response)
#         matched_trials = []

#         if isinstance(match_results, list):
#             for trial, match_result in zip(trials, match_results):
#                 matched_trials.append({
#                     "trial_id": trial.get("id"),
#                     "title": trial.get("title", "Unknown Trial"),
#                     "description": trial.get("description", "No description provided."),
#                     "match_score": match_result.get("match_score", 0),
#                     "recommendation": match_result.get("overall_recommendation", "UNKNOWN"),
#                     "criteria_analysis": match_result.get("criteria_analysis", {}),
#                     "summary": match_result.get("summary", "No summary available.")
#                 })
#         else:
#             logger.error("❌ Invalid JSON structure returned by LLM")

#     except Exception as e:
#         logger.error(f"❌ Error during LLM trial matching: {str(e)}")
#         debug_data["error"] = str(e)
#         matched_trials = []

#     with open(debug_filename, "w") as f:
#         json.dump(debug_data, f, indent=2)
#     logger.info(f"💾 Saved LLM trial matching debug output to {debug_filename}")
#     print(f"💾 Saved LLM trial matching debug output to {debug_filename}")

#     matched_trials.sort(key=lambda x: x.get('match_score', 0), reverse=True)
#     logger.info(f"✅ Trial matching completed. {len(matched_trials)} trials matched.")

#     matched_trials_filename = f"logs/matched_trials_{int(time.time())}.json"
#     with open(matched_trials_filename, "w") as f:
#         json.dump(matched_trials, f, indent=2)
#     logger.info(f"💾 Matched trials saved to {matched_trials_filename}")

#     return matched_trials


import json
import time
import re
from typing import Dict, Any, List

def parse_llm_response(raw_response: str) -> list:
    """
    Estrae e parsifica il JSON dei trial dalla chiave 'response' all'interno di raw_response.
    """
    try:
        # Decodifica il JSON dalla stringa di raw_response
        response_data = json.loads(raw_response)
        
        # Verifica se esiste la chiave 'response' e la estrae
        llm_text_response = response_data.get("response", "")
        if not llm_text_response:
            raise ValueError("❌ Nessuna risposta trovata nella chiave 'response'.")

        # Cerca il blocco JSON nella risposta usando regex
        json_match = re.search(r"```json\s*(\[.*?\])\s*```", llm_text_response, re.DOTALL)
        if not json_match:
            json_match = re.search(r"```(.*?)```", llm_text_response, re.DOTALL)

        if json_match:
            json_text = json_match.group(1).strip()
            parsed_json = json.loads(json_text)
            return parsed_json if isinstance(parsed_json, list) else []

        else:
            raise ValueError("❌ Nessun blocco JSON trovato nella risposta LLM.")

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"❌ Errore durante il parsing della risposta LLM: {str(e)}")
        return []

def match_trials_llm(llm_text: Dict[str, Any]) -> List[Dict[str, Any]]:
    logger.info("✅ Starting LLM Trial Matching (Batched)...")
    print("✅ Starting LLM Trial Matching (Batched)...")  # Immediate feedback

    llm = get_llm_processor()
    trials = get_all_trials()
    logger.info(f"✅ Trials loaded: {len(trials)}")
    print(f"✅ Trials loaded: {len(trials)}")

    if not trials:
        logger.error("❌ No trials found in database")
        print("❌ No trials found in database")
        return []

    matched_trials = []
    logger.info("🔍 Matching Trials using LLM with Batching (4 Trials per Batch)...")
    print("🔍 Matching Trials using LLM with Batching (4 Trials per Batch)...")

    batch_size = 3
    trial_batches = [trials[i:i + batch_size] for i in range(0, len(trials), batch_size)]
    debug_filename = f"logs/llm_match_debug_{int(time.time())}.json"
    debug_data = {"llm_text": llm_text, "batch_responses": []}
    logger.info(f"✅ Debug file initialized: {debug_filename}")

    for batch_index, batch in enumerate(trial_batches):
        logger.info(f"🔹 Processing batch {batch_index + 1} of {len(trial_batches)}...")

        prompt = f"""
You are a clinical AI assistant. Is the following patient eligible for this trials? 

PATIENT FEATURES:
{json.dumps(llm_text, indent=2)}

### TRIALS:
{json.dumps([trial for trial in batch], indent=2)}

Explain me why you decided the eligibility or not through a JSON list where each object is in the following strict format :
[
  {{
    "trial_id": string,
    "title": string,
    "description": string,
    "match_score": integer (0 to 100),
    "overall_recommendation": string,
    "criteria_analysis": string,
    "summary": string
  }}
]
"""
        try:
            response = llm.generate_response(prompt)
            logger.info(f"🔧 LLM Raw Response (Batch {batch_index + 1}): {response[:1000]}")

            if not response:
                logger.error(f"❌ Empty response from LLM for Batch {batch_index + 1}")
                debug_data["batch_responses"].append({
                    "batch_index": batch_index + 1,
                    "response": "EMPTY RESPONSE"
                })
                continue

            # Save the raw response in debug data
            debug_data["batch_responses"].append({
                "batch_index": batch_index + 1,
                "raw_response": response
            })

            # ✅ Parsing the JSON response using the robust function
            match_results = parse_llm_response(response)

            if isinstance(match_results, list):
                for trial, match_result in zip(batch, match_results):
                    matched_trials.append({
                        "trial_id": trial.get("id"),
                        "title": trial.get("title", "Unknown Trial"),
                        "description": trial.get("description", "No description provided."),
                        "match_score": match_result.get("match_score", 0),
                        "recommendation": match_result.get("overall_recommendation", "UNKNOWN"),
                        "criteria_analysis": match_result.get("criteria_analysis"),
                        "summary": match_result.get("summary", "No summary available.")
                    })
            else:
                logger.error(f"❌ Invalid JSON structure for Batch {batch_index + 1}")

        except Exception as e:
            logger.error(f"❌ Error in LLM matching for batch {batch_index + 1}: {str(e)}")
            debug_data["batch_responses"].append({
                "batch_index": batch_index + 1,
                "error": str(e)
            })

    # Save the full debug data to the debug file
    with open(debug_filename, "w") as f:
        json.dump(debug_data, f, indent=2)
    logger.info(f"💾 Saved LLM trial matching debug output to {debug_filename}")
    print(f"💾 Saved LLM trial matching debug output to {debug_filename}")

    # ✅ Sort matched trials by Match Score (High to Low)
    matched_trials.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    logger.info(f"✅ Trial matching completed. {len(matched_trials)} trials matched.")

    # Save matched trials for further review
    matched_trials_filename = f"logs/matched_trials_{int(time.time())}.json"
    with open(matched_trials_filename, "w") as f:
        json.dump(matched_trials, f, indent=2)
    logger.info(f"💾 Matched trials saved to {matched_trials_filename}")

    return matched_trials



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
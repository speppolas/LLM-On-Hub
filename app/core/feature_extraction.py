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
def normalize_llm_features(features: dict) -> dict:
    LIST_FIELDS = [
        "biomarkers",
        "prior_systemic_therapies",
        "comorbidities",
        "concomitant_treatments",
        "brain_metastasis"
    ]

    for field in LIST_FIELDS:
        if field in features:
            value = features[field]

            # Empty list → epistemic unknown
            if isinstance(value, list) and len(value) == 0:
                features[field] = ["not mentioned"]

    return features



def normalize_prior_vs_concomitant(patient: dict) -> dict:
    prior = set(patient.get("prior_systemic_therapies", []))
    concomitant = set(patient.get("concomitant_treatments", []))

    # Se un farmaco è concomitante, NON può essere prior
    cleaned_prior = [
        x for x in prior
        if x not in concomitant and x != "not mentioned"
    ]

    if not cleaned_prior:
        patient["prior_systemic_therapies"] = ["not mentioned"]
    else:
        patient["prior_systemic_therapies"] = cleaned_prior

    return patient
def extract_first_json_object(text: str) -> dict:
    """
    Extracts the first valid JSON object from a string.
    Robust to markdown, explanations, code fences.
    """
    import json

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object start found")

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i+1]
                return json.loads(candidate)

    raise ValueError("No complete JSON object found")

def extract_features_with_llm(text: str) -> Dict[str, Any]:
    from app.core.llm_processor import get_llm_processor
    llm = get_llm_processor()
    prompt = f"""
Sei un modello NLP per l’estrazione strutturata di dati clinici sul carcinoma polmonare.

Data la seguente cartella clinica STRUTTURATA usando l’estrazione BASATA SU SEZIONI:

Testo:
{text}

Restituisci UNO e SOLO UNO oggetto JSON che rispetti ESATTAMENTE lo schema e le regole seguenti.
- Output: SOLO l’oggetto JSON. Nessun testo prima/dopo. Nessun markdown. Nessun commento. Nessun code fence.
- Se un valore non è ricavabile dal testo, scrivi esattamente "not mentioned" (per TUTTI i campi, inclusi i numerici).
- Quando sono richieste liste, restituisci un array JSON. Se non è menzionato nulla, restituisci ["not mentioned"].
- Normalizza i nomi in inglese quando possibile (es. carboplatino → carboplatin; linfonodali → lymph nodes).

========================
SCHEMA JSON (OBBLIGATORIO)
========================

{{
  "age": "int | not mentioned",

  "gender": "male | female | not mentioned",

  "ecog_ps": "0 | 1 | 2 | not mentioned",

  "histology": "squamous | adenocarcinoma | small_cell | not mentioned",

  "current_stage": "II | III | IV | not mentioned",

  "line_of_therapy": "1L | 2L | >=3L | adjuvant | neoadjuvant | maintenance | not mentioned",

  "pd_l1_tps": "0% | <1% | 1-49% | >=50% | not mentioned",

  "biomarkers": ["KRAS_G12C", "KRAS_Q61H", "EGFR_exon19_del", "EGFR_L858R", "EGFR_T790M", "EGFR_L861Q", "EGFR_P772R", "ALK rearrangement", "ALK", "ROS1", "RET", "NTRK", "MET_amplification", "MET_exon14", "HER2_exon20", "BRAF_V600E", "STK11", "TP53", "DNMT3A"] | ["not mentioned"],

  "brain_metastasis": ["true | false"],

  "brain_metastasis_status": "none | treated_stable | active_symptomatic | not mentioned",

  "prior_systemic_therapies": ["osimertinib", "erlotinib", "gefitinib", "alectinib", "lorlatinib", "amivantamab", "carboplatin", "cisplatin", "pemetrexed", "etoposide", "vinorelbine", "gemcitabine", "topotecan", "pembrolizumab", "nivolumab", "atezolizumab", "durvalumab", "cemiplimab", "bevacizumab"] | ["not mentioned"],

  "comorbidities": ["hypertension", "immunodeficiency", "inflammatory bowel disease", "autoimmune disease", "active infection", "ILD", "pneumonitis", "COPD", "type 2 diabetes", "myocardial infarction", "transient ischemic attack", "obstructive sleep apnea", "benign prostatic hyperplasia", "dyslipidemia", "asthma", "hypothyroidism", "gastritis", "hepatic steatosis", "nasal polyposis", "extrasystole", "osteoporosis", "rheumatoid arthritis", "vulvar lichen", "previous Hodgkin lymphoma", "previous thyroid cancer", "previous testicular seminoma", "previous breast cancer", "previous colon cancer", "previous melanoma"] | ["not mentioned"],

  "concomitant_treatments": ["radiotherapy (brain)", "radiotherapy (bone)", "radiotherapy (lung)", "radiotherapy (liver)", "radiotherapy (adjuvant)", "radiotherapy (panencephalic)", "radiotherapy (stereotactic)", "chemoradiotherapy", "RTCT", "surgery", "neurosurgery"] | ["not mentioned"]
}}

========================
REGOLE CLINICHE CHIAVE
========================

HISTOLOGY
- Se trovi SCLC → "small_cell"
- current_stage = "IV" se metastasi a distanza sono MAI menzionate.

LINE_OF_THERAPY
• Se il testo indica candidabilità, pianificazione o avvio di prima linea → "1L"
- Se non chiaramente indicata → "not mentioned".

PD-L1
- Estrarre SEMPRE se presente nel testo, anche se EGFR/ALK positivi.
- Mappare solo nei bucket consentiti: "0%" | "<1%" | "1-49%" | ">=50%"
-  quidni se trovi PD-L1: 70% -> ">=50%"

BIOMARKERS
- Usa SOLO i valori consentiti.
- Cerca preferibilmente in “Diagnosi”, “Istologia”, “Biologia Molecolare”.

BRAIN METASTASIS
- brain_metastasis=["true"] SOLO se il testo menziona esplicitamente
  metastasi cerebrali / CNS metastases.
- brain_metastasis_status:
   • se brain_metastasis=["false"] → brain_metastasis_status MUST be "none"
  • "treated_stable" SOLO se è esplicitamente indicato trattamento locale
    già completato (RT o chirurgia) e assenza di sintomi/progressione.
  • "active_symptomatic" SOLO se sono esplicitamente menzionati
    sintomi neurologici, progressione o necessità di steroidi.
  • In assenza di indicazioni chiare → "false".

PRIOR_SYSTEMIC_THERAPIES
- Includi SOLO terapie sistemiche GIÀ SOMMINISTRATE.
- Considera come somministrate frasi come:
  "in trattamento con", "ha ricevuto", "precedentemente trattata con",
  "dopo fallimento di", "in progressione dopo".
- Escludi terapie pianificate, proposte o da iniziare.
- Chirurgia e radioterapia NON sono terapie sistemiche.
  Esempi:
    • "la paziente è candidata a carboplatino + etoposide + atezolizumab"
      → ["not mentioned"]
    • "avvio del trattamento (primo ciclo senza immunoterapia)"
      → ["not mentioned"]  
    • "ha già ricevuto 2 cicli di carboplatino + etoposide"
      → ["carboplatin","etoposide"]


COMORBIDITIES
- guarda attentamente la sezione "COMORBIDITÀ" nella sottosezione "Oncologiche:". 
COMORBIDITIES (STRICT)
- Inserisci una comorbidità SOLO se è esplicitamente dichiarata nel testo (diagnosi, anamnesi, comorbidità, terapia cronica specifica).
- NON inferire mai comorbidità da età, fumo, farmaci generici, sintomi, esami o fattori di rischio.
  Esempi di inferenza VIETATA:
  • “fuma” ≠ COPD
  • “dispnea” ≠ asthma/COPD
  • “statina” ≠ dyslipidemia (a meno che non sia scritto)
  • “metformina” ≠ type 2 diabetes (a meno che non sia scritto)
  • “steroidi” ≠ autoimmune disease/immunodeficiency (a meno che non sia scritto)
- Se il testo dice solo “negativo per” o “assenza di”, NON inserire la comorbidità.
- Se non trovi una sezione comorbidità/anamnesi, restituisci ["not mentioned"] (non riempire con ipotesi).
- Usa SOLO i valori consentiti. Se la condizione è menzionata ma non è nella lista consentita, NON aggiungerla e NON sostituirla con un valore simile.


CONCOMITANT_TREATMENTS
- Includi SOLO trattamenti oncologici LOCALI (RT, chirurgia, chemioradioterapia).
- Escludi sempre farmaci sistemici.


========================
FINAL INSTRUCTION
========================
Restituisci ORA SOLO l’oggetto JSON.
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
        llm_text = extract_first_json_object(llm_text_str)
        llm_text = normalize_llm_features(llm_text)
        llm_text = normalize_prior_vs_concomitant(llm_text)

        
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
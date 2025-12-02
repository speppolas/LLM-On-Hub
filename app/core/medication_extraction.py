# import os
# import json
# import time
# import logging
# from typing import Union
# from app import logger
# from app.core.llm_processor import get_llm_processor
# from app.core.feature_extraction import extract_text_from_pdf
# from app.core.transform_medications_data import normalize_medication_entry, extract_comorbidity  #vale norm
# import pandas as pd

# # Ensure the logs folder exists
# os.makedirs("logs", exist_ok=True)

# def extract_medications_from_pdf(pdf_file: Union[str, bytes]):
#     try:
#         text = extract_text_from_pdf(pdf_file)
#         return extract_medications(text)
#     except Exception as e:
#         logger.error(f"❌ Error reading PDF for medication extraction: {str(e)}")
#         return {}
    
# #valentina csv sequenziale 
# def extract_medications_from_csv(csv_file: Union[str, bytes]):
#     try:
#         data = {}
#         df = pd.read_csv(csv_file)
#         for index, row in df.iterrows():
#             data[row['id']] = extract_medications(row['report'])
#         return data
#     except Exception as e:
#         logger.error(f"❌ Error reading CSV for medication extraction: {str(e)}")
#         return {}
# # from concurrent.futures import ThreadPoolExecutor, as_completed
# # #vale parallela
# # def extract_medications_from_csv(csv_file: Union[str, bytes]):
# #     try:
# #         df = pd.read_csv(csv_file)
# #         data = {}

# #         with ThreadPoolExecutor(max_workers=4) as executor:
# #             futures = {
# #                 executor.submit(extract_medications, row['report']): row['id']
# #                 for _, row in df.iterrows()
# #                 if pd.notna(row['report']) and pd.notna(row['id'])
# #             }

# #             for future in as_completed(futures):
# #                 row_id = futures[future]
# #                 try:
# #                     data[row_id] = future.result()
# #                 except Exception as e:
# #                     logger.error(f"❌ Failed to extract medications for ID {row_id}: {str(e)}")
# #                     data[row_id] = {}

# #         return data

# #     except Exception as e:
# #         logger.error(f"❌ Error reading CSV for medication extraction: {str(e)}")
# #         return {}



# # vale esx seq
# def extract_medications_from_excel(excel_file: Union[str, bytes]):
#     try:
#         data = {}
#         df = pd.read_excel(excel_file, engine='openpyxl')
#         for index, row in df.iterrows():
#             data[row['id']] = extract_medications(row['report'])
#         return data
#     except Exception as e:
#         logger.error(f"❌ Error reading PDF for medication extraction: {str(e)}")
#         return {}

# # from concurrent.futures import ThreadPoolExecutor, as_completed
# #vale esx par
# # def extract_medications_from_excel(excel_file: Union[str, bytes]):
# #     try:
# #         df = pd.read_excel(excel_file, engine='openpyxl')
# #         data = {}
# #         print(df)
# #         with ThreadPoolExecutor(max_workers=4) as executor:
# #             futures = {
# #                 executor.submit(extract_medications, row['report']): row['id']
# #                 for _, row in df.iterrows()
# #                 if pd.notna(row['report']) and pd.notna(row['id'])
# #             }

# #             for future in as_completed(futures):
# #                 row_id = futures[future]
# #                 try:
# #                     data[row_id] = future.result()
# #                 except Exception as e:
# #                     logger.error(f"❌ Failed to extract medications for ID {row_id}: {str(e)}")
# #                     data[row_id] = {}

# #         return data

# #     except Exception as e:
# #         print(f"❌ Error reading Excel for medication extraction: {str(e)}")
# #         logger.error(f"❌ Error reading Excel for medication extraction: {str(e)}")
# #         return {}

# def extract_medications(text: str):
#     llm = get_llm_processor()
#     prompt = f"""
# You are a medical assistant. Carefully analyze the following clinical text and extract **all** mentioned **medications**, including anticancer therapies and any supportive or comorbidity-related treatments.

# Rules for "mutation":
# - If the text mentions a mutation, write it exactly if it is one of: G719A,G719S,G719D,G719C,G719X,E709K,E709A,L718Q,S768I,T790M,C797S,G724S,R776H,L858R,L861Q,L861R,T854A,G154V,T1010I,EXON 19 DEL,EXON 20 INS,L792X,L718X.
# - If the mutation is written differently (e.g., E746-A750del, delezione dell' esone 19, Glu746_Ala750del, etc.), normalize to the correct form from the list.
# - If the mutation is clearly present but not in the list, write 'altre mutazioni'.
# - Never leave the field empty.

# Rules for "exon":
# - If the text explicitly mentions an exon (esone/exon/ex.) with a number, extract it (e.g., 'esone 19'); otherwise write 'n/a'.

# Rules for "modality":
# - If the text explicitly mentions a route of administration such as "orale", "per bocca", "po" "endovenosa", "sottocutanea", etc., extract it.
# - Do NOT infer modality from contextual hints like "a stomaco pieno", "a digiuno",  or similar wording. 
# - If the explicit route is not mentioned, write "n/a".

# Return your answer strictly in JSON format, following this structure:

# {{
#   "medications": [
#     {{
#       "medication": "name only",
#       "dosage": "e.g., 250 mg",
#       "frequency": "e.g., 1 cp/die",
#       "period": "e.g., 21 cicli",
#       "mutation": "e.g., L858R",
#       "exon": "e.g., esone 19",
#       "modality": "e.g., orale, endovenosa",
#       "collateral effects": "if any side effect is mentioned, e.g., skin rash"
#     }}
#   ],
#   "comorbidity": "list any comorbidities found, e.g., hypertension, diabetes, tabagism"
# }}

# Only return the final JSON object without any explanation or extra text.

# Text:
# {text}
# """
#     logger.info(f"Prompt sent to LLM (medication):\n{prompt[:2000]}")

#     try:
#         response = llm.generate_response(prompt)
#         logger.info(f"🧠 LLM Medication Response: {response[:1000]}")

#         filename = f"logs/llm_medication_debug_{int(time.time())}.json"
#         with open(filename, "w") as f:
#             json.dump({"prompt": prompt, "response": response}, f, indent=2)

#         resp_json = json.loads(response)
#         llm_text = json.loads(resp_json['response']) if isinstance(resp_json['response'], str) else resp_json['response']
        

# #norm vale
#         if not isinstance(llm_text, dict):
#             logger.error(f"❌ LLM medication output is not a list: {llm_text}")
#             return {'medications':[], 'comorbidity':''}
        
        
#     #     logger.info(f"✅ Extracted Medication Features: {json.dumps(llm_text, indent=2)}")
#     #     return llm_text

#     # except Exception as e:
#     #     logger.exception("❌ Medication LLM parsing failed")
#     #     return []
#     #da vale norm
#         medications = llm_text.get("medications", [])

#         # 🔁 Applica la normalizzazione a ogni farmaco
#         normalized_meds = [
#             normalize_medication_entry(med) for med in medications if isinstance(med, dict)
#         ]

#         # 📍 Se il campo comorbidity non è presente, lo estraiamo direttamente
#         comorbidity = llm_text.get("comorbidity")
#         if not comorbidity or comorbidity == "n/a":
#             comorbidity = extract_comorbidity(text)

#         result = {
#             "medications": normalized_meds,
#             "comorbidity": comorbidity
#         }

#         logger.info(f"✅ Normalized Medication Features: {json.dumps(result, indent=2)}")
#         return result

#     except Exception as e:
#         logger.exception("❌ Medication LLM parsing failed")
#         return {"medications": [], "comorbidity": extract_comorbidity(text)}

# #a vale norm




## EXTRACTION 2
# import os
# import json
# import time
# import logging
# from typing import Union, Any, Dict
# from app import logger
# from app.core.llm_processor import get_llm_processor
# from app.core.feature_extraction import extract_text_from_pdf
# from app.core.transform_medications_data import normalize_medication_entry, extract_comorbidity  # vale norm
# import pandas as pd

# # Ensure the logs folder exists
# os.makedirs("logs", exist_ok=True)

# # -----------------------
# # JSON parsing helpers
# # -----------------------

# def _safe_json_extract_block(s: str) -> str:
#     """
#     Try to extract the FIRST well-formed JSON object from a raw string.
#     - Finds first '{' and last '}' and returns that slice if consistent.
#     - If it fails, returns the original string.
#     """
#     if not isinstance(s, str):
#         return s
#     start = s.find("{")
#     end = s.rfind("}")
#     if start != -1 and end != -1 and end > start:
#         return s[start:end + 1]
#     return s

# def _coerce_to_json_dict(raw: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
#     """
#     Handles common LLM response shapes:
#     1) raw is already a JSON object -> dict
#     2) raw is a JSON with wrapper {"response": "<JSON_STRING>"} -> unwrap recursively
#     3) raw contains prose + JSON -> isolate the first JSON block and parse it
#     Returns {} if nothing can be parsed into a dict.
#     """
#     # Case: already dict-like (from some backends)
#     if isinstance(raw, dict):
#         # unwrap one level if needed
#         inner = raw.get("response")
#         if isinstance(inner, str):
#             inner_block = _safe_json_extract_block(inner)
#             try:
#                 obj = json.loads(inner_block)
#                 return obj if isinstance(obj, dict) else {}
#             except Exception:
#                 return raw
#         return raw

#     # Case: string — try direct parse
#     if isinstance(raw, str):
#         try:
#             obj = json.loads(raw)
#             if isinstance(obj, dict) and "response" in obj and isinstance(obj["response"], str):
#                 inner = obj["response"].strip()
#                 inner_block = _safe_json_extract_block(inner)
#                 try:
#                     inner_obj = json.loads(inner_block)
#                     return inner_obj if isinstance(inner_obj, dict) else obj
#                 except Exception:
#                     return obj
#             return obj if isinstance(obj, dict) else {}
#         except Exception:
#             pass

#         # Scavenger: try to extract JSON block from prose
#         block = _safe_json_extract_block(raw)
#         try:
#             obj = json.loads(block)
#             return obj if isinstance(obj, dict) else {}
#         except Exception:
#             return {}

#     # Fallback
#     return {}

# # -----------------------
# # Optional post-parse merge
# # -----------------------

# def _merge_meds_by_name(rows):
#     """
#     Merge rows with the same medication name (case-insensitive),
#     preferring non-'n/a' values for each field.
#     """
#     by = {}
#     for r in rows or []:
#         if not isinstance(r, dict):
#             continue
#         key = (r.get("medication") or "").strip().lower()
#         if not key:
#             continue
#         if key not in by:
#             by[key] = r
#         else:
#             for k in ["dosage", "frequency", "period", "mutation", "exon", "modality", "collateral effects"]:
#                 if (by[key].get(k) in (None, "", "n/a")) and (r.get(k) not in (None, "", "n/a")):
#                     by[key][k] = r[k]
#     return list(by.values())

# # -----------------------
# # PDF / CSV / XLSX entrypoints
# # -----------------------

# def extract_medications_from_pdf(pdf_file: Union[str, bytes]):
#     try:
#         text = extract_text_from_pdf(pdf_file)
#         return extract_medications(text)
#     except Exception as e:
#         logger.error(f"❌ Error reading PDF for medication extraction: {str(e)}")
#         return {}

# # valentina csv sequenziale
# def extract_medications_from_csv(csv_file: Union[str, bytes]):
#     try:
#         data = {}
#         df = pd.read_csv(csv_file)
#         for index, row in df.iterrows():
#             data[row['id']] = extract_medications(row['report'])
#         return data
#     except Exception as e:
#         logger.error(f"❌ Error reading CSV for medication extraction: {str(e)}")
#         return {}

# # from concurrent.futures import ThreadPoolExecutor, as_completed
# # #vale parallela
# # def extract_medications_from_csv(csv_file: Union[str, bytes]):
# #     try:
# #         df = pd.read_csv(csv_file)
# #         data = {}
# #         with ThreadPoolExecutor(max_workers=4) as executor:
# #             futures = {
# #                 executor.submit(extract_medications, row['report']): row['id']
# #                 for _, row in df.iterrows()
# #                 if pd.notna(row['report']) and pd.notna(row['id'])
# #             }
# #             for future in as_completed(futures):
# #                 row_id = futures[future]
# #                 try:
# #                     data[row_id] = future.result()
# #                 except Exception as e:
# #                     logger.error(f"❌ Failed to extract medications for ID {row_id}: {str(e)}")
# #                     data[row_id] = {}
# #         return data
# #     except Exception as e:
# #         logger.error(f"❌ Error reading CSV for medication extraction: {str(e)}")
# #         return {}

# # vale esx seq
# def extract_medications_from_excel(excel_file: Union[str, bytes]):
#     try:
#         data = {}
#         df = pd.read_excel(excel_file, engine='openpyxl')
#         for index, row in df.iterrows():
#             data[row['id']] = extract_medications(row['report'])
#         return data
#     except Exception as e:
#         logger.error(f"❌ Error reading PDF for medication extraction: {str(e)}")
#         return {}

# # from concurrent.futures import ThreadPoolExecutor, as_completed
# # vale esx par
# # def extract_medications_from_excel(excel_file: Union[str, bytes]):
# #     try:
# #         df = pd.read_excel(excel_file, engine='openpyxl')
# #         data = {}
# #         print(df)
# #         with ThreadPoolExecutor(max_workers=4) as executor:
# #             futures = {
# #                 executor.submit(extract_medications, row['report']): row['id']
# #                 for _, row in df.iterrows()
# #                 if pd.notna(row['report']) and pd.notna(row['id'])
# #             }
# #             for future in as_completed(futures):
# #                 row_id = futures[future]
# #                 try:
# #                     data[row_id] = future.result()
# #                 except Exception as e:
# #                     logger.error(f"❌ Failed to extract medications for ID {row_id}: {str(e)}")
# #                     data[row_id] = {}
# #         return data
# #     except Exception as e:
# #         print(f"❌ Error reading Excel for medication extraction: {str(e)}")
# #         logger.error(f"❌ Error reading Excel for medication extraction: {str(e)}")
# #         return {}

# # -----------------------
# # Core extractor
# # -----------------------

# def extract_medications(text: str):
#     llm = get_llm_processor()
#     prompt = f"""
# You are a medical assistant. Carefully analyze the following clinical text and extract **all** mentioned **medications**, including anticancer therapies and any supportive or comorbidity-related treatments.

# Rules for "mutation":
# - If the text mentions a mutation, write it exactly if it is one of: G719A,G719S,G719D,G719C,G719X,E709K,E709A,L718Q,S768I,T790M,C797S,G724S,R776H,L858R,L861Q,L861R,T854A,G154V,T1010I,EXON 19 DEL,EXON 20 INS,L792X,L718X.
# - If the mutation is written differently (e.g., E746-A750del, delezione dell' esone 19, Glu746_Ala750del, etc.), normalize to the correct form from the list.
# - If the mutation is clearly present but not in the list, write 'altre mutazioni'.
# - Never leave the field empty.

# Rules for "exon":
# - If the text explicitly mentions an exon (esone/exon/ex.) with a number, extract it (e.g., 'esone 19'); otherwise write 'n/a'.

# Rules for "modality":
# - If the text explicitly mentions a route of administration such as "orale", "per bocca", "po" "endovenosa", "sottocutanea", etc., extract it.
# - Do NOT infer modality from contextual hints like "a stomaco pieno", "a digiuno",  or similar wording. 
# - If the explicit route is not mentioned, write "n/a".

# Return your answer strictly in JSON format, following this structure:

# {{
#   "medications": [
#     {{
#       "medication": "name only",
#       "dosage": "e.g., 250 mg",
#       "frequency": "e.g., 1 cp/die",
#       "period": "e.g., 21 cicli",
#       "mutation": "e.g., L858R",
#       "exon": "e.g., esone 19",
#       "modality": "e.g., orale, endovenosa",
#       "collateral effects": "if any side effect is mentioned, e.g., skin rash"
#     }}
#   ],
#   "comorbidity": "list any comorbidities found, e.g., hypertension, diabetes, tabagism"
# }}

# Only return the final JSON object without any explanation or extra text.

# Text:
# {text}
# """
#     logger.info(f"Prompt sent to LLM (medication):\n{prompt[:2000]}")

#     try:
#         response = llm.generate_response(prompt)
#         # Persist raw exchange for debugging
#         filename = f"logs/llm_medication_debug_{int(time.time())}.json"
#         try:
#             with open(filename, "w") as f:
#                 json.dump({"prompt": prompt, "response": response}, f, indent=2)
#         except Exception:
#             pass

#         # -----------------------
#         # Robust JSON parsing
#         # -----------------------
#         # Some backends return a dict; others return a JSON string with wrapper {"response": "...json..."}
#         raw_str = response if isinstance(response, str) else json.dumps(response)
#         llm_obj = _coerce_to_json_dict(raw_str)

#         # Tolerant access to "medications" array (accepts common variants)
#         meds = (llm_obj.get("medications")
#                 or llm_obj.get("meds")
#                 or llm_obj.get("drugs")
#                 or [])
#         meds = meds if isinstance(meds, list) else []

#         normalized_meds = []
#         for m in meds:
#             if not isinstance(m, dict):
#                 continue

#             # Key aliasing (no regex here)
#             key_map = {
#                 "medication": ["medication", "drug", "farmaco", "name"],
#                 "dosage": ["dosage", "dose", "posologia"],
#                 "frequency": ["frequency", "freq", "frequenza"],
#                 "period": ["period", "durata", "cicli"],
#                 "mutation": ["mutation", "mutazione"],
#                 "exon": ["exon", "esone", "exone"],  # accept typo "exone"
#                 "modality": ["modality", "route", "via", "somministrazione"],
#                 "collateral effects": ["collateral effects", "side effects", "eventi avversi", "ae"]
#             }

#             def pick(d, keys, default="n/a"):
#                 for k in keys:
#                     if k in d and d[k] not in (None, ""):
#                         return d[k]
#                 return default

#             item = {
#                 "medication": pick(m, key_map["medication"], "n/a"),
#                 "dosage": pick(m, key_map["dosage"], "n/a"),
#                 "frequency": pick(m, key_map["frequency"], "n/a"),
#                 "period": pick(m, key_map["period"], "n/a"),
#                 "mutation": pick(m, key_map["mutation"], "n/a"),
#                 "exon": pick(m, key_map["exon"], "n/a"),
#                 "modality": pick(m, key_map["modality"], "n/a"),
#                 "collateral effects": pick(m, key_map["collateral effects"], "n/a"),
#             }

#             # Light cleanups (no regex; deep normalization stays in transform_medications_data)
#             # 1) modality: drop notes in parentheses; whitelist plausible values
#             if isinstance(item["modality"], str):
#                 item["modality"] = item["modality"].split("(")[0].strip().lower()
#                 if item["modality"] not in {"orale", "endovenosa", "sottocutanea", "intramuscolare", "n/a"}:
#                     item["modality"] = "n/a"

#             # 2) exon: unify label spelling
#             if isinstance(item["exon"], str):
#                 item["exon"] = (
#                     item["exon"]
#                     .replace("Exon", "esone")
#                     .replace("EXON", "esone")
#                     .replace("Esone", "esone")
#                     .strip()
#                 )

#             # 3) mutation: try to keep only the salient token if present
#             if isinstance(item["mutation"], str):
#                 mut = item["mutation"]
#                 for token in ["L858R", "L861Q", "T790M", "EXON 19 DEL", "EXON 20 INS", "G719X", "S768I", "C797S", "L718Q"]:
#                     if token.lower() in mut.lower():
#                         item["mutation"] = token
#                         break

#             # 4) dosage/frequency: if dosage clearly contains frequency, duplicate into frequency when missing
#             if isinstance(item["dosage"], str) and item["frequency"] == "n/a":
#                 low = item["dosage"].lower()
#                 hints = [" cp/die", "/die", " x", " die", " al giorno", " qd", " bid", " tid", " qid"]
#                 if any(h in low for h in hints):
#                     item["frequency"] = low

#             # 5) empty strings -> "n/a"
#             for k, v in list(item.items()):
#                 if isinstance(v, str) and not v.strip():
#                     item[k] = "n/a"

#             # Use your downstream normalization (already present)
#             item = normalize_medication_entry(item)
#             normalized_meds.append(item)

#         # Merge duplicates by medication name
#         normalized_meds = _merge_meds_by_name(normalized_meds)

#         # Comorbidity: keep your fallback if missing/n/a
#         comorbidity = llm_obj.get("comorbidity")
#         if not comorbidity or comorbidity == "n/a":
#             comorbidity = extract_comorbidity(text)

#         result = {
#             "medications": normalized_meds,
#             "comorbidity": comorbidity
#         }

#         logger.info(f"✅ Normalized Medication Features: {json.dumps(result, indent=2)}")
#         return result

#     except Exception as e:
#         logger.exception("❌ Medication LLM parsing failed")
#         return {"medications": [], "comorbidity": extract_comorbidity(text)}









## EXTRACTION 3
import os
import json
import time
import logging
from typing import Union, Any, Dict, List
from app import logger
from app.core.llm_processor import get_llm_processor
from app.core.feature_extraction import extract_text_from_pdf
from app.core.transform_medications_data import normalize_medication_entry, extract_comorbidity  # vale norm
import pandas as pd
import re

# Ensure the logs folder exists
os.makedirs("logs", exist_ok=True)

# -----------------------
# JSON parsing helpers
# -----------------------

def _safe_json_extract_block(s: str) -> str:
    """
    Try to extract the FIRST well-formed JSON object from a raw string.
    - Finds first '{' and last '}' and returns that slice if consistent.
    - If it fails, returns the original string.
    """
    if not isinstance(s, str):
        return s
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start:end + 1]
    return s

def _coerce_to_json_dict(raw: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Handles common LLM response shapes:
    1) raw is already a JSON object -> dict
    2) raw is a JSON with wrapper {"response": "<JSON_STRING>"} -> unwrap recursively
    3) raw contains prose + JSON -> isolate the first JSON block and parse it
    Returns {} if nothing can be parsed into a dict.
    """
    # Case: already dict-like (from some backends)
    if isinstance(raw, dict):
        # unwrap one level if needed
        inner = raw.get("response")
        if isinstance(inner, str):
            inner_block = _safe_json_extract_block(inner)
            try:
                obj = json.loads(inner_block)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return raw
        return raw

    # Case: string — try direct parse
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "response" in obj and isinstance(obj["response"], str):
                inner = obj["response"].strip()
                inner_block = _safe_json_extract_block(inner)
                try:
                    inner_obj = json.loads(inner_block)
                    return inner_obj if isinstance(inner_obj, dict) else obj
                except Exception:
                    return obj
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass

        # Scavenger: try to extract JSON block from prose
        block = _safe_json_extract_block(raw)
        try:
            obj = json.loads(block)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    # Fallback
    return {}

# -----------------------
# Optional post-parse merge
# -----------------------

def _merge_meds_by_name(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge rows with the same medication name (case-insensitive),
    preferring non-'n/a' values for each field.
    """
    by = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        key = (r.get("medication") or "").strip().lower()
        if not key:
            continue
        if key not in by:
            by[key] = r
        else:
            for k in ["dosage", "frequency", "period", "mutation", "exon", "modality", "collateral effects"]:
                if (by[key].get(k) in (None, "", "n/a")) and (r.get(k) not in (None, "", "n/a")):
                    by[key][k] = r[k]
    return list(by.values())

# -----------------------
# Modality acceptance (STRICT)
# -----------------------

# Conservativa: accettiamo SOLO se troviamo chiaramente uno di questi token espliciti.
# La normalizzazione fine (es. mappare "po" -> "orale") resta a normalize_medication_entry.
_ALLOWED_MODALITY_KEYWORDS = [
    r"\borale\b", r"\bper\s*bocca\b", r"\bper\s*os\b", r"\bp\.?o\.?\b", r"\bos\b",
    r"\bendovenosa\b", r"\bev\b", r"\biv\b",
    r"\bsottocutanea\b", r"\bsc\b",
    r"\bintramuscolare\b", r"\bim\b",
    r"\bsublinguale\b", r"\btopica\b", r"\btransdermica\b",
    r"\binalatoria\b", r"\baerosol\b", r"\binhalatoria\b"
]
_ALLOWED_MODALITY_RE = re.compile("|".join(_ALLOWED_MODALITY_KEYWORDS), flags=re.IGNORECASE)

def _accept_or_null_modality(value: Any) -> str:
    """
    Keep modality ONLY if an explicit keyword is present.
    Otherwise return 'n/a'. Do not 'guess' from context.
    """
    if not isinstance(value, str):
        return "n/a"
    raw = value.strip()
    if not raw:
        return "n/a"
    # drop trailing notes in parentheses to avoid false positives like "(assumere a digiuno)"
    raw_head = raw.split("(", 1)[0].strip()
    if _ALLOWED_MODALITY_RE.search(raw_head or ""):
        return raw_head.lower()
    return "n/a"

# -----------------------
# PDF / CSV / XLSX entrypoints
# -----------------------

def extract_medications_from_pdf(pdf_file: Union[str, bytes]):
    try:
        text = extract_text_from_pdf(pdf_file)
        return extract_medications(text)
    except Exception as e:
        logger.error(f"❌ Error reading PDF for medication extraction: {str(e)}")
        return {}

# valentina csv sequenziale 
def extract_medications_from_csv(csv_file: Union[str, bytes]):
    try:
        data = {}
        df = pd.read_csv(csv_file)
        for index, row in df.iterrows():
            data[row['id']] = extract_medications(row['report'])
        return data
    except Exception as e:
        logger.error(f"❌ Error reading CSV for medication extraction: {str(e)}")
        return {}

# vale esx seq
def extract_medications_from_excel(excel_file: Union[str, bytes]):
    try:
        data = {}
        df = pd.read_excel(excel_file, engine='openpyxl')
        for index, row in df.iterrows():
            data[row['id']] = extract_medications(row['report'])
        return data
    except Exception as e:
        logger.error(f"❌ Error reading PDF for medication extraction: {str(e)}")
        return {}

# -----------------------
# Core extractor
# -----------------------

def extract_medications(text: str):
    llm = get_llm_processor()
    prompt = f"""
You are a medical assistant. Carefully analyze the following clinical text and extract **all** mentioned **medications**, including anticancer therapies and any supportive or comorbidity-related treatments.

Rules for "mutation":
- If the text mentions a mutation, write it exactly if it is one of: G719A,G719S,G719D,G719C,G719X,E709K,E709A,L718Q,S768I,T790M,C797S,G724S,R776H,L858R,L861Q,L861R,T854A,G154V,T1010I,EXON 19 DEL,EXON 20 INS,L792X,L718X.
- If the mutation is written differently (e.g., E746-A750del, delezione dell' esone 19, Glu746_Ala750del, etc.), normalize to the correct form from the list.
- If the mutation is clearly present but not in the list, write 'altre mutazioni'.
- Never leave the field empty.

Rules for "exon":
- If the text explicitly mentions an exon (esone/exon/ex.) with a number, extract it (e.g., 'esone 19'); otherwise write 'n/a'.

Rules for "modality":
- If the text explicitly mentions a route of administration such as "orale", "per bocca", "po" "endovenosa", "sottocutanea", etc., extract it.
- Do NOT infer modality from contextual hints like "a stomaco pieno", "a digiuno",  or similar wording. 
- If the explicit route is not mentioned, write "n/a".

Return your answer strictly in JSON format, following this structure:

{{
  "medications": [
    {{
      "medication": "name only",
      "dosage": "e.g., 250 mg",
      "frequency": "e.g., 1 cp/die",
      "period": "e.g., 21 cicli",
      "mutation": "e.g., L858R",
      "exon": "e.g., esone 19",
      "modality": "e.g., orale, endovenosa",
      "collateral effects": "if any side effect is mentioned, e.g., skin rash"
    }}
  ],
  "comorbidity": "list any comorbidities found, e.g., hypertension, diabetes, tabagism"
}}

Only return the final JSON object without any explanation or extra text.

Text:
{text}
"""
    logger.info(f"Prompt sent to LLM (medication):\n{prompt[:2000]}")

    try:
        response = llm.generate_response(prompt)
        # Persist raw exchange for debugging
        filename = f"logs/llm_medication_debug_{int(time.time())}.json"
        try:
            with open(filename, "w") as f:
                json.dump({"prompt": prompt, "response": response}, f, indent=2)
        except Exception:
            pass

        # -----------------------
        # Robust JSON parsing
        # -----------------------
        # Some backends return a dict; others return a JSON string with wrapper {"response": "...json..."}
        raw_str = response if isinstance(response, str) else json.dumps(response)
        llm_obj = _coerce_to_json_dict(raw_str)

        # Tolerant access to "medications" array (accepts common variants)
        meds = (llm_obj.get("medications")
                or llm_obj.get("meds")
                or llm_obj.get("drugs")
                or [])
        meds = meds if isinstance(meds, list) else []

        normalized_meds = []
        for m in meds:
            if not isinstance(m, dict):
                continue

            # Key aliasing (no regex here)
            key_map = {
                "medication": ["medication", "drug", "farmaco", "name"],
                "dosage": ["dosage", "dose", "posologia"],
                "frequency": ["frequency", "freq", "frequenza"],
                "period": ["period", "durata", "cicli"],
                "mutation": ["mutation", "mutazione"],
                "exon": ["exon", "esone", "exone"],  # accept typo "exone"
                "modality": ["modality", "route", "via", "somministrazione"],
                "collateral effects": ["collateral effects", "side effects", "eventi avversi", "ae"]
            }

            def pick(d, keys, default="n/a"):
                for k in keys:
                    if k in d and d[k] not in (None, ""):
                        return d[k]
                return default

            item = {
                "medication": pick(m, key_map["medication"], "n/a"),
                "dosage": pick(m, key_map["dosage"], "n/a"),
                "frequency": pick(m, key_map["frequency"], "n/a"),
                "period": pick(m, key_map["period"], "n/a"),
                "mutation": pick(m, key_map["mutation"], "n/a"),
                "exon": pick(m, key_map["exon"], "n/a"),
                "modality": pick(m, key_map["modality"], "n/a"),
                "collateral effects": pick(m, key_map["collateral effects"], "n/a"),
            }

            # -----------------------
            # STRICT modality policy
            # -----------------------
            item["modality"] = _accept_or_null_modality(item["modality"])

            # 2) exon: unify label spelling (cosmetico; normalizzazione vera altrove)
            if isinstance(item["exon"], str):
                item["exon"] = (
                    item["exon"]
                    .replace("Exon", "esone")
                    .replace("EXON", "esone")
                    .replace("Esone", "esone")
                    .strip()
                )

            # 3) mutation: se l'LLM ha scritto frasi lunghe, prova a preservare solo il token noto (senza dedurre)
            if isinstance(item["mutation"], str):
                mut = item["mutation"]
                for token in ["L858R", "L861Q", "T790M", "EXON 19 DEL", "EXON 20 INS", "G719X", "S768I", "C797S", "L718Q"]:
                    if token.lower() in mut.lower():
                        item["mutation"] = token
                        break

            # 4) dosage/frequency: se la posologia contiene pattern tipici di frequenza e frequency è vuoto, duplica (non inferiamo route)
            if isinstance(item["dosage"], str) and item["frequency"] == "n/a":
                low = item["dosage"].lower()
                hints = [" cp/die", "/die", " x", " die", " al giorno", " qd", " bid", " tid", " qid"]
                if any(h in low for h in hints):
                    item["frequency"] = low

            # 5) empty strings -> "n/a"
            for k, v in list(item.items()):
                if isinstance(v, str) and not v.strip():
                    item[k] = "n/a"

            # Normalizzazione profonda demandata al tuo transformer
            item = normalize_medication_entry(item)
            normalized_meds.append(item)

        # Merge duplicates by medication name
        normalized_meds = _merge_meds_by_name(normalized_meds)

        # Comorbidity: fallback se mancante
        comorbidity = llm_obj.get("comorbidity")
        if not comorbidity or comorbidity == "n/a":
            comorbidity = extract_comorbidity(text)

        result = {
            "medications": normalized_meds,
            "comorbidity": comorbidity,
            "model": llm.model if hasattr(llm, 'model') else 'unknown'
        }

        logger.info(f"✅ Normalized Medication Features: {json.dumps(result, indent=2)}")
        return result

    except Exception as e:
        logger.exception("❌ Medication LLM parsing failed")
        return {"medications": [], "comorbidity": extract_comorbidity(text)}

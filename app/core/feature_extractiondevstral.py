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

# Create detailed console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def extract_text_from_pdf(pdf_file: Union[str, bytes]) -> str:
    """Extract text from PDF."""
    try:
        logger.info("📄 Starting PDF text extraction...")
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            logger.info(f"📄 PDF has {len(pdf.pages)} pages")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                logger.debug(f"📄 Extracted {len(page_text) if page_text else 0} chars from page {i+1}")
        
        logger.info(f"✅ PDF extraction complete: {len(text)} total characters extracted")
        return text.strip()
    except Exception as e:
        logger.error(f"❌ Error extracting text from PDF: {str(e)}")
        raise Exception(f"Unable to extract text from PDF: {str(e)}")


def parse_llm_json_response(response: Any) -> Dict[str, Any]:
    """Parse LLM response into JSON, handling wrappers, code fences, and nested JSON strings."""
    logger.debug("🔍 Attempting to parse LLM JSON response...")

    # If it's already the schema we want, return it directly
    if isinstance(response, dict):
        # Unwrap common provider envelopes
        if 'response' in response:
            logger.debug("📦 Found 'response' wrapper, unwrapping...")
            return parse_llm_json_response(response['response'])
        if 'message' in response:
            logger.debug("📦 Found 'message' wrapper, unwrapping...")
            return parse_llm_json_response(response['message'])
        if 'content' in response:
            logger.debug("📦 Found 'content' wrapper, unwrapping...")
            return parse_llm_json_response(response['content'])

        # Looks like the final schema?
        if any(k in response for k in ('age', 'histology', 'current_stage', 'ecog_ps')):
            logger.debug("✅ Detected final features schema")
            return response

    # Handle string responses
    if isinstance(response, str):
        text = response.strip()
        logger.debug(f"🔍 Response is string, length: {len(text)}")

        # 1) Try direct JSON
        try:
            loaded = json.loads(text)
            logger.debug("✅ Direct JSON parse successful; recursing to unwrap if needed")
            return parse_llm_json_response(loaded)
        except Exception as e:
            logger.debug(f"⚠️ Direct parse failed: {e}")

        # 2) Extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
        if json_match:
            inner = json_match.group(1).strip()
            try:
                loaded = json.loads(inner)
                logger.debug("✅ Extracted JSON from code fence; recursing")
                return parse_llm_json_response(loaded)
            except Exception as e:
                logger.debug(f"⚠️ Code fence JSON parse failed: {e}")

        # 3) Find the first JSON object {...}
        obj_match = re.search(r'\{(?:[^{}]|(?R))*\}', text)  # balanced-ish fallback
        if obj_match:
            try:
                loaded = json.loads(obj_match.group(0))
                logger.debug("✅ Extracted JSON object from text; recursing")
                return parse_llm_json_response(loaded)
            except Exception as e:
                logger.debug(f"⚠️ Object extraction parse failed: {e}")

    logger.error(f"❌ Could not parse response into features JSON. Preview: {str(response)[:200]}")
    return {}

def extract_features_with_llm(text: str) -> Dict[str, Any]:
    """Extract clinical features using LLM with flexible parsing."""
    logger.info("="*80)
    logger.info("🚀 STARTING FEATURE EXTRACTION WITH LLM")
    logger.info("="*80)
    
    llm = get_llm_processor()
    
    # Simplified, direct prompt
    prompt = f"""Extract clinical features from this medical record and return ONLY a JSON object.

REQUIRED JSON STRUCTURE:
{{
  "age": <number or "not mentioned">,
  "age_source_text": "<exact text about age>",
  "gender": "male" | "female" | "not mentioned",
  "gender_source_text": "<exact text about gender>",
  "ecog_ps": 0 | 1 | 2 | "not mentioned",
  "ecog_ps_source_text": "<exact text about ECOG>",
  "histology": "adenocarcinoma" | "squamous" | "small_cell" | "not mentioned",
  "histology_source_text": "<exact text about histology>",
  "current_stage": "II" | "III" | "IV" | "not mentioned",
  "current_stage_source_text": "<exact text about stage>",
  "line_of_therapy": "1L" | "2L" | ">=3L" | "not mentioned",
  "line_of_therapy_source_text": "<exact text about therapy line>",
  "pd_l1_tps": "<1%" | "1-49%" | ">=50%" | "not mentioned",
  "pd_l1_tps_source_text": "<exact text about PD-L1>",
  "biomarkers": "EGFR_L858R" | "EGFR_exon19_del" | "KRAS_G12C" | "ALK" | "not mentioned",
  "biomarkers_source_text": "<exact text about mutations>",
  "brain_metastasis": ["true"] | ["false"] | ["not mentioned"],
  "brain_metastasis_source_text": "<exact text about brain mets>",
  "prior_systemic_therapies": ["list of drugs"] | ["not mentioned"],
  "prior_systemic_therapies_source_text": "<exact text about prior therapies>",
  "comorbidities": ["list"] | ["not mentioned"],
  "comorbidities_source_text": "<exact text about comorbidities>",
  "concomitant_treatments": ["list"] | ["not mentioned"],
  "concomitant_treatments_source_text": "<exact text about current meds>"
}}

Medical Record:
{text[:4000]}

Return ONLY the JSON object, no explanations."""

    logger.info(f"📝 Prompt created, length: {len(prompt)} characters")
    logger.info(f"📝 Text snippet being analyzed: {text[:200]}...")

    try:
        logger.info("🤖 Sending request to LLM...")
        start_time = time.time()
        response = llm.generate_response(prompt)
        elapsed_time = time.time() - start_time
        logger.info(f"✅ LLM responded in {elapsed_time:.2f} seconds")
        logger.info(f"📊 Response type: {type(response)}")
        
        # Save raw extraction debug log
        extraction_debug_file = f"logs/extraction_debug_{int(time.time())}.json"
        try:
            with open(extraction_debug_file, "w", encoding="utf-8") as f:
                debug_data = {
                    "timestamp": datetime.now().isoformat(),
                    "prompt_length": len(prompt),
                    "prompt_preview": prompt[:1000],
                    "full_prompt": prompt,
                    "response_type": str(type(response)),
                    "raw_response": str(response),
                    "response_time_seconds": elapsed_time
                }
                json.dump(debug_data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"💾 Saved extraction debug log to: {extraction_debug_file}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save extraction debug log: {e}")
        
        # Parse the response
        logger.info("🔧 Parsing LLM response...")
        parsed = parse_llm_json_response(response)
        
        # Check if parsing was successful
        if parsed:
            logger.info(f"✅ Successfully parsed {len(parsed)} fields from LLM response")
            logger.info(f"📋 Extracted fields: {list(parsed.keys())[:10]}...")
        else:
            logger.warning("⚠️ Parsing returned empty dict")
        
        # If parsing failed or got wrong structure, create from scratch
        if not parsed or 'age_source_text' not in parsed:
            logger.warning("⚠️ LLM didn't follow schema, using fallback extraction...")
            parsed = extract_features_fallback(text)
            logger.info(f"🔧 Fallback extraction completed with {len(parsed)} fields")
        
        # Ensure all required fields exist
        logger.info("🔍 Validating required fields...")
        ensure_required_fields(parsed)
        logger.info("✅ All required fields validated")
        
        # Log extracted features summary
        logger.info("📊 EXTRACTED FEATURES SUMMARY:")
        logger.info(f"  - Age: {parsed.get('age')}")
        logger.info(f"  - Gender: {parsed.get('gender')}")
        logger.info(f"  - ECOG PS: {parsed.get('ecog_ps')}")
        logger.info(f"  - Histology: {parsed.get('histology')}")
        logger.info(f"  - Stage: {parsed.get('current_stage')}")
        logger.info(f"  - Line of therapy: {parsed.get('line_of_therapy')}")
        logger.info(f"  - Biomarkers: {parsed.get('biomarkers')}")
        
        logger.info("="*80)
        logger.info("✅ FEATURE EXTRACTION COMPLETE")
        logger.info("="*80)
        
        return parsed
        
    except Exception as e:
        logger.error(f"❌ Feature extraction error: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {str(e)}")
        logger.info("⚠️ Falling back to regex extraction...")
        return extract_features_fallback(text)


def extract_features_fallback(text: str) -> Dict[str, Any]:
    """Fallback extraction using regex patterns when LLM fails."""
    logger.info("🔄 Starting fallback feature extraction with regex...")
    
    features = {
        "age": "not mentioned",
        "age_source_text": "not mentioned",
        "gender": "not mentioned", 
        "gender_source_text": "not mentioned",
        "ecog_ps": "not mentioned",
        "ecog_ps_source_text": "not mentioned",
        "histology": "not mentioned",
        "histology_source_text": "not mentioned",
        "current_stage": "not mentioned",
        "current_stage_source_text": "not mentioned",
        "line_of_therapy": "not mentioned",
        "line_of_therapy_source_text": "not mentioned",
        "pd_l1_tps": "not mentioned",
        "pd_l1_tps_source_text": "not mentioned",
        "biomarkers": "not mentioned",
        "biomarkers_source_text": "not mentioned",
        "brain_metastasis": ["not mentioned"],
        "brain_metastasis_source_text": "not mentioned",
        "prior_systemic_therapies": ["not mentioned"],
        "prior_systemic_therapies_source_text": "not mentioned",
        "comorbidities": ["not mentioned"],
        "comorbidities_source_text": "not mentioned",
        "concomitant_treatments": ["not mentioned"],
        "concomitant_treatments_source_text": "not mentioned"
    }
    
    # Extract age - look for various patterns
    age_patterns = [
        r'(?:Età|età|Age|age)[:\s]*(\d+)\s*anni?',
        r'(\d+)\s*anni',
        r'(?:Età|età)[:\s]*(\d+)',
        r'Data di nascita:[^0-9]*\d+/\d+/(\d{4})'  # Calculate from birth year
    ]
    for pattern in age_patterns:
        age_match = re.search(pattern, text)
        if age_match:
            if 'nascita' in pattern and age_match:
                birth_year = int(age_match.group(1))
                features["age"] = 2025 - birth_year
                # Find the full context
                context_match = re.search(r'[^\n]*' + re.escape(age_match.group(0)) + r'[^\n]*', text)
                features["age_source_text"] = context_match.group(0) if context_match else age_match.group(0)
            else:
                features["age"] = int(age_match.group(1))
                features["age_source_text"] = age_match.group(0)
            logger.debug(f"✅ Extracted age: {features['age']} from: {features['age_source_text'][:50]}")
            break
    
    # Extract gender with better source text
    gender_match = re.search(r'Sesso:\s*([MF])\b', text)
    if gender_match:
        features["gender"] = "male" if gender_match.group(1) == "M" else "female"
        features["gender_source_text"] = gender_match.group(0)
        logger.debug(f"✅ Extracted gender: {features['gender']}")
    
    # Extract ECOG with context
    ecog_patterns = [
        r'PS ECOG[:\s]*(\d)',
        r'ECOG[:\s]*(\d)',
        r'Performance Status[:\s]*(\d)'
    ]
    for pattern in ecog_patterns:
        ecog_match = re.search(pattern, text, re.I)
        if ecog_match:
            features["ecog_ps"] = int(ecog_match.group(1))
            features["ecog_ps_source_text"] = ecog_match.group(0)
            logger.debug(f"✅ Extracted ECOG: {features['ecog_ps']}")
            break
    
    # Extract histology with full context
    histology_patterns = [
        (r'[Aa]denocarcinoma[^,.\n]*', 'adenocarcinoma'),
        (r'[Ss]quamous[^,.\n]*', 'squamous'),
        (r'[Ss]mall[\s-]?cell[^,.\n]*', 'small_cell'),
        (r'NSCLC[^,.\n]*', 'non_small_cell'),
        (r'SCLC[^,.\n]*', 'small_cell')
    ]
    for pattern, hist_type in histology_patterns:
        hist_match = re.search(pattern, text)
        if hist_match:
            features["histology"] = hist_type if hist_type != 'non_small_cell' else 'adenocarcinoma'
            features["histology_source_text"] = hist_match.group(0)
            logger.debug(f"✅ Extracted histology: {features['histology']}")
            break
    
    # Extract stage with TNM context
    stage_patterns = [
        r'(?:stadio|stage)[:\s]*([IVX]+[AB]?)',
        r'pT\d+[ab]?N\d+[ab]?\s*\(([IVX]+[AB]?)\)',
        r'\b(III[AB]?|IV[AB]?|II[AB]?)\b'
    ]
    for pattern in stage_patterns:
        stage_match = re.search(pattern, text, re.I)
        if stage_match:
            stage = stage_match.group(1)
            if 'IV' in stage:
                features["current_stage"] = "IV"
            elif 'III' in stage:
                features["current_stage"] = "III"
            elif 'II' in stage:
                features["current_stage"] = "II"
            # Get broader context for source text
            context_match = re.search(r'[^.]*' + re.escape(stage_match.group(0)) + r'[^.]*', text)
            features["current_stage_source_text"] = context_match.group(0)[:100] if context_match else stage_match.group(0)
            logger.debug(f"✅ Extracted stage: {features['current_stage']}")
            break
    
    # Extract mutations with full description
    mutation_patterns = [
        (r'EGFR[^,.\n]*L858R[^,.\n]*', 'EGFR_L858R'),
        (r'EGFR[^,.\n]*exon\s*19[^,.\n]*', 'EGFR_exon19_del'),
        (r'KRAS[^,.\n]*G12C[^,.\n]*', 'KRAS_G12C'),
        (r'ALK[^,.\n]*positive', 'ALK'),
        (r'ROS1[^,.\n]*positive', 'ROS1')
    ]
    for pattern, mutation_type in mutation_patterns:
        mut_match = re.search(pattern, text, re.I)
        if mut_match:
            features["biomarkers"] = mutation_type
            features["biomarkers_source_text"] = mut_match.group(0)
            logger.debug(f"✅ Extracted biomarker: {features['biomarkers']}")
            break
    
    # Extract therapy line with context
    therapy_patterns = [
        (r'(?:candidabile a |eligible for )?(?:II linea|seconda linea|second[- ]line|2L)', '2L'),
        (r'(?:candidabile a |eligible for )?(?:I linea|prima linea|first[- ]line|1L)', '1L'),
        (r'(?:candidabile a |eligible for )?(?:III linea|terza linea|third[- ]line|3L)', '>=3L')
    ]
    for pattern, line in therapy_patterns:
        therapy_match = re.search(pattern, text, re.I)
        if therapy_match:
            features["line_of_therapy"] = line
            features["line_of_therapy_source_text"] = therapy_match.group(0)
            logger.debug(f"✅ Extracted therapy line: {features['line_of_therapy']}")
            break
    
    # Extract prior therapies
    therapy_drugs = ['carboplatin', 'cisplatin', 'osimertinib', 'pembrolizumab', 'nivolumab', 
                     'atezolizumab', 'durvalumab', 'docetaxel', 'paclitaxel', 'pemetrexed']
    found_therapies = []
    therapy_contexts = []
    for drug in therapy_drugs:
        drug_match = re.search(rf'\b{drug}\b', text, re.I)
        if drug_match:
            found_therapies.append(drug.lower())
            # Get context around the drug mention
            context_match = re.search(rf'[^.]*\b{drug}\b[^.]*', text, re.I)
            if context_match:
                therapy_contexts.append(context_match.group(0))
    
    if found_therapies:
        features["prior_systemic_therapies"] = found_therapies
        features["prior_systemic_therapies_source_text"] = '; '.join(therapy_contexts[:3])  # First 3 contexts
        logger.debug(f"✅ Extracted prior therapies: {found_therapies}")
    
    # Extract PD-L1
    pdl1_patterns = [
        r'PD-?L1[:\s]*([<>=]+\s*\d+%)',
        r'PD-?L1[:\s]*(\d+%)',
        r'TPS[:\s]*([<>=]+\s*\d+%)'
    ]
    for pattern in pdl1_patterns:
        pdl1_match = re.search(pattern, text, re.I)
        if pdl1_match:
            pdl1_value = pdl1_match.group(1)
            if '<1' in pdl1_value or '0%' in pdl1_value:
                features["pd_l1_tps"] = "<1%"
            elif any(x in pdl1_value for x in ['>=50', '>50', '≥50']):
                features["pd_l1_tps"] = ">=50%"
            else:
                features["pd_l1_tps"] = "1-49%"
            features["pd_l1_tps_source_text"] = pdl1_match.group(0)
            logger.debug(f"✅ Extracted PD-L1: {features['pd_l1_tps']}")
            break
    
    logger.info(f"✅ Fallback extraction complete, found {sum(1 for v in features.values() if v != 'not mentioned' and v != ['not mentioned'])} fields")
    return features


def ensure_required_fields(features: Dict[str, Any]) -> None:
    """Ensure all required fields exist in features dict."""
    required_fields = [
        "age", "age_source_text",
        "gender", "gender_source_text",
        "ecog_ps", "ecog_ps_source_text",
        "histology", "histology_source_text",
        "current_stage", "current_stage_source_text",
        "line_of_therapy", "line_of_therapy_source_text",
        "pd_l1_tps", "pd_l1_tps_source_text",
        "biomarkers", "biomarkers_source_text",
        "brain_metastasis", "brain_metastasis_source_text",
        "prior_systemic_therapies", "prior_systemic_therapies_source_text",
        "comorbidities", "comorbidities_source_text",
        "concomitant_treatments", "concomitant_treatments_source_text"
    ]
    
    added_fields = []
    for field in required_fields:
        if field not in features:
            if field.endswith('_source_text'):
                features[field] = "not mentioned"
            elif 'metastasis' in field or 'therapies' in field or 'comorbidities' in field or 'treatments' in field:
                features[field] = ["not mentioned"]
            else:
                features[field] = "not mentioned"
            added_fields.append(field)
    
    if added_fields:
        logger.debug(f"📝 Added {len(added_fields)} missing fields: {added_fields[:5]}...")


def parse_trial_matching_response(response: Any) -> List[Dict[str, Any]]:
    """Parse trial matching response into a list of trial results."""
    logger.debug("🔍 Parsing trial matching response...")

    # Final list?
    if isinstance(response, list):
        logger.debug(f"✅ Response is already a list with {len(response)} items")
        return response

    # Provider envelopes
    if isinstance(response, dict):
        if 'response' in response:
            logger.debug("📦 Unwrapping 'response' field...")
            return parse_trial_matching_response(response['response'])
        if 'trials' in response and isinstance(response['trials'], list):
            logger.debug(f"📦 Found 'trials' list with {len(response['trials'])} items")
            return response['trials']
        if 'results' in response and isinstance(response['results'], list):
            logger.debug(f"📦 Found 'results' list with {len(response['results'])} items")
            return response['results']

    # String handling
    if isinstance(response, str):
        text = response.strip()

        # 1) Try direct JSON, then recurse
        try:
            loaded = json.loads(text)
            logger.debug("✅ Direct JSON parse successful; recursing")
            return parse_trial_matching_response(loaded)
        except Exception as e:
            logger.debug(f"⚠️ Direct parse failed: {e}")

        # 2) Extract JSON array from code fence
        array_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', text, re.IGNORECASE)
        if array_match:
            try:
                loaded = json.loads(array_match.group(1))
                logger.debug(f"✅ Extracted array from code fence; {len(loaded)} items")
                return parse_trial_matching_response(loaded)
            except Exception as e:
                logger.debug(f"⚠️ Code fence array parse failed: {e}")

        # 3) First JSON array in text
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            try:
                loaded = json.loads(array_match.group(0))
                logger.debug(f"✅ Extracted array from text; {len(loaded)} items")
                return parse_trial_matching_response(loaded)
            except Exception as e:
                logger.debug(f"⚠️ Inline array parse failed: {e}")

    logger.error("❌ Could not parse trial matching response")
    return []


def match_trials_llm(features: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Match patient to trials using LLM."""
    logger.info("="*80)
    logger.info("🎯 STARTING CLINICAL TRIAL MATCHING")
    logger.info("="*80)
    
    llm = get_explainer_llm()
    trials = get_all_trials()
    
    logger.info(f"📚 Loaded {len(trials)} trials from database")
    
    if not trials:
        logger.error("❌ No trials found in database")
        return []
    
    # Remove source_text fields for cleaner matching
    clean_features = {k: v for k, v in features.items() if not k.endswith('_source_text')}
    logger.info("🧹 Cleaned features for matching (removed source_text fields)")
    
    matched_trials = []
    batch_size = 3
    total_batches = (len(trials) + batch_size - 1) // batch_size
    
    logger.info(f"📦 Processing {len(trials)} trials in {total_batches} batches of {batch_size}")
    
    # Create trial matching debug log
    matching_debug_file = f"logs/trial_matching_debug_{int(time.time())}.json"
    matching_debug_data = {
        "timestamp": datetime.now().isoformat(),
        "patient_features": clean_features,
        "total_trials": len(trials),
        "batch_size": batch_size,
        "batches": []
    }
    
    for batch_num, i in enumerate(range(0, len(trials), batch_size), 1):
        batch = trials[i:i + batch_size]
        logger.info(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} trials)...")
        
        prompt = f"""Evaluate if this patient matches these clinical trials.

PATIENT:
Age: {clean_features.get('age')}
Gender: {clean_features.get('gender')}
ECOG: {clean_features.get('ecog_ps')}
Histology: {clean_features.get('histology')}
Stage: {clean_features.get('current_stage')}
Line of therapy: {clean_features.get('line_of_therapy')}
Biomarkers: {clean_features.get('biomarkers')}
Brain metastasis: {clean_features.get('brain_metastasis')}
Prior therapies: {clean_features.get('prior_systemic_therapies')}

TRIALS:
{json.dumps(batch, indent=2)}

For each trial, return a JSON array with this EXACT format:
[
  {{
    "trial_id": "<trial id>",
    "title": "<trial title>",
    "match_score": <0-100>,
    "recommendation": "Eligible" or "Not Eligible",
    "criteria_analysis": "<brief analysis>",
    "summary": "<one sentence summary>"
  }}
]

Rules:
- Start with 100 points
- Subtract 10 for each unmet inclusion
- Subtract 50 for each violated exclusion
- Score ≥70 = "Eligible", <70 = "Not Eligible"

Return ONLY the JSON array."""

        batch_debug = {
            "batch_number": batch_num,
            "trial_ids": [t.get("id", "unknown") for t in batch],
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:500]
        }

        try:
            logger.info(f"🤖 Sending batch {batch_num} to LLM...")
            start_time = time.time()
            response = llm.generate_response(prompt)
            elapsed_time = time.time() - start_time
            logger.info(f"✅ LLM responded in {elapsed_time:.2f} seconds")
            
            batch_debug["response_time"] = elapsed_time
            batch_debug["raw_response"] = str(response)[:1000]
            
            results = parse_trial_matching_response(response)
            batch_debug["parsed_results_count"] = len(results) if results else 0
            
            if results:
                logger.info(f"✅ Parsed {len(results)} trial results from batch {batch_num}")
                for idx, result in enumerate(results[:len(batch)]):
                    if idx < len(batch):
                        trial = batch[idx]
                        trial_result = {
                            "trial_id": trial.get("id", result.get("trial_id")),
                            "title": trial.get("title", result.get("title", "Unknown")),
                            "description": trial.get("description", ""),
                            "match_score": result.get("match_score", 0),
                            "recommendation": result.get("recommendation", "Not Eligible"),
                            "criteria_analysis": result.get("criteria_analysis", ""),
                            "summary": result.get("summary", "")
                        }
                        matched_trials.append(trial_result)
                        
                        # Log individual trial result
                        logger.debug(f"  Trial {trial_result['trial_id']}: Score={trial_result['match_score']}, {trial_result['recommendation']}")
            else:
                logger.warning(f"⚠️ No results parsed from batch {batch_num}")
                batch_debug["error"] = "No results parsed"
            
        except Exception as e:
            logger.error(f"❌ Error matching batch {batch_num}: {e}")
            batch_debug["error"] = str(e)
        
        matching_debug_data["batches"].append(batch_debug)
    
    # Sort by score
    matched_trials.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    
    # Save trial matching debug log
    try:
        with open(matching_debug_file, "w", encoding="utf-8") as f:
            matching_debug_data["total_matched"] = len(matched_trials)
            matching_debug_data["eligible_count"] = sum(1 for t in matched_trials if t.get("recommendation") == "Eligible")
            json.dump(matching_debug_data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"💾 Saved trial matching debug log to: {matching_debug_file}")
    except Exception as e:
        logger.warning(f"⚠️ Could not save matching debug log: {e}")
    
    # Log summary
    logger.info("📊 TRIAL MATCHING SUMMARY:")
    logger.info(f"  - Total trials evaluated: {len(trials)}")
    logger.info(f"  - Total matches found: {len(matched_trials)}")
    eligible = [t for t in matched_trials if t.get("recommendation") == "Eligible"]
    logger.info(f"  - Eligible trials: {len(eligible)}")
    if eligible:
        logger.info("  - Top eligible trials:")
        for t in eligible[:3]:
            logger.info(f"    • {t['title'][:50]}... (Score: {t['match_score']})")
    
    logger.info("="*80)
    logger.info(f"✅ TRIAL MATCHING COMPLETE - {len(matched_trials)} trials matched")
    logger.info("="*80)
    
    return matched_trials


def highlight_sources(text: str, features: Dict[str, Any]) -> str:
    """Highlight source text in HTML."""
    logger.debug("🎨 Starting text highlighting...")
    highlighted = text
    
    colors = {
        'age': '#ffeb3b',
        'gender': '#e91e63',
        'diagnosis': '#2196f3',
        'stage': '#4caf50',
        'ecog': '#ff9800',
        'mutations': '#9c27b0',
        'metastases': '#f44336',
        'pd_l1': '#00bcd4'
    }
    
    highlight_count = 0
    for key, value in features.items():
        if key.endswith('_source_text') and value != "not mentioned":
            feature_type = key.split('_')[0]
            color = colors.get(feature_type, '#ffeb3b')
            
            if isinstance(value, str) and len(value) > 2:
                pattern = re.escape(value)
                replacement = f'<mark style="background:{color}">{value}</mark>'
                highlighted = re.sub(pattern, replacement, highlighted, count=1)
                highlight_count += 1
    
    logger.debug(f"✅ Applied {highlight_count} text highlights")
    return highlighted


def create_annotated_pdf(pdf_path: str, features: Dict[str, Any], output_path: str = None) -> str:
    """Create annotated PDF with highlighted features."""
    logger.info("📑 Starting PDF annotation...")
    try:
        pdf_document = fitz.open(pdf_path)
        logger.info(f"📑 Opened PDF with {len(pdf_document)} pages")
        
        highlight_colors = {
            'age': (1.0, 0.92, 0.23, 0.3),
            'gender': (0.91, 0.12, 0.39, 0.3),
            'histology': (0.13, 0.59, 0.95, 0.3),
            'stage': (0.30, 0.69, 0.31, 0.3),
            'ecog': (1.0, 0.60, 0.0, 0.3),
            'biomarkers': (0.61, 0.15, 0.69, 0.3)
        }
        
        annotation_count = 0
        for key, value in features.items():
            if key.endswith('_source_text') and value != "not mentioned":
                feature_type = key.split('_')[0]
                color = highlight_colors.get(feature_type, (1.0, 0.92, 0.23, 0.3))
                
                if isinstance(value, str) and len(value) > 2:
                    for page_num in range(len(pdf_document)):
                        page = pdf_document[page_num]
                        text_instances = page.search_for(value)
                        
                        for inst in text_instances:
                            highlight = page.add_highlight_annot(inst)
                            highlight.set_colors(stroke=color[:3])
                            highlight.set_opacity(color[3])
                            highlight.update()
                            annotation_count += 1
        
        if output_path is None:
            output_path = os.path.join('uploads', f'annotated_{int(time.time())}.pdf')
        
        pdf_document.save(output_path)
        pdf_document.close()
        logger.info(f"✅ PDF annotation complete: {annotation_count} annotations added")
        logger.info(f"📄 Saved annotated PDF to: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Error creating annotated PDF: {e}")
        return pdf_path


def process_patient_document(text_or_file: Union[str, bytes], is_file: bool = False) -> Dict[str, Any]:
    """Main processing pipeline."""
    logger.info("="*80)
    logger.info("🏥 STARTING PATIENT DOCUMENT PROCESSING")
    logger.info("="*80)
    
    try:
        pdf_path = None
        if is_file:
            pdf_path = text_or_file
            logger.info(f"📂 Processing PDF file: {pdf_path}")
            text_content = extract_text_from_pdf(text_or_file)
        else:
            logger.info("📝 Processing text input")
            text_content = str(text_or_file)
        
        logger.info(f"📏 Document length: {len(text_content)} characters")
        
        # Extract features
        logger.info("\n🔬 Phase 1: Feature Extraction")
        features = extract_features_with_llm(text_content)
        
        # Create annotated PDF if applicable
        annotated_pdf_url = None
        if pdf_path and is_file:
            logger.info("\n📑 Phase 2: PDF Annotation")
            try:
                annotated_path = create_annotated_pdf(pdf_path, features)
                annotated_pdf_url = f"/view-pdf/{os.path.basename(annotated_path)}"
            except Exception as e:
                logger.error(f"❌ Annotation failed: {e}")
        
        # Highlight text
        logger.info("\n🎨 Phase 3: Text Highlighting")
        highlighted_text = highlight_sources(text_content, features)
        
        # Match trials
        logger.info("\n🎯 Phase 4: Clinical Trial Matching")
        matched_trials = match_trials_llm(features)
        
        # Clean features for frontend (remove source_text fields)
        clean_features = {k: v for k, v in features.items() if not k.endswith('_source_text')}
        
        logger.info("="*80)
        logger.info("✅ DOCUMENT PROCESSING COMPLETE")
        logger.info(f"  - Features extracted: {len(clean_features)}")
        logger.info(f"  - Trials matched: {len(matched_trials)}")
        logger.info(f"  - PDF annotated: {'Yes' if annotated_pdf_url else 'No'}")
        logger.info("="*80)
        
        return {
            "success": True,
            "features": clean_features,
            "highlighted_text": highlighted_text,
            "annotated_pdf_url": annotated_pdf_url,
            "matched_trials": matched_trials,
            "original_text": text_content
        }
        
    except Exception as e:
        logger.error(f"❌ PROCESSING ERROR: {e}")
        logger.error(f"📋 Error type: {type(e).__name__}")
        logger.error(f"📋 Error details: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "features": {},
            "highlighted_text": "",
            "annotated_pdf_url": None,
            "matched_trials": []
        }
        
def strip_source_fields(features: Dict[str, Any]) -> Dict[str, Any]:
    """Remove source_text fields from features dict."""
    return
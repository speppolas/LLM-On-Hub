# app/core/feature_extraction.py
import os
import time
import re
import json
import logging
import pdfplumber
import fitz
from typing import Dict, Any, Union, List
from datetime import datetime
from flask import current_app
from app.core.llm_processor import get_explainer_llm  # Gemma (o alias) userà questo
from app.utils import get_all_trials
from app import logger

os.makedirs("logs", exist_ok=True)

def extract_text_from_pdf(pdf_file: Union[str, bytes]) -> str:
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t:
                text += t + "\n"
    return text.strip()

def parse_trial_matching_response(response: Any) -> List[Dict[str, Any]]:
    """Riusa il parser già presente per trasformare l’output LLM in lista di trial."""
    # Pass 1: già lista
    if isinstance(response, list):
        return response
    # Pass 2: dict con vari “envelope”
    if isinstance(response, dict):
        for key in ("response", "trials", "results", "message", "content"):
            if key in response:
                return parse_trial_matching_response(response[key])
    # Pass 3: stringa -> tenta JSON/array anche in code fence
    if isinstance(response, str):
        s = response.strip()
        try:
            return parse_trial_matching_response(json.loads(s))
        except Exception:
            pass
        m = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', s, re.I)
        if m:
            try:
                return parse_trial_matching_response(json.loads(m.group(1)))
            except Exception:
                pass
        m = re.search(r'\[[\s\S]*\]', s)
        if m:
            try:
                return parse_trial_matching_response(json.loads(m.group(0)))
            except Exception:
                pass
    # Fallback: nessun parse
    return []

# app/core/feature_extraction.py

from typing import Dict, Any, Union, List, Tuple

def _slim_trial(t: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only what the LLM truly needs."""
    return {
        "id": t.get("id") or t.get("trial_id") or t.get("nct_id"),
        "title": t.get("title", ""),
        "inclusion": t.get("inclusion", []),
        "exclusion": t.get("exclusion", []),
        # add other small, high-signal fields if you have them (e.g., phase, tumor_type)
    }

def _chunk(seq: List[Any], size: int) -> List[List[Any]]:
    return [seq[i:i+size] for i in range(0, len(seq), size)]

def _normalize_llm_items(raw: Any) -> List[Dict[str, Any]]:
    """Leverages existing robust parsing, then enforces dict structure."""
    items = parse_trial_matching_response(raw) or []
    norm = []
    for it in items:
        if isinstance(it, dict):
            norm.append({
                "idx": it.get("idx"),  # may be None; we’ll fix below
                "trial_id": it.get("trial_id") or it.get("id"),
                "title": it.get("title", ""),
                "match_score": it.get("match_score", 0),
                "recommendation": it.get("recommendation", "Not Eligible"),
                "criteria_analysis": it.get("criteria_analysis", ""),
                "summary": it.get("summary", "")
            })
    return norm

def match_trials_from_text(text_content: str) -> List[Dict[str, Any]]:
    """
    Direct matching: batch trials, force 1:1 mapping with an 'idx', then merge & de-dup.
    """
    llm = get_explainer_llm()
    all_trials = get_all_trials()
    if not all_trials:
        return []

    # 1) Slim trials to reduce prompt length / noise
    slimmed: List[Dict[str, Any]] = []
    for t in all_trials:
        s = _slim_trial(t)
        if s.get("id"):
            slimmed.append(s)

    # (Optional pre-filter) naive filter by cancer keywords to cut batches, if desired:
    # patient_kw = set(re.findall(r'\b(nsclc|sclc|adenocarcinoma|squamous|lung|thoracic)\b', text_content.lower()))
    # if patient_kw:
    #     slimmed = [t for t in slimmed if any(k in (t.get("title","")+str(t.get("inclusion",""))+str(t.get("exclusion",""))).lower() for k in patient_kw)] or slimmed

    # 2) Batching
    BATCH_SIZE = 5
    batches = _chunk(slimmed, BATCH_SIZE)

    merged_results: List[Dict[str, Any]] = []
    global_idx = 0

    for batch in batches:
        # Assign a stable idx per trial *within this batch*
        indexed_batch = []
        for j, t in enumerate(batch):
            indexed_batch.append({
                "idx": j,  # local idx 0..(len(batch)-1)
                "id": t["id"],
                "title": t["title"],
                "inclusion": t.get("inclusion", []),
                "exclusion": t.get("exclusion", [])
            })

        # 3) Strong, deterministic instruction: one output per input trial, same order, same idx/id
        prompt = f"""You are a clinical trial matching engine.

INPUT_PATIENT_TEXT (truncated):
{text_content[:6000]}

INPUT_TRIALS (BATCH, JSON):
{json.dumps(indexed_batch, ensure_ascii=False)}

TASK:
For EACH object in INPUT_TRIALS, return EXACTLY ONE result object, in the SAME ORDER, preserving BOTH "idx" and "id" from the input.
NEVER merge trials, NEVER duplicate the same trial, and NEVER invent new trial IDs.

SCORING RULES:
- Start at 100
- −10 for each REQUIRED inclusion that is not met
- −50 for each exclusion criterion that appears to be violated
- recommendation = "Eligible" if score ≥ 70 else "Not Eligible"

STRICT OUTPUT: return ONLY a JSON array with length == len(INPUT_TRIALS), where each element is:
{{
  "idx": <same integer from INPUT_TRIALS>,
  "trial_id": "<MUST be exactly the same as input 'id'>",
  "title": "<echo title or leave empty>",
  "match_score": <0-100 integer>,
  "recommendation": "Eligible" | "Not Eligible",
  "criteria_analysis": "<brief reason referencing key inclusions/exclusions>",
  "summary": "<one-sentence summary>"
}}

DO NOT return any commentary outside the JSON array.
"""

        raw = llm.generate_response(prompt)
        items = _normalize_llm_items(raw)

        # 4) Map results back to the correct trial by idx (defensive)
        by_idx: Dict[int, Dict[str, Any]] = {}
        for it in items:
            if isinstance(it.get("idx"), int) and 0 <= it["idx"] < len(indexed_batch):
                in_trial = indexed_batch[it["idx"]]
                # If LLM put the wrong id, force-correct it
                trial_id = in_trial["id"]
                by_idx[it["idx"]] = {
                    "trial_id": trial_id,
                    "title": it.get("title") or in_trial.get("title", ""),
                    "match_score": int(it.get("match_score", 0)) if str(it.get("match_score", "")).isdigit() else 0,
                    "recommendation": "Eligible" if str(it.get("recommendation","")).lower().startswith("eligible") and int(it.get("match_score", 0)) >= 70 else "Not Eligible",
                    "criteria_analysis": it.get("criteria_analysis", ""),
                    "summary": it.get("summary", "")
                }

        # Fill any missing outputs to preserve 1:1,
        # e.g. if model returned fewer items, create safe fallbacks:
        for j, in_trial in enumerate(indexed_batch):
            if j not in by_idx:
                by_idx[j] = {
                    "trial_id": in_trial["id"],
                    "title": in_trial["title"],
                    "match_score": 0,
                    "recommendation": "Not Eligible",
                    "criteria_analysis": "No structured output for this trial in the batch; defaulted to Not Eligible.",
                    "summary": ""
                }

        # Keep batch order
        batch_results = [by_idx[j] for j in range(len(indexed_batch))]
        merged_results.extend(batch_results)
        global_idx += len(indexed_batch)

    # 5) De-duplicate by trial_id (keep highest score)
    best_by_id: Dict[str, Dict[str, Any]] = {}
    for r in merged_results:
        tid = r.get("trial_id")
        if not tid:
            continue
        prev = best_by_id.get(tid)
        if not prev or (r.get("match_score", 0) > prev.get("match_score", 0)):
            best_by_id[tid] = r

    final = list(best_by_id.values())
    final.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return final

def process_patient_document(text_or_file: Union[str, bytes], is_file: bool = False) -> Dict[str, Any]:
    """
    NUOVA PIPELINE “direct”: estrae solo il testo (se PDF) e fa match diretto con Gemma.
    Niente feature extraction, niente highlight, niente annotated PDF.
    """
    try:
        if is_file:
            text_content = extract_text_from_pdf(text_or_file)
        else:
            text_content = str(text_or_file)

        matched_trials = match_trials_from_text(text_content)

        return {
            "success": True,
            "features": {},                 # più nessuna feature
            "highlighted_text": "",         # niente highlight
            "annotated_pdf_url": None,      # niente annotated PDF
            "matched_trials": matched_trials,
            "original_text": text_content
        }
    except Exception as e:
        logger.exception("Direct matching pipeline failed")
        return {
            "success": False,
            "error": str(e),
            "features": {},
            "highlighted_text": "",
            "annotated_pdf_url": None,
            "matched_trials": []
        }





def extract_features_with_llm(text_content: str) -> Dict[str, Any]:
    return

def highlight_sources(text_content: str, features: Dict[str, Any]) -> str:
    return 
def create_annotated_pdf(original_pdf: bytes, features: Dict[str, Any]) -> bytes:
    return

def strip_source_fields(features: Dict[str, Any]) -> Dict[str, Any]:
    return

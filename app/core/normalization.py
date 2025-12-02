# normalization.py
import json
import re
from typing import Any, Dict, List, Optional

# ---------------------------
# SCHEMA defaults e chiavi ammesse
# ---------------------------
SCHEMA_DEFAULTS: Dict[str, Any] = {
    "age": None, "age_source_text": None, "age_source_spans": [],
    "gender": "not mentioned", "gender_source_text": None, "gender_source_spans": [],
    "diagnosis": "not mentioned", "diagnosis_source_text": None, "diagnosis_source_spans": [],
    "stage": "not mentioned", "stage_source_text": None, "stage_source_spans": [],
    "ecog_ps": None, "ecog_ps_source_text": None, "ecog_ps_source_spans": [],
    "mutations": "not mentioned", "mutations_source_text": None, "mutations_source_spans": [],
    "metastases": ["not mentioned"], "metastases_source_text": None, "metastases_source_spans": [],
    "previous_treatments": ["not mentioned"], "previous_treatments_source_text": None, "previous_treatments_source_spans": [],
    "PD_L1": "not mentioned", "PD_L1_source_text": None, "PD_L1_source_spans": [],
    "previous_treatments_metastatic_first_line": "not mentioned", "previous_treatments_metastatic_first_line_source_text": None, "previous_treatments_metastatic_first_line_source_spans": [],
    "previous_treatments_metastatic_second_line": "not mentioned", "previous_treatments_metastatic_second_line_source_text": None, "previous_treatments_metastatic_second_line_source_spans": [],
    "previous_treatments_metastatic_third_line": "not mentioned", "previous_treatments_metastatic_third_line_source_text": None, "previous_treatments_metastatic_third_line_source_spans": [],
    "previous_treatments_localized": ["not mentioned"], "previous_treatments_localized_source_text": None, "previous_treatments_localized_source_spans": [],
    "response_to_last_treatment": "not mentioned", "response_to_last_treatment_source_text": None, "response_to_last_treatment_source_spans": [],
    "comorbidities": ["not mentioned"], "comorbidities_source_text": None, "comorbidities_source_spans": []
}
ALLOWED_KEYS = set(SCHEMA_DEFAULTS.keys())

# ---------------------------
# Vocabolari / domini ammessi
# ---------------------------
GENDER_MAP = {
    "m": "male", "male": "male", "maschio": "male",
    "f": "female", "female": "female", "femmina": "female"
}
DIAG_MAP = {
    "sclc": "SCLC",
    "small cell": "SCLC",
    "adenocarcinoma": "adenocarcinoma",
    "adenoca": "adenocarcinoma",
    "squamous": "squamous cell lung cancer",
    "squam": "squamous cell lung cancer",
    "squamous cell lung cancer": "squamous cell lung cancer",
}
META_ALLOWED = {"brain", "liver", "bone", "lymph nodes", "adrenal", "pleural"}
PREV_TX_ALLOWED = {
    "carboplatin","cisplatin","paclitaxel","docetaxel","pembrolizumab","nivolumab",
    "atezolizumab","durvalumab","osimertinib","erlotinib","gefitinib","afatinib",
    "crizotinib","alectinib"
}
PREV_LOC_ALLOWED = {
    "adjuvant chemotherapy","adjuvant radiotherapy","adjuvant immunotherapy",
    "adjuvant targeted therapy","perioperative adjuvant chemotherapy","neoadjuvant chemotherapy"
}
COMORB_ALLOWED = {
    "HIV","pregnancy","active autoimmune disease","severe cardiovascular disease",
    "active infection","interstitial lung disease","hepatitis B","hepatitis C",
    "pneumonitis","immunodeficiency","other significant comorbidities"
}

# ---------------------------
# Helpers
# ---------------------------
def _to_int_or_none(v: Any) -> Optional[int]:
    try:
        if v is None or isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip()
        if not s:
            return None
        m = re.search(r'(-?\d+)', s)
        return int(m.group(1)) if m else None
    except Exception:
        return None

def _norm_gender(v: Any) -> str:
    if v is None:
        return "not mentioned"
    return GENDER_MAP.get(str(v).strip().lower(), "not mentioned")

# --- SOSTITUISCI _norm_diag esistente con questo ---
def _norm_diag(v: Any) -> str:
    if v is None:
        return "not mentioned"
    s = str(v).strip().lower()

    # normalizza punctuation/spazi
    s_clean = re.sub(r'\s+', ' ', s)

    # boundary-based matches per evitare "nsclc" -> "sclc"
    if re.search(r'\bnsclc\b', s_clean):
        # prova a capire il sottotipo se presente
        if re.search(r'\b(adk|adenoca|adenocarcinoma)\b', s_clean):
            return "adenocarcinoma"
        if re.search(r'\b(squam|squamous)\b', s_clean):
            return "squamous cell lung cancer"
        return "other"  # NSCLC non specificato

    if re.search(r'\bsclc\b', s_clean):
        return "SCLC"

    # matching diretto sottotipi
    if re.search(r'\b(adk|adenoca|adenocarcinoma)\b', s_clean):
        return "adenocarcinoma"
    if re.search(r'\b(squam|squamous|squamous cell lung cancer)\b', s_clean):
        return "squamous cell lung cancer"

    # adeno-squamoso
    if re.search(r'\b(adeno[- ]?squamous|adenosquamous)\b', s_clean):
        return "other"

    return "other" if s_clean else "not mentioned"


def _norm_stage(v: Any) -> str:
    if v is None:
        return "not mentioned"
    s = str(v).strip().upper()
    s = re.sub(r"STAGE\s*", "", s)
    s = s.replace(" ", "")
    if "II" in s and "III" not in s and "IV" not in s:
        return "II"
    if "III" in s and "IV" not in s:
        return "III"
    if "IV" in s:
        return "IV"
    return "not mentioned"

def _norm_ecog_ps(v: Any) -> Optional[int]:
    i = _to_int_or_none(v)
    return i if i in (0, 1) else None

def _norm_pd_l1(v: Any) -> str:
    if v is None:
        return "not mentioned"
    s = str(v).strip().replace(" ", "").lower().replace("%", "")
    try:
        m = re.search(r'(\d{1,3})', s)
        if m:
            val = int(m.group(1))
            if val < 1: return "<1%"
            if 1 <= val <= 49: return "1-49%"
            if val >= 50: return ">50%"
    except Exception:
        pass
    if "<1" in s: return "<1%"
    if "1-49" in s or "1to49" in s or "1–49" in s: return "1-49%"
    if ">50" in s or ">=50" in s or "50-100" in s: return ">50%"
    return "not mentioned"

def _norm_mutations(v: Any) -> str:
    if v is None: return "not mentioned"
    s = str(v).lower()
    if "egfr" in s: return "EGFR"
    if "kras" in s: return "KRAS"
    if "met" in s: return "MET"
    return "not mentioned"

def _as_list(v: Any) -> List[str]:
    if v is None: return []
    if isinstance(v, list):
        return [str(x) for x in v if x is not None]
    return [str(v)]

# --- SOSTITUISCI _norm_metastases con questo ---
def _norm_metastases(v: Any) -> List[str]:
    items = [x.strip().lower() for x in _as_list(v)]
    keep: List[str] = []

    for it in items:
        if not it:
            continue
        # sinonimi italiani + inglese
        if any(tok in it for tok in ["encefal", "cerebr", "brain"]):
            keep.append("brain")
        if any(tok in it for tok in ["epat", "fegat", "liver"]):
            keep.append("liver")
        if any(tok in it for tok in ["ossee", "ossea", "scheletr", "bone"]):
            keep.append("bone")
        if "linfon" in it or "lymph" in it:
            keep.append("lymph nodes")
        if "surrenal" in it or "adrenal" in it:
            keep.append("adrenal")
        if "pleur" in it or "pleural" in it:
            keep.append("pleural")

    if not keep:
        return ["not mentioned"]

    # dedup preservando ordine
    out, seen = [], set()
    for k in keep:
        if k not in seen:
            out.append(k); seen.add(k)
    return out


def _norm_prev_treatments(v: Any) -> List[str]:
    items = [x.strip().lower() for x in _as_list(v)]
    keep: List[str] = []
    for it in items:
        for canon in PREV_TX_ALLOWED:
            if canon in it:
                keep.append(canon); break
    return sorted(list(dict.fromkeys(keep))) or ["not mentioned"]

def _norm_prev_localized(v: Any) -> List[str]:
    items = [x.strip().lower() for x in _as_list(v)]
    keep: List[str] = []
    SYN = {
        "adjuvant chemotherapy": ["adiuvante","adjuvant chemo","chemioterapia adiuvante"],
        "adjuvant radiotherapy": ["radioterapia adiuvante","adjuvant radio"],
        "adjuvant immunotherapy": ["immunoterapia adiuvante"],
        "adjuvant targeted therapy": ["terapia target adiuvante","adjuvant targeted"],
        "perioperative adjuvant chemotherapy": ["perioperatoria","perioperative chemo"],
        "neoadjuvant chemotherapy": ["neoadiuvante","neoadjuvant chemo"]
    }
    for it in items:
        for canon in PREV_LOC_ALLOWED:
            if canon in it: keep.append(canon)
        for canon, vars_ in SYN.items():
            if any(vv in it for vv in vars_): keep.append(canon)
    return sorted(list(dict.fromkeys(keep))) or ["not mentioned"]

def _norm_prev_line(v: Any) -> str:
    if v is None: return "not mentioned"
    s = str(v).strip().lower()
    if any(tok in s for tok in ["immun","pembro","nivo","atezo","durva"," io "]): return "immuno"
    if any(tok in s for tok in ["chemo","chemio","platin","tax","docetaxel","paclitaxel"]): return "chemio"
    if any(tok in s for tok in ["target","tk","egfr","kras","met","osim","erlotinib","gefitinib","afatinib","crizotinib","alectinib"]): return "target"
    return "not mentioned"

def _norm_comorbidities(v: Any) -> List[str]:
    items = [x.strip().lower() for x in _as_list(v)]
    keep: List[str] = []
    for it in items:
        for canon in COMORB_ALLOWED:
            if canon.lower() in it: keep.append(canon); break
        if "cardi" in it and "severe cardiovascular disease" not in keep:
            keep.append("severe cardiovascular disease")
        if "polmonit" in it and "pneumonitis" not in keep:
            keep.append("pneumonitis")
        if "interstiz" in it and "interstitial lung disease" not in keep:
            keep.append("interstitial lung disease")
    return sorted(list(dict.fromkeys(keep))) or ["not mentioned"]

def _ensure_list_spans(x: Any) -> List[List[int]]:
    """Coerce *_source_spans to [[start,end], ...]."""
    if x in (None, "", []): return []
    val = x
    if isinstance(x, str):
        try: val = json.loads(x)
        except Exception: return []
    if isinstance(val, dict):
        val = [val]
    out: List[List[int]] = []
    if isinstance(val, list):
        for item in val:
            if isinstance(item, dict):
                s, e = item.get("start"), item.get("end")
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                s, e = item[0], item[1]
            else:
                continue
            if isinstance(s, int) and isinstance(e, int) and 0 <= s < e:
                out.append([s, e])
    return out

# ---------------------------
# API di normalizzazione PUBLIC
# ---------------------------
def normalize_features_for_schema(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    - Rimuove chiavi extra (allow-list)
    - Inserisce default mancanti
    - Converte i valori nei domini ammessi
    - Preserva *_source_text / normalizza *_source_spans
    """
    out: Dict[str, Any] = {}
    out.update(SCHEMA_DEFAULTS)

    # Copia solo chiavi ammesse
    for k, v in features.items():
        if k in ALLOWED_KEYS:
            out[k] = v

    # Normalizza domini
    out["age"] = _to_int_or_none(out.get("age"))
    out["gender"] = _norm_gender(out.get("gender"))
    out["diagnosis"] = _norm_diag(out.get("diagnosis"))
    out["stage"] = _norm_stage(out.get("stage"))
    out["ecog_ps"] = _norm_ecog_ps(out.get("ecog_ps"))
    out["mutations"] = _norm_mutations(out.get("mutations"))
    out["metastases"] = _norm_metastases(out.get("metastases"))
    out["previous_treatments"] = _norm_prev_treatments(out.get("previous_treatments"))
    out["PD_L1"] = _norm_pd_l1(out.get("PD_L1"))
    out["previous_treatments_metastatic_first_line"] = _norm_prev_line(out.get("previous_treatments_metastatic_first_line"))
    out["previous_treatments_metastatic_second_line"] = _norm_prev_line(out.get("previous_treatments_metastatic_second_line"))
    out["previous_treatments_metastatic_third_line"] = _norm_prev_line(out.get("previous_treatments_metastatic_third_line"))
    out["previous_treatments_localized"] = _norm_prev_localized(out.get("previous_treatments_localized"))
    s = str(out.get("response_to_last_treatment") or "").strip().lower()
    if s not in {"progression","no progression","not mentioned"}:
        if "progress" in s: s = "progression"
        elif any(tok in s for tok in ["stable","no prog","non prog"]): s = "no progression"
        else: s = "not mentioned"
    out["response_to_last_treatment"] = s
    out["comorbidities"] = _norm_comorbidities(out.get("comorbidities"))

    # Spans
    for k in list(out.keys()):
        if k.endswith("_source_spans"):
            out[k] = _ensure_list_spans(out[k])

    return out

def count_defaults(d: Dict[str, Any]) -> int:
    """Conta quanti campi sono rimasti ai valori di default dello schema."""
    cnt = 0
    for k, v in d.items():
        if k in SCHEMA_DEFAULTS and v == SCHEMA_DEFAULTS[k]:
            cnt += 1
    return cnt

__all__ = [
    "SCHEMA_DEFAULTS", "ALLOWED_KEYS",
    "normalize_features_for_schema", "count_defaults"
]




# # >>> schema_validation.py  (APPENDI IN FONDO AL FILE)
# from typing import Dict, Any, List

# # ---------------------------
# # NORMALIZZAZIONE (Mossa qui)
# # ---------------------------
# DRUG_MAP = {
#     "pembro": "pembrolizumab", "nivo": "nivolumab", "atezo": "atezolizumab", "durva": "durvalumab",
#     "carbo": "carboplatin", "cis": "cisplatin", "osim": "osimertinib", "erlo": "erlotinib",
#     "gefi": "gefitinib", "crizo": "crizotinib", "alec": "alectinib"
# }

# ALLOWED_DRUGS = {
#     "carboplatin", "cisplatin", "paclitaxel", "docetaxel", "pembrolizumab",
#     "nivolumab", "atezolizumab", "durvalumab", "osimertinib", "erlotinib",
#     "gefitinib", "afatinib", "crizotinib", "alectinib", "not mentioned"
# }

# ALLOWED_METS = {"brain", "liver", "bone", "lymph nodes", "adrenal", "pleural", "not mentioned"}

# ALLOWED_LOC = {
#     "adjuvant chemotherapy", "adjuvant radiotherapy", "adjuvant immunotherapy",
#     "adjuvant targeted therapy", "perioperative adjuvant chemotherapy",
#     "neoadjuvant chemotherapy", "not mentioned"
# }

# def normalize_features_for_schema(f: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Normalizza l'output LLM per aderire rigorosamente allo schema ClinicalFeatures.
#     (Questa è la funzione che prima era in feature_extraction.py.)
#     """
#     out = dict(f)

#     # Gender
#     g = str(out.get("gender", "not mentioned")).lower()
#     if g in {"m", "uomo", "maschio"}:
#         out["gender"] = "male"
#     elif g in {"f", "donna", "femmina"}:
#         out["gender"] = "female"
#     elif g not in {"male", "female", "not mentioned"}:
#         out["gender"] = "not mentioned"

#     # Diagnosis
#     diag = out.get("diagnosis", "not mentioned")
#     if diag not in {"SCLC", "adenocarcinoma", "squamous cell lung cancer", "other", "not mentioned"}:
#         out["diagnosis"] = "not mentioned"

#     # Stage
#     if out.get("stage") not in {"II", "III", "IV", "not mentioned"}:
#         out["stage"] = "not mentioned"

#     # ECOG
#     ec = out.get("ecog_ps", None)
#     try:
#         ec = int(ec) if ec is not None else None
#     except (ValueError, TypeError):
#         ec = None
#     if ec not in (0, 1):
#         ec = None
#     out["ecog_ps"] = ec

#     # PD-L1
#     if out.get("PD_L1") not in {"<1%", "1-49%", ">50%", "not mentioned"}:
#         out["PD_L1"] = "not mentioned"

#     # Mutations (prioritized bucket)
#     if out.get("mutations") not in {"EGFR", "KRAS", "MET", "not mentioned"}:
#         out["mutations"] = "not mentioned"

#     # Metastases
#     mets = out.get("metastases")
#     if not isinstance(mets, list):
#         mets = []
#     mets = [m for m in mets if isinstance(m, str) and m in ALLOWED_METS]
#     out["metastases"] = mets or ["not mentioned"]

#     # Previous treatments
#     prev = out.get("previous_treatments")
#     if not isinstance(prev, list):
#         prev = []
#     norm = []
#     for d in prev:
#         if not isinstance(d, str):
#             continue
#         dd = DRUG_MAP.get(d.strip().lower(), d.strip().lower())
#         if dd in ALLOWED_DRUGS:
#             norm.append(dd)
#     # dedup preservando ordine
#     seen = set()
#     norm2: List[str] = []
#     for d in norm:
#         if d not in seen:
#             norm2.append(d)
#             seen.add(d)
#     out["previous_treatments"] = norm2 or ["not mentioned"]

#     # Metastatic lines
#     for k in ("previous_treatments_metastatic_first_line",
#               "previous_treatments_metastatic_second_line",
#               "previous_treatments_metastatic_third_line"):
#         v = out.get(k, "not mentioned")
#         if v not in {"immuno", "chemio", "target", "not mentioned"}:
#             out[k] = "not mentioned"

#     # Localized
#     loc = out.get("previous_treatments_localized")
#     if not isinstance(loc, list):
#         loc = []
#     loc = [x for x in loc if isinstance(x, str) and x in ALLOWED_LOC]
#     out["previous_treatments_localized"] = loc or ["not mentioned"]

#     # Response
#     if out.get("response_to_last_treatment") not in {"progression", "no progression", "not mentioned"}:
#         out["response_to_last_treatment"] = "not mentioned"

#     # Comorbidities
#     comorbidities = out.get("comorbidities")
#     if not isinstance(comorbidities, list):
#         comorbidities = []
#     allowed_comorbidities = ClinicalFeatures.ALLOWED_COMORBIDITIES
#     comorbidities = [c for c in comorbidities if isinstance(c, str) and c in allowed_comorbidities]
#     out["comorbidities"] = comorbidities or ["not mentioned"]

#     return out

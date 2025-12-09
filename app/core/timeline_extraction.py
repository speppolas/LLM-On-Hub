import os
import json
import time
import logging
from typing import Union, List, Dict, Any, Tuple, Optional
from dateutil import parser
import pandas as pd
import html
import re
import unicodedata
from app import logger
from app.core.llm_processor import get_llm_processor



def _coerce_event_keys(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalizes ANY messy LLM JSON into:
        [{"data": "...", "testo": "..."}]

    Accepts:
    - direct arrays
    - wrappers (timeline, events, items, output)
    - deeply nested dicts containing date/text fields
    - dictionaries with multiple medical sections
    """

    # --- 1) If the top-level is a dict, unwrap known wrappers ---
    if isinstance(raw, dict):
        for key in ("events", "items", "timeline", "result", "output", "predictions"):
            if key in raw and isinstance(raw[key], list):
                raw = raw[key]
                break

    # --- 2) If still a dict, treat it as a nested medical object ---
    #       → search recursively for event-like dicts
    if isinstance(raw, dict):
        collected = []
        for k, v in raw.items():
            collected.extend(_coerce_event_keys(v))
        return collected

    # --- 3) If not a list by now, we cannot parse ---
    if not isinstance(raw, list):
        return []

    out = []

    # Field names we will interpret as a date
    date_keys = [
        "data", "date", "data_evento", "when", "giorno", "day",
        "date_event", "date_of_event", "event_date"
    ]

    # Field names we interpret as the event text / meaning
    text_keys = [
        "testo", "evento", "label", "name",
        "description", "descrizione", "details", "summary", "title", "text",
        "treatment", "trattamento", "terapia",
        "procedure", "procedura",
        "diagnosis", "diagnosi",
        "biopsia", "biopsy",
        "esame", "exam",
        "finding", "findings",
        "event", "type"
    ]

    def get_ci(d: dict, keys: list):
        """Case-insensitive key getter."""
        for k in d:
            for target in keys:
                if k.lower() == target.lower():
                    return d[k]
        return None

    # --- 4) Process each element in the list ---
    for ev in raw:
        if isinstance(ev, dict):

            data = get_ci(ev, date_keys)
            testo = get_ci(ev, text_keys)

            # If list of findings → join them
            if isinstance(testo, list):
                testo = " ".join(x for x in testo if isinstance(x, str))

            # If still missing text → search alternative fields
            if not testo:
                for fallback_key in ev:
                    if isinstance(ev[fallback_key], str) and ev[fallback_key].strip():
                        testo = ev[fallback_key].strip()
                        break

            if isinstance(data, list):
                data = data[0] if data else ""

            # Only accept if we have meaningful text
            if isinstance(testo, str) and testo.strip():
                out.append({
                    "data": str(data or "").strip(),
                    "testo": testo.strip()
                })

        # If the item is itself a list or dict → recurse
        elif isinstance(ev, (list, dict)):
            out.extend(_coerce_event_keys(ev))

    return out


# ---------------------------------------------------
# Helpers: normalization AAAAAAAAAAAAAAAAAAAAAAAAAAAA
# ---------------------------------------------------
def _strip_accents(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFD', s)
                   if unicodedata.category(ch) != 'Mn')

def _prep(s: str) -> str:
    """Lowercase + remove accents + normalize hyphens + collapse spaces."""
    s = _strip_accents(s or '').lower()
    s = s.replace('‐', '-').replace('–', '-').replace('—', '-')
    s = re.sub(r'\s+', ' ', s).strip()
    return s



# ---------------------------------------------------
# DEFINITIONS OF CANONICAL EVENTS
# ---------------------------------------------------
ALLOWED_EVENTS = {
    "Diagnosi": [
        "diagnosi"
    ],

    "Biopsia o Agobiopsia": [
        "biopsia",
        "agobiopsia",
        ("biopsia", "epatica"),
    ],

    "Inizio del trattamento di I linea": [
        re.compile(r"\bprima\s*linea\b"),
        re.compile(r"(?<!i)\bi\s*linea\b"),
    ],

    "Inizio del trattamento di II linea": [
        re.compile(r"\bseconda\s*linea\b"),
        re.compile(r"\bii\s*linea\b"),
    ],

    "Inizio del trattamento di III linea": [
        re.compile(r"\bterza\s*linea\b"),
        re.compile(r"\biii\s*linea\b"),
    ],

    "TC torace/total body": [
        "tc torace", "tac torace", "tc tb", "tac tb",
        "tc total body", "tac total body",
        ("tc", "torace"), ("tac", "torace"),
        ("tc", "mdc"), ("tac", "mdc"),
        ("tc", "c/t/a"), ("tc", "e/t/a"),
        ("ct", "torace"), ("ct", "chest")
    ],

    "Evidenze di discontinuità nella malattia oncologica toracica": [
        "discontinuita",
        "interruzione",
        "stop terapia",
        "sospensione"
    ],
}

# ---------------------------------------------------
# AUTO-ASSIGN I/II/III LINEA FROM "avvio"/"inizio"
# ---------------------------------------------------
def _assign_lines_for_avvio(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not events:
        return events

    candidate_indices = []
    for i, ev in enumerate(events):
        t = _prep(ev.get("testo") or "")
        if any(word in t for word in ("avvio", "avviat", "inizio terapia", "inizio trattamento")):
            if ev.get("data"):
                candidate_indices.append(i)

    if not candidate_indices:
        return events

    # Sort by date
    candidate_indices.sort(key=lambda idx: events[idx].get("data") or "")

    labels = [
        "Inizio del trattamento di I linea",
        "Inizio del trattamento di II linea",
        "Inizio del trattamento di III linea",
    ]

    for n, idx in enumerate(candidate_indices[:3]):
        events[idx]["testo"] = labels[n]
        events[idx]["_assigned_line"] = True

    # Drop additional "avvio" events beyond 3
    keep = set(candidate_indices[:3])
    final = []
    for i, ev in enumerate(events):
        if i in candidate_indices and i not in keep:
            continue
        final.append(ev)

    return final

# # ---------------------------------------------------
# # CANONICAL NORMALIZATION + FILTERING
# # ---------------------------------------------------
# def normalize_texts(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     normalized = []

#     for ev in events:
#         text = (ev.get("testo") or "").strip()
#         norm = _prep(text)
#         matched = False

#         # If already assigned to I/II/III linea → keep
#         if ev.get("_assigned_line"):
    #         normalized.append(ev)
    #         continue

    #     # Match against event dictionary
    #     for canon, variants in ALLOWED_EVENTS.items():
    #         for variant in variants:

    #             # 1) REGEX
    #             if isinstance(variant, re.Pattern):
    #                 if variant.search(norm):
    #                     ev["testo"] = canon
    #                     matched = True
    #                     break

    #             # 2) simple substring
    #             elif isinstance(variant, str):
    #                 if variant in norm:
    #                     ev["testo"] = canon
    #                     matched = True
    #                     break

    #             # 3) tuple = ALL must be present
    #             elif isinstance(variant, tuple):
    #                 if all(v in norm for v in variant):
    #                     ev["testo"] = canon
    #                     matched = True
    #                     break

    #         if matched:
    #             break

    #     # If still not matched → drop it
    #     if not matched:
    #         logger.debug(f"⚠️ Unmatched event dropped: '{text}' (normalized='{norm}')")
    #         continue

    #     normalized.append(ev)

    # return normalized




# Ensure the logs folder exists
os.makedirs("logs", exist_ok=True)

# -----------------------------
# Text cleaner for HTML tags/entities
# -----------------------------
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

_TAG_RE = re.compile(r"<[^>]+>")

def clean_report_text(text: str) -> str:
    if not text:
        return ""

    # Remove HTML tags
    try:
        text = BeautifulSoup(text, "html.parser").get_text(separator=" ")
    except Exception:
        text = _TAG_RE.sub(" ", text)

    # Decode html entities
    text = html.unescape(text)

    # Collapse multiple spaces (not newlines)
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize newlines
    text = re.sub(r"\s*\n\s*", "\n", text).strip()

    # Insert space before dates
    text = re.sub(
        r'(?<![\d\s(\[.\-])(?=\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ' ',
        text
    )

    # Insert missing space after "." unless decimal
    text = re.sub(
        r'(?<!\d)\.(?!(\s|$|\d))',
        '. ',
        text
    )

    return text


# DATE NORMALIZATION (MINIMAL SKELETON)
# -----------------------------
DATE_PATTERN = re.compile(
    r"""
    (
        \d{1,2}[/-]\d{1,2}[/-]\d{2,4} |
        \d{1,2}\.\d{1,2}\.\d{2,4}     |
        \d{4}-\d{1,2}-\d{1,2}         |
        \d{1,2}[/-]\d{4}             |
        (19|20)\d{2}
    )
    """,
    re.VERBOSE
)

def normalize_single_date(raw: str) -> str:
    raw = raw.strip()

    # month/year
    if re.fullmatch(r"\d{1,2}[/-]\d{4}", raw):
        month, year = re.split(r"[/-]", raw)
        return f"{int(year):04d}-{int(month):02d}-15"

    # year only
    if re.fullmatch(r"(19|20)\d{2}", raw):
        y = int(raw)
        return f"{y}-06-30"

    # full or ambiguous date
    try:
        dt = parser.parse(raw, dayfirst=True, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw


def normalize_all_dates_in_text(text: str) -> str:
    def repl(m):
        return normalize_single_date(m.group(0))
    return DATE_PATTERN.sub(repl, text)


# Only used to detect where to split (we don't clean dates)

DATE_REGEX = r"""
    (
        \d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4} |   # 07/02/2017 or 7-2-17
        \d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2} |   # 2017-02-07
        \d{1,2}[/\-\.]\d{4} |                 # 02/2017
        (19|20)\d{2}                         # 2017
    )
"""


# split only when "." is followed (optionally after spaces) by a date

def split_on_fullstop_date(text: str):
    """
    Produces lines by splitting ONLY on:  . <spaces> <DATE>
    Keeps date inside the new line.
    """
    # pattern: "." optional spaces date
    pattern = re.compile(rf'\.(\s*)({DATE_REGEX})', re.VERBOSE)

    segments = []
    last = 0

    for m in pattern.finditer(text):
        end_dot = m.start()  # position of "."
        seg = text[last:end_dot+1].strip()
        if seg:
            segments.append(seg)

        # next segment starts at the date
        last = m.start(2)  # group 2 = actual date match

    # final remainder
    tail = text[last:].strip()
    if tail:
        segments.append(tail)

    return segments


# FINAL PRETTY TIMELINE FORMATTER

def new_report(raw_text: str):
    """
    1. Clean text
    2. Split based on '.' followed by date
    3. One event per line, preserving multi-date sentences
    """
    cleaned = clean_report_text(raw_text)
    lines = split_on_fullstop_date(cleaned)

    # Final whitespace normalization
    pretty = []
    for line in lines:
        line = re.sub(r'\s+', ' ', line).strip()
        pretty.append(line)

    return "\n".join(pretty)

# FULL PREPROCESSING PIPELINE
# -----------------------------
def preprocess_for_llm(raw_text: str) -> str:
    t = clean_report_text(raw_text) 
    t = normalize_all_dates_in_text(t)
    t = new_report(t)
    return t


# -----------------------------
# UNIFIED PROMPT (SKELETON)
# -----------------------------
UNIFIED_PROMPT = """
Sei un estrattore di dati medici.

COMPITO:
Dal testo fornito, estrai SOLO i seguenti eventi, e la data annessa:
- Diagnosi: sempre una e una sola, spesso si trova all'inizio del documento, ma a volte è mancante.
- Biopsia: potrebbe essere ripetuta, o mancante.
- Inizio del trattamento di I linea: sicuramente presente.
- Inizio del trattamento di II linea: potrebbe essere presente o mancante.
- Inizio del trattamento di III linea: potrebbe essere presente o mancante.
- TC torace/total body: scritta come TAC o TC, potrebbe essere ripetuta più volte.
- Evidenze di discontinuità nella malattia oncologica toracica: spesso mancante.

OUTPUT OBBLIGATORIO:
Per ognuno degli eventi sopra, ritorna ESCLUSIVAMENTE un OGGETTO JSON con data ed etichetta dell'evento, con ESATTAMENTE i seguenti
campi:

[
  {"data": "YYYY-MM-DD", "testo": "etichetta evento"},
  ...
]

REGOLE:
- NON inventare dati non presenti.
- IGNORA GLI EVENTI NON RICHIESTI
- NON AGGIUNGERE TESTO EXTRA
- SEGUI CON PRECISIONE LE ISTRUZIONI.

TESTO:
<<<{TEXT}>>>

RISPOSTA JSON:
Devi rispondere SOLO con un array JSON valido.
NON AGGIUNGERE spiegazioni, testo, commenti, markdown,
titoli, sintesi o note.
NON inserire alcun campo diverso da "data" e "testo".
La risposta deve iniziare con "[" e terminare con "]".
"""


# -----------------------------
# LLM CALL WRAPPER
# -----------------------------
def run_unified_prompt(preprocessed_text: str) -> str:
    llm = get_llm_processor()
    msg = UNIFIED_PROMPT.replace("{TEXT}", preprocessed_text)

    logger.info(f"[UNIFIED] prompt preview:\n{msg[:1500]}")
    resp = llm.generate_response(msg)

    print("\n\n====== RAW LLM RESPONSE ======\n", resp, "\n==============================\n\n")
    return resp

def force_json_array(text: str) -> list:
    """
    Ensures output is a JSON array, even if the model returned narrative text.
    """
    # Try direct JSON
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return arr
    except:
        pass

    # Try to extract first array anywhere in the text
    m = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', text)
    if m:
        try:
            return json.loads(m.group(0))
        except:
            pass

    # ABSOLUTE LAST RESORT: call a repair model
    llm = get_llm_processor()
    repair_prompt = f"""
Converti il seguente testo in un array JSON valido con oggetti {{ "data": "...", "testo": "..." }}.
NON aggiungere testo. SOLO l'array JSON.

TESTO:
<<<
{text}
>>>

RISPOSTA SOLO JSON:
"""
    repaired = llm.generate_response(repair_prompt)
    try:
        return json.loads(repaired)
    except:
        return []




# -----------------------------
# PARSE LLM RESPONSE (SKELETON)
# -----------------------------
def parse_unified_response(resp: str):
    """
    Extract JSON array from Llama-style response:
    {"model": "...", "response": "[ ... ]"}
    And fallback to raw text if necessary.
    """
    # First try to load the outer JSON wrapper returned by Ollama
    try:
        data = json.loads(resp)
        # If the model wrapped output inside "response"
        if isinstance(data, dict) and "response" in data:
            inner = data["response"].strip()
            # Remove <<< >>> or markdown fences if present
            inner = inner.replace("<<<", "").replace(">>>", "")
            inner = inner.replace("```json", "").replace("```", "")
            return force_json_array(inner)
    except:
        pass

    # If not wrapped, treat as raw string
    cleaned = resp.replace("<<<", "").replace(">>>", "")
    cleaned = cleaned.replace("```json", "").replace("```", "")
    return force_json_array(cleaned)



# -----------------------------
# PUBLIC API
# -----------------------------
def extract_timeline_from_text(text: str) -> List[Dict[str, Any]]:
    pre = preprocess_for_llm(text)
    raw = run_unified_prompt(pre)

    parsed = parse_unified_response(raw)      # ensures JSON array
    cleaned = _coerce_event_keys(parsed)      # normalizes keys

    return cleaned


def extract_timeline_from_excel(excel_file: Union[str, bytes]) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(excel_file)
    except Exception:
        df = pd.read_csv(excel_file)

    if df.empty:
        return []

    colmap = {str(c).strip().lower(): c for c in df.columns}
    if "report" not in colmap:
        return []

    report_col = colmap["report"]
    results = []

    for idx, row in df.iterrows():
        rid = row.get("id", idx)
        text = str(row.get(report_col) or "")
        events = extract_timeline_from_text(text)
        results.append({"id": str(rid), "events": events})

    return results
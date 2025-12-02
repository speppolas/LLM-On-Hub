## BEFORE DROPPING LOW CONFIDENCE, WITH DATES NORMALISATION AT THE END
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

def _clean_report_text(text: str) -> str:
    """
    Normalizza il report prima del prompt LLM:
    - rimuove tag HTML
    - decodifica entità HTML (&egrave; -> è)
    - compatta spaziature
    """
    if not text:
        return ""

    if BeautifulSoup is not None:
        try:
            text = BeautifulSoup(text, "html.parser").get_text(separator=" ")
        except Exception:
            text = _TAG_RE.sub(" ", text)
    else:
        text = _TAG_RE.sub(" ", text)

    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    return text

# -----------------------------
# JSON extraction / sanitation
# -----------------------------
def _extract_first_json_array(text: str) -> Optional[str]:
    """
    Estrae il *primo* array JSON ben bilanciato presente nel testo.
    Gestisce testo extra prima/dopo e blocchi ```json ... ``` o ``` ... ```.
    """
    # 1) fenced ```json ... ```
    m = re.search(r"```json\s*(\[[\s\S]*?\])\s*```", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 1b) fenced generico ```
    m = re.search(r"```\s*(\[[\s\S]*?\])\s*```", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 2) ricerca manuale del primo array bilanciato
    in_str = False
    esc = False
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == '[':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ']':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        return text[start:i+1].strip()
    return None

def _extract_first_json_object(text: str) -> Optional[str]:
    """
    Estrae il *primo* oggetto JSON ben bilanciato presente nel testo.
    Gestisce testo extra e blocchi codefence.
    """
    # fenced ```json ... ```
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # fenced generico ```
    m = re.search(r"```\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # ricerca manuale del primo oggetto
    in_str = False
    esc = False
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        return text[start:i+1].strip()
    return None

def _load_json_safely(raw: str) -> Any:
    """
    Tenta vari approcci per decodificare JSON da stringa rumorosa.
    """
    if raw is None:
        raise ValueError("Nessun JSON trovato.")
    try:
        return json.loads(raw)
    except Exception:
        try:
            return json.loads(raw.replace('\\"', '"'))
        except Exception as e:
            raise ValueError(f"JSON non valido: {e}")

def _get_ci(d: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """
    Recupera valore stringa da dizionario in modo case-insensitive,
    accettando anche varianti con underscore/spazi.
    """
    if not isinstance(d, dict):
        return None
    norm = {}
    for k, v in d.items():
        nk = re.sub(r'[\s_]+', '', str(k)).lower()
        norm[nk] = v
    for k in keys:
        nk = re.sub(r'[\s_]+', '', k).lower()
        val = norm.get(nk)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None

def _coerce_event_keys(raw_events: Any) -> List[Dict[str, Any]]:
    """
    Converte varie forme di eventi in [{data: str, testo: str}], scartando il resto.

    - Accetta wrapper tipo {"events":[...]}, {"items":[...]}, {"timeline":[...]}.
    - DATA: data, date, data_evento, when, giorno, day
    - TESTO: testo, evento, description/descrizione/details/summary/title/text,
             trattamento/terapia, procedura, diagnosi, biopsia, esame, label/name
    """
    if isinstance(raw_events, dict):
        for k in ("events", "items", "predictions", "timeline", "result", "output"):
            v = raw_events.get(k)
            if isinstance(v, list):
                raw_events = v
                break

    if not isinstance(raw_events, list):
        raise ValueError(f"Expected a JSON array, got {type(raw_events)}")

    out: List[Dict[str, Any]] = []
    for ev in raw_events:
        if not isinstance(ev, dict):
            continue

        data = _get_ci(ev, [
            "data", "date", "data_evento", "when", "giorno", "day"
        ])

        testo = _get_ci(ev, [
            "testo", "evento",
            "description", "descrizione", "details",
            "summary", "title", "text",
            "treatment", "trattamento", "terapia",
            "procedura", "procedure",
            "diagnosi", "diagnosis",
            "biopsy", "biopsia",
            "esame",
            "label", "name"
        ])

        if not testo:
            parts = []
            for k in ("event_type", "type", "test_name", "procedure_name", "medication", "medicazione"):
                v = _get_ci(ev, [k])
                if v:
                    parts.append(v)
            for k in ("details", "description", "descrizione"):
                v = _get_ci(ev, [k])
                if v:
                    parts.append(v)
            if parts:
                testo = " ".join(parts)

        if not testo:
            for k in ev:
                if isinstance(ev[k], str) and ev[k].strip():
                    testo = ev[k].strip()
                    break

        if isinstance(data, str) and isinstance(testo, str):
            out.append({"data": data.strip(), "testo": testo.strip()})

    return out

def _validate_events_schema(events: Any) -> None:
    """
    Verifica che ogni elemento abbia ALMENO le chiavi 'data' e 'testo' stringa.
    """
    if not isinstance(events, list):
        raise ValueError(f"Expected list, got {type(events)}")
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            raise ValueError(f"Event {i} is not a dict")
        if "data" not in ev or "testo" not in ev:
            raise ValueError(f"Event {i} missing required keys: {ev.keys()}")
        if not isinstance(ev["data"], str) or not isinstance(ev["testo"], str):
            raise ValueError(f"Event {i} fields must be strings: {ev}")

def clean_llm_json_response(response: str) -> List[Dict[str, Any]]:
    """
    Estrae un array JSON valido da una risposta LLM rumorosa (con eventuale wrapper {"response": ...}),
    mappa chiavi comuni verso {data, testo} e convalida.
    """
    # 0) decodifica involucro {"response": "..."} se presente
    try:
        outer = json.loads(response)
        raw_inner = outer.get("response", "")
    except json.JSONDecodeError:
        raw_inner = response

    # 1) estrai array JSON da blocco codefence o testo
    snippet = _extract_first_json_array(raw_inner)
    candidate = snippet if snippet is not None else raw_inner.strip()

    # 2) parse
    parsed = _load_json_safely(candidate)

    # 3) normalizza chiavi verso {data, testo}
    events = _coerce_event_keys(parsed)

    # 4) valida schema minimo
    _validate_events_schema(events)

    return events

# -----------------------------
# Date normalization (coarse-aware)
# -----------------------------
DATE_FULL = re.compile(r'\b(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})\b')   # 2021-05-14 / 2021/5/14
DATE_DMY  = re.compile(r'\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{2,4})\b')  # 14/10/2014
DATE_MY   = re.compile(r'\b(\d{1,2})[-/\.](\d{4})\b')                   # 05/2021
DATE_Y    = re.compile(r'\b(19|20)\d{2}\b')                             # 1900..2099
DATE_RANGE_DMY = re.compile(r'\b(\d{1,2})\s*[-–—]\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\b')
DATE_RANGE_FULL_DMY = re.compile(
    r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\s*[-–—]\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\b'
)
DATE_RANGE_FULL_ISO = re.compile(
    r'\b(19|20)\d{2}-\d{1,2}-\d{1,2}\s*[-–—]\s*(19|20)\d{2}-\d{1,2}-\d{1,2}\b'
)

def _to_iso(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"

def _valid_year(y: int) -> bool:
    return 1900 <= y <= 2100

def _parse_coarse_date(s: str) -> Tuple[Optional[str], str]:
    """
    Riconosce:
      - YYYY-MM-DD / DD-MM-YYYY / MM-YYYY / YYYY
      - Range DD-DD/MM/YYYY (prende il primo giorno)
      - Range completo DD/MM/YYYY - DD/MM/YYYY (prende la più precoce)
      - Range ISO YYYY-MM-DD - YYYY-MM-DD (prende la più precoce)
    Restituisce (iso_yyyy_mm_dd, granularity: 'day'|'month'|'year'|'unknown').
    Per date senza giorno/mese usa sentinelle (15 per mese, 30/06 per anno).
    """
    s = (s or '').strip()
    if not s:
        return None, "unknown"

    m = DATE_RANGE_FULL_ISO.search(s)
    if m:
        parts = re.findall(r'(?:19|20)\d{2}-\d{1,2}-\d{1,2}', s)
        if len(parts) >= 2:
            try:
                dl = parser.parse(parts[0]).date()
                dr = parser.parse(parts[1]).date()
                dmin = min(dl, dr)
                if _valid_year(dmin.year):
                    return dmin.strftime("%Y-%m-%d"), "day"
            except Exception:
                pass

    m = DATE_RANGE_FULL_DMY.search(s)
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()
        y1 = int(y1); y1 = y1 + 2000 if y1 < 100 else y1
        y2 = int(y2); y2 = y2 + 2000 if y2 < 100 else y2
        try:
            from datetime import date
            dl = date(y1, int(mo1), int(d1))
            dr = date(y2, int(mo2), int(d2))
            dmin = dl if dl <= dr else dr
            if _valid_year(dmin.year):
                return dmin.strftime("%Y-%m-%d"), "day"
        except Exception:
            pass

    m = DATE_RANGE_DMY.search(s)
    if m:
        d1, d2, mo, y = m.groups()
        y = int(y)
        y = y + 2000 if y < 100 else y
        if _valid_year(y):
            return _to_iso(y, int(mo), int(d1)), "day"

    m = DATE_FULL.search(s)
    if m:
        y, mo, d = map(int, m.groups())
        if _valid_year(y):
            return _to_iso(y, mo, d), "day"

    m = DATE_DMY.search(s)
    if m:
        d, mo, y = m.groups()
        y = int(y)
        y = y + 2000 if y < 100 else y
        if _valid_year(y):
            return _to_iso(y, int(mo), int(d)), "day"

    m = DATE_MY.search(s)
    if m:
        mo, y = map(int, m.groups())
        if _valid_year(y):
            return _to_iso(y, mo, 15), "month"

    m = DATE_Y.search(s)
    if m:
        y = int(m.group(0))
        if _valid_year(y):
            return _to_iso(y, 6, 30), "year"

    try:
        dt = parser.parse(s, dayfirst=True, fuzzy=True)
        if _valid_year(dt.year):
            return dt.strftime("%Y-%m-%d"), "day"
        return None, "unknown"
    except Exception:
        return None, "unknown"

def normalize_dates(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizza event["data"] in ISO YYYY-MM-DD e salva granularità in _granularity.
    """
    normalized = []
    for evt in events:
        raw_date = evt.get("data", "")
        iso, gran = _parse_coarse_date(raw_date)
        evt["data"] = iso
        evt["_granularity"] = gran
        normalized.append(evt)
    return normalized

# -----------------------------
# Event canonicalization
# -----------------------------
def _strip_accents(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')

def _prep(s: str) -> str:
    s = _strip_accents(s or '').lower()
    s = s.replace('‐', '-').replace('-', '-').replace('–', '-').replace('—', '-')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

ALLOWED_EVENTS: Dict[str, List[Union[str, Tuple[str, ...], re.Pattern]]] = {
    "Diagnosi": [ "diagnosi" ],
    "Biopsia o Agobiopsia": [ ("biopsia"), ("agobiopsia") ],
    "Inizio del trattamento di I linea": [
        re.compile(r"\bprima\s*linea\b"), re.compile(r"(?<!i)\bi\s*linea\b"),
    ],
    "Inizio del trattamento di II linea": [
        re.compile(r"\bseconda\s*linea\b"), re.compile(r"\bii\s*linea\b"),
    ],
    "Inizio del trattamento di III linea": [
        re.compile(r"\bterza\s*linea\b"), re.compile(r"\biii\s*linea\b"),
    ],
    "TC torace/total body": [
        ("tac", "torace"), ("tc", "torace"),
        ("tac", "tb"), ("tc", "tb"),
        ("tac", "total-body"), ("tc", "total-body"),
        ("tac", "mdc"), ("tc", "mdc"),
        ("tc", "c/t/a"), ("tc", "e/t/a"),
        ("tac", "c/t/a"),
        "tc tb e/o torace", "tc torace", "tac torace", "tc tb", "tctb", "tac tb",
        "tc total body", "tac total body", "tc totale corpo", "tc totale torace",
        "tac totale torace", "tac totale corpo",
        ("ct", "torace"), ("ct", "tb"), ("ct", "total"), ("ct", "chest"),
        ("ct", "c/t/a"), ("ct", "e/t/a"),
    ],
    "Evidenze di discontinuità nella malattia oncologica toracica": [
        "discontinuita", "interruzione", "interrotto", "stop", "sospensione"
    ],
}

def _assign_lines_for_avvio(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trasforma eventi con 'avvio/inizio' in linee I/II/III in ordine cronologico (max 3).
    Non tocca eventi che già sono linee esplicite.
    """
    if not events:
        return events

    cand_idx = []
    for i, ev in enumerate(events):
        t = _prep(ev.get("testo") or "")
        if any(k in t for k in ("avvio", "avviata", "avviato", "avvi", "inizio terapia", "inizio trattamento")):
            cand_idx.append(i)

    if not cand_idx:
        return events

    cand_idx = [i for i in cand_idx if events[i].get("data")]
    if not cand_idx:
        return events

    cand_idx.sort(key=lambda i: events[i].get("data") or "")

    labels = [
        "Inizio del trattamento di I linea",
        "Inizio del trattamento di II linea",
        "Inizio del trattamento di III linea",
    ]

    kept = set()
    drops = set()
    for rank, i in enumerate(cand_idx):
        if rank < 3:
            events[i]["testo"] = labels[rank]
            events[i]["_assigned_line"] = True
            kept.add(i)
        else:
            drops.add(i)

    if drops:
        events = [e for j, e in enumerate(events) if j not in drops]

    return events

def normalize_texts(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mappa event["testo"] ai nomi canonici. Scarta gli eventi che non matchano.
    """
    normalized: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("_assigned_line") and ev.get("testo") in (
            "Inizio del trattamento di I linea",
            "Inizio del trattamento di II linea",
            "Inizio del trattamento di III linea",
        ):
            normalized.append(ev)
            continue

        original = (ev.get("testo") or "").strip()
        raw_norm = _prep(original)
        matched = False

        for canon, variants in ALLOWED_EVENTS.items():
            for variant in variants:
                if isinstance(variant, re.Pattern):
                    if variant.search(raw_norm):
                        ev["testo"] = canon
                        matched = True
                        break
                elif isinstance(variant, str):
                    if variant in raw_norm:
                        ev["testo"] = canon
                        matched = True
                        break
                else:
                    if isinstance(variant, tuple) and all(sub in raw_norm for sub in variant):
                        ev["testo"] = canon
                        matched = True
                        break
            if matched:
                break

        if not matched:
            logger.debug(f'❓ No match for "{original}" (norm="{raw_norm}") against any canonical variant.')
            continue

        normalized.append(ev)

    return normalized

# -----------------------------
# PROMPTS - raw strings, NO normalizzazione date dal LLM
# -----------------------------
PROMPT_A_LINES = r'''
Sei un oncologo toracico e ricevi un documento contenente la storia clinica di un paziente affetto da tumore al polmone.
Esegui con cura i seguenti compiti, nell'ordine:

1. Leggi il documento che segue riga per riga e comprendi la storia clinica del paziente
2. Fermati ogni volta che viene nominato un nuovo farmaco: Gefitinib, Erlotinib, Osimertinib, Afatinib o Poziotinib (non inventare mensioni se non vengono nominati)
3. In corrispondenza di questa menzione, recupera la data annessa, e associa una linea di trattamento (in ordine: I, II, III). Se l'anno non è specificato per quella esatta data, deducilo dalle date circostanti.
4. Raggiunta la III linea fermati. Ciò che viene dopo è irrilevante.

Vincoli:
- Aggiustamenti di dose o mantenimento con lo stesso farmaco NON determinano una nuova linea.
- Sicuramente nel documento è presente l'avvio della I linea, ma la II e III linea è probabile che manchino. In questo caso, NON inventarle e NON riportarle.
- Per ogni linea, esiste UNA SOLA (o zero in caso di II e III linea mancanti) data associata, dunque il tuo JSON conterrà AL MASSIMO 3 tuple (linea, data).

Rispondi SOLO con un oggetto JSON:
{
  "lines": [
    {"line":"I|II|III", "date_raw":"string",
     "evidence":{"quote":"<=160c", "char_start":0, "char_end":0},
     "confidence":"high|medium|low"}
  ],
  "third_line":{"present":true|false, "char_start":0, "date_raw":"string|null",
                "confidence":"high|medium|low"}
}

Vincoli: NON normalizzare nè modificare le date. Copiale esattamente come scritte.
Se non riesci a identificare una data, osserva le date circostanti e prova a dedurla.

Esempio di JSON corretto:
{
  "lines": [
    {"line":"I", "date_raw":"05/06/2014", "evidence":{"quote":"Adeguatamente informata sul piano di cura e sul programma di trattamento con Afatinib, la paziente accetta di partecipare allo studio con Afatinib05/06 - 03/10/2014 terapia con Afatinib all'interno di trial Divisionale."}, "confidence":"high"}
    {"line":"II", "date_raw":"17/4/2019", "evidence":{"quote":"17/4/2019 - 01/04/2020 Osimertinib"}, "confidence":"high"}
    {"line":"III", "date_raw":"08/04/2020", "evidence":{"quote":"08/04/2020 - 07/07/2020 CT secondo Carboplatino + Pemetrexed per 4 cicli"}, "confidence":"high"}
  ],
  "third_line":{"present":true, "char_start":0, "date_raw":"08/04/2020", "confidence":"high"}
}

'''

PROMPT_B_CTS_RECIST = r'''
Sei un oncologo toracico e ricevi un documento contenente la storia clinica di un paziente affetto da tumore al polmone.
Esegui con cura i seguenti compiti, nell'ordine:

1. Leggi il documento che segue riga per riga e comprendi la storia clinica del paziente
2. Fermati ogni volta che viene nominata: "TAC" o "TC" (non ci interessano altri esami di imaging come RMN, PET, RX, ecografie...)
3. In corrispondenza di questa menzione, recupera la data annessa così come è scritta, senza modificarla
4. Procedi a leggere la descrizione successiva alla menzione ed etichetta la TAC corrente secondo questi criteri:
    - CR: Scomparsa di tutte le lesioni (tutti i linfonodi prima identificati come patologici devono avere diametro inferiore ai 10 mm), negativizzazione dei marker tumorali sierici
    - PR: Riduzione della somma dei diametri di tutte le lesioni pari almeno al 30%
    - PD: Incremento relativo della somma dei diametri di almeno il 20% e in assoluto di almeno 5 mm, comparsa di almeno una nuova lesione, inequivocabile progressione di una lesione non target.
    - SD: Tutti i casi non appartenenti alle descrizioni precedenti oppure persistenza di una lesione non target oppure marker sierici sopra la norma anche in assenza di lesioni radiologicamente evidenti
    - NE: Non è possibile classificare la risposta per mancanza di dati
5. Continua la lettura, ripetendo il procedimento dal punto 2 per TUTTE le TAC che incontri.

Ogni TAC avrà una e una sola response_recist, escluse le tac basali, che non possono essere valutate.

JSON richiesto:
{
  "cts":[
    {"ct_id":"CT001", "date_raw":"string",
     "evidence":{"quote":"<=160c","char_start":0,"char_end":0},
     "snippet":"<=350c","anatomy":["torace"],
     "line_context":"I|II|unknown",
     "response_recist":"CR|PR|SD|PD|NE",
     "basis":{"compared_to":"CT000|null","rationale":"<=220c"}}
  ],
  "per_line_summary":[
    {"line":"I","best_response":"CR|PR|SD|PD|NE","first_pd_date_raw":"string|null"},
    {"line":"II","best_response":"CR|PR|SD|PD|NE","first_pd_date_raw":"string|null"}
  ]
}

Vincoli: Verifica che l'evento con la data corrispondente sia presente nel testo, se non è presente, non riportarlo.
E' richiesta massima precisione nell'identificazione delle date corrette, non modificarle o inventarle per alcun motivo (minimizza Falsi Positivi e Falsi Negativi).

Esempio di JSON corretto:
{
  "cts":[
    {
  "ct_id": "CT001", "date_raw": "27/02/2019",
  "evidence": {"quote": "dimensionalmente invariata la nota lesione espansiva del LSS (3.8 x 1 cm)", "char_start": 168, "char_end": 250},
  "snippet": "TC (27/02/2019): dimensionalmente invariata la nota lesione espansiva del LSS (3.8 x 1 cm); invariato l'ispessimento cortico-pleurico e le alterazioni micronodulari bilaterali; invariate le millimetriche adenopatie residue in paratracheale inferiore; invariate le lesioni ripetitive residue a livello epatico.",
  "anatomy": ["torace", "fegato", "pleura"],
  "line_context": I",
  "response_recist": "SD",
  "basis": {"compared_to": "CT000", "rationale": "invariata la nota lesione espansiva del LSS; invariate le lesioni residue epatiche"
  }
}

    '''

PROMPT_C_OTHER = r'''
Sei un oncologo toracico e ricevi un documento contenente la storia clinica di un paziente affetto da tumore al polmone.
Esegui con cura i seguenti compiti, nell'ordine:
1. Leggi il documento che segue riga per riga e comprendi la storia clinica del paziente
2. Estrai TUTTI gli eventi relativi a:
3. Fermati ogni volta che viene nominato uno dei seguenti eventi:
    - Diagnosi: è sempre una e una sola, spesso si trova all'inizio del documento, ma a volte è mancante. Se non è esplicitamente menzionata, non inventarla)
    - Biopsia o Agobiopsia: potrebbe essere ripetuta, o potrebbe essere mancante
    - Discontinuità nella malattia oncologica toracica: spesso mancante, se non è presente, non inventarla
4. In corrispondenza dell'evento, recupera la data annessa esattamente come è scritta, senza modificarla
5. Continua la lettura, ripetendo il procediento dal punto 2.


Rispondi con un ARRAY JSON, ogni oggetto:
[{"data":"string","testo":"etichetta evento"}]

Vincoli: Le date devono essere una sottostringa esatta del testo, non modificarle, non inferirle e non inventarle.
Verifica che l'evento con la data corrispondente sia presente nel testo, se non è presente, non riportarlo.
Non inventare eventi non menzionati, e non ignorare quelli menzionati.
E' richiesta massima precisione nell'identificazione delle date corrette, non modificarle o inventarle per alcun motivo (minimizza Falsi Positivi e Falsi Negativi).

Esempio di JSON corretto:

Se il testo è: "03/2014 Comparsa di linfoadenopatia sovraclaveare destra."
Restituisci: {"data":"03/2014","testo":"Diagnosi"},

Se il testo è: "18/03/2019 Eseguita biopsia di adenopatia sovraclaveare sinistra richiesta caratterizzazione molecolare su tessuto da biopsia"
Restituisci: {"data":"18/03/2019","testo":"Biopsia o Agobiopsia"},

Se il testo è: "Quadro sostanzialmente invariato rispetto al precedente controllo del 30.11.201714/08/2018 SOSPESA terapia con osimertinib (Tagrisso) 80 mg 1 cp die per neutropenia grave."
Restituisci: {"data":"14/08/2018","testo":"Discontinuità nella malattia oncologica toracica"}

'''

# -----------------------------
# LLM helpers
# -----------------------------
def _llm_call(prompt: str, document: str, phase: str) -> str:
    llm = get_llm_processor()
    msg = f"{prompt}\n\nTESTO:\n<<<\n{document}\n>>>\n\nJSON:"
    logger.info(f"[LLM {phase}] prompt preview:\n{msg[:1500]}")
    resp = llm.generate_response(msg)
    # unique filename per call (ms precision)
    ts = int(time.time() * 1000)
    debug_file = f"logs/llm_{phase}_debug_{ts}.json"
    try:
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump({"phase": phase, "prompt": msg[:8000], "response": resp[:8000]}, f,
                      ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("[LLM %s] failed to write debug file", phase)
    return resp

def _parse_lines_response(resp: str) -> Dict[str, Any]:
    """
    Parsing robusto dell'output di PROMPT A.
    """
    # alcune LLM wrappano in {"response": "..."}
    try:
        outer = json.loads(resp)
        raw = outer.get("response", resp)
    except Exception:
        raw = resp

    obj_str = _extract_first_json_object(raw)
    data = _load_json_safely(obj_str) if obj_str else {}
    # forma attesa: {"lines":[...], "third_line":{...}}
    lines = data.get("lines") or []
    third = data.get("third_line") or {"present": False}
    # sanitize min
    out_lines = []
    for it in lines:
        if not isinstance(it, dict):
            continue
        line = (it.get("line") or "").strip().upper()
        if line not in ("I", "II", "III"):
            continue
        date_raw = it.get("date_raw")
        ev = it.get("evidence") or {}
        cs, ce = ev.get("char_start"), ev.get("char_end")
        conf = it.get("confidence") or "low"
        out_lines.append({
            "line": line,
            "date_raw": date_raw,
            "evidence": {"quote": ev.get("quote"), "char_start": cs, "char_end": ce},
            "confidence": conf
        })
    tl = {
        "present": bool(third.get("present")),
        "char_start": third.get("char_start"),
        "date_raw": third.get("date_raw"),
        "confidence": third.get("confidence") or "low"
    }
    return {"lines": out_lines, "third_line": tl}

def _parse_cts_response(resp: str) -> Dict[str, Any]:
    try:
        outer = json.loads(resp)
        raw = outer.get("response", resp)
    except Exception:
        raw = resp
    obj_str = _extract_first_json_object(raw)
    data = _load_json_safely(obj_str) if obj_str else {}
    cts = data.get("cts") or []
    pls = data.get("per_line_summary") or []
    # sanitize rapido
    out_cts = []
    for it in cts:
        if not isinstance(it, dict):
            continue
        out_cts.append({
            "ct_id": it.get("ct_id"),
            "date_raw": it.get("date_raw"),
            # niente date_norm dall'LLM
            "evidence": it.get("evidence") or {},
            "snippet": it.get("snippet"),
            "anatomy": it.get("anatomy") or [],
            "line_context": it.get("line_context") or "unknown",
            "response_recist": it.get("response_recist"),
            "basis": it.get("basis") or {}
        })
    # opzionale: rinominiamo chiave summary delle date in *_raw per coerenza
    for x in pls:
        if "first_pd_date" in x and "first_pd_date_raw" not in x:
            x["first_pd_date_raw"] = x.get("first_pd_date")
            del x["first_pd_date"]
    return {"cts": out_cts, "per_line_summary": pls}

# -----------------------------
# Small post guards
# -----------------------------
RECIST_DOWNMAP = [
    (re.compile(r"\b(invariat[ao]|stazionari[ao]|sovrapponibil[ei])\b", re.I), "SD"),
    (re.compile(r"\b(nuov[ae]\s+lesion|progression|aument[oi])\b", re.I), "PD"),
    (re.compile(r"\b(scomparsa)\b", re.I), "CR"),
    (re.compile(r"\b(liev[e|a]|minim[ao])\s+riduzion", re.I), "SD"),
    (re.compile(r"\b(>=?\s*30%|30\s*%|trenta\s*%)\b", re.I), "PR"),
    (re.compile(r"\b(marcat[ao]\s+riduzion)\b", re.I), "PR"),
]

def _normalize_date_from_quote(date_raw: Optional[str]) -> Optional[str]:
    if not date_raw:
        return None
    iso, _ = _parse_coarse_date(date_raw)
    return iso

def _fix_ct_dates(ct: Dict[str, Any]) -> None:
    """
    Imposta date_norm dalle date raw del LLM (nessun confronto con l'LLM).
    """
    ct["date_norm"] = _normalize_date_from_quote(ct.get("date_raw"))

def _sanitize_recist_from_snippet(ct: Dict[str, Any]) -> None:
    resp = (ct.get("response_recist") or "").upper()
    snippet = ct.get("snippet") or ""
    if not resp:
        return
    for rx, mapped in RECIST_DOWNMAP:
        if rx.search(snippet):
            if mapped == "SD" and resp in ("PR", "CR"):
                ct["response_recist"] = "SD"; ct["_response_adjusted"] = True; return
            if mapped == "PD" and resp in ("PR", "CR", "SD"):
                ct["response_recist"] = "PD"; ct["_response_adjusted"] = True; return
            if mapped == "CR" and resp != "CR":
                ct["response_recist"] = "CR"; ct["_response_adjusted"] = True; return
            if mapped == "PR" and resp in ("SD", "NE"):
                ct["response_recist"] = "PR"; ct["_response_adjusted"] = True; return

def _dedup_cts(cts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not cts:
        return cts
    def key(ct):
        dn = ct.get("date_norm") or ""
        anat = ",".join(sorted([a.lower() for a in (ct.get("anatomy") or [])]))
        return dn, anat
    seen = {}
    for ct in sorted(cts, key=lambda x: x.get("date_norm") or ""):
        k = key(ct)
        if k in seen:
            prev = seen[k]
            if len((ct.get("snippet") or "")) > len((prev.get("snippet") or "")):
                seen[k] = ct
        else:
            seen[k] = ct
    return list(seen.values())

def _normalize_lines_dates(lines_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggiunge date_norm calcolata da date_raw per ogni linea (se possibile).
    """
    out = {"lines": [], "third_line": dict(lines_info.get("third_line") or {})}
    for ln in lines_info.get("lines", []):
        ln = dict(ln)
        ln["date_norm"] = _normalize_date_from_quote(ln.get("date_raw"))
        out["lines"].append(ln)
    if "date_raw" in out["third_line"]:
        out["third_line"]["date_norm"] = _normalize_date_from_quote(out["third_line"].get("date_raw"))
    return out

# NEW: minimal helper to convert lines to regular display events
def _lines_to_events(lines_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Converte le linee (I/II/III) in eventi {data, testo} per la timeline.
    """
    label_map = {
        "I": "Inizio del trattamento di I linea",
        "II": "Inizio del trattamento di II linea",
        "III": "Inizio del trattamento di III linea",
    }
    events: List[Dict[str, Any]] = []
    for ln in lines_info.get("lines", []):
        line_code = (ln.get("line") or "").strip().upper()
        label = label_map.get(line_code)
        if not label:
            continue
        date_val = ln.get("date_norm") or (ln.get("date_raw") or "")
        events.append({
            "data": date_val,
            "testo": label,
            "_from_lines": True  # flag interno, non usato in export ma utile per debug
        })
    return events

# -----------------------------
# Flow: 3 prompt
# -----------------------------
def _run_prompt_lines(full_text: str) -> Dict[str, Any]:
    resp = _llm_call(PROMPT_A_LINES, full_text, phase="A_lines")
    return _parse_lines_response(resp)

def _truncate_at_third_line(full_text: str, lines_info: Dict[str, Any]) -> str:
    tl = lines_info.get("third_line") or {}
    if tl.get("present") and tl.get("confidence") != "low" and isinstance(tl.get("char_start"), int):
        cut = tl["char_start"]
        if 0 < cut <= len(full_text):
            return full_text[:cut]
    return full_text

def _run_prompt_cts_recist(trunc_text: str, lines_info: Dict[str, Any]) -> Dict[str, Any]:
    # Build a tiny header with line starts to anchor the model
    lines_ctx_rows = []
    for ln in sorted(lines_info.get("lines", []), key=lambda x: (x.get("line"), x.get("date_norm") or "")):
        lines_ctx_rows.append(f'{ln.get("line")}:{ln.get("date_norm") or "null"}@{ln.get("evidence",{}).get("char_start")}')
    header = "INIZI_LINEE: " + ", ".join(lines_ctx_rows) + "\n"
    resp = _llm_call(PROMPT_B_CTS_RECIST, header + trunc_text, phase="B_cts")
    return _parse_cts_response(resp)

def _run_prompt_other_events(trunc_text: str) -> List[Dict[str, Any]]:
    # Only Prompt C here; returns a plain ARRAY of {data, testo}
    resp = _llm_call(PROMPT_C_OTHER, trunc_text, phase="C_other")
    try:
        outer = json.loads(resp)
        inner = outer.get("response", resp)
    except Exception:
        inner = resp
    arr = _extract_first_json_array(inner) or inner.strip()
    parsed = _load_json_safely(arr)
    events = _coerce_event_keys(parsed)
    _validate_events_schema(events)
    return events

# -----------------------------
# Pipeline helpers (nuovo flow)
# -----------------------------
def _merge_events(other_events: List[Dict[str, Any]], cts_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Converte CTs in eventi canonici + campi extra RECIST e unisce con other_events.
    """
    # 1) normalizza OTHER (diagnosi/biopsia/discontinuità)
    dated_other = normalize_dates(other_events)
    dated_other = _assign_lines_for_avvio(dated_other)
    norm_other = normalize_texts(dated_other)
    # escludi esplicitamente eventuali CT o linee (difesa)
    norm_other = [e for e in norm_other if e.get("testo") not in (
        "TC torace/total body",
        "Inizio del trattamento di I linea",
        "Inizio del trattamento di II linea",
        "Inizio del trattamento di III linea",
    )]

    # 2) CTs → eventi canonici
    cts = cts_pack.get("cts") or []
    for ct in cts:
        _fix_ct_dates(ct)
        _sanitize_recist_from_snippet(ct)

    cts = _dedup_cts(cts)

    ct_events: List[Dict[str, Any]] = []
    for ct in cts:
        ev = {
            "data": ct.get("date_norm") or (ct.get("date_raw") or ""),
            "testo": "TC torace/total body",
            # campi extra per frontend/export:
            "risposta_recist": (ct.get("response_recist") or "").upper() or None,
            "basis_compared_to": (ct.get("basis") or {}).get("compared_to"),
            "basis_note": (ct.get("basis") or {}).get("rationale"),
            "_ct_id": ct.get("ct_id"),
            "_line_context": ct.get("line_context"),
            "_snippet": ct.get("snippet"),
        }
        ct_events.append(ev)

    # 3) merge + sort
    merged = norm_other + ct_events
    merged = normalize_dates(merged)  # assicura ISO per tutti prima del sort
    logger.debug(f"[MERGE] {len(norm_other)} other events + {len(ct_events)} CTs → {len(merged)} total merged events.")
    merged.sort(key=lambda ev: ev.get("data") or "")
    return merged

# -----------------------------
# Public pipeline
# -----------------------------
def _process_single_text_block(text: str) -> List[Dict[str, Any]]:
    """
    Nuovo flow:
      1) Prompt A (linee) su testo completo
      2) Troncamento pre-III (se disponibile e confidence non bassa)
      3) Prompt B (CT + RECIST) sul testo troncato
      4) Prompt C (altri eventi fino a III) sul testo troncato
      5) Merge e normalizzazione finale (+ aggiunta linee per display)
    """
    clean_text = _clean_report_text(text or "")
    if not clean_text:
        return []

    # 1) LINEE
    try:
        lines_info = _run_prompt_lines(clean_text)
        # normalizziamo le date delle linee (server-side) per header B e display
        lines_info = _normalize_lines_dates(lines_info)
    except Exception:
        logger.exception("❌ Errore nel parsing delle linee")
        lines_info = {"lines": [], "third_line": {"present": False}}

    # 2) TRONCAMENTO
    truncated = _truncate_at_third_line(clean_text, lines_info)

    # 3) CT + RECIST
    try:
        cts_pack = _run_prompt_cts_recist(truncated, lines_info)
    except Exception:
        logger.exception("❌ Errore nel parsing delle TC/RECIST")
        cts_pack = {"cts": [], "per_line_summary": []}

    # 4) ALTRI EVENTI (no TC, no linee) fino a III
    try:
        other = _run_prompt_other_events(truncated)
    except Exception:
        logger.exception("❌ Errore nel parsing degli altri eventi")
        other = []

    # 5) MERGE
    merged = _merge_events(other, cts_pack)

    # 5b) Aggiungi le LINEE alla timeline come eventi visualizzabili (MINIMAL CHANGE)
    try:
        line_events = _lines_to_events(lines_info)
        line_events = normalize_dates(line_events)
        merged.extend(line_events)
        merged.sort(key=lambda ev: ev.get("data") or "")
    except Exception:
        logger.exception("⚠️ Errore aggiungendo eventi linea alla timeline")

    logger.info(f"✅ Eventi totali (pre-III) incluse linee: {len(merged)}")
    
    # (BOR computed client-side — no injection server-side)
    return merged

def extract_timeline_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Estrae, normalizza e ordina gli eventi da testo clinico grezzo (helper pubblico).
    Ritorna lista di eventi con almeno {data, testo}. Le TC includono:
      - risposta_recist (CR/PR/SD/PD/NE)
      - basis_compared_to
      - basis_note
    """
    try:
        return _process_single_text_block(text)
    except Exception as e:
        logger.error(f"❌ Error extracting timeline from text: {e}")
        return []

def extract_timeline_from_excel(excel_file: Union[str, bytes]) -> List[Dict[str, Any]]:
    """
    Legge file Excel/CSV con colonna 'report' e opzionale 'id'.
    Ritorna: [{"id": <id>, "events": [ {data, testo, ...}, ... ]}, ...]
    """
    try:
        try:
            df = pd.read_excel(excel_file)
        except Exception:
            df = pd.read_csv(excel_file)
    except Exception as e:
        logger.error(f"❌ Impossibile leggere il file Excel/CSV: {e}")
        return []

    if df.empty:
        logger.warning("⚠️ File Excel/CSV vuoto.")
        return []

    colmap = {str(c).strip().lower(): c for c in df.columns}
    if "report" not in colmap:
        candidates = [c for c in colmap if "report" in c or "referto" in c or "testo" in c]
        if not candidates:
            logger.error("❌ Colonna 'report' non trovata nel file.")
            return []
        report_col = colmap[candidates[0]]
    else:
        report_col = colmap["report"]

    id_col: Optional[str] = colmap.get("id")

    results: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        rid = row[id_col] if (id_col is not None and id_col in row) else idx
        text = str(row.get(report_col) or "")
        events = _process_single_text_block(text)
        results.append({"id": str(rid), "events": events})

    logger.info(f"✅ Timelines generate per {len(results)} righe.")
    
    # --- NEW: embed model used for extraction ---
    try:
        from app.core.llm_processor import get_current_model_name
        model_used = get_current_model_name()
        logger.info(f"🧠 Model used for extraction: {model_used}")

        # Save to metadata JSON (so frontend download can include it)
        meta_path = os.path.join("uploads", f"timeline_extraction_model.json")
        os.makedirs("uploads", exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"model_used": model_used, "timestamp": time.time()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"⚠️ Could not record model used for extraction: {e}")    
    
    return results








# import os
# import json
# import time
# import logging
# from typing import Union, List, Dict, Any, Tuple, Optional
# from dateutil import parser
# import pandas as pd
# import html
# import re
# import unicodedata

# from app import logger
# from app.core.llm_processor import get_llm_processor

# # Ensure the logs folder exists
# os.makedirs("logs", exist_ok=True)

# # -----------------------------
# # Text cleaner for HTML tags/entities
# # -----------------------------
# try:
#     from bs4 import BeautifulSoup
# except Exception:
#     BeautifulSoup = None

# _TAG_RE = re.compile(r"<[^>]+>")

# def _clean_report_text(text: str) -> str:
#     """
#     Normalizza il report prima del prompt LLM:
#     - rimuove tag HTML
#     - decodifica entità HTML (&egrave; -> è)
#     - compatta spaziature
#     """
#     if not text:
#         return ""

#     if BeautifulSoup is not None:
#         try:
#             text = BeautifulSoup(text, "html.parser").get_text(separator=" ")
#         except Exception:
#             text = _TAG_RE.sub(" ", text)
#     else:
#         text = _TAG_RE.sub(" ", text)

#     text = html.unescape(text)
#     text = re.sub(r"[ \t]+", " ", text)
#     text = re.sub(r"\s*\n\s*", "\n", text).strip()
#     return text

# # -----------------------------
# # JSON extraction / sanitation
# # -----------------------------
# def _extract_first_json_array(text: str) -> Optional[str]:
#     """
#     Estrae il *primo* array JSON ben bilanciato presente nel testo.
#     Gestisce testo extra prima/dopo e blocchi ```json ... ``` o ``` ... ```.
#     """
#     # 1) fenced ```json ... ```
#     m = re.search(r"```json\s*(\[[\s\S]*?\])\s*```", text, flags=re.IGNORECASE)
#     if m:
#         return m.group(1).strip()

#     # 1b) fenced generico ```
#     m = re.search(r"```\s*(\[[\s\S]*?\])\s*```", text, flags=re.IGNORECASE)
#     if m:
#         return m.group(1).strip()

#     # 2) ricerca manuale del primo array bilanciato
#     in_str = False
#     esc = False
#     depth = 0
#     start = -1
#     for i, ch in enumerate(text):
#         if in_str:
#             if esc:
#                 esc = False
#             elif ch == "\\":
#                 esc = True
#             elif ch == '"':
#                 in_str = False
#             continue
#         else:
#             if ch == '"':
#                 in_str = True
#                 continue
#             if ch == '[':
#                 if depth == 0:
#                     start = i
#                 depth += 1
#             elif ch == ']':
#                 if depth > 0:
#                     depth -= 1
#                     if depth == 0 and start != -1:
#                         return text[start:i+1].strip()
#     return None

# def _extract_first_json_object(text: str) -> Optional[str]:
#     """
#     Estrae il *primo* oggetto JSON ben bilanciato presente nel testo.
#     Gestisce testo extra e blocchi codefence.
#     """
#     # fenced ```json ... ```
#     m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
#     if m:
#         return m.group(1).strip()

#     # fenced generico ```
#     m = re.search(r"```\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
#     if m:
#         return m.group(1).strip()

#     # ricerca manuale del primo oggetto
#     in_str = False
#     esc = False
#     depth = 0
#     start = -1
#     for i, ch in enumerate(text):
#         if in_str:
#             if esc:
#                 esc = False
#             elif ch == "\\":
#                 esc = True
#             elif ch == '"':
#                 in_str = False
#             continue
#         else:
#             if ch == '"':
#                 in_str = True
#                 continue
#             if ch == '{':
#                 if depth == 0:
#                     start = i
#                 depth += 1
#             elif ch == '}':
#                 if depth > 0:
#                     depth -= 1
#                     if depth == 0 and start != -1:
#                         return text[start:i+1].strip()
#     return None

# def _load_json_safely(raw: str) -> Any:
#     """
#     Tenta vari approcci per decodificare JSON da stringa rumorosa.
#     """
#     if raw is None:
#         raise ValueError("Nessun JSON trovato.")
#     try:
#         return json.loads(raw)
#     except Exception:
#         try:
#             return json.loads(raw.replace('\\"', '"'))
#         except Exception as e:
#             raise ValueError(f"JSON non valido: {e}")

# def _get_ci(d: Dict[str, Any], keys: List[str]) -> Optional[str]:
#     """
#     Recupera valore stringa da dizionario in modo case-insensitive,
#     accettando anche varianti con underscore/spazi.
#     """
#     if not isinstance(d, dict):
#         return None
#     norm = {}
#     for k, v in d.items():
#         nk = re.sub(r'[\s_]+', '', str(k)).lower()
#         norm[nk] = v
#     for k in keys:
#         nk = re.sub(r'[\s_]+', '', k).lower()
#         val = norm.get(nk)
#         if isinstance(val, str) and val.strip():
#             return val.strip()
#     return None

# def _coerce_event_keys(raw_events: Any) -> List[Dict[str, Any]]:
#     """
#     Converte varie forme di eventi in [{data: str, testo: str}], scartando il resto.

#     - Accetta wrapper tipo {"events":[...]}, {"items":[...]}, {"timeline":[...]}.
#     - DATA: data, date, data_evento, when, giorno, day
#     - TESTO: testo, evento, description/descrizione/details/summary/title/text,
#              trattamento/terapia, procedura, diagnosi, biopsia, esame, label/name
#     """
#     if isinstance(raw_events, dict):
#         for k in ("events", "items", "predictions", "timeline", "result", "output"):
#             v = raw_events.get(k)
#             if isinstance(v, list):
#                 raw_events = v
#                 break

#     if not isinstance(raw_events, list):
#         raise ValueError(f"Expected a JSON array, got {type(raw_events)}")

#     out: List[Dict[str, Any]] = []
#     for ev in raw_events:
#         if not isinstance(ev, dict):
#             continue

#         data = _get_ci(ev, [
#             "data", "date", "data_evento", "when", "giorno", "day"
#         ])

#         testo = _get_ci(ev, [
#             "testo", "evento",
#             "description", "descrizione", "details",
#             "summary", "title", "text",
#             "treatment", "trattamento", "terapia",
#             "procedura", "procedure",
#             "diagnosi", "diagnosis",
#             "biopsy", "biopsia",
#             "esame",
#             "label", "name"
#         ])

#         if not testo:
#             parts = []
#             for k in ("event_type", "type", "test_name", "procedure_name", "medication", "medicazione"):
#                 v = _get_ci(ev, [k])
#                 if v:
#                     parts.append(v)
#             for k in ("details", "description", "descrizione"):
#                 v = _get_ci(ev, [k])
#                 if v:
#                     parts.append(v)
#             if parts:
#                 testo = " ".join(parts)

#         if not testo:
#             for k in ev:
#                 if isinstance(ev[k], str) and ev[k].strip():
#                     testo = ev[k].strip()
#                     break

#         if isinstance(data, str) and isinstance(testo, str):
#             out.append({"data": data.strip(), "testo": testo.strip()})

#     return out

# def _validate_events_schema(events: Any) -> None:
#     """
#     Verifica che ogni elemento abbia ALMENO le chiavi 'data' e 'testo' stringa.
#     """
#     if not isinstance(events, list):
#         raise ValueError(f"Expected list, got {type(events)}")
#     for i, ev in enumerate(events):
#         if not isinstance(ev, dict):
#             raise ValueError(f"Event {i} is not a dict")
#         if "data" not in ev or "testo" not in ev:
#             raise ValueError(f"Event {i} missing required keys: {ev.keys()}")
#         if not isinstance(ev["data"], str) or not isinstance(ev["testo"], str):
#             raise ValueError(f"Event {i} fields must be strings: {ev}")

# def clean_llm_json_response(response: str) -> List[Dict[str, Any]]:
#     """
#     Estrae un array JSON valido da una risposta LLM rumorosa (con eventuale wrapper {"response": ...}),
#     mappa chiavi comuni verso {data, testo} e convalida.
#     """
#     # 0) decodifica involucro {"response": "..."} se presente
#     try:
#         outer = json.loads(response)
#         raw_inner = outer.get("response", "")
#     except json.JSONDecodeError:
#         raw_inner = response

#     # 1) estrai array JSON da blocco codefence o testo
#     snippet = _extract_first_json_array(raw_inner)
#     candidate = snippet if snippet is not None else raw_inner.strip()

#     # 2) parse
#     parsed = _load_json_safely(candidate)

#     # 3) normalizza chiavi verso {data, testo}
#     events = _coerce_event_keys(parsed)

#     # 4) valida schema minimo
#     _validate_events_schema(events)

#     return events

# # -----------------------------
# # Date normalization (coarse-aware)
# # -----------------------------
# DATE_FULL = re.compile(r'\b(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})\b')   # 2021-05-14 / 2021/5/14
# DATE_DMY  = re.compile(r'\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{2,4})\b')  # 14/10/2014
# DATE_MY   = re.compile(r'\b(\d{1,2})[-/\.](\d{4})\b')                   # 05/2021
# DATE_Y    = re.compile(r'\b(19|20)\d{2}\b')                             # 1900..2099
# DATE_RANGE_DMY = re.compile(r'\b(\d{1,2})\s*[-–—]\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\b')
# DATE_RANGE_FULL_DMY = re.compile(
#     r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\s*[-–—]\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\b'
# )
# DATE_RANGE_FULL_ISO = re.compile(
#     r'\b(19|20)\d{2}-\d{1,2}-\d{1,2}\s*[-–—]\s*(19|20)\d{2}-\d{1,2}-\d{1,2}\b'
# )

# def _to_iso(y: int, m: int, d: int) -> str:
#     return f"{y:04d}-{m:02d}-{d:02d}"

# def _valid_year(y: int) -> bool:
#     return 1900 <= y <= 2100

# def _parse_coarse_date(s: str) -> Tuple[Optional[str], str]:
#     """
#     Riconosce:
#       - YYYY-MM-DD / DD-MM-YYYY / MM-YYYY / YYYY
#       - Range DD-DD/MM/YYYY (prende il primo giorno)
#       - Range completo DD/MM/YYYY - DD/MM/YYYY (prende la più precoce)
#       - Range ISO YYYY-MM-DD - YYYY-MM-DD (prende la più precoce)
#     Restituisce (iso_yyyy_mm_dd, granularity: 'day'|'month'|'year'|'unknown').
#     Per date senza giorno/mese usa sentinelle (15 per mese, 30/06 per anno).
#     """
#     s = (s or '').strip()
#     if not s:
#         return None, "unknown"

#     m = DATE_RANGE_FULL_ISO.search(s)
#     if m:
#         parts = re.findall(r'(?:19|20)\d{2}-\d{1,2}-\d{1,2}', s)
#         if len(parts) >= 2:
#             try:
#                 dl = parser.parse(parts[0]).date()
#                 dr = parser.parse(parts[1]).date()
#                 dmin = min(dl, dr)
#                 if _valid_year(dmin.year):
#                     return dmin.strftime("%Y-%m-%d"), "day"
#             except Exception:
#                 pass

#     m = DATE_RANGE_FULL_DMY.search(s)
#     if m:
#         d1, mo1, y1, d2, mo2, y2 = m.groups()
#         y1 = int(y1); y1 = y1 + 2000 if y1 < 100 else y1
#         y2 = int(y2); y2 = y2 + 2000 if y2 < 100 else y2
#         try:
#             from datetime import date
#             dl = date(y1, int(mo1), int(d1))
#             dr = date(y2, int(mo2), int(d2))
#             dmin = dl if dl <= dr else dr
#             if _valid_year(dmin.year):
#                 return dmin.strftime("%Y-%m-%d"), "day"
#         except Exception:
#             pass

#     m = DATE_RANGE_DMY.search(s)
#     if m:
#         d1, d2, mo, y = m.groups()
#         y = int(y)
#         y = y + 2000 if y < 100 else y
#         if _valid_year(y):
#             return _to_iso(y, int(mo), int(d1)), "day"

#     m = DATE_FULL.search(s)
#     if m:
#         y, mo, d = map(int, m.groups())
#         if _valid_year(y):
#             return _to_iso(y, mo, d), "day"

#     m = DATE_DMY.search(s)
#     if m:
#         d, mo, y = m.groups()
#         y = int(y)
#         y = y + 2000 if y < 100 else y
#         if _valid_year(y):
#             return _to_iso(y, int(mo), int(d)), "day"

#     m = DATE_MY.search(s)
#     if m:
#         mo, y = map(int, m.groups())
#         if _valid_year(y):
#             return _to_iso(y, mo, 15), "month"

#     m = DATE_Y.search(s)
#     if m:
#         y = int(m.group(0))
#         if _valid_year(y):
#             return _to_iso(y, 6, 30), "year"

#     try:
#         dt = parser.parse(s, dayfirst=True, fuzzy=True)
#         if _valid_year(dt.year):
#             return dt.strftime("%Y-%m-%d"), "day"
#         return None, "unknown"
#     except Exception:
#         return None, "unknown"

# def normalize_dates(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """
#     Normalizza event["data"] in ISO YYYY-MM-DD e salva granularità in _granularity.
#     """
#     normalized = []
#     for evt in events:
#         raw_date = evt.get("data", "")
#         iso, gran = _parse_coarse_date(raw_date)
#         evt["data"] = iso
#         evt["_granularity"] = gran
#         normalized.append(evt)
#     return normalized

# # -------- NEW: pre-LLM in-text date normalization (Italian DMY → ISO) --------
# def _normalize_dates_in_text(text: str) -> str:
#     """
#     Converte nel testo le date al formato:
#       - DD/MM/YYYY (o DD-MM-YYYY o DD.MM.YYYY) -> YYYY-MM-DD
#       - MM/YYYY (o MM-YYYY o MM.YYYY) -> YYYY-MM
#       - YYYY resta invariato
#     Giorno, mese e anno sono interpretati come DMY (contesto italiano).
#     Non modifica numeri non conformi ai pattern.
#     """

#     def sub_dmy(m: re.Match) -> str:
#         d, mo, y = m.group(1), m.group(2), m.group(3)
#         # 2-digit year -> 2000+yy (coerente con contesto dataset)
#         y_i = int(y)
#         if y_i < 100:
#             y_i += 2000
#         return f"{y_i:04d}-{int(mo):02d}-{int(d):02d}"

#     def sub_my(m: re.Match) -> str:
#         mo, y = m.group(1), m.group(2)
#         return f"{int(y):04d}-{int(mo):02d}"

#     # Ordine importante: prima DMY, poi MY (per evitare sovrapposizioni)
#     txt = re.sub(DATE_DMY, sub_dmy, text)
#     txt = re.sub(DATE_MY, sub_my, txt)
#     return txt

# # -----------------------------
# # Event canonicalization
# # -----------------------------
# def _strip_accents(s: str) -> str:
#     return ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')

# def _prep(s: str) -> str:
#     s = _strip_accents(s or '').lower()
#     s = s.replace('‐', '-').replace('-', '-').replace('–', '-').replace('—', '-')
#     s = re.sub(r'\s+', ' ', s).strip()
#     return s

# ALLOWED_EVENTS: Dict[str, List[Union[str, Tuple[str, ...], re.Pattern]]] = {
#     "Diagnosi": [ "diagnosi" ],
#     "Biopsia o Agobiopsia": [ ("biopsia"), ("agobiopsia") ],
#     "Inizio del trattamento di I linea": [
#         re.compile(r"\bprima\s*linea\b"), re.compile(r"(?<!i)\bi\s*linea\b"),
#     ],
#     "Inizio del trattamento di II linea": [
#         re.compile(r"\bseconda\s*linea\b"), re.compile(r"\bii\s*linea\b"),
#     ],
#     "Inizio del trattamento di III linea": [
#         re.compile(r"\bterza\s*linea\b"), re.compile(r"\biii\s*linea\b"),
#     ],
#     "TC torace/total body": [
#         ("tac", "torace"), ("tc", "torace"),
#         ("tac", "tb"), ("tc", "tb"),
#         ("tac", "total-body"), ("tc", "total-body"),
#         ("tac", "mdc"), ("tc", "mdc"),
#         ("tc", "c/t/a"), ("tc", "e/t/a"),
#         ("tac", "c/t/a"),
#         "tc tb e/o torace", "tc torace", "tac torace", "tc tb", "tctb", "tac tb",
#         "tc total body", "tac total body", "tc totale corpo", "tc totale torace",
#         "tac totale torace", "tac totale corpo",
#         ("ct", "torace"), ("ct", "tb"), ("ct", "total"), ("ct", "chest"),
#         ("ct", "c/t/a"), ("ct", "e/t/a"),
#     ],
#     "Evidenze di discontinuità nella malattia oncologica toracica": [
#         "discontinuita", "interruzione", "interrotto", "stop", "sospensione"
#     ],
# }

# def _assign_lines_for_avvio(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """
#     Trasforma eventi con 'avvio/inizio' in linee I/II/III in ordine cronologico (max 3).
#     Non tocca eventi che già sono linee esplicite.
#     """
#     if not events:
#         return events

#     cand_idx = []
#     for i, ev in enumerate(events):
#         t = _prep(ev.get("testo") or "")
#         if any(k in t for k in ("avvio", "avviata", "avviato", "avvi", "inizio terapia", "inizio trattamento")):
#             cand_idx.append(i)

#     if not cand_idx:
#         return events

#     cand_idx = [i for i in cand_idx if events[i].get("data")]
#     if not cand_idx:
#         return events

#     cand_idx.sort(key=lambda i: events[i].get("data") or "")

#     labels = [
#         "Inizio del trattamento di I linea",
#         "Inizio del trattamento di II linea",
#         "Inizio del trattamento di III linea",
#     ]

#     kept = set()
#     drops = set()
#     for rank, i in enumerate(cand_idx):
#         if rank < 3:
#             events[i]["testo"] = labels[rank]
#             events[i]["_assigned_line"] = True
#             kept.add(i)
#         else:
#             drops.add(i)

#     if drops:
#         events = [e for j, e in enumerate(events) if j not in drops]

#     return events

# def normalize_texts(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """
#     Mappa event["testo"] ai nomi canonici. Scarta gli eventi che non matchano.
#     """
#     normalized: List[Dict[str, Any]] = []
#     for ev in events:
#         if ev.get("_assigned_line") and ev.get("testo") in (
#             "Inizio del trattamento di I linea",
#             "Inizio del trattamento di II linea",
#             "Inizio del trattamento di III linea",
#         ):
#             normalized.append(ev)
#             continue

#         original = (ev.get("testo") or "").strip()
#         raw_norm = _prep(original)
#         matched = False

#         for canon, variants in ALLOWED_EVENTS.items():
#             for variant in variants:
#                 if isinstance(variant, re.Pattern):
#                     if variant.search(raw_norm):
#                         ev["testo"] = canon
#                         matched = True
#                         break
#                 elif isinstance(variant, str):
#                     if variant in raw_norm:
#                         ev["testo"] = canon
#                         matched = True
#                         break
#                 else:
#                     if isinstance(variant, tuple) and all(sub in raw_norm for sub in variant):
#                         ev["testo"] = canon
#                         matched = True
#                         break
#             if matched:
#                 break

#         if not matched:
#             logger.debug(f'❓ No match for "{original}" (norm="{raw_norm}") against any canonical variant.')
#             continue

#         normalized.append(ev)

#     return normalized

# # -----------------------------
# # PROMPTS (concisi, ITA) — raw strings, NO normalizzazione date dal LLM
# # -----------------------------
# PROMPT_A_LINES = r'''
# Sei un oncologo toracico e ricevi un documento contenente la storia clinica di un paziente affetto da tumore al polmone.
# Esegui con cura i seguenti compiti, nell'ordine:

# 1. Leggi il documento che segue riga per riga e comprendi la storia clinica del paziente
# 2. Fermati ogni volta che viene nominato un nuovo farmaco: Gefitinib, Erlotinib, Osimertinib, Afatinib o Poziotinib
# 3. In corrispondenza di questa menzione, recupera la data annessa, e associa una linea di trattamento (in ordine: I, II, III)
# 4. Raggiunta la III linea fermati. Non ci interessa tutto quello che viene dopo.

# Vincoli:
# - Aggiustamenti di dose o mantenimento con lo stesso farmaco NON determinano una nuova linea.
# - Sicuramente nel documento è presente l'avvio della I linea, ma la II e III linea è probabile che manchino. in questo caso, NON inventarle.
# - Per ogni linea, esiste UNA SOLA (o zero in caso di II e III linea mancanti) data associata, dunque il tuo JSON conterrà AL MASSIMO 3 tuple (linea, data).

# Rispondi SOLO con un oggetto JSON:
# {
#   "lines": [
#     {"line":"I|II|III", "date_raw":"string|null",
#      "evidence":{"quote":"<=160c", "char_start":0, "char_end":0},
#      "confidence":"high|medium|low"}
#   ],
#   "third_line":{"present":true|false, "char_start":0, "date_raw":"string|null",
#                 "confidence":"high|medium|low"}
# }

# Vincoli: NON normalizzare nè modificare le date. Copiale esattamente come scritte.
# '''

# PROMPT_B_CTS_RECIST = r'''
# Sei un oncologo toracico e ricevi un documento contenente la storia clinica di un paziente affetto da tumore al polmone.
# Esegui con cura i seguenti compiti, nell'ordine:

# 1. Leggi il documento che segue riga per riga e comprendi la storia clinica del paziente
# 2. Fermati ogni volta che viene nominata: "TAC" o "TC" (non ci interessano altri esami di imaging come RMN, PET, RX, ecografie...)
# 3. In corrispondenza di questa menzione, recupera la data annessa (è sempre scritta PRIMA della menzione, es: 10/11/2021 TAC torace:...)
# 4. Procedi a leggere la descrizione successiva alla menzione ed etichetta la TAC corrente secondo questi criteri:
#     - CR: Scomparsa di tutte le lesioni (tutti i linfonodi prima identificati come patologici devono avere diametro inferiore ai 10 mm), negativizzazione dei marker tumorali sierici
#     - PR: Riduzione della somma dei diametri di tutte le lesioni pari almeno al 30%
#     - PD: Incremento relativo della somma dei diametri di almeno il 20% e in assoluto di almeno 5 mm, comparsa di almeno una nuova lesione, inequivocabile progressione di una lesione non target.
#     - SD: Tutti i casi non appartenenti alle descrizioni precedenti oppure persistenza di una lesione non target oppure marker sierici sopra la norma anche in assenza di lesioni radiologicamente evidenti
#     - NE: Non è possibile classificare la risposta per mancanza di dati
# 5. Continua la lettura, ripetendo il procediento dal punto 2.

# Ogni TAC avrà una e una sola classificazione, escluse le tac basali.

# JSON richiesto:
# {
#   "cts":[
#     {"ct_id":"CT001", "date_raw":"string",
#      "date_confidence":"high|medium|low",
#      "evidence":{"quote":"<=160c","char_start":0,"char_end":0},
#      "snippet":"<=350c","anatomy":["torace"],
#      "line_context":"I|II|unknown",
#      "response_recist":"CR|PR|SD|PD|NE",
#      "basis":{"compared_to":"CT000|null","rationale":"<=220c"}}
#   ],
#   "per_line_summary":[
#     {"line":"I","best_response":"CR|PR|SD|PD|NE","first_pd_date_raw":"string|null"},
#     {"line":"II","best_response":"CR|PR|SD|PD|NE","first_pd_date_raw":"string|null"}
#   ]
# }

# Vincoli: Verifica che l'evento con la data corrispondente sia presente nel testo, se la confidenza sulla data è bassa, imposta "date_confidence":"low".
# E' richiesta massima precisione nell'identificazione delle date corrette, non modificarle o inventarle per alcun motivo (minimizza Falsi Positivi e Falsi Negativi).
# '''

# PROMPT_C_OTHER = r'''
# Sei un oncologo toracico e ricevi un documento contenente la storia clinica di un paziente affetto da tumore al polmone.
# Esegui con cura i seguenti compiti, nell'ordine:
# 1. Leggi il documento che segue riga per riga e comprendi la storia clinica del paziente
# 2. Estrai TUTTI gli eventi relativi a:
# 3. Fermati ogni volta che viene nominato uno dei seguenti eventi:
#     - Diagnosi: non è mai ripetuta (in genere si trova all'inizio del documento. Se l'evento è mancante perché non esplicitamente menzionato, non inventarlo)
#     - Biopsia o Agobiopsia: potrebbe essere ripetuta, o potrebbe essere mancante
#     - Discontinuità nella malattia oncologica toracica (spesso definito da: “sospensione”, “interruzione”, “stop”, “interrotto”, “sospeso” di un farmaco)
# 4. In corrispondenza dell'evento, recupera la data annessa
# 5. Continua la lettura, ripetendo il procediento dal punto 2.

# Rispondi con un ARRAY JSON di oggetti:
# [{"data":"string","testo":"etichetta evento","date_confidence":"high|medium|low"}]

# Vincoli: Le date devono essere una sottostringa esatta del testo, non modificarle, non inferirle e non inventarle.
# Se la confidenza sulla data è "low", imposta "date_confidence":"low".
# Non inventare eventi non menzionati, e non ignorare quelli menzionati.
# E' richiesta massima precisione nell'identificazione delle date corrette, non modificarle o inventarle per alcun motivo (minimizza Falsi Positivi e Falsi Negativi).
# '''

# # -----------------------------
# # LLM helpers
# # -----------------------------
# def _llm_call(prompt: str, document: str, phase: str) -> str:
#     llm = get_llm_processor()
#     msg = f"{prompt}\n\nTESTO:\n<<<\n{document}\n>>>\n\nJSON:"
#     logger.info(f"[LLM {phase}] prompt preview:\n{msg[:1500]}")
#     resp = llm.generate_response(msg)
#     # unique filename per call (ms precision)
#     ts = int(time.time() * 1000)
#     debug_file = f"logs/llm_{phase}_debug_{ts}.json"
#     try:
#         with open(debug_file, "w", encoding="utf-8") as f:
#             json.dump({"phase": phase, "prompt": msg[:8000], "response": resp[:8000]}, f,
#                       ensure_ascii=False, indent=2)
#     except Exception:
#         logger.exception("[LLM %s] failed to write debug file", phase)
#     return resp

# def _parse_lines_response(resp: str) -> Dict[str, Any]:
#     """
#     Parsing robusto dell'output di PROMPT A.
#     """
#     # alcune LLM wrappano in {"response": "..."}
#     try:
#         outer = json.loads(resp)
#         raw = outer.get("response", resp)
#     except Exception:
#         raw = resp

#     obj_str = _extract_first_json_object(raw)
#     data = _load_json_safely(obj_str) if obj_str else {}
#     # forma attesa: {"lines":[...], "third_line":{...}}
#     lines = data.get("lines") or []
#     third = data.get("third_line") or {"present": False}
#     # sanitize min
#     out_lines = []
#     for it in lines:
#         if not isinstance(it, dict):
#             continue
#         line = (it.get("line") or "").strip().upper()
#         if line not in ("I", "II", "III"):
#             continue
#         date_raw = it.get("date_raw")
#         ev = it.get("evidence") or {}
#         cs, ce = ev.get("char_start"), ev.get("char_end")
#         conf = it.get("confidence") or "low"
#         out_lines.append({
#             "line": line,
#             "date_raw": date_raw,
#             "evidence": {"quote": ev.get("quote"), "char_start": cs, "char_end": ce},
#             "confidence": conf
#         })
#     tl = {
#         "present": bool(third.get("present")),
#         "char_start": third.get("char_start"),
#         "date_raw": third.get("date_raw"),
#         "confidence": third.get("confidence") or "low"
#     }
#     return {"lines": out_lines, "third_line": tl}

# def _parse_cts_response(resp: str) -> Dict[str, Any]:
#     try:
#         outer = json.loads(resp)
#         raw = outer.get("response", resp)
#     except Exception:
#         raw = resp
#     obj_str = _extract_first_json_object(raw)
#     data = _load_json_safely(obj_str) if obj_str else {}
#     cts = data.get("cts") or []
#     pls = data.get("per_line_summary") or []
#     # sanitize rapido + FILTRO low/medium date_confidence
#     out_cts = []
#     for it in cts:
#         if not isinstance(it, dict):
#             continue
#         date_conf = (it.get("date_confidence") or "").lower()
#         if date_conf in ("low", "medium"):
#             continue
#         out_cts.append({
#             "ct_id": it.get("ct_id"),
#             "date_raw": it.get("date_raw"),
#             "date_confidence": date_conf or None,
#             # niente date_norm dall'LLM
#             "evidence": it.get("evidence") or {},
#             "snippet": it.get("snippet"),
#             "anatomy": it.get("anatomy") or [],
#             "line_context": it.get("line_context") or "unknown",
#             "response_recist": it.get("response_recist"),
#             "basis": it.get("basis") or {}
#         })
#     # opzionale: rinominiamo chiave summary delle date in *_raw per coerenza
#     for x in pls:
#         if "first_pd_date" in x and "first_pd_date_raw" not in x:
#             x["first_pd_date_raw"] = x.get("first_pd_date")
#             del x["first_pd_date"]
#     return {"cts": out_cts, "per_line_summary": pls}

# # -----------------------------
# # Small post guards
# # -----------------------------
# RECIST_DOWNMAP = [
#     (re.compile(r"\b(invariat[ao]|stazionari[ao]|sovrapponibil[ei])\b", re.I), "SD"),
#     (re.compile(r"\b(nuov[ae]\s+lesion|progression|aument[oi])\b", re.I), "PD"),
#     (re.compile(r"\b(scomparsa)\b", re.I), "CR"),
#     (re.compile(r"\b(liev[e|a]|minim[ao])\s+riduzion", re.I), "SD"),
#     (re.compile(r"\b(>=?\s*30%|30\s*%|trenta\s*%)\b", re.I), "PR"),
#     (re.compile(r"\b(marcat[ao]\s+riduzion)\b", re.I), "PR"),
# ]

# def _normalize_date_from_quote(date_raw: Optional[str]) -> Optional[str]:
#     """
#     Normalizza la data grezza estratta dal LLM, rimuovendo testo extra come 'TAC torace:'.
#     """
#     if not date_raw:
#         return None

#     # 🔹 Rimuovi eventuale testo dopo la data (es: "10/11/2021 TAC torace:")
#     date_raw = re.split(r'\bTAC\b|\bTC\b', date_raw, 1, flags=re.IGNORECASE)[0].strip()

#     iso, _ = _parse_coarse_date(date_raw)
#     return iso

# def _fix_ct_dates(ct: Dict[str, Any]) -> None:
#     """
#     Imposta date_norm dalle date raw del LLM (nessun confronto con l'LLM).
#     """
#     ct["date_norm"] = _normalize_date_from_quote(ct.get("date_raw"))

# def _sanitize_recist_from_snippet(ct: Dict[str, Any]) -> None:
#     resp = (ct.get("response_recist") or "").upper()
#     snippet = ct.get("snippet") or ""
#     if not resp:
#         return
#     for rx, mapped in RECIST_DOWNMAP:
#         if rx.search(snippet):
#             if mapped == "SD" and resp in ("PR", "CR"):
#                 ct["response_recist"] = "SD"; ct["_response_adjusted"] = True; return
#             if mapped == "PD" and resp in ("PR", "CR", "SD"):
#                 ct["response_recist"] = "PD"; ct["_response_adjusted"] = True; return
#             if mapped == "CR" and resp != "CR":
#                 ct["response_recist"] = "CR"; ct["_response_adjusted"] = True; return
#             if mapped == "PR" and resp in ("SD", "NE"):
#                 ct["response_recist"] = "PR"; ct["_response_adjusted"] = True; return

# def _dedup_cts(cts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     if not cts:
#         return cts
#     def key(ct):
#         dn = ct.get("date_norm") or ""
#         anat = ",".join(sorted([a.lower() for a in (ct.get("anatomy") or [])]))
#         return dn, anat
#     seen = {}
#     for ct in sorted(cts, key=lambda x: x.get("date_norm") or ""):
#         k = key(ct)
#         if k in seen:
#             prev = seen[k]
#             if len((ct.get("snippet") or "")) > len((prev.get("snippet") or "")):
#                 seen[k] = ct
#         else:
#             seen[k] = ct
#     return list(seen.values())

# def _normalize_lines_dates(lines_info: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Aggiunge date_norm calcolata da date_raw per ogni linea (se possibile).
#     """
#     out = {"lines": [], "third_line": dict(lines_info.get("third_line") or {})}
#     for ln in lines_info.get("lines", []):
#         ln = dict(ln)
#         ln["date_norm"] = _normalize_date_from_quote(ln.get("date_raw"))
#         out["lines"].append(ln)
#     if "date_raw" in out["third_line"]:
#         out["third_line"]["date_norm"] = _normalize_date_from_quote(out["third_line"].get("date_raw"))
#     return out

# # NEW: minimal helper to convert lines to regular display events
# def _lines_to_events(lines_info: Dict[str, Any]) -> List[Dict[str, Any]]:
#     """
#     Converte le linee (I/II/III) in eventi {data, testo} per la timeline.
#     """
#     label_map = {
#         "I": "Inizio del trattamento di I linea",
#         "II": "Inizio del trattamento di II linea",
#         "III": "Inizio del trattamento di III linea",
#     }
#     events: List[Dict[str, Any]] = []
#     for ln in lines_info.get("lines", []):
#         line_code = (ln.get("line") or "").strip().upper()
#         label = label_map.get(line_code)
#         if not label:
#             continue
#         date_val = ln.get("date_norm") or (ln.get("date_raw") or "")
#         events.append({
#             "data": date_val,
#             "testo": label,
#             "_from_lines": True  # flag interno, non usato in export ma utile per debug
#         })
#     return events

# # -----------------------------
# # Flow: 3 prompt
# # -----------------------------
# def _run_prompt_lines(full_text: str) -> Dict[str, Any]:
#     resp = _llm_call(PROMPT_A_LINES, full_text, phase="A_lines")
#     return _parse_lines_response(resp)

# def _truncate_at_third_line(full_text: str, lines_info: Dict[str, Any]) -> str:
#     tl = lines_info.get("third_line") or {}
#     if tl.get("present") and tl.get("confidence") != "low" and isinstance(tl.get("char_start"), int):
#         cut = tl["char_start"]
#         if 0 < cut <= len(full_text):
#             return full_text[:cut]
#     return full_text

# def _run_prompt_cts_recist(trunc_text: str, lines_info: Dict[str, Any]) -> Dict[str, Any]:
#     # Build a tiny header with line starts to anchor the model
#     lines_ctx_rows = []
#     for ln in sorted(lines_info.get("lines", []), key=lambda x: (x.get("line"), x.get("date_norm") or "")):
#         lines_ctx_rows.append(f'{ln.get("line")}:{ln.get("date_norm") or "null"}@{ln.get("evidence",{}).get("char_start")}')
#     header = "INIZI_LINEE: " + ", ".join(lines_ctx_rows) + "\n"
#     resp = _llm_call(PROMPT_B_CTS_RECIST, header + trunc_text, phase="B_cts")
#     return _parse_cts_response(resp)

# def _run_prompt_other_events(trunc_text: str) -> List[Dict[str, Any]]:
#     # Prompt C: ritorna un ARRAY di oggetti con {data, testo, date_confidence}
#     resp = _llm_call(PROMPT_C_OTHER, trunc_text, phase="C_other")
#     try:
#         outer = json.loads(resp)
#         inner = outer.get("response", resp)
#     except Exception:
#         inner = resp
#     arr = _extract_first_json_array(inner) or inner.strip()
#     parsed = _load_json_safely(arr)
#     if not isinstance(parsed, list):
#         raise ValueError("Prompt C expected a JSON array.")
#     events: List[Dict[str, Any]] = []
#     for it in parsed:
#         if not isinstance(it, dict):
#             continue
#         dc = (it.get("date_confidence") or "").lower()
#         if dc in ("low", "medium"):
#             continue
#         data = it.get("data")
#         testo = it.get("testo")
#         if isinstance(data, str) and isinstance(testo, str):
#             events.append({"data": data.strip(), "testo": testo.strip()})
#     _validate_events_schema(events)
#     return events

# # -----------------------------
# # Pipeline helpers (nuovo flow)
# # -----------------------------
# def _merge_events(other_events: List[Dict[str, Any]], cts_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
#     """
#     Converte CTs in eventi canonici + campi extra RECIST e unisce con other_events.
#     """
#     # 1) normalizza OTHER (diagnosi/biopsia/discontinuità)
#     # (rimosso normalize_dates per display finale: assumiamo date già ISO dal pre-pass)
#     dated_other = other_events
#     dated_other = _assign_lines_for_avvio(dated_other)
#     norm_other = normalize_texts(dated_other)
#     # escludi esplicitamente eventuali CT o linee (difesa)
#     norm_other = [e for e in norm_other if e.get("testo") not in (
#         "TC torace/total body",
#         "Inizio del trattamento di I linea",
#         "Inizio del trattamento di II linea",
#         "Inizio del trattamento di III linea",
#     )]

#     # 2) CTs → eventi canonici
#     cts = cts_pack.get("cts") or []
#     for ct in cts:
#         _fix_ct_dates(ct)
#         _sanitize_recist_from_snippet(ct)

#     cts = _dedup_cts(cts)

#     ct_events: List[Dict[str, Any]] = []
#     for ct in cts:
#         ev = {
#             "data": ct.get("date_norm") or (ct.get("date_raw") or ""),
#             "testo": "TC torace/total body",
#             # campi extra per frontend/export:
#             "risposta_recist": (ct.get("response_recist") or "").upper() or None,
#             "basis_compared_to": (ct.get("basis") or {}).get("compared_to"),
#             "basis_note": (ct.get("basis") or {}).get("rationale"),
#             "_ct_id": ct.get("ct_id"),
#             "_line_context": ct.get("line_context"),
#             "_snippet": ct.get("snippet"),
#         }
#         ct_events.append(ev)

#     # 3) merge + sort (senza normalize_dates finale: le date nel testo sono già ISO)
#     merged = norm_other + ct_events
#     merged.sort(key=lambda ev: ev.get("data") or "")

#     # 4) Calcola la Best Response per la I linea
#     def _compute_best_response(events):
#         """
#         Calcola la migliore risposta RECIST tra i CT compresi tra
#         'Inizio I linea' e 'Inizio II linea' (se presente).
#         """
#         order = {"CR": 1, "PR": 2, "SD": 3, "PD": 4, "NE": 5}
#         best = None
#         start_I = None
#         start_II = None

#         # Trova i confini temporali
#         for ev in events:
#             testo = ev.get("testo", "").lower()
#             data = ev.get("data")
#             if not data:
#                 continue
#             if "inizio" in testo and "i linea" in testo:
#                 start_I = data
#             elif "inizio" in testo and "ii linea" in testo:
#                 start_II = data

#         if not start_I:
#             return None  # impossibile definire I linea

#         # Seleziona CTs nella finestra temporale
#         for ev in events:
#             testo = ev.get("testo", "").lower()
#             data = ev.get("data")
#             resp = (ev.get("risposta_recist") or "").upper()
#             if not data or "tc" not in testo:
#                 continue

#             if data >= start_I and (not start_II or data < start_II):
#                 if resp in order:
#                     if best is None or order[resp] < order[best]:
#                         best = resp

#         return best or "NE"

#     try:
#         best_resp = _compute_best_response(merged)
#         if best_resp:
#             merged.append({
#                 "data": None,
#                 "testo": f"Best Response (I line): {best_resp}",
#                 "_synthetic": True
#             })
#     except Exception:
#         logger.exception("⚠️ Failed computing best response for I line")
#         best_resp = None

#     logger.info(f"CT events parsed: {len(ct_events)} (with RECIST labels)")
#     return merged, {"bor_first_line": best_resp or "NE"}

# # -----------------------------
# # Public pipeline
# # -----------------------------
# def _process_single_text_block(text: str) -> List[Dict[str, Any]]:
#     """
#     Nuovo flow:
#       1) Pre-pass: pulizia + normalizzazione date in TESTO (DMY/MY -> ISO) PRIMA dei prompt
#       2) Prompt A (linee) su testo completo normalizzato
#       3) Troncamento pre-III (se disponibile e confidence non bassa)
#       4) Prompt B (CT + RECIST) sul testo troncato normalizzato
#       5) Prompt C (altri eventi fino a III) sul testo troncato normalizzato
#       6) Merge e sort finale (senza normalizzazione date di display)
#     """
#     clean_text = _clean_report_text(text or "")
#     if not clean_text:
#         return []

#     # (1) Normalizzazione date in testo (DMY/MY -> ISO); giorno invariato se presente
#     normalized_doc = _normalize_dates_in_text(clean_text)

#     # 2) LINEE
#     try:
#         lines_info = _run_prompt_lines(normalized_doc)
#         # normalizziamo le date delle linee (server-side) per header B e display
#         lines_info = _normalize_lines_dates(lines_info)
#     except Exception:
#         logger.exception("❌ Errore nel parsing delle linee")
#         lines_info = {"lines": [], "third_line": {"present": False}}

#     # 3) TRONCAMENTO
#     truncated = _truncate_at_third_line(normalized_doc, lines_info)

#     # 4) CT + RECIST
#     try:
#         cts_pack = _run_prompt_cts_recist(truncated, lines_info)
#     except Exception:
#         logger.exception("❌ Errore nel parsing delle TC/RECIST")
#         cts_pack = {"cts": [], "per_line_summary": []}

#     # 5) ALTRI EVENTI (no TC, no linee) fino a III
#     try:
#         other = _run_prompt_other_events(truncated)
#     except Exception:
#         logger.exception("❌ Errore nel parsing degli altri eventi")
#         other = []

#     # 6) MERGE
#     merged = _merge_events(other, cts_pack)

#     # 6b) Aggiungi le LINEE alla timeline come eventi visualizzabili (senza normalize_dates)
#     try:
#         line_events = _lines_to_events(lines_info)
#         merged.extend(line_events)
#         merged.sort(key=lambda ev: ev.get("data") or "")

#         logger.info(f"✅ Eventi totali (pre-III) incluse linee: {len(merged)}")
#         return {"events": merged, "summary": summary, "completed": True}

# def extract_timeline_from_text(text: str) -> List[Dict[str, Any]]:
#     """
#     Estrae, normalizza e ordina gli eventi da testo clinico grezzo (helper pubblico).
#     Ritorna lista di eventi con almeno {data, testo}. Le TC includono:
#       - risposta_recist (CR/PR/SD/PD/NE)
#       - basis_compared_to
#       - basis_note
#     """
#     try:
#         return _process_single_text_block(text)
#     except Exception as e:
#         logger.error(f"❌ Error extracting timeline from text: {e}")
#         return []

# def extract_timeline_from_excel(excel_file: Union[str, bytes]) -> List[Dict[str, Any]]:
#     """
#     Legge file Excel/CSV con colonna 'report' e opzionale 'id'.
#     Ritorna: [{"id": <id>, "events": [ {data, testo, ...}, ... ]}, ...]
#     """
#     try:
#         try:
#             df = pd.read_excel(excel_file)
#         except Exception:
#             df = pd.read_csv(excel_file)
#     except Exception as e:
#         logger.error(f"❌ Impossibile leggere il file Excel/CSV: {e}")
#         return []

#     if df.empty:
#         logger.warning("⚠️ File Excel/CSV vuoto.")
#         return []

#     colmap = {str(c).strip().lower(): c for c in df.columns}
#     if "report" not in colmap:
#         candidates = [c for c in colmap if "report" in c or "referto" in c or "testo" in c]
#         if not candidates:
#             logger.error("❌ Colonna 'report' non trovata nel file.")
#             return []
#         report_col = colmap[candidates[0]]
#     else:
#         report_col = colmap["report"]

#     id_col: Optional[str] = colmap.get("id")

#     results: List[Dict[str, Any]] = []
#     for idx, row in df.iterrows():
#         rid = row[id_col] if (id_col is not None and id_col in row) else idx
#         text = str(row.get(report_col) or "")
#         events = _process_single_text_block(text)
#         results.append({"id": str(rid), "events": events})

#     logger.info(f"✅ Timelines generate per {len(results)} righe.")
#     return results
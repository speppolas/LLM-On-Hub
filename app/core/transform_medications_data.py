# NORM 1
# # normalizza minuscole farmaci

# def normalize_medication_entry(entry: dict) -> dict:
#     """
#     Applica tutte le funzioni di normalizzazione a un dizionario di farmaco.
#     """
#     # Combina i testi in un unico blocco per pattern estrattivi
#     text = " ".join([str(v) for v in entry.values() if isinstance(v, str)])

#     # Estrazione avanzata
#     mutation_exon = extract_all(text)

#     return {
#         **entry,
#         "dosage": clean_dosage(text),
#         "frequency": extract_frequency(text),
#         "period": normalize_period(text),
#         "modality": extract_modality(text),
#         "mutation": mutation_exon["mutation"],
#         "exon": mutation_exon["exon"],
#         "collateral": extract_collateral_effect(text),
#         "comorbidity": extract_comorbidity(text),
#     }





# import re

# # Unità valide (tutte minuscole)
# VALID_UNITS = [
#     'mg', 'g', 'mcg', 'μg', 'ng', 'ui', 'ml', 'gtt', 'fl',
#     'cp', 'cps', 'cpr', 'bustina', 'bustine', 'supposta', 'supposte',
#     'mEq', 'kcal', 'mg/ml', 'mg/m2', 'mg/mq', 'mg/kg', 'mg/kg/die',
#     'ui/kg', 'ml/kg', 'auc'
# ]

# # Normalizzazione unità equivalenti
# UNIT_NORMALIZATION = {
#     'μg': 'mcg',
#     'mL': 'ml',
#     'MG': 'mg',
#     'MG/ML': 'mg/ml',
#     'MG/M2': 'mg/m2',
#     'MG/MQ': 'mg/mq',
#     'CC': 'ml',
# }

# # Regex pattern principali per dosaggio
# DOSAGE_PATTERNS = [
#     r'\b\d+(?:[\.,]\d+)?\s*(mg\/kg(?:\/die)?|mg\/mq|mg\/m2|mg\/ml|ml\/kg|ui\/kg)\b',
#     r'\bauc\s*\d+(?:[\.,]\d+)?\b',
#     r'\bdose (?:flat|standard) di\s*(\d+(?:[\.,]\d+)?)\s*mg\b',
#     r'\b(?:mg|g|mcg|μg|ng|ui|ml|gtt|fl|mEq|kcal)\s*\d+(?:[\.,]\d+)?\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|μg|ng|ui|ml|gtt|fl|mEq|kcal)\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|μg|ng|ui|ml)\s*(tot(?:ali)?|complessivi|pari a|circa)\b',
#     r'\b\d+(?:[\.,]\d+)?\s*\+\s*\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\s*→\s*\d+(?:[\.,]\d+)?\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\s*e\s*\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\b',
#     r'\b\d+\s*(?:cp|cps|cpr|bustina|bustine|supposta|supposte)\s*da\s*(\d+(?:[\.,]\d+)?)\s*(mg|mcg|g|ml)\b',
#     r'\b(mg|g|mcg|μg|ml|ui)\s*\d+(?:[\.,]\d+)?\b',
# ]

# # Rimozione parole spurie
# MODIFIERS = ['tot', 'totali', 'complessivi', 'pari a', 'circa']

# def normalize_unit(unit):
#     unit = unit.lower()
#     return UNIT_NORMALIZATION.get(unit.upper(), unit)

# def clean_dosage(text):
#     text = text.lower()
#     for pattern in DOSAGE_PATTERNS:
#         match = re.search(pattern, text)
#         if match:
#             if 'auc' in match.group(0):
#                 return match.group(0).replace(' ', '').upper()
#             raw = match.group(0)
#             raw = re.sub(r'[,]', '.', raw)
#             raw = re.sub(r'\s+', ' ', raw)
#             raw = re.sub(r'\b(' + '|'.join(MODIFIERS) + r')\b', '', raw).strip()
#             m = re.search(r'(\d+(?:\.\d+)?)\s*(mg\/kg\/die|mg\/kg|mg\/ml|mg\/m2|mg\/mq|ml\/kg|ui\/kg|mg|g|mcg|μg|ml|ui|gtt|fl|mEq|kcal)', raw)
#             if m:
#                 val = m.group(1)
#                 unit = normalize_unit(m.group(2))
#                 return f"{val} {unit}"
#     return 'n/a'

# def normalize_period(text):
#     text = text.lower()
#     match = re.search(r'(\d+)\s*(?:cycles|cicli)', text)
#     if match:
#         return f"{match.group(1)} cicli"
#     return "n/a"


# def extract_frequency(text):
#     text = text.lower()

#     abbrev_patterns = [
#         r'\b(qd|bid|tid|qid|qod|q\d{1,2}h|q\d{1,2}d)\b',
#     ]
#     posology_patterns = [
#         r'\b\d+(?:[\.,]\d+)?\s*(?:cp|cps|cpr|compressa|compresse|bustina|bustine|supposta|supposte|fiala|fiale|gtt|spruzzo|puff|nebulizzazione|dose|flacone|flaconcino)\s*(?:/|al|alla|x)?\s*(?:die|dì|giorno|giorni|settimana|settimane|h|ore)?\b',
#         r'\b\d+(?:[\.,]\d+)?\s*x\s*\d+(?:[\.,]\d+)?\s*/die\b',
#         r'\b\d+(?:[\.,]\d+)?\s*(?:mg|g|ui)\s*(?:/die|/dì|/24h| al giorno| al dì| per die)\b',

#     ]
#     descriptive_patterns = [
#         r'\bogni\s+\d+\s*(?:h|ore|gg|giorni|settimane|mesi)\b',
#         r'\b\d+\s*volte?\s*(?:al|a)?\s*(?:giorno|settimana|mese|settimane|giorni)\b',
#         r'\buna\s+volta\s*(?:al|a)?\s*(?:giorno|settimana|mese)\b',
#         r'\bdue\s+volte\s*(?:die|al giorno)\b',
#         r'\btre\s+volte\s*(?:die|al giorno)\b',
#         r'\bogni\s+(?:mattina|sera|notte)\b',
#         r'\b(?:lun|mar|mer|gio|ven|sab|dom)(?:[-–](?:lun|mar|mer|gio|ven|sab|dom))*\b',
#         r'\bogni\s+\d{1,2}(?:°|o)?\s+e\s+\d{1,2}(?:°|o)?\s+del\s+mese\b',
#     ]
#     structured_patterns = [
#         r'\bd\d+\s+q\d+\b',
#         #r'\bd\d+\b',
#         #r'\bg\d+\b',
#         r'\bgiorni\s+\d+(?:[-–]\d+)+\s+ogni\s+\d+\s+giorni\b',
#         r'\bgiorni\s+\d+\s+e\s+\d+\s+ogni\s+\d+\s+giorni\b',
#     ]
#     all_patterns = abbrev_patterns + posology_patterns + descriptive_patterns + structured_patterns

#     for pattern in all_patterns:
#         match = re.search(pattern, text)
#         if match:
#             result = match.group(0)
#             result = result.replace('dì', 'die').replace('/24h', '/die')
#             return result.strip()

#     return "n/a"


# MODALITY_MAP = {
#     "orale": [
#         r"\bpo\b", r"\bp\.?o\.?\b", r"\bos\b", r"\bper os\b", r"\bper via orale\b",
#         r"\boral\b", r"\bcp per os\b", r"\bassunzione per bocca\b", r"\bvia boccale\b"
#     ],
#     "endovenosa": [
#         r"\bev\b", r"\be\.?v\.?\b", r"\bi\.?v\.?\b", r"\bvia endovenosa\b", r"\bper via endovenosa\b",
#         r"\binfusione ev\b", r"\bbolo ev\b", r"\bpush ev\b", r"\bflebo\b", r"\bterapia ev\b",
#         r"\bsomministrazione endovenosa\b", r"\bfleboclisi\b", r"\binfusione in vena\b",
#         r"\bendovena\b", r"\bev continua\b", r"\bev lenta\b", r"\bev in flebo\b", r"\bi\.?v\.? push\b"
#     ],
#     "sottocutanea": [
#         r"\bsc\b", r"\bs\.?c\.?\b", r"\bs/c\b", r"\bsottocute\b", r"\bin sottocute\b",
#         r"\bsomministrazione s\.?c\.?\b", r"\bsubcutanea\b", r"\bsub cute\b"
#     ],
#     "intramuscolare": [
#         r"\bim\b", r"\bi\.?m\.?\b", r"\bvia intramuscolare\b", r"\bin muscolo\b",
#         r"\bsomministrazione intramuscolare\b", r"\bintramuscolare\b", r"\bper muscolum\b"
#     ],
#     "rettale": [
#         r"\bpr\b", r"\bper rectum\b", r"\bsupposta\b", r"\bclistere\b", r"\bmicroclisma\b",
#         r"\bvia rettale\b", r"\bsomministrazione rettale\b"
#     ],
#     "inalatoria": [
#         r"\bvia aerosolica\b", r"\bnebulizzazione\b", r"\bspray inalato\b", r"\bpuff\b",
#         r"\bvia inalatoria\b", r"\berogatore pressurizzato\b", r"\baerosol terapia\b",
#         r"\binalazione\b", r"\binalazione spray\b", r"\bper nebulizzazione\b"
#     ],
#     "topica": [
#         r"\bvia topica\b", r"\bper via topica\b", r"\bapplicazione cutanea\b", r"\buso esterno\b",
#         r"\bcrema\b", r"\bunguento\b", r"\bad usum dermicum\b", r"\buso dermatologico\b",
#         r"\bpomata cutanea\b", r"\buso locale\b", r"\bapplicazione locale\b"
#     ],
#     "intradermica": [
#         r"\biniezione intradermica\b", r"\bvia intradermica\b"
#     ],
#     "transdermica": [
#         r"\bcerotto transdermico\b", r"\bpatch transdermico\b", r"\bcerotto a rilascio lento\b"
#     ],
#     "sublinguale": [
#         r"\bvia sublinguale\b", r"\bvia sublinguale rapida\b"
#     ],
#     "buccale": [
#         r"\bvia buccale\b", r"\bbuccale orodispersibile\b"
#     ],
#     "nasale": [
#         r"\bper via nasale\b", r"\binstillazione nasale\b", r"\bspray nasale\b"
#     ],
#     "auricolare": [
#         r"\bvia auricolare\b"
#     ],
#     "vescicale": [
#         r"\bvia uretrovescicale\b", r"\binstillazione vescicale\b"
#     ],
#     "intratecale": [
#         r"\bper via intratecale\b", r"\biniezione intratecale\b", r"\bintratecale lombare\b"
#     ],
#     "endouretrale": [
#         r"\bvia endouretrale\b", r"\binstillazione endouretrale\b"
#     ],
#     "congiuntivale": [
#         r"\bper via congiuntivale\b"
#     ],
#     "endocavitaria": [
#         r"\bvia endocavitaria\b"
#     ],
# }

# def extract_modality(text):
#     text = text.lower()
#     for modality, patterns in MODALITY_MAP.items():
#         for pattern in patterns:
#             if re.search(pattern, text):
#                 return modality
#     return "n/a"


# KNOWN_MUTATIONS = [
#     "G719A", "G719S", "G719D", "G719C", "G719X",
#     "E709K", "E709A", "L718Q", "S768I", "T790M", "C797S", "G724S",
#     "R776H", "L858R", "L861Q", "L861R", "T854A", "G154V", "T1010I", "Exon 19 del",
#     "L858R","G719X","Exon 20 ins", "L792X","L718X"
# ]

# MUTATION_TO_EXON = {
#     "G719A": "esone 18", "G719S": "esone 18", "G719D": "esone 18", "G719C": "esone 18",
#     "G719X": "esone 18", "E709K": "esone 18", "E709A": "esone 18", "L718Q": "esone 18", "G724S": "esone 18",
#     "S768I": "esone 20", "T790M": "esone 20", "C797S": "esone 20", "R776H": "esone 20", "T1010I": "esone 20",
#     "L858R": "esone 21", "L861Q": "esone 21", "L861R": "esone 21", "T854A": "esone 21", "G154V": "esone 5", "exon 19 del": "esone 19"
# }

# def extract_mutation(text):
#     text = text.upper()
#     found = []
#     for mutation in KNOWN_MUTATIONS:
#         pattern = rf'\b(?:P\.|EGFR\s*|MUTAZIONE\s*|VARIANTE\s*|SOSTITUZIONE\s*)*{mutation}\b'
#         if re.search(pattern, text):
#             found.append(mutation)
#     return "+".join(found) if found else "n/a"

# def extract_exon(text):
#     text = text.lower()
#     found = []
#     for exon_num in range(1, 31):
#         pattern = rf'\b(?:egfr|tp53)?[ :]*?(esone|exon|ex\.?|ex)\s*{exon_num}\b'
#         if re.search(pattern, text):
#             exon_label = f"esone {exon_num}"
#             if exon_label not in found:
#                 found.append(exon_label)
#     return "+".join(found) if found else "n/a"

# def get_exons_from_mutations(mutation_str):
#     if mutation_str == "n/a":
#         return "n/a"
#     exons = {MUTATION_TO_EXON[m] for m in mutation_str.split("+") if m in MUTATION_TO_EXON}
#     return "+".join(sorted(exons)) if exons else "n/a"

# def extract_all(text):
#     mutation = extract_mutation(text)
#     exon = extract_exon(text)
#     if exon == "n/a" and mutation != "n/a":
#         exon = get_exons_from_mutations(mutation)
#     return {"mutation": mutation, "exon": exon}


# def extract_collateral_effect(text):
#     text = text.lower()

#     # Verifica presenza di motivazioni cliniche (sospensione o modifica terapia)
#     if not re.search(r"(sospes[oa]|non somministrato|modificat[oa].*terapia)", text):
#         return "n/a"

#     # Rimuove contenuti indesiderati
#     text = re.sub(r"\([^)]*\)", "", text)  # rimuove parentesi e contenuto
#     text = re.sub(r"\b(g\d)\b", "", text)  # rimuove G1, G2, ecc.
#     text = re.sub(r"\b(egfr|mutazione|carcinosi|progressione|malattia|adenocarcinoma|metastasi|diagnosi|lesione|invasione vascolare|gene|tp53)\b", "", text)

#     # Estrae effetti collaterali clinici potenziali
#     matches = re.findall(r"(?:per|a causa di|per rischio di|per rischio emorragico da)\s+([a-z\s]+?)(?:$|\.|,| e |;)", text)

#     # Pulizia risultati
#     cleaned = []
#     for m in matches:
#         eff = m.strip()
#         eff = re.sub(r"\s+", " ", eff)
#         if eff and eff not in cleaned:
#             cleaned.append(eff)

#     return "+".join(cleaned) if cleaned else "n/a"


# EXCLUDE_PATTERNS = [
#     r'\b(egfr|mutato|metastasi|adenocarcinoma|carcinosi|tumore|neoplasia|alterazioni molecolari|amplificazione met|ebv-dna)\b',
#     r'\b(ecog ps|performance status|età avanzata|paziente anziano)\b',
#     r'\b(febbre|diarrea|nausea|inappetenza|astenia|dolore diffuso|danno renale da .+|cisplatino|denosumab|creatininemia|ast|alt|elevati)\b'
#      r'\betà\b', r'\ball\'?età\b', r'\bdall[ao]\b', r'\bnel\s+\d{4}\b', r'\bnel\s+[12]\d{3}\b',
#     r'\bdal\s+\d{4}\b', r'\bda\s+\d{4}\b', r'\banni\b', r'\betà di\b'
# ]


# KNOWN_COMORBIDITIES = [
#     "diabete mellito", "iperglicemia", "dmt2", "dispnea", "desaturazione", "edema",
#     "ectasia", "aneurisma", "versamento pleurico", "atelettasia", "ispessimento pleurico",
#     "focalità epatiche", "lesioni cerebrali", "tep", "embolia", "idronefrosi",
#     "linfonodi", "noduli polmonari", "gliosi", "splenomegalia", "cisti corticali",
#     "ipertrofia prostatica", "prostatite", "artrosi", "radicolopatia", "discopia",
#     "enfisema", "irritazione tracheale", "vasculite", "fibrillazione atriale", "leucemia",
#     "leucocitosi", "neutropenia", "piastrinopenia", "bradicardia", "tachicardia",
#     "irc", "insufficienza renale cronica", "insufficienza mitralica", "insufficienza aortica",
#     "dilatazione atriale", "lesione polmonare", "linfoadenopatie", "versamento ascitico",
#     "versamento peritoneale", "pirosi gastrica", "sindrome di gilbert", "morbo di basedow",
#     "covid-19", "trombosi", "diverticoli", "granulomatosi", "stenosi",
#     "lesioni encefaliche", "deficit visivo", "ipoacusia", "epilessia", "convulsioni",
#     "sindrome di parkinson", "discopatia", "ernia discale", "protrusioni", "stenosi foraminale",
#     "polipo", "difficoltà di idratazione", "sindrome neurologica", "alterazioni spondilo-artrosiche",
#     "basalioma", "frattura", "lateropulsione", "fumo attivo", "tabagismo", "dlco ridotto",
#     "compromissione uditiva", "ventricolare", "gliosi", "ampliate cavità ventricolari",
#     "ipotrofia cerebellare", "dilatazione spazi subaracnoidei", "tronco encefalico assottigliato",
#     "ipertrofia", "congestione emorroidaria", "opacità polmonari", "addensamenti", "febbre"
# ]

# def extract_comorbidity(text):
#     text = text.lower()

#     # 🔧 Rimozione contenuti non clinici (date, età)
#     # 🔧 Rimozione contenuti non clinici (date, età, periodi)
#     text = re.sub(r"\([^)]*\)", "", text)
#     text = re.sub(r"\bnel\s+\d{4}\b", "", text)
#     text = re.sub(r"\bdal\s+\d{4}\b", "", text)
#     text = re.sub(r"\bda\s+\d{4}\b", "", text)
#     text = re.sub(r"\bdal\s+\d{1,2}/\d{1,2}/\d{2,4}\b", "", text)
#     text = re.sub(r"\bil\s+\d{1,2}/\d{1,2}/\d{2,4}\b", "", text)
#     text = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "", text)
#     text = re.sub(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b", "", text)
#     text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", text)
#     text = re.sub(r"\binizio\s+\w+\b", "", text)
#     text = re.sub(r"\bdalla\s+nascita\b", "", text)
#     text = re.sub(r"\bda\s+\d+\s+anni\b", "", text)
#     text = re.sub(r"\betà\s+di\s+\d+\s+anni\b", "", text)
#     text = re.sub(r"\ball['’]?\s?età\s+di\s+\d+\s+anni\b", "", text)
#     text = re.sub(r"\bdi\s+\d+\s+anni\b", "", text)
#     text = re.sub(r"\banno\s+\d{4}\b", "", text)
#     text = re.sub(r"\b(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b", "", text)



#     # Pulizia spazi
#     text = re.sub(r"[,;]", " ", text)
#     text = re.sub(r"\s+", " ", text).strip()

#     found = []
#     for term in KNOWN_COMORBIDITIES:
#         if re.search(rf"\b{re.escape(term)}\b", text) and term not in found:
#             found.append(term)

#     return ", ".join(found) if found else "n/a"



# # NORM 2

# # # normalizza minuscole farmaci



# def normalize_medication_entry(entry: dict) -> dict:
#     """
#     Applica tutte le funzioni di normalizzazione a un dizionario di farmaco.
#     Tutti i valori stringa vengono forzati a minuscolo.
#     """
#     # Porta tutti i valori stringa in minuscolo
#     entry = {
#         k: (v.lower().strip() if isinstance(v, str) else v)
#         for k, v in entry.items()
#     }

#     # Combina i testi in un unico blocco per pattern estrattivi
#     text = " ".join([str(v) for v in entry.values() if isinstance(v, str)])

#     # Estrazione avanzata
#     mutation_exon = extract_all(text)

#     return {
#         **entry,
#         "dosage": clean_dosage(text),
#         "frequency": extract_frequency(text),
#         "period": normalize_period(text),
#         "modality": extract_modality(text),
#         "mutation": mutation_exon["mutation"],
#         "exon": mutation_exon["exon"],
#         "collateral": extract_collateral_effect(text),
#         "comorbidity": extract_comorbidity(text),
#     }




# import re

# # Unità valide (tutte minuscole)
# VALID_UNITS = [
#     'mg', 'g', 'mcg', 'μg', 'ng', 'ui', 'ml', 'gtt', 'fl',
#     'cp', 'cps', 'cpr', 'bustina', 'bustine', 'supposta', 'supposte',
#     'mEq', 'kcal', 'mg/ml', 'mg/m2', 'mg/mq', 'mg/kg', 'mg/kg/die',
#     'ui/kg', 'ml/kg', 'auc'
# ]

# # Normalizzazione unità equivalenti
# UNIT_NORMALIZATION = {
#     'μg': 'mcg',
#     'mL': 'ml',
#     'MG': 'mg',
#     'MG/ML': 'mg/ml',
#     'MG/M2': 'mg/m2',
#     'MG/MQ': 'mg/mq',
#     'CC': 'ml',
# }

# # Regex pattern principali per dosaggio
# DOSAGE_PATTERNS = [
#     r'\b\d+(?:[\.,]\d+)?\s*(mg\/kg(?:\/die)?|mg\/mq|mg\/m2|mg\/ml|ml\/kg|ui\/kg)\b',
#     r'\bauc\s*\d+(?:[\.,]\d+)?\b',
#     r'\bdose (?:flat|standard) di\s*(\d+(?:[\.,]\d+)?)\s*mg\b',
#     r'\b(?:mg|g|mcg|μg|ng|ui|ml|gtt|fl|mEq|kcal)\s*\d+(?:[\.,]\d+)?\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|μg|ng|ui|ml|gtt|fl|mEq|kcal)\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|μg|ng|ui|ml)\s*(tot(?:ali)?|complessivi|pari a|circa)\b',
#     r'\b\d+(?:[\.,]\d+)?\s*\+\s*\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\s*→\s*\d+(?:[\.,]\d+)?\b',
#     r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\s*e\s*\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\b',
#     r'\b\d+\s*(?:cp|cps|cpr|bustina|bustine|supposta|supposte)\s*da\s*(\d+(?:[\.,]\d+)?)\s*(mg|mcg|g|ml)\b',
#     r'\b(mg|g|mcg|μg|ml|ui)\s*\d+(?:[\.,]\d+)?\b',
# ]

# # Rimozione parole spurie
# MODIFIERS = ['tot', 'totali', 'complessivi', 'pari a', 'circa']

# def normalize_unit(unit):
#     unit = unit.lower()
#     return UNIT_NORMALIZATION.get(unit.upper(), unit)

# def clean_dosage(text):
#     text = text.lower()
#     for pattern in DOSAGE_PATTERNS:
#         match = re.search(pattern, text)
#         if match:
#             if 'auc' in match.group(0):
#                 return match.group(0).replace(' ', '').upper()
#             raw = match.group(0)
#             raw = re.sub(r'[,]', '.', raw)
#             raw = re.sub(r'\s+', ' ', raw)
#             raw = re.sub(r'\b(' + '|'.join(MODIFIERS) + r')\b', '', raw).strip()
#             m = re.search(r'(\d+(?:\.\d+)?)\s*(mg\/kg\/die|mg\/kg|mg\/ml|mg\/m2|mg\/mq|ml\/kg|ui\/kg|mg|g|mcg|μg|ml|ui|gtt|fl|mEq|kcal)', raw)
#             if m:
#                 val = m.group(1)
#                 unit = normalize_unit(m.group(2))
#                 return f"{val} {unit}"
#     return 'n/a'


# MODALITY_MAP = {
#     "orale": [
#         r"\bpo\b", r"\bp\.?o\.?\b", r"\bos\b", r"\bper os\b", r"\bper via orale\b",
#         r"\boral\b", r"\bcp per os\b", r"\bassunzione per bocca\b", r"\bvia boccale\b", r"\borale\b"
#     ],
#     "endovenosa": [
#         r"\bev\b", r"\be\.?v\.?\b", r"\bi\.?v\.?\b", r"\bvia endovenosa\b", r"\bper via endovenosa\b",
#         r"\binfusione ev\b", r"\bbolo ev\b", r"\bpush ev\b", r"\bflebo\b", r"\bterapia ev\b",
#         r"\bsomministrazione endovenosa\b", r"\bfleboclisi\b", r"\binfusione in vena\b",
#         r"\bendovena\b", r"\bev continua\b", r"\bev lenta\b", r"\bev in flebo\b", r"\bi\.?v\.? push\b"
#     ],
#     "sottocutanea": [
#         r"\bsc\b", r"\bs\.?c\.?\b", r"\bs/c\b", r"\bsottocute\b", r"\bin sottocute\b",
#         r"\bsomministrazione s\.?c\.?\b", r"\bsubcutanea\b", r"\bsub cute\b"
#     ],
#     "intramuscolare": [
#         r"\bim\b", r"\bi\.?m\.?\b", r"\bvia intramuscolare\b", r"\bin muscolo\b",
#         r"\bsomministrazione intramuscolare\b", r"\bintramuscolare\b", r"\bper muscolum\b"
#     ],
#     "rettale": [
#         r"\bpr\b", r"\bper rectum\b", r"\bsupposta\b", r"\bclistere\b", r"\bmicroclisma\b",
#         r"\bvia rettale\b", r"\bsomministrazione rettale\b"
#     ],
#     "inalatoria": [
#         r"\bvia aerosolica\b", r"\bnebulizzazione\b", r"\bspray inalato\b", r"\bpuff\b",
#         r"\bvia inalatoria\b", r"\berogatore pressurizzato\b", r"\baerosol terapia\b",
#         r"\binalazione\b", r"\binalazione spray\b", r"\bper nebulizzazione\b"
#     ],
#     "topica": [
#         r"\bvia topica\b", r"\bper via topica\b", r"\bapplicazione cutanea\b", r"\buso esterno\b",
#         r"\bcrema\b", r"\bunguento\b", r"\bad usum dermicum\b", r"\buso dermatologico\b",
#         r"\bpomata cutanea\b", r"\buso locale\b", r"\bapplicazione locale\b"
#     ],
#     "intradermica": [
#         r"\biniezione intradermica\b", r"\bvia intradermica\b"
#     ],
#     "transdermica": [
#         r"\bcerotto transdermico\b", r"\bpatch transdermico\b", r"\bcerotto a rilascio lento\b"
#     ],
#     "sublinguale": [
#         r"\bvia sublinguale\b", r"\bvia sublinguale rapida\b"
#     ],
#     "buccale": [
#         r"\bvia buccale\b", r"\bbuccale orodispersibile\b"
#     ],
#     "nasale": [
#         r"\bper via nasale\b", r"\binstillazione nasale\b", r"\bspray nasale\b"
#     ],
#     "auricolare": [
#         r"\bvia auricolare\b"
#     ],
#     "vescicale": [
#         r"\bvia uretrovescicale\b", r"\binstillazione vescicale\b"
#     ],
#     "intratecale": [
#         r"\bper via intratecale\b", r"\biniezione intratecale\b", r"\bintratecale lombare\b"
#     ],
#     "endouretrale": [
#         r"\bvia endouretrale\b", r"\binstillazione endouretrale\b"
#     ],
#     "congiuntivale": [
#         r"\bper via congiuntivale\b"
#     ],
#     "endocavitaria": [
#         r"\bvia endocavitaria\b"
#     ],
# }

# def extract_modality(text):
#     text = text.lower()
#     for modality, patterns in MODALITY_MAP.items():
#         for pattern in patterns:
#             if re.search(pattern, text):
#                 return modality
#     return "n/a"



# def extract_collateral_effect(text):
#     text = text.lower()

#     # Verifica presenza di motivazioni cliniche (sospensione o modifica terapia)
#     if not re.search(r"(sospes[oa]|non somministrato|modificat[oa].*terapia)", text):
#         return "n/a"

#     # Rimuove contenuti indesiderati
#     text = re.sub(r"\([^)]*\)", "", text)  # rimuove parentesi e contenuto
#     text = re.sub(r"\b(g\d)\b", "", text)  # rimuove G1, G2, ecc.
#     text = re.sub(r"\b(egfr|mutazione|carcinosi|progressione|malattia|adenocarcinoma|metastasi|diagnosi|lesione|invasione vascolare|gene|tp53)\b", "", text)

#     # Estrae effetti collaterali clinici potenziali
#     matches = re.findall(r"(?:per|a causa di|per rischio di|per rischio emorragico da)\s+([a-z\s]+?)(?:$|\.|,| e |;)", text)

#     # Pulizia risultati
#     cleaned = []
#     for m in matches:
#         eff = m.strip()
#         eff = re.sub(r"\s+", " ", eff)
#         if eff and eff not in cleaned:
#             cleaned.append(eff)

#     return "+".join(cleaned) if cleaned else "n/a"


# EXCLUDE_PATTERNS = [
#     r'\b(egfr|mutato|metastasi|adenocarcinoma|carcinosi|tumore|neoplasia|alterazioni molecolari|amplificazione met|ebv-dna)\b',
#     r'\b(ecog ps|performance status|età avanzata|paziente anziano)\b',
#     r'\b(febbre|diarrea|nausea|inappetenza|astenia|dolore diffuso|danno renale da .+|cisplatino|denosumab|creatininemia|ast|alt|elevati)\b'
#      r'\betà\b', r'\ball\'?età\b', r'\bdall[ao]\b', r'\bnel\s+\d{4}\b', r'\bnel\s+[12]\d{3}\b',
#     r'\bdal\s+\d{4}\b', r'\bda\s+\d{4}\b', r'\banni\b', r'\betà di\b'
# ]


# # =========================
# # PERIOD (sostituisce la tua normalize_period "semplice")
# # =========================
# import re, unicodedata
# from typing import List, Dict, Tuple

# def normalize_period(text: str) -> str:
#     text = text.lower()
#     # numero + ciclo/cicli + varianti EN
#     match = re.search(r'(\d+)\s*(?:ciclo|cicli|cycle|cycles)\b', text)
#     if match:
#         num = int(match.group(1))
#         return "1 ciclo" if num == 1 else f"{num} cicli"
#     return "n/a"


# # =========================
# # FREQUENCY (sostituisce totalmente extract_frequency)
# # =========================
# _NUM = r"\d+(?:[.,]\d+)?"

# def _norm_num(s: str) -> str:
#     s = s.replace(",", ".")
#     try:
#         f = float(s)
#         return str(int(f)) if f.is_integer() else str(f)
#     except Exception:
#         return s

# def _norm_spaces(s: str) -> str:
#     t = (s or "").lower()
#     t = unicodedata.normalize("NFKD", t).replace("\u00a0", " ").replace("\u200b", "")
#     t = t.replace("×", "x")
#     t = t.replace("dì", "die")  # unifica 'dì'→'die'
#     t = re.sub(r"\s+", " ", t)
#     return f" {t} "

# CP_FORMS = (
#     r"(?:cp|cps|cpr|comp(?:ressa|resse)?|compressa|compresse|"
#     r"caps(?:ula|ule)?|caps|pastiglia|pastiglie|pillola|pillole|"
#     r"tab|tabs|tabl|tablet|tav|comp\.)"
# )

# def extract_frequency(text: str) -> str:
#     if not text:
#         return "n/a"

#     t = _norm_spaces(text)

#     # 1) mg/die
#     m = re.search(
#         rf"\b({_NUM})\s*mg\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
#     )
#     if m:
#         return f"{_norm_num(m.group(1))} mg/die"

#     # 2) cp/die
#     m = re.search(
#         rf"\b({_NUM})\s*{CP_FORMS}\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
#     )
#     if m:
#         return f"{_norm_num(m.group(1))} cp/die"

#     # 3) gtt/die
#     m = re.search(
#         rf"\b({_NUM})\s*(?:gtt|goccia|gocce)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
#     )
#     if m:
#         return f"{_norm_num(m.group(1))} gtt/die"

#     # 4) puff/die
#     m = re.search(
#         rf"\b({_NUM})\s*(?:puff|spruzzo|spruzzi|inalazione|inalazioni)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
#     )
#     if m:
#         return f"{_norm_num(m.group(1))} puff/die"

#     # 5) fiala/die
#     m = re.search(
#         rf"\b({_NUM})\s*(?:fiala|fiale|flacone|flaconi|flaconcino|flaconcini)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
#     )
#     if m:
#         return f"{_norm_num(m.group(1))} fiala/die"

#     # 6) bustina/die
#     m = re.search(
#         rf"\b({_NUM})\s*(?:bustina|bustine)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
#     )
#     if m:
#         return f"{_norm_num(m.group(1))} bustina/die"

#     # 7) qd / once daily (senza unità specifiche)
#     if re.search(r"\bq\.?d\.?\b", t):
#         return "qd"
#     if re.search(r"\bod\b", t) and re.search(r"\b(die|giorn|daily|assunz|dose|per os|po)\b", t):
#         return "qd"
#     if re.search(r"\bonce\s*daily\b|\bdaily\b", t):
#         return "qd"
#     if re.search(r"\buna\s+volta\s+(?:al|a)\s+giorno\b", t):
#         return "qd"
#     if re.search(r"\bogni\s+giorno\b|\bgiornalier[oa]\b|\bper\s+die\b", t):
#         return "qd"
#     if re.search(r"\bq\s*24\s*h\b|\bq24h\b|\bogni\s*24\s*ore\b", t):
#         return "qd"
#     if re.search(rf"\b1\s*/\s*(?:die|giorno|24h)\b", t) and not re.search(r"\bmg\b|cp|cpr|compres|caps|pillol|tab|gtt|puff|fiala|bustina", t):
#         return "qd"
#     if re.search(r"\s/die\b", t) and not re.search(r"\bmg\b|cp|cpr|compres|caps|pillol|tab|gtt|puff|fiala|bustina", t):
#         return "qd"

#     # 8) solo unità senza "al giorno"
#     m = re.search(rf"\b({_NUM})\s*{CP_FORMS}\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
#     if m:
#         return f"{_norm_num(m.group(1))} cp"
#     m = re.search(rf"\b({_NUM})\s*(?:gtt|goccia|gocce)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
#     if m:
#         return f"{_norm_num(m.group(1))} gtt"
#     m = re.search(rf"\b({_NUM})\s*(?:puff|spruzzo|spruzzi|inalazione|inalazioni)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
#     if m:
#         return f"{_norm_num(m.group(1))} puff"
#     m = re.search(rf"\b({_NUM})\s*(?:fiala|fiale|flacone|flaconi|flaconcino|flaconcini)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
#     if m:
#         return f"{_norm_num(m.group(1))} fiala"
#     m = re.search(rf"\b({_NUM})\s*(?:bustina|bustine)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
#     if m:
#         return f"{_norm_num(m.group(1))} bustina"

#     return "n/a"



# # =========================
# # COMORBIDITÀ (drop-in con rimozione date/età multilingue + sinonimi EN→IT)
# # =========================
# import re, unicodedata

# _NEGATIONS = re.compile(
#     r"\b(assenza di|afebbril\w*|nega(?:to|ta)?|non\s+(?:ha|presenta|evidenza|documenta|riporta)|"
#     r"senza|negativo\a?\s+per|no\s+(?:segni|sintomi|evidenza)|"
#     r"denies|no history of|negative for)\b", re.IGNORECASE
# )

# # Canonici IT già presenti + alcune new entry frequenti
# KNOWN_COMORBIDITIES = [
#     "diabete mellito", "iperglicemia", "dmt2", "dispnea", "desaturazione", "edema",
#     "ectasia", "aneurisma", "versamento pleurico", "atelettasia", "ispessimento pleurico",
#     "focalità epatiche", "lesioni cerebrali", "tep", "embolia", "idronefrosi",
#     "linfonodi", "noduli polmonari", "gliosi", "splenomegalia", "cisti corticali",
#     "ipertrofia prostatica", "prostatite", "artrosi", "radicolopatia", "discopia",
#     "enfisema", "irritazione tracheale", "vasculite", "fibrillazione atriale", "leucemia",
#     "leucocitosi", "neutropenia", "piastrinopenia", "bradicardia", "tachicardia",
#     "irc", "insufficienza renale cronica", "insufficienza mitralica", "insufficienza aortica",
#     "dilatazione atriale", "lesione polmonare", "linfoadenopatie", "versamento ascitico",
#     "versamento peritoneale", "pirosi gastrica", "sindrome di gilbert", "morbo di basedow",
#     "covid-19", "trombosi", "diverticoli", "granulomatosi", "stenosi",
#     "lesioni encefaliche", "deficit visivo", "ipoacusia", "epilessia", "convulsioni",
#     "sindrome di parkinson", "discopatia", "ernia discale", "protrusioni", "stenosi foraminale",
#     "polipo", "difficoltà di idratazione", "sindrome neurologica", "alterazioni spondilo-artrosiche",
#     "basalioma", "frattura", "lateropulsione", "fumo attivo", "tabagismo", "dlco ridotto",
#     "compromissione uditiva", "ventricolare", "gliosi", "ampliate cavità ventricolari",
#     "ipotrofia cerebellare", "dilatazione spazi subaracnoidei", "tronco encefalico assottigliato",
#     "ipertrofia", "congestione emorroidaria", "opacità polmonari", "addensamenti", "febbre",
#     # IT canonici per mapping EN:
#     "ipertensione", "frattura del femore", "malattia polmonare preesistente", "tabagismo",
# ]

# # Sinonimi/varianti EN (e qualche sigla) → canonico IT
# # (match case-insensitive, ripulisce parentesi tipo "(not specified)")
# COMORBID_SYNONYMS = [
#     (re.compile(r"\bdiabet(?:es|ic)\s+mellitus\b|\btype\s*2\s+diabet(?:es)?\b|\bdm\s*2\b|\bdmt2\b", re.I), "diabete mellito"),
#     (re.compile(r"\bhypertension\b|\bhigh\s*blood\s*pressure\b|^htn\b", re.I), "ipertensione"),
#     (re.compile(r"\bfracture\s+of\s+(?:the\s+)?femur\b|\bfemoral\s+fracture\b", re.I), "frattura del femore"),
#     (re.compile(r"\bpre[-\s]?existing\s+lung\s+disease\b|\bpreexisting\s+lung\s+disease\b|\bchronic\s+lung\s+disease\b", re.I),
#      "malattia polmonare preesistente"),
#     (re.compile(r"\bsmoking\s+history\b|\b(?:tobacco|nicotine)\s+use\s+history\b|\b(?:ex|former)[-\s]?smoker\b|\bcurrent\s+smoker\b|\bsmoker\b", re.I),
#      "tabagismo"),
#     # Extra utili comuni:
#     (re.compile(r"\bobesity\b|\bobese\b", re.I), "obesità"),
#     (re.compile(r"\bhypercholesterolemia\b|\bdyslipid(?:emia|aemia)\b", re.I), "dislipidemia"),
# ]

# def _preclean_dates(text: str) -> str:
#     """
#     Pulizia aggressiva e multilingue di date/età/tempi:
#     - yyyy-mm-dd, dd/mm/yyyy, dd.mm.yy, yyyy/mm/dd, 12/05, '14
#     - mesi IT/EN (anche con inizio/fine/metà / early/late/mid)
#     - giorni settimana IT/EN e range (lun-ven / mon–fri)
#     - settimane/quarter (settimana 34/2023, w34 2023, q1/t1 2022)
#     - orari (ore 14:30, 14h, 09:00)
#     - intervalli “dal … al …” / “from … to …”, “between … and …”
#     - età/durate: “dall’età di 7 aa”, “aged 12”, “from age 12”, “since birth”
#     - note cronologiche: “dal 2014”, “since 2014”, “from 2014”
#     - parentesi che contengono solo date/anni/orari
#     """
#     t = (text or "")
#     t = unicodedata.normalize("NFKD", t)
#     t = t.replace("\u00A0", " ").replace("’", "'").replace("“", '"').replace("”", '"')
#     t = re.sub(r"\s+", " ", t).strip()

#     # --- base numeriche ---
#     numeric = [
#         r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
#         r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
#         r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b",
#         r"\b\d{1,2}[/-]\d{1,2}\b",
#         r"\b'\d{2}\b",
#         r"\b(19|20)\d{2}\b",
#     ]

#     # --- mesi IT + EN ---
#     mesi_it = r"(?:gen(?:naio)?|feb(?:braio)?|mar(?:zo)?|apr(?:ile)?|mag(?:gio)?|giu(?:gno)?|lug(?:lio)?|ago(?:sto)?|set(?:tembre)?|ott(?:obre)?|nov(?:embre)?|dic(?:embre)?)"
#     mesi_en = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
#     months = [
#         rf"\b(?:inizio|fine|met[àa]|early|late|mid)?\s*{mesi_it}\.?\s*(?:'\d{{2}}|(?:19|20)\d{{2}})?\b",
#         rf"\b(?:early|late|mid)?\s*{mesi_en}\.?\s*(?:'\d{{2}}|(?:19|20)\d{{2}})?\b",
#     ]

#     # --- giorni settimana IT + EN + range ---
#     dow_it = r"(?:lun(?:ed[iì])?|mar(?:ted[iì])?|mer(?:coled[iì])?|gio(?:ved[iì])?|ven(?:erd[iì])?|sab(?:ato)?|dom(?:enica)?)"
#     dow_en = r"(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
#     weekdays = [
#         rf"\b{dow_it}\b", rf"\b{dow_en}\b",
#         rf"\b(?:lun|mar|mer|gio|ven|sab|dom)(?:[-–](?:lun|mar|mer|gio|ven|sab|dom))+\b",
#         rf"\b(?:mon|tue|wed|thu|fri|sat|sun)(?:[-–](?:mon|tue|wed|thu|fri|sat|sun))+\b",
#     ]

#     # --- settimane/trim/quarter ---
#     wk_q = [
#         r"\bsettimana\s*\d{1,2}(?:/\d{2,4})?\b",
#         r"\bw\s*\d{1,2}\s*(?:\d{4})?\b",
#         r"\b(?:q|t)\s*[1-4]\s*(?:\d{4})?\b",
#         r"\b(?:quarter|trimester)\s*[1-4]\s*(?:\d{4})?\b",
#     ]

#     # --- orari ---
#     times = [
#         r"\b(?:ore\s*)?\d{1,2}:\d{2}\b",
#         r"\b(?:ore\s*)?\d{1,2}\s*h\b",
#         r"\bore\s*\d{1,2}\b",
#     ]

#     # --- range e riferimenti temporali ---
#     ranges = [
#         r"\b(?:dal|dall[ao]?)\s+[^,;.]{1,30}?\s+(?:al|all[ao]?)\s+[^,;.]{1,30}\b",
#         r"\bfrom\s+[^,;.]{1,30}?\s+to\s+[^,;.]{1,30}\b",
#         r"\bbetween\s+[^,;.]{1,30}?\s+and\s+[^,;.]{1,30}\b",
#         r"\bsince\s+(?:birth|childhood|\d{4})\b",
#         r"\bfrom\s+(?:\d{4}|birth|childhood)\b",
#         r"\bsince\s+\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
#     ]

#     # --- età/durate IT+EN ---
#     ages = [
#         r"\b[>~≈]?\s*\d+\s*(?:anni|aa|a)\b",
#         r"\bda\s+\d+\s*(?:anni|aa|a)\b",
#         r"\ball['’]?\s?et[aà]\s+di\s+\d+\s+anni\b",
#         r"\bdi\s+\d+\s+anni\b",
#         r"\bdalla\s+nascita\b",
#         r"\baged?\s+\d+\b",
#         r"\bfrom\s+age\s+\d+\b",
#         r"\b(?:years?\s+old|yo|yrs?\s+old)\b",
#         r"\bsince\s+age\s+\d+\b",
#     ]

#     # --- parentesi con soli riferimenti cronologici (entro 50 char) ---
#     paren_time = [
#         r"\((?=[^)]{0,50}\b(?:\d{4}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
#         r"(?:ore\s*)?\d{1,2}:\d{2}|"
#         r"(?:gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))\b)[^)]*\)"
#     ]

#     # Applica rimozioni
#     for rx in (paren_time + ranges + numeric + months + weekdays + wk_q + times + ages):
#         t = re.sub(rx, " ", t, flags=re.IGNORECASE)

#     # Qualificatori superflui tipici inglesi nelle comorbidità
#     t = re.sub(r"\((?:not\s+specified|unspecified|history\s+of)\)", " ", t, flags=re.I)

#     # Pulizia finale
#     t = re.sub(r"[,;/]", " ", t)
#     t = re.sub(r"\s+", " ", t).strip()
#     return t


# def extract_comorbidity(text: str, return_list: bool = False) -> str | list[str]:
#     """
#     - Rimuove riferimenti cronologici/età in IT/EN.
#     - Riconosce comorbidità italiane note (KNOWN_COMORBIDITIES).
#     - Aggiunge sinonimi inglesi via COMORBID_SYNONYMS mappando a un etichetta canonica italiana.
#     - Evita match negati guardando una finestra a sinistra (60 char).
#     """
#     if not text:
#         return [] if return_list else "n/a"

#     t = _preclean_dates(text)

#     found: list[str] = []

#     # 1) Sinonimi EN → canonico IT
#     for rx, canon in COMORBID_SYNONYMS:
#         for m in rx.finditer(t):
#             left = t[max(0, m.start()-60):m.start()]
#             if _NEGATIONS.search(left):
#                 continue
#             if canon not in found:
#                 found.append(canon)

#     # 2) Termini IT noti (match preciso su parola)
#     for term in KNOWN_COMORBIDITIES:
#         rx = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
#         for m in rx.finditer(t):
#             left = t[max(0, m.start()-60):m.start()]
#             if _NEGATIONS.search(left):
#                 continue
#             if term not in found:
#                 found.append(term)

#     if return_list:
#         return found
#     return ", ".join(found) if found else "n/a"

# # # # =========================
# # # # MUTATION + EXON (sostituiscono extract_mutation/extract_exon/get_exons_from_mutations/extract_all)
# # # # =========================
# _OCR_FIXES = [
#     (re.compile(r'\bI858R\b', re.I), 'L858R'),
#     (re.compile(r'\bI861Q\b', re.I), 'L861Q'),
#     (re.compile(r'\bI861R\b', re.I), 'L861R'),
#     (re.compile(r'\bI718Q\b', re.I), 'L718Q'),
#     (re.compile(r'\bT79OM\b', re.I), 'T790M'),
#     (re.compile(r'\bC79?7S\b', re.I), 'C797S'),
#     (re.compile(r'\bG7I9([A-Z])\b', re.I), r'G719\1'),
# ]

# def _norm(s: str) -> str:
#     t = s or ""
#     for rx, rp in _OCR_FIXES: t = rx.sub(rp, t)
#     t = re.sub(r'[\u00A0·•]+', ' ', t)
#     t = re.sub(r'\s+', ' ', t)
#     return t

# KNOWN_MUTATIONS = [
#     "G719A","G719S","G719D","G719C","G719X","E709K","E709A","L718Q","L718X","G724S",
#     "S768I","T790M","C797S","R776H","T1010I","L792X",
#     "L858R","L861Q","L861R","T854A",
#     "G154V",
#     "Exon 19 del","Exon 20 ins",
# ]

# MUTATION_TO_EXON = {
#     "G719A":"esone 18","G719S":"esone 18","G719D":"esone 18","G719C":"esone 18","G719X":"esone 18",
#     "E709K":"esone 18","E709A":"esone 18","L718Q":"esone 18","L718X":"esone 18","G724S":"esone 18",
#     "S768I":"esone 20","T790M":"esone 20","C797S":"esone 20","R776H":"esone 20","T1010I":"esone 20","L792X":"esone 20",
#     "L858R":"esone 21","L861Q":"esone 21","L861R":"esone 21","T854A":"esone 21",
#     "G154V":"esone 5",
#     "Exon 19 del":"esone 19","Exon 20 ins":"esone 20",
# }

# _NEGATIONS_MUT = re.compile(r'\b(assenza di|wild[- ]?type|wt|negativo per|no (?:evidenza|mutazioni?))\b', re.I)
# _EX_LABEL = r'(?:esone|exon|ex\.?|ex)\s*'
# _MUT_PREFIX = r'(?:\b(?:EGFR|ERBB1)\b[ \t:/-]*)?(?:\b(?:p\.?|mutazione|variante|sostituzione)\b[ \t:/-]*)?'
# _AA = r'[ACDEFGHIKLMNPQRSTVWY]'

# def _dedup(seq: List[str]) -> List[str]:
#     seen, out = set(), []
#     for x in seq:
#         if x not in seen:
#             seen.add(x); out.append(x)
#     return out

# def _find_mutation_spans(t: str) -> List[Dict]:
#     spans = []
#     _DEL_WORD = r'(?:del(?:ezione)?|deletion|Δ|del\.)'
#     _INS_WORD = r'(?:ins(?:erzione)?|insertion|dup(?:licazione)?)'
#     ex19 = re.compile(rf'(?:\b(?:EGFR|ERBB1)\b[ \t:/-]*)?(?:{_EX_LABEL}?19[ \t-]*{_DEL_WORD}|{_DEL_WORD}[ \t-]*{_EX_LABEL}?19|{_EX_LABEL}19[ \t-]*(?:del|deletion|Δ))', re.I)
#     ex20 = re.compile(rf'(?:\b(?:EGFR|ERBB1)\b[ \t:/-]*)?(?:{_EX_LABEL}?20[ \t-]*{_INS_WORD}|{_INS_WORD}[ \t-]*{_EX_LABEL}?20|{_EX_LABEL}20[ \t-]*(?:ins|insertion|dup))', re.I)
#     for m in ex19.finditer(t):
#         spans.append({"type":"mutation","value":"Exon 19 del","start":m.start(),"end":m.end(),"source":"struct"})
#     for m in ex20.finditer(t):
#         spans.append({"type":"mutation","value":"Exon 20 ins","start":m.start(),"end":m.end(),"source":"struct"})

#     for tok in KNOWN_MUTATIONS:
#         if tok.startswith("Exon "):
#             continue
#         rx = re.compile(rf'{_MUT_PREFIX}\b{re.escape(tok)}\b', re.I)
#         for m in rx.finditer(t):
#             spans.append({"type":"mutation","value":tok,"start":m.start(),"end":m.end(),"source":"catalog"})

#     rx_gen = re.compile(rf'{_MUT_PREFIX}\b({_AA})(\d{{2,4}})({_AA}|X)\b', re.I)
#     for m in rx_gen.finditer(t):
#         cand = f"{m.group(1).upper()}{m.group(2)}{m.group(3).upper()}"
#         if cand in KNOWN_MUTATIONS:
#             spans.append({"type":"mutation","value":cand,"start":m.start(),"end":m.end(),"source":"generic"})
#     return spans

# def _find_exon_spans(t: str) -> List[Dict]:
#     spans = []
#     rx_exon = re.compile(rf'(?:\b(?:EGFR|ERBB1)\b[ \t:/-]*)?(?:{_EX_LABEL})0*([1-2]?\d|30)\b', re.I)
#     for m in rx_exon.finditer(t):
#         n = int(m.group(1))
#         spans.append({"type":"exon","value":f"esone {n}","n":n,"start":m.start(),"end":m.end(),"source":"explicit"})
#     return spans

# def _within_window(a: Tuple[int,int], b: Tuple[int,int], max_dist: int = 80) -> bool:
#     a_mid = (a[0]+a[1])//2; b_mid = (b[0]+b[1])//2
#     return abs(a_mid - b_mid) <= max_dist

# def extract_all_plus(text: str, mapping_policy: str = "fallback") -> Dict[str, object]:
#     raw = text or ""
#     t = _norm(raw)

#     if _NEGATIONS_MUT.search(t):
#         return {"mutation":"n/a","exon":"n/a","links":[],"confidence":"high","conflict":False}

#     m_spans = _find_mutation_spans(t)
#     e_spans = _find_exon_spans(t)

#     muts = _dedup([s["value"] for s in m_spans])
#     exons = _dedup([s["value"] for s in e_spans])

#     links = []
#     for ms in m_spans:
#         mval = ms["value"]
#         near = sorted(
#             [es for es in e_spans if _within_window((ms["start"], ms["end"]), (es["start"], es["end"]), 80)],
#             key=lambda es: abs(((ms["start"]+ms["end"])//2) - ((es["start"]+es["end"])//2))
#         )
#         if near:
#             links.append((mval, near[0]["value"]))

#     inferred = []
#     if mapping_policy in ("always","fallback"):
#         for m in muts:
#             ex_inf = MUTATION_TO_EXON.get(m)
#             if ex_inf and (mapping_policy == "always" or (mapping_policy == "fallback" and not exons)):
#                 inferred.append(ex_inf)

#     if mapping_policy == "always":
#         final_exons = _dedup(exons + [e for e in inferred if e not in exons]) if (exons or inferred) else []
#     elif mapping_policy == "fallback":
#         final_exons = exons if exons else _dedup(inferred)
#     else:
#         final_exons = exons

#     conflict = False
#     for m, e_near in links:
#         e_map = MUTATION_TO_EXON.get(m)
#         if e_map and e_near != e_map:
#             conflict = True
#             break

#     has_mut = bool(muts and muts != ["n/a"])
#     has_expl_exon = bool(exons)
#     has_link = bool(links)
#     if has_mut and (has_expl_exon or has_link):
#         confidence = "high"
#     elif has_mut and final_exons:
#         confidence = "medium"
#     elif has_mut:
#         confidence = "low"
#     else:
#         confidence = "n/a"

#     return {
#         "mutation": "+".join(muts) if muts else "n/a",
#         "exon": "+".join(final_exons) if final_exons else "n/a",
#         "links": links,
#         "confidence": confidence,
#         "conflict": conflict
#     }

# def extract_all(text: str) -> Dict[str,str]:
#     """Wrapper compatibile con il tuo pipeline"""
#     res = extract_all_plus(text, mapping_policy="fallback")
#     return {"mutation": res["mutation"], "exon": res["exon"]}




# NORM 3


# NORM 2

# # normalizza minuscole farmaci



def normalize_medication_entry(entry: dict) -> dict:
    """
    Applica tutte le funzioni di normalizzazione a un dizionario di farmaco.
    Tutti i valori stringa vengono forzati a minuscolo.
    """
    # Porta tutti i valori stringa in minuscolo
    entry = {
        k: (v.lower().strip() if isinstance(v, str) else v)
        for k, v in entry.items()
    }

    # Combina i testi in un unico blocco per pattern estrattivi
    text = " ".join([str(v) for v in entry.values() if isinstance(v, str)])

    # Estrazione avanzata
    mutation_exon = extract_all(text)

    return {
        **entry,
        "dosage": clean_dosage(text),
        "frequency": extract_frequency(text),
        "period": normalize_period(text),
        "modality": extract_modality(text),
        "mutation": mutation_exon["mutation"],
        "exon": mutation_exon["exon"],
        "collateral": extract_collateral_effect(text),
        "comorbidity": extract_comorbidity(text),
    }




import re

# Unità valide (tutte minuscole)
VALID_UNITS = [
    'mg', 'g', 'mcg', 'μg', 'ng', 'ui', 'ml', 'gtt', 'fl',
    'cp', 'cps', 'cpr', 'bustina', 'bustine', 'supposta', 'supposte',
    'mEq', 'kcal', 'mg/ml', 'mg/m2', 'mg/mq', 'mg/kg', 'mg/kg/die',
    'ui/kg', 'ml/kg', 'auc'
]

# Normalizzazione unità equivalenti
UNIT_NORMALIZATION = {
    'μg': 'mcg',
    'mL': 'ml',
    'MG': 'mg',
    'MG/ML': 'mg/ml',
    'MG/M2': 'mg/m2',
    'MG/MQ': 'mg/mq',
    'CC': 'ml',
}

# Regex pattern principali per dosaggio
DOSAGE_PATTERNS = [
    r'\b\d+(?:[\.,]\d+)?\s*(mg\/kg(?:\/die)?|mg\/mq|mg\/m2|mg\/ml|ml\/kg|ui\/kg)\b',
    r'\bauc\s*\d+(?:[\.,]\d+)?\b',
    r'\bdose (?:flat|standard) di\s*(\d+(?:[\.,]\d+)?)\s*mg\b',
    r'\b(?:mg|g|mcg|μg|ng|ui|ml|gtt|fl|mEq|kcal)\s*\d+(?:[\.,]\d+)?\b',
    r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|μg|ng|ui|ml|gtt|fl|mEq|kcal)\b',
    r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|μg|ng|ui|ml)\s*(tot(?:ali)?|complessivi|pari a|circa)\b',
    r'\b\d+(?:[\.,]\d+)?\s*\+\s*\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\b',
    r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\s*→\s*\d+(?:[\.,]\d+)?\b',
    r'\b\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\s*e\s*\d+(?:[\.,]\d+)?\s*(mg|g|mcg|ml|ui)\b',
    r'\b\d+\s*(?:cp|cps|cpr|bustina|bustine|supposta|supposte)\s*da\s*(\d+(?:[\.,]\d+)?)\s*(mg|mcg|g|ml)\b',
    r'\b(mg|g|mcg|μg|ml|ui)\s*\d+(?:[\.,]\d+)?\b',
]

# Rimozione parole spurie
MODIFIERS = ['tot', 'totali', 'complessivi', 'pari a', 'circa']

def normalize_unit(unit):
    unit = unit.lower()
    return UNIT_NORMALIZATION.get(unit.upper(), unit)

def clean_dosage(text):
    text = text.lower()
    for pattern in DOSAGE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            if 'auc' in match.group(0):
                return match.group(0).replace(' ', '').upper()
            raw = match.group(0)
            raw = re.sub(r'[,]', '.', raw)
            raw = re.sub(r'\s+', ' ', raw)
            raw = re.sub(r'\b(' + '|'.join(MODIFIERS) + r')\b', '', raw).strip()
            m = re.search(r'(\d+(?:\.\d+)?)\s*(mg\/kg\/die|mg\/kg|mg\/ml|mg\/m2|mg\/mq|ml\/kg|ui\/kg|mg|g|mcg|μg|ml|ui|gtt|fl|mEq|kcal)', raw)
            if m:
                val = m.group(1)
                unit = normalize_unit(m.group(2))
                return f"{val} {unit}"
    return 'n/a'


# MODALITY_MAP = {
#     "orale": [
#         r"\bpo\b", r"\bp\.?o\.?\b", r"\bos\b", r"\bper os\b", r"\bper via orale\b",
#         r"\boral\b", r"\bcp per os\b", r"\bassunzione per bocca\b", r"\bvia boccale\b", r"\borale\b"
#     ],
#     "endovenosa": [
#         r"\bev\b", r"\be\.?v\.?\b", r"\bi\.?v\.?\b", r"\bvia endovenosa\b", r"\bper via endovenosa\b",
#         r"\binfusione ev\b", r"\bbolo ev\b", r"\bpush ev\b", r"\bflebo\b", r"\bterapia ev\b",
#         r"\bsomministrazione endovenosa\b", r"\bfleboclisi\b", r"\binfusione in vena\b",
#         r"\bendovena\b", r"\bev continua\b", r"\bev lenta\b", r"\bev in flebo\b", r"\bi\.?v\.? push\b"
#     ],
#     "sottocutanea": [
#         r"\bsc\b", r"\bs\.?c\.?\b", r"\bs/c\b", r"\bsottocute\b", r"\bin sottocute\b",
#         r"\bsomministrazione s\.?c\.?\b", r"\bsubcutanea\b", r"\bsub cute\b"
#     ],
#     "intramuscolare": [
#         r"\bim\b", r"\bi\.?m\.?\b", r"\bvia intramuscolare\b", r"\bin muscolo\b",
#         r"\bsomministrazione intramuscolare\b", r"\bintramuscolare\b", r"\bper muscolum\b"
#     ],
#     "rettale": [
#         r"\bpr\b", r"\bper rectum\b", r"\bsupposta\b", r"\bclistere\b", r"\bmicroclisma\b",
#         r"\bvia rettale\b", r"\bsomministrazione rettale\b"
#     ],
#     "inalatoria": [
#         r"\bvia aerosolica\b", r"\bnebulizzazione\b", r"\bspray inalato\b", r"\bpuff\b",
#         r"\bvia inalatoria\b", r"\berogatore pressurizzato\b", r"\baerosol terapia\b",
#         r"\binalazione\b", r"\binalazione spray\b", r"\bper nebulizzazione\b"
#     ],
#     "topica": [
#         r"\bvia topica\b", r"\bper via topica\b", r"\bapplicazione cutanea\b", r"\buso esterno\b",
#         r"\bcrema\b", r"\bunguento\b", r"\bad usum dermicum\b", r"\buso dermatologico\b",
#         r"\bpomata cutanea\b", r"\buso locale\b", r"\bapplicazione locale\b"
#     ],
#     "intradermica": [
#         r"\biniezione intradermica\b", r"\bvia intradermica\b"
#     ],
#     "transdermica": [
#         r"\bcerotto transdermico\b", r"\bpatch transdermico\b", r"\bcerotto a rilascio lento\b"
#     ],
#     "sublinguale": [
#         r"\bvia sublinguale\b", r"\bvia sublinguale rapida\b"
#     ],
#     "buccale": [
#         r"\bvia buccale\b", r"\bbuccale orodispersibile\b"
#     ],
#     "nasale": [
#         r"\bper via nasale\b", r"\binstillazione nasale\b", r"\bspray nasale\b"
#     ],
#     "auricolare": [
#         r"\bvia auricolare\b"
#     ],
#     "vescicale": [
#         r"\bvia uretrovescicale\b", r"\binstillazione vescicale\b"
#     ],
#     "intratecale": [
#         r"\bper via intratecale\b", r"\biniezione intratecale\b", r"\bintratecale lombare\b"
#     ],
#     "endouretrale": [
#         r"\bvia endouretrale\b", r"\binstillazione endouretrale\b"
#     ],
#     "congiuntivale": [
#         r"\bper via congiuntivale\b"
#     ],
#     "endocavitaria": [
#         r"\bvia endocavitaria\b"
#     ],
# }

# def extract_modality(text):
#     text = text.lower()
#     for modality, patterns in MODALITY_MAP.items():
#         for pattern in patterns:
#             if re.search(pattern, text):
#                 return modality
#     return "n/a"

import re, html

# --- Regex affidabili per la via di somministrazione ---
MODALITY_MAP = {
    "orale": [
        r"\bper\s+os\b",
        # p.o. / p o / po -> valido SOLO se subito dopo c'è schedula/dose/unità
        r"\b(p\.?\s*o\.?)\b(?=\s*(?:qd|od|die|bid|tid|qid|q\d+h|\d+x/?die|daily|giorn(?:o|i)|settiman(?:a|e)?|mg|mcg|µg|g|cp|caps(?:ule)?|comp(?:resse)?|tbl|tabs?))",
        r"\bper\s+via\s+orale\b",
        r"\borale\b",
        r"\bcp\s+per\s+os\b",
        r"\bassunzione\s+per\s+bocca\b",
        r"\bvia\s+boccale\b",
        r"\b(?:erlotinib|gefitinib|osimertinib|afatinib|poziotinib)\b",
    ],
    "endovenosa": [
        r"\bev\b", r"\be\.?v\.?\b", r"\bi\.?v\.?\b",
        r"\bvia\s+endovenosa\b", r"\bper\s+via\s+endovenosa\b",
        r"\binfusione\s+ev\b", r"\bbolo\s+ev\b", r"\bpush\s+ev\b",
        r"\bflebo\b", r"\bterapia\s+ev\b", r"\bfleboclisi\b",
        r"\binfusione\s+in\s+vena\b", r"\bendovena\b",
        r"\bev\s+continua\b", r"\bev\s+lenta\b", r"\bev\s+in\s+flebo\b",
        r"\bi\.?v\.?\s+push\b",
    ],
    "sottocutanea": [
        r"\bsc\b", r"\bs\.?c\.?\b", r"\bs/c\b", r"\bsottocute\b", r"\bin\s+sottocute\b",
        r"\bsomministrazione\s+s\.?c\.?\b", r"\bsubcutanea\b", r"\bsub\s+cute\b",
    ],
    "intramuscolare": [
        r"\bim\b", r"\bi\.?m\.?\b", r"\bvia\s+intramuscolare\b", r"\bin\s+muscolo\b",
        r"\bsomministrazione\s+intramuscolare\b", r"\bintramuscolare\b", r"\bper\s+muscolum\b",
    ],
    "rettale": [
        r"\bpr\b", r"\bper\s+rectum\b", r"\bsupposta\b", r"\bclistere\b", r"\bmicroclisma\b",
        r"\bvia\s+rettale\b", r"\bsomministrazione\s+rettale\b",
    ],
    "inalatoria": [
        r"\bvia\s+aerosolica\b", r"\bnebulizzazione\b", r"\bspray\s+inalato\b", r"\bpuff\b",
        r"\bvia\s+inalatoria\b", r"\berogatore\s+pressurizzato\b", r"\baerosol\s+terapia\b",
        r"\binalazione\b", r"\binalazione\s+spray\b", r"\bper\s+nebulizzazione\b",
    ],
    "topica": [
        r"\bvia\s+topica\b", r"\bper\s+via\s+topica\b", r"\bapplicazione\s+cutanea\b", r"\buso\s+esterno\b",
        r"\bcrema\b", r"\bunguento\b", r"\bad\s+usum\s+dermicum\b", r"\buso\s+dermatologico\b",
        r"\bpomata\s+cutanea\b", r"\buso\s+locale\b", r"\bapplicazione\s+locale\b",
    ],
    "intradermica": [
        r"\biniezione\s+intradermica\b", r"\bvia\s+intradermica\b",
    ],
    "transdermica": [
        r"\bcerotto\s+transdermico\b", r"\bpatch\s+transdermico\b", r"\bcerotto\s+a\s+rilascio\s+lento\b",
    ],
    "sublinguale": [
        r"\bvia\s+sublinguale\b", r"\bvia\s+sublinguale\s+rapida\b",
    ],
    "buccale": [
        r"\bvia\s+buccale\b", r"\bbuccale\s+orodispersibile\b",
    ],
    "nasale": [
        r"\bper\s+via\s+nasale\b", r"\binstillazione\s+nasale\b", r"\bspray\s+nasale\b",
    ],
    "auricolare": [
        r"\bvia\s+auricolare\b",
    ],
    "vescicale": [
        r"\bvia\s+uretrovescicale\b", r"\binstillazione\s+vescicale\b",
    ],
    "intratecale": [
        r"\bper\s+via\s+intratecale\b", r"\biniezione\s+intratecale\b", r"\bintratecale\s+lombare\b",
    ],
    "endouretrale": [
        r"\bvia\s+endouretrale\b", r"\binstillazione\s+endouretrale\b",
    ],
    "congiuntivale": [
        r"\bper\s+via\s+congiuntivale\b",
    ],
    "endocavitaria": [
        r"\bvia\s+endocavitaria\b",
    ],
}

def _route_norm(text: str) -> str:
    """Normalizza testo e neutralizza 'un po'' per evitare falsi positivi con p.o./po."""
    t = html.unescape(text or "")
    t = t.lower().replace("’", "'").replace("\u00a0", " ")
    # evita che 'un po'' triggeri la via orale
    t = re.sub(r"\bun\s+po['’]?\b", "un poco", t)
    return t

def extract_modality(text: str) -> str:
    t = _route_norm(text)
    for modality, patterns in MODALITY_MAP.items():
        for pattern in patterns:
            if re.search(pattern, t, flags=re.I):
                return modality
    return "n/a"


def extract_collateral_effect(text):
    text = text.lower()

    # Verifica presenza di motivazioni cliniche (sospensione o modifica terapia)
    if not re.search(r"(sospes[oa]|non somministrato|modificat[oa].*terapia)", text):
        return "n/a"

    # Rimuove contenuti indesiderati
    text = re.sub(r"\([^)]*\)", "", text)  # rimuove parentesi e contenuto
    text = re.sub(r"\b(g\d)\b", "", text)  # rimuove G1, G2, ecc.
    text = re.sub(r"\b(egfr|mutazione|carcinosi|progressione|malattia|adenocarcinoma|metastasi|diagnosi|lesione|invasione vascolare|gene|tp53)\b", "", text)

    # Estrae effetti collaterali clinici potenziali
    matches = re.findall(r"(?:per|a causa di|per rischio di|per rischio emorragico da)\s+([a-z\s]+?)(?:$|\.|,| e |;)", text)

    # Pulizia risultati
    cleaned = []
    for m in matches:
        eff = m.strip()
        eff = re.sub(r"\s+", " ", eff)
        if eff and eff not in cleaned:
            cleaned.append(eff)

    return "+".join(cleaned) if cleaned else "n/a"


EXCLUDE_PATTERNS = [
    r'\b(egfr|mutato|metastasi|adenocarcinoma|carcinosi|tumore|neoplasia|alterazioni molecolari|amplificazione met|ebv-dna)\b',
    r'\b(ecog ps|performance status|età avanzata|paziente anziano)\b',
    r'\b(febbre|diarrea|nausea|inappetenza|astenia|dolore diffuso|danno renale da .+|cisplatino|denosumab|creatininemia|ast|alt|elevati)\b'
     r'\betà\b', r'\ball\'?età\b', r'\bdall[ao]\b', r'\bnel\s+\d{4}\b', r'\bnel\s+[12]\d{3}\b',
    r'\bdal\s+\d{4}\b', r'\bda\s+\d{4}\b', r'\banni\b', r'\betà di\b'
]


# =========================
# PERIOD (sostituisce la tua normalize_period "semplice")
# =========================
import re, unicodedata
from typing import List, Dict, Tuple

def normalize_period(text: str) -> str:
    text = text.lower()
    # numero + ciclo/cicli + varianti EN
    match = re.search(r'(\d+)\s*(?:ciclo|cicli|cycle|cycles)\b', text)
    if match:
        num = int(match.group(1))
        return "1 ciclo" if num == 1 else f"{num} cicli"
    return "n/a"


# =========================
# FREQUENCY (sostituisce totalmente extract_frequency)
# =========================
_NUM = r"\d+(?:[.,]\d+)?"

def _norm_num(s: str) -> str:
    s = s.replace(",", ".")
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else str(f)
    except Exception:
        return s

def _norm_spaces(s: str) -> str:
    t = (s or "").lower()
    t = unicodedata.normalize("NFKD", t).replace("\u00a0", " ").replace("\u200b", "")
    t = t.replace("×", "x")
    t = t.replace("dì", "die")  # unifica 'dì'→'die'
    t = re.sub(r"\s+", " ", t)
    return f" {t} "

CP_FORMS = (
    r"(?:cp|cps|cpr|comp(?:ressa|resse)?|compressa|compresse|"
    r"caps(?:ula|ule)?|caps|pastiglia|pastiglie|pillola|pillole|"
    r"tab|tabs|tabl|tablet|tav|comp\.)"
)

def extract_frequency(text: str) -> str:
    if not text:
        return "n/a"

    t = _norm_spaces(text)

    # 1) mg/die
    m = re.search(
        rf"\b({_NUM})\s*mg\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
    )
    if m:
        return f"{_norm_num(m.group(1))} mg/die"

    # 2) cp/die
    m = re.search(
        rf"\b({_NUM})\s*{CP_FORMS}\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
    )
    if m:
        return f"{_norm_num(m.group(1))} cp/die"

    # 3) gtt/die
    m = re.search(
        rf"\b({_NUM})\s*(?:gtt|goccia|gocce)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
    )
    if m:
        return f"{_norm_num(m.group(1))} gtt/die"

    # 4) puff/die
    m = re.search(
        rf"\b({_NUM})\s*(?:puff|spruzzo|spruzzi|inalazione|inalazioni)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
    )
    if m:
        return f"{_norm_num(m.group(1))} puff/die"

    # 5) fiala/die
    m = re.search(
        rf"\b({_NUM})\s*(?:fiala|fiale|flacone|flaconi|flaconcino|flaconcini)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
    )
    if m:
        return f"{_norm_num(m.group(1))} fiala/die"

    # 6) bustina/die
    m = re.search(
        rf"\b({_NUM})\s*(?:bustina|bustine)\s*(?:/|x|\b(?:per|al|alla|a)\b|\s*)\s*(?:die|giorno|24h)\b", t
    )
    if m:
        return f"{_norm_num(m.group(1))} bustina/die"

    # 7) qd / once daily (senza unità specifiche)
    if re.search(r"\bq\.?d\.?\b", t):
        return "qd"
    if re.search(r"\bod\b", t) and re.search(r"\b(die|giorn|daily|assunz|dose|per os|po)\b", t):
        return "qd"
    if re.search(r"\bonce\s*daily\b|\bdaily\b", t):
        return "qd"
    if re.search(r"\buna\s+volta\s+(?:al|a)\s+giorno\b", t):
        return "qd"
    if re.search(r"\bogni\s+giorno\b|\bgiornalier[oa]\b|\bper\s+die\b", t):
        return "qd"
    if re.search(r"\bq\s*24\s*h\b|\bq24h\b|\bogni\s*24\s*ore\b", t):
        return "qd"
    if re.search(rf"\b1\s*/\s*(?:die|giorno|24h)\b", t) and not re.search(r"\bmg\b|cp|cpr|compres|caps|pillol|tab|gtt|puff|fiala|bustina", t):
        return "qd"
    if re.search(r"\s/die\b", t) and not re.search(r"\bmg\b|cp|cpr|compres|caps|pillol|tab|gtt|puff|fiala|bustina", t):
        return "qd"

    # 8) solo unità senza "al giorno"
    # m = re.search(rf"\b({_NUM})\s*{CP_FORMS}\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
    # if m:
    #     return f"{_norm_num(m.group(1))} cp"
    m = re.search(rf"\b({_NUM})\s*{CP_FORMS}\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
    if m:
        # Forza sempre l'output in "cp/die"
        return f"{_norm_num(m.group(1))} cp/die"

    m = re.search(rf"\b({_NUM})\s*(?:gtt|goccia|gocce)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
    if m:
        return f"{_norm_num(m.group(1))} gtt"
    m = re.search(rf"\b({_NUM})\s*(?:puff|spruzzo|spruzzi|inalazione|inalazioni)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
    if m:
        return f"{_norm_num(m.group(1))} puff"
    m = re.search(rf"\b({_NUM})\s*(?:fiala|fiale|flacone|flaconi|flaconcino|flaconcini)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
    if m:
        return f"{_norm_num(m.group(1))} fiala"
    m = re.search(rf"\b({_NUM})\s*(?:bustina|bustine)\b(?!\s*(?:/|x|\b(?:per|al|alla|a)\b)\s*(?:die|giorno|24h)\b)", t)
    if m:
        return f"{_norm_num(m.group(1))} bustina"

    return "n/a"



# =========================
# COMORBIDITÀ (drop-in con rimozione date/età multilingue + sinonimi EN→IT)
# =========================
import re, unicodedata

_NEGATIONS = re.compile(
    r"\b(assenza di|afebbril\w*|nega(?:to|ta)?|non\s+(?:ha|presenta|evidenza|documenta|riporta)|"
    r"senza|negativo\a?\s+per|no\s+(?:segni|sintomi|evidenza)|"
    r"denies|no history of|negative for)\b", re.IGNORECASE
)

# Canonici IT già presenti + alcune new entry frequenti
KNOWN_COMORBIDITIES = [
    "diabete mellito", "iperglicemia", "dmt2", "dispnea", "desaturazione", "edema",
    "ectasia", "aneurisma", "versamento pleurico", "atelettasia", "ispessimento pleurico",
    "focalità epatiche", "lesioni cerebrali", "tep", "embolia", "idronefrosi",
    "linfonodi", "noduli polmonari", "gliosi", "splenomegalia", "cisti corticali",
    "ipertrofia prostatica", "prostatite", "artrosi", "radicolopatia", "discopia",
    "enfisema", "irritazione tracheale", "vasculite", "fibrillazione atriale", "leucemia",
    "leucocitosi", "neutropenia", "piastrinopenia", "bradicardia", "tachicardia",
    "irc", "insufficienza renale cronica", "insufficienza mitralica", "insufficienza aortica",
    "dilatazione atriale", "lesione polmonare", "linfoadenopatie", "versamento ascitico",
    "versamento peritoneale", "pirosi gastrica", "sindrome di gilbert", "morbo di basedow",
    "covid-19", "trombosi", "diverticoli", "granulomatosi", "stenosi",
    "lesioni encefaliche", "deficit visivo", "ipoacusia", "epilessia", "convulsioni",
    "sindrome di parkinson", "discopatia", "ernia discale", "protrusioni", "stenosi foraminale",
    "polipo", "difficoltà di idratazione", "sindrome neurologica", "alterazioni spondilo-artrosiche",
    "basalioma", "frattura", "lateropulsione", "fumo attivo", "tabagismo", "dlco ridotto",
    "compromissione uditiva", "ventricolare", "gliosi", "ampliate cavità ventricolari",
    "ipotrofia cerebellare", "dilatazione spazi subaracnoidei", "tronco encefalico assottigliato",
    "ipertrofia", "congestione emorroidaria", "opacità polmonari", "addensamenti", "febbre",
    # IT canonici per mapping EN:
    "ipertensione", "frattura del femore", "malattia polmonare preesistente", "tabagismo",
]

# Sinonimi/varianti EN (e qualche sigla) → canonico IT
# (match case-insensitive, ripulisce parentesi tipo "(not specified)")
COMORBID_SYNONYMS = [
    (re.compile(r"\bdiabet(?:es|ic)\s+mellitus\b|\btype\s*2\s+diabet(?:es)?\b|\bdm\s*2\b|\bdmt2\b", re.I), "diabete mellito"),
    (re.compile(r"\bhypertension\b|\bhigh\s*blood\s*pressure\b|^htn\b", re.I), "ipertensione"),
    (re.compile(r"\bfracture\s+of\s+(?:the\s+)?femur\b|\bfemoral\s+fracture\b", re.I), "frattura del femore"),
    (re.compile(r"\bpre[-\s]?existing\s+lung\s+disease\b|\bpreexisting\s+lung\s+disease\b|\bchronic\s+lung\s+disease\b", re.I),
     "malattia polmonare preesistente"),
    (re.compile(r"\bsmoking\s+history\b|\b(?:tobacco|nicotine)\s+use\s+history\b|\b(?:ex|former)[-\s]?smoker\b|\bcurrent\s+smoker\b|\bsmoker\b", re.I),
     "tabagismo"),
    # Extra utili comuni:
    (re.compile(r"\bobesity\b|\bobese\b", re.I), "obesità"),
    (re.compile(r"\bhypercholesterolemia\b|\bdyslipid(?:emia|aemia)\b", re.I), "dislipidemia"),
]

def _preclean_dates(text: str) -> str:
    """
    Pulizia aggressiva e multilingue di date/età/tempi:
    - yyyy-mm-dd, dd/mm/yyyy, dd.mm.yy, yyyy/mm/dd, 12/05, '14
    - mesi IT/EN (anche con inizio/fine/metà / early/late/mid)
    - giorni settimana IT/EN e range (lun-ven / mon–fri)
    - settimane/quarter (settimana 34/2023, w34 2023, q1/t1 2022)
    - orari (ore 14:30, 14h, 09:00)
    - intervalli “dal … al …” / “from … to …”, “between … and …”
    - età/durate: “dall’età di 7 aa”, “aged 12”, “from age 12”, “since birth”
    - note cronologiche: “dal 2014”, “since 2014”, “from 2014”
    - parentesi che contengono solo date/anni/orari
    """
    t = (text or "")
    t = unicodedata.normalize("NFKD", t)
    t = t.replace("\u00A0", " ").replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"\s+", " ", t).strip()

    # --- base numeriche ---
    numeric = [
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b",
        r"\b\d{1,2}[/-]\d{1,2}\b",
        r"\b'\d{2}\b",
        r"\b(19|20)\d{2}\b",
    ]

    # --- mesi IT + EN ---
    mesi_it = r"(?:gen(?:naio)?|feb(?:braio)?|mar(?:zo)?|apr(?:ile)?|mag(?:gio)?|giu(?:gno)?|lug(?:lio)?|ago(?:sto)?|set(?:tembre)?|ott(?:obre)?|nov(?:embre)?|dic(?:embre)?)"
    mesi_en = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    months = [
        rf"\b(?:inizio|fine|met[àa]|early|late|mid)?\s*{mesi_it}\.?\s*(?:'\d{{2}}|(?:19|20)\d{{2}})?\b",
        rf"\b(?:early|late|mid)?\s*{mesi_en}\.?\s*(?:'\d{{2}}|(?:19|20)\d{{2}})?\b",
    ]

    # --- giorni settimana IT + EN + range ---
    dow_it = r"(?:lun(?:ed[iì])?|mar(?:ted[iì])?|mer(?:coled[iì])?|gio(?:ved[iì])?|ven(?:erd[iì])?|sab(?:ato)?|dom(?:enica)?)"
    dow_en = r"(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
    weekdays = [
        rf"\b{dow_it}\b", rf"\b{dow_en}\b",
        rf"\b(?:lun|mar|mer|gio|ven|sab|dom)(?:[-–](?:lun|mar|mer|gio|ven|sab|dom))+\b",
        rf"\b(?:mon|tue|wed|thu|fri|sat|sun)(?:[-–](?:mon|tue|wed|thu|fri|sat|sun))+\b",
    ]

    # --- settimane/trim/quarter ---
    wk_q = [
        r"\bsettimana\s*\d{1,2}(?:/\d{2,4})?\b",
        r"\bw\s*\d{1,2}\s*(?:\d{4})?\b",
        r"\b(?:q|t)\s*[1-4]\s*(?:\d{4})?\b",
        r"\b(?:quarter|trimester)\s*[1-4]\s*(?:\d{4})?\b",
    ]

    # --- orari ---
    times = [
        r"\b(?:ore\s*)?\d{1,2}:\d{2}\b",
        r"\b(?:ore\s*)?\d{1,2}\s*h\b",
        r"\bore\s*\d{1,2}\b",
    ]

    # --- range e riferimenti temporali ---
    ranges = [
        r"\b(?:dal|dall[ao]?)\s+[^,;.]{1,30}?\s+(?:al|all[ao]?)\s+[^,;.]{1,30}\b",
        r"\bfrom\s+[^,;.]{1,30}?\s+to\s+[^,;.]{1,30}\b",
        r"\bbetween\s+[^,;.]{1,30}?\s+and\s+[^,;.]{1,30}\b",
        r"\bsince\s+(?:birth|childhood|\d{4})\b",
        r"\bfrom\s+(?:\d{4}|birth|childhood)\b",
        r"\bsince\s+\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
    ]

    # --- età/durate IT+EN ---
    ages = [
        r"\b[>~≈]?\s*\d+\s*(?:anni|aa|a)\b",
        r"\bda\s+\d+\s*(?:anni|aa|a)\b",
        r"\ball['’]?\s?et[aà]\s+di\s+\d+\s+anni\b",
        r"\bdi\s+\d+\s+anni\b",
        r"\bdalla\s+nascita\b",
        r"\baged?\s+\d+\b",
        r"\bfrom\s+age\s+\d+\b",
        r"\b(?:years?\s+old|yo|yrs?\s+old)\b",
        r"\bsince\s+age\s+\d+\b",
    ]

    # --- parentesi con soli riferimenti cronologici (entro 50 char) ---
    paren_time = [
        r"\((?=[^)]{0,50}\b(?:\d{4}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
        r"(?:ore\s*)?\d{1,2}:\d{2}|"
        r"(?:gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))\b)[^)]*\)"
    ]

    # Applica rimozioni
    for rx in (paren_time + ranges + numeric + months + weekdays + wk_q + times + ages):
        t = re.sub(rx, " ", t, flags=re.IGNORECASE)

    # Qualificatori superflui tipici inglesi nelle comorbidità
    t = re.sub(r"\((?:not\s+specified|unspecified|history\s+of)\)", " ", t, flags=re.I)

    # Pulizia finale
    t = re.sub(r"[,;/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_comorbidity(text: str, return_list: bool = False) -> str | list[str]:
    """
    - Rimuove riferimenti cronologici/età in IT/EN.
    - Riconosce comorbidità italiane note (KNOWN_COMORBIDITIES).
    - Aggiunge sinonimi inglesi via COMORBID_SYNONYMS mappando a un etichetta canonica italiana.
    - Evita match negati guardando una finestra a sinistra (60 char).
    """
    if not text:
        return [] if return_list else "n/a"

    t = _preclean_dates(text)

    found: list[str] = []

    # 1) Sinonimi EN → canonico IT
    for rx, canon in COMORBID_SYNONYMS:
        for m in rx.finditer(t):
            left = t[max(0, m.start()-60):m.start()]
            if _NEGATIONS.search(left):
                continue
            if canon not in found:
                found.append(canon)

    # 2) Termini IT noti (match preciso su parola)
    for term in KNOWN_COMORBIDITIES:
        rx = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for m in rx.finditer(t):
            left = t[max(0, m.start()-60):m.start()]
            if _NEGATIONS.search(left):
                continue
            if term not in found:
                found.append(term)

    if return_list:
        return found
    return ", ".join(found) if found else "n/a"

# NORM EXONS 1

# # # =========================
# # # MUTATION + EXON 
# # # =========================

# import re

# # Mutazioni consentite (canoniche, maiuscole)
# _MX_ALLOWED = {
#     "G719A","G719S","G719D","G719C","G719X",
#     "E709K","E709A","L718Q","S768I","T790M","C797S","G724S",
#     "R776H","L858R","L861Q","L861R","T854A","G154V","T1010I",
#     "EXON 19 DEL","EXON 20 INS","L792X","L718X"
# }

# # Fix OCR comuni
# _MX_OCR = [
#     (re.compile(r'\bI858R\b', re.I), 'L858R'),
#     (re.compile(r'\bI861Q\b', re.I), 'L861Q'),
#     (re.compile(r'\bI861R\b', re.I), 'L861R'),
#     (re.compile(r'\bI718Q\b', re.I), 'L718Q'),
#     (re.compile(r'\bT79OM\b', re.I), 'T790M'),
#     (re.compile(r'\bC79?7S\b', re.I), 'C797S'),
#     (re.compile(r'\bG7I9([A-Z])\b', re.I), r'G719\1'),
# ]

# def _mx_norm(s: str) -> str:
#     t = s or ""
#     for rx, rp in _MX_OCR:
#         t = rx.sub(rp, t)
#     # compatta spazi e caratteri strani
#     t = re.sub(r'[\u00A0·•]+', ' ', t)
#     t = re.sub(r'\s+', ' ', t).strip()
#     return t

# # 3→1 lettera (case-insensitive) per forme p.Leu858Arg ecc.
# _AA3_TO1 = {
#     'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E','GLY':'G',
#     'HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F','PRO':'P','SER':'S',
#     'THR':'T','TRP':'W','TYR':'Y','VAL':'V','TER':'X','STOP':'X','XAA':'X'
# }
# def _aa_to1(tok: str):
#     if not tok: return None
#     tok = tok.strip()
#     if len(tok) == 1:
#         ch = tok.upper()
#         return ch if ch in "ACDEFGHIKLMNPQRSTVWYX" else None
#     return _AA3_TO1.get(tok.upper())

# def _dedup(seq):
#     seen, out = set(), []
#     for x in seq:
#         if x not in seen:
#             seen.add(x); out.append(x)
#     return out

# # Negazioni locali (non bloccanti): se compaiono immediatamente a sinistra, scartiamo quel match
# _NEG_NEAR = re.compile(r'(assenza|assenti|negativ\w*|wild[ -]?type|wt|no\s+(?:mutaz|evidenza))', re.I)

# def _neg_left(t: str, start: int, lookback: int = 30) -> bool:
#     left = t[max(0, start - lookback):start]
#     return _NEG_NEAR.search(left) is not None

# # --- MUTAZIONI ---
# def _find_aa_changes(t: str):
#     """Cattura L858R / p.L858R / L 858 R / p.(Leu858Arg) / Leu 858 Arg / ..."""
#     found = []

#     # 1-lettera
#     rx1 = re.compile(
#         r'(?:\bp\.?\s*\(?\s*)?([A-Za-z])\s*[-_.]?\s*(\d{2,4})\s*[-_.]?\s*([A-Za-zX=])\)?',
#         re.I
#     )
#     # 3-lettere
#     rx3 = re.compile(
#         r'(?:\bp\.?\s*\(?\s*)?([A-Za-z]{3})\s*[-_.]?\s*(\d{2,4})\s*[-_.]?\s*([A-Za-z]{3}|X|STOP|TER|=)\)?',
#         re.I
#     )

#     for m in rx1.finditer(t):
#         if _neg_left(t, m.start()): continue
#         a1 = _aa_to1(m.group(1)); pos = m.group(2); a2 = _aa_to1(m.group(3))
#         if a1 and a2:
#             found.append(f"{a1}{pos}{a2}")

#     for m in rx3.finditer(t):
#         if _neg_left(t, m.start()): continue
#         a1 = _aa_to1(m.group(1)); pos = m.group(2); a2 = _aa_to1(m.group(3))
#         if a1 and a2:
#             found.append(f"{a1}{pos}{a2}")

#     return _dedup(found)

# # --- STRUTTURALI (Exon 19 del / Exon 20 ins/dup) ---
# _ROMAN_TO_INT = {'XVIII':18,'XIX':19,'XX':20,'XXI':21}
# def _exon_num(d: str, r: str):
#     if d: 
#         try: return int(d)
#         except: return None
#     if r: 
#         return _ROMAN_TO_INT.get(r.upper())
#     return None

# _EX_LABEL = r'(?:d[eu]ll[aeo]?\s*)?(?:esone|exon|ex\.?|ex)\s*'
# _DEL_WORD = r'(?:del(?:ezione|l[ea])?|deletion|loss(?:\s+of)?|Δ|del\.)'
# _INS_WORD = r'(?:ins(?:erzione)?|insertion|dup(?:licazione)?|dup\.?|ins/dup|dup/ins|delins)'

# def _find_structural(t: str):
#     muts = []

#     # “delezione dell’esone 19”, “esone 19 delezione”, “exon 19 deletion”, “ex19del”, “ex 19 del”
#     rx_del = re.compile(
#         rf'(?:{_EX_LABEL}(?P<d>0*\d{{1,2}})|{_EX_LABEL}(?P<r>xviii|xix|xx|xxi))\s*(?:°|º)?\s*[-: ]*\s*{_DEL_WORD}'
#         rf'|{_DEL_WORD}\s*[-: ]*(?:{_EX_LABEL}(?P<d2>0*\d{{1,2}})|{_EX_LABEL}(?P<r2>xviii|xix|xx|xxi))'
#         rf'|\bex\.?\s*0*(?P<d3>19)\s*del\b',
#         re.I
#     )
#     # “inserzione/dup dell’esone 20”, “exon 20 insertion/dup”, “ex20ins”, “ex 20 dup”
#     rx_ins = re.compile(
#         rf'(?:{_EX_LABEL}(?P<di>0*\d{{1,2}})|{_EX_LABEL}(?P<ri>xviii|xix|xx|xxi))\s*(?:°|º)?\s*[-: ]*\s*{_INS_WORD}'
#         rf'|{_INS_WORD}\s*[-: ]*(?:{_EX_LABEL}(?P<di2>0*\d{{1,2}})|{_EX_LABEL}(?P<ri2>xviii|xix|xx|xxi))'
#         rf'|\bex\.?\s*0*(?P<di3>20)\s*(?:ins|dup)\b',
#         re.I
#     )

#     for m in rx_del.finditer(t):
#         if _neg_left(t, m.start()): continue
#         n = _exon_num(m.group('d') or m.group('d2') or m.group('d3'),
#                       m.group('r') or m.group('r2'))
#         if n == 19:
#             muts.append("Exon 19 del")

#     for m in rx_ins.finditer(t):
#         if _neg_left(t, m.start()): continue
#         n = _exon_num(m.group('di') or m.group('di2') or m.group('di3'),
#                       m.group('ri') or m.group('ri2'))
#         if n == 20:
#             muts.append("Exon 20 ins")

#     return _dedup(muts)

# # --- ESPRESSIONI ESONE (per il campo 'exon') ---
# def _find_exons(t: str):
#     out = []
#     rx1 = re.compile(rf'{_EX_LABEL}(?:(?P<d>0*\d{{1,2}})|(?P<r>xviii|xix|xx|xxi))\s*(?:°|º)?\b', re.I)
#     rx2 = re.compile(rf'\b(?:(?P<d>\d{{1,2}})|(?P<r>xviii|xix|xx|xxi))\s*(?:°|º)?\s*(?:esone|exon|ex\.?|ex)\b', re.I)
#     rx3 = re.compile(r'\bex\.?\s*0*(\d{1,2})\b', re.I)
#     def _emit(n):
#         if n is not None:
#             out.append(f"esone {n}")
#     for m in rx1.finditer(t):
#         if _neg_left(t, m.start()): continue
#         n = _exon_num(m.group('d'), m.group('r')); _emit(n)
#     for m in rx2.finditer(t):
#         if _neg_left(t, m.start()): continue
#         n = _exon_num(m.group('d'), m.group('r')); _emit(n)
#     for m in rx3.finditer(t):
#         if _neg_left(t, m.start()): continue
#         try: _emit(int(m.group(1)))
#         except: pass
#     return _dedup(out)

# def _extract_all(text: str):
#     t = _mx_norm(text)

#     # 1) mutazioni da pattern AA + strutturali
#     aa = _find_aa_changes(t)
#     st = _find_structural(t)
#     muts_all = _dedup(aa + st)

#     # 2) separa consentite vs. altre
#     allowed, other = [], False
#     for tok in muts_all:
#         canon = tok.upper().strip()
#         if canon in _MX_ALLOWED:
#             if canon == "EXON 19 DEL": allowed.append("Exon 19 del")
#             elif canon == "EXON 20 INS": allowed.append("Exon 20 ins")
#             else: allowed.append(canon)  # es. L858R
#         else:
#             other = True

#     allowed = _dedup(allowed)
#     if allowed and other:
#         mutation_str = "+".join(allowed + ["altre mutazioni"])
#     elif allowed:
#         mutation_str = "+".join(allowed)
#     else:
#         mutation_str = "altre mutazioni" if other else "n/a"

#     # 3) esoni (solo se citati esplicitamente)
#     exons = _find_exons(t)
#     exon_str = "+".join(exons) if exons else "n/a"

#     return {"mutation": mutation_str, "exon": exon_str}

# def extract_all(text: str) -> dict:
#     """Compatibile con la tua pipeline. Non lancia eccezioni."""
#     try:
#         return _extract_all(text)
#     except Exception:
#         # fallback ultra-sicuro: non blocca mai il resto della normalizzazione
#         return {"mutation": "n/a", "exon": "n/a"}









# NORM EXONS 2 CON ALTRE MUTAZIONI

import re
import html  # <— per decodificare entità HTML (&egrave;, &rsquo; …)

# Mutazioni consentite (canoniche, maiuscole)
_MX_ALLOWED = {
    "G719A","G719S","G719D","G719C","G719X",
    "E709K","E709A","L718Q","S768I","T790M","C797S","G724S",
    "R776H","L858R","L861Q","L861R","T854A","G154V","T1010I",
    "EXON 19 DEL","EXON 20 INS","L792X","L718X"
}

# Fix OCR comuni
_MX_OCR = [
    (re.compile(r'\bI858R\b', re.I), 'L858R'),
    (re.compile(r'\bI861Q\b', re.I), 'L861Q'),
    (re.compile(r'\bI861R\b', re.I), 'L861R'),
    (re.compile(r'\bI718Q\b', re.I), 'L718Q'),
    (re.compile(r'\bT79OM\b', re.I), 'T790M'),
    (re.compile(r'\bC79?7S\b', re.I), 'C797S'),
    (re.compile(r'\bG7I9([A-Z])\b', re.I), r'G719\1'),
]

def _mx_norm(s: str) -> str:
    # normalizza HTML e trattini tipografici
    t = html.unescape(s or "")
    for rx, rp in _MX_OCR: t = rx.sub(rp, t)
    t = (t.replace("–", "-").replace("—", "-").replace("−", "-")
           .replace("\u00A0", " ").replace("\u200b", " ").replace("’", "'"))
    t = re.sub(r'[\u2022·•]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

# 3→1 lettera (case-insensitive) per forme p.Leu858Arg ecc.
_AA3_TO1 = {
    'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E','GLY':'G',
    'HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F','PRO':'P','SER':'S',
    'THR':'T','TRP':'W','TYR':'Y','VAL':'V','TER':'X','STOP':'X','XAA':'X'
}
def _aa_to1(tok: str):
    if not tok: return None
    tok = tok.strip()
    if len(tok) == 1:
        ch = tok.upper()
        return ch if ch in "ACDEFGHIKLMNPQRSTVWYX" else None
    return _AA3_TO1.get(tok.upper())

def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

# Negazioni locali (non bloccanti)
_NEG_NEAR = re.compile(r'(assenza|assenti|negativ\w*|wild[ -]?type|wt|no\s+(?:mutaz|evidenza))', re.I)
def _neg_left(t: str, start: int, lookback: int = 30) -> bool:
    left = t[max(0, start - lookback):start]
    return _NEG_NEAR.search(left) is not None

# --- MUTAZIONI (AA→AA) ---
def _find_aa_changes(t: str):
    found = []
    rx1 = re.compile(r'(?:\bp\.?\s*\(?\s*)?([A-Za-z])\s*[-_.]?\s*(\d{2,4})\s*[-_.]?\s*([A-Za-zX=])\)?', re.I)
    rx3 = re.compile(r'(?:\bp\.?\s*\(?\s*)?([A-Za-z]{3})\s*[-_.]?\s*(\d{2,4})\s*[-_.]?\s*([A-Za-z]{3}|X|STOP|TER|=)\)?', re.I)
    for m in rx1.finditer(t):
        if _neg_left(t, m.start()): continue
        a1 = _aa_to1(m.group(1)); pos = m.group(2); a2 = _aa_to1(m.group(3))
        if a1 and a2: found.append(f"{a1}{pos}{a2}")
    for m in rx3.finditer(t):
        if _neg_left(t, m.start()): continue
        a1 = _aa_to1(m.group(1)); pos = m.group(2); a2 = _aa_to1(m.group(3))
        if a1 and a2: found.append(f"{a1}{pos}{a2}")
    return _dedup(found)

# --- STRUTTURALI (Exon 19 del / Exon 20 ins-dup) ---
_ROMAN_TO_INT = {'XVIII':18,'XIX':19,'XX':20,'XXI':21}
def _exon_num(d: str, r: str):
    if d:
        try: return int(d)
        except: return None
    if r: return _ROMAN_TO_INT.get(r.upper())
    return None

# PATCH: accetta "del/dell’/dell' esone", anche con apostrofi
_EX_LABEL = r"(?: (?:d[eu]ll[aeo]?|del)\s*['’]?\s*)?(?:esone|exon|ex\.?|ex)\s*"
_EX_LABEL = _EX_LABEL.replace(" ", "")  # rimuove spazi inseriti per leggibilità

_DEL_WORD = r'(?:del(?:ezione|l[ea])?|deletion|loss(?:\s+of)?|Δ|del\.)'
_INS_WORD = r'(?:ins(?:erzione)?|insertion|dup(?:licazione)?|dup\.?|ins/dup|dup/ins|delins)'

def _find_structural(t: str):
    muts = []
    # forme ravvicinate
    rx_del = re.compile(
        rf'(?:{_EX_LABEL}(?P<d>0*\d{{1,2}})|{_EX_LABEL}(?P<r>xviii|xix|xx|xxi))\s*(?:°|º)?\s*[-: ]*\s*{_DEL_WORD}'
        rf'|{_DEL_WORD}\s*[-: ]*(?:{_EX_LABEL}(?P<d2>0*\d{{1,2}})|{_EX_LABEL}(?P<r2>xviii|xix|xx|xxi))'
        rf'|\bex\.?\s*0*(?P<d3>19)\s*del\b', re.I
    )
    rx_ins = re.compile(
        rf'(?:{_EX_LABEL}(?P<di>0*\d{{1,2}})|{_EX_LABEL}(?P<ri>xviii|xix|xx|xxi))\s*(?:°|º)?\s*[-: ]*\s*{_INS_WORD}'
        rf'|{_INS_WORD}\s*[-: ]*(?:{_EX_LABEL}(?P<di2>0*\d{{1,2}})|{_EX_LABEL}(?P<ri2>xviii|xix|xx|xxi))'
        rf'|\bex\.?\s*0*(?P<di3>20)\s*(?:ins|dup)\b', re.I
    )
    for m in rx_del.finditer(t):
        if _neg_left(t, m.start()): continue
        n = _exon_num(m.group('d') or m.group('d2') or m.group('d3'),
                      m.group('r') or m.group('r2'))
        if n == 19: muts.append("exon 19 del")
    for m in rx_ins.finditer(t):
        if _neg_left(t, m.start()): continue
        n = _exon_num(m.group('di') or m.group('di2') or m.group('di3'),
                      m.group('ri') or m.group('ri2'))
        if n == 20: muts.append("exon 20 ins")

    # PATCH: gap ampio tra keyword e "esone N" (fino a 1200 char)
    GAP = r'[\s\S]{0,1200}?'
    if re.search(rf'{_DEL_WORD}{GAP}{_EX_LABEL}(?:0*19|xix)\b', t, re.I): muts.append("exon 19 del")
    if re.search(rf'{_EX_LABEL}(?:0*19|xix)\b{GAP}{_DEL_WORD}', t, re.I): muts.append("exon 19 del")
    if re.search(rf'{_INS_WORD}{GAP}{_EX_LABEL}(?:0*20|xx)\b',  t, re.I): muts.append("exon 20 ins")
    if re.search(rf'{_EX_LABEL}(?:0*20|xx)\b{GAP}{_INS_WORD}',  t, re.I): muts.append("exon 20 ins")

    # PATCH: range E746–A750del / p.(Glu746_Ala750del) → exon 19 del
    if re.search(r'\bE\s*746\s*[_\-]\s*A\s*750\s*(?:del)?\b', t, re.I) \
       or re.search(r'\bp\.\s*\(?\s*(?:GLU|E)\s*746\s*[_\-]\s*(?:ALA|A)\s*750\s*(?:del)?\)?\b', t, re.I):
        muts.append("exon 19 del")

    return _dedup(muts)

# --- ESPRESSIONI ESONE (campo 'exon' se citato esplicitamente) ---
def _find_exons(t: str):
    out = []
    rx1 = re.compile(rf'{_EX_LABEL}(?:(?P<d>0*\d{{1,2}})|(?P<r>xviii|xix|xx|xxi))\s*(?:°|º)?\b', re.I)
    rx2 = re.compile(rf'\b(?:(?P<d>\d{{1,2}})|(?P<r>xviii|xix|xx|xxi))\s*(?:°|º)?\s*(?:esone|exon|ex\.?|ex)\b', re.I)
    rx3 = re.compile(r'\bex\.?\s*0*(\d{1,2})\b', re.I)
    def _emit(n):
        if n is not None: out.append(f"esone {n}")
    for m in rx1.finditer(t):
        if _neg_left(t, m.start()): continue
        n = _exon_num(m.group('d'), m.group('r')); _emit(n)
    for m in rx2.finditer(t):
        if _neg_left(t, m.start()): continue
        n = _exon_num(m.group('d'), m.group('r')); _emit(n)
    for m in rx3.finditer(t):
        if _neg_left(t, m.start()): continue
        try: _emit(int(m.group(1)))
        except: pass
    return _dedup(out)

def _extract_all(text: str):
    t = _mx_norm(text)
    aa = _find_aa_changes(t)
    st = _find_structural(t)
    muts_all = _dedup(aa + st)

    # separa consentite vs altre
    allowed, other = [], False
    for tok in muts_all:
        canon = tok.upper().strip()
        if canon in _MX_ALLOWED:
            if canon == "EXON 19 DEL": allowed.append("exon 19 del")
            elif canon == "EXON 20 INS": allowed.append("exon 20 ins")
            else: allowed.append(canon)
        else:
            other = True

    allowed = _dedup(allowed)
    mutation_str = "+".join(allowed + (["altre mutazioni"] if allowed and other else [])) if allowed else ("altre mutazioni" if other else "n/a")

    exons = _find_exons(t)
    exon_str = "+".join(exons) if exons else "n/a"
    return {"mutation": mutation_str, "exon": exon_str}

def extract_all(text: str) -> dict:
    try:
        return _extract_all(text)
    except Exception:
        return {"mutation": "n/a", "exon": "n/a"}





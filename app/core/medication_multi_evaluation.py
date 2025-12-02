


# # EVALE CON ARROTONDAMENTO
# # EVAL COMPLETA - versione corretta con arrotondamenti e fix DataFrame

# import os
# import re
# import json
# import zipfile
# import ast
# import numpy as np
# import pandas as pd
# from typing import Dict, Tuple, List, Optional, Iterable, Set
# from sklearn.metrics import (
#     classification_report, confusion_matrix
# )

# # ---- Matplotlib (headless) ----
# try:
#     import matplotlib
#     matplotlib.use("Agg")
#     import matplotlib.pyplot as plt
#     import seaborn as sns
# except Exception:
#     plt = None  # se matplotlib non disponibile

# from decimal import Decimal, ROUND_HALF_UP

# # ========================
# # Config / Constants
# # ========================

# BOOL_TRUE = {"true", "1", "yes", "y", "ja"}
# BOOL_FALSE = {"false", "0", "no", "n", "nein"}

# META_EXCLUDE = {
#     "id","report","report_id_short","metadata","matching_report","no_matching_report",
#     "report_redacted","Index","personal_info_list","masked_report",""
# }

# # Lista TKI ristretta (EGFR TKI + poziotinib)
# DEFAULT_TKI_LIST = {
#     "erlotinib", "gefitinib", "afatinib", "osimertinib", "poziotinib",
# }

# # ========================
# # Helpers
# # ========================

# def _read_table(path: str) -> pd.DataFrame:
#     ext = os.path.splitext(path)[-1].lower()
#     if ext == ".csv":
#         return pd.read_csv(path, dtype=str)
#     elif ext in {".xlsx", ".xls"}:
#         return pd.read_excel(path, dtype=str)
#     elif ext in {".txt"}:
#         with open(path, "r", encoding="utf-8") as f:
#             ids = [line.strip() for line in f if line.strip()]
#         return pd.DataFrame({"id": ids})
#     else:
#         raise ValueError(f"Unsupported file type: {ext}")

# def _norm(s: str) -> str:
#     if s is None:
#         return ""
#     s = str(s).strip().lower()
#     s = re.sub(r"\s+", " ", s)
#     return s

# def _short_id_from_llm(llm_id: str) -> str:
#     sid = str(llm_id)
#     sid = sid.split(".pdf")[0]
#     sid = sid.split("$")[0]
#     return sid

# def _is_bool_like_series(values: List[str]) -> bool:
#     vals = {_norm(v) for v in values if v is not None}
#     allowed = BOOL_TRUE | BOOL_FALSE
#     non_empty = {v for v in vals if v != ""}
#     return len(non_empty) > 0 and non_empty.issubset(allowed)

# def _unique_clean(series: pd.Series) -> Set[str]:
#     return set(series.astype(str).fillna("").str.strip().str.lower().tolist())

# def _is_mostly_free_text(values: Set[str]) -> bool:
#     """
#     Heuristica: se (quasi) tutti i valori sono diversi e mediamente lunghi,
#     trattiamo la colonna come testo libero -> niente multiclass.
#     """
#     if not values:
#         return False
#     vals = [v for v in values if v != ""]
#     if not vals:
#         return False
#     uniq_ratio = len(set(vals)) / max(1, len(vals))
#     lengths = sorted(len(v) for v in vals)
#     median_len = lengths[len(lengths)//2] if lengths else 0
#     return (uniq_ratio > 0.8 and median_len > 12)

# # ========================
# # TKI helpers (filtro, senza aggiungere colonne)
# # ========================

# def _is_tki_from_text(text: str, tki_list: Set[str]) -> bool:
#     t = _norm(text)
#     if not t:
#         return False
#     return any(tok in t for tok in tki_list)

# def _filter_tki(df: pd.DataFrame, tki_set: Set[str], medication_col: str = "medication") -> pd.DataFrame:
#     """Ritorna solo le righe in cui 'medication' contiene un TKI (case-insensitive)."""
#     if medication_col not in df.columns:
#         return df.iloc[0:0].copy()
#     return df[df[medication_col].fillna("").map(lambda x: _is_tki_from_text(x, tki_set))].copy()

# # ========================
# # Composite Key helpers (ID + medication)
# # ========================

# def _normmed(df: pd.DataFrame, col: str = "medication") -> pd.Series:
#     """Normalizza la colonna medication, se presente; altrimenti stringa vuota."""
#     if col in df.columns:
#         return df[col].fillna("").astype(str).str.strip().str.lower()
#     return pd.Series([""] * len(df), index=df.index)

# def _attach_composite_keys(df_pred: pd.DataFrame, df_gt: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
#     """
#     Chiave di join per-farmaco:
#       - GT:  id := id + '::' + medication
#       - PRED: report_id_short := report_id_short + '::' + medication
#     """
#     if "report_id_short" not in df_pred.columns:
#         df_pred["report_id_short"] = df_pred["id"].map(_short_id_from_llm)

#     df_gt = df_gt.copy()
#     df_pred = df_pred.copy()

#     df_gt["id"] = df_gt["id"].astype(str) + "::" + _normmed(df_gt)
#     df_pred["report_id_short"] = df_pred["report_id_short"].astype(str) + "::" + _normmed(df_pred)
#     return df_pred, df_gt

# # ========================
# # Core preparation
# # ========================

# def _prepare_frames(pred_path: str, gt_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
#     df_pred = _read_table(pred_path)
#     df_gt = _read_table(gt_path)

#     df_pred = df_pred.rename(columns=lambda x: x.replace(" ", "_"))
#     df_gt = df_gt.rename(columns=lambda x: x.replace(" ", "_"))

#     if "id" not in df_pred.columns:
#         raise ValueError("Predictions file is missing 'id' column.")
#     if "id" not in df_gt.columns:
#         raise ValueError("Ground truth file is missing 'id' column.")

#     if "report_id_short" not in df_pred.columns:
#         df_pred["report_id_short"] = df_pred["id"].map(_short_id_from_llm)

#     # chiave composita per conservare le righe multiple per farmaco
#     df_pred, df_gt = _attach_composite_keys(df_pred, df_gt)
#     return df_pred, df_gt

# def _detect_label_types(
#     df_pred: pd.DataFrame,
#     df_gt: pd.DataFrame,
#     extra_boolean_labels: Optional[List[str]] = None,
#     *,
#     max_multiclass: int = 15,
#     min_support: int = 0,
# ) -> Dict[str, str]:
#     """
#     Rileva automaticamente il tipo di ciascuna colonna condivisa tra pred e GT:
#       - 'boolean'
#       - 'multiclass'
#       - 'stringmatch'
#       - 'ignore' se il supporto non-buoto è troppo basso
#     """
#     extra_boolean_labels = set(extra_boolean_labels or [])
#     label_types: Dict[str, str] = {}

#     candidates = [c for c in df_pred.columns if c not in META_EXCLUDE and c in df_gt.columns]

#     for col in candidates:
#         gt_col = df_gt[col].astype(str)
#         pr_col = df_pred[col].astype(str)

#         non_empty = (gt_col.str.strip() != "") | (pr_col.str.strip() != "")
#         support = int(non_empty.sum())
#         if support < min_support:
#             label_types[col] = "ignore"
#             continue

#         if col in extra_boolean_labels:
#             label_types[col] = "boolean"
#             continue

#         gt_vals = list(gt_col.fillna(""))
#         if _is_bool_like_series(gt_vals):
#             label_types[col] = "boolean"
#             continue

#         union_vals = _unique_clean(gt_col) | _unique_clean(pr_col)
#         union_vals.discard("")
#         if 1 <= len(union_vals) <= max_multiclass and not _is_mostly_free_text(union_vals):
#             label_types[col] = "multiclass"
#             continue

#         label_types[col] = "stringmatch"

#     return label_types

# def _r2(x) -> float:
#     """
#     Arrotonda a 2 decimali con ROUND_HALF_UP:
#     0.667 -> 0.67, 0.665 -> 0.67, 0.664 -> 0.66.
#     Ritorna float per comodità di serializzazione.
#     """
#     try:
#         return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
#     except Exception:
#         return 0.0

# # ========================
# # Per-feature computation
# # ========================

# def _compute_per_feature(
#     df_pred: pd.DataFrame,
#     df_gt: pd.DataFrame,
#     label_types: Dict[str, str],
#     out_dir: str
# ) -> Dict:
#     os.makedirs(out_dir, exist_ok=True)
#     per_feature = {}

#     # build mappa GT per lookup O(1)
#     gt_map = df_gt.set_index("id")

#     for feat, ftype in label_types.items():
#         if feat not in df_pred.columns or feat not in df_gt.columns:
#             continue

#         # allinea sugli ID (id::medication)
#         y_true, y_pred = [], []
#         for row in df_pred.itertuples():
#             rid_short = row.report_id_short
#             try:
#                 gt_val = str(gt_map.at[rid_short, feat]).strip().lower()
#             except KeyError:
#                 continue
#             pr_val = str(getattr(row, feat, "")).strip().lower()
#             y_true.append(gt_val)
#             y_pred.append(pr_val)

#         if not y_true:
#             continue

#         # etichette globali stabili (senza stringa vuota)
#         col_gt_all = (
#             df_gt[feat].astype(str).fillna("").str.strip().str.lower()
#             if feat in df_gt.columns else pd.Series([], dtype=str)
#         )
#         col_pr_all = (
#             df_pred[feat].astype(str).fillna("").str.strip().str.lower()
#             if feat in df_pred.columns else pd.Series([], dtype=str)
#         )

#         labels_all = sorted(set(col_gt_all.tolist()) | set(col_pr_all.tolist()))
#         labels_all = [x for x in labels_all if x != ""]
#         if not labels_all:
#             labels_all = sorted(set(y_true) | set(y_pred))

#         report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
#         cm_np = confusion_matrix(y_true, y_pred, labels=labels_all)
#         cm_mat = cm_np.tolist()

#         # plot CM
#         if plt is not None and len(labels_all) > 0:
#             plt.figure(figsize=(6, 5))
#             sns.heatmap(
#                 cm_np, annot=True, fmt="d", cmap="Blues",
#                 xticklabels=labels_all, yticklabels=labels_all
#             )
#             plt.xlabel("Predicted")
#             plt.ylabel("Ground Truth")
#             plt.title(f"Confusion Matrix - {feat}")
#             plt.tight_layout()
#             plt.savefig(os.path.join(out_dir, f"cm_{feat}.png"))
#             plt.close()

#         # salva JSON della CM + report
#         with open(os.path.join(out_dir, f"cm_{feat}.json"), "w", encoding="utf-8") as f:
#             json.dump({
#                 "labels": labels_all,
#                 "matrix": cm_mat,
#                 "report": report
#             }, f, ensure_ascii=False, indent=2)

#         per_feature[feat] = {
#             "type": ftype,
#             "macro_avg": report.get("macro avg", {}),
#             "weighted_avg": report.get("weighted avg", {}),
#             "per_class": report,
#             "confusion_matrix": {"labels": labels_all, "matrix": cm_mat},
#             "support": len(y_true)
#         }

#     return per_feature

# # ========================
# # Overall (macro + weighted tra feature)
# # ========================

# def _overall_from_per_feature(per_feature: Dict[str, Dict]) -> Dict[str, float]:
#     # macro (esistenti)
#     macro = {"accuracy": [], "precision": [], "recall": [], "f1": []}
#     # weighted (per-feature)
#     weighted = {"precision": [], "recall": [], "f1": []}

#     # accuracy pesata per supporto (feature-weighted)
#     acc_weighted_num = 0.0
#     support_total = 0

#     # micro: somma su tutte le feature (concatenazione dei casi)
#     micro_tp_total = 0  # somma delle diagonali
#     micro_total = 0     # somma di tutte le celle

#     for _, m in per_feature.items():
#         # macro (media semplice tra feature)
#         if "macro_avg" in m:
#             macro["precision"].append(m["macro_avg"].get("precision", 0))
#             macro["recall"].append(m["macro_avg"].get("recall", 0))
#             macro["f1"].append(m["macro_avg"].get("f1-score", 0))
#         macro["accuracy"].append(m.get("per_class", {}).get("accuracy", 0))

#         # weighted (media semplice delle weighted per-feature)
#         if "weighted_avg" in m:
#             weighted["precision"].append(m["weighted_avg"].get("precision", 0))
#             weighted["recall"].append(m["weighted_avg"].get("recall", 0))
#             weighted["f1"].append(m["weighted_avg"].get("f1-score", 0))

#         # accuracy pesata per supporto (feature-level)
#         s = int(m.get("support", 0))
#         a = float(m.get("per_class", {}).get("accuracy", 0))
#         acc_weighted_num += a * s
#         support_total += s

#         # micro: usa la confusion matrix della feature
#         cm = m.get("confusion_matrix", {})
#         mat = np.array(cm.get("matrix", []), dtype=int)
#         if mat.size > 0:
#             micro_tp_total += int(np.trace(mat))
#             micro_total += int(np.sum(mat))

#     accuracy_weighted = (acc_weighted_num / support_total) if support_total > 0 else 0.0

#     # micro (multiclasse single-label): precision == recall == f1 == accuracy == TP/Total
#     micro_score = (micro_tp_total / micro_total) if micro_total > 0 else 0.0

#     return {
#         # macro complessive (media semplice)
#         "accuracy": float(np.mean(macro["accuracy"])) if macro["accuracy"] else 0.0,
#         "precision": float(np.mean(macro["precision"])) if macro["precision"] else 0.0,
#         "recall":    float(np.mean(macro["recall"])) if macro["recall"] else 0.0,
#         "f1":        float(np.mean(macro["f1"])) if macro["f1"] else 0.0,

#         # weighted complessive (media semplice delle weighted per-feature)
#         "precision_weighted": float(np.mean(weighted["precision"])) if weighted["precision"] else 0.0,
#         "recall_weighted":    float(np.mean(weighted["recall"])) if weighted["recall"] else 0.0,
#         "f1_weighted":        float(np.mean(weighted["f1"])) if weighted["f1"] else 0.0,

#         # accuracy pesata per supporto (usata nella riga "weighted avg")
#         "accuracy_weighted":  float(accuracy_weighted),

#         # micro su tutte le feature concatenate
#         "accuracy_micro": float(micro_score),
#         "precision_micro": float(micro_score),
#         "recall_micro": float(micro_score),
#         "f1_micro": float(micro_score),

#         # supporti utili (per la tabella)
#         "support_sum": int(support_total),
#     }

# # ========================
# # Exact-Match per record (tutta la riga)
# # ========================
# def _compute_exact_match(df_pred: pd.DataFrame,
#                          df_gt: pd.DataFrame,
#                          label_types: Dict[str, str],
#                          out_dir: str):
#     """
#     Exact-match per record confrontando TUTTE le feature condivise tra pred e GT,
#     escludendo solo i meta campi in META_EXCLUDE. NON usa label_types per
#     decidere cosa includere.
#     Scrive:
#       - exact_match.csv  (id, exact_match, n_mismatches, mismatched_fields)
#       - exact_match.json (accuracy, n_records, features_used, by_id[...])
#     """
#     def _cell_norm(v):
#         s = str(v)
#         if s.strip().startswith("[") and s.strip().endswith("]"):
#             try:
#                 lst = ast.literal_eval(s)
#                 for x in lst:
#                     xs = str(x).strip()
#                     if xs:
#                         s = xs
#                         break
#             except Exception:
#                 pass
#         s = s.strip().lower()
#         s = re.sub(r"\s+", " ", s)
#         return s

#     os.makedirs(out_dir, exist_ok=True)

#     pred = df_pred.groupby("report_id_short", as_index=False).first()
#     gt   = df_gt.groupby("id", as_index=False).first()

#     shared_cols = sorted([
#         c for c in pred.columns
#         if c in gt.columns and c not in META_EXCLUDE
#     ])

#     ids = sorted(set(pred["report_id_short"].astype(str)) & set(gt["id"].astype(str)))

#     rows = []
#     em_hits = 0

#     for rid in ids:
#         pr = pred[pred["report_id_short"] == rid].iloc[0]
#         gr = gt[gt["id"] == rid].iloc[0]

#         mismatches = 0
#         bad_fields = []

#         for f in shared_cols:
#             y_true = _cell_norm(gr.get(f, ""))
#             y_pred = _cell_norm(pr.get(f, ""))
#             if y_true != y_pred:
#                 mismatches += 1
#                 bad_fields.append(f"{f}: GT='{y_true}' | PRED='{y_pred}'")

#         em = 1 if mismatches == 0 else 0
#         em_hits += em
#         rows.append({
#             "id": rid,
#             "exact_match": em,
#             "n_mismatches": mismatches,
#             "mismatched_fields": "; ".join(bad_fields)
#         })

#     em_csv = os.path.join(out_dir, "exact_match.csv")
#     pd.DataFrame(rows, columns=["id", "exact_match", "n_mismatches", "mismatched_fields"]).to_csv(em_csv, index=False)

#     n = len(ids)
#     em_json = os.path.join(out_dir, "exact_match.json")
#     with open(em_json, "w", encoding="utf-8") as f:
#         json.dump({
#             "accuracy": (float(em_hits) / n if n else 0.0),
#             "n_records": n,
#             "features_used": shared_cols,
#             "by_id": rows
#         }, f, ensure_ascii=False, indent=2)

# # ========================
# # Outputs
# # ========================
# def _write_outputs(per_feature: Dict[str, Dict], overall: Dict[str, float], out_dir: str, diagnostics: Optional[Dict] = None):
#     os.makedirs(out_dir, exist_ok=True)

#     # ---- med_metrics.csv (SOLO per-feature) ----
#     columns = ["feature", "accuracy", "precision", "recall", "f1-score", "support"]
#     rows = []
#     for feat, m in per_feature.items():
#         sup = int(m.get("support", 0))
#         rows.append({
#             "feature": feat,
#             "accuracy": _r2(m.get("per_class", {}).get("accuracy", 0)),
#             "precision": _r2(m["macro_avg"].get("precision", 0)),
#             "recall":    _r2(m["macro_avg"].get("recall", 0)),
#             "f1-score":  _r2(m["macro_avg"].get("f1-score", 0)),
#             "support":   str(sup),
#         })

#     pd.DataFrame(rows, columns=columns).to_csv(os.path.join(out_dir, "med_metrics.csv"), index=False)

#     # ---- med_metrics_weighted.csv (weighted per-feature) ----
#     rows_w = []
#     for feat, m in per_feature.items():
#         rows_w.append({
#             "feature": feat,
#             "precision_weighted": _r2(m["weighted_avg"].get("precision", 0)),
#             "recall_weighted":    _r2(m["weighted_avg"].get("recall", 0)),
#             "f1_weighted":        _r2(m["weighted_avg"].get("f1-score", 0)),
#             "support":            int(m["support"]) if "support" in m else 0,
#         })
#     pd.DataFrame(
#         rows_w,
#         columns=["feature","precision_weighted","recall_weighted","f1_weighted","support"]
#     ).to_csv(os.path.join(out_dir, "med_metrics_weighted.csv"), index=False)

#     # ---- global_metrics.json (+ weighted & micro overall) ----
#     payload = {
#         "accuracy":           _r2(overall.get("accuracy", 0)),
#         "precision":          _r2(overall.get("precision", 0)),
#         "recall":             _r2(overall.get("recall", 0)),
#         "f1_score":           _r2(overall.get("f1", 0)),

#         "precision_weighted": _r2(overall.get("precision_weighted, 0".replace(",","")) if isinstance(overall.get("precision_weighted"), str) else overall.get("precision_weighted", 0)),
#         "recall_weighted":    _r2(overall.get("recall_weighted, 0".replace(",","")) if isinstance(overall.get("recall_weighted"), str) else overall.get("recall_weighted", 0)),
#         "f1_weighted":        _r2(overall.get("f1_weighted, 0".replace(",","")) if isinstance(overall.get("f1_weighted"), str) else overall.get("f1_weighted", 0)),
#         "accuracy_weighted":  _r2(overall.get("accuracy_weighted, 0".replace(",","")) if isinstance(overall.get("accuracy_weighted"), str) else overall.get("accuracy_weighted", 0)),

#         "precision_micro":    _r2(overall.get("precision_micro", 0)),
#         "recall_micro":       _r2(overall.get("recall_micro", 0)),
#         "f1_micro":           _r2(overall.get("f1_micro", 0)),
#         "accuracy_micro":     _r2(overall.get("accuracy_micro", 0)),
#     }
#     if diagnostics:
#         payload["diagnostics"] = diagnostics

#     with open(os.path.join(out_dir, "global_metrics.json"), "w", encoding="utf-8") as f:
#         json.dump(payload, f, ensure_ascii=False, indent=2)

#     # ---- Grafici ----
#     try:
#         df_plot = pd.read_csv(os.path.join(out_dir, "med_metrics.csv"), dtype=str, keep_default_na=False)
#         # F1
#         if not df_plot.empty and {"feature","f1-score"} <= set(df_plot.columns) and plt is not None:
#             plt.figure(figsize=(8,4))
#             plt.bar(df_plot["feature"].astype(str), pd.to_numeric(df_plot["f1-score"], errors="coerce").fillna(0.0))
#             plt.xticks(rotation=45, ha="right")
#             plt.ylabel("F1 (macro)")
#             plt.title("F1 per feature")
#             plt.tight_layout()
#             plt.savefig(os.path.join(out_dir, "med_f1.png"))
#             plt.close()
#         # Accuracy
#         if not df_plot.empty and "accuracy" in df_plot.columns and plt is not None:
#             plt.figure(figsize=(8,4))
#             plt.bar(df_plot["feature"].astype(str), pd.to_numeric(df_plot["accuracy"], errors="coerce").fillna(0.0))
#             plt.xticks(rotation=45, ha="right")
#             plt.ylabel("Accuracy (macro)")
#             plt.title("Accuracy per feature")
#             plt.tight_layout()
#             plt.savefig(os.path.join(out_dir, "med_accuracy.png"))
#             plt.close()
#         # Precision
#         if not df_plot.empty and "precision" in df_plot.columns and plt is not None:
#             plt.figure(figsize=(8,4))
#             plt.bar(df_plot["feature"].astype(str), pd.to_numeric(df_plot["precision"], errors="coerce").fillna(0.0))
#             plt.xticks(rotation=45, ha="right")
#             plt.ylabel("Precision (macro)")
#             plt.title("Precision per feature")
#             plt.tight_layout()
#             plt.savefig(os.path.join(out_dir, "med_precision.png"))
#             plt.close()
#         # Recall
#         if not df_plot.empty and "recall" in df_plot.columns and plt is not None:
#             plt.figure(figsize=(8,4))
#             plt.bar(df_plot["feature"].astype(str), pd.to_numeric(df_plot["recall"], errors="coerce").fillna(0.0))
#             plt.xticks(rotation=45, ha="right")
#             plt.ylabel("Recall (macro)")
#             plt.title("Recall per feature")
#             plt.tight_layout()
#             plt.savefig(os.path.join(out_dir, "med_recall.png"))
#             plt.close()
#     except Exception as e:
#         print("WARN: grafici non creati:", e)

#     # ---- ZIP ----
#     try:
#         zip_path = os.path.join(out_dir, "eval_results.zip")
#         with zipfile.ZipFile(zip_path, "w") as zf:
#             for fn in ("med_metrics.csv", "med_metrics_weighted.csv",
#                        "global_metrics.json", "med_f1.png",
#                        "exact_match.csv", "exact_match.json"):
#                 p = os.path.join(out_dir, fn)
#                 if os.path.exists(p):
#                     zf.write(p, arcname=fn)
#             for fn in os.listdir(out_dir):
#                 if fn.startswith("cm_") and (fn.endswith(".png") or fn.endswith(".json")):
#                     zf.write(os.path.join(out_dir, fn), arcname=fn)
#     except Exception as e:
#         print("WARN: ZIP non creato:", e)

# # ========================
# # Public API — valutatore per feature con filtro TKI
# # ========================

# def run_medication_evaluation(
#     pred_path: str,
#     gt_path: str,
#     static_dir: str = None,
#     *,
#     tki_only: bool = True,
#     custom_tki_list: Optional[Iterable[str]] = None,
#     id_filter: Optional[Iterable[str] or str] = None,
# ) -> Dict:
#     if static_dir is None:
#         base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#         static_dir = os.path.join(base, "static")
#         os.makedirs(static_dir, exist_ok=True)

#     df_pred, df_gt = _prepare_frames(pred_path, gt_path)

#     # TKI filter PRIMA di tutto (per-riga)
#     tki_set = set(_norm(x) for x in (custom_tki_list or DEFAULT_TKI_LIST))
#     if tki_only:
#         df_pred = _filter_tki(df_pred, tki_set, medication_col="medication")
#         df_gt   = _filter_tki(df_gt,   tki_set, medication_col="medication")

#     # one-row per chiave composta (id::medication)
#     df_pred = df_pred.groupby("report_id_short", as_index=False).first()
#     df_gt   = df_gt.groupby("id", as_index=False).first()

#     # Riduci ai soli ID comuni (e opzionale filtro esplicito)
#     ids_pred = set(df_pred["report_id_short"].astype(str))
#     ids_gt   = set(df_gt["id"].astype(str))
#     ids_comuni = ids_pred & ids_gt

#     if id_filter is not None:
#         if isinstance(id_filter, str):
#             id_filter = [id_filter]
#         id_filter = {str(x) for x in id_filter}
#         ids_comuni = ids_comuni & id_filter

#     df_pred = df_pred[df_pred["report_id_short"].astype(str).isin(ids_comuni)].copy()
#     df_gt   = df_gt[df_gt["id"].astype(str).isin(ids_comuni)].copy()

#     # auto-detect dei tipi
#     label_types = _detect_label_types(df_pred, df_gt)

#     per_feature = _compute_per_feature(df_pred, df_gt, label_types, out_dir=static_dir)
#     overall = _overall_from_per_feature(per_feature)

#     diagnostics = {
#         "ids_eval_count": len(ids_comuni),
#         "tki_only": bool(tki_only),
#         "mode": "feature"
#     }

#     # Exact-Match su tutta la riga
#     _compute_exact_match(df_pred, df_gt, label_types, out_dir=static_dir)

#     _write_outputs(per_feature, overall, static_dir, diagnostics=diagnostics)

#     return {
#         "per_feature": per_feature,
#         "overall": overall,
#         "out_dir": static_dir,
#         "diagnostics": diagnostics
#     }





# evale 2



# EVALE CON ARROTONDAMENTO
# EVAL COMPLETA - versione corretta con arrotondamenti e fix DataFrame

import os
import re
import json
import zipfile
import ast
import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional, Iterable, Set
from sklearn.metrics import (
    classification_report, confusion_matrix
)

# ---- Matplotlib (headless) ----
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
except Exception:
    plt = None  # se matplotlib non disponibile

from decimal import Decimal, ROUND_HALF_UP

# ========================
# Config / Constants
# ========================

BOOL_TRUE = {"true", "1", "yes", "y", "ja"}
BOOL_FALSE = {"false", "0", "no", "n", "nein"}

META_EXCLUDE = {
    "id","report","report_id_short","metadata","matching_report","no_matching_report",
    "report_redacted","Index","personal_info_list","masked_report",""
}

# Lista TKI ristretta (EGFR TKI + poziotinib)
DEFAULT_TKI_LIST = {
    "erlotinib", "gefitinib", "afatinib", "osimertinib", "poziotinib",
}

# ========================
# Helpers
# ========================

def _read_table(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".csv":
        return pd.read_csv(path, dtype=str)
    elif ext in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str)
    elif ext in {".txt"}:
        with open(path, "r", encoding="utf-8") as f:
            ids = [line.strip() for line in f if line.strip()]
        return pd.DataFrame({"id": ids})
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _short_id_from_llm(llm_id: str) -> str:
    sid = str(llm_id)
    sid = sid.split(".pdf")[0]
    sid = sid.split("$")[0]
    return sid

def _is_bool_like_series(values: List[str]) -> bool:
    vals = {_norm(v) for v in values if v is not None}
    allowed = BOOL_TRUE | BOOL_FALSE
    non_empty = {v for v in vals if v != ""}
    return len(non_empty) > 0 and non_empty.issubset(allowed)

def _unique_clean(series: pd.Series) -> Set[str]:
    return set(series.astype(str).fillna("").str.strip().str.lower().tolist())

def _is_mostly_free_text(values: Set[str]) -> bool:
    """
    Heuristica: se (quasi) tutti i valori sono diversi e mediamente lunghi,
    trattiamo la colonna come testo libero -> niente multiclass.
    """
    if not values:
        return False
    vals = [v for v in values if v != ""]
    if not vals:
        return False
    uniq_ratio = len(set(vals)) / max(1, len(vals))
    lengths = sorted(len(v) for v in vals)
    median_len = lengths[len(lengths)//2] if lengths else 0
    return (uniq_ratio > 0.8 and median_len > 12)

# ========================
# TKI helpers (filtro, senza aggiungere colonne)
# ========================

def _is_tki_from_text(text: str, tki_list: Set[str]) -> bool:
    t = _norm(text)
    if not t:
        return False
    return any(tok in t for tok in tki_list)

def _filter_tki(df: pd.DataFrame, tki_set: Set[str], medication_col: str = "medication") -> pd.DataFrame:
    """Ritorna solo le righe in cui 'medication' contiene un TKI (case-insensitive)."""
    if medication_col not in df.columns:
        return df.iloc[0:0].copy()
    return df[df[medication_col].fillna("").map(lambda x: _is_tki_from_text(x, tki_set))].copy()

# ========================
# Composite Key helpers (ID + medication)
# ========================

def _normmed(df: pd.DataFrame, col: str = "medication") -> pd.Series:
    """Normalizza la colonna medication, se presente; altrimenti stringa vuota."""
    if col in df.columns:
        return df[col].fillna("").astype(str).str.strip().str.lower()
    return pd.Series([""] * len(df), index=df.index)

def _attach_composite_keys(df_preds: list, df_gt: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Chiave di join per-farmaco:
      - GT:  id := id + '::' + medication
      - PRED: report_id_short := report_id_short + '::' + medication
    """
    for df_pred in df_preds:
        if "report_id_short" not in df_pred.columns:
            df_pred["report_id_short"] = df_pred["id"].map(_short_id_from_llm)

    df_gt = df_gt.copy()
    df_preds = [df_pred.copy() for df_pred in df_preds]

    df_gt["id"] = df_gt["id"].astype(str) + "::" + _normmed(df_gt)
    for df_pred in df_preds:
        df_pred["report_id_short"] = df_pred["report_id_short"].astype(str) + "::" + _normmed(df_pred)
    return df_preds, df_gt

# ========================
# Core preparation
# ========================

def _prepare_frames(pred_paths: str, gt_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df_preds = [_read_table(pred_path) for pred_path in pred_paths]
    df_gt = _read_table(gt_path)

    df_preds = [df_pred.rename(columns=lambda x: x.replace(" ", "_")) for df_pred in df_preds]
    df_gt = df_gt.rename(columns=lambda x: x.replace(" ", "_"))

    for df_pred in df_preds:
        if "id" not in df_pred.columns:
            raise ValueError("Predictions file is missing 'id' column.")
    if "id" not in df_gt.columns:
        raise ValueError("Ground truth file is missing 'id' column.")

    for df_pred in df_preds:
        if "report_id_short" not in df_pred.columns:
            df_pred["report_id_short"] = df_pred["id"].map(_short_id_from_llm)

    # chiave composita per conservare le righe multiple per farmaco
    df_preds, df_gt = _attach_composite_keys(df_preds, df_gt)
    return df_preds, df_gt

def _detect_label_types(
    df_preds: list,
    df_gt: pd.DataFrame,
    extra_boolean_labels: Optional[List[str]] = None,
    *,
    max_multiclass: int = 15,
    min_support: int = 0,
) -> Dict[str, str]:
    """
    Rileva automaticamente il tipo di ciascuna colonna condivisa tra pred e GT:
      - 'boolean'
      - 'multiclass'
      - 'stringmatch'
      - 'ignore' se il supporto non-buoto è troppo basso
    """
    extra_boolean_labels = set(extra_boolean_labels or [])
    label_types: Dict[str, str] = {}

    candidates = list(set([c for df_pred in df_preds for c in df_pred.columns if c not in META_EXCLUDE and c in df_gt.columns]))

    for col in candidates:
        gt_col = df_gt[col].astype(str)
        for df_pred in df_preds:
            if col in df_pred:
                pr_col = df_pred[col].astype(str)
                break

        non_empty = (gt_col.str.strip() != "") | (pr_col.str.strip() != "")
        support = int(non_empty.sum())
        if support < min_support:
            label_types[col] = "ignore"
            continue

        if col in extra_boolean_labels:
            label_types[col] = "boolean"
            continue

        gt_vals = list(gt_col.fillna(""))
        if _is_bool_like_series(gt_vals):
            label_types[col] = "boolean"
            continue

        union_vals = _unique_clean(gt_col) | _unique_clean(pr_col)
        union_vals.discard("")
        if 1 <= len(union_vals) <= max_multiclass and not _is_mostly_free_text(union_vals):
            label_types[col] = "multiclass"
            continue

        label_types[col] = "stringmatch"

    return label_types

def _r2(x) -> float:
    """
    Arrotonda a 2 decimali con ROUND_HALF_UP:
    0.667 -> 0.67, 0.665 -> 0.67, 0.664 -> 0.66.
    Ritorna float per comodità di serializzazione.
    """
    try:
        return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0

# ========================
# Per-feature computation
# ========================

def _compute_per_feature(
    df_pred: pd.DataFrame,
    df_gt: pd.DataFrame,
    label_types: Dict[str, str],
    out_dir: str
) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    per_feature = {}

    # build mappa GT per lookup O(1)
    gt_map = df_gt.set_index("id")

    for feat, ftype in label_types.items():
        if feat not in df_pred.columns or feat not in df_gt.columns:
            continue

        # allinea sugli ID (id::medication)
        y_true, y_pred = [], []
        for row in df_pred.itertuples():
            rid_short = row.report_id_short
            try:
                gt_val = str(gt_map.at[rid_short, feat]).strip().lower()
            except KeyError:
                continue
            pr_val = str(getattr(row, feat, "")).strip().lower()
            y_true.append(gt_val)
            y_pred.append(pr_val)

        if not y_true:
            continue

        # etichette globali stabili (senza stringa vuota)
        col_gt_all = (
            df_gt[feat].astype(str).fillna("").str.strip().str.lower()
            if feat in df_gt.columns else pd.Series([], dtype=str)
        )
        col_pr_all = (
            df_pred[feat].astype(str).fillna("").str.strip().str.lower()
            if feat in df_pred.columns else pd.Series([], dtype=str)
        )

        labels_all = sorted(set(col_gt_all.tolist()) | set(col_pr_all.tolist()))
        labels_all = [x for x in labels_all if x != ""]
        if not labels_all:
            labels_all = sorted(set(y_true) | set(y_pred))

        report = classification_report(
    y_true, y_pred,
    labels=labels_all,            # ← stessa base etichette della CM
    target_names=labels_all,      # ← nomi coerenti nel report
    output_dict=True,
    zero_division=0
)

        cm_np = confusion_matrix(y_true, y_pred, labels=labels_all)
        cm_mat = cm_np.tolist()

        # plot CM
        if plt is not None and len(labels_all) > 0:
            plt.figure(figsize=(6, 5))
            sns.heatmap(
                cm_np, annot=True, fmt="d", cmap="Blues",
                xticklabels=labels_all, yticklabels=labels_all
            )
            plt.xlabel("Predicted")
            plt.ylabel("Ground Truth")
            plt.title(f"Confusion Matrix - {feat}")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, f"cm_{feat}.png"))
            plt.close()

        # salva JSON della CM + report
        with open(os.path.join(out_dir, f"cm_{feat}.json"), "w", encoding="utf-8") as f:
            json.dump({
                "labels": labels_all,
                "matrix": cm_mat,
                "report": report
            }, f, ensure_ascii=False, indent=2)

        per_feature[feat] = {
            "type": ftype,
            "macro_avg": report.get("macro avg", {}),
            "weighted_avg": report.get("weighted avg", {}),
            "per_class": report,
            "confusion_matrix": {"labels": labels_all, "matrix": cm_mat},
            "support": len(y_true)
        }

    return per_feature

# # ========================
# # Overall (macro + weighted tra feature) ACCURACY WEIGHTED MACRO E MICRO
# # ========================

 
# def _overall_from_per_feature(per_feature: Dict[str, Dict]) -> Dict[str, float]:
#     """
#     OVERALL = media tra feature (pari peso a ciascun task).
#     Per ogni feature:
#       - ricostruisce la CM e calcola metriche 'alla sklearn'
#         (macro/weighted/micro da TP/FP/FN, accuracy separata),
#       - poi fa la media aritmetica tra feature.
#     """
#     import numpy as np

#     out_keys = [
#         "accuracy","precision","recall","f1",
#         "precision_weighted","recall_weighted","f1_weighted",
#         "accuracy_weighted","precision_micro","recall_micro","f1_micro","accuracy_micro",
#         "support_sum",
#     ]
#     agg = {k: 0.0 for k in out_keys}
#     feat_count = 0

#     def _metrics_from_cm(G: np.ndarray) -> Dict[str, float]:
#         total = int(G.sum())
#         tp = np.diag(G).astype(float)
#         per_class_true = G.sum(axis=1).astype(float)   # support (y_true)
#         per_class_pred = G.sum(axis=0).astype(float)   # count (y_pred)

#         # per-class
#         precision_c = np.divide(tp, per_class_pred, out=np.zeros_like(tp), where=per_class_pred > 0)
#         recall_c    = np.divide(tp, per_class_true, out=np.zeros_like(tp), where=per_class_true > 0)
#         denom = precision_c + recall_c
#         f1_c = np.divide(2 * precision_c * recall_c, denom, out=np.zeros_like(denom), where=denom > 0)

#         # macro (classi con supporto > 0)
#         valid = per_class_true > 0
#         macro_precision = float(precision_c[valid].mean()) if valid.any() else 0.0
#         macro_recall    = float(recall_c[valid].mean())    if valid.any() else 0.0
#         macro_f1        = float(f1_c[valid].mean())        if valid.any() else 0.0

#         # weighted (pesi = supporto vero per classe)
#         supp = per_class_true
#         supp_sum = float(supp.sum())
#         if supp_sum > 0:
#             weighted_precision = float((precision_c * supp).sum() / supp_sum)
#             weighted_recall    = float((recall_c    * supp).sum() / supp_sum)
#             weighted_f1        = float((f1_c        * supp).sum() / supp_sum)
#         else:
#             weighted_precision = weighted_recall = weighted_f1 = 0.0

#         # micro (da TP/FP/FN; corretto anche in multi-label)
#         TP_sum = float(tp.sum())
#         FP_sum = float(per_class_pred.sum() - tp.sum())
#         FN_sum = float(per_class_true.sum() - tp.sum())

#         micro_precision = TP_sum / (TP_sum + FP_sum) if (TP_sum + FP_sum) > 0 else 0.0
#         micro_recall    = TP_sum / (TP_sum + FN_sum) if (TP_sum + FN_sum) > 0 else 0.0
#         micro_den       = micro_precision + micro_recall
#         micro_f1        = (2 * micro_precision * micro_recall / micro_den) if micro_den > 0 else 0.0

#         accuracy = TP_sum / total if total > 0 else 0.0

#         return dict(
#             accuracy=accuracy,
#             precision=macro_precision, recall=macro_recall, f1=macro_f1,
#             precision_weighted=weighted_precision, recall_weighted=weighted_recall, f1_weighted=weighted_f1,
#             accuracy_weighted=accuracy,
#             precision_micro=micro_precision, recall_micro=micro_recall, f1_micro=micro_f1, accuracy_micro=accuracy,
#             support_sum=int(supp_sum),
#         )

#     for feat, m in per_feature.items():
#         cm = m.get("confusion_matrix", {})
#         labels = cm.get("labels", []) or []
#         mat = np.array(cm.get("matrix", []), dtype=int)
#         if mat.size == 0 or len(labels) == 0:
#             continue
#         if mat.shape != (len(labels), len(labels)):
#             continue

#         feat_metrics = _metrics_from_cm(mat)
#         for k in out_keys:
#             agg[k] += float(feat_metrics[k])
#         feat_count += 1

#     if feat_count == 0:
#         return {k: 0.0 for k in out_keys}

    # media semplice tra feature (pari peso ai task)
    # for k in out_keys:
    #     agg[k] = float(agg[k] / feat_count)

    # # support_sum come media dei supporti per feature (coerente con "pari peso")
    # agg["support_sum"] = int(agg["support_sum"])
    # return agg


# # ========================
# # Overall (macro + weighted tra feature) ACCURACY OVERALL IN STRINGA
# # ========================

def _overall_from_per_feature(per_feature: Dict[str, Dict]) -> Dict[str, float]:
    """
    OVERALL:
      - Precision/Recall/F1: media tra feature (pari peso ai task).
      - Accuracy: pooled su tutte le feature (TP_tot / N_tot).
    """
    import numpy as np

    out_keys = [
        "accuracy","precision","recall","f1",
        "precision_weighted","recall_weighted","f1_weighted",
        "accuracy_weighted","precision_micro","recall_micro","f1_micro","accuracy_micro",
        "support_sum",
    ]
    agg = {k: 0.0 for k in out_keys}
    feat_count = 0

    # accumulatori per accuracy pooled
    tp_global = 0.0
    n_global = 0.0

    def _metrics_from_cm(G: np.ndarray) -> Dict[str, float]:
        total = int(G.sum())
        tp = np.diag(G).astype(float)
        per_class_true = G.sum(axis=1).astype(float)
        per_class_pred = G.sum(axis=0).astype(float)

        precision_c = np.divide(tp, per_class_pred, out=np.zeros_like(tp), where=per_class_pred > 0)
        recall_c    = np.divide(tp, per_class_true, out=np.zeros_like(tp), where=per_class_true > 0)
        denom = precision_c + recall_c
        f1_c = np.divide(2 * precision_c * recall_c, denom, out=np.zeros_like(denom), where=denom > 0)

        valid = per_class_true > 0
        macro_precision = float(precision_c[valid].mean()) if valid.any() else 0.0
        macro_recall    = float(recall_c[valid].mean())    if valid.any() else 0.0
        macro_f1        = float(f1_c[valid].mean())        if valid.any() else 0.0

        supp = per_class_true
        supp_sum = float(supp.sum())
        if supp_sum > 0:
            weighted_precision = float((precision_c * supp).sum() / supp_sum)
            weighted_recall    = float((recall_c    * supp).sum() / supp_sum)
            weighted_f1        = float((f1_c        * supp).sum() / supp_sum)
        else:
            weighted_precision = weighted_recall = weighted_f1 = 0.0

        TP_sum = float(tp.sum())
        FP_sum = float(per_class_pred.sum() - tp.sum())
        FN_sum = float(per_class_true.sum() - tp.sum())

        micro_precision = TP_sum / (TP_sum + FP_sum) if (TP_sum + FP_sum) > 0 else 0.0
        micro_recall    = TP_sum / (TP_sum + FN_sum) if (TP_sum + FN_sum) > 0 else 0.0
        micro_den       = micro_precision + micro_recall
        micro_f1        = (2 * micro_precision * micro_recall / micro_den) if micro_den > 0 else 0.0

        accuracy = TP_sum / total if total > 0 else 0.0

        return dict(
            accuracy=accuracy,
            precision=macro_precision, recall=macro_recall, f1=macro_f1,
            precision_weighted=weighted_precision, recall_weighted=weighted_recall, f1_weighted=weighted_f1,
            accuracy_weighted=accuracy,
            precision_micro=micro_precision, recall_micro=micro_recall, f1_micro=micro_f1, accuracy_micro=accuracy,
            support_sum=int(supp_sum),
            _tp=TP_sum, _n=total,   # <— servono solo per il pooled
        )

    for feat, m in per_feature.items():
        cm = m.get("confusion_matrix", {})
        labels = cm.get("labels", []) or []
        mat = np.array(cm.get("matrix", []), dtype=int)
        if mat.size == 0 or len(labels) == 0 or mat.shape != (len(labels), len(labels)):
            continue

        fm = _metrics_from_cm(mat)
        # somma per media tra feature (resto delle metriche)
        for k in out_keys:
            if k in fm:
                agg[k] += float(fm[k])
        feat_count += 1

        # accumula per accuracy pooled
        tp_global += fm["_tp"]
        n_global  += fm["_n"]

    if feat_count == 0:
        return {k: 0.0 for k in out_keys}

    # media semplice tra feature per tutte le metriche NON accuracy
    for k in out_keys:
        agg[k] = float(agg[k] / feat_count)

    # override: accuracy pooled su tutte le feature
    pooled_acc = (tp_global / n_global) if n_global > 0 else 0.0
    agg["accuracy"] = pooled_acc
    agg["accuracy_micro"] = pooled_acc   # in single-label coincide col micro sul pool globale
    agg["accuracy_weighted"] = pooled_acc

    # support_sum: mantieni come media (coerente con "pari peso ai task")
    agg["support_sum"] = int(agg["support_sum"])
    return agg

# ========================
# Exact-Match per record (tutta la riga)
# ========================
def _compute_exact_match(df_pred: pd.DataFrame,
                         df_gt: pd.DataFrame,
                         label_types: Dict[str, str],
                         out_dir: str):
    """
    Exact-match per record confrontando TUTTE le feature condivise tra pred e GT,
    escludendo solo i meta campi in META_EXCLUDE. NON usa label_types per
    decidere cosa includere.
    Scrive:
      - exact_match.csv  (id, exact_match, n_mismatches, mismatched_fields)
      - exact_match.json (accuracy, n_records, features_used, by_id[...])
    """
    def _cell_norm(v):
        s = str(v)
        if s.strip().startswith("[") and s.strip().endswith("]"):
            try:
                lst = ast.literal_eval(s)
                for x in lst:
                    xs = str(x).strip()
                    if xs:
                        s = xs
                        break
            except Exception:
                pass
        s = s.strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s

    os.makedirs(out_dir, exist_ok=True)

    pred = df_pred.groupby("report_id_short", as_index=False).first()
    gt   = df_gt.groupby("id", as_index=False).first()

    shared_cols = sorted([
        c for c in pred.columns
        if c in gt.columns and c not in META_EXCLUDE
    ])

    ids = sorted(set(pred["report_id_short"].astype(str)) & set(gt["id"].astype(str)))

    rows = []
    em_hits = 0

    for rid in ids:
        pr = pred[pred["report_id_short"] == rid].iloc[0]
        gr = gt[gt["id"] == rid].iloc[0]

        mismatches = 0
        bad_fields = []

        for f in shared_cols:
            y_true = _cell_norm(gr.get(f, ""))
            y_pred = _cell_norm(pr.get(f, ""))
            if y_true != y_pred:
                mismatches += 1
                bad_fields.append(f"{f}: GT='{y_true}' | PRED='{y_pred}'")

        em = 1 if mismatches == 0 else 0
        em_hits += em
        rows.append({
            "id": rid,
            "exact_match": em,
            "n_mismatches": mismatches,
            "mismatched_fields": "; ".join(bad_fields)
        })

    em_csv = os.path.join(out_dir, "exact_match.csv")
    pd.DataFrame(rows, columns=["id", "exact_match", "n_mismatches", "mismatched_fields"]).to_csv(em_csv, index=False)

    n = len(ids)
    em_json = os.path.join(out_dir, "exact_match.json")
    with open(em_json, "w", encoding="utf-8") as f:
        json.dump({
            "accuracy": (float(em_hits) / n if n else 0.0),
            "n_records": n,
            "features_used": shared_cols,
            "by_id": rows
        }, f, ensure_ascii=False, indent=2)



def _plot_metrics_heatmap(csv_path: str, out_path: str):
    """Heatmap (feature × metriche) da med_metrics.csv"""
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return
        metrics = ["accuracy","precision","recall","f1-score"]
        df_m = df.set_index("feature")[metrics].astype(float)
        plt.figure(figsize=(8, len(df_m)*0.4+2))
        sns.heatmap(df_m, annot=True, fmt=".2f", cmap="YlGnBu", cbar=True)
        plt.title("Heatmap per feature")
        plt.tight_layout()
        plt.savefig(out_path)
        plt.close()
    except Exception as e:
        print("WARN: heatmap non creata:", e)


def _plot_global_radar(overall: Dict[str,float], out_path: str):
    """Radar/spider plot delle metriche globali"""
    try:
        labels = ["accuracy","precision","recall","f1"]
        values = [float(overall.get(k,0)) for k in labels]

        # chiudi solo i valori, NON aggiungere etichette
        values += [values[0]]

        # calcola gli angoli per i 5 punti (4+chiusura)
        angles = np.linspace(0, 2*np.pi, len(values), endpoint=False)

        fig = plt.figure(figsize=(5,5))
        ax = fig.add_subplot(111, polar=True)

        # traccia il poligono chiuso
        ax.plot(angles, values, "o-", linewidth=2)
        ax.fill(angles, values, alpha=0.25)

        # mostra SOLO le 4 etichette sugli assi (non la chiusura)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels)
        ax.tick_params(pad=15)   # allontana le etichette dal centro

        ax.set_yticks([0.2,0.4,0.6,0.8,1.0])
        ax.set_ylim(0,1)
        ax.set_title("Metriche complessive", pad=25)

        plt.tight_layout()
        plt.savefig(out_path)
        plt.close()
    except Exception as e:
        print("WARN: radar non creato:", e)





# ========================
# Outputs
# ========================
# ========================
# Outputs
# ========================
def _write_outputs(per_features: Dict[str, Dict], out_dir: str, diagnostics: Optional[Dict] = None):
    os.makedirs(out_dir, exist_ok=True)

    # ---- med_metrics.csv (SOLO per-feature) ----
    metrics = ["accuracy", "precision", "recall", "f1-score"]
    print(per_features)
    for metric in metrics:
        data = {}
        for model_name in per_features:
            row = {}
            for feat, m in per_features[model_name].items():
                sup = int(m.get("support", 0))
                mdata = m.get("per_class", {}) if metric == 'accuracy' else m['macro_avg']
                row[feat] = _r2(mdata.get(metric, 0))
            data[model_name.split('/')[-1].replace('.csv', '')] = row
        print(data)
        pd.DataFrame(data).T.to_csv(os.path.join(out_dir, f"med_multi_{metric}.csv"))

    metric_files = []
    heatmap_files = []
    # ---- Heatmap filtrata ----
    for metric in metrics:
        metric_file =  f"med_multi_{metric}.csv"
        metric_files.append(metric_file)
        
        try:
            df_h = pd.read_csv(os.path.join(out_dir, metric_file), index_col=0)
            df_h = df_h[[c for c in df_h.columns if c not in ["collateral", "comorbidity"]]]
           
            if not df_h.empty:
                # plt.figure(figsize=(8, len(df_m)*0.4+2))
                sns.heatmap(df_h, annot=True, fmt=".2f", cmap="YlGnBu", cbar=True)
                plt.title(metric.capitalize() +" per feature")
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f"heatmap_{metric}.png"))
                plt.close()
                heatmap_files.append(f"heatmap_{metric}.png")
        except Exception as e:
            print("WARN: heatmap non creata:", e)



    # ---- ZIP ----
    try:
        zip_path = os.path.join(out_dir, "eval_multi_results.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for fn in metric_files+heatmap_files:
                p = os.path.join(out_dir, fn)
                if os.path.exists(p):
                    zf.write(p, arcname=fn)
    except Exception as e:
        print("WARN: ZIP non creato:", e)


# ========================
# Public API — valutatore per feature con filtro TKI
# ========================

def run_medication_multi_evaluation(
    pred_paths: str,
    gt_path: str,
    static_dir: str = None,
    *,
    tki_only: bool = True,
    custom_tki_list: Optional[Iterable[str]] = None,
    id_filter: Optional[Iterable[str] or str] = None,
) -> Dict:
    if static_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_dir = os.path.join(base, "static")
        os.makedirs(static_dir, exist_ok=True)

    df_preds, df_gt = _prepare_frames(pred_paths, gt_path)


    
    # TKI filter PRIMA di tutto (per-riga)
    tki_set = set(_norm(x) for x in (custom_tki_list or DEFAULT_TKI_LIST))
    if tki_only:
        df_preds = [_filter_tki(df_pred, tki_set, medication_col="medication") for df_pred in df_preds]
        df_gt   = _filter_tki(df_gt,   tki_set, medication_col="medication")

 
    
    # one-row per chiave composta (id::medication)
    df_preds = [df_pred.groupby("report_id_short", as_index=False).first() for df_pred in df_preds]
    df_gt   = df_gt.groupby("id", as_index=False).first()



    # Riduci ai soli ID comuni (e opzionale filtro esplicito)
    ids_preds = None
    for df_pred in df_preds:
        if ids_preds is None:
            ids_preds = set(df_pred["report_id_short"].astype(str))
        else:
            ids_preds = ids_preds & set(df_pred["report_id_short"].astype(str))
    ids_gt   = set(df_gt["id"].astype(str))
    ids_comuni = ids_preds & ids_gt
    

    if id_filter is not None:
        if isinstance(id_filter, str):
            id_filter = [id_filter]
        id_filter = {str(x) for x in id_filter}
        ids_comuni = ids_comuni & id_filter

    df_preds = [df_pred[df_pred["report_id_short"].astype(str).isin(ids_comuni)].copy() for df_pred in df_preds]
    df_gt   = df_gt[df_gt["id"].astype(str).isin(ids_comuni)].copy()

    # auto-detect dei tipi
    label_types = _detect_label_types(df_preds, df_gt)

    per_feature = []
    for model_path, df_pred in zip(pred_paths, df_preds):
        per_feature.append(_compute_per_feature(df_pred, df_gt, label_types, out_dir=static_dir))
        # overall = _overall_from_per_feature(per_feature)
    diagnostics = {
        "ids_eval_count": len(ids_comuni),
        "tki_only": bool(tki_only),
        "mode": "feature"
    }

        # Exact-Match su tutta la riga
        # _compute_exact_match(df_pred, df_gt, label_types, out_dir=static_dir)

    _write_outputs({p:pf for p, pf in zip(pred_paths,per_feature)}, static_dir, diagnostics=diagnostics)
    print('3')
    return {
        "per_feature": per_feature,
        "out_dir": static_dir,
        "diagnostics": diagnostics
    }


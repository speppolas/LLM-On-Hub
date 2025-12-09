import os
import json
import logging
import time
import subprocess
from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory
from werkzeug.utils import secure_filename
from typing import Dict, Any, Optional

# Use the already-registered blueprint from app.api
from app.api import bp
from app.utils import clean_expired_files as utils_clean_expired_files, get_all_trials

from app.core.normalization import normalize_features_for_schema
from app.core.feature_extraction import (
    extract_text_from_pdf, 
    extract_features_with_llm, 
    highlight_sources, 
    create_annotated_pdf,
    process_patient_document,
    # Add this for the highlighting function

)
from app.core.medication_extraction import extract_medications_from_excel, extract_medications_from_csv
from app.core.timeline_extraction import extract_timeline_from_excel, extract_timeline_from_text
from app.core.medication_evaluation import run_medication_evaluation
from app.core.medication_multi_evaluation import run_medication_multi_evaluation
from app import logger
import pandas as pds

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_safety(file) -> Dict[str, Any]:
    """Validate uploaded file for safety and compliance."""
    if not file or file.filename == '':
        return {"valid": False, "error": "No file selected"}
    
    if not allowed_file(file.filename):
        return {"valid": False, "error": "File type not allowed. Please upload PDF files only."}
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset pointer
    
    if file_size > MAX_FILE_SIZE:
        return {"valid": False, "error": f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"}
    
    if file_size == 0:
        return {"valid": False, "error": "File is empty"}
    
    return {"valid": True, "size": file_size}

@bp.route('/')
def index():
    logger.info("Accessed home page")
    return render_template('index.html')

@bp.route('/medications')
def medications():
    return render_template('medications.html')

@bp.route('/timeline')
def timeline():
    return render_template('timeline.html')

@bp.route('/settings')
def settings_page():
    return render_template('settings.html')

@bp.route('/trials')
def trials_page():
    return render_template('trials.html')

# Add this to routes.py in the process endpoint, updating the response section:
'''
# MAIN PROCESSING ENDPOINT - Fixed URL to match frontend
@bp.route('/api/process', methods=['POST'])
def process():
    try:
        logger.info("Processing request started")
        
        # Clean expired files first
        utils_clean_expired_files()
        
        # Check if it's a file upload or text input
        if 'file' in request.files and request.files['file'].filename:
            # Handle file upload
            file = request.files['file']
            
            # Validate file
            validation_result = validate_file_safety(file)
            if not validation_result["valid"]:
                return jsonify({
                    "success": False,
                    "error": validation_result["error"],
                    "error_type": "file_validation"
                }), 400
            
            # Save file temporarily
            filename = secure_filename(file.filename)
            timestamp = str(int(time.time()))
            safe_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
            
            try:
                file.save(filepath)
                logger.info(f"File saved: {safe_filename} ({validation_result['size']} bytes)")
                
                # Use the main processing pipeline
                result = process_patient_document(filepath, is_file=True)
                
                # DON'T clean up the original file immediately since we need it for viewing
                # It will be cleaned later by the scheduled cleanup
                
                if not result["success"]:
                    return jsonify(result), 500
                
                # Return the complete results including annotated PDF URL
                return jsonify({
                    "success": True,
                    "features": result["features"],        # Clean features (no source text)
                    "highlighted_text": result["highlighted_text"],  # Text with highlights
                    "annotated_pdf_url": result.get("annotated_pdf_url"),  # URL to annotated PDF
                    "matched_trials": result["matched_trials"],
                    "processing_metadata": {
                        "timestamp": time.time(),
                        "input_type": "file",
                        "filename": filename,
                        "features_count": len(result["features"]),
                        "trials_matched": len(result["matched_trials"]),
                        "has_highlighted_text": bool(result["highlighted_text"]),
                        "has_annotated_pdf": bool(result.get("annotated_pdf_url"))
                    }
                })
                
            except Exception as e:
                # Clean up file on error
                if os.path.exists(filepath):
                    os.remove(filepath)
                logger.error(f"File processing error: {str(e)}")
                return jsonify({
                    "success": False,
                    "error": f"File processing failed: {str(e)}",
                    "error_type": "processing"
                }), 500
                
        elif request.form.get('text_content'):
            # Handle text input
            text_content = request.form.get('text_content', '').strip()
            
            if not text_content:
                return jsonify({
                    "success": False,
                    "error": "No text content provided",
                    "error_type": "validation"
                }), 400
            
            if len(text_content) < 50:
                return jsonify({
                    "success": False,
                    "error": "Please provide more detailed clinical information",
                    "error_type": "validation"
                }), 400
            
            # Use the main processing pipeline
            result = process_patient_document(text_content, is_file=False)
            
            if not result["success"]:
                return jsonify(result), 500
            
            return jsonify({
                "success": True,
                "features": result["features"],        # Clean features (no source text)
                "highlighted_text": result["highlighted_text"],  # Text with highlights  
                "annotated_pdf_url": None,  # No PDF for text input
                "matched_trials": result["matched_trials"],
                "processing_metadata": {
                    "timestamp": time.time(),
                    "input_type": "text",
                    "features_count": len(result["features"]),
                    "trials_matched": len(result["matched_trials"]),
                    "has_highlighted_text": bool(result["highlighted_text"]),
                    "has_annotated_pdf": False
                }
            })
            
        else:
            return jsonify({
                "success": False,
                "error": "No file or text content provided",
                "error_type": "validation"
            }), 400
            
    except Exception as e:
        logger.error(f"Unexpected error in process endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An unexpected error occurred during processing: {str(e)}",
            "error_type": "server",
            "debug_info": str(e) if current_app.debug else None
        }), 500
'''
@bp.route('/api/process', methods=['POST'])
def process():
    try:
        logger.info("Processing request started")

        # Clean expired files first
        utils_clean_expired_files()

        # Check if it's a file upload or text input
        if 'file' in request.files and request.files['file'].filename:
            # Handle file upload
            file = request.files['file']
            
            # Validate file
            validation_result = validate_file_safety(file)
            if not validation_result["valid"]:
                return jsonify({
                    "success": False,
                    "error": validation_result["error"],
                    "error_type": "file_validation"
                }), 400
            
            # Save file temporarily
            filename = secure_filename(file.filename)
            timestamp = str(int(time.time()))
            safe_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
            
            try:
                file.save(filepath)
                logger.info(f"File saved: {safe_filename} ({validation_result['size']} bytes)")
                
                # Process the file (PDF) through the feature extraction pipeline
                result = process_patient_document(filepath, is_file=True)

                # Don't clean up the original file immediately
                if not result["success"]:
                    return jsonify(result), 500
                
                # Return processed results including annotated PDF URL
                return jsonify({
                    "success": True,
                    "features": result["features"],
                    "highlighted_text": result["highlighted_text"],
                    "annotated_pdf_url": result.get("annotated_pdf_url"),
                    "matched_trials": result["matched_trials"]
                })
                
            except Exception as e:
                if os.path.exists(filepath):
                    os.remove(filepath)
                logger.error(f"File processing error: {str(e)}")
                return jsonify({
                    "success": False,
                    "error": f"File processing failed: {str(e)}",
                    "error_type": "processing"
                }), 500

        elif request.form.get('text_content'):
            # Handle text input
            text_content = request.form.get('text_content', '').strip()
            if not text_content:
                return jsonify({
                    "success": False,
                    "error": "No text content provided",
                    "error_type": "validation"
                }), 400
            
            if len(text_content) < 50:
                return jsonify({
                    "success": False,
                    "error": "Please provide more detailed clinical information",
                    "error_type": "validation"
                }), 400
            
            result = process_patient_document(text_content, is_file=False)
            
            if not result["success"]:
                return jsonify(result), 500
            
            return jsonify({
                "success": True,
                "features": result["features"],
                "highlighted_text": result["highlighted_text"],  
                "annotated_pdf_url": None,  
                "matched_trials": result["matched_trials"]
            })

        else:
            return jsonify({
                "success": False,
                "error": "No file or text content provided",
                "error_type": "validation"
            }), 400

    except Exception as e:
        logger.error(f"Unexpected error in process endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An unexpected error occurred during processing: {str(e)}",
            "error_type": "server",
            "debug_info": str(e) if current_app.debug else None
        }), 500


@bp.route('/api/models')
def get_models():
    """Returns supported generative models."""
    allowed_models = [
        #"mistral:instruct",
        #"qwen2.5:32b",
        #"phi4:14b",
        #"deepseek-r1:14b",
        #"gemma:latest",
        #"qwen:14b",
        #"qwen:latest",
        #"llama3:8b-instruct-q4_K_M",
        #"mistral-small3.2:24b",
        #"devstral:24b",
        #"qwen3:30b",
        #"qwen3:14b",
        "gemma3:12b",
        "gemma3:27b",
        #"llama3.1:8b-custom",
        "llama3.1:8b",
        "mistral:latest",
    ]
    return jsonify({"models": allowed_models}), 200

import tempfile

CONFIG_DEFAULT = {
    "LLM_MODEL": "llama3.1:8b-custom",
    "LLM_CONTEXT_SIZE": 8192,
    "LLM_TEMPERATURE": 0.1,
    "TRIAL_MATCHING_BATCH_SIZE": 4,
}
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _load_config():
    if not os.path.exists(CONFIG_PATH):
        _save_config(CONFIG_DEFAULT)
        return dict(CONFIG_DEFAULT)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(CONFIG_DEFAULT)
        merged.update(data or {})
        return merged
    except Exception:
        _save_config(CONFIG_DEFAULT)
        return dict(CONFIG_DEFAULT)


def _save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="config.", suffix=".json",
                                    dir=os.path.dirname(CONFIG_PATH))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(cfg, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, CONFIG_PATH)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@bp.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(_load_config())


@bp.route("/api/settings", methods=["POST"])
def save_settings():
    incoming = request.get_json(force=True, silent=True) or {}
    current = _load_config()

    def _int(value, fallback):
        try: return int(value)
        except Exception: return fallback

    def _float(value, fallback):
        try: return float(value)
        except Exception: return fallback

    updated = dict(current)
    if "LLM_MODEL" in incoming:
        updated["LLM_MODEL"] = str(incoming["LLM_MODEL"])
    if "LLM_CONTEXT_SIZE" in incoming:
        updated["LLM_CONTEXT_SIZE"] = _int(incoming["LLM_CONTEXT_SIZE"], current["LLM_CONTEXT_SIZE"])
    if "LLM_TEMPERATURE" in incoming:
        updated["LLM_TEMPERATURE"] = _float(incoming["LLM_TEMPERATURE"], current["LLM_TEMPERATURE"])
    if "TRIAL_MATCHING_BATCH_SIZE" in incoming:
        updated["TRIAL_MATCHING_BATCH_SIZE"] = _int(incoming["TRIAL_MATCHING_BATCH_SIZE"], current["TRIAL_MATCHING_BATCH_SIZE"])

    _save_config(updated)
    return jsonify({"message": "Settings saved successfully!", "settings": updated})


@bp.route('/api/trials', methods=['GET'])
def get_trials():
    try:
        trials = get_all_trials()
        
        # Optional filtering
        phase_filter = request.args.get('phase')
        cancer_type_filter = request.args.get('cancer_type')
        
        filtered_trials = trials
        
        if phase_filter:
            filtered_trials = [t for t in filtered_trials 
                             if t.get('phase', '').lower() == phase_filter.lower()]
        
        if cancer_type_filter:
            filtered_trials = [t for t in filtered_trials 
                             if cancer_type_filter.lower() in t.get('title', '').lower()]
        
        return jsonify({
            "success": True,
            "trials": filtered_trials,
            "total_count": len(trials),
            "filtered_count": len(filtered_trials)
        })
        
    except Exception as e:
        logger.error(f"Error fetching trials: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to fetch trials",
            "error_type": "database"
        }), 500

@bp.route('/api/validate-features', methods=['POST'])
def validate_clinical_features():
    """Endpoint for validating clinical features against medical guidelines."""
    try:
        features = request.json.get('features', {})
        
        if not features:
            return jsonify({
                "success": False,
                "error": "No features provided for validation"
            }), 400
        
        # Normalize and validate features
        normalized_features = normalize_features_for_schema(features)
        
        # Create validation report
        validation_report = {
            "success": True,
            "normalized_features": normalized_features,
            "validation_summary": {
                "total_fields": len(features),
                "normalized_fields": len(normalized_features),
                "changes_made": []
            }
        }
        
        # Compare original vs normalized to identify changes
        for key in features:
            if key in normalized_features:
                if features[key] != normalized_features[key]:
                    validation_report["validation_summary"]["changes_made"].append({
                        "field": key,
                        "original": features[key],
                        "normalized": normalized_features[key]
                    })
        
        return jsonify(validation_report)
        
    except Exception as e:
        logger.error(f"Feature validation error: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Feature validation failed",
            "error_type": "validation"
        }), 500

@bp.route('/view-pdf/<path:filename>')
def view_pdf(filename):
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    return send_from_directory(upload_folder, filename)

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'logo.svg',
        mimetype='image/svg+xml'
    )

@bp.route('/api/clean', methods=['POST'])
def clean_files():
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        utils_clean_expired_files(upload_folder)
        logger.info("Expired files cleaned")
        return jsonify({'status': 'success', 'message': 'Expired files cleaned successfully'}), 200
    except Exception as e:
        logger.error(f"Failed to clean files: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring system status."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {
                "upload_folder": os.path.exists(UPLOAD_FOLDER),
                "logs_folder": os.path.exists("logs"),
                "database": True,
                "llm_processor": True
            }
        }
        
        failed_components = [k for k, v in health_status["components"].items() if not v]
        
        if failed_components:
            health_status["status"] = "degraded"
            health_status["issues"] = failed_components
            return jsonify(health_status), 206
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }), 503

@bp.route('/api/system-stats', methods=['GET'])
def get_system_stats():
    """Get system statistics and processing metrics."""
    try:
        log_files = []
        if os.path.exists("logs"):
            log_files = [f for f in os.listdir("logs") if f.endswith('.json')]
        
        stats = {
            "success": True,
            "statistics": {
                "total_log_files": len(log_files),
                "upload_folder_size": get_folder_size(UPLOAD_FOLDER),
                "logs_folder_size": get_folder_size("logs"),
                "available_trials": len(get_all_trials()),
            },
            "recent_activity": {
                "recent_extractions": len([f for f in log_files if 'extraction' in f]),
                "recent_matches": len([f for f in log_files if 'matched' in f]),
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Stats collection error: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to collect system statistics"
        }), 500

def get_folder_size(folder_path: str) -> int:
    """Calculate total size of folder in bytes."""
    try:
        if not os.path.exists(folder_path):
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        return total_size
    except:
        return 0

# Error handlers
@bp.errorhandler(413)
def file_too_large(e):
    """Handle file too large error."""
    return jsonify({
        "success": False,
        "error": f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB",
        "error_type": "file_size"
    }), 413

@bp.errorhandler(400)
def bad_request(e):
    """Handle bad request errors."""
    return jsonify({
        "success": False,
        "error": "Bad request",
        "error_type": "client"
    }), 400

@bp.errorhandler(500)
def internal_error(e):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {str(e)}")
    return jsonify({
        "success": False,
        "error": "Internal server error",
        "error_type": "server"
    }), 500


# -------------------------
# MEDICATIONS (Excel/CSV)
# -------------------------
@bp.route('/process_medications', methods=['POST'])
def process_medications():
    return handle_feature_extraction_excel(extract_func=extract_medications_from_excel, label="medications")

# -------------------------
# TIMELINE (Excel file)
# -------------------------
@bp.route('/process_timeline', methods=['POST'])
def process_timeline():
    return handle_timeline_extraction_excel(extract_func=extract_timeline_from_excel, label="timeline")

# Per-row endpoint to process a single report string (for sequential display on the frontend)
@bp.route('/process_timeline_text', methods=['POST'])
def process_timeline_text():
    try:
        payload = request.get_json(force=True, silent=False)
        row_id = str(payload.get('id', '') if payload else '')
        report = (payload.get('report') or '').strip()
        if not report:
            return jsonify({'error': 'Missing "report" text.'}), 400

        events = extract_timeline_from_text(report)

        cleaned_events = []
        for ev in events:
            if isinstance(ev, dict):
                # Ensure required keys exist
                ev.setdefault('data', '')
                ev.setdefault('testo', '')
                cleaned_events.append(ev)
            else:
                # If the model returned a string (bad), wrap it safely
                cleaned_events.append({
                    "data": "",
                    "testo": str(ev)
                })

        events = cleaned_events
        return jsonify({'id': row_id, 'features': events}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()   # <<< prints full traceback to your terminal
        raise                   # <<< rethrow so Flask debugger shows the error



################################
        # # Ensure all RECIST-related fields exist for frontend rendering
        # for ev in events:
        #     ev.setdefault('risposta_recist', '')
        #     ev.setdefault('basis_note', '')
        #     ev.setdefault('basis_compared_to', '')


    #     return jsonify({'id': row_id, 'features': events}), 200
    # except Exception as e:
    #     logger.exception("❌ Error in /process_timeline_text")
    #     return jsonify({'error': str(e)}), 500
################################


# @bp.route('/medications_evaluation')
# def medications_evaluation():
#     import os, json
#     import pandas as pd

#     med_path = os.path.join('app', 'static', 'med_metrics.csv')
#     metrics_path = os.path.join('app', 'static', 'global_metrics.json')
#     med_img_path = "med_f1.png"

#     if os.path.exists(med_path):
#         df = pd.read_csv(
#             med_path,
#             dtype={'support': 'string'},
#             keep_default_na=False
#         )
#         if 'support' in df.columns:
#             df['support'] = df['support'].apply(
#                 lambda x: x if x == '' else str(int(float(x))) if str(x).replace('.', '', 1).isdigit() else str(x)
#             )
#         med_metrics = df.to_dict(orient='records')
#     else:
#         med_metrics = []

#     summary = {}
#     if os.path.exists(metrics_path):
#         with open(metrics_path) as f:
#             summary = json.load(f)

#     return render_template(
#         'medications_evaluation.html',
#         med_metrics=med_metrics,
#         summary_metrics=summary,
#         combo_metrics=[],
#         med_img=med_img_path,
#         acc_img="med_accuracy.png",
#         prec_img="med_precision.png",
#         rec_img="med_recall.png"
#     )
@bp.route('/medications_evaluation')
def medications_evaluation():
    import os, json
    import pandas as pd

    base_static = os.path.join('app', 'static')
    med_path = os.path.join(base_static, 'med_metrics.csv')
    metrics_path = os.path.join(base_static, 'global_metrics.json')

    # nuovi percorsi immagini
    heatmap_img_path = "heatmap_metrics.png"
    radar_img_path = "global_radar.png"

    med_img_path = "med_f1.png"

    if os.path.exists(med_path):
        df = pd.read_csv(
            med_path,
            dtype={'support': 'string'},
            keep_default_na=False
        )
        if 'support' in df.columns:
            df['support'] = df['support'].apply(
                lambda x: x if x == '' else str(int(float(x))) if str(x).replace('.', '', 1).isdigit() else str(x)
            )
        med_metrics = df.to_dict(orient='records')
    else:
        med_metrics = []

    summary = {}
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            summary = json.load(f)

    return render_template(
        'medications_evaluation.html',
        med_metrics=med_metrics,
        summary_metrics=summary,
        combo_metrics=[],
        med_img=med_img_path,
        acc_img="med_accuracy.png",
        prec_img="med_precision.png",
        rec_img="med_recall.png",
        heatmap_img=heatmap_img_path,
        radar_img=radar_img_path
    )
    
@bp.route('/medications_multi_evaluation')
def medications_multi_evaluation():
    import os, json
    import pandas as pd

    base_static = os.path.join('app', 'static')

    f1_img = None
    acc_img = None
    prec_img = None
    rec_img = None
    if os.path.exists(os.path.join(base_static, 'heatmap_f1-score.png')):
        f1_img = "heatmap_f1-score.png"
    if os.path.exists(os.path.join(base_static, 'heatmap_accuracy.png')):
        acc_img = "heatmap_accuracy.png"
    if os.path.exists(os.path.join(base_static, 'heatmap_precision.png')):
        prec_img = "heatmap_precision.png"
    if os.path.exists(os.path.join(base_static, 'heatmap_recall.png')):
        rec_img = "heatmap_recall.png"
    med_metrics = False
    if all(img is not None for img in [f1_img, acc_img, prec_img, rec_img]):
        med_metrics = True
    return render_template(
        'medications_multi_evaluation.html',
        f1_img=f1_img,
        acc_img=acc_img,
        prec_img=prec_img,
        rec_img=rec_img,
        med_metrics=med_metrics
    )

# -------------------------
# TIMELINE EVALUATION (UI)
# -------------------------
@bp.route('/timeline_evaluation')
def timeline_evaluation():
    base_dir = os.path.join(current_app.static_folder, 'timeline_eval')
    summary_file = os.path.join(base_dir, 'timeline_summary.json')
    metrics_file = os.path.join(base_dir, 'timeline_metrics.csv')
    counts_file  = os.path.join(base_dir, 'timeline_counts.csv')

    overall = {}
    per_event = []
    candidate_files = {
        "summary": "timeline_eval/timeline_summary.json",
        "metrics": "timeline_eval/timeline_metrics.csv",
        "counts":  "timeline_eval/timeline_counts.csv",
    }

    if os.path.exists(summary_file):
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                s = json.load(f)
            overall = s.get('overall', {}) or {}
            per_event = s.get('per_event', []) or []
        except Exception as e:
            current_app.logger.exception(f"❌ Failed to read summary JSON: {e}")

    if not per_event and os.path.exists(metrics_file):
        try:
            df = pd.read_csv(metrics_file)
            per_event = df.to_dict(orient='records')
        except Exception as e:
            current_app.logger.exception(f"❌ Failed to read metrics CSV: {e}")

    files = {}
    for key, relpath in candidate_files.items():
        if os.path.exists(os.path.join(current_app.static_folder, relpath)):
            files[key] = relpath

    return render_template(
        'timeline_evaluation.html',
        overall=overall,
        per_event=per_event,
        files=files
    )

@bp.route('/upload_evaluation_data', methods=['POST'])
def upload_evaluation_data():
    try:
        pred_file = request.files.get('predictions')

        gt_file = request.files.get('ground_truth')
        if not pred_file or not gt_file:
            return jsonify({'error': 'Both files are required'}), 400

        upload_dir = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        pred_path = os.path.join(upload_dir, secure_filename(pred_file.filename))
        gt_path = os.path.join(upload_dir, secure_filename(gt_file.filename))
        pred_file.save(pred_path)
        gt_file.save(gt_path)

        run_medication_evaluation(pred_path, gt_path)
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.exception("❌ Evaluation upload or run failed")
        return jsonify({'error': str(e)}), 500
    
@bp.route('/upload_multi_evaluation_data', methods=['POST'])
def upload_multi_evaluation_data():
    try:
        pred_files = []
        i=0
        while True:
            pred_file = request.files.get('predictions'+str(i))
            if pred_file:
                pred_files.append(pred_file)
            else: break
            i+=1
        gt_file = request.files.get('ground_truth')
        
        upload_dir = os.path.join(os.getcwd(), 'uploads_multi')
        os.makedirs(upload_dir, exist_ok=True)

        pred_paths = []
        for pred_file in pred_files:
            pred_path = os.path.join(upload_dir, secure_filename(pred_file.filename))
            pred_paths.append(pred_path)
            pred_file.save(pred_path)
        
        gt_path = os.path.join(upload_dir, secure_filename(gt_file.filename))
        gt_file.save(gt_path)

        run_medication_multi_evaluation(pred_paths, gt_path)

        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.exception("❌ Evaluation upload or run failed")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/recist_evaluation', methods=['POST'])
def recist_evaluation():
    """
    Evaluate RECIST predictions vs ground truth and return summary + per-class metrics.
    """
    try:
        import pandas as pd
        from sklearn.metrics import classification_report, confusion_matrix

        pred_file = request.files.get('predictions')
        gt_file = request.files.get('ground_truth')

        if not pred_file or not gt_file:
            return jsonify({'error': 'Both predictions and ground truth files are required'}), 400

        # Save temp
        upload_dir = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        pred_path = os.path.join(upload_dir, secure_filename(pred_file.filename))
        gt_path = os.path.join(upload_dir, secure_filename(gt_file.filename))
        pred_file.save(pred_path)
        gt_file.save(gt_path)

        # Load
        pred_df = pd.read_excel(pred_path) if pred_path.endswith('.xlsx') else pd.read_csv(pred_path)
        gt_df = pd.read_excel(gt_path) if gt_path.endswith('.xlsx') else pd.read_csv(gt_path)

        # Expect columns: id, risposta_recist
        if 'risposta_recist' not in pred_df.columns or 'risposta_recist' not in gt_df.columns:
            return jsonify({'error': 'Missing risposta_recist column in one of the files'}), 400

        y_true = gt_df['risposta_recist'].astype(str).str.upper()
        y_pred = pred_df['risposta_recist'].astype(str).str.upper()

        labels = sorted(set(y_true) | set(y_pred))
        report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
        matrix = confusion_matrix(y_true, y_pred, labels=labels)

        overall = {
            "Accuracy": report["accuracy"],
            "Macro Precision": report["macro avg"]["precision"],
            "Macro Recall": report["macro avg"]["recall"],
            "Macro F1": report["macro avg"]["f1-score"],
        }

        per_class = []
        for lbl in labels:
            if lbl in report:
                per_class.append({
                    "Label": lbl,
                    "Precision": report[lbl]["precision"],
                    "Recall": report[lbl]["recall"],
                    "F1": report[lbl]["f1-score"],
                    "Support": int(report[lbl]["support"]),
                })

        matrix_data = {
            "labels": labels,
            "matrix": matrix.tolist(),
        }

        return jsonify({
            "status": "ok",
            "recist_summary": overall,
            "recist_perclass": per_class,
            "recist_matrix": matrix_data,
        })
    except Exception as e:
        logger.exception("❌ RECIST evaluation failed")
        return jsonify({'error': str(e)}), 500

# -------------------------
# Helpers
# -------------------------
def handle_feature_extraction(extract_func, label):
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file = request.files.get('file')
        raw_text = request.form.get('text', '').strip()
        pdf_filename = None
        features = {}
        if file and file.filename.endswith('.pdf'):
            pdf_filename = secure_filename(file.filename)
            path = os.path.join(upload_dir, pdf_filename)
            file.save(path)
            with open(path, 'rb') as f:
                features = extract_func(f)
            logger.info(f"📄 Processed {label} PDF: {pdf_filename}")
        elif raw_text:
            features = extract_func(raw_text)
            logger.info(f"📝 Processed {label} raw text ({len(raw_text)} chars)")
        else:
            return jsonify({'error': 'Please upload a PDF or enter clinical text.'}), 400
        return jsonify({
            'features': features,
            'pdf_filename': pdf_filename
        })
    except Exception as e:
        logger.exception(f"❌ Error processing {label}")
        return jsonify({'error': str(e)}), 500

def handle_feature_extraction_excel(extract_func, label):
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file = request.files.get('file')
        features = {}
        if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.csv')):
            filename = secure_filename(file.filename)
            path = os.path.join(upload_dir, filename)
            file.save(path)
            with open(path, 'rb') as f:
                if file.filename.endswith('.xlsx'):
                    features = extract_func(f)
                elif file.filename.endswith('.csv'):
                    features = extract_medications_from_csv(f)
            logger.info(f"📄 Processed {label} file: {filename}")
        else:
            return jsonify({'error': 'Please upload an Excel (.xlsx) or CSV (.csv) file.'}), 400
        # get current model from config.json
        model = _load_config().get('LLM_MODEL', 'unknown')
        return jsonify({'features': features, 'pdf_filename': None, 'model': model})
    except Exception as e:
        logger.exception(f"❌ Error processing {label}")
        return jsonify({'error': str(e)}), 500

def handle_timeline_extraction_excel(extract_func, label):
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file = request.files.get('file')
        features = {}
        if file and file.filename.endswith('.xlsx'):
            filename = secure_filename(file.filename)
            path = os.path.join(upload_dir, filename)
            file.save(path)
            with open(path, 'rb') as f:
                features = extract_func(f)
            logger.info(f"📄 Processed {label} Excel: {filename}")
        else:
            return jsonify({'error': 'Please upload an Excel (.xlsx) file for timeline.'}), 400
        return jsonify({'features': features, 'pdf_filename': None})
    except Exception as e:
        logger.exception(f"❌ Error processing {label}")
        return jsonify({'error': str(e)}), 500

@bp.after_request
def add_no_cache_headers(resp):
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

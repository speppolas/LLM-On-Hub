#routes.py
import os
import json
import logging
import subprocess
from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app.api import bp
from app.utils import (
    extract_text_from_pdf,
    clean_expired_files,
    get_all_trials
)
from app.core.ontology_engine.pipeline import evaluate_patient_against_trials
from app.core.feature_extraction import highlight_sources, extract_features_with_llm
from app.core.llm_processor import get_llm_processor
from app import logger 
from app.core.feature_extraction import extract_features_with_llm, extract_text_from_pdf
from app.core.medication_extraction import extract_medications_from_pdf
from app.core.timeline_extraction import extract_timeline_from_pdf


bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)
       
 
@bp.route('/')
def index():
    logger.info("✅ Accessed home page")
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

@bp.route('/api/settings', methods=['GET', 'POST'])
def update_settings():
    if request.method == 'POST':
        data = request.json
        try:
            with open("config.json", "w") as f:
                json.dump(data, f, indent=4)
            logger.info("✅ Settings updated")
            return jsonify({"status": "success", "message": "Settings updated successfully"}), 200
        except Exception as e:
            logger.error(f"❌ Failed to update settings: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    elif request.method == 'GET':
        try:
            with open("config.json", "r") as f:
                settings = json.load(f)
            return jsonify(settings), 200
        except Exception as e:
            logger.error(f"❌ Failed to retrieve settings: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/models')
def get_models():
    try:
        output = subprocess.check_output(['ollama', 'list'], text=True)
        models = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/process', methods=['POST'])
def process():
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        file = request.files.get('file')
        raw_text = request.form.get('text', '').strip()
        text = ''
        pdf_filename = None

        if file and file.filename.endswith('.pdf'):
            pdf_filename = secure_filename(file.filename)
            upload_path = os.path.join(upload_dir, pdf_filename)
            file.save(upload_path)

            with open(upload_path, 'rb') as f:
                text = extract_text_from_pdf(f)

            logger.info(f"📄 PDF '{pdf_filename}' uploaded and text extracted ({len(text)} chars)")

        elif raw_text:
            text = raw_text
            logger.info(f"📝 Raw text received ({len(text)} chars)")

        else:
            logger.warning("❌ No input provided")
            return jsonify({'error': 'Please upload a PDF or enter clinical text.'}), 400

        if not text:
            logger.warning("❌ Extracted text is empty")
            return jsonify({'error': 'Extracted text is empty.'}), 400

        logger.info("🤖 Calling LLM for feature extraction...")
        import time

        t0 = time.perf_counter()
        llm_text = extract_features_with_llm(text)
        feature_extraction_ms = (time.perf_counter() - t0) * 1000

        llm_text = extract_features_with_llm(text)

        if not isinstance(llm_text, dict) or not llm_text:
            logger.error("❌ Invalid or empty response from LLM")
            return jsonify({'error': 'LLM returned an invalid or empty response.'}), 500
        
        logger.info(f"✅ Extracted Features: {json.dumps(llm_text, indent=2)}")
    
        logger.info("🧠 Running neuro-symbolic eligibility engine...")
        logger.debug(f"🔍 DEBUG: Calling match_trials_llm with features: {json.dumps(llm_text, indent=2)}")
        
        out = evaluate_patient_against_trials(llm_text)
        matched_trials = out["results"]
        logger.info(f"✅ Matched Trials: {len(matched_trials)} trials found.")

        timings = out["timings"]

        trial_matching_ms = timings.get("trial_loop", {}).get("mean_ms", None)
        total_screening_ms = (feature_extraction_ms + (trial_matching_ms or 0))
        logger.info(f"⏱ Screening timings: {json.dumps(timings, indent=2)}")

        
        return jsonify({
        "features": llm_text,
        "text": text,
        "pdf_filename": pdf_filename,
        "matched_trials": matched_trials,
        "timings": timings,
        "screening_time": {
        "feature_extraction_ms": round(feature_extraction_ms, 2),
        "trial_matching_ms": trial_matching_ms,
        "total_ms": round(total_screening_ms, 2)
    }
})

    except Exception as e:
        logger.exception("❌ Unhandled exception in /process")
        return jsonify({'error': str(e)}), 500

@bp.route("/match_trials", methods=["POST"])
def match_trials():
    patient_features = request.json
    out = evaluate_patient_against_trials(patient_features)
    return jsonify(out)

@bp.route('/api/trials', methods=['GET'])
def get_trials():
    try:
        trials = get_all_trials()
        return jsonify(trials)
    except Exception as e:
        logger.error(f"❌ Failed to retrieve trials: {e}")
        return jsonify({'error': 'Unable to retrieve trials'}), 500

@bp.route('/trials')
def trials_page():
    return render_template('trials.html')

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

# Clean Expired Files
@bp.route('/api/clean', methods=['POST'])
def clean_files():
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        clean_expired_files(upload_folder)
        logger.info("✅ Expired files cleaned")
        return jsonify({'status': 'success', 'message': 'Expired files cleaned successfully'}), 200
    except Exception as e:
        logger.error(f"❌ Failed to clean files: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@bp.route('/process_medications', methods=['POST'])
def process_medications():
    return handle_feature_extraction(extract_func=extract_medications_from_pdf, label="medications")


@bp.route('/process_timeline', methods=['POST'])
def process_timeline():
    return handle_feature_extraction(extract_func=extract_timeline_from_pdf, label="timeline")


def handle_feature_extraction(extract_func, label):
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        file = request.files.get('file')
        raw_text = request.form.get('text', '').strip()
        pdf_filename = None
        text = ''
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
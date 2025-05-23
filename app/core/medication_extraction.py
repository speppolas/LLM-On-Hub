import os
import json
import time
import logging
from typing import Union
from app import logger
from app.core.llm_processor import get_llm_processor
from app.core.feature_extraction import extract_text_from_pdf

# Ensure the logs folder exists
os.makedirs("logs", exist_ok=True)

def extract_medications_from_pdf(pdf_file: Union[str, bytes]):
    try:
        text = extract_text_from_pdf(pdf_file)
        return extract_medications(text)
    except Exception as e:
        logger.error(f"❌ Error reading PDF for medication extraction: {str(e)}")
        return {}

def extract_medications(text: str):
    llm = get_llm_processor()

    prompt = f"""You are a medical assistant. Extract medications with dosage, frequency, and indication. Output JSON format ONLY:

[
  {{
    "medication": "Name",
    "dosage": "e.g., 10 mg",
    "frequency": "e.g., twice daily",
    "indication": "Reason prescribed"
  }},
  ...
]

Text:
{text}
"""
    logger.info(f"Prompt sent to LLM (medication):\n{prompt[:2000]}")

    try:
        response = llm.generate_response(prompt)
        logger.info(f"🧠 LLM Medication Response: {response[:1000]}")

        filename = f"logs/llm_medication_debug_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump({"prompt": prompt, "response": response}, f, indent=2)

        resp_json = json.loads(response)
        llm_text = json.loads(resp_json['response']) if isinstance(resp_json['response'], str) else resp_json['response']

        if not isinstance(llm_text, list):
            logger.error(f"❌ LLM medication output is not a list: {llm_text}")
            return []

        logger.info(f"✅ Extracted Medication Features: {json.dumps(llm_text, indent=2)}")
        return llm_text

    except Exception as e:
        logger.exception("❌ Medication LLM parsing failed")
        return []

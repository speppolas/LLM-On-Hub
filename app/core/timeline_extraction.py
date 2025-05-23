import os
import json
import time
import re
import logging
from typing import Union
from app import logger
from app.core.llm_processor import get_llm_processor
from app.core.feature_extraction import extract_text_from_pdf

# Ensure the logs folder exists
os.makedirs("logs", exist_ok=True)

def extract_timeline_from_pdf(pdf_file: Union[str, bytes]):
    try:
        text = extract_text_from_pdf(pdf_file)
        return extract_timeline(text)
    except Exception as e:
        logger.error(f"❌ Error reading PDF for timeline extraction: {str(e)}")
        return {}

def extract_timeline(text: str):
    llm = get_llm_processor()

    prompt = f"""You are a medical assistant. Extract a timeline of clinical events. Output ONLY a JSON array like:

[
  {{
    "date": "YYYY-MM-DD" or null,
    "event": "Short description",
    "details": "Optional long description"
  }},
  ...
]

Text:
{text}
"""

    logger.info(f"Prompt sent to LLM (timeline):\n{prompt[:2000]}")

    try:
        response = llm.generate_response(prompt)
        logger.info(f"🧠 LLM Timeline Response: {response[:1000]}")

        filename = f"logs/llm_timeline_debug_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump({"prompt": prompt, "response": response}, f, indent=2)

        resp_json = json.loads(response)
        raw = resp_json.get("response", "")
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)

        if not json_match:
            logger.error("❌ No JSON array found in timeline LLM response.")
            return []

        json_text = json_match.group(0)
        llm_text = json.loads(json_text)


        if not isinstance(llm_text, list):
            logger.error(f"❌ LLM timeline output is not a list: {llm_text}")
            return []

        logger.info(f"✅ Extracted Timeline Features: {json.dumps(llm_text, indent=2)}")
        return llm_text

    except Exception as e:
        logger.exception("❌ Timeline LLM parsing failed")
        return []

import os
import logging
import requests
import json
import sys

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("record.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    """
    Load the SAME config.json that the frontend modifies.
    Located at: app/routes/config.json

    If it fails, fall back to the backend’s built-in defaults
    (LLAMA 3.1 8B + 131k context or whatever defaults you prefer).
    """
    import os
    import json

    # llm_processor.py is inside app/core/, so go up to app/ and into api/
    base_dir = os.path.dirname(os.path.dirname(__file__))  # -> app/
    config_path = os.path.join(base_dir, "api", "config.json")

    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"✅ Loaded config from {config_path}")
                return config
        else:
            logger.warning(f"⚠️ Config file missing: {config_path}")

    except Exception as e:
        logger.error(f"❌ Error loading config file: {e}")

    # -----------------------------
    # FALLBACK: USE DEFAULTS HERE
    # -----------------------------
    logger.warning("⚠️ Using backend default LLM settings.")
    return {
        "LLM_MODEL": "llama3.1:8b",        # 🔥 your current default
        "LLM_CONTEXT_SIZE": 131072,        # 🔥 your current default
        "LLM_TEMPERATURE": 0.0,
        "TRIAL_MATCHING_BATCH_SIZE": 4,
        "LLM_JSON_MODE": True
    }

class LLMProcessor:
    def __init__(self):
        config = load_config()
        self.api_url = os.getenv("OLLAMA_SERVER_URL", "http://127.0.0.1:11434/api/generate")
        self.model = config.get("LLM_MODEL")
        self.context_size = config.get("LLM_CONTEXT_SIZE")
        self.temperature = config.get("LLM_TEMPERATURE")
        self.max_tokens = min(self.context_size - 512, self.context_size // 2)

    def generate_response(self, prompt: str, temperature: float = None, max_tokens: int = None) -> str:
        # 🔥 Reload config EVERY TIME
        cfg = load_config()
        self.model = cfg.get("LLM_MODEL", self.model)
        self.context_size = cfg.get("LLM_CONTEXT_SIZE", self.context_size)
        self.temperature = cfg.get("LLM_TEMPERATURE", self.temperature)
        self.max_tokens = min(self.context_size - 512, self.context_size // 2)

        print(f"[LLM] Using model={self.model}, ctx={self.context_size}, temp={self.temperature}")

        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        # -------------------------------------------------------
        # 🔍 DEBUG: PRINT THE FULL PROMPT SENT TO THE MODEL
        # -------------------------------------------------------
        print("\n================ PROMPT SENT TO MODEL ================")
        print(prompt)
        print("================ END PROMPT ==========================\n")

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "num_ctx": self.context_size,
                "max_tokens": max_tokens,
                "stream": False
            }

            # print(f"Sending request to Ollama API with payload: {payload}")
            response = requests.post(self.api_url, json=payload)
            print(f"Ollama API response status: {response.status_code}")
            if response.status_code == 200:
                # print(f"Ollama API response body (truncated): {response.text[:500]}")
                return response.text
            else:
                logger.error(f"Non-200 response from Ollama API: {response.status_code} - {response.text}")
                return ""
        except Exception as e:
            print('Exception:', e)
            logger.error(f"Error contacting Ollama API: {e}")
            return ""


def get_llm_processor():
    return LLMProcessor()

class LLMProcessorTM:
    def __init__(self):
        config = load_config()
        self.api_url = os.getenv("OLLAMA_SERVER_URL", "http://127.0.0.1:11434/api/generate")
        self.model = config.get("LLM_MODEL", "gemma3:27b")
        self.context_size = int(config.get("LLM_CONTEXT_SIZE", 8192))
        self.temperature = float(config.get("LLM_TEMPERATURE", 0.1))
        self.max_tokens = max(256, min(self.context_size - 512, self.context_size // 2))
        
        logger.info(f"LLM Processor initialized - Model: {self.model}, Context: {self.context_size}")

    def test_connectionTM(self):
        """Test connection to Ollama server"""
        try:
            test_url = self.api_url.replace("/api/generate", "/api/tags")
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                logger.info("✅ Ollama server connection OK")
                return True
            else:
                logger.error(f"❌ Ollama server responded with status: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to Ollama server: {e}")
            return False

# --- PATCH in llm_processor.py ---  (sostituisci il metodo generate_responseTM esistente)
    def generate_responseTM(
        self,
        prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False,
        timeout: int = 600,
        grammar: str = None,           # 👈 nuovo
    ) -> str:
        if not prompt or not prompt.strip():
            logger.error("Empty prompt provided")
            return ""

        temp = self.temperature if temperature is None else float(temperature)
        num_predict = self.max_tokens if max_tokens is None else int(max_tokens)

        # 🔥 Reload config before each inference
        cfg = load_config()
        self.model = cfg.get("LLM_MODEL", self.model)
        self.context_size = int(cfg.get("LLM_CONTEXT_SIZE", self.context_size))
        self.temperature = float(cfg.get("LLM_TEMPERATURE", self.temperature))
        self.max_tokens = max(256, min(self.context_size - 512, self.context_size // 2))

        print(f"[LLM-TM] Using model={self.model}, ctx={self.context_size}, temp={self.temperature}")


        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temp,
            "num_ctx": int(self.context_size),
            "num_predict": int(num_predict),
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        if grammar:
            payload["grammar"] = grammar  # 👈 invio grammatica GBNF a Ollama

        try:
            logger.info(f"Ollama request → model={self.model}, temp={temp}, num_ctx={self.context_size}, num_predict={num_predict}, json={json_mode}, grammar={'yes' if grammar else 'no'}")
            r = requests.post(self.api_url, json=payload, timeout=timeout)
            logger.info(f"Ollama status: {r.status_code}")
            if r.status_code == 200:
                response_data = r.json()
                if "response" in response_data:
                    return response_data["response"]
                else:
                    logger.warning("No 'response' field in Ollama output")
                    return str(response_data)
            else:
                logger.error(f"Non-200 from Ollama: {r.status_code} - {r.text[:600]}")
                return ""
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {timeout}s")
            return ""
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama server - is it running?")
            return ""
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from Ollama: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error contacting Ollama API: {e}")
            return ""


def get_llm_processorTM():
    """Factory function to get LLM processor instance"""
    processor = LLMProcessorTM()
    if not processor.test_connectionTM():
        logger.warning("⚠️ LLM processor created but connection test failed")
    return processor

class GemmaLLMProcessor(LLMProcessor):
    def __init__(self):
        super().__init__()
        self.model = "gemma3:27b"  # Gemma-specific model
        logger.info("GemmaLLMProcessor initialized")
    def generate_response(self, prompt: str, temperature: float=None, max_tokens: int=None, json_mode: bool=False, timeout: int=600) -> str:
        num_predict = self.max_tokens if max_tokens is None else int(max_tokens)
        # Replica la logica base ma aggiunge il supporto a format=json
        payload = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "num_ctx": self.context_size,
                "num_predict": num_predict,
                "stream": False
            }
        if json_mode:
            payload["format"] = "json"
        r = requests.post(self.api_url, json=payload, timeout=timeout)
        return r.text if r.status_code == 200 else ""

def get_explainer_llm():
    """Factory function to get Gemma-specific LLM processor"""
    return GemmaLLMProcessor()
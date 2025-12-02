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
    """Load configuration with better error handling"""
    try:
        if not os.path.exists("config.json"):
            logger.warning("Config file not found, creating default")
            default_config = {
                "LLM_MODEL": "gemma3:27b",
                "LLM_CONTEXT_SIZE": 8192,
                "LLM_TEMPERATURE": 0.1,
                "TRIAL_MATCHING_BATCH_SIZE": 4,
                "LLM_JSON_MODE": True  # Added missing field
            }
            with open("config.json", "w") as f:
                json.dump(default_config, f, indent=4)
            return default_config
            
        with open("config.json", "r") as f:
            config = json.load(f)
            logger.info("✅ Config loaded successfully")
            return config
            
    except Exception as e:
        logger.error(f"❌ Unable to load config file: {e}")
        # Emergency defaults
        return {
            "LLM_MODEL": "gemma3:27b",
            "LLM_CONTEXT_SIZE": 8192,
            "LLM_TEMPERATURE": 0.1,
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
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
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
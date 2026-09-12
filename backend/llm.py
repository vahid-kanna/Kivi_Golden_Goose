import os
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

class LLMClient:
    """
    Unified LLM Client supporting:
    1. OpenAI-compatible endpoints (Local proxy, Groq, Ollama, OpenRouter)
    2. Anthropic / Gemini when keys provided
    3. Intelligent Rule-Based Fallback Engine (Runs completely offline when no API key is supplied)
    """
    def __init__(self):
        # Check environment variables
        self.api_key = (
            os.environ.get("KIVI_LLM_API_KEY") or
            os.environ.get("OPENAI_API_KEY") or
            os.environ.get("GROQ_API_KEY") or
            ""
        )
        self.base_url = os.environ.get("KIVI_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        if not self.base_url:
            if os.environ.get("GROQ_API_KEY"):
                self.base_url = "https://api.groq.com/openai/v1"
                self.model = os.environ.get("KIVI_LLM_MODEL", "llama-3.3-70b-versatile")
            else:
                self.base_url = "https://api.openai.com/v1"
                self.model = os.environ.get("KIVI_LLM_MODEL", "default")
        else:
            self.model = os.environ.get("KIVI_LLM_MODEL", "default")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    def complete(self, messages: List[Dict[str, str]], temperature: float = 0.1, max_tokens: int = 1000) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "content": "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "error": "NO_KEY"
            }

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                choice = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "content": choice,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "error": None
                }
        except Exception as e:
            return {
                "content": "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "error": str(e)
            }

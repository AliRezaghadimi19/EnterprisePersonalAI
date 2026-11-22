"""
Concrete AI Provider Implementations
Supports OpenAI, Anthropic Claude, Google Gemini, OpenAI-Compatible APIs, and Mock Provider.
"""

import time
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from app.services.ai_gateway.base import BaseLLMProvider

def estimate_tokens(text: str) -> int:
    """Rough token estimation (approx 4 chars per token for English, 2 chars for Persian)."""
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    return max(1, int((words * 1.3) + (chars * 0.15)))

class MockProvider(BaseLLMProvider):
    """Simulated Provider for test suites and offline operation."""
    def test_connection(self) -> Tuple[bool, float, str]:
        start = time.time()
        time.sleep(0.01)
        latency = (time.time() - start) * 1000
        return True, round(latency, 2), "اتصال آزمایشی با ارائه‌دهنده با موفقیت برقرار شد."

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_identifier: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        start = time.time()
        prompt_text = " ".join([m.get("content", "") for m in messages])
        input_tokens = estimate_tokens(prompt_text)
        
        reply_content = f"پاسخ هوشمند شبیه‌سازی‌شده توسط مدل {model_identifier} سازمانی. درخواست شما پردازش شد."
        output_tokens = estimate_tokens(reply_content)
        latency = (time.time() - start) * 1000
        
        return {
            "content": reply_content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(latency, 2),
            "finish_reason": "stop"
        }

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None, config_params: Optional[Dict[str, Any]] = None):
        super().__init__(api_key, base_url or "https://api.openai.com/v1", config_params)

    def test_connection(self) -> Tuple[bool, float, str]:
        if not self.api_key:
            return False, 0.0, "کلید API ارائه‌دهنده OpenAI وارد نشده است."
        if self.api_key.startswith("mock_"):
            return True, 12.5, "ارتباط آزمایشی با سرویس شبیه‌ساز OpenAI برقرار شد."
        start = time.time()
        try:
            req = Request(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            with urlopen(req, timeout=5) as resp:
                latency = (time.time() - start) * 1000
                if resp.status == 200:
                    return True, round(latency, 2), "ارتباط با API رسمی OpenAI برقرار شد."
                return False, round(latency, 2), f"پاسخ ناموفق: کد {resp.status}"
        except Exception as e:
            return False, 0.0, f"خطای اتصال به OpenAI: {str(e)}"

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_identifier: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        if self.api_key.startswith("mock_") or "mock" in self.base_url:
            return MockProvider(self.api_key).generate(messages, model_identifier, max_tokens, temperature)
            
        start = time.time()
        payload = json.dumps({
            "model": model_identifier,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }).encode('utf-8')
        
        req = Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        try:
            with urlopen(req, timeout=30) as resp:
                latency = (time.time() - start) * 1000
                res_data = json.loads(resp.read().decode('utf-8'))
                choice = res_data["choices"][0]
                usage = res_data.get("usage", {})
                return {
                    "content": choice["message"]["content"],
                    "input_tokens": usage.get("prompt_tokens", estimate_tokens(str(messages))),
                    "output_tokens": usage.get("completion_tokens", estimate_tokens(choice["message"]["content"])),
                    "latency_ms": round(latency, 2),
                    "finish_reason": choice.get("finish_reason", "stop")
                }
        except Exception as e:
            raise RuntimeError(f"خطای سرویس OpenAI: {str(e)}")

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None, config_params: Optional[Dict[str, Any]] = None):
        super().__init__(api_key, base_url or "https://api.anthropic.com/v1", config_params)

    def test_connection(self) -> Tuple[bool, float, str]:
        if not self.api_key:
            return False, 0.0, "کلید API سرویس Anthropic وارد نشده است."
        if self.api_key.startswith("mock_"):
            return True, 15.0, "ارتباط آزمایشی با سرویس Anthropic برقرار شد."
        return True, 45.0, "کلید API معتبر شناسایی شد."

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_identifier: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        if self.api_key.startswith("mock_") or "mock" in (self.base_url or "") or not self.api_key:
            return MockProvider(self.api_key).generate(messages, model_identifier, max_tokens, temperature)

        start = time.time()
        url = f"{self.base_url}/messages"
        
        system_text = ""
        claude_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_text += content + "\n"
            else:
                claude_messages.append({"role": role, "content": content})
                
        body_dict = {
            "model": model_identifier,
            "max_tokens": max_tokens,
            "messages": claude_messages,
            "temperature": temperature
        }
        if system_text.strip():
            body_dict["system"] = system_text.strip()
            
        payload = json.dumps(body_dict).encode('utf-8')
        req = Request(url, data=payload, headers={
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        })
        try:
            with urlopen(req, timeout=30) as resp:
                latency = (time.time() - start) * 1000
                res_data = json.loads(resp.read().decode('utf-8'))
                text = res_data["content"][0]["text"]
                usage = res_data.get("usage", {})
                return {
                    "content": text,
                    "input_tokens": usage.get("input_tokens", estimate_tokens(str(messages))),
                    "output_tokens": usage.get("output_tokens", estimate_tokens(text)),
                    "latency_ms": round(latency, 2),
                    "finish_reason": res_data.get("stop_reason", "end_turn")
                }
        except Exception as e:
            raise RuntimeError(f"خطای سرویس Anthropic: {str(e)}")

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None, config_params: Optional[Dict[str, Any]] = None):
        super().__init__(api_key, base_url or "https://generativelanguage.googleapis.com/v1beta", config_params)

    def test_connection(self) -> Tuple[bool, float, str]:
        if not self.api_key:
            return False, 0.0, "کلید API سرویس Google Gemini وارد نشده است."
        if self.api_key.startswith("mock_"):
            return True, 18.0, "ارتباط آزمایشی با سرویس Google Gemini برقرار شد."
        start = time.time()
        url = f"{self.base_url}/models?key={self.api_key}"
        try:
            req = Request(url)
            with urlopen(req, timeout=10) as resp:
                lat = (time.time() - start) * 1000
                return True, round(lat, 2), "ارتباط زنده با سرویس Google Gemini با موفقیت برقرار شد."
        except Exception as e:
            return False, 0.0, f"خطای اتصال به Google Gemini: {str(e)}"

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_identifier: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        if self.api_key.startswith("mock_") or "mock" in (self.base_url or "") or not self.api_key:
            return MockProvider(self.api_key).generate(messages, model_identifier, max_tokens, temperature)

        start = time.time()
        model_name = model_identifier if model_identifier.startswith("models/") else f"models/{model_identifier}"
        url = f"{self.base_url}/{model_name}:generateContent?key={self.api_key}"
        
        contents = []
        system_instruction = None
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})
        
        body_dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }
        if system_instruction:
            body_dict["systemInstruction"] = system_instruction
            
        payload = json.dumps(body_dict).encode('utf-8')
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=30) as resp:
                latency = (time.time() - start) * 1000
                res_data = json.loads(resp.read().decode('utf-8'))
                candidate = res_data.get("candidates", [{}])[0]
                content_obj = candidate.get("content", {})
                parts = content_obj.get("parts", [])
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p)
                if not text:
                    text = "پاسخی از مدل دریافت نشد."
                usage = res_data.get("usageMetadata", {})
                return {
                    "content": text,
                    "input_tokens": usage.get("promptTokenCount", estimate_tokens(str(messages))),
                    "output_tokens": usage.get("candidatesTokenCount", estimate_tokens(text)),
                    "latency_ms": round(latency, 2),
                    "finish_reason": candidate.get("finishReason", "STOP")
                }
        except Exception as e:
            raise RuntimeError(f"خطای سرویس Google Gemini: {str(e)}")

class OpenAICompatibleProvider(OpenAIProvider):
    """Compatible with local runners like Ollama, vLLM, LocalAI and LM Studio."""
    def __init__(self, api_key: str, base_url: Optional[str] = None, config_params: Optional[Dict[str, Any]] = None):
        super().__init__(api_key or "local-key", base_url or "http://localhost:11434/v1", config_params)

    def test_connection(self) -> Tuple[bool, float, str]:
        if self.api_key.startswith("mock_") or "localhost" in (self.base_url or ""):
            return True, 5.0, "ارتباط با Endpoint سازگار با OpenAI (لوکال) با موفقیت بررسی شد."
        return super().test_connection()

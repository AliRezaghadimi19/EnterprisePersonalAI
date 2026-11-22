"""
AI Gateway - Base Provider Interface
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

class BaseLLMProvider(ABC):
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        config_params: Optional[Dict[str, Any]] = None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.config_params = config_params or {}

    @abstractmethod
    def test_connection(self) -> Tuple[bool, float, str]:
        """
        Test reachability and authentication with the provider.
        Returns: (success: bool, latency_ms: float, message_fa: str)
        """
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model_identifier: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Execute completion request.
        Returns dict containing:
        {
            "content": str,
            "input_tokens": int,
            "output_tokens": int,
            "latency_ms": float,
            "finish_reason": str
        }
        """
        pass

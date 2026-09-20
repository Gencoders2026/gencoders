"""
LLM client wrapper for the Customer Simulator Agent.

Uses the OpenAI SDK in an OpenAI-compatible way so it works with
OpenAI, Groq, or any compatible endpoint. If no key is configured
or the call fails, the caller falls back to rule-based generation.
"""

from typing import List, Dict, Optional

try:  # package-relative import
    from .config import (
        OPENAI_API_KEY,
        LLM_BASE_URL,
        LLM_MODEL,
        LLM_TEMPERATURE,
        MAX_TOKENS,
        USE_LLM,
    )
except ImportError:  # flat import when run directly
    from config import (
        OPENAI_API_KEY,
        LLM_BASE_URL,
        LLM_MODEL,
        LLM_TEMPERATURE,
        MAX_TOKENS,
        USE_LLM,
    )


class LLMClient:
    """Thin wrapper around an OpenAI-compatible chat completion API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        self.api_key = api_key if api_key is not None else OPENAI_API_KEY
        self.base_url = base_url if base_url is not None else LLM_BASE_URL
        self.model = model or LLM_MODEL
        self.temperature = (
            LLM_TEMPERATURE if temperature is None else temperature
        )
        self.max_tokens = MAX_TOKENS if max_tokens is None else max_tokens

        if enabled is None:
            enabled = USE_LLM

        self.enabled = bool(enabled and self.api_key)
        self._client = None

        if self.enabled:
            self._init_client()

    # --------------------------------------------------------
    # INIT
    # --------------------------------------------------------

    def _init_client(self):
        try:
            from openai import OpenAI

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url

            self._client = OpenAI(**kwargs)

        except Exception:
            self._client = None
            self.enabled = False

    # --------------------------------------------------------
    # AVAILABILITY
    # --------------------------------------------------------

    def is_available(self) -> bool:
        return self.enabled and self._client is not None

    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        """
        Generate a completion.

        `messages` is a list of {"role": "user"/"assistant", "content": str}.
        Returns the assistant text, or None if unavailable / failed.
        """

        if not self.is_available():
            return None

        try:
            payload = [{"role": "system", "content": system_prompt}]
            payload.extend(messages)

            response = self._client.chat.completions.create(
                model=self.model,
                messages=payload,
                temperature=(
                    self.temperature if temperature is None else temperature
                ),
                max_tokens=self.max_tokens,
            )

            text = response.choices[0].message.content
            if text:
                return text.strip()

            return None

        except Exception:
            return None
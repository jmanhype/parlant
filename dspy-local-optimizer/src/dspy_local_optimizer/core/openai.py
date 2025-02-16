"""Module for OpenAI model integration."""

import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAILanguageModel:
    """Language model implementation for OpenAI."""
    
    def __init__(self, api_key: str) -> None:
        """Initialize the OpenAI language model.
        
        Args:
            api_key: OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
        self._history: List[Dict[str, str]] = []
        
    def __call__(self, prompt: str) -> str:
        """Generate a response for the given prompt.
        
        Args:
            prompt: The input prompt
            
        Returns:
            str: The generated response
        """
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        result = response.choices[0].message.content
        self._history.append({"prompt": prompt, "response": result})
        return result
        
    def inspect_history(self, n: int = 1) -> List[Dict[str, str]]:
        """Get the last n interactions.
        
        Args:
            n: Number of interactions to return
            
        Returns:
            List of prompt-response pairs
        """
        return self._history[-n:]

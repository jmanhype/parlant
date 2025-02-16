"""Module for Ollama model initialization and management."""

import logging
import subprocess
import time
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

import requests


class OllamaLanguageModel:
    """Language model implementation for Ollama."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Ollama language model.
        
        Args:
            api_key: Not used for Ollama but kept for consistency
        """
        self.base_url = "http://localhost:11434/api"
        self._history = []

    def __call__(self, prompt: str) -> str:
        """Generate a response for the given prompt.
        
        Args:
            prompt: The input prompt
            
        Returns:
            str: The generated response
        """
        response = requests.post(
            f"{self.base_url}/generate",
            json={"model": "llama2", "prompt": prompt}
        )
        response.raise_for_status()
        result = response.json()["response"]
        self._history.append((prompt, result))
        return result
        
    def inspect_history(self, n: int = 1) -> List[Dict[str, str]]:
        """Get the last n interactions.
        
        Args:
            n: Number of interactions to return
            
        Returns:
            List of prompt-response pairs
        """
        return [{"prompt": p, "response": r} for p, r in self._history[-n:]]


def initialize_ollama_model(model_name: str, max_retries: int = 3) -> None:
    """Initialize and ensure Ollama model is ready.
    
    Args:
        model_name: Name of the Ollama model to initialize
        max_retries: Maximum number of retry attempts for model pull
        
    Raises:
        RuntimeError: If Ollama server cannot be started or model cannot be pulled
    """
    # Check if Ollama server is running
    try:
        result = subprocess.run(['pgrep', 'ollama'], capture_output=True)
        if result.returncode != 0:
            logger.info("Starting Ollama server...")
            subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(2)  # Wait for server startup
    except Exception as e:
        raise RuntimeError(f"Failed to start Ollama server: {str(e)}")
        
    # Pull model with retries
    for attempt in range(max_retries):
        try:
            logger.info(f"Pulling Ollama model {model_name}, attempt {attempt + 1}/{max_retries}")
            subprocess.run(['ollama', 'pull', model_name], check=True)
            return
        except subprocess.CalledProcessError as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to pull Ollama model {model_name}: {str(e)}")
            time.sleep(2 ** attempt)  # Exponential backoff

"""DSPy integration for optimizing guidelines."""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from dataclasses import dataclass

import dspy
from dspy import ChainOfThought, Example, LM, Module, Signature
from dspy.teleprompt import COPRO

from parlant.core.guidelines import Guideline, GuidelineContent
from parlant.core.metrics import ModelMetrics
from parlant.core.ollama import initialize_ollama_model

logger = logging.getLogger(__name__)

@dataclass
class OptimizationBatch:
    """A batch of guidelines to optimize together."""
    guidelines: List[Guideline]
    examples: List[Example]
    batch_size: int = 10
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def latency(self) -> Optional[float]:
        """Calculate batch processing latency in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class MetricsLogger:
    """Wrapper around language model to track metrics."""
    
    def __init__(self, lm: LM, metrics: ModelMetrics):
        """Initialize the metrics logger.
        
        Args:
            lm: Language model to wrap
            metrics: Metrics tracker
        """
        self.lm = lm
        self.metrics = metrics
        
    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to wrapped language model.
        
        Args:
            name: Name of attribute to access
            
        Returns:
            Attribute value
        """
        # Get the attribute from the wrapped LM
        attr = getattr(self.lm, name)
        
        # If it's a method, wrap it to track metrics
        if callable(attr):
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self.metrics.total_api_calls += 1
                result = attr(*args, **kwargs)
                logger.info(f"Response format: {type(result)}")
                logger.info(f"Response content: {result}")
                if hasattr(result, 'usage') and hasattr(result.usage, 'total_tokens'):
                    self.metrics.total_tokens += result.usage.total_tokens
                elif hasattr(result, 'usage') and isinstance(result.usage, dict) and 'total_tokens' in result.usage:
                    self.metrics.total_tokens += result.usage['total_tokens']
                elif isinstance(result, list) and result and isinstance(result[0], dict) and 'usage' in result[0]:
                    for r in result:
                        if 'usage' in r and 'total_tokens' in r['usage']:
                            self.metrics.total_tokens += r['usage']['total_tokens']
                elif isinstance(result, dict) and 'usage' in result and 'total_tokens' in result['usage']:
                    self.metrics.total_tokens += result['usage']['total_tokens']
                elif isinstance(result, list) and result and isinstance(result[0], str):
                    # For DSPy responses that are lists of strings, estimate tokens
                    for r in result:
                        # Rough estimate: 1 token per 4 characters
                        self.metrics.total_tokens += len(r) // 4
                return result
            return wrapper
        return attr
        
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Handle direct calls to the language model.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Model output
        """
        self.metrics.total_api_calls += 1
        result = self.lm(*args, **kwargs)
        logger.info(f"Response format: {type(result)}")
        logger.info(f"Response content: {result}")
        if hasattr(result, 'usage') and hasattr(result.usage, 'total_tokens'):
            self.metrics.total_tokens += result.usage.total_tokens
        elif hasattr(result, 'usage') and isinstance(result.usage, dict) and 'total_tokens' in result.usage:
            self.metrics.total_tokens += result.usage['total_tokens']
        elif isinstance(result, list) and result and isinstance(result[0], dict) and 'usage' in result[0]:
            for r in result:
                if 'usage' in r and 'total_tokens' in r['usage']:
                    self.metrics.total_tokens += r['usage']['total_tokens']
        elif isinstance(result, dict) and 'usage' in result and 'total_tokens' in result['usage']:
            self.metrics.total_tokens += result['usage']['total_tokens']
        elif isinstance(result, list) and result and isinstance(result[0], str):
            # For DSPy responses that are lists of strings, estimate tokens
            for r in result:
                # Rough estimate: 1 token per 4 characters
                self.metrics.total_tokens += len(r) // 4
        return result


class GuidelineProgram(Module):
    """DSPy program for optimizing guidelines."""
    
    def __init__(self, api_key: str, model_name: str = "openai/gpt-3.5-turbo", use_optimizer: bool = True, metrics: Optional[ModelMetrics] = None):
        """Initialize the program with a signature.
        
        Args:
            api_key: API key for the model provider
            model_name: Name of the model to use (e.g., "openai/gpt-3.5-turbo", "ollama/llama2")
            use_optimizer: Whether to use DSPy's COPRO optimizer
            metrics: Optional metrics tracker for monitoring performance
        """
        super().__init__()
        
        # Define signature with instructions
        self.input_keys = ["condition"]
        self.output_keys = ["action"]
        
        # Initialize Ollama if needed
        if "ollama" in model_name:
            ollama_model = model_name.split("/")[1]
            initialize_ollama_model(ollama_model)
        
        # Configure the language model
        self.lm = LM(model_name, api_key=api_key, temperature=0.7, max_tokens=200)
        if metrics:
            self.lm = MetricsLogger(self.lm, metrics)
        dspy.configure(lm=self.lm)
        
        # Configure optimizer if needed
        if use_optimizer:
            self.optimizer = COPRO(
                prompt_model=self.lm,
                init_temperature=0.7,
                breadth=3,  # Number of candidates to generate
                depth=1     # Number of iterations
            )
            # Will be compiled later with actual training data
            
    def forward(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate a response for a given condition.
        
        Args:
            **kwargs: Keyword arguments containing the condition
            
        Returns:
            Dictionary with the generated response
        """
        condition = kwargs["condition"]
        prompt = """Given a customer service scenario, generate a clear and effective response.
        Follow these guidelines:
        1. Be professional and courteous - use phrases like "please", "thank you", "assist", "help", or "understand"
        2. Address the specific concern directly and explicitly
        3. Provide actionable information and specific details, including numbers or prices where relevant
        4. Keep responses between 20 and 200 characters
        5. Use relevant terminology (e.g., 'pricing tiers', 'technical specifications', 'error messages')
        6. For pricing questions, always mention specific tiers and prices:
           - Basic: $10/month (includes basic features)
           - Pro: $25/month (includes advanced features)
           - Enterprise: Custom pricing (includes all features + dedicated support)
        7. For technical issues, ask for specific details about the problem
        8. Never include error messages, debugging info, or technical traces in responses
        
        Example response: "Thank you for your interest in our pricing. Our Basic tier is $10/month with essential features, while our Pro tier at $25/month includes advanced capabilities. I'd be happy to explain the specific features included in each tier."
        
        Customer scenario: {condition}
        
        Response: """
        
        response = self.lm(prompt.format(condition=condition))
        if isinstance(response, list):
            response = response[0] if response else ""
        elif isinstance(response, dict):
            response = response.get("text", "")
        elif not isinstance(response, str):
            response = str(response)
            
        return {"action": response}


class BatchOptimizedGuidelineManager:
    """Manager for optimizing guidelines in batches."""
    
    def __init__(self, api_key: str, model_name: str = "openai/gpt-3.5-turbo", use_optimizer: bool = True):
        """Initialize the manager.
        
        Args:
            api_key: API key for the model provider
            model_name: Name of the model to use (e.g., "openai/gpt-3.5-turbo", "ollama/llama2")
            use_optimizer: Whether to use DSPy's COPRO optimizer
        """
        self.metrics = ModelMetrics()
        self.program = GuidelineProgram(api_key=api_key, model_name=model_name, use_optimizer=use_optimizer, metrics=self.metrics)
        
    def optimize_guidelines(
            self, 
            guidelines: Sequence[Guideline],
            examples: List[Dict[str, str]],
            batch_size: int = 10
        ) -> List[Guideline]:
        """Optimize guidelines using DSPy's COPRO optimizer.
        
        Args:
            guidelines: List of guidelines to optimize
            examples: List of example dictionaries for training
            batch_size: Size of batches for optimization
            
        Returns:
            List of optimized guidelines
        """
        logger.info(f"Starting optimization of {len(guidelines)} guidelines")
        start_time = time.time()
        
        # Convert examples to DSPy format
        dspy_examples = [
            Example(condition=ex["input"], action=ex["output"])
            for ex in examples
        ]
        
        # Compile the program with examples if using optimizer
        if hasattr(self.program, "optimizer"):
            try:
                self.program.optimizer.compile(
                    self.program,
                    trainset=dspy_examples,
                    max_iterations=3,
                    verbose=True
                )
            except Exception as e:
                logger.error(f"Failed to compile optimizer: {e}")
                # Fall back to unoptimized program
                
        optimized_guidelines = []
        
        # Process guidelines in batches
        for i in range(0, len(guidelines), batch_size):
            batch = guidelines[i:i + batch_size]
            
            # Process each guideline in the batch
            for guideline in batch:
                try:
                    # Generate response
                    result = self.program(condition=guideline.content.condition)
                    response = result.get("action", "")
                    
                    # Create new optimized guideline
                    optimized_guideline = Guideline(
                        id=guideline.id,
                        creation_utc=guideline.creation_utc,
                        content=GuidelineContent(
                            condition=guideline.content.condition,
                            action=response
                        )
                    )
                    optimized_guidelines.append(optimized_guideline)
                    
                except Exception as e:
                    logger.error(f"Failed to optimize guideline {guideline.id}: {e}")
                    # Keep original guideline on error
                    optimized_guidelines.append(guideline)
        
        self.metrics.total_time = time.time() - start_time
        return optimized_guidelines

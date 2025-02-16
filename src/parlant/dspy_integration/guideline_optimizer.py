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


class GuidelineProgram(dspy.Module):
    """A DSPy program for generating and optimizing customer service responses.
    
    This program uses a language model to generate professional and effective
    customer service responses based on given conditions. It can be optionally
    optimized using DSPy's COPRO optimizer.
    
    Attributes:
        condition: Input field for the customer service condition
        response: Output field for the generated response
        lm: Language model instance for generating responses
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "openai/gpt-3.5-turbo", metrics: Optional[ModelMetrics] = None) -> None:
        """Initialize the program with a language model.
        
        Args:
            api_key: Optional API key for the model provider. If not provided, uses the configured LM.
            model_name: Name of the model to use (e.g., "openai/gpt-3.5-turbo", "ollama/llama2")
            metrics: Optional metrics tracker for monitoring performance
        """
        super().__init__()
        
        # Define input/output fields
        self.condition = dspy.InputField(desc="The customer service condition/scenario to respond to")
        self.response = dspy.OutputField(desc="The generated customer service response")
        
        # Configure language model if needed
        if api_key:
            # Initialize Ollama if needed
            if "ollama" in model_name:
                ollama_model = model_name.split("/")[1]
                initialize_ollama_model(ollama_model)
            
            # Configure the language model
            self.lm = LM(model_name, api_key=api_key, temperature=0.7, max_tokens=200)
            if metrics:
                self.lm = MetricsLogger(self.lm, metrics)
            dspy.configure(lm=self.lm)

    def forward(self, condition: str) -> Dict[str, str]:
        """Generate a customer service response for a given condition.
        
        This method uses the configured language model to generate a professional
        and effective response following customer service best practices.
        
        Args:
            condition: The customer service condition/scenario to respond to
            
        Returns:
            Dictionary containing the generated response under the 'response' key
            
        Raises:
            ValueError: If no condition is provided
        """
        if not condition:
            raise ValueError("Condition must be provided")
            
        # Generate response using DSPy signature
        response = dspy.Predict("condition -> response")(condition=condition).response
        return {"response": response}


class BatchOptimizedGuidelineManager:
    """Manager for optimizing multiple guidelines using DSPy.
    
    This class handles the optimization of multiple guidelines in batches,
    using DSPy's COPRO optimizer to improve response quality.
    
    Attributes:
        metrics: Metrics tracker for monitoring performance
        lm: Language model instance for generating responses
        program: GuidelineProgram instance for response generation
        optimizer: Optional COPRO optimizer for improving response quality
        use_optimizer: Whether to use DSPy's COPRO optimizer
    """
    
    def __init__(self, api_key: str, model_name: str = "openai/gpt-3.5-turbo", use_optimizer: bool = True) -> None:
        """Initialize the manager.
        
        Args:
            api_key: API key for the model provider
            model_name: Name of the model to use (e.g., "openai/gpt-3.5-turbo", "ollama/llama2")
            use_optimizer: Whether to use DSPy's COPRO optimizer
        """
        self.metrics = ModelMetrics()
        self.use_optimizer = use_optimizer
        
        # Initialize Ollama if needed
        if "ollama" in model_name:
            ollama_model = model_name.split("/")[1]
            initialize_ollama_model(ollama_model)
        
        # Configure the language model
        self.lm = LM(model_name, api_key=api_key, temperature=0.7, max_tokens=200)
        if self.metrics:
            self.lm = MetricsLogger(self.lm, self.metrics)
        dspy.configure(lm=self.lm)
        
        # Create base program
        self.program = GuidelineProgram(metrics=self.metrics)  # Use the configured LM
        
        # Configure optimizer if needed
        if use_optimizer:
            self.optimizer = COPRO(
                prompt_model=self.lm,
                init_temperature=1.0,  # Higher temperature for more diverse responses
                breadth=12,           # More candidates
                depth=4,              # More iterations for refinement
                threshold=0.5,        # More lenient threshold
                metric=self._calculate_response_quality
            )

    def _calculate_response_quality(self, pred: Any, gold: Any) -> float:
        """Calculate quality score for a response.
        
        The score is based on multiple factors including:
        - Response length (30-150 words preferred)
        - Use of professional language
        - Overlap with gold response terminology
        - Presence of follow-up questions
        - Proper sentence endings
        
        Args:
            pred: Predicted response
            gold: Gold/reference response
            
        Returns:
            Quality score between 0 and 1
        """
        # Extract response strings from prediction and gold
        pred_str = pred.get("response", "") if isinstance(pred, dict) else getattr(pred, "response", "")
        gold_str = gold.get("response", "") if isinstance(gold, dict) else getattr(gold, "response", "")
        
        # If either response is missing, return 0
        if not pred_str or not gold_str:
            return 0.0
            
        score = 0.3  # Base score for any valid response
        
        # Length check - prefer concise responses but be more lenient
        words = len(pred_str.split())
        if 30 <= words <= 100:  # Sweet spot
            score += 0.2
        elif 20 <= words <= 150:  # Still acceptable
            score += 0.1
            
        # Contains relevant terminology from gold response
        gold_words = set(gold_str.lower().split())
        pred_words = set(pred_str.lower().split())
        overlap = len(gold_words.intersection(pred_words))
        score += min(0.2, overlap * 0.02)  # More lenient word overlap
            
        # Professional language - award partial points for each term
        professional_terms = [
            "please", "thank", "assist", "help", "understand", "appreciate",
            "apologize", "sorry", "support", "resolve", "investigate",
            "provide", "explain", "guide", "recommend"
        ]
        prof_count = sum(1 for term in professional_terms if term in pred_str.lower())
        score += min(0.2, prof_count * 0.04)  # More credit for professional terms
            
        # Check for specific response elements
        if "?" in pred_str:  # Has follow-up questions
            score += 0.1
            
        if any(pred_str.strip().endswith(p) for p in [".", "!", "?"]):  # Complete sentence
            score += 0.1
            
        if any(char.isdigit() for char in pred_str):  # Contains specific numbers/details
            score += 0.1
            
        # Structure and formatting
        if len(pred_str.split("\n")) > 1:  # Good formatting with line breaks
            score += 0.1
            
        # Deductions
        deductions = 0.0
        
        # Error messages or debugging info
        error_terms = ["error:", "exception:", "debug:", "traceback", "undefined", "null"]
        if any(term in pred_str.lower() for term in error_terms):
            deductions += 0.3
            
        # Very short or very long responses
        if words < 15 or words > 200:
            deductions += 0.2
            
        # Repetitive text
        if len(set(pred_str.split())) < len(pred_str.split()) / 3:
            deductions += 0.2
            
        return max(0.0, min(1.0, score - deductions))

    def optimize_guidelines(
            self, 
            guidelines: Sequence[Guideline],
            examples: List[Dict[str, str]],
            batch_size: int = 10
        ) -> List[Guideline]:
        """Optimize guidelines using DSPy's COPRO optimizer.
        
        This method processes guidelines in batches, using the COPRO optimizer
        to improve response quality based on example data.
        
        Args:
            guidelines: List of guidelines to optimize
            examples: List of example dictionaries for training
            batch_size: Size of batches for optimization
            
        Returns:
            List of optimized guidelines with improved responses
        """
        logger.info(f"Starting optimization of {len(guidelines)} guidelines")
        start_time = time.time()
        
        # Convert examples to DSPy format
        dspy_examples = []
        for ex in examples:
            example = Example(
                condition=ex["condition"],
                response=ex["response"]
            ).with_inputs("condition")
            dspy_examples.append(example)
        
        # Compile the program with examples if using optimizer
        if hasattr(self, "optimizer"):
            try:
                # Create an evaluator for the optimizer
                evaluator = dspy.Evaluate(
                    devset=dspy_examples[:2],  # Use a smaller dev set for faster evaluation
                    metric=self.optimizer.metric
                )
                
                # Compile with the evaluator
                with dspy.settings.context(lm=self.lm):
                    try:
                        # Run optimization
                        optimized_program = self.optimizer.compile(
                            self.program,
                            trainset=dspy_examples[2:],  # Use remaining examples for training
                            eval_kwargs={"evaluator": evaluator}
                        )
                        
                        # Update program if optimization succeeded
                        if optimized_program:
                            logger.info("Successfully optimized program with COPRO")
                            self.program = optimized_program
                        else:
                            logger.warning("COPRO optimization returned None, using original program")
                            
                    except IndexError:
                        logger.warning("No valid candidates found during optimization, using original program")
                    except Exception as e:
                        logger.error(f"Failed to compile optimizer: {e}")
                        logger.debug("Falling back to unoptimized program", exc_info=True)
                    
            except Exception as e:
                logger.error(f"Failed to set up optimization: {e}")
                logger.debug("Falling back to unoptimized program", exc_info=True)
                
        optimized_guidelines = []
        
        # Process guidelines in batches
        for i in range(0, len(guidelines), batch_size):
            batch = guidelines[i:i + batch_size]
            
            # Process each guideline in the batch
            for guideline in batch:
                try:
                    # Generate response using the program
                    result = self.program(condition=guideline.content.condition)
                    response = result.get("response", "")
                    
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

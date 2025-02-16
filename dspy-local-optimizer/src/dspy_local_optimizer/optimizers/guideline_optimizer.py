"""Module for optimizing guidelines using DSPy."""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
from dataclasses import dataclass
import time
from datetime import datetime

import dspy
from dspy import Example, ChainOfThought, LM, Module, Signature, TypedPredictor
from dspy.teleprompt import COPRO

from dspy_local_optimizer.core.ollama import OllamaLanguageModel
from dspy_local_optimizer.core.openai import OpenAILanguageModel
from dspy_local_optimizer.core.models import Guideline, GuidelineContent
from dspy_local_optimizer.core.metrics import ModelMetrics
from dspy_local_optimizer.core.ollama import initialize_ollama_model

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
        
        # Store init params
        self._init_params = {
            'api_key': api_key,
            'model_name': model_name,
            'use_optimizer': use_optimizer,
            'metrics': metrics
        }
        
        # Initialize Ollama if needed
        if "ollama" in model_name:
            ollama_model = model_name.split("/")[1]
            initialize_ollama_model(ollama_model)
        
        # Configure the language model
        self.lm = LM(model_name, temperature=0.7, max_tokens=200)
        if metrics:
            self.lm = MetricsLogger(self.lm, metrics)
        dspy.configure(lm=self.lm)
        
        # Configure optimizer if needed
        if use_optimizer:
            self.optimizer = COPRO(
                prompt_model=self.lm,
                init_temperature=0.8,
                breadth=5,  # Increased for better exploration
                depth=2,    # Allow iterative improvement
                track_stats=True  # Enable stats tracking
            )
            
        # Set initial instructions
        self.predictor = dspy.Predict(dspy.Signature({
            "condition": dspy.InputField(desc="The customer's inquiry or situation"),
            "response": dspy.OutputField(desc="Your professional and helpful response", prefix="Here's how I would help: ")
        }))
        
        # Add instructions
        self.predictor.signature.instructions = """You are a professional customer service representative. Your task is to provide helpful, polite, and clear responses to customer inquiries.
        
        Key guidelines:
        1. Always start with a polite greeting or acknowledgment
        2. Show empathy and understanding
        3. Be clear and specific in your response
        4. Ask clarifying questions when needed
        5. End with an offer for further assistance
        
        Format your response in a professional tone, maintaining a balance between being friendly and respectful.
        
        Examples:
        condition: "My order hasn't arrived yet and it's been a week"
        response: "I understand your concern about the delayed order. Let me help you track its status. Could you please provide your order number? I'll make sure to expedite this for you and keep you updated on its progress."
        
        condition: "The product I received is damaged"
        response: "I'm very sorry to hear that your product arrived damaged. This must be frustrating. I'll help you get this resolved right away. Could you please send photos of the damage? I'll arrange for a replacement to be shipped to you immediately."
        
        condition -> response"""
        
    def __getstate__(self):
        """Get state for pickling."""
        state = self.__dict__.copy()
        # Remove unpicklable attributes
        state.pop('lm', None)
        state.pop('optimizer', None)
        state.pop('predictor', None)
        return state
        
    def __setstate__(self, state):
        """Set state during unpickling."""
        self.__dict__.update(state)
        # Restore state using stored init params
        if '_init_params' in state:
            params = state['_init_params']
            self.__init__(**params)
        
    def forward(self, **kwargs: Any) -> Dict[str, str]:
        """Generate a response for a given condition.
        
        Args:
            **kwargs: Keyword arguments containing the condition
            
        Returns:
            Dictionary with the generated response
        """
        condition = kwargs.get("condition")
        if not condition:
            raise ValueError("Condition is required")
            
        try:
            # Generate response using predictor
            result = self.predictor(condition=condition)
            
            # Extract response from result
            if hasattr(result, 'response'):
                response = result.response
            elif isinstance(result, dict):
                response = result.get('response', '')
            else:
                response = str(result)
                
            # Clean up response
            if isinstance(response, list):
                response = response[0] if response else ""
            elif isinstance(response, dict):
                response = response.get("text", "")
            elif not isinstance(response, str):
                response = str(response)
                
            response = response.strip().strip('"').strip()
            
            # Log response for debugging
            logger.debug(f"Generated response: {response}")
            
            # Validate response
            if not response:
                logger.warning("Empty response generated")
                response = "I apologize, but I am unable to provide a response at this time. Please try again."
                
            # Return response in expected format
            return {"response": response}
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise


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
        
    def _calculate_response_quality(self, pred: str, gold: str) -> float:
        """Calculate a quality score between predicted and gold responses.
        
        The score is based on:
        1. Word overlap ratio (using sets)
        2. Length similarity
        3. Key phrase presence
        4. Sentence structure similarity
        
        Args:
            pred: Predicted response
            gold: Gold standard response
            
        Returns:
            float: Quality score between 0 and 1
        """
        # Normalize text
        pred = pred.lower().strip()
        gold = gold.lower().strip()
        
        # Get word sets
        pred_words = set(pred.split())
        gold_words = set(gold.split())
        
        if not pred_words or not gold_words:
            return 0.0
            
        # Calculate word overlap using Jaccard similarity
        intersection = pred_words.intersection(gold_words)
        union = pred_words.union(gold_words)
        overlap_score = len(intersection) / len(union) if union else 0
        
        # Calculate length similarity (penalize if too short or too long)
        len_ratio = min(len(pred.split()) / max(len(gold.split()), 1),
                       len(gold.split()) / max(len(pred.split()), 1))
        
        # Check for key phrases that should be present
        key_phrases = ["thank", "please", "help", "assist", "understand", 
                      "would you like", "can you", "let me know"]
        phrase_matches = sum(1 for phrase in key_phrases if phrase in pred)
        phrase_score = phrase_matches / len(key_phrases)
        
        # Check sentence structure (looking for questions and acknowledgments)
        pred_has_question = any(x in pred for x in ["?", "could you", "would you", "can you"])
        gold_has_question = any(x in gold for x in ["?", "could you", "would you", "can you"])
        structure_score = float(pred_has_question == gold_has_question)
        
        # Combine scores with weights (emphasizing overlap and key phrases)
        final_score = (
            0.4 * overlap_score +
            0.2 * len_ratio +
            0.3 * phrase_score +
            0.1 * structure_score
        )
        
        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, final_score))
        
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
        
        # Convert examples to DSPy format and specify inputs
        dspy_examples = [
            Example(condition=ex["condition"], response=ex["response"]).with_inputs("condition")
            for ex in examples
        ]
        
        # Create an evaluator for the optimizer
        evaluator = dspy.Evaluate(
            devset=dspy_examples[:5],  # Use a small dev set
            metric=lambda pred, gold: self._calculate_response_quality(
                pred.get("response", "") if isinstance(pred, dict) else getattr(pred, "response", ""),
                gold.get("response", "") if isinstance(gold, dict) else getattr(gold, "response", "")
            ),
            num_threads=1,
            display_progress=True,
            display_table=0
        )
        
        # Configure optimizer with increased breadth and depth
        if not hasattr(self.program, "optimizer"):
            self.program.optimizer = COPRO(
                prompt_model=self.program.lm,
                init_temperature=0.8,
                breadth=5,  # Increased from 2 to get more candidates
                depth=2,    # Increased from 1 to allow iterative improvement
                metric=evaluator.metric,  # Use evaluator's metric
                track_stats=True  # Enable stats tracking
            )
        
        # Compile the program with examples if using optimizer
        if hasattr(self.program, "optimizer"):
            try:
                # Compile with the evaluator
                with dspy.settings.context(lm=self.program.lm):
                    # Run optimization with evaluator
                    optimized_program = self.program.optimizer.compile(
                        self.program,
                        trainset=dspy_examples,
                        eval_kwargs={"evaluator": evaluator}  # Pass evaluator to compile
                    )
                    
                    # Update program if optimization succeeded
                    if optimized_program:
                        logger.info("Successfully optimized program with COPRO")
                        self.program = optimized_program
                    else:
                        logger.warning("COPRO optimization returned None, using original program")
                    
            except Exception as e:
                logger.error(f"Failed to compile optimizer: {e}")
                logger.debug("Falling back to unoptimized program", exc_info=True)
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
                    
                    # Extract response from result
                    if isinstance(result, dict):
                        response = result.get("response", "")
                    else:
                        response = getattr(result, "response", "")
                        
                    # Clean up response
                    if isinstance(response, list):
                        response = response[0] if response else ""
                    elif isinstance(response, dict):
                        response = response.get("text", "")
                    elif not isinstance(response, str):
                        response = str(response)
                        
                    response = response.strip().strip('"').strip()
                    
                    # Log response for debugging
                    logger.debug(f"Generated response: {response}")
                    
                    # Create new optimized guideline
                    optimized_guideline = Guideline(
                        id=guideline.id,
                        creation_utc=guideline.creation_utc,
                        content=GuidelineContent(
                            condition=guideline.content.condition,
                            response=response
                        )
                    )
                    optimized_guidelines.append(optimized_guideline)
                    
                except Exception as e:
                    logger.error(f"Failed to optimize guideline {guideline.id}: {e}")
                    logger.debug("Keeping original guideline", exc_info=True)
                    # Keep original guideline on error
                    optimized_guidelines.append(guideline)
        
        self.metrics.total_time = time.time() - start_time
        return optimized_guidelines

@dataclass
class GuidelineContent:
    """Content of a guideline.
    
    Attributes:
        condition: The customer's inquiry or situation
        response: The response to provide for this condition
    """
    condition: str
    response: str  

@dataclass
class Guideline:
    """A guideline for customer service responses.
    
    Attributes:
        id: Unique identifier for the guideline
        creation_utc: When the guideline was created
        content: The guideline's content (condition and response)
    """
    id: str
    creation_utc: datetime
    content: GuidelineContent

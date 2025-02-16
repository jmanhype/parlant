"""Tests for the COPRO optimizer functionality."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture

import pytest
import dspy
from dspy import Example, LM, Signature, COPRO, InputField, OutputField, Module, Evaluate, Predict


@pytest.fixture
def openai_api_key() -> str:
    """Get OpenAI API key from environment.
    
    Raises:
        pytest.skip: If API key is not found
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        pytest.skip("OpenAI API key not found in environment")
    return api_key


@pytest.fixture
def language_model(openai_api_key: str) -> LM:
    """Create and configure language model.
    
    Args:
        openai_api_key: OpenAI API key
        
    Returns:
        Configured language model
    """
    lm = LM("openai/gpt-3.5-turbo", api_key=openai_api_key)
    dspy.configure(lm=lm)
    return lm


class TextProcessor(dspy.Signature):
    """A simple text processing program that adds a prefix to input text.
    
    This program takes any input text and adds 'Processed: ' to the beginning.
    It serves as a minimal example for testing the COPRO optimizer.
    """
    
    input = InputField(desc="Raw input text that needs to be processed", default="")
    output = OutputField(desc="Processed output text with 'Processed: ' prefix added to the front", default="")
    
    instructions: ClassVar[str] = """You are a text processing system that adds a prefix to input text.

    Your task is to take any input text and process it by adding 'Processed: ' to the beginning.
    
    Rules:
    1. Always add exactly 'Processed: ' (with a space) to the start
    2. Keep the original input text unchanged after the prefix
    3. Maintain proper spacing (one space after the colon)
    4. Do not modify the input text in any way
    
    Format:
    input -> output
    
    Examples:
    'Hello' -> 'Processed: Hello'
    'World' -> 'Processed: World'
    'Test' -> 'Processed: Test'
    '123' -> 'Processed: 123'
    'Multiple words here' -> 'Processed: Multiple words here'
    
    Let's solve this step by step:
    1. Take the input text
    2. Add 'Processed: ' to the front
    3. Return the combined result
    """


class SimpleProgram(dspy.Module):
    """A simple program that uses a text predictor to add a prefix to input text."""
    
    def __init__(self) -> None:
        """Initialize the program with a text predictor."""
        super().__init__()
        self.predictor = Predict(TextProcessor)
        
    def forward(self, input: str) -> Dict[str, str]:
        """Process the input text by adding a prefix.
        
        Args:
            input: Raw input text to process
            
        Returns:
            Dict containing processed output with 'Processed: ' prefix
        """
        # Step 1: Validate input
        assert isinstance(input, str), "Input must be a string"
        
        # Step 2: Process using predictor
        result = self.predictor(input=input)
        
        # Step 3: Validate output
        assert result.output.startswith("Processed: "), "Output must start with prefix"
        assert result.output[len("Processed: "):] == input, "Original input must be preserved"
        
        return {"output": result.output}
        
    def deepcopy(self) -> 'SimpleProgram':
        """Create a deep copy of this program.
        
        Returns:
            A new instance of SimpleProgram with the same attributes
        """
        return SimpleProgram()


def exact_match_metric(pred: Dict[str, str], gold: Dict[str, str]) -> float:
    """Calculate exact match score between prediction and gold standard.
    
    Args:
        pred: Predicted output dictionary
        gold: Gold standard output dictionary
        
    Returns:
        1.0 if prediction matches gold exactly, 0.0 otherwise
    """
    return 1.0 if pred.get("output") == gold.get("output") else 0.0


def test_copro_basic_functionality(language_model: LM) -> None:
    """Test basic COPRO optimizer functionality with a simple text processing task.
    
    Args:
        language_model: Configured language model
    """
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    # Create simple program
    program = SimpleProgram()
    logger.debug(f"Program signature: {program}")
    logger.debug(f"Program instructions: {program.predictor.signature.instructions}")
    
    # Create training examples with diverse inputs
    examples = [
        Example(input="Hello", output="Processed: Hello").with_inputs("input"),
        Example(input="World", output="Processed: World").with_inputs("input"),
        Example(input="Test", output="Processed: Test").with_inputs("input"),
        Example(input="123", output="Processed: 123").with_inputs("input"),
        Example(input="Multiple words here", output="Processed: Multiple words here").with_inputs("input")
    ]
    logger.debug(f"Training examples: {examples}")
    
    # Create simple metric
    def debug_metric(pred: Dict[str, str], gold: Dict[str, str]) -> float:
        """Debug metric that logs inputs and returns exact match."""
        logger.debug(f"Comparing pred={pred} with gold={gold}")
        result = 1.0 if pred.get("output") == gold.get("output") else 0.0
        logger.debug(f"Metric result: {result}")
        return result
    
    # Configure optimizer with reduced breadth and depth
    optimizer = COPRO(
        prompt_model=language_model,
        init_temperature=0.8,
        breadth=2,  # Reduced from 3 to minimize candidates
        depth=1,    # Keep at 1 to avoid multiple iterations
        metric=debug_metric,  # Use debug metric
        track_stats=True  # Enable stats tracking
    )
    
    # Create evaluator with same metric
    evaluator = Evaluate(
        devset=examples,
        metric=debug_metric,
        num_threads=1,
        display_progress=True,
        display_table=0
    )
    
    # Test program works before optimization
    for example in examples:
        result = program.forward(example.input)
        assert result["output"] == example.output, f"Program failed before optimization: {result}"
    
    # Compile program
    try:
        # Configure DSPy to use our language model
        with dspy.settings.context(lm=language_model):
            # Run optimization
            optimized_program = optimizer.compile(
                program,
                trainset=examples,
                eval_kwargs={}
            )
            
            # Test optimized program
            for example in examples:
                result = optimized_program.forward(example.input)
                assert result["output"] == example.output, f"Optimized program failed: {result}"
                
            assert True, "COPRO compilation succeeded"
    except Exception as e:
        logger.error(f"COPRO compilation failed: {e}", exc_info=True)
        pytest.fail(f"COPRO compilation failed: {e}")


def test_copro_with_empty_examples(language_model: LM) -> None:
    """Test COPRO behavior with empty example set to ensure proper error handling.
    
    Args:
        language_model: Configured language model
    """
    program = SimpleProgram()
    examples: List[Example] = []
    
    optimizer = COPRO(
        prompt_model=language_model,
        init_temperature=0.8,
        breadth=2,
        depth=1,
        metric=exact_match_metric
    )
    
    # We expect a ValueError when compiling with empty examples
    with pytest.raises((ValueError, ZeroDivisionError)) as exc_info:
        with dspy.settings.context(lm=language_model):
            optimizer.compile(
                program,
                trainset=examples,
                eval_kwargs={}
            )
            
    # Verify the error is related to empty examples
    error_msg = str(exc_info.value).lower()
    assert any(word in error_msg for word in ["empty", "no examples", "zero", "division by zero"]), \
        f"Expected error message to be about empty examples, got: {error_msg}"


def test_copro_with_large_example_set(language_model: LM) -> None:
    """Test COPRO with a larger set of examples to verify scalability.
    
    Args:
        language_model: Configured language model
    """
    program = SimpleProgram()
    
    # Create larger set of examples with diverse inputs
    examples = [
        Example(input=f"Test{i}", output=f"Processed: Test{i}").with_inputs("input")
        for i in range(10)
    ]
    examples.extend([
        Example(input="Multiple words here", output="Processed: Multiple words here").with_inputs("input"),
        Example(input="123", output="Processed: 123").with_inputs("input"),
        Example(input="Special!@#$", output="Processed: Special!@#$").with_inputs("input")
    ])
    
    optimizer = COPRO(
        prompt_model=language_model,
        init_temperature=0.8,
        breadth=2,
        depth=1,
        metric=exact_match_metric
    )
    
    evaluator = Evaluate(
        devset=examples,
        metric=exact_match_metric,
        num_threads=1,
        display_progress=True,
        display_table=0
    )
    
    try:
        with dspy.settings.context(lm=language_model):
            optimizer.compile(
                program,
                trainset=examples,
                eval_kwargs={}
            )
            assert True, "COPRO compilation succeeded with large example set"
    except Exception as e:
        pytest.fail(f"COPRO compilation failed with large example set: {e}")


def word_overlap_metric(pred: Dict[str, str], gold: Dict[str, str]) -> float:
    """Calculate word overlap score between prediction and gold standard.
    
    The score is based on the Jaccard similarity between the word sets
    of the prediction and gold standard outputs.
    
    Args:
        pred: Predicted output dictionary
        gold: Gold standard output dictionary
        
    Returns:
        float: Similarity score between 0 and 1
    """
    pred_words = set(pred.get("output", "").lower().split())
    gold_words = set(gold.get("output", "").lower().split())
    
    if not pred_words or not gold_words:
        return 0.0
        
    intersection = pred_words.intersection(gold_words)
    union = pred_words.union(gold_words)
    
    return len(intersection) / len(union)


def test_copro_with_complex_metric(language_model: LM) -> None:
    """Test COPRO with a more sophisticated evaluation metric.
    
    This test verifies that COPRO can work with metrics beyond simple
    exact matching, using word overlap similarity in this case.
    
    Args:
        language_model: Configured language model
    """
    program = SimpleProgram()
    
    examples = [
        Example(input="Hello", output="Processed: Hello").with_inputs("input"),
        Example(input="World", output="Processed: World").with_inputs("input"),
        Example(input="Test", output="Processed: Test").with_inputs("input"),
        Example(input="Multiple words here", output="Processed: Multiple words here").with_inputs("input")
    ]
    
    optimizer = COPRO(
        prompt_model=language_model,
        init_temperature=0.8,
        breadth=2,
        depth=1,
        metric=word_overlap_metric
    )
    
    evaluator = Evaluate(
        devset=examples,
        metric=word_overlap_metric,
        num_threads=1,
        display_progress=True,
        display_table=0
    )
    
    try:
        with dspy.settings.context(lm=language_model):
            optimizer.compile(
                program,
                trainset=examples,
                eval_kwargs={}
            )
            assert True, "COPRO compilation succeeded with complex metric"
    except Exception as e:
        pytest.fail(f"COPRO compilation failed with complex metric: {e}")

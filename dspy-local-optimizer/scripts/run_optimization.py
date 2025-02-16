"""Script to run guideline optimization with different models."""

import copy
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional

import dspy
from dspy import Example, LM

from dspy_local_optimizer import BatchOptimizedGuidelineManager, Guideline, GuidelineContent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Example guidelines
GUIDELINES: List[Guideline] = [
    Guideline(
        id="1",
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer asks about pricing tiers",
            response="We offer three pricing tiers: Basic ($10/month), Pro ($25/month), and Enterprise (custom pricing)."
        )
    ),
    Guideline(
        id="2", 
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer reports a technical error",
            response="Could you please provide more details about the error you're experiencing? This will help me better assist you."
        )
    ),
    Guideline(
        id="3",
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer requests a refund",
            response="I understand you'd like a refund. Could you please explain the reason for your request? This will help me process it appropriately."
        )
    )
]

# Example training data
TRAINING_DATA: List[Dict[str, str]] = [
    {
        "condition": "Customer asks about pricing tiers",
        "response": "Thank you for your inquiry about our pricing. Our Basic tier is $10/month with essential features, while our Pro tier is $25/month with advanced capabilities. Feel free to ask more about specific features included in each tier."
    },
    {
        "condition": "Customer reports a technical error",
        "response": "Thank you for bringing this to our attention. Could you please provide more details about the technical error you are experiencing so we can assist you better?"
    },
    {
        "condition": "Customer requests a refund",
        "response": "Thank you for reaching out about a refund. Please provide your order number and reason for the refund request so we can assist you further."
    },
    {
        "condition": "Customer asks about feature availability",
        "response": "Thank you for your interest in our features. I'll be happy to explain what's available. Which specific feature would you like to know more about?"
    },
    {
        "condition": "Customer reports slow performance",
        "response": "I'm sorry to hear you're experiencing performance issues. To help you better, could you please tell me: 1) When did you first notice the slowdown? 2) Which specific operations are affected?"
    },
    # Pricing tier examples
    {
        "condition": "I want to know about your pricing plans",
        "response": "Thank you for your interest in our pricing plans! We offer three tiers:\n\n1. Basic ($10/month): Essential features and email support\n2. Pro ($25/month): Advanced features and priority support\n3. Enterprise (custom pricing): Full feature set with dedicated support\n\nWould you like me to explain any specific tier in more detail?"
    },
    {
        "condition": "What features do I get with the Basic plan?",
        "response": "Thank you for asking about our Basic plan! For $10/month, you'll receive:\n\n1. Core platform features\n2. Basic analytics dashboard\n3. Email support (24-48 hour response time)\n4. Up to 5 user accounts\n\nWould you like to compare this with our Pro plan, or do you have any specific questions about these features?"
    },
    {
        "condition": "Tell me about the Pro tier benefits",
        "response": "I'd be happy to explain our Pro tier benefits! At $25/month, the Pro plan includes:\n\n1. All Basic features, plus:\n2. Advanced analytics with custom reports\n3. Priority support (4-8 hour response time)\n4. Up to 20 user accounts\n5. API access\n\nWe also offer a 14-day free trial of the Pro tier. Would you like me to help you get started with that?"
    },
    # Technical error examples
    {
        "condition": "I'm getting an error when trying to log in",
        "response": "I apologize for the login trouble you're experiencing. To help you quickly resolve this, could you please:\n\n1. Tell me what error message you're seeing\n2. Confirm which browser and device you're using\n3. Let me know if this started happening recently\n\nIn the meantime, try clearing your browser cache and cookies. I'm here to guide you through the process if needed."
    },
    {
        "condition": "The dashboard won't load properly",
        "response": "I'm sorry to hear you're having trouble with the dashboard. Let's troubleshoot this together:\n\n1. First, could you try refreshing the page?\n2. If that doesn't work, please try accessing it in a different browser\n3. Are you seeing any specific error messages?\n\nPlease let me know what happens after trying these steps, and I'll help you further."
    },
    {
        "condition": "404 error on the reports page",
        "response": "I apologize for the 404 error you're encountering. This typically means the page cannot be found. To help resolve this:\n\n1. Could you confirm the exact URL you're trying to access?\n2. Were you directed here from another page in our system?\n3. Have you accessed this report successfully before?\n\nI'll help track down the correct page or restore access if needed."
    },
    # Refund examples
    {
        "condition": "I want a refund for my subscription",
        "response": "I understand you're requesting a refund. I'll be happy to help you with this process. Could you please:\n\n1. Provide your account or order number\n2. Let me know the reason for the refund request\n3. Confirm when the charge was made\n\nThis information will help me process your refund request as quickly as possible."
    },
    {
        "condition": "Do you have a money-back guarantee?",
        "response": "Yes, we absolutely do! We offer a 30-day money-back guarantee on all our subscription plans. Here's how it works:\n\n1. If you're not satisfied within 30 days of purchase\n2. Contact us with your order number\n3. We'll process a full refund, no questions asked\n\nWould you like me to help you with a refund request now?"
    },
    {
        "condition": "I was charged twice this month",
        "response": "I sincerely apologize for the double charge. This shouldn't happen, and I'll help resolve this right away. Please:\n\n1. Provide your account number\n2. Send me the dates of both charges\n3. Share any transaction IDs you have\n\nI'll investigate this immediately and ensure you receive a refund for the duplicate charge."
    }
]

def prepare_examples(training_data: List[Dict[str, str]]) -> List[dspy.Example]:
    """Convert training data to DSPy examples with proper input field specification.
    
    Args:
        training_data: List of dictionaries with condition and response fields
        
    Returns:
        List of DSPy examples
        
    Raises:
        ValueError: If training data is empty or malformed
    """
    if not training_data:
        raise ValueError("Training data cannot be empty")
        
    examples = []
    for data in training_data:
        if not isinstance(data, dict) or "condition" not in data or "response" not in data:
            raise ValueError(f"Invalid training data format: {data}")
            
        # Create example with both input and output fields
        example = dspy.Example(
            condition=data["condition"],
            response=data["response"]
        ).with_inputs("condition")  # Specify input field
        examples.append(example)
        
    return examples

def run_optimization(model_name: str, batch_size: int = 5) -> None:
    """Run optimization with specified model.

    Args:
        model_name: Name of model to use
        batch_size: Size of batches for processing. Defaults to 5.
        
    Raises:
        ValueError: If API key is missing or invalid
        RuntimeError: If optimization fails
    """
    logger.info(f"Running optimization with {model_name}")
    logger.info("-" * 80)
    
    # Validate API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found in environment")
    
    try:
        # Prepare examples
        examples = prepare_examples(TRAINING_DATA)
        logger.info(f"Prepared {len(examples)} training examples")
        
        # Initialize optimizer with minimal configuration
        optimizer = BatchOptimizedGuidelineManager(
            api_key=api_key,
            model_name=model_name,
            use_optimizer=True
        )
        
        # Run optimization with prepared examples
        optimized: List[Guideline] = optimizer.optimize_guidelines(
            guidelines=copy.deepcopy(GUIDELINES),  # Use deepcopy to avoid modifying originals
            examples=examples,  # Pass the properly prepared examples
            batch_size=batch_size
        )
        
        # Print results
        logger.info(f"Total API calls: {optimizer.metrics.total_api_calls}")
        logger.info(f"Total tokens: {optimizer.metrics.total_tokens}")
        logger.info(f"Total time: {optimizer.metrics.total_time:.2f} seconds")
        logger.info("\nExample responses:\n")
        
        for guideline in optimized[:3]:  # Show first 3 responses
            logger.info(f"Condition: {guideline.content.condition}")
            logger.info(f"Response: {guideline.content.response}\n")
        
        logger.info("-" * 80)
        
    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        raise RuntimeError(f"Failed to run optimization with {model_name}: {e}")

def main() -> None:
    """Run optimization with both models.
    
    This function runs the optimization process with both GPT-3.5-turbo and Llama2 models.
    It handles any errors that occur during optimization and ensures proper cleanup.
    """
    try:
        # Run with GPT-3.5-turbo
        run_optimization("openai/gpt-3.5-turbo")
        
        # Run with Llama2
        run_optimization("ollama/llama2")
        
    except Exception as e:
        logger.error(f"Main execution failed: {e}", exc_info=True)
        raise
    finally:
        # Cleanup and final logging
        logger.info("Optimization run completed")

if __name__ == "__main__":
    main()

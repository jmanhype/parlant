"""Script to run guideline optimization with different models."""

import os
import asyncio
from datetime import datetime
from typing import List, Dict

import dspy
from dspy.teleprompt import COPRO

from parlant.core.guidelines import Guideline, GuidelineContent
from parlant.dspy_integration.guideline_optimizer import BatchOptimizedGuidelineManager, GuidelineProgram

# Example guidelines
GUIDELINES = [
    Guideline(
        id="1",
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer asks about pricing tiers",
            action="We offer three pricing tiers: Basic ($10/month), Pro ($25/month), and Enterprise (custom pricing)."
        )
    ),
    Guideline(
        id="2", 
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer reports a technical error",
            action="Could you please provide more details about the error you're experiencing? This will help me better assist you."
        )
    ),
    Guideline(
        id="3",
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer requests a refund",
            action="I understand you'd like a refund. Could you please explain the reason for your request? This will help me process it appropriately."
        )
    ),
    Guideline(
        id="4",
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer asks about feature availability",
            action="I'll be happy to explain our feature availability. Which specific feature are you interested in?"
        )
    ),
    Guideline(
        id="5",
        creation_utc=datetime.now(),
        content=GuidelineContent(
            condition="Customer reports slow performance",
            action="I'm sorry to hear about the performance issues. Could you tell me: 1) When did you first notice this? 2) Which specific operations are slow?"
        )
    )
]

# Example training data
TRAINING_DATA = [
    {
        "condition": "Customer asks about upgrading their subscription",
        "response": "I can help you upgrade your subscription. Currently, you can upgrade to our Pro tier ($25/month) or Enterprise tier (custom pricing). Which would you like to learn more about?"
    },
    {
        "condition": "Customer can't log in to their account",
        "response": "I'm sorry you're having trouble logging in. To help you best: 1) Are you getting any specific error messages? 2) Have you tried resetting your password?"
    },
    {
        "condition": "Customer complains about app crashing",
        "response": "I apologize for the inconvenience. To help resolve this quickly: 1) What device/OS are you using? 2) When did the crashes start? 3) Does it happen during specific actions?"
    },
    {
        "condition": "Customer wants to cancel subscription",
        "response": "I understand you'd like to cancel. Before proceeding, may I ask about your reasons? We might have solutions to address your concerns, or I can offer alternative plans that better suit your needs."
    },
    {
        "condition": "Customer asks about data security",
        "response": "We take data security very seriously. Our platform uses industry-standard encryption, regular security audits, and complies with GDPR/CCPA. Would you like more specific details about any aspect of our security measures?"
    },
    {
        "condition": "Customer requests API documentation",
        "response": "Our API documentation is available at docs.example.com. It includes quickstart guides, endpoint references, and code samples. Which programming language are you using? I can point you to relevant examples."
    },
    {
        "condition": "Customer reports missing data",
        "response": "I understand this is concerning. Let's investigate: 1) Which specific data is missing? 2) When did you last see it? 3) Have you made any recent changes? This will help us locate and restore your data quickly."
    },
    {
        "condition": "Customer asks about integration options",
        "response": "We offer several integration options including REST API, webhooks, and native connectors for popular platforms. Could you tell me which system you're looking to integrate with? I'll provide specific compatibility details."
    }
]

def calculate_response_quality(condition: str, response: str) -> float:
    """Calculate quality score for a response.
    
    Args:
        condition: Input condition
        response: Generated response
        
    Returns:
        Quality score between 0 and 1
    """
    score = 0.0
    
    # Length check (not too short, not too long)
    if 20 <= len(response) <= 200:
        score += 0.2
        
    # Contains relevant terminology
    keywords = ["pricing", "tier", "technical", "error", "feature", "subscription", "account"]
    if any(keyword in response.lower() for keyword in keywords):
        score += 0.2
        
    # Includes specific details
    if any(char.isdigit() for char in response) or "$" in response:
        score += 0.2
        
    # Professional language
    professional_terms = ["please", "thank", "assist", "help", "understand"]
    if any(term in response.lower() for term in professional_terms):
        score += 0.2
        
    # No error messages or debugging info
    error_terms = ["error:", "exception:", "debug:", "traceback"]
    if not any(term in response.lower() for term in error_terms):
        score += 0.2
        
    return score

def run_optimization(model_name: str, batch_size: int = 5) -> None:
    """Run optimization with specified model.
    
    Args:
        model_name: Name of model to use
        batch_size: Size of batches for processing
    """
    print(f"\nRunning optimization with {model_name}")
    print("-" * 80)
    
    # Initialize optimizer
    optimizer = BatchOptimizedGuidelineManager(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name=model_name,
        use_optimizer=True
    )
    
    # Configure optimizer if needed
    if optimizer.use_optimizer:
        optimizer.optimizer = COPRO(
            prompt_model=optimizer.lm,
            init_temperature=1.0,      # Higher temperature for more diverse candidates
            breadth=12,                # Generate more candidates
            depth=4,                   # More iterations for refinement
            threshold=0.5,             # More lenient threshold
            top_k=3,                   # Keep top 3 candidates at each step
            max_steps=50,              # Allow more optimization steps
            metric=lambda pred, gold: GuidelineProgram()._calculate_response_quality(
                pred.get("response", "") if isinstance(pred, dict) else getattr(pred, "response", ""),
                gold.get("response", "") if isinstance(gold, dict) else getattr(gold, "response", "")
            )
        )
    
    # Run optimization
    optimized = optimizer.optimize_guidelines(
        guidelines=GUIDELINES,
        examples=TRAINING_DATA,
        batch_size=batch_size
    )
    
    # Calculate average quality score
    avg_quality = sum(
        calculate_response_quality(g.content.condition, g.content.action)
        for g in optimized
    ) / len(optimized)
    
    # Print results
    print(f"Average response quality: {avg_quality:.2f}")
    print(f"Total API calls: {optimizer.metrics.total_api_calls}")
    print(f"Total tokens: {optimizer.metrics.total_tokens}")
    print(f"Total time: {optimizer.metrics.total_time:.2f} seconds")
    print("\nExample responses:")
    
    for guideline in optimized:
        print(f"\nCondition: {guideline.content.condition}")
        print(f"Response: {guideline.content.action}")
    
    print("-" * 80)

def main() -> None:
    """Run optimization with both models."""
    # Run with GPT-3.5-turbo
    run_optimization("openai/gpt-3.5-turbo")
    
    # Run with Llama2
    run_optimization("ollama/llama2")

if __name__ == "__main__":
    main()

<div align="center">
  <img alt="Parlant Logo" src="https://github.com/emcie-co/parlant/blob/daa1993d0fb20c9a6ffd33b1758752f892d482e7/logo.png" width="350" />
  <p>A better way to iterate and hone the outputs of AI chat agents so that your customers actually engage with them</p>
</div>

[Documentation](https://www.parlant.io/docs/quickstart/introduction) | [![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Why Use Parlant?
Building conversational AI agents is relatively simple for most developers—at least, it's relatively simple to build an initial prototype.

But these prototypes are rarely production-ready. Once the prototype is functional, it has to be tuned continually so that its behavior actually provides customers with the experience they expect, and that business stakeholders are satisfied with the service it provides. With DYI prompt-engineering, this is a lot of work.

Parlant bridges this gap by making it easy, fast, and reliable for developers to adjust and maintain the behavior of AI agents based on feedback from customers and business stakeholders.

## Key Features
**Works out-of-the-box with all major LLM providers:**
- [OpenAI](https://platform.openai.com/docs/overview) (also via [Azure](https://learn.microsoft.com/en-us/azure/ai-services/openai/))
- [Gemini](https://ai.google.dev/)
- [Meta Llama 3](https://www.llama.com/) (via [Together AI](https://www.together.ai/) or [Cerebras](https://cerebras.ai/))
- [Anthropic](https://www.anthropic.com/api) (also via [AWS Bedrock](https://aws.amazon.com/bedrock/))

### Reliable Behavior Control
- **Guidelines**: Define clear rules for how your agent should respond in specific situations, like ensuring premium features are only offered to eligible customers
- **Coherence Checks**: Automatically detect when new guidelines might conflict with existing ones, preventing confusion in your agent's behavior
- **Dynamic Context**: Adapt your agent's responses based on user attributes like subscription tier or account status
- **Guided Tool Integration**: Control exactly when, why, and how your agent accesses your business APIs, ensuring appropriate use of backend services

### Developer Experience
- **Instant Feedback**: Changes to guidelines, glossary, or tools take effect immediately—no retraining or redeployment needed
- **Version Control**: Track all behavioral changes in Git, making it easy to review and roll back modifications to your agent's responses
- **Clear Separation**: Keep your business logic in tool code while managing conversational behavior through guidelines
- **Type Safety**: Strongly-typed, native client SDKs for reliable development and clear interfaces

### Production Benefits
- **Safe Updates**: Modify your agent's behavior without risking existing, tested functionality—each change is evaluated for conflicts before being applied
- **Consistent Scaling**: Your agent maintains reliable, predictable behavior regardless of conversation complexity
- **Explainable Actions**: Understand and troubleshoot exactly why your agent chose specific responses through clear guideline tracing
- **Quality Assurance**: Integrated Chat UI makes it easy to iterate on and verify behavioral changes before deployment

## Real-World Impact

[Revenued](https://www.revenued.com), A business capital provider, could get into trouble if their AI agents make false claims or make statements that imply discrimination in lending.

With Parlant, they've been able to quickly integrate feedback from customer service experts and then test and verify that the agents aren't making problematic promises or statements to customers.

## Getting Started



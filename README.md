
<div align="center">
<img alt="Parlant Logo" src="https://github.com/emcie-co/parlant/blob/6b9fb0f642b4054cbeb8490659f9cb963787e933/logo.png" width="125" />
  <h3>Parlant</h3>
  <p>A feedback-driven approach to building and guiding customer-facing agents</p>
  <a href="https://www.parlant.io/docs/quickstart/introduction" target="_blank">Documentation</a>
  <p>
    <a href="https://opensource.org/licenses/Apache-2.0"><img alt="Apache 2 License" src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" /></a>
  </p>
</div>

## Why use Parlant?
Building conversational AI agents is relatively simple for most developers—at least, it's relatively simple to build an initial prototype.

But these prototypes are rarely ready to meet customers. Once the prototype is functional, it has to be continually tuned so that its behavior actually provides customers with a good experience that business stakeholders are happy with. With DIY prompt-engineering, reliably incorporating feedback from stakeholders is challenging, as simple implementations tend to be fragile and inconsistent.

Parlant bridges this gap in a way that makes it easy and fast for developers to reliably adjust the behavior of AI agents based on feedback from customers and business stakeholders.

## Key benefits

### Reliable behavior control
- **Guidelines**: Reliably and predictably control how your agent responds to specific situations, like ensuring premium features are only offered to eligible customers, or that it doesn't over-promise things in attempt to satisfy a customer
- **Coherence Checks**: Automatically detect when new guidelines might conflict with existing ones, preventing confusion in your agent's behavior
- **Dynamic Context**: Adapt your agent's responses based on user attributes like subscription tier or account status
- **Guided Tool Integration**: Control exactly when, why, and how your agent accesses your business APIs, ensuring appropriate use of backend services

### A better developer experience
- **Instant Feedback**: Changes to guidelines, glossary, or tools take effect immediately—no model retraining or redeployment needed
- **Version Control**: Track all behavioral changes in Git, making it easy to review and roll back modifications to your agent's responses
- **Clear Separation**: Keep your business logic in tool code while managing conversational behavior through guidelines
- **Type Safety**: Strongly-typed, native client SDKs for reliable development and clear interfaces

### Actually ready for production
- **Safe Updates**: Modify your agent's behavior without risking existing, tested functionality—each change is evaluated for conflicts before being applied
- **Consistent Scaling**: Your agent maintains reliable, predictable behavior regardless of conversation complexity
- **Explainable Actions**: Understand and troubleshoot exactly why your agent chose specific responses through clear guideline tracing
- **Quality Assurance**: Integrated Chat UI makes it easy to iterate on and verify behavioral changes before deployment

## Real-world impact

[Revenued](https://www.revenued.com), A business capital provider, could get into trouble if their AI agents make false claims or make statements that imply discrimination in lending.

With Parlant, they've been able to quickly integrate feedback from customer service experts and then test and verify that the agents aren't making problematic promises or statements to customers.

## Works with all major LLM providers
- [OpenAI](https://platform.openai.com/docs/overview) (also via [Azure](https://learn.microsoft.com/en-us/azure/ai-services/openai/))
- [Gemini](https://ai.google.dev/)
- [Meta Llama 3](https://www.llama.com/) (via [Together AI](https://www.together.ai/) or [Cerebras](https://cerebras.ai/))
- [Anthropic](https://www.anthropic.com/api) (also via [AWS Bedrock](https://aws.amazon.com/bedrock/))

## Getting Started



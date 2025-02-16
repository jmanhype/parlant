# DSPy Local Optimizer

A lightweight framework for optimizing LLM responses using DSPy, with support for both cloud and local models.

## Features

- DSPy-based optimization pipeline
- Support for local models (Llama2) via Ollama
- Cloud model support (OpenAI)
- Quality metrics tracking
- Batch processing capabilities
- Response quality scoring

## Installation

1. Install Poetry (package manager):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

3. Install Ollama for local model support:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

4. Pull the Llama2 model:
```bash
ollama pull llama2
```

## Usage

Basic usage example:

```python
from dspy_local_optimizer import BatchOptimizedGuidelineManager

# Initialize optimizer
optimizer = BatchOptimizedGuidelineManager(
    model_name="ollama/llama2",  # or "openai/gpt-3.5-turbo"
    use_optimizer=True
)

# Run optimization
optimized = optimizer.optimize_guidelines(
    guidelines=your_guidelines,
    examples=training_data,
    batch_size=5
)
```

For more examples, see the `scripts` directory.

## Development

1. Run tests:
```bash
poetry run pytest
```

2. Run quality checks:
```bash
poetry run ruff check .
```

## License

MIT License

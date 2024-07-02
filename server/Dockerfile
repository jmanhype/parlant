FROM python:3.12-slim

ENV POETRY_VERSION=1.8.3
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Set PYTHONPATH to recognize the emcie packages.
ENV PYTHONPATH=/app/src

RUN pip install poetry==$POETRY_VERSION

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-dev

COPY src /app/src
COPY bin /app/bin

# Expose the port your app runs on
EXPOSE 8000

CMD ["poetry", "run", "python", "/app/bin/emcie-server", "-c", "/mnt/data/config.json"]
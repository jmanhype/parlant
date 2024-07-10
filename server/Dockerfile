FROM python:3.12-slim

ENV POETRY_VERSION=1.8.3
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CXXFLAGS='-std=c++11'
ENV PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y g++ && rm -rf /var/lib/apt/lists/*
RUN pip install poetry==$POETRY_VERSION

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-dev

RUN pip install "chromadb==0.5.3" "tinydb==4.8.0"

COPY src /app/src
COPY bin /app/bin

# Expose the port your app runs on
EXPOSE 8000

CMD ["poetry", "run", "python", "/app/bin/emcie-server", "run"]

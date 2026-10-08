# --- STAGE 1: Base Environment ---
FROM python:3.11-slim AS base

WORKDIR /apps/martiadrogue/data-reaper

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG USERNAME=data-reaper-app
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Mount point of the validated CSVs (`dataset_import_dir`); Compose binds
# the host folder over it, read-only.
RUN mkdir -p /var/lib/data_reaper/csv


# --- STAGE 2: Development Builder ---
FROM base AS builder-dev

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN mkdir -p backend/src/data_reaper && touch backend/src/data_reaper/__init__.py

RUN pip install --no-cache-dir --upgrade pip \
    && pip install ".[dev]" --no-cache-dir .


# --- STAGE 3: Development Runtime Target ---
FROM base AS development

COPY --from=builder-dev /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder-dev /usr/local/bin /usr/local/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    jq \
    && rm -rf /var/lib/apt/lists/*

COPY ./backend/src ./backend/src
COPY pyproject.toml README.md ./
RUN pip install -e . --no-deps

EXPOSE 8000
USER data-reaper-app

CMD ["uvicorn", "data_reaper.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

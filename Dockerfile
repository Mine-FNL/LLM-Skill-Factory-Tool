# syntax=docker/dockerfile:1.7
#
# Multi-stage build: a builder stage that compiles the package, then a slim
# runtime stage that ships only what's needed to run the app. Non-root user,
# HEALTHCHECK wired to the in-tree healthcheck module.

ARG PYTHON_VERSION=3.11
ARG STREAMLIT_VERSION=1.36

# ---- builder ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Build dependencies (only needed if any package has a native component; kept
# minimal — the current requirements are pure-Python).
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# Install the runtime deps into a prefix we'll copy into the runtime stage.
RUN pip install --prefix=/install -r requirements.txt

# ---- runtime ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Create a non-root user. UID 10001 is well outside the typical human-user
# range, so file ownership in mounted volumes is unambiguous.
RUN groupadd --system --gid 10001 sf \
    && useradd  --system --uid 10001 --gid sf --home-dir /app --shell /usr/sbin/nologin sf

WORKDIR /app

# Copy the prebuilt deps from the builder.
COPY --from=builder /install /usr/local

# Copy the application source.
COPY --chown=sf:sf app.py ./
COPY --chown=sf:sf skill_factory ./skill_factory
COPY --chown=sf:sf ui ./ui
COPY --chown=sf:sf .streamlit ./.streamlit
COPY --chown=sf:sf .env.example ./
COPY --chown=sf:sf presets ./presets
COPY --chown=sf:sf examples ./examples

# Generated skills live here by default; make the directory writable for the
# non-root user so SKILLS_DIR=/app/skills works out of the box.
RUN mkdir -p /app/skills && chown -R sf:sf /app

USER sf

EXPOSE 8501

# HEALTHCHECK uses the in-tree module so production deployments can `docker ps`
# to see whether the app is ready. Adjust interval/timeout to taste.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-m", "skill_factory.healthcheck", "--quiet"]

# Provide a provider key at runtime, e.g.:
#   docker run -p 8501:8501 -e OPENROUTER_API_KEY=sk-or-... skill-factory
#   docker run -p 8501:8501 -e LLM_PROVIDER=kimi    -e MOONSHOT_API_KEY=...   skill-factory
#   docker run -p 8501:8501 -e LLM_PROVIDER=minimax -e MINIMAX_API_KEY=...    skill-factory
CMD ["streamlit", "run", "app.py"]

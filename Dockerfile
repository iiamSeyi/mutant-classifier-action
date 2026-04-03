# Dockerfile
# ==========
# This container is the runtime environment for the entire tool.
# It needs to contain:
#   - Java 17 (to compile and run the target project + PIT)
#   - Maven (to invoke PIT via mvn pitest:mutationCoverage)
#   - Python 3.11 (to run our classifier script)
#   - Python dependencies (PyTorch, etc. - stubs for Phase 1, real for Phase 3)
#
# We use a multi-stage build to keep the final image lean:
#   Stage 1 (builder): install Python deps into a venv
#   Stage 2 (runtime): copy only what's needed to run
#
# Why Eclipse Temurin base image?
#   - Official, well-maintained Java image
#   - Available for multiple architectures (important for GitHub-hosted runners)
#   - Includes Maven in the 'temurin' variants

# ── Stage 1: Python dependency builder ────────────────────────────────────────
FROM eclipse-temurin:17-jdk-jammy AS python-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtual environment for Python deps
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python requirements
# In Phase 1, this is lightweight (just xml parsing + json).
# In Phase 3, we add: torch, gensim (Word2Vec), javalang (AST)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime image ─────────────────────────────────────────────────────
FROM eclipse-temurin:17-jdk-jammy AS runtime

LABEL org.opencontainers.image.title="Equivalent Mutant Classifier"
LABEL org.opencontainers.image.description="PIT + ML classifier for equivalent mutant detection"

# Install Maven and Python runtime (no dev tools needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    maven \
    python3.11 \
    python3.11-venv \
    && rm -rf /var/lib/apt/lists/*

# Copy the Python venv from builder stage
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set up working directory for our tool's scripts
WORKDIR /action

# Copy our tool's Python script and any supporting files
COPY classify.py .
COPY entrypoint.sh .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# GitHub Actions mounts the calling repo at /github/workspace
# Our entrypoint changes into the right subdirectory before running Maven
ENTRYPOINT ["/action/entrypoint.sh"]
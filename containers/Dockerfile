# Claude Conductor - Multi-stage build for production
FROM ubuntu:22.04 AS base

# Build arguments
ARG PYTHON_VERSION=3.10
ARG NODE_VERSION=18
ARG CLAUDE_CODE_VERSION=latest

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WORKSPACE_DIR=/workspace \
    CLAUDE_USER=claude \
    CLAUDE_UID=1000 \
    CLAUDE_GID=1000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    curl \
    wget \
    git \
    unzip \
    ca-certificates \
    gnupg2 \
    lsb-release \
    # Build tools
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    # Python dependencies
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    # System utilities
    htop \
    vim \
    nano \
    jq \
    tree \
    # Network utilities
    netcat \
    telnet \
    # Process management
    supervisor \
    # Cleanup
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Node.js LTS
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create user and group (without sudo access for security)
RUN groupadd -g ${CLAUDE_GID} ${CLAUDE_USER} \
    && useradd -m -u ${CLAUDE_UID} -g ${CLAUDE_GID} -s /bin/bash ${CLAUDE_USER} \
    && mkdir -p ${WORKSPACE_DIR} \
    && chown -R ${CLAUDE_USER}:${CLAUDE_USER} ${WORKSPACE_DIR}

# Install uv for Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.cargo/bin/uv /usr/local/bin/uv \
    && uv --version

# Development stage
FROM base AS development

# Install development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdb \
    strace \
    valgrind \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files for development
COPY --chown=${CLAUDE_USER}:${CLAUDE_USER} pyproject.toml /app/pyproject.toml
COPY --chown=${CLAUDE_USER}:${CLAUDE_USER} .python-version /app/.python-version

# Install development packages using uv
RUN cd /app && \
    uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install -e ".[dev]"

# Production stage
FROM base AS production

# Copy application files
COPY --chown=${CLAUDE_USER}:${CLAUDE_USER} . /app
WORKDIR /app

# Install Claude Conductor using uv
RUN cd /app && \
    uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install -e ".[all]"

# Install Claude Code CLI (mock for now)
COPY --chown=${CLAUDE_USER}:${CLAUDE_USER} containers/install-claude-code.sh /tmp/install-claude-code.sh
RUN chmod +x /tmp/install-claude-code.sh && bash /tmp/install-claude-code.sh

# Create necessary directories
RUN mkdir -p \
    ${WORKSPACE_DIR} \
    /home/${CLAUDE_USER}/.conductor \
    /home/${CLAUDE_USER}/.cache \
    /var/log/conductor \
    && chown -R ${CLAUDE_USER}:${CLAUDE_USER} \
        ${WORKSPACE_DIR} \
        /home/${CLAUDE_USER}/.conductor \
        /home/${CLAUDE_USER}/.cache \
        /var/log/conductor

# Copy configuration files
COPY --chown=${CLAUDE_USER}:${CLAUDE_USER} containers/supervisor.conf /etc/supervisor/conf.d/conductor.conf
COPY --chown=${CLAUDE_USER}:${CLAUDE_USER} containers/entrypoint.sh /entrypoint.sh
COPY --chown=${CLAUDE_USER}:${CLAUDE_USER} containers/healthcheck.sh /healthcheck.sh

# Make scripts executable
RUN chmod +x /entrypoint.sh /healthcheck.sh

# Set up volumes
VOLUME ["${WORKSPACE_DIR}", "/var/log/conductor"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /healthcheck.sh

# Expose ports
EXPOSE 8080 8081

# Switch to non-root user
USER ${CLAUDE_USER}
WORKDIR ${WORKSPACE_DIR}

# Labels for metadata
LABEL maintainer="Claude Conductor Team" \
      version="1.0.0" \
      description="Claude Conductor Multi-Agent Orchestration System" \
      org.opencontainers.image.title="Claude Conductor" \
      org.opencontainers.image.description="Multi-agent orchestration system for Claude Code instances" \
      org.opencontainers.image.vendor="Claude Conductor Team" \
      org.opencontainers.image.licenses="MIT"

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Entry point
ENTRYPOINT ["/entrypoint.sh"]
CMD ["orchestrator"]
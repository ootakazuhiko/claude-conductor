# Claude Code Agent Container
FROM ubuntu:22.04

# 環境変数設定
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 基本パッケージのインストール
RUN apt-get update && apt-get install -y \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    build-essential \
    ca-certificates \
    gnupg \
    lsb-release \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Node.js LTS版のインストール
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs

# Python環境のセットアップ
RUN python3 -m pip install --upgrade pip setuptools wheel

# Claude Code CLIのインストール準備
# TODO: 実際のClaude Code CLIがリリースされたら、ここを更新する
COPY containers/install-claude-code.sh /tmp/install-claude-code.sh
RUN chmod +x /tmp/install-claude-code.sh && /tmp/install-claude-code.sh

# 作業ディレクトリの設定
WORKDIR /workspace

# 非rootユーザーの作成
RUN useradd -m -s /bin/bash claude && \
    usermod -aG sudo claude && \
    echo 'claude ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# ユーザー切り替え
USER claude

# エントリーポイント
COPY containers/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["claude-code", "--headless"]
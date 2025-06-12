#!/bin/bash
# Claude Code Container Entrypoint

set -e

echo "Starting Claude Code Agent Container..."

# 環境変数の確認
echo "Agent ID: ${AGENT_ID:-unknown}"
echo "Workspace: ${WORKSPACE:-/workspace}"

# ワークスペースディレクトリの作成
mkdir -p "${WORKSPACE:-/workspace}"
cd "${WORKSPACE:-/workspace}"

# Git設定（コンテナ内での作業用）
if [ ! -f ~/.gitconfig ]; then
    git config --global user.name "Claude Agent"
    git config --global user.email "agent@claude-conductor.local"
    git config --global init.defaultBranch main
fi

# Claude Code CLIの確認
if command -v claude-code > /dev/null; then
    echo "Claude Code CLI is available"
    claude-code --version
else
    echo "Warning: Claude Code CLI not found"
fi

# 引数に基づいてコマンドを実行
exec "$@"
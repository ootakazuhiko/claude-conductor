# Claude Conductor

A multi-agent orchestration system for Claude Code instances, enabling parallel execution and coordinated task distribution across multiple containerized agents.

複数のClaude Codeインスタンスを統合管理する多エージェント・オーケストレーション・システム。並列実行と協調タスク分散を実現します。

## Overview

Claude Conductor allows you to run multiple Claude Code instances in headless mode within isolated containers (Podman/Docker), coordinate their work through an Agent2Agent protocol, and distribute complex tasks efficiently across the fleet.

Claude Conductorは、複数のClaude Codeインスタンスを独立したコンテナ（Podman/Docker）内でヘッドレスモードで実行し、Agent2Agentプロトコルを通じて作業を調整し、複雑なタスクを効率的に分散処理できるシステムです。

## Features

- **Multi-Agent Orchestration**: Manage multiple Claude Code agents simultaneously
- **Containerized Isolation**: Each agent runs in its own Podman/Docker container
- **Agent2Agent Protocol**: Inter-agent communication for task coordination
- **Task Distribution**: Intelligent task scheduling and load balancing
- **Parallel Execution**: Execute multiple tasks concurrently
- **Health Monitoring**: Automatic health checks and recovery
- **Flexible Configuration**: YAML-based configuration system

**機能**

- **マルチエージェント・オーケストレーション**: 複数のClaude Codeエージェントを同時管理
- **コンテナ隔離**: 各エージェントが独自のPodman/Dockerコンテナで実行
- **Agent2Agentプロトコル**: タスク調整のためのエージェント間通信
- **タスク分散**: インテリジェントなタスクスケジューリングと負荷分散
- **並列実行**: 複数タスクの同時実行
- **ヘルスモニタリング**: 自動ヘルスチェックと復旧機能
- **柔軟な設定**: YAML設定システム

## Quick Start

### Prerequisites

- Python 3.9+
- Podman or Docker
- Claude Code CLI

### Installation (Using uv - Recommended)

1. Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the repository:
```bash
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor
```

3. Set up the environment:
```bash
uv venv
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate  # On Windows

uv pip install -e ".[all]"
```

### Installation (Traditional method)

1. Clone the repository:
```bash
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor
```

2. Set up the environment:
```bash
chmod +x setup_project.sh
./setup_project.sh
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## クイックスタート

### 前提条件

- Python 3.9+
- Podman または Docker
- Claude Code CLI

### インストール (uvを使用 - 推奨)

1. uvをインストール:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. リポジトリをクローン:
```bash
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor
```

3. 環境をセットアップ:
```bash
uv venv
source .venv/bin/activate  # Linux/macOSの場合
# または
.venv\Scripts\activate  # Windowsの場合

uv pip install -e ".[all]"
```

### インストール (従来の方法)

1. リポジトリをクローン:
```bash
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor
```

2. 環境をセットアップ:
```bash
chmod +x setup_project.sh
./setup_project.sh
```

3. 依存関係をインストール:
```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from conductor import Orchestrator, Task

# Create orchestrator with 3 agents
orchestrator = Orchestrator()
orchestrator.config["num_agents"] = 3
orchestrator.start()

# Execute a code review task
task = Task(
    task_type="code_review",
    description="Review Python files for style and bugs",
    files=["src/main.py", "src/utils.py"]
)

result = orchestrator.execute_task(task)
print(f"Task completed: {result.status}")

orchestrator.stop()
```

### 基本的な使用方法

```python
from conductor import Orchestrator, Task

# 3つのエージェントでオーケストレーターを作成
orchestrator = Orchestrator()
orchestrator.config["num_agents"] = 3
orchestrator.start()

# コードレビュータスクを実行
task = Task(
    task_type="code_review",
    description="Review Python files for style and bugs",
    files=["src/main.py", "src/utils.py"]
)

result = orchestrator.execute_task(task)
print(f"Task completed: {result.status}")

orchestrator.stop()
```

## Architecture

```
┌─────────────────┐
│   Orchestrator  │  Central coordination
└─────────┬───────┘
          │
    ┌─────┴─────┐
    │  Message  │  Agent2Agent Protocol
    │  Broker   │
    └─────┬─────┘
          │
   ┌──────┼──────┐
   │      │      │
┌──▼──┐ ┌─▼───┐ ┌─▼───┐
│Agent│ │Agent│ │Agent│  Claude Code Instances
│  1  │ │  2  │ │  3  │  (Podman Containers)
└─────┘ └─────┘ └─────┘
```

## アーキテクチャ

```
┌─────────────────┐
│   Orchestrator  │  中央調整
└─────────┬───────┘
          │
    ┌─────┴─────┐
    │  Message  │  Agent2Agentプロトコル
    │  Broker   │
    └─────┬─────┘
          │
   ┌──────┼──────┐
   │      │      │
┌──▼──┐ ┌─▼───┐ ┌─▼───┐
│Agent│ │Agent│ │Agent│  Claude Codeインスタンス
│  1  │ │  2  │ │  3  │  (Podmanコンテナ)
└─────┘ └─────┘ └─────┘
```

## Project Structure

```
claude-conductor/
├── README.md
├── LICENSE
├── .github/workflows/     # CI/CD workflows
├── conductor/             # Main package
│   ├── __init__.py
│   ├── orchestrator.py    # Main orchestration logic
│   ├── agent.py          # Agent wrapper and management
│   └── protocol.py       # Agent2Agent communication
├── containers/           # Docker/Podman configurations
├── examples/            # Usage examples
├── tests/              # Test suite
├── docs/               # Documentation
└── scripts/            # Utility scripts
```

## プロジェクト構造

```
claude-conductor/
├── README.md
├── LICENSE
├── .github/workflows/     # CI/CDワークフロー
├── conductor/             # メインパッケージ
│   ├── __init__.py
│   ├── orchestrator.py    # メインオーケストレーションロジック
│   ├── agent.py          # エージェントラッパーと管理
│   └── protocol.py       # Agent2Agent通信
├── containers/           # Docker/Podman設定
├── examples/            # 使用例
├── tests/              # テストスイート
├── docs/               # ドキュメント
└── scripts/            # ユーティリティスクリプト
```

## Configuration

Configure the system using `config/config.yaml`:

```yaml
orchestrator:
  num_agents: 3
  max_workers: 10
  task_timeout: 300

agent:
  container_memory: "2g"
  container_cpu: "1.0"
  health_check_interval: 30

communication:
  socket_path: "/tmp/claude_orchestrator.sock"
  message_timeout: 5.0
```

## 設定

`config/config.yaml`を使用してシステムを設定:

```yaml
orchestrator:
  num_agents: 3              # エージェント数
  max_workers: 10            # 最大ワーカー数
  task_timeout: 300          # タスクタイムアウト（秒）

agent:
  container_memory: "2g"     # コンテナメモリ制限
  container_cpu: "1.0"       # コンテナCPU制限
  health_check_interval: 30  # ヘルスチェック間隔（秒）

communication:
  socket_path: "/tmp/claude_orchestrator.sock"  # ソケットパス
  message_timeout: 5.0       # メッセージタイムアウト（秒）
```

## Task Types

- **code_review**: Analyze code for issues and improvements
- **refactor**: Restructure code while maintaining functionality
- **test_generation**: Generate comprehensive test suites
- **analysis**: Perform code analysis and documentation
- **generic**: Execute custom commands

## タスクタイプ

- **code_review**: コードの問題点と改善点を分析
- **refactor**: 機能を維持しながらコードを再構築
- **test_generation**: 包括的なテストスイートを生成
- **analysis**: コード分析とドキュメント作成
- **generic**: カスタムコマンドを実行

## Development

### Running Tests

```bash
./tests/run_tests.sh
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 開発

### テストの実行

```bash
./tests/run_tests.sh
```

### 貢献方法

1. リポジトリをフォーク
2. 機能ブランチを作成
3. 変更を実装
4. テストを追加
5. プルリクエストを送信

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ライセンス

このプロジェクトはMITライセンスの下でライセンスされています。詳細は[LICENSE](LICENSE)ファイルをご覧ください。

## Roadmap

- [ ] Kubernetes deployment support
- [ ] Redis-based message broker
- [ ] Web UI for monitoring
- [ ] Auto-scaling capabilities
- [ ] Distributed deployment
- [ ] Performance metrics dashboard

## ロードマップ

- [ ] Kubernetesデプロイメントサポート
- [ ] Redisベースメッセージブローカー
- [ ] 監視用Web UI
- [ ] オートスケーリング機能
- [ ] 分散デプロイメント
- [ ] パフォーマンスメトリクスダッシュボード

## Support

For issues and questions, please open an issue on the [GitHub repository](https://github.com/ootakazuhiko/claude-conductor/issues).

## サポート

問題や質問については、[GitHubリポジトリ](https://github.com/ootakazuhiko/claude-conductor/issues)でイシューを作成してください。
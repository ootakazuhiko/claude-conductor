# Claude Conductor - Isolated Workspaces

## 概要

隔離されたワークスペース機能により、各エージェントが独立したPodmanコンテナ内で開発対象システムの動作確認を行えます。これにより、以下のメリットが得られます：

- **完全な環境分離**: 各エージェントが独自のファイルシステム、ネットワーク、プロセス空間を持つ
- **再現性の確保**: 同じ環境を何度でも再構築可能
- **安全な実験**: ホストシステムに影響を与えずにコードを実行
- **並列開発**: 複数の異なる環境を同時に実行可能

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│                  Host System                        │
│  ┌───────────────────────────────────────────────┐ │
│  │           Claude Conductor Core                │ │
│  │  ┌─────────────┐  ┌────────────────────────┐ │ │
│  │  │Orchestrator │  │ Workspace Isolation     │ │ │
│  │  │             │  │ Manager                  │ │ │
│  │  └──────┬──────┘  └───────────┬──────────────┘ │ │
│  └─────────┼─────────────────────┼───────────────┘ │
│            │                     │                   │
│  ┌─────────▼──────────┐ ┌───────▼────────┐        │
│  │   Agent 1          │ │   Agent 2      │        │
│  │ ┌────────────────┐ │ │ ┌────────────┐ │        │
│  │ │ Python Dev     │ │ │ │ Node.js    │ │        │
│  │ │ Container      │ │ │ │ Container  │ │        │
│  │ │ ┌────────────┐ │ │ │ │ ┌────────┐ │ │        │
│  │ │ │ Workspace  │ │ │ │ │ │Workspace│ │ │        │
│  │ │ │ /workspace │ │ │ │ │ │/workspace │ │        │
│  │ │ └────────────┘ │ │ │ │ └────────┘ │ │        │
│  │ └────────────────┘ │ │ └────────────┘ │        │
│  └────────────────────┘ └────────────────┘        │
└─────────────────────────────────────────────────────┘
```

## 機能

### 1. 環境プリセット

事前定義された開発環境：

- **python-dev**: Python開発環境（pytest, black, flake8含む）
- **nodejs-dev**: Node.js開発環境（jest, eslint, prettier含む）
- **fullstack**: フルスタック開発環境（Python, Node.js, データベースツール）
- **minimal**: 最小構成（git, curl のみ）
- **python-ml**: データサイエンス環境（Jupyter, pandas, scikit-learn）

### 2. ワークスペース管理

- **自動作成**: タスク実行時に自動的にワークスペースを作成
- **永続化**: ボリュームマウントによるデータの永続化
- **スナップショット**: 任意の時点での状態保存と復元
- **クリーンアップ**: 使用後の自動削除またはデバッグ用の保持

### 3. リソース制御

- **メモリ制限**: エージェントごとのメモリ使用量制限
- **CPU制限**: CPU使用率の制限
- **ストレージ制限**: ワークスペースサイズの制限
- **ネットワーク分離**: 専用ネットワークでの通信

## 設定

### 基本設定 (`config/standalone-isolated.yaml`)

```yaml
# 隔離ワークスペースの有効化
isolated_workspace:
  enabled: true
  mode: "sandbox"  # sandbox | shared | hybrid
  
  # エージェントコンテナ設定
  agent_containers:
    base_image: "ubuntu:22.04"
    persistent_volumes: true
    volume_size: "10Gi"
    
    # リソース制限
    resources:
      requests:
        memory: "512Mi"
        cpu: "0.5"
      limits:
        memory: "2Gi"
        cpu: "1.0"

# Podman設定
podman_config:
  network:
    name: "claude-dev-net"
    subnet: "10.89.0.0/24"
  security:
    userns: "keep-id"
```

### カスタム環境の定義

```yaml
isolated_workspace:
  agent_containers:
    environments:
      - name: "custom-env"
        dockerfile: |
          FROM ubuntu:22.04
          RUN apt-get update && apt-get install -y \
              python3 python3-pip \
              nodejs npm \
              postgresql-client \
              redis-tools
          WORKDIR /workspace
        volumes:
          - "source:/workspace/src"
          - "cache:/workspace/.cache"
```

## 使用方法

### 1. 起動

```bash
# 隔離ワークスペースモードで起動
./scripts/start-isolated.sh

# 停止
./scripts/start-isolated.sh stop
```

### 2. タスクの実行

#### Python開発環境でのテスト実行

```bash
curl -X POST http://localhost:8081/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "task_type": "isolated_execution",
    "description": "Run Python tests",
    "environment": "python-dev",
    "commands": [
      "cd /workspace/src",
      "python -m pytest tests/"
    ]
  }'
```

#### Node.jsプロジェクトのビルド

```bash
curl -X POST http://localhost:8081/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "task_type": "isolated_execution",
    "description": "Build Node.js project",
    "environment": "nodejs-dev",
    "commands": [
      "cd /workspace/src",
      "npm install",
      "npm run build",
      "npm test"
    ]
  }'
```

#### フルスタック統合テスト

```bash
curl -X POST http://localhost:8081/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "task_type": "isolated_execution",
    "description": "Run integration tests",
    "environment": "fullstack",
    "services": ["postgres:14", "redis:7"],
    "commands": [
      "cd /workspace",
      "./scripts/setup-dev.sh",
      "./scripts/run-integration-tests.sh"
    ]
  }'
```

### 3. スナップショット管理

```python
# Pythonスクリプトでの例
from conductor.workspace_isolation import WorkspaceIsolationManager

manager = WorkspaceIsolationManager(config)

# スナップショットの作成
await manager.create_snapshot(agent_id, "before-deployment")

# 作業を実行...

# 問題が発生した場合は復元
await manager.restore_snapshot(agent_id, "before-deployment")
```

## 高度な使用例

### 1. CI/CDパイプライン統合

```yaml
# .github/workflows/test.yml
name: Isolated Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start Claude Conductor
        run: |
          ./scripts/start-isolated.sh
          
      - name: Run isolated tests
        run: |
          curl -X POST http://localhost:8081/tasks \
            -H 'Content-Type: application/json' \
            -d @tests/isolated-test-suite.json
```

### 2. 並列テスト実行

```python
async def run_parallel_tests():
    tasks = []
    
    # Python テスト
    tasks.append(create_task(
        task_type="isolated_execution",
        environment="python-dev",
        commands=["pytest tests/unit/", "pytest tests/integration/"]
    ))
    
    # JavaScript テスト
    tasks.append(create_task(
        task_type="isolated_execution",
        environment="nodejs-dev",
        commands=["npm test", "npm run e2e"]
    ))
    
    # 並列実行
    results = await orchestrator.execute_parallel_tasks(tasks)
```

### 3. セキュリティスキャン

```bash
# 隔離環境でのセキュリティスキャン
curl -X POST http://localhost:8081/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "task_type": "isolated_execution",
    "description": "Security scan",
    "environment": "security-tools",
    "commands": [
      "cd /workspace",
      "bandit -r src/",
      "safety check",
      "npm audit"
    ]
  }'
```

## トラブルシューティング

### Podmanが見つからない

```bash
# Podmanのインストール
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y podman

# RHEL/CentOS/Fedora
sudo dnf install -y podman

# macOS
brew install podman
```

### コンテナが起動しない

```bash
# Podmanの状態確認
podman system info

# ログの確認
podman logs claude-agent-<agent-id>

# コンテナの手動削除
podman rm -f $(podman ps -a --filter "name=claude-agent-*" -q)
```

### ワークスペースの手動クリーンアップ

```bash
# 全ワークスペースの削除
rm -rf ~/.claude-conductor/isolated/*

# 未使用イメージの削除
podman image prune -a
```

## パフォーマンス最適化

### 1. イメージのキャッシュ

```yaml
# ベースイメージを事前にプル
podman_config:
  preload_images:
    - "python:3.11-slim"
    - "node:18-alpine"
    - "ubuntu:22.04"
```

### 2. ボリュームの最適化

```yaml
storage:
  volumes:
    driver: "overlay"
    options:
      - "size=5G"
      - "inodes=100k"
```

### 3. ネットワークパフォーマンス

```yaml
podman_config:
  network:
    mtu: 9000  # ジャンボフレーム
    driver: "bridge"
```

## セキュリティ考慮事項

### 1. 権限の制限

- 非rootユーザーでの実行
- 最小権限の原則
- Capabilityの削除

### 2. ネットワーク分離

- 専用ネットワークの使用
- 外部アクセスの制限
- ポート公開の最小化

### 3. リソース制限

- メモリ・CPU制限の強制
- ディスククォータ
- プロセス数制限

## まとめ

隔離されたワークスペース機能により、Claude Conductorは安全で再現性の高い開発・テスト環境を提供します。各エージェントが独立した環境で動作することで、複雑なシステムの開発やテストを効率的に行うことができます。
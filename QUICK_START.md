# Claude Conductor - Quick Start Guide

手軽に単一のPCでClaude Conductorを試すためのガイドです。

## 🚀 ワンコマンドインストール

```bash
# リポジトリをクローン
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor

# スタンドアロン版ブランチに切り替え
git checkout feature/standalone-subset

# インストールと起動
./quick-start.sh
```

これだけで完了です！ダッシュボードが http://localhost:8080 で利用可能になります。

## 📋 システム要件

- **Python 3.10+** (推奨: 3.11)
- **メモリ**: 最低2GB、推奨4GB
- **ディスク**: 最低1GB空き容量
- **OS**: Linux、macOS、Windows (WSL2)

### オプション要件
- **Docker/Podman**: コンテナモード使用時
- **Git**: ソースコードのクローン用

## 🎯 使用方法

### 基本コマンド

```bash
# システム開始
conductor start

# コンテナモードで開始
conductor start-container

# 状態確認
conductor status

# ダッシュボードを開く
conductor dashboard

# テスト実行
conductor test

# システム停止
conductor stop
```

### Webダッシュボード

1. ブラウザで http://localhost:8080 にアクセス
2. 右側の「Submit Task」でタスクを送信
3. リアルタイムでエージェントの状態を監視

## 📁 ディレクトリ構造

```
~/.claude-conductor/
├── config/           # 設定ファイル
│   └── config.yaml
├── workspace/        # 作業ディレクトリ
├── logs/            # ログファイル
├── venv/            # Python仮想環境
└── conductor        # CLIツール
```

## ⚙️ 設定のカスタマイズ

### エージェント数の変更

```yaml
# ~/.claude-conductor/config/config.yaml
num_agents: 3        # デフォルト: 2
max_workers: 6       # デフォルト: 4
```

### リソース制限の調整

```yaml
container_config:
  memory_limit: "2g"   # デフォルト: 1g
  cpu_limit: "1.0"     # デフォルト: 0.5
```

### ポート番号の変更

```yaml
network:
  dashboard_port: 8080  # Webダッシュボード
  api_port: 8081       # API (オプション)
```

## 🧪 サンプルタスク

### 1. 基本的なコマンド実行

```bash
# Webダッシュボードから送信
Task Type: Generic
Description: echo "Hello, Claude Conductor!"
Priority: 5
```

### 2. ファイル解析

```bash
# まずサンプルファイルを作成
echo "def hello(): print('Hello')" > ~/.claude-conductor/workspace/sample.py

# Webダッシュボードから送信  
Task Type: Code Review
Description: Review Python code
Files: sample.py
Priority: 7
```

### 3. CLIからのテスト

```bash
# 基本テスト
conductor test

# カスタムタスクの作成 (Python)
python3 -c "
from conductor import create_task, Orchestrator
task = create_task(
    task_type='analysis',
    description='Analyze project structure', 
    priority=6
)
print(f'Task created: {task.task_id}')
"
```

## 🐳 Dockerモード

### 基本的な使用

```bash
# Docker Composeで起動
docker-compose -f docker-compose.standalone.yml up

# バックグラウンドで起動
docker-compose -f docker-compose.standalone.yml up -d

# 停止
docker-compose -f docker-compose.standalone.yml down
```

### ファイルサーバー付きで起動

```bash
# Webベースのファイルブラウザも起動
docker-compose -f docker-compose.standalone.yml --profile files up

# ファイルアクセス: http://localhost:8090
```

## 🔧 トラブルシューティング

### よくある問題

1. **ポート8080が使用中**
   ```bash
   # ポート確認
   lsof -i :8080
   
   # 設定変更
   conductor config
   # dashboard_port: 8888 に変更
   ```

2. **Pythonバージョンエラー**
   ```bash
   # Pythonバージョン確認
   python3 --version
   
   # 要求: Python 3.10+
   ```

3. **メモリ不足**
   ```bash
   # 設定でエージェント数を削減
   conductor config
   # num_agents: 1 に変更
   ```

### ログの確認

```bash
# リアルタイムログ
conductor logs

# 詳細ログファイル
tail -f ~/.claude-conductor/logs/*.log

# エラーログのみ
grep ERROR ~/.claude-conductor/logs/*.log
```

### 完全な再インストール

```bash
# 停止
conductor stop

# アンインストール
./quick-start.sh uninstall

# 再インストール
./quick-start.sh install
```

## 📊 パフォーマンスチューニング

### 軽量設定 (低スペックPC向け)

```yaml
num_agents: 1
max_workers: 2
container_config:
  memory_limit: "512m"
  cpu_limit: "0.25"
```

### 高性能設定 (高スペックPC向け)

```yaml
num_agents: 4
max_workers: 8
container_config:
  memory_limit: "4g" 
  cpu_limit: "2.0"
```

## 🔒 セキュリティ

スタンドアロン版は**ローカル専用**として設計されています：

- APIは127.0.0.1のみでリッスン
- 認証は無効化
- HTTPSは無効化
- 外部ネットワークアクセス制限

**本番環境では使用しないでください。**

## 🚀 次のステップ

1. **本格運用**: メインブランチのフル機能版を検討
2. **クラスタ展開**: Kubernetes設定を利用
3. **カスタム拡張**: エージェントの追加やカスタムタスクタイプ
4. **監視強化**: Prometheus + Grafana統合

## 📚 参考資料

- **メインドキュメント**: `README.md`
- **設定リファレンス**: `config/standalone.yaml`
- **API文書**: http://localhost:8080/docs (起動後)
- **ログ形式**: `~/.claude-conductor/logs/`

## 💬 サポート

問題が発生した場合：

1. `conductor status` で状態確認
2. `conductor logs` でログ確認  
3. GitHubでIssue報告
4. `./quick-start.sh uninstall` で完全削除

---

**重要**: これはスタンドアロン版です。本格的な本番環境利用には、メインブランチのフル機能版をご利用ください。
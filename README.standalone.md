# Claude Conductor - Standalone Subset

単一PCで手軽にClaude Conductorを試すためのサブセット版です。

## 🎯 概要

この`feature/standalone-subset`ブランチは、以下のような方に最適です：

- **Claude Conductorを手軽に試したい**
- **単一PCでの軽量運用**
- **開発・学習目的での利用**
- **複雑な設定なしでの実行**

## 🚀 インストール方法

### 方法1: フル機能版（推奨）

```bash
# リポジトリクローン
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor

# スタンドアロンブランチに切り替え
git checkout feature/standalone-subset

# ワンコマンドセットアップ
./quick-start.sh
```

### 方法2: 超簡単版

```bash
# 最小限のデモ版
curl -sSL https://raw.githubusercontent.com/ootakazuhiko/claude-conductor/feature/standalone-subset/simple-setup.sh | bash
```

## 🎮 使用方法

### フル機能版の場合

```bash
# システム起動
conductor start

# Webダッシュボード
conductor dashboard  # http://localhost:8080

# テスト実行
conductor test

# システム停止
conductor stop
```

### Dockerモードの場合

```bash
# Docker Composeで起動
docker-compose -f docker-compose.standalone.yml up

# ファイルサーバー付き
docker-compose -f docker-compose.standalone.yml --profile files up
```

## 📊 機能比較

| 機能 | Standalone版 | Full版 |
|------|-------------|--------|
| 基本オーケストレーション | ✅ | ✅ |
| Webダッシュボード | ✅ | ✅ |
| コンテナ統合 | ✅ | ✅ |
| エージェント数 | 1-4 | 無制限 |
| Redis統合 | ❌ | ✅ |
| Kubernetes | ❌ | ✅ |
| 監視・メトリクス | 基本のみ | 完全 |
| クラスタ機能 | ❌ | ✅ |
| 認証・セキュリティ | 無効 | 完全 |

## 📁 ディレクトリ構造

```
~/.claude-conductor/               # インストールディレクトリ
├── conductor*                     # CLIツール
├── config/
│   └── config.yaml               # 設定ファイル
├── workspace/                    # 作業ディレクトリ
├── logs/                        # ログファイル
├── venv/                        # Python仮想環境
├── start-local.sh*              # ローカル起動
├── start-container.sh*          # コンテナ起動
├── stop.sh*                     # 停止スクリプト
└── README.md                    # 詳細ドキュメント
```

## ⚙️ 設定

### 基本設定 (`config/config.yaml`)

```yaml
# エージェント数（1-4推奨）
num_agents: 2

# 同時実行数
max_workers: 4

# タスクタイムアウト（秒）
task_timeout: 120

# ログレベル
log_level: "INFO"

# リソース制限
container_config:
  memory_limit: "1g"
  cpu_limit: "0.5"
```

### 軽量設定例

```yaml
num_agents: 1
max_workers: 2
container_config:
  memory_limit: "512m"
  cpu_limit: "0.25"
```

## 🧪 サンプルタスク

### 1. 基本コマンド

```bash
# Webダッシュボードから実行
Task Type: Generic
Description: echo "Hello, Claude Conductor!"
Priority: 5
```

### 2. Pythonスクリプト実行例

```bash
# ファイル作成
echo 'print("Hello from Python!")' > ~/.claude-conductor/workspace/hello.py

# タスク実行
Task Type: Generic  
Description: python3 hello.py
Files: hello.py
```

### 3. CLIからの例

```bash
# サンプル実行
python3 examples/standalone_examples.py

# カスタムタスク
python3 -c "
from conductor import create_task
task = create_task(
    task_type='generic',
    description='date && hostname',
    priority=5
)
print(f'Task ID: {task.task_id}')
"
```

## 🐳 Docker使用例

### 基本起動

```bash
docker-compose -f docker-compose.standalone.yml up
```

### バックグラウンド起動

```bash
docker-compose -f docker-compose.standalone.yml up -d
```

### ファイルブラウザ付き

```bash
docker-compose -f docker-compose.standalone.yml --profile files up
# ファイルアクセス: http://localhost:8090
```

### ログ確認

```bash
docker-compose -f docker-compose.standalone.yml logs -f
```

## 🔧 トラブルシューティング

### よくある問題

1. **ポート競合**
   ```bash
   # ポート8080が使用中の場合
   conductor config
   # dashboard_port: 8888 に変更
   ```

2. **メモリ不足**
   ```bash
   # エージェント数を削減
   conductor config
   # num_agents: 1 に変更
   ```

3. **Python環境エラー**
   ```bash
   # 仮想環境の再作成
   conductor stop
   rm -rf ~/.claude-conductor/venv
   ./quick-start.sh
   ```

### ログ確認

```bash
# リアルタイムログ
conductor logs

# エラーログのみ
grep ERROR ~/.claude-conductor/logs/*.log

# 詳細ログ
tail -f ~/.claude-conductor/logs/*.log
```

### 完全リセット

```bash
# 完全アンインストール
./quick-start.sh uninstall

# または手動削除
rm -rf ~/.claude-conductor
```

## 🚀 パフォーマンス設定

### 低スペックPC (2GB RAM)

```yaml
num_agents: 1
max_workers: 2
container_config:
  memory_limit: "512m"
  cpu_limit: "0.25"
```

### 中スペックPC (4GB RAM)

```yaml
num_agents: 2
max_workers: 4
container_config:
  memory_limit: "1g"
  cpu_limit: "0.5"
```

### 高スペックPC (8GB+ RAM)

```yaml
num_agents: 4
max_workers: 8
container_config:
  memory_limit: "2g"
  cpu_limit: "1.0"
```

## 🔒 セキュリティについて

⚠️ **重要**: この版は**ローカル開発・テスト専用**です。

- 認証機能は無効
- HTTPSは無効
- 外部アクセス制限
- セキュリティ機能は最小限

**本番環境では絶対に使用しないでください。**

## 📈 本格運用への移行

Standalone版で満足できたら、以下を検討してください：

### 1. Full版への移行

```bash
# メインブランチに切り替え
git checkout main

# フル機能でセットアップ
./setup.py install
```

### 2. クラウド展開

```bash
# Kubernetes展開
kubectl apply -k k8s/

# Docker Swarm展開
docker stack deploy -c docker-compose.yml conductor
```

### 3. 監視・ロギング

```bash
# Prometheus + Grafana
docker-compose --profile monitoring up

# ELK Stack統合
# 詳細は docs/monitoring.md を参照
```

## 🆚 他のオーケストレーターとの比較

| 特徴 | Claude Conductor | Airflow | Prefect |
|------|-----------------|---------|---------|
| 学習コストの低さ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| セットアップの簡単さ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Claude統合 | ⭐⭐⭐⭐⭐ | ❌ | ❌ |
| 軽量性 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| エンタープライズ機能 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 📚 参考資料

- **完全ドキュメント**: [README.md](README.md)
- **クイックスタート**: [QUICK_START.md](QUICK_START.md)
- **サンプルコード**: [examples/](examples/)
- **設定リファレンス**: [config/standalone.yaml](config/standalone.yaml)

## 💬 コミュニティ・サポート

- **GitHub Issues**: バグ報告・機能要望
- **GitHub Discussions**: 使用方法・ベストプラクティス
- **Examples**: `examples/standalone_examples.py`

## 📄 ライセンス

MIT License - 商用・非商用問わず自由に利用可能

---

**🎯 まずは試してみましょう！**

```bash
./quick-start.sh && conductor start
```

ダッシュボード: http://localhost:8080
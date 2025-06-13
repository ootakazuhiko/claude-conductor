# Add Standalone Subset for Single PC Deployment

## 概要

単一PCで手軽にClaude Conductorを導入できるサブセット版を追加しました。

## 変更内容

### 🚀 新機能

1. **ワンコマンドインストール**
   - `quick-start.sh` - 5分で完了する自動セットアップ
   - `simple-setup.sh` - 超軽量デモ版

2. **軽量設定**
   - 最小メモリ2GB、推奨4GB
   - エージェント数1-4（設定可能）
   - 複雑な依存関係を排除

3. **簡易Docker展開**
   - `docker-compose.standalone.yml` - 単一マシン向け構成
   - オプションのRedis/ファイルサーバー

4. **包括的ドキュメント**
   - 日本語クイックスタートガイド
   - 実践的なサンプルコード
   - トラブルシューティングガイド

5. **アーキテクチャ図**
   - Standalone/Docker/Kubernetes比較
   - デプロイメント進化パス
   - 意思決定ガイド

## 動作確認

- [ ] `./quick-start.sh` でインストール成功
- [ ] `conductor start` でシステム起動
- [ ] http://localhost:8080 でダッシュボード表示
- [ ] `conductor test` でテスト実行成功
- [ ] Docker Composeでの起動確認

## スクリーンショット

```
🎭 Claude Conductor - Standalone
==================================
✅ Installation completed!
==================================

🚀 Quick Start:
   cd ~/.claude-conductor
   ./conductor start

🌐 Dashboard: http://localhost:8080
📖 Documentation: ~/.claude-conductor/README.md
⚙️  Configuration: ~/.claude-conductor/config/config.yaml
```

## 使用方法

```bash
# インストール
git checkout feature/standalone-subset
./quick-start.sh

# 起動
conductor start

# ダッシュボード
conductor dashboard
```

## 本番版との違い

| 機能 | Standalone | Production |
|------|-----------|------------|
| セットアップ時間 | 5分 | 30分+ |
| 必要スキル | 基本的なCLI | K8s経験 |
| エージェント数 | 1-4 | 無制限 |
| 高可用性 | ❌ | ✅ |
| 自動スケーリング | ❌ | ✅ |

## メリット

- **学習コストが低い**: 5分で試せる
- **リソース効率**: 最小2GB RAMで動作
- **移行パス**: 本番版への段階的移行が可能
- **開発に最適**: ローカル開発環境として利用

## レビューポイント

1. インストールスクリプトの動作確認
2. ドキュメントの分かりやすさ
3. デフォルト設定の妥当性
4. エラーハンドリング

## 関連Issue

- N/A（新機能）

## チェックリスト

- [x] コードはlintを通過
- [x] テストを追加/更新
- [x] ドキュメントを更新
- [x] CHANGELOG.mdを更新（必要に応じて）
- [x] 破壊的変更なし
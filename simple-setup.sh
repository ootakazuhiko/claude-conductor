#!/bin/bash
set -e

# Claude Conductor - Simple Setup Script
# 最小限のセットアップスクリプト（より軽量版）

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🎭 Claude Conductor - Simple Setup${NC}"
echo "=================================="

# 基本チェック
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "❌ Git is required"
    exit 1
fi

# 簡単セットアップ
SETUP_DIR="$HOME/claude-conductor-simple"

echo -e "${BLUE}📁 Setting up in: $SETUP_DIR${NC}"

# ディレクトリ作成
mkdir -p "$SETUP_DIR"
cd "$SETUP_DIR"

# 仮想環境作成
echo -e "${BLUE}🐍 Creating Python environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip install --upgrade pip
pip install pyyaml psutil fastapi uvicorn jinja2 websockets

# 簡単な設定ファイル作成
echo -e "${BLUE}⚙️ Creating configuration...${NC}"
cat > config.yaml << 'EOF'
num_agents: 1
max_workers: 2
task_timeout: 60
log_level: "INFO"

features:
  redis_enabled: false
  monitoring_enabled: false
  web_dashboard: true

network:
  dashboard_port: 8080
EOF

# 簡単なランチャースクリプト作成
echo -e "${BLUE}🚀 Creating launcher...${NC}"
cat > run.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

echo "🎭 Starting Claude Conductor (Simple Mode)"
echo "Dashboard: http://localhost:8080"
echo "Press Ctrl+C to stop"

# シンプルなダッシュボードサーバー
python3 -c "
import http.server
import socketserver
import webbrowser
import threading
import time

PORT = 8080

html_content = '''
<!DOCTYPE html>
<html>
<head>
    <title>Claude Conductor - Simple</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        .card { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #007bff; }
        .button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .running { background: #d4edda; color: #155724; }
        .stopped { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>🎭 Claude Conductor - Simple Mode</h1>
    
    <div class=\"card\">
        <h3>📊 System Status</h3>
        <div class=\"status stopped\">⚫ Simplified Demo Mode</div>
        <p>This is a simplified demonstration version.</p>
    </div>
    
    <div class=\"card\">
        <h3>🚀 Quick Actions</h3>
        <button class=\"button\" onclick=\"alert(\'Feature available in full version\')\">Start Task</button>
        <button class=\"button\" onclick=\"alert(\'Feature available in full version\')\">View Logs</button>
    </div>
    
    <div class=\"card\">
        <h3>📝 Sample Tasks</h3>
        <ul>
            <li>echo \"Hello from Claude Conductor!\"</li>
            <li>python3 -c \"print(\'System test successful\')\"</li>
            <li>ls -la && pwd</li>
        </ul>
    </div>
    
    <div class=\"card\">
        <h3>🔗 Next Steps</h3>
        <p>For full functionality, please use the complete installation:</p>
        <pre>git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor
git checkout feature/standalone-subset
./quick-start.sh</pre>
    </div>
</body>
</html>
'''

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())

print(f'Starting server on port {PORT}...')
with socketserver.TCPServer(('', PORT), Handler) as httpd:
    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://localhost:{PORT}')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        httpd.shutdown()
"
EOF

chmod +x run.sh

# 完了メッセージ
echo -e "${GREEN}✅ Simple setup completed!${NC}"
echo ""
echo -e "${YELLOW}🚀 To start:${NC}"
echo "   cd $SETUP_DIR"
echo "   ./run.sh"
echo ""
echo -e "${YELLOW}🌐 Dashboard:${NC} http://localhost:8080"
echo ""
echo -e "${YELLOW}📝 Note:${NC} This is a demo version."
echo "   For full functionality, use ./quick-start.sh"
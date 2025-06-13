#!/usr/bin/env python3
"""
Claude Conductor - Isolated Workspace Examples
隔離されたワークスペースを使用したタスク実行の例
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Import conductor modules (assuming conductor is installed)
try:
    from conductor import Orchestrator, Task
    from conductor.workspace_isolation import WorkspaceIsolationManager
except ImportError:
    print("Please install Claude Conductor first")
    print("Run: pip install -e .")
    exit(1)


class IsolatedWorkspaceExamples:
    """隔離されたワークスペースの使用例"""
    
    def __init__(self, config_path: str = None):
        """初期化"""
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                self.config = json.load(f)
        else:
            # デフォルト設定
            self.config = {
                'isolated_workspace': {
                    'enabled': True,
                    'mode': 'sandbox'
                }
            }
    
    async def example_python_development(self):
        """Python開発環境での例"""
        print("\n🐍 Python Development Environment Example")
        print("=" * 50)
        
        # Pythonプロジェクトのセットアップ
        task = {
            'task_type': 'isolated_execution',
            'description': 'Setup and test Python project',
            'environment': 'python-dev',
            'commands': [
                # 仮想環境の作成
                'python3 -m venv /workspace/venv',
                'source /workspace/venv/bin/activate',
                
                # プロジェクトのセットアップ
                'mkdir -p /workspace/src/myproject',
                'cd /workspace/src/myproject',
                
                # サンプルコードの作成
                'cat > app.py << EOF\n'
                'def greet(name):\n'
                '    return f"Hello, {name}!"\n'
                '\n'
                'if __name__ == "__main__":\n'
                '    print(greet("Claude Conductor"))\n'
                'EOF',
                
                # テストファイルの作成
                'mkdir -p tests',
                'cat > tests/test_app.py << EOF\n'
                'import sys\n'
                'sys.path.insert(0, "..")\n'
                'from app import greet\n'
                '\n'
                'def test_greet():\n'
                '    assert greet("World") == "Hello, World!"\n'
                '    assert greet("Python") == "Hello, Python!"\n'
                '\n'
                'if __name__ == "__main__":\n'
                '    test_greet()\n'
                '    print("All tests passed!")\n'
                'EOF',
                
                # テストの実行
                'cd /workspace/src/myproject',
                'python app.py',
                'python tests/test_app.py',
                
                # Pytestでのテスト
                'pip install pytest',
                'pytest tests/'
            ]
        }
        
        return task
    
    async def example_nodejs_development(self):
        """Node.js開発環境での例"""
        print("\n📦 Node.js Development Environment Example")
        print("=" * 50)
        
        task = {
            'task_type': 'isolated_execution',
            'description': 'Setup and build Node.js project',
            'environment': 'nodejs-dev',
            'commands': [
                # プロジェクトの初期化
                'cd /workspace',
                'npm init -y',
                
                # package.jsonの更新
                'npm pkg set name="claude-conductor-demo"',
                'npm pkg set version="1.0.0"',
                'npm pkg set scripts.start="node src/index.js"',
                'npm pkg set scripts.test="jest"',
                'npm pkg set scripts.build="echo Building project..."',
                
                # ソースコードの作成
                'mkdir -p src',
                'cat > src/index.js << EOF\n'
                'const express = require("express");\n'
                'const app = express();\n'
                '\n'
                'app.get("/", (req, res) => {\n'
                '    res.json({ message: "Hello from Claude Conductor!" });\n'
                '});\n'
                '\n'
                'app.get("/health", (req, res) => {\n'
                '    res.json({ status: "healthy", timestamp: new Date() });\n'
                '});\n'
                '\n'
                'const PORT = process.env.PORT || 3000;\n'
                'app.listen(PORT, () => {\n'
                '    console.log(`Server running on port ${PORT}`);\n'
                '});\n'
                '\n'
                'module.exports = app;\n'
                'EOF',
                
                # テストの作成
                'mkdir -p __tests__',
                'cat > __tests__/app.test.js << EOF\n'
                'const request = require("supertest");\n'
                'const app = require("../src/index");\n'
                '\n'
                'describe("API Tests", () => {\n'
                '    test("GET / returns welcome message", async () => {\n'
                '        const response = await request(app).get("/");\n'
                '        expect(response.status).toBe(200);\n'
                '        expect(response.body.message).toBe("Hello from Claude Conductor!");\n'
                '    });\n'
                '\n'
                '    test("GET /health returns health status", async () => {\n'
                '        const response = await request(app).get("/health");\n'
                '        expect(response.status).toBe(200);\n'
                '        expect(response.body.status).toBe("healthy");\n'
                '    });\n'
                '});\n'
                'EOF',
                
                # 依存関係のインストール
                'npm install express',
                'npm install --save-dev jest supertest',
                
                # ビルドとテスト
                'npm run build',
                'npm test'
            ]
        }
        
        return task
    
    async def example_fullstack_development(self):
        """フルスタック開発環境での例"""
        print("\n🚀 Full Stack Development Environment Example")
        print("=" * 50)
        
        task = {
            'task_type': 'isolated_execution',
            'description': 'Setup full stack development environment',
            'environment': 'fullstack',
            'commands': [
                # ディレクトリ構造の作成
                'cd /workspace',
                'mkdir -p backend frontend database scripts',
                
                # バックエンドのセットアップ (Python/Flask)
                'cd /workspace/backend',
                'cat > requirements.txt << EOF\n'
                'flask==2.3.0\n'
                'flask-cors==4.0.0\n'
                'sqlalchemy==2.0.0\n'
                'psycopg2-binary==2.9.0\n'
                'EOF',
                
                'cat > app.py << EOF\n'
                'from flask import Flask, jsonify\n'
                'from flask_cors import CORS\n'
                '\n'
                'app = Flask(__name__)\n'
                'CORS(app)\n'
                '\n'
                '@app.route("/api/status")\n'
                'def status():\n'
                '    return jsonify({\n'
                '        "status": "running",\n'
                '        "service": "backend",\n'
                '        "version": "1.0.0"\n'
                '    })\n'
                '\n'
                '@app.route("/api/data")\n'
                'def get_data():\n'
                '    return jsonify({\n'
                '        "items": [\n'
                '            {"id": 1, "name": "Item 1"},\n'
                '            {"id": 2, "name": "Item 2"}\n'
                '        ]\n'
                '    })\n'
                '\n'
                'if __name__ == "__main__":\n'
                '    app.run(host="0.0.0.0", port=5000)\n'
                'EOF',
                
                # フロントエンドのセットアップ (React)
                'cd /workspace/frontend',
                'cat > package.json << EOF\n'
                '{\n'
                '  "name": "frontend",\n'
                '  "version": "1.0.0",\n'
                '  "scripts": {\n'
                '    "dev": "vite",\n'
                '    "build": "vite build",\n'
                '    "test": "echo Testing frontend..."\n'
                '  },\n'
                '  "dependencies": {\n'
                '    "react": "^18.0.0",\n'
                '    "react-dom": "^18.0.0",\n'
                '    "axios": "^1.0.0"\n'
                '  },\n'
                '  "devDependencies": {\n'
                '    "vite": "^4.0.0",\n'
                '    "@vitejs/plugin-react": "^4.0.0"\n'
                '  }\n'
                '}\n'
                'EOF',
                
                # データベーススクリプト
                'cd /workspace/database',
                'cat > init.sql << EOF\n'
                'CREATE DATABASE claude_conductor;\n'
                '\n'
                '\\c claude_conductor;\n'
                '\n'
                'CREATE TABLE tasks (\n'
                '    id SERIAL PRIMARY KEY,\n'
                '    name VARCHAR(255) NOT NULL,\n'
                '    status VARCHAR(50) DEFAULT "pending",\n'
                '    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n'
                ');\n'
                '\n'
                'INSERT INTO tasks (name) VALUES \n'
                '    ("Setup environment"),\n'
                '    ("Run tests"),\n'
                '    ("Deploy application");\n'
                'EOF',
                
                # 統合スクリプト
                'cd /workspace/scripts',
                'cat > run-all.sh << EOF\n'
                '#!/bin/bash\n'
                'echo "Starting full stack application..."\n'
                '\n'
                '# Install dependencies\n'
                'cd /workspace/backend\n'
                'pip install -r requirements.txt\n'
                '\n'
                'cd /workspace/frontend\n'
                'npm install\n'
                '\n'
                '# Run tests\n'
                'echo "Running backend tests..."\n'
                'cd /workspace/backend\n'
                'python -m pytest tests/ || echo "No tests found"\n'
                '\n'
                'echo "Running frontend tests..."\n'
                'cd /workspace/frontend\n'
                'npm test\n'
                '\n'
                'echo "Full stack setup complete!"\n'
                'EOF',
                
                'chmod +x /workspace/scripts/run-all.sh',
                '/workspace/scripts/run-all.sh'
            ]
        }
        
        return task
    
    async def example_data_science_environment(self):
        """データサイエンス環境での例"""
        print("\n📊 Data Science Environment Example")
        print("=" * 50)
        
        task = {
            'task_type': 'isolated_execution',
            'description': 'Setup data science environment with Jupyter',
            'environment': 'python-ml',
            'commands': [
                # Jupyter環境のセットアップ
                'cd /workspace',
                'pip install jupyter pandas numpy matplotlib seaborn scikit-learn',
                
                # サンプルノートブックの作成
                'mkdir -p notebooks',
                'cat > notebooks/example_analysis.py << EOF\n'
                '#!/usr/bin/env python3\n'
                '"""Sample Data Analysis Script"""\n'
                '\n'
                'import pandas as pd\n'
                'import numpy as np\n'
                'import matplotlib.pyplot as plt\n'
                'from sklearn.model_selection import train_test_split\n'
                'from sklearn.linear_model import LinearRegression\n'
                'from sklearn.metrics import mean_squared_error, r2_score\n'
                '\n'
                '# Generate sample data\n'
                'np.random.seed(42)\n'
                'X = np.random.rand(100, 1) * 10\n'
                'y = 2.5 * X + np.random.randn(100, 1) * 2\n'
                '\n'
                '# Create DataFrame\n'
                'df = pd.DataFrame({"X": X.flatten(), "y": y.flatten()})\n'
                'print("Data shape:", df.shape)\n'
                'print("\\nData summary:")\n'
                'print(df.describe())\n'
                '\n'
                '# Split data\n'
                'X_train, X_test, y_train, y_test = train_test_split(\n'
                '    X, y, test_size=0.2, random_state=42\n'
                ')\n'
                '\n'
                '# Train model\n'
                'model = LinearRegression()\n'
                'model.fit(X_train, y_train)\n'
                '\n'
                '# Make predictions\n'
                'y_pred = model.predict(X_test)\n'
                '\n'
                '# Evaluate model\n'
                'mse = mean_squared_error(y_test, y_pred)\n'
                'r2 = r2_score(y_test, y_pred)\n'
                '\n'
                'print(f"\\nModel Performance:")\n'
                'print(f"MSE: {mse:.4f}")\n'
                'print(f"R2 Score: {r2:.4f}")\n'
                'print(f"Coefficient: {model.coef_[0][0]:.4f}")\n'
                'print(f"Intercept: {model.intercept_[0]:.4f}")\n'
                '\n'
                '# Save plot\n'
                'plt.figure(figsize=(10, 6))\n'
                'plt.scatter(X_test, y_test, color="blue", label="Actual")\n'
                'plt.plot(X_test, y_pred, color="red", linewidth=2, label="Predicted")\n'
                'plt.xlabel("X")\n'
                'plt.ylabel("y")\n'
                'plt.title("Linear Regression Results")\n'
                'plt.legend()\n'
                'plt.grid(True)\n'
                'plt.savefig("/workspace/regression_plot.png")\n'
                'print("\\nPlot saved to /workspace/regression_plot.png")\n'
                'EOF',
                
                # 分析の実行
                'cd /workspace/notebooks',
                'python example_analysis.py',
                
                # 結果の確認
                'ls -la /workspace/',
                'file /workspace/regression_plot.png'
            ]
        }
        
        return task
    
    async def example_security_testing(self):
        """セキュリティテスト環境での例"""
        print("\n🔒 Security Testing Environment Example")
        print("=" * 50)
        
        task = {
            'task_type': 'isolated_execution',
            'description': 'Run security scans in isolated environment',
            'environment': 'security-test',
            'commands': [
                # セキュリティツールのインストール
                'apt-get update',
                'apt-get install -y python3-pip git',
                'pip3 install bandit safety pylint',
                
                # サンプルコードの作成（脆弱性を含む）
                'mkdir -p /workspace/vulnerable_app',
                'cd /workspace/vulnerable_app',
                
                'cat > app.py << EOF\n'
                'import os\n'
                'import pickle\n'
                'import subprocess\n'
                'from flask import Flask, request\n'
                '\n'
                'app = Flask(__name__)\n'
                '\n'
                '# Security issue: Command injection\n'
                '@app.route("/ping")\n'
                'def ping():\n'
                '    host = request.args.get("host", "localhost")\n'
                '    # Vulnerable to command injection\n'
                '    result = os.system(f"ping -c 1 {host}")\n'
                '    return {"result": result}\n'
                '\n'
                '# Security issue: Insecure deserialization\n'
                '@app.route("/load")\n'
                'def load_data():\n'
                '    data = request.get_data()\n'
                '    # Vulnerable to arbitrary code execution\n'
                '    obj = pickle.loads(data)\n'
                '    return {"loaded": str(obj)}\n'
                '\n'
                '# Security issue: Hardcoded credentials\n'
                'DATABASE_PASSWORD = "admin123"\n'
                'API_KEY = "sk-1234567890abcdef"\n'
                '\n'
                'if __name__ == "__main__":\n'
                '    # Security issue: Debug mode in production\n'
                '    app.run(debug=True, host="0.0.0.0")\n'
                'EOF',
                
                'cat > requirements.txt << EOF\n'
                'flask==2.0.0\n'
                'requests==2.20.0\n'
                'urllib3==1.24.0\n'
                'EOF',
                
                # セキュリティスキャンの実行
                'echo "\\n=== Running Bandit Security Scan ==="',
                'bandit -r . -f json -o /workspace/bandit_report.json || true',
                'bandit -r . || true',
                
                'echo "\\n=== Running Safety Dependency Check ==="',
                'safety check -r requirements.txt || true',
                
                'echo "\\n=== Running Pylint Code Analysis ==="',
                'pylint app.py --exit-zero',
                
                # レポートの生成
                'echo "\\n=== Security Scan Summary ==="',
                'echo "Reports generated:"',
                'ls -la /workspace/*.json 2>/dev/null || echo "No JSON reports"',
                'echo "\\nSecurity scan complete!"'
            ]
        }
        
        return task


async def run_examples():
    """サンプルを実行"""
    examples = IsolatedWorkspaceExamples()
    
    # 実行するサンプルを選択
    tasks = [
        await examples.example_python_development(),
        await examples.example_nodejs_development(),
        await examples.example_fullstack_development(),
        await examples.example_data_science_environment(),
        await examples.example_security_testing()
    ]
    
    print("\n" + "=" * 70)
    print("Claude Conductor - Isolated Workspace Examples")
    print("=" * 70)
    print("\nAvailable examples:")
    print("1. Python Development Environment")
    print("2. Node.js Development Environment")
    print("3. Full Stack Development")
    print("4. Data Science Environment")
    print("5. Security Testing Environment")
    print("\nThese examples demonstrate how to use isolated workspaces")
    print("for different development and testing scenarios.")
    print("\nEach task runs in a completely isolated container with")
    print("its own filesystem, network, and process space.")
    
    # タスクをJSONとして出力（API呼び出し用）
    print("\n" + "=" * 70)
    print("Example API calls:")
    print("=" * 70)
    
    for i, task in enumerate(tasks, 1):
        print(f"\n{i}. {task['description']}:")
        print("```bash")
        print("curl -X POST http://localhost:8081/tasks \\")
        print("  -H 'Content-Type: application/json' \\")
        print("  -d '" + json.dumps(task, indent=2) + "'")
        print("```")


if __name__ == "__main__":
    asyncio.run(run_examples())
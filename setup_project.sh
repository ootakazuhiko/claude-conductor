#!/bin/bash
# setup_project.sh

PROJECT_DIR="$HOME/claude-code-orchestrator"
mkdir -p $PROJECT_DIR/{src,tests,config,examples,logs,workspace}
cd $PROJECT_DIR

# Git初期化
git init

# .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
venv/
.env
logs/
workspace/
*.sock
.pytest_cache/
*.log
EOF

# Python環境
python3 -m venv venv
source venv/bin/activate

# requirements.txt
cat > requirements.txt << 'EOF'
pytest==7.4.0
pytest-asyncio==0.21.0
pytest-timeout==2.1.0
pyyaml==6.0
redis==4.6.0
psutil==5.9.5
EOF

pip install -r requirements.txt

echo "Project setup completed at $PROJECT_DIR"
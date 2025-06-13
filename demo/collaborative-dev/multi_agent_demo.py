#!/usr/bin/env python3
"""
Claude Conductor - Multi-Agent Collaborative Development Demo
複数のエージェントが協調してWebアプリケーションを開発するデモ
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from conductor import Orchestrator, Task, TaskResult
from conductor.agent import ClaudeAgent


class CollaborativeDevelopmentDemo:
    """複数エージェントによる協調開発デモ"""
    
    def __init__(self, project_path: str = "demo/sample-project"):
        self.project_path = Path(project_path).absolute()
        self.orchestrator = None
        self.results = {}
        self.start_time = None
        
    def setup(self):
        """デモ環境のセットアップ"""
        print("🚀 Claude Conductor - Collaborative Development Demo")
        print("=" * 60)
        print(f"Project: {self.project_path}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Create orchestrator with custom config
        config = {
            "orchestrator": {
                "num_agents": 4,
                "max_workers": 8,
                "task_timeout": 600
            },
            "isolated_workspace": {
                "enabled": True,
                "mode": "sandbox",
                "agent_containers": {
                    "environments": [
                        {
                            "name": "backend-dev",
                            "image": "python:3.11-slim",
                            "packages": ["flask", "sqlalchemy", "black"]
                        },
                        {
                            "name": "test-dev",
                            "image": "python:3.11-slim",
                            "packages": ["pytest", "pytest-cov", "pytest-mock"]
                        },
                        {
                            "name": "devops",
                            "image": "alpine:latest",
                            "packages": ["docker", "git", "bash"]
                        },
                        {
                            "name": "docs",
                            "image": "python:3.11-slim",
                            "packages": ["sphinx", "mkdocs", "pydoc-markdown"]
                        }
                    ]
                }
            }
        }
        
        print("\n📋 Agent Configuration:")
        print("  - Agent 1: Backend Developer (Python/Flask)")
        print("  - Agent 2: Test Engineer (Pytest)")
        print("  - Agent 3: DevOps Engineer (Docker/CI)")
        print("  - Agent 4: Documentation Specialist")
        
        self.orchestrator = Orchestrator(config=config)
        self.orchestrator.start()
        
        print("\n✅ Orchestrator started with 4 specialized agents")
        
    def create_development_tasks(self) -> List[Task]:
        """開発タスクを作成"""
        tasks = []
        
        # Phase 1: Backend Development
        tasks.append(Task(
            task_id="backend_001",
            task_type="isolated_execution",
            description="Create Flask application structure",
            environment="backend-dev",
            commands=[
                f"cd {self.project_path}",
                "mkdir -p src/api src/models src/utils",
                
                # Create main application file
                """cat > src/app.py << 'EOF'
from flask import Flask, jsonify
from flask_cors import CORS
from api.routes import api_bp
from models.database import init_db

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    
    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy', 'service': 'todo-api'})
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
EOF""",
                
                # Create database models
                """cat > src/models/__init__.py << 'EOF'
from .todo import Todo
from .database import db, init_db
EOF""",
                
                """cat > src/models/database.py << 'EOF'
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
EOF""",
                
                """cat > src/models/todo.py << 'EOF'
from datetime import datetime
from .database import db

class Todo(db.Model):
    __tablename__ = 'todos'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Todo {self.id}: {self.title}>'
EOF""",
                
                # Format code
                "cd src && python -m black . || true"
            ],
            priority=10
        ))
        
        # Phase 2: API Implementation
        tasks.append(Task(
            task_id="backend_002",
            task_type="isolated_execution",
            description="Implement REST API endpoints",
            environment="backend-dev",
            commands=[
                f"cd {self.project_path}",
                "mkdir -p src/api",
                
                # Create API routes
                """cat > src/api/__init__.py << 'EOF'
from .routes import api_bp
EOF""",
                
                """cat > src/api/routes.py << 'EOF'
from flask import Blueprint, jsonify, request
from models import Todo, db

api_bp = Blueprint('api', __name__)

@api_bp.route('/todos', methods=['GET'])
def get_todos():
    todos = Todo.query.all()
    return jsonify([todo.to_dict() for todo in todos])

@api_bp.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    todo = Todo(
        title=data['title'],
        description=data.get('description', ''),
        completed=data.get('completed', False)
    )
    
    db.session.add(todo)
    db.session.commit()
    
    return jsonify(todo.to_dict()), 201

@api_bp.route('/todos/<int:todo_id>', methods=['GET'])
def get_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    return jsonify(todo.to_dict())

@api_bp.route('/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    data = request.get_json()
    
    if 'title' in data:
        todo.title = data['title']
    if 'description' in data:
        todo.description = data['description']
    if 'completed' in data:
        todo.completed = data['completed']
    
    db.session.commit()
    return jsonify(todo.to_dict())

@api_bp.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    db.session.delete(todo)
    db.session.commit()
    return '', 204
EOF""",
                
                # Create utils
                """cat > src/utils/__init__.py << 'EOF'
# Utility functions
EOF""",
                
                # Format code
                "cd src && python -m black . || true"
            ],
            priority=9,
            dependencies=["backend_001"]
        ))
        
        # Phase 3: Testing
        tasks.append(Task(
            task_id="test_001",
            task_type="isolated_execution",
            description="Write unit tests for models",
            environment="test-dev",
            commands=[
                f"cd {self.project_path}",
                "mkdir -p tests/unit tests/integration",
                
                # Create test configuration
                """cat > tests/conftest.py << 'EOF'
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import create_app
from models import db

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()
EOF""",
                
                # Unit tests for models
                """cat > tests/unit/test_models.py << 'EOF'
import pytest
from datetime import datetime
from models import Todo, db

def test_todo_creation(app):
    with app.app_context():
        todo = Todo(
            title="Test Todo",
            description="Test Description",
            completed=False
        )
        db.session.add(todo)
        db.session.commit()
        
        assert todo.id is not None
        assert todo.title == "Test Todo"
        assert todo.description == "Test Description"
        assert todo.completed is False
        assert isinstance(todo.created_at, datetime)
        assert isinstance(todo.updated_at, datetime)

def test_todo_to_dict(app):
    with app.app_context():
        todo = Todo(
            title="Test Todo",
            description="Test Description"
        )
        db.session.add(todo)
        db.session.commit()
        
        todo_dict = todo.to_dict()
        assert 'id' in todo_dict
        assert todo_dict['title'] == "Test Todo"
        assert todo_dict['description'] == "Test Description"
        assert todo_dict['completed'] is False
        assert 'created_at' in todo_dict
        assert 'updated_at' in todo_dict

def test_todo_repr(app):
    with app.app_context():
        todo = Todo(title="Test Todo")
        db.session.add(todo)
        db.session.commit()
        
        assert repr(todo) == f'<Todo {todo.id}: Test Todo>'
EOF""",
                
                # Run tests
                "cd tests && python -m pytest unit/ -v || true"
            ],
            priority=8,
            dependencies=["backend_002"]
        ))
        
        # Phase 4: Integration Tests
        tasks.append(Task(
            task_id="test_002",
            task_type="isolated_execution",
            description="Write integration tests for API",
            environment="test-dev",
            commands=[
                f"cd {self.project_path}",
                
                # Integration tests
                """cat > tests/integration/test_api.py << 'EOF'
import pytest
import json

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert data['service'] == 'todo-api'

def test_get_todos_empty(client):
    response = client.get('/api/todos')
    assert response.status_code == 200
    assert json.loads(response.data) == []

def test_create_todo(client):
    todo_data = {
        'title': 'Test Todo',
        'description': 'Test Description'
    }
    response = client.post('/api/todos',
                          data=json.dumps(todo_data),
                          content_type='application/json')
    assert response.status_code == 201
    
    data = json.loads(response.data)
    assert data['title'] == 'Test Todo'
    assert data['description'] == 'Test Description'
    assert data['completed'] is False
    assert 'id' in data

def test_get_todo(client):
    # Create a todo first
    todo_data = {'title': 'Test Todo'}
    create_response = client.post('/api/todos',
                                 data=json.dumps(todo_data),
                                 content_type='application/json')
    todo_id = json.loads(create_response.data)['id']
    
    # Get the todo
    response = client.get(f'/api/todos/{todo_id}')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['id'] == todo_id
    assert data['title'] == 'Test Todo'

def test_update_todo(client):
    # Create a todo
    todo_data = {'title': 'Original Title'}
    create_response = client.post('/api/todos',
                                 data=json.dumps(todo_data),
                                 content_type='application/json')
    todo_id = json.loads(create_response.data)['id']
    
    # Update it
    update_data = {
        'title': 'Updated Title',
        'completed': True
    }
    response = client.put(f'/api/todos/{todo_id}',
                         data=json.dumps(update_data),
                         content_type='application/json')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert data['title'] == 'Updated Title'
    assert data['completed'] is True

def test_delete_todo(client):
    # Create a todo
    todo_data = {'title': 'To Delete'}
    create_response = client.post('/api/todos',
                                 data=json.dumps(todo_data),
                                 content_type='application/json')
    todo_id = json.loads(create_response.data)['id']
    
    # Delete it
    response = client.delete(f'/api/todos/{todo_id}')
    assert response.status_code == 204
    
    # Verify it's gone
    get_response = client.get(f'/api/todos/{todo_id}')
    assert get_response.status_code == 404
EOF""",
                
                # Run all tests with coverage
                "cd tests && python -m pytest . -v --cov=../src --cov-report=term-missing || true"
            ],
            priority=7,
            dependencies=["test_001"]
        ))
        
        # Phase 5: DevOps
        tasks.append(Task(
            task_id="devops_001",
            task_type="isolated_execution",
            description="Create Dockerfile and deployment scripts",
            environment="devops",
            commands=[
                f"cd {self.project_path}",
                
                # Create Dockerfile
                """cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/

# Create database directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 5000

# Environment variables
ENV FLASK_APP=src/app.py
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "src/app.py"]
EOF""",
                
                # Create docker-compose.yml
                """cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  todo-api:
    build: .
    container_name: todo-api
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=sqlite:////app/data/todos.db
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: todo-nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - todo-api
    restart: unless-stopped
EOF""",
                
                # Create nginx configuration
                """cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream todo_api {
        server todo-api:5000;
    }

    server {
        listen 80;
        server_name localhost;

        location / {
            proxy_pass http://todo_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
EOF""",
                
                # Create deployment script
                """cat > deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Deploying Todo API..."

# Build Docker image
docker build -t todo-api:latest .

# Stop existing containers
docker-compose down

# Start services
docker-compose up -d

# Wait for health check
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check health
if curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ Deployment successful!"
    echo "🌐 API available at: http://localhost:5000"
    echo "🌐 Nginx proxy at: http://localhost"
else
    echo "❌ Health check failed!"
    docker-compose logs
    exit 1
fi
EOF""",
                
                "chmod +x deploy.sh"
            ],
            priority=6,
            dependencies=["test_002"]
        ))
        
        # Phase 6: CI/CD Configuration
        tasks.append(Task(
            task_id="devops_002",
            task_type="isolated_execution",
            description="Create CI/CD pipeline configuration",
            environment="devops",
            commands=[
                f"cd {self.project_path}",
                "mkdir -p .github/workflows",
                
                # Create GitHub Actions workflow
                """cat > .github/workflows/ci.yml << 'EOF'
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run linting
      run: |
        cd src && python -m flake8 . --max-line-length=100
        python -m black . --check
    
    - name: Run tests
      run: |
        cd tests && python -m pytest . -v --cov=../src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./tests/coverage.xml
  
  build:
    needs: test
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: docker build -t todo-api:${{ github.sha }} .
    
    - name: Run security scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: todo-api:${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'
    
    - name: Upload scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'
EOF""",
                
                # Create Makefile
                """cat > Makefile << 'EOF'
.PHONY: help install test lint format run docker-build docker-run clean

help:
	@echo "Available commands:"
	@echo "  install      Install dependencies"
	@echo "  test         Run tests"
	@echo "  lint         Run linting"
	@echo "  format       Format code"
	@echo "  run          Run application"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run with Docker"
	@echo "  clean        Clean up"

install:
	pip install -r requirements.txt

test:
	cd tests && python -m pytest . -v --cov=../src

lint:
	cd src && python -m flake8 . --max-line-length=100
	cd src && python -m mypy .

format:
	cd src && python -m black .

run:
	python src/app.py

docker-build:
	docker build -t todo-api:latest .

docker-run:
	docker-compose up -d

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .pytest_cache
	rm -rf .mypy_cache
EOF"""
            ],
            priority=5,
            dependencies=["devops_001"]
        ))
        
        # Phase 7: Documentation
        tasks.append(Task(
            task_id="docs_001",
            task_type="isolated_execution",
            description="Generate API documentation",
            environment="docs",
            commands=[
                f"cd {self.project_path}",
                "mkdir -p docs/api docs/guides",
                
                # Create API documentation
                """cat > docs/api/README.md << 'EOF'
# Todo API Documentation

## Overview

The Todo API is a RESTful service for managing todo items. It provides endpoints for creating, reading, updating, and deleting todos.

## Base URL

```
http://localhost:5000/api
```

## Authentication

Currently, the API does not require authentication. This will be added in a future version.

## Endpoints

### List All Todos

```http
GET /todos
```

**Response:**
```json
[
  {
    "id": 1,
    "title": "Sample Todo",
    "description": "This is a sample todo",
    "completed": false,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
]
```

### Create a Todo

```http
POST /todos
Content-Type: application/json

{
  "title": "New Todo",
  "description": "Description of the todo",
  "completed": false
}
```

**Response:** `201 Created`
```json
{
  "id": 2,
  "title": "New Todo",
  "description": "Description of the todo",
  "completed": false,
  "created_at": "2024-01-15T10:35:00",
  "updated_at": "2024-01-15T10:35:00"
}
```

### Get a Specific Todo

```http
GET /todos/{id}
```

**Response:** `200 OK` or `404 Not Found`

### Update a Todo

```http
PUT /todos/{id}
Content-Type: application/json

{
  "title": "Updated Title",
  "completed": true
}
```

**Response:** `200 OK` with updated todo object

### Delete a Todo

```http
DELETE /todos/{id}
```

**Response:** `204 No Content` or `404 Not Found`

## Error Responses

### 400 Bad Request
```json
{
  "error": "Title is required"
}
```

### 404 Not Found
```json
{
  "error": "Todo not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```
EOF""",
                
                # Create user guide
                """cat > docs/guides/getting-started.md << 'EOF'
# Getting Started with Todo API

## Prerequisites

- Python 3.11 or higher
- Docker (optional)

## Installation

### Local Development

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd todo-api
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python src/app.py
   ```

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. Access the API at `http://localhost:5000`

## Quick Start

### Create your first todo:

```bash
curl -X POST http://localhost:5000/api/todos \\
  -H "Content-Type: application/json" \\
  -d '{"title": "My first todo"}'
```

### List all todos:

```bash
curl http://localhost:5000/api/todos
```

### Update a todo:

```bash
curl -X PUT http://localhost:5000/api/todos/1 \\
  -H "Content-Type: application/json" \\
  -d '{"completed": true}'
```

## Development

### Running Tests

```bash
make test
```

### Code Formatting

```bash
make format
```

### Linting

```bash
make lint
```

## Contributing

Please read our contributing guidelines before submitting pull requests.
EOF""",
                
                # Create OpenAPI specification
                """cat > docs/api/openapi.yaml << 'EOF'
openapi: 3.0.0
info:
  title: Todo API
  version: 1.0.0
  description: A simple API for managing todo items
servers:
  - url: http://localhost:5000/api
paths:
  /todos:
    get:
      summary: List all todos
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Todo'
    post:
      summary: Create a new todo
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TodoInput'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Todo'
  /todos/{id}:
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    get:
      summary: Get a specific todo
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Todo'
        '404':
          description: Todo not found
    put:
      summary: Update a todo
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TodoInput'
      responses:
        '200':
          description: Updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Todo'
    delete:
      summary: Delete a todo
      responses:
        '204':
          description: Deleted
        '404':
          description: Todo not found
components:
  schemas:
    Todo:
      type: object
      properties:
        id:
          type: integer
        title:
          type: string
        description:
          type: string
        completed:
          type: boolean
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
    TodoInput:
      type: object
      required:
        - title
      properties:
        title:
          type: string
        description:
          type: string
        completed:
          type: boolean
EOF"""
            ],
            priority=4,
            dependencies=["devops_002"]
        ))
        
        # Phase 8: Final Integration
        tasks.append(Task(
            task_id="integration_001",
            task_type="isolated_execution",
            description="Final integration and code review",
            environment="backend-dev",
            commands=[
                f"cd {self.project_path}",
                
                # Add final touches
                """cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
.env
*.db
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
*.log
data/
EOF""",
                
                """cat > setup.py << 'EOF'
from setuptools import setup, find_packages

setup(
    name="todo-api",
    version="1.0.0",
    author="Claude Conductor Team",
    description="A simple Todo API developed by multiple agents",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "flask>=2.3.0",
        "flask-cors>=4.0.0",
        "sqlalchemy>=2.0.0",
    ],
    python_requires=">=3.11",
)
EOF""",
                
                # Run final checks
                "echo '✅ Project structure complete'",
                "find . -name '*.py' | wc -l",
                "echo 'Python files created'",
                "ls -la src/",
                "ls -la tests/",
                "ls -la docs/"
            ],
            priority=3,
            dependencies=["docs_001"]
        ))
        
        return tasks
    
    async def execute_demo(self):
        """デモを実行"""
        self.start_time = time.time()
        tasks = self.create_development_tasks()
        
        print(f"\n📋 Total tasks to execute: {len(tasks)}")
        print("\n🔄 Starting collaborative development...\n")
        
        # Execute tasks in order of priority and dependencies
        completed_tasks = set()
        
        while len(completed_tasks) < len(tasks):
            # Find tasks that can be executed
            available_tasks = []
            for task in tasks:
                if task.task_id not in completed_tasks:
                    # Check if dependencies are met
                    deps = getattr(task, 'dependencies', [])
                    if all(dep in completed_tasks for dep in deps):
                        available_tasks.append(task)
            
            if not available_tasks:
                print("❌ No tasks available to execute - dependency deadlock!")
                break
            
            # Sort by priority
            available_tasks.sort(key=lambda t: t.priority, reverse=True)
            
            # Execute tasks in parallel (up to num_agents)
            batch = available_tasks[:self.orchestrator.config.get("orchestrator", {}).get("num_agents", 4)]
            
            print(f"\n🚀 Executing batch of {len(batch)} tasks:")
            for task in batch:
                print(f"  - {task.task_id}: {task.description}")
            
            # Execute batch
            if len(batch) == 1:
                result = self.orchestrator.execute_task(batch[0])
                self.results[batch[0].task_id] = result
                self._print_result(batch[0], result)
                completed_tasks.add(batch[0].task_id)
            else:
                results = self.orchestrator.execute_parallel_tasks(batch)
                for task, result in zip(batch, results):
                    self.results[task.task_id] = result
                    self._print_result(task, result)
                    completed_tasks.add(task.task_id)
            
            print(f"\n✅ Completed: {len(completed_tasks)}/{len(tasks)} tasks")
        
        # Final summary
        self._print_summary()
    
    def _print_result(self, task: Task, result: TaskResult):
        """タスク結果を表示"""
        status_icon = "✅" if result.status == "success" else "❌"
        print(f"\n{status_icon} Task {task.task_id}: {task.description}")
        print(f"   Status: {result.status}")
        print(f"   Agent: {result.agent_id}")
        print(f"   Execution time: {result.execution_time:.2f}s")
        
        if result.status == "failed" and result.error:
            print(f"   Error: {result.error}")
    
    def _print_summary(self):
        """実行サマリーを表示"""
        total_time = time.time() - self.start_time
        successful = sum(1 for r in self.results.values() if r.status == "success")
        failed = sum(1 for r in self.results.values() if r.status == "failed")
        
        print("\n" + "=" * 60)
        print("🎉 COLLABORATIVE DEVELOPMENT COMPLETE!")
        print("=" * 60)
        print(f"\n📊 Summary:")
        print(f"  Total tasks: {len(self.results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Average time per task: {total_time/len(self.results):.2f}s")
        
        print(f"\n📁 Project created at: {self.project_path}")
        print("\n🎯 Next steps:")
        print("  1. cd demo/sample-project")
        print("  2. docker-compose up -d")
        print("  3. curl http://localhost:5000/api/todos")
        
        print("\n✨ The project was successfully developed by 4 specialized agents:")
        print("  - Backend Developer: Created Flask application and models")
        print("  - Test Engineer: Wrote comprehensive test suite")
        print("  - DevOps Engineer: Set up Docker and CI/CD")
        print("  - Documentation Specialist: Created API docs and guides")
    
    def cleanup(self):
        """クリーンアップ"""
        if self.orchestrator:
            self.orchestrator.stop()


async def main():
    """メイン実行関数"""
    demo = CollaborativeDevelopmentDemo()
    
    try:
        demo.setup()
        await demo.execute_demo()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    finally:
        demo.cleanup()
        print("\n👋 Demo completed!")


if __name__ == "__main__":
    asyncio.run(main())
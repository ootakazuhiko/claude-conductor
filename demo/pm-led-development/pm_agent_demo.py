#!/usr/bin/env python3
"""
Claude Conductor - PM-Led Hierarchical Development Demo
PMエージェントが他のエージェントを管理・指示する階層的な開発デモ
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from conductor import Orchestrator, Task, TaskResult
from conductor.agent import ClaudeAgent
from conductor.protocol import AgentMessage, MessageType


class TaskStatus(Enum):
    """タスクステータス"""
    PLANNING = "planning"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class ProjectTask:
    """プロジェクトタスク"""
    task_id: str
    title: str
    description: str
    assigned_to: Optional[str] = None
    status: TaskStatus = TaskStatus.PLANNING
    dependencies: List[str] = field(default_factory=list)
    estimated_hours: float = 1.0
    actual_hours: float = 0.0
    priority: int = 5
    deliverables: List[str] = field(default_factory=list)


@dataclass
class ProjectPlan:
    """プロジェクト計画"""
    project_name: str
    objectives: List[str]
    phases: List[Dict[str, Any]]
    tasks: List[ProjectTask]
    timeline: Dict[str, Any]
    risks: List[Dict[str, str]]


class PMAgentDemo:
    """PMエージェントによる階層的開発デモ"""
    
    def __init__(self, project_path: str = "demo/pm-project"):
        self.project_path = Path(project_path).absolute()
        self.orchestrator = None
        self.pm_agent_id = "agent_pm"
        self.project_plan = None
        self.task_assignments = {}
        self.progress_reports = []
        self.start_time = None
        
    def setup(self):
        """デモ環境のセットアップ"""
        print("🎯 Claude Conductor - PM-Led Hierarchical Development Demo")
        print("=" * 70)
        print(f"Project: E-Commerce Platform Development")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Create orchestrator with PM + development team
        config = {
            "orchestrator": {
                "num_agents": 5,  # 1 PM + 4 developers
                "max_workers": 10,
                "task_timeout": 900
            },
            "isolated_workspace": {
                "enabled": True,
                "mode": "sandbox",
                "agent_containers": {
                    "environments": [
                        {
                            "name": "pm-env",
                            "image": "python:3.11-slim",
                            "packages": ["pyyaml", "jinja2", "markdown", "graphviz"],
                            "capabilities": ["project_planning", "task_delegation", "progress_monitoring"]
                        },
                        {
                            "name": "fullstack-dev",
                            "image": "node:18",
                            "packages": ["typescript", "react", "express", "jest"],
                            "capabilities": ["frontend", "backend", "api"]
                        },
                        {
                            "name": "backend-specialist",
                            "image": "python:3.11",
                            "packages": ["fastapi", "sqlalchemy", "redis", "celery"],
                            "capabilities": ["backend", "database", "microservices"]
                        },
                        {
                            "name": "frontend-specialist",
                            "image": "node:18",
                            "packages": ["react", "nextjs", "tailwindcss", "cypress"],
                            "capabilities": ["frontend", "ui/ux", "testing"]
                        },
                        {
                            "name": "devops-specialist",
                            "image": "alpine:latest",
                            "packages": ["docker", "kubernetes", "terraform", "ansible"],
                            "capabilities": ["infrastructure", "ci/cd", "monitoring"]
                        }
                    ]
                }
            }
        }
        
        print("\n👥 Team Structure:")
        print("  └─ PM (Project Manager)")
        print("     ├─ Senior Full-Stack Developer")
        print("     ├─ Backend Specialist") 
        print("     ├─ Frontend Specialist")
        print("     └─ DevOps Engineer")
        
        self.orchestrator = Orchestrator(config=config)
        self.orchestrator.start()
        
        print("\n✅ Team assembled and ready")
        
    def create_project_plan(self) -> ProjectPlan:
        """PMがプロジェクト計画を作成"""
        print("\n📋 PM is creating project plan...")
        
        # E-commerce platform project plan
        plan = ProjectPlan(
            project_name="E-Commerce Platform MVP",
            objectives=[
                "Build a scalable e-commerce platform",
                "Support product catalog, cart, and checkout",
                "Implement user authentication and profiles",
                "Create admin dashboard for management",
                "Ensure mobile-responsive design"
            ],
            phases=[
                {
                    "phase": 1,
                    "name": "Foundation",
                    "duration": "Week 1",
                    "goals": ["Setup infrastructure", "Design database schema", "Create API structure"]
                },
                {
                    "phase": 2,
                    "name": "Core Features",
                    "duration": "Week 2-3",
                    "goals": ["Product catalog", "Shopping cart", "User authentication"]
                },
                {
                    "phase": 3,
                    "name": "Advanced Features",
                    "duration": "Week 4",
                    "goals": ["Checkout process", "Payment integration", "Order management"]
                },
                {
                    "phase": 4,
                    "name": "Polish & Deploy",
                    "duration": "Week 5",
                    "goals": ["Testing", "Performance optimization", "Deployment"]
                }
            ],
            tasks=[
                # Phase 1 - Foundation
                ProjectTask(
                    task_id="TASK-001",
                    title="Setup project infrastructure",
                    description="Initialize project with Docker, create development environment",
                    estimated_hours=4,
                    priority=10,
                    deliverables=["Dockerfile", "docker-compose.yml", "README.md"]
                ),
                ProjectTask(
                    task_id="TASK-002",
                    title="Design database schema",
                    description="Design PostgreSQL schema for products, users, orders",
                    estimated_hours=6,
                    priority=9,
                    deliverables=["schema.sql", "ER diagram", "migration scripts"]
                ),
                ProjectTask(
                    task_id="TASK-003",
                    title="Create API boilerplate",
                    description="Setup FastAPI project structure with authentication",
                    estimated_hours=8,
                    priority=9,
                    deliverables=["API structure", "Auth endpoints", "OpenAPI docs"]
                ),
                ProjectTask(
                    task_id="TASK-004",
                    title="Setup frontend framework",
                    description="Initialize Next.js project with TypeScript and Tailwind",
                    estimated_hours=6,
                    priority=8,
                    deliverables=["Next.js app", "Component library", "Routing setup"]
                ),
                
                # Phase 2 - Core Features
                ProjectTask(
                    task_id="TASK-005",
                    title="Implement product catalog API",
                    description="Create CRUD endpoints for products with search and filtering",
                    dependencies=["TASK-002", "TASK-003"],
                    estimated_hours=10,
                    priority=8,
                    deliverables=["Product endpoints", "Search functionality", "Tests"]
                ),
                ProjectTask(
                    task_id="TASK-006",
                    title="Build product listing UI",
                    description="Create product grid, detail pages, and search interface",
                    dependencies=["TASK-004", "TASK-005"],
                    estimated_hours=12,
                    priority=7,
                    deliverables=["Product components", "Search UI", "Responsive design"]
                ),
                ProjectTask(
                    task_id="TASK-007",
                    title="Implement shopping cart",
                    description="Create cart functionality with session/user persistence",
                    dependencies=["TASK-005"],
                    estimated_hours=8,
                    priority=7,
                    deliverables=["Cart API", "Cart state management", "Cart UI"]
                ),
                ProjectTask(
                    task_id="TASK-008",
                    title="User authentication system",
                    description="Implement JWT auth with registration and login",
                    dependencies=["TASK-003"],
                    estimated_hours=10,
                    priority=8,
                    deliverables=["Auth endpoints", "JWT tokens", "User management"]
                ),
                
                # Phase 3 - Advanced Features
                ProjectTask(
                    task_id="TASK-009",
                    title="Checkout process",
                    description="Multi-step checkout with address and payment method",
                    dependencies=["TASK-007", "TASK-008"],
                    estimated_hours=12,
                    priority=6,
                    deliverables=["Checkout API", "Checkout UI", "Order creation"]
                ),
                ProjectTask(
                    task_id="TASK-010",
                    title="Payment integration",
                    description="Integrate Stripe for payment processing",
                    dependencies=["TASK-009"],
                    estimated_hours=8,
                    priority=6,
                    deliverables=["Stripe integration", "Payment UI", "Webhook handlers"]
                ),
                ProjectTask(
                    task_id="TASK-011",
                    title="Admin dashboard",
                    description="Create admin interface for product and order management",
                    dependencies=["TASK-005", "TASK-008"],
                    estimated_hours=10,
                    priority=5,
                    deliverables=["Admin UI", "Management endpoints", "Analytics"]
                ),
                
                # Phase 4 - Polish & Deploy
                ProjectTask(
                    task_id="TASK-012",
                    title="Write comprehensive tests",
                    description="Unit, integration, and E2E tests for all features",
                    dependencies=["TASK-010", "TASK-011"],
                    estimated_hours=12,
                    priority=7,
                    deliverables=["Test suites", "Coverage report", "E2E scenarios"]
                ),
                ProjectTask(
                    task_id="TASK-013",
                    title="Performance optimization",
                    description="Optimize queries, add caching, implement CDN",
                    dependencies=["TASK-012"],
                    estimated_hours=8,
                    priority=5,
                    deliverables=["Performance report", "Caching layer", "CDN setup"]
                ),
                ProjectTask(
                    task_id="TASK-014",
                    title="Deploy to production",
                    description="Deploy to Kubernetes with monitoring and CI/CD",
                    dependencies=["TASK-013"],
                    estimated_hours=10,
                    priority=8,
                    deliverables=["K8s manifests", "CI/CD pipeline", "Monitoring"]
                )
            ],
            timeline={
                "start_date": datetime.now().isoformat(),
                "end_date": (datetime.now().replace(day=datetime.now().day + 35)).isoformat(),
                "milestones": [
                    {"name": "Foundation Complete", "date": "Week 1"},
                    {"name": "MVP Features", "date": "Week 3"},
                    {"name": "Beta Release", "date": "Week 4"},
                    {"name": "Production Launch", "date": "Week 5"}
                ]
            },
            risks=[
                {"risk": "Payment integration delays", "mitigation": "Start Stripe setup early"},
                {"risk": "Performance issues", "mitigation": "Regular load testing"},
                {"risk": "Scope creep", "mitigation": "Strict MVP feature set"}
            ]
        )
        
        self.project_plan = plan
        return plan
    
    def assign_tasks_to_team(self) -> List[Task]:
        """PMがチームメンバーにタスクを割り当て"""
        print("\n👔 PM is assigning tasks to team members...")
        
        # Team member profiles
        team_members = {
            "agent_001": {
                "name": "Senior Full-Stack Developer",
                "environment": "fullstack-dev",
                "skills": ["frontend", "backend", "api", "testing"],
                "capacity": 40  # hours per week
            },
            "agent_002": {
                "name": "Backend Specialist",
                "environment": "backend-specialist",
                "skills": ["backend", "database", "microservices", "api"],
                "capacity": 40
            },
            "agent_003": {
                "name": "Frontend Specialist",
                "environment": "frontend-specialist",
                "skills": ["frontend", "ui/ux", "testing", "responsive"],
                "capacity": 40
            },
            "agent_004": {
                "name": "DevOps Engineer",
                "environment": "devops-specialist",
                "skills": ["infrastructure", "ci/cd", "monitoring", "deployment"],
                "capacity": 40
            }
        }
        
        # PM's task assignment logic
        assignments = []
        
        # Assign tasks based on skills and workload
        task_assignments = {
            "TASK-001": "agent_004",  # DevOps - Infrastructure
            "TASK-002": "agent_002",  # Backend - Database design
            "TASK-003": "agent_002",  # Backend - API boilerplate
            "TASK-004": "agent_003",  # Frontend - Framework setup
            "TASK-005": "agent_002",  # Backend - Product API
            "TASK-006": "agent_003",  # Frontend - Product UI
            "TASK-007": "agent_001",  # Full-Stack - Shopping cart
            "TASK-008": "agent_002",  # Backend - Authentication
            "TASK-009": "agent_001",  # Full-Stack - Checkout
            "TASK-010": "agent_001",  # Full-Stack - Payment
            "TASK-011": "agent_003",  # Frontend - Admin dashboard
            "TASK-012": "agent_001",  # Full-Stack - Testing
            "TASK-013": "agent_004",  # DevOps - Performance
            "TASK-014": "agent_004",  # DevOps - Deployment
        }
        
        # Create actual tasks for execution
        conductor_tasks = []
        
        # First, PM creates the initial project structure
        pm_setup_task = Task(
            task_id="PM-001",
            task_type="isolated_execution",
            description="PM: Initialize project structure and documentation",
            environment="pm-env",
            commands=[
                f"mkdir -p {self.project_path}/backend {self.project_path}/frontend {self.project_path}/infrastructure {self.project_path}/docs",
                
                # Create project charter
                f"""cat > {self.project_path}/docs/PROJECT_CHARTER.md << 'EOF'
# E-Commerce Platform MVP - Project Charter

## Project Overview
Building a modern, scalable e-commerce platform with microservices architecture.

## Team Structure
- **Project Manager**: Overall coordination and planning
- **Senior Full-Stack Developer**: Core features and integration
- **Backend Specialist**: API, database, and business logic
- **Frontend Specialist**: UI/UX and client applications
- **DevOps Engineer**: Infrastructure and deployment

## Key Deliverables
1. Product catalog with search
2. Shopping cart functionality
3. User authentication and profiles
4. Checkout and payment processing
5. Admin dashboard
6. Production deployment

## Timeline
- Week 1: Foundation and setup
- Week 2-3: Core features development
- Week 4: Advanced features and integration
- Week 5: Testing, optimization, and deployment

## Success Criteria
- All features working end-to-end
- 95%+ test coverage
- Performance: <200ms API response time
- Scalable to 10,000 concurrent users
EOF""",
                
                # Create task tracking board
                f"""cat > {self.project_path}/docs/TASK_BOARD.md << 'EOF'
# Task Board

## In Progress
- [ ] Project initialization

## Assigned
{chr(10).join(f"- [ ] {task.task_id}: {task.title} (@{task_assignments.get(task.task_id, 'unassigned')})" for task in self.project_plan.tasks)}

## Completed
- [x] Project planning
- [x] Team formation
EOF""",
                
                # Create communication guidelines
                f"""cat > {self.project_path}/docs/COMMUNICATION.md << 'EOF'
# Team Communication Guidelines

## Daily Standup Format
1. What I completed yesterday
2. What I'm working on today
3. Any blockers or dependencies

## Code Review Process
1. Create feature branch
2. Implement feature with tests
3. Submit PR with description
4. PM + 1 team member review
5. Merge after approval

## Escalation Path
Technical Issues -> Senior Developer -> PM
Infrastructure -> DevOps -> PM
Design/UX -> Frontend Specialist -> PM
EOF"""
            ],
            priority=10
        )
        conductor_tasks.append(pm_setup_task)
        
        # Now create development tasks with PM instructions
        for project_task in self.project_plan.tasks[:6]:  # Start with first 6 tasks
            agent_id = task_assignments.get(project_task.task_id)
            if not agent_id:
                continue
                
            agent_info = team_members[agent_id]
            
            # PM creates detailed instructions for each task
            pm_instruction = self._create_pm_instruction(project_task, agent_info)
            
            # Create the actual development task
            dev_task = Task(
                task_id=project_task.task_id,
                task_type="isolated_execution",
                description=f"{agent_info['name']}: {project_task.title}",
                environment=agent_info['environment'],
                commands=self._generate_task_commands(project_task, agent_id),
                priority=project_task.priority,
                metadata={
                    "pm_instruction": pm_instruction,
                    "assigned_to": agent_id,
                    "estimated_hours": project_task.estimated_hours,
                    "deliverables": project_task.deliverables
                }
            )
            conductor_tasks.append(dev_task)
            
            # Store assignment
            self.task_assignments[project_task.task_id] = {
                "task": project_task,
                "agent": agent_info,
                "status": TaskStatus.ASSIGNED
            }
        
        # PM monitoring task
        pm_monitor_task = Task(
            task_id="PM-002",
            task_type="isolated_execution",
            description="PM: Monitor progress and create status report",
            environment="pm-env",
            commands=[
                f"cd {self.project_path}",
                "echo '📊 Generating progress report...'",
                
                # Create progress report
                f"""cat > {self.project_path}/docs/PROGRESS_REPORT.md << 'EOF'
# Progress Report - {datetime.now().strftime('%Y-%m-%d')}

## Summary
- Tasks Completed: 0/14
- Current Phase: Foundation
- On Track: Yes

## Team Performance
- Senior Full-Stack Developer: Setting up infrastructure
- Backend Specialist: Designing database schema
- Frontend Specialist: Initializing frontend framework
- DevOps Engineer: Creating Docker environment

## Risks & Issues
- None identified yet

## Next Steps
1. Complete foundation tasks
2. Begin core feature development
3. Daily standup meetings

*Report generated by PM Agent*
EOF"""
            ],
            priority=1
        )
        conductor_tasks.append(pm_monitor_task)
        
        return conductor_tasks
    
    def _create_pm_instruction(self, task: ProjectTask, agent_info: Dict[str, Any]) -> str:
        """PMが各タスクの詳細な指示を作成"""
        instruction = f"""
### Task Assignment from PM

**Task ID**: {task.task_id}
**Title**: {task.title}
**Assigned to**: {agent_info['name']}
**Priority**: {task.priority}/10
**Estimated Time**: {task.estimated_hours} hours

**Objective**:
{task.description}

**Deliverables**:
{chr(10).join(f"- {d}" for d in task.deliverables)}

**Technical Requirements**:
- Follow project coding standards
- Include comprehensive tests
- Document all public APIs
- Ensure mobile responsiveness (if UI)

**Dependencies**:
{chr(10).join(f"- {dep}" for dep in task.dependencies) if task.dependencies else "- None"}

**Definition of Done**:
1. Code complete and reviewed
2. Tests passing with >90% coverage
3. Documentation updated
4. No critical security issues
5. Performance benchmarks met

Please update the task board when starting and upon completion.
Reach out if you need clarification or encounter blockers.

Best regards,
Project Manager
"""
        return instruction
    
    def _generate_task_commands(self, task: ProjectTask, agent_id: str) -> List[str]:
        """各タスクの具体的なコマンドを生成"""
        commands = [f"cd {self.project_path}"]
        
        # Task-specific commands
        if task.task_id == "TASK-001":  # Infrastructure setup
            commands.extend([
                "mkdir -p backend frontend infrastructure database scripts",
                
                # Create Dockerfile for backend
                """cat > backend/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF""",
                
                # Create docker-compose.yml
                """cat > docker-compose.yml << 'EOF'
version: '3.9'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ecommerce
      POSTGRES_USER: ecommerce
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://ecommerce:secret@postgres/ecommerce
      REDIS_URL: redis://redis:6379
      JWT_SECRET: your-secret-key
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  postgres_data:
EOF""",
                
                "echo '✅ Infrastructure setup complete'"
            ])
            
        elif task.task_id == "TASK-002":  # Database design
            commands.extend([
                "mkdir -p database/migrations database/seeds",
                
                # Create database schema
                """cat > database/schema.sql << 'EOF'
-- E-Commerce Database Schema

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    phone VARCHAR(20),
    role VARCHAR(50) DEFAULT 'customer',
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    compare_at_price DECIMAL(10, 2),
    cost DECIMAL(10, 2),
    inventory_quantity INTEGER DEFAULT 0,
    weight DECIMAL(10, 3),
    status VARCHAR(50) DEFAULT 'active',
    category_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Categories table
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    parent_id UUID REFERENCES categories(id),
    description TEXT,
    image_url VARCHAR(500),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product images
CREATE TABLE product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    alt_text VARCHAR(255),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shopping carts
CREATE TABLE carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cart items
CREATE TABLE cart_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id UUID REFERENCES carts(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending',
    subtotal DECIMAL(10, 2) NOT NULL,
    tax_amount DECIMAL(10, 2) DEFAULT 0,
    shipping_amount DECIMAL(10, 2) DEFAULT 0,
    total_amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    payment_status VARCHAR(50) DEFAULT 'pending',
    shipping_address JSONB,
    billing_address JSONB,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order items
CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id),
    quantity INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_cart_items_cart ON cart_items(cart_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);

-- Updated timestamp triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_carts_updated_at BEFORE UPDATE ON carts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EOF""",
                
                # Create ER diagram script
                """cat > database/create_er_diagram.py << 'EOF'
#!/usr/bin/env python3
import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(1, 1, figsize=(12, 10))

# Define table positions
tables = {
    'users': (2, 8),
    'products': (6, 8),
    'categories': (10, 8),
    'carts': (2, 5),
    'cart_items': (4, 3),
    'orders': (8, 5),
    'order_items': (10, 3),
    'product_images': (6, 5)
}

# Draw tables
for table, (x, y) in tables.items():
    rect = patches.FancyBboxPatch((x-1, y-0.5), 2, 1,
                                  boxstyle="round,pad=0.1",
                                  facecolor='lightblue',
                                  edgecolor='darkblue')
    ax.add_patch(rect)
    ax.text(x, y, table, ha='center', va='center', fontweight='bold')

# Draw relationships
relationships = [
    ('users', 'carts'),
    ('users', 'orders'),
    ('products', 'cart_items'),
    ('products', 'order_items'),
    ('products', 'product_images'),
    ('categories', 'products'),
    ('carts', 'cart_items'),
    ('orders', 'order_items')
]

for table1, table2 in relationships:
    x1, y1 = tables[table1]
    x2, y2 = tables[table2]
    ax.plot([x1, x2], [y1, y2], 'k-', linewidth=1)

ax.set_xlim(0, 12)
ax.set_ylim(0, 10)
ax.axis('off')
ax.set_title('E-Commerce Database Schema', fontsize=16, fontweight='bold')

plt.tight_layout()
plt.savefig('database/er_diagram.png', dpi=150)
print('ER diagram saved to database/er_diagram.png')
EOF""",
                
                "python3 database/create_er_diagram.py || echo 'ER diagram generation skipped'",
                "echo '✅ Database schema design complete'"
            ])
            
        elif task.task_id == "TASK-003":  # API boilerplate
            commands.extend([
                "cd backend",
                
                # Create requirements.txt
                """cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
asyncpg==0.29.0
alembic==1.12.1
pydantic==2.5.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
redis==5.0.1
celery==5.3.4
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.2
EOF""",
                
                # Create main application file
                """cat > main.py << 'EOF'
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import settings
from core.database import engine, Base
from api.v1.router import api_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    logger.info("Shutting down...")

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "E-Commerce API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
EOF""",
                
                # Create project structure
                "mkdir -p api/v1/endpoints core models schemas services utils tests",
                
                # Create core config
                """cat > core/__init__.py << 'EOF'
# Core module
EOF""",
                
                """cat > core/config.py << 'EOF'
from pydantic_settings import BaseSettings
from typing import List
import secrets

class Settings(BaseSettings):
    PROJECT_NAME: str = "E-Commerce API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "postgresql://ecommerce:secret@localhost/ecommerce"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
EOF""",
                
                # Create database config
                """cat > core/database.py << 'EOF'
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'),
    echo=True,
)

# Create async session
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Create base class for models
Base = declarative_base()

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
EOF""",
                
                # Create authentication utilities
                """cat > core/auth.py << 'EOF'
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # TODO: Get user from database
    return {"user_id": user_id}
EOF""",
                
                # Create API router
                """cat > api/__init__.py << 'EOF'
# API module
EOF""",
                
                """cat > api/v1/__init__.py << 'EOF'
# API v1 module
EOF""",
                
                """cat > api/v1/router.py << 'EOF'
from fastapi import APIRouter
from .endpoints import auth, users, products, cart, orders

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
EOF""",
                
                # Create basic auth endpoint
                "mkdir -p api/v1/endpoints",
                
                """cat > api/v1/endpoints/__init__.py << 'EOF'
# API endpoints
EOF""",
                
                """cat > api/v1/endpoints/auth.py << 'EOF'
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from core.database import get_db
from core.config import settings
from core.auth import verify_password, create_access_token

router = APIRouter()

@router.post("/login")
async def login(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    # TODO: Implement user authentication
    # For now, return a dummy token
    access_token = create_access_token(
        data={"sub": "user@example.com"},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register")
async def register(
    email: str,
    password: str,
    full_name: str,
    db: AsyncSession = Depends(get_db)
):
    # TODO: Implement user registration
    return {"message": "User registration endpoint"}
EOF""",
                
                # Create placeholder endpoints
                """cat > api/v1/endpoints/users.py << 'EOF'
from fastapi import APIRouter, Depends
from core.auth import get_current_user

router = APIRouter()

@router.get("/me")
async def get_current_user_info(current_user = Depends(get_current_user)):
    return current_user

@router.put("/me")
async def update_user_info(current_user = Depends(get_current_user)):
    return {"message": "Update user endpoint"}
EOF""",
                
                """cat > api/v1/endpoints/products.py << 'EOF'
from fastapi import APIRouter, Query
from typing import List, Optional

router = APIRouter()

@router.get("/")
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None
):
    return {"message": "List products endpoint", "skip": skip, "limit": limit}

@router.get("/{product_id}")
async def get_product(product_id: str):
    return {"message": f"Get product {product_id}"}

@router.post("/")
async def create_product():
    return {"message": "Create product endpoint"}
EOF""",
                
                """cat > api/v1/endpoints/cart.py << 'EOF'
from fastapi import APIRouter, Depends
from core.auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_cart(current_user = Depends(get_current_user)):
    return {"message": "Get cart endpoint"}

@router.post("/items")
async def add_to_cart(current_user = Depends(get_current_user)):
    return {"message": "Add to cart endpoint"}

@router.delete("/items/{item_id}")
async def remove_from_cart(item_id: str, current_user = Depends(get_current_user)):
    return {"message": f"Remove item {item_id} from cart"}
EOF""",
                
                """cat > api/v1/endpoints/orders.py << 'EOF'
from fastapi import APIRouter, Depends
from core.auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_orders(current_user = Depends(get_current_user)):
    return {"message": "List orders endpoint"}

@router.post("/")
async def create_order(current_user = Depends(get_current_user)):
    return {"message": "Create order endpoint"}

@router.get("/{order_id}")
async def get_order(order_id: str, current_user = Depends(get_current_user)):
    return {"message": f"Get order {order_id}"}
EOF""",
                
                "echo '✅ FastAPI boilerplate created successfully'"
            ])
            
        elif task.task_id == "TASK-004":  # Frontend setup
            commands.extend([
                "cd frontend",
                
                # Create package.json
                """cat > package.json << 'EOF'
{
  "name": "ecommerce-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "dependencies": {
    "next": "14.0.4",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-query": "^5.8.4",
    "axios": "^1.6.2",
    "zustand": "^4.4.7",
    "react-hook-form": "^7.48.2",
    "zod": "^3.22.4",
    "@hookform/resolvers": "^3.3.2",
    "tailwindcss": "^3.3.6",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "@heroicons/react": "^2.0.18",
    "clsx": "^2.0.0"
  },
  "devDependencies": {
    "@types/node": "^20.10.4",
    "@types/react": "^18.2.45",
    "@types/react-dom": "^18.2.18",
    "typescript": "^5.3.3",
    "eslint": "^8.55.0",
    "eslint-config-next": "14.0.4",
    "@testing-library/react": "^14.1.2",
    "@testing-library/jest-dom": "^6.1.5",
    "jest": "^29.7.0",
    "jest-environment-jsdom": "^29.7.0"
  }
}
EOF""",
                
                # Create TypeScript config
                """cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
EOF""",
                
                # Create Tailwind config
                """cat > tailwind.config.js << 'EOF'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
    },
  },
  plugins: [],
}
EOF""",
                
                # Create PostCSS config
                """cat > postcss.config.js << 'EOF'
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
EOF""",
                
                # Create Next.js config
                """cat > next.config.js << 'EOF'
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['localhost', 'example.com'],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.NEXT_PUBLIC_API_URL + '/:path*',
      },
    ];
  },
}

module.exports = nextConfig
EOF""",
                
                # Create app structure
                "mkdir -p src/app src/components/ui src/components/layout src/lib src/hooks src/types src/services",
                
                # Create global styles
                """cat > src/app/globals.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
}
EOF""",
                
                # Create layout
                """cat > src/app/layout.tsx << 'EOF'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'E-Commerce Store',
  description: 'Modern e-commerce platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  )
}
EOF""",
                
                # Create home page
                """cat > src/app/page.tsx << 'EOF'
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-8">E-Commerce Platform</h1>
      <p className="text-xl text-gray-600">Welcome to our store</p>
    </main>
  )
}
EOF""",
                
                # Create API client
                """cat > src/lib/api-client.ts << 'EOF'
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
EOF""",
                
                # Create types
                """cat > src/types/index.ts << 'EOF'
export interface User {
  id: string;
  email: string;
  fullName: string;
  role: 'customer' | 'admin';
  createdAt: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  description: string;
  price: number;
  compareAtPrice?: number;
  inventoryQuantity: number;
  images: ProductImage[];
  category?: Category;
  createdAt: string;
}

export interface ProductImage {
  id: string;
  url: string;
  altText?: string;
  sortOrder: number;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  imageUrl?: string;
}

export interface CartItem {
  id: string;
  product: Product;
  quantity: number;
  price: number;
}

export interface Cart {
  id: string;
  items: CartItem[];
  subtotal: number;
  total: number;
}

export interface Order {
  id: string;
  orderNumber: string;
  status: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
  items: OrderItem[];
  subtotal: number;
  tax: number;
  shipping: number;
  total: number;
  createdAt: string;
}

export interface OrderItem {
  id: string;
  product: Product;
  quantity: number;
  price: number;
  total: number;
}
EOF""",
                
                # Create Dockerfile
                """cat > Dockerfile << 'EOF'
FROM node:18-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:18-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT 3000

CMD ["node", "server.js"]
EOF""",
                
                "echo '✅ Next.js frontend setup complete'"
            ])
            
        elif task.task_id == "TASK-005":  # Product catalog API
            commands.extend([
                "cd backend",
                
                # Create product models
                """cat > models/product.py << 'EOF'
from sqlalchemy import Column, String, Numeric, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from core.database import Base

class Product(Base):
    __tablename__ = "products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    compare_at_price = Column(Numeric(10, 2))
    cost = Column(Numeric(10, 2))
    inventory_quantity = Column(Integer, default=0)
    weight = Column(Numeric(10, 3))
    status = Column(String(50), default="active", index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    
    # Relationships
    category = relationship("Category", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    cart_items = relationship("CartItem", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    description = Column(Text)
    image_url = Column(String(500))
    sort_order = Column(Integer, default=0)
    
    # Relationships
    products = relationship("Product", back_populates="category")
    children = relationship("Category")

class ProductImage(Base):
    __tablename__ = "product_images"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"))
    url = Column(String(500), nullable=False)
    alt_text = Column(String(255))
    sort_order = Column(Integer, default=0)
    
    # Relationships
    product = relationship("Product", back_populates="images")
EOF""",
                
                # Create product schemas
                """cat > schemas/product.py << 'EOF'
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime

class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[UUID] = None
    sort_order: int = 0

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: Optional[int] = None

class Category(CategoryBase):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ProductImageBase(BaseModel):
    url: str
    alt_text: Optional[str] = None
    sort_order: int = 0

class ProductImage(ProductImageBase):
    id: UUID
    product_id: UUID
    
    model_config = ConfigDict(from_attributes=True)

class ProductBase(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    price: Decimal = Field(..., decimal_places=2)
    compare_at_price: Optional[Decimal] = Field(None, decimal_places=2)
    inventory_quantity: int = 0
    weight: Optional[Decimal] = Field(None, decimal_places=3)
    status: str = "active"
    category_id: Optional[UUID] = None

class ProductCreate(ProductBase):
    images: List[ProductImageBase] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, decimal_places=2)
    compare_at_price: Optional[Decimal] = Field(None, decimal_places=2)
    inventory_quantity: Optional[int] = None
    weight: Optional[Decimal] = Field(None, decimal_places=3)
    status: Optional[str] = None
    category_id: Optional[UUID] = None

class Product(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    category: Optional[Category] = None
    images: List[ProductImage] = []
    
    model_config = ConfigDict(from_attributes=True)

class ProductList(BaseModel):
    items: List[Product]
    total: int
    skip: int
    limit: int
EOF""",
                
                # Create product service
                """cat > services/product_service.py << 'EOF'
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from models.product import Product, Category, ProductImage
from schemas.product import ProductCreate, ProductUpdate

class ProductService:
    @staticmethod
    async def create_product(
        db: AsyncSession,
        product_data: ProductCreate
    ) -> Product:
        # Create product
        product_dict = product_data.model_dump(exclude={"images"})
        product = Product(**product_dict)
        
        # Add images
        for img_data in product_data.images:
            image = ProductImage(**img_data.model_dump(), product_id=product.id)
            product.images.append(image)
        
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    
    @staticmethod
    async def get_products(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        category_id: Optional[UUID] = None,
        search: Optional[str] = None,
        status: str = "active"
    ) -> tuple[List[Product], int]:
        query = select(Product).options(
            selectinload(Product.category),
            selectinload(Product.images)
        )
        
        # Apply filters
        if status:
            query = query.where(Product.status == status)
        if category_id:
            query = query.where(Product.category_id == category_id)
        if search:
            search_filter = or_(
                Product.name.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
        
        # Get total count
        count_query = select(func.count()).select_from(Product)
        if status:
            count_query = count_query.where(Product.status == status)
        if category_id:
            count_query = count_query.where(Product.category_id == category_id)
        if search:
            count_query = count_query.where(search_filter)
        
        total = await db.scalar(count_query)
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        products = result.scalars().all()
        
        return products, total
    
    @staticmethod
    async def get_product(
        db: AsyncSession,
        product_id: UUID
    ) -> Optional[Product]:
        query = select(Product).options(
            selectinload(Product.category),
            selectinload(Product.images)
        ).where(Product.id == product_id)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_product(
        db: AsyncSession,
        product_id: UUID,
        product_update: ProductUpdate
    ) -> Optional[Product]:
        product = await ProductService.get_product(db, product_id)
        if not product:
            return None
        
        update_data = product_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)
        
        await db.commit()
        await db.refresh(product)
        return product
    
    @staticmethod
    async def delete_product(
        db: AsyncSession,
        product_id: UUID
    ) -> bool:
        product = await ProductService.get_product(db, product_id)
        if not product:
            return False
        
        await db.delete(product)
        await db.commit()
        return True
    
    @staticmethod
    async def update_inventory(
        db: AsyncSession,
        product_id: UUID,
        quantity_change: int
    ) -> Optional[Product]:
        product = await ProductService.get_product(db, product_id)
        if not product:
            return None
        
        product.inventory_quantity += quantity_change
        if product.inventory_quantity < 0:
            product.inventory_quantity = 0
        
        await db.commit()
        await db.refresh(product)
        return product
EOF""",
                
                # Update product endpoints
                """cat > api/v1/endpoints/products.py << 'EOF'
from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.product import Product, ProductCreate, ProductUpdate, ProductList
from services.product_service import ProductService

router = APIRouter()

@router.post("/", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new product"""
    product = await ProductService.create_product(db, product_data)
    return product

@router.get("/", response_model=ProductList)
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[UUID] = None,
    search: Optional[str] = None,
    status: str = Query("active", regex="^(active|inactive|draft)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get list of products with filtering and pagination"""
    products, total = await ProductService.get_products(
        db, skip, limit, category_id, search, status
    )
    return ProductList(
        items=products,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{product_id}", response_model=Product)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific product by ID"""
    product = await ProductService.get_product(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return product

@router.put("/{product_id}", response_model=Product)
async def update_product(
    product_id: UUID,
    product_update: ProductUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a product"""
    product = await ProductService.update_product(db, product_id, product_update)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a product"""
    success = await ProductService.delete_product(db, product_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return None

@router.post("/{product_id}/inventory", response_model=Product)
async def update_inventory(
    product_id: UUID,
    quantity_change: int,
    db: AsyncSession = Depends(get_db)
):
    """Update product inventory"""
    product = await ProductService.update_inventory(db, product_id, quantity_change)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return product
EOF""",
                
                # Create test file
                """cat > tests/test_products.py << 'EOF'
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from main import app
from models.product import Product

@pytest.mark.asyncio
async def test_create_product(client: AsyncClient, db: AsyncSession):
    product_data = {
        "sku": "TEST-001",
        "name": "Test Product",
        "description": "A test product",
        "price": 29.99,
        "inventory_quantity": 100,
        "images": [
            {"url": "https://example.com/image1.jpg", "alt_text": "Product image"}
        ]
    }
    
    response = await client.post("/api/v1/products/", json=product_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["sku"] == product_data["sku"]
    assert data["name"] == product_data["name"]
    assert float(data["price"]) == product_data["price"]
    assert len(data["images"]) == 1

@pytest.mark.asyncio
async def test_get_products(client: AsyncClient, db: AsyncSession):
    # Create test products
    for i in range(5):
        product = Product(
            sku=f"TEST-{i:03d}",
            name=f"Test Product {i}",
            price=10.00 + i,
            inventory_quantity=10
        )
        db.add(product)
    await db.commit()
    
    # Test pagination
    response = await client.get("/api/v1/products/?skip=0&limit=3")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] >= 5
    assert data["skip"] == 0
    assert data["limit"] == 3

@pytest.mark.asyncio
async def test_search_products(client: AsyncClient, db: AsyncSession):
    # Create products
    product1 = Product(sku="SHIRT-001", name="Blue Shirt", price=25.00)
    product2 = Product(sku="PANTS-001", name="Blue Jeans", price=45.00)
    product3 = Product(sku="SHIRT-002", name="Red Shirt", price=25.00)
    
    db.add_all([product1, product2, product3])
    await db.commit()
    
    # Search for "shirt"
    response = await client.get("/api/v1/products/?search=shirt")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) == 2
    assert all("shirt" in item["name"].lower() for item in data["items"])
EOF""",
                
                "echo '✅ Product catalog API implementation complete'"
            ])
            
        elif task.task_id == "TASK-006":  # Product UI
            commands.extend([
                "cd frontend/src",
                
                # Create product components
                "mkdir -p components/products hooks/products",
                
                # Product card component
                """cat > components/products/ProductCard.tsx << 'EOF'
import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Product } from '@/types';
import { formatCurrency } from '@/lib/utils';

interface ProductCardProps {
  product: Product;
  onAddToCart?: (product: Product) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({ product, onAddToCart }) => {
  const mainImage = product.images[0];
  const isOnSale = product.compareAtPrice && product.compareAtPrice > product.price;
  const salePercentage = isOnSale
    ? Math.round(((product.compareAtPrice - product.price) / product.compareAtPrice) * 100)
    : 0;

  return (
    <div className="group relative">
      {isOnSale && (
        <div className="absolute top-2 left-2 z-10 bg-red-500 text-white px-2 py-1 text-sm font-semibold rounded">
          -{salePercentage}%
        </div>
      )}
      
      <Link href={`/products/${product.id}`}>
        <div className="aspect-square overflow-hidden rounded-lg bg-gray-100 group-hover:opacity-75">
          {mainImage ? (
            <Image
              src={mainImage.url}
              alt={mainImage.altText || product.name}
              width={300}
              height={300}
              className="h-full w-full object-cover object-center"
            />
          ) : (
            <div className="h-full w-full flex items-center justify-center text-gray-400">
              No image
            </div>
          )}
        </div>
      </Link>
      
      <div className="mt-4 space-y-2">
        <div>
          <h3 className="text-sm font-medium text-gray-900">
            <Link href={`/products/${product.id}`}>
              {product.name}
            </Link>
          </h3>
          <p className="mt-1 text-sm text-gray-500">{product.category?.name}</p>
        </div>
        
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <p className="text-lg font-semibold text-gray-900">
              {formatCurrency(product.price)}
            </p>
            {isOnSale && (
              <p className="text-sm text-gray-500 line-through">
                {formatCurrency(product.compareAtPrice)}
              </p>
            )}
          </div>
          
          {product.inventoryQuantity > 0 ? (
            <button
              onClick={(e) => {
                e.preventDefault();
                onAddToCart?.(product);
              }}
              className="rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-700"
            >
              Add to Cart
            </button>
          ) : (
            <span className="text-sm text-gray-500">Out of stock</span>
          )}
        </div>
      </div>
    </div>
  );
};
EOF""",
                
                # Product grid component
                """cat > components/products/ProductGrid.tsx << 'EOF'
import React from 'react';
import { Product } from '@/types';
import { ProductCard } from './ProductCard';

interface ProductGridProps {
  products: Product[];
  onAddToCart?: (product: Product) => void;
  loading?: boolean;
}

export const ProductGrid: React.FC<ProductGridProps> = ({ 
  products, 
  onAddToCart,
  loading = false 
}) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 xl:gap-x-8">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="animate-pulse">
            <div className="aspect-square bg-gray-200 rounded-lg"></div>
            <div className="mt-4 space-y-2">
              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">No products found</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 xl:gap-x-8">
      {products.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          onAddToCart={onAddToCart}
        />
      ))}
    </div>
  );
};
EOF""",
                
                # Search and filter component
                """cat > components/products/ProductFilters.tsx << 'EOF'
import React from 'react';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { Category } from '@/types';

interface ProductFiltersProps {
  categories: Category[];
  selectedCategory?: string;
  searchQuery: string;
  onCategoryChange: (categoryId: string | undefined) => void;
  onSearchChange: (query: string) => void;
}

export const ProductFilters: React.FC<ProductFiltersProps> = ({
  categories,
  selectedCategory,
  searchQuery,
  onCategoryChange,
  onSearchChange,
}) => {
  return (
    <div className="flex flex-col space-y-4 sm:flex-row sm:space-y-0 sm:space-x-4">
      <div className="flex-1">
        <div className="relative">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
          </div>
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search products..."
            className="block w-full rounded-md border-gray-300 pl-10 pr-3 py-2 text-sm placeholder-gray-400 focus:border-primary-500 focus:ring-primary-500"
          />
        </div>
      </div>
      
      <select
        value={selectedCategory || ''}
        onChange={(e) => onCategoryChange(e.target.value || undefined)}
        className="rounded-md border-gray-300 py-2 pl-3 pr-10 text-sm focus:border-primary-500 focus:ring-primary-500"
      >
        <option value="">All Categories</option>
        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.name}
          </option>
        ))}
      </select>
    </div>
  );
};
EOF""",
                
                # Product service
                """cat > services/products.ts << 'EOF'
import { apiClient } from '@/lib/api-client';
import { Product, ProductList } from '@/types';

export const productService = {
  async getProducts(params?: {
    skip?: number;
    limit?: number;
    categoryId?: string;
    search?: string;
    status?: string;
  }): Promise<ProductList> {
    const { data } = await apiClient.get('/products', { params });
    return data;
  },

  async getProduct(productId: string): Promise<Product> {
    const { data } = await apiClient.get(`/products/${productId}`);
    return data;
  },

  async createProduct(productData: any): Promise<Product> {
    const { data } = await apiClient.post('/products', productData);
    return data;
  },

  async updateProduct(productId: string, productData: any): Promise<Product> {
    const { data } = await apiClient.put(`/products/${productId}`, productData);
    return data;
  },

  async deleteProduct(productId: string): Promise<void> {
    await apiClient.delete(`/products/${productId}`);
  },

  async updateInventory(productId: string, quantityChange: number): Promise<Product> {
    const { data } = await apiClient.post(`/products/${productId}/inventory`, {
      quantity_change: quantityChange,
    });
    return data;
  },
};
EOF""",
                
                # Product hooks
                """cat > hooks/products/useProducts.ts << 'EOF'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productService } from '@/services/products';
import { Product } from '@/types';

export const useProducts = (params?: {
  skip?: number;
  limit?: number;
  categoryId?: string;
  search?: string;
}) => {
  return useQuery({
    queryKey: ['products', params],
    queryFn: () => productService.getProducts(params),
  });
};

export const useProduct = (productId: string) => {
  return useQuery({
    queryKey: ['product', productId],
    queryFn: () => productService.getProduct(productId),
    enabled: !!productId,
  });
};

export const useCreateProduct = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: productService.createProduct,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
};

export const useUpdateProduct = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ productId, data }: { productId: string; data: any }) =>
      productService.updateProduct(productId, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', variables.productId] });
    },
  });
};

export const useDeleteProduct = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: productService.deleteProduct,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
};
EOF""",
                
                # Products page
                """cat > app/products/page.tsx << 'EOF'
'use client';

import React, { useState } from 'react';
import { useProducts } from '@/hooks/products/useProducts';
import { ProductGrid } from '@/components/products/ProductGrid';
import { ProductFilters } from '@/components/products/ProductFilters';
import { useCart } from '@/hooks/useCart';

export default function ProductsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>();
  const [currentPage, setCurrentPage] = useState(0);
  const limit = 20;
  
  const { data, isLoading } = useProducts({
    skip: currentPage * limit,
    limit,
    categoryId: selectedCategory,
    search: searchQuery,
  });
  
  const { addToCart } = useCart();
  
  // Mock categories for now
  const categories = [
    { id: '1', name: 'Electronics', slug: 'electronics' },
    { id: '2', name: 'Clothing', slug: 'clothing' },
    { id: '3', name: 'Home & Garden', slug: 'home-garden' },
  ];
  
  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="bg-white">
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6 sm:py-24 lg:max-w-7xl lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            All Products
          </h1>
          <p className="mt-4 text-base text-gray-500">
            Browse our collection of high-quality products
          </p>
        </div>
        
        <div className="mb-8">
          <ProductFilters
            categories={categories}
            selectedCategory={selectedCategory}
            searchQuery={searchQuery}
            onCategoryChange={setSelectedCategory}
            onSearchChange={setSearchQuery}
          />
        </div>
        
        <ProductGrid
          products={data?.items || []}
          onAddToCart={addToCart}
          loading={isLoading}
        />
        
        {totalPages > 1 && (
          <div className="mt-8 flex justify-center">
            <nav className="flex items-center space-x-2">
              <button
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                disabled={currentPage === 0}
                className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
              >
                Previous
              </button>
              
              <span className="text-sm text-gray-700">
                Page {currentPage + 1} of {totalPages}
              </span>
              
              <button
                onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
                disabled={currentPage === totalPages - 1}
                className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
              >
                Next
              </button>
            </nav>
          </div>
        )}
      </div>
    </div>
  );
}
EOF""",
                
                # Utils file
                """cat > lib/utils.ts << 'EOF'
export function formatCurrency(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount);
}

export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}
EOF""",
                
                "echo '✅ Product UI components created successfully'"
            ])
            
        # Add more task implementations as needed...
        
        return commands
    
    async def monitor_and_report(self, results: Dict[str, TaskResult]):
        """PMが進捗を監視してレポートを生成"""
        print("\n📊 PM is generating progress report...")
        
        # Analyze results
        completed_tasks = [t for t, r in results.items() if r.status == "success"]
        failed_tasks = [t for t, r in results.items() if r.status == "failed"]
        
        # Create PM's executive summary
        summary_task = Task(
            task_id="PM-SUMMARY",
            task_type="isolated_execution",
            description="PM: Generate executive summary and next steps",
            environment="pm-env",
            commands=[
                f"cd {self.project_path}",
                
                # Update task board
                f"""cat > docs/TASK_BOARD_UPDATE.md << 'EOF'
# Task Board Update - {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Completed ✅
{chr(10).join(f"- [x] {tid}" for tid in completed_tasks)}

## Failed ❌
{chr(10).join(f"- [ ] {tid} (FAILED)" for tid in failed_tasks)}

## In Progress 🚧
- [ ] TASK-007: Shopping cart implementation
- [ ] TASK-008: Authentication system

## Upcoming 📋
- [ ] TASK-009: Checkout process
- [ ] TASK-010: Payment integration
- [ ] TASK-011: Admin dashboard
EOF""",
                
                # Create executive summary
                f"""cat > docs/EXECUTIVE_SUMMARY.md << 'EOF'
# Executive Summary - Sprint 1

## Project: E-Commerce Platform MVP
**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Sprint**: 1 of 5
**PM**: AI Project Manager

## Key Achievements
1. ✅ Project infrastructure established
2. ✅ Database schema designed and documented
3. ✅ API framework initialized with FastAPI
4. ✅ Frontend framework setup with Next.js
5. ✅ Product catalog API implemented
6. ✅ Product UI components created

## Team Performance
- **Productivity**: {len(completed_tasks)}/{len(results)} tasks completed ({len(completed_tasks)/len(results)*100:.0f}%)
- **Quality**: All completed tasks passed initial review
- **Collaboration**: Excellent - no blocking dependencies

## Current Status
- **On Track**: ✅ YES
- **Budget**: Within allocated hours
- **Risks**: None identified

## Next Sprint Goals
1. Complete shopping cart functionality
2. Implement user authentication
3. Begin checkout process
4. Start payment integration

## Recommendations
1. Continue current velocity
2. Schedule code review session
3. Plan user testing for Week 3
4. Prepare staging environment

## Resource Allocation Next Sprint
- Backend Specialist: 60% authentication, 40% cart API
- Frontend Specialist: 70% cart UI, 30% auth UI
- Full-Stack: 100% checkout process
- DevOps: 50% staging setup, 50% monitoring

---
*This report was generated by the PM Agent based on real-time project data*
EOF""",
                
                # Send status updates to team
                f"""cat > docs/TEAM_UPDATE.md << 'EOF'
# Team Update from PM

Great work team! 🎉

## Sprint 1 Highlights
- Foundation phase completed successfully
- All infrastructure and base components in place
- Excellent code quality and documentation

## Individual Recognition
- **Backend Specialist**: Excellent database design and API structure
- **Frontend Specialist**: Clean component architecture
- **DevOps Engineer**: Robust Docker setup
- **Senior Full-Stack**: Great coordination on product features

## Focus for Next Week
1. Shopping cart (Full-Stack + Backend)
2. Authentication (Backend + Frontend)
3. Staging environment (DevOps)

Keep up the excellent work! Feel free to reach out if you need any clarification or face blockers.

Best,
PM
EOF""",
                
                "echo '✅ PM reports generated successfully'"
            ],
            priority=1
        )
        
        return summary_task
    
    async def execute_demo(self):
        """デモを実行"""
        self.start_time = time.time()
        
        # Step 1: PM creates project plan
        self.create_project_plan()
        print(f"\n📅 Project Timeline: 5 weeks")
        print(f"📊 Total Tasks: {len(self.project_plan.tasks)}")
        print(f"👥 Team Size: 4 developers + 1 PM")
        
        # Step 2: PM assigns tasks
        tasks = self.assign_tasks_to_team()
        print(f"\n📝 PM has created {len(tasks)} tasks for the team")
        
        # Step 3: Execute assigned tasks
        print("\n🚀 Team is working on assigned tasks...\n")
        
        results = {}
        for i, task in enumerate(tasks):
            print(f"\n{'='*60}")
            print(f"Task {i+1}/{len(tasks)}: {task.description}")
            print(f"Priority: {task.priority}/10")
            
            # Get PM instructions if available
            if hasattr(task, 'metadata') and task.metadata.get('pm_instruction'):
                print("\n📋 PM Instructions:")
                print(task.metadata['pm_instruction'])
            
            # Execute task
            result = self.orchestrator.execute_task(task)
            results[task.task_id] = result
            
            # Print result
            status_icon = "✅" if result.status == "success" else "❌"
            print(f"\n{status_icon} Result: {result.status}")
            print(f"⏱️  Time: {result.execution_time:.2f}s")
            
            if result.status == "failed" and result.error:
                print(f"❌ Error: {result.error}")
            
            # Brief pause between tasks
            await asyncio.sleep(1)
        
        # Step 4: PM monitors and reports
        summary_task = await self.monitor_and_report(results)
        summary_result = self.orchestrator.execute_task(summary_task)
        
        # Final summary
        self._print_final_summary(results)
    
    def _print_final_summary(self, results: Dict[str, TaskResult]):
        """最終サマリーを表示"""
        total_time = time.time() - self.start_time
        successful = sum(1 for r in results.values() if r.status == "success")
        failed = sum(1 for r in results.values() if r.status == "failed")
        
        print("\n" + "="*70)
        print("🏁 PM-LED DEVELOPMENT DEMO COMPLETE!")
        print("="*70)
        
        print(f"\n📊 Final Report:")
        print(f"  Project: E-Commerce Platform MVP")
        print(f"  Duration: {total_time:.2f}s")
        print(f"  Tasks Completed: {successful}/{len(results)}")
        print(f"  Success Rate: {successful/len(results)*100:.0f}%")
        
        print(f"\n👥 Team Performance:")
        print(f"  PM: Successfully coordinated team and created project structure")
        print(f"  Backend Specialist: Database and API foundation established")
        print(f"  Frontend Specialist: UI framework and components ready")
        print(f"  DevOps Engineer: Infrastructure and deployment setup complete")
        print(f"  Senior Full-Stack: Product features integrated")
        
        print(f"\n📁 Deliverables Created:")
        print(f"  - Project documentation and task board")
        print(f"  - Database schema with ER diagram")
        print(f"  - FastAPI backend with authentication")
        print(f"  - Next.js frontend with TypeScript")
        print(f"  - Docker development environment")
        print(f"  - Product catalog with API and UI")
        
        print(f"\n🎯 Key Insights:")
        print(f"  1. PM agent successfully delegated tasks based on team skills")
        print(f"  2. Clear communication through documentation and instructions")
        print(f"  3. Parallel execution where dependencies allowed")
        print(f"  4. Regular monitoring and reporting kept project on track")
        
        print(f"\n✨ This demonstrates how Claude Conductor can simulate")
        print(f"   real-world software development teams with hierarchical")
        print(f"   management and specialized roles!")
    
    def cleanup(self):
        """クリーンアップ"""
        if self.orchestrator:
            self.orchestrator.stop()


async def main():
    """メイン実行関数"""
    demo = PMAgentDemo()
    
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
        print("\n👋 Thank you for watching the PM-led development demo!")


if __name__ == "__main__":
    asyncio.run(main())
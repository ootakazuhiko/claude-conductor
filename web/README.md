# Claude Conductor Web Dashboard

A modern, responsive web dashboard for monitoring and controlling the Claude Conductor multi-agent orchestration system.

## Features

### 🎯 Core Features
- **Real-time Monitoring**: Live updates via WebSocket connections
- **Agent Management**: Monitor agent status, health, and current tasks
- **Task Submission**: Submit tasks with various types and priorities
- **Statistics Dashboard**: Track performance metrics and execution history
- **Activity Logging**: Real-time activity feed with export capabilities

### 🔒 Security Features
- **JWT Authentication**: Secure user authentication system
- **Role-based Access Control**: Different permission levels
- **API Key Management**: Support for API key authentication
- **Audit Logging**: Comprehensive security event tracking
- **Session Management**: Secure session handling

### 📊 Advanced Features
- **Token Usage Analytics**: Monitor Claude API token consumption and costs
- **LLM-as-Judge Evaluation**: View task quality evaluations
- **MCP Integration Status**: Monitor Model Context Protocol connections
- **Performance Metrics**: Real-time performance monitoring
- **Export Capabilities**: Export logs and dashboard data

## Installation

### Prerequisites
- Python 3.8+
- FastAPI and dependencies (see requirements.txt)
- Claude Conductor system

### Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the dashboard only:**
   ```bash
   python web/dashboard.py --port 8080
   ```

3. **Start with orchestrator:**
   ```bash
   python web/dashboard.py --with-orchestrator --port 8080
   ```

4. **Start with security enabled:**
   ```bash
   python web/dashboard.py --secure --config config/config.yaml --port 8080
   ```

### Configuration Options

```bash
# Basic usage
python web/dashboard.py

# Custom port
python web/dashboard.py --port 8080

# Don't open browser automatically
python web/dashboard.py --no-browser

# Start with orchestrator
python web/dashboard.py --with-orchestrator

# Start with secure orchestrator
python web/dashboard.py --secure --config config/config.yaml

# Load custom configuration
python web/dashboard.py --config /path/to/config.yaml
```

## Usage

### Dashboard Sections

#### 📊 System Statistics
- **Tasks Completed/Failed**: Track task execution results
- **Average Execution Time**: Performance metrics
- **Active Agents**: Current agent count
- **Token Usage**: Claude API consumption
- **Cost Today**: Daily cost tracking

#### 🤖 Agent Status
- **Agent Health**: Real-time health monitoring
- **Current Tasks**: What each agent is working on
- **Performance Metrics**: Agent-specific statistics
- **Health Check Failures**: Error tracking

#### ➕ Task Management
- **Task Submission**: Create new tasks via web interface
- **Task Types**: Support for multiple task types:
  - Generic tasks
  - Code review
  - Code refactoring
  - Test generation
  - Code analysis
- **Priority Setting**: 1-10 priority scale
- **File Specification**: Attach files to tasks

#### 🔒 Security Management
- **User Authentication**: Login/logout functionality
- **Role Management**: View user roles and permissions
- **Security Statistics**: Authentication and authorization metrics
- **Audit Log Access**: View security events (admin only)

#### 📈 Advanced Analytics
- **Evaluation Reports**: LLM-as-judge evaluation results
- **Token Analytics**: Detailed usage and cost breakdown
- **Optimization Suggestions**: Cost reduction recommendations
- **MCP Integration**: External tool integration status

### API Endpoints

#### Authentication
- `POST /api/auth/login` - User authentication
- `GET /api/status` - System status (includes user info if authenticated)

#### Task Management
- `POST /api/task` - Submit new task
- `GET /api/agents` - Get agent status

#### Security (Admin only)
- `GET /api/security/stats` - Security statistics
- `GET /api/evaluation/reports` - Evaluation reports
- `GET /api/tokens/usage` - Token usage analytics

#### Real-time Updates
- `WebSocket /ws` - Real-time data updates

### Security Configuration

#### Default Users
- **Username**: `admin`
- **Default Roles**: Super Admin
- **Permissions**: Full system access

#### User Roles
- **Super Admin**: Full system control
- **Admin**: System management
- **Operator**: Task execution and monitoring
- **Agent Manager**: Agent control
- **Task Manager**: Task management
- **Viewer**: Read-only access
- **API Client**: Programmatic access

#### Permissions
- Orchestrator: admin, read, write
- Agent: create, read, update, delete, control
- Task: create, read, update, delete, execute
- System: admin, monitor, config
- Evaluation: read, admin

## Architecture

### Frontend Components
- **HTML5**: Modern semantic markup
- **CSS3**: Responsive design with grid layout
- **JavaScript ES6+**: Modern client-side functionality
- **WebSocket**: Real-time communication

### Backend Components
- **FastAPI**: High-performance web framework
- **Uvicorn**: ASGI server
- **Jinja2**: Template engine
- **WebSocket**: Real-time updates
- **JWT**: Secure authentication

### Integration Points
- **Claude Conductor**: Main orchestration system
- **Security Manager**: Authentication and authorization
- **Evaluation Manager**: Task quality assessment
- **Token Optimizer**: Usage and cost tracking
- **MCP Integration**: External tool connections

## Development

### Adding New Features

1. **Backend API Endpoints**:
   ```python
   @app.get("/api/new-feature")
   async def new_feature(current_user: Optional[User] = Depends(get_current_user)):
       # Implementation
       return {"data": "response"}
   ```

2. **Frontend Components**:
   ```javascript
   async function loadNewFeature() {
       const response = await fetch('/api/new-feature');
       const data = await response.json();
       updateUI(data);
   }
   ```

3. **Dashboard Integration**:
   ```html
   <div class="card">
       <h2>🆕 New Feature</h2>
       <div id="new-feature-content"></div>
   </div>
   ```

### Customization

#### Styling
- Modify `web/static/dashboard.css` for custom styles
- Update color scheme in CSS variables
- Add custom animations and transitions

#### Functionality
- Extend `DashboardManager` class in `dashboard.js`
- Add new API endpoints in `dashboard.py`
- Create custom WebSocket message handlers

## Production Deployment

### Docker Deployment
```bash
# Build container with web dashboard
docker build -f containers/Dockerfile -t claude-conductor-web .

# Run with dashboard
docker run -p 8080:8080 claude-conductor-web python web/dashboard.py --port 8080
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-conductor-dashboard
spec:
  template:
    spec:
      containers:
      - name: dashboard
        image: claude-conductor-web:latest
        ports:
        - containerPort: 8080
        command: ["python", "web/dashboard.py", "--port", "8080"]
```

### Environment Variables
```bash
export CLAUDE_API_KEY="your-api-key"
export JWT_SECRET="your-jwt-secret"
export REDIS_URL="redis://localhost:6379"
```

### Performance Optimization
- Enable gzip compression
- Use CDN for static assets
- Configure proper caching headers
- Monitor WebSocket connection limits

## Security Considerations

### Production Security
- Change default JWT secret
- Use HTTPS in production
- Configure CORS appropriately
- Enable audit logging
- Regular security updates

### Access Control
- Configure role-based permissions
- Monitor authentication failures
- Set up rate limiting
- Enable session timeout

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check firewall settings
   - Verify port accessibility
   - Check browser security settings

2. **Authentication Issues**
   - Verify JWT secret configuration
   - Check user credentials
   - Review audit logs

3. **Performance Issues**
   - Monitor WebSocket message frequency
   - Check agent response times
   - Review browser console for errors

### Debug Mode
```bash
python web/dashboard.py --debug
```

### Logging
- Dashboard logs: stdout/stderr
- Access logs: FastAPI access logs
- Security logs: Audit system
- WebSocket logs: Connection status

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
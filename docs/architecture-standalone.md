# Claude Conductor - Architecture Diagrams

## Standalone Subset Architecture (単一PC版)

```mermaid
graph TB
    subgraph "Local Machine"
        subgraph "User Interface"
            Browser[Web Browser<br/>localhost:8080]
            CLI[CLI Tool<br/>conductor]
        end
        
        subgraph "Claude Conductor Core"
            Orchestrator[Orchestrator<br/>タスク管理・分配]
            Dashboard[Web Dashboard<br/>FastAPI/HTTP Server]
            API[API Server<br/>REST API]
        end
        
        subgraph "Agent Pool (1-4 agents)"
            Agent1[Agent 1<br/>Claude Code Mock]
            Agent2[Agent 2<br/>Claude Code Mock]
            AgentN[Agent N<br/>Optional]
        end
        
        subgraph "Local Storage"
            Config[(Config<br/>YAML)]
            Workspace[(Workspace<br/>Files)]
            Logs[(Logs<br/>Text Files)]
        end
        
        subgraph "Communication"
            Queue[In-Memory Queue<br/>タスクキュー]
            Socket[Unix Socket<br/>エージェント通信]
        end
    end
    
    Browser -->|HTTP/WebSocket| Dashboard
    CLI -->|Python API| Orchestrator
    Dashboard -->|Internal API| Orchestrator
    API -->|REST| Orchestrator
    
    Orchestrator -->|Task Assignment| Queue
    Queue -->|Task Distribution| Agent1
    Queue -->|Task Distribution| Agent2
    Queue -.->|Optional| AgentN
    
    Agent1 <-->|Unix Socket| Socket
    Agent2 <-->|Unix Socket| Socket
    AgentN <-.->|Unix Socket| Socket
    
    Orchestrator -->|Read/Write| Config
    Agent1 -->|Read/Write| Workspace
    Agent2 -->|Read/Write| Workspace
    Orchestrator -->|Write| Logs
    
    style Browser fill:#e1f5fe
    style CLI fill:#e1f5fe
    style Orchestrator fill:#fff3e0
    style Dashboard fill:#fff3e0
    style API fill:#fff3e0
    style Agent1 fill:#e8f5e9
    style Agent2 fill:#e8f5e9
    style AgentN fill:#f3e5f5
    style Queue fill:#fce4ec
    style Socket fill:#fce4ec
    style Config fill:#f5f5f5
    style Workspace fill:#f5f5f5
    style Logs fill:#f5f5f5
```

### Standalone版の特徴:
- **シンプルな構成**: 単一マシンで完結
- **軽量リソース**: メモリ2GB、CPU 0.5-2コア
- **ローカルストレージ**: ファイルベースの永続化
- **インメモリキュー**: Redisなしでの動作
- **Mockモード**: Claude Code CLIのモック実装

---

## Docker Compose Standalone Architecture

```mermaid
graph TB
    subgraph "Docker Host"
        subgraph "Docker Network: conductor-standalone"
            subgraph "Main Container"
                ConductorContainer[claude-conductor-standalone<br/>Orchestrator + Dashboard]
                Supervisor[Supervisor<br/>プロセス管理]
            end
            
            subgraph "Optional Containers"
                Redis[(Redis<br/>Optional)]
                FileServer[Nginx<br/>File Server<br/>:8090]
            end
        end
        
        subgraph "Docker Volumes"
            VolumeWorkspace[(conductor_workspace<br/>~/.claude-conductor/workspace)]
            VolumeLogs[(conductor_logs<br/>~/.claude-conductor/logs)]
            VolumeConfig[(conductor_config<br/>~/.claude-conductor/config)]
        end
        
        subgraph "Host Ports"
            Port8080[8080: Dashboard]
            Port8081[8081: API]
            Port8090[8090: Files]
        end
    end
    
    subgraph "External Access"
        UserBrowser[User Browser]
        UserCLI[User CLI]
    end
    
    UserBrowser -->|HTTP| Port8080
    UserCLI -->|HTTP API| Port8081
    UserBrowser -.->|HTTP| Port8090
    
    Port8080 --> ConductorContainer
    Port8081 --> ConductorContainer
    Port8090 -.-> FileServer
    
    ConductorContainer --> Supervisor
    ConductorContainer -.->|Optional| Redis
    
    ConductorContainer --> VolumeWorkspace
    ConductorContainer --> VolumeLogs
    ConductorContainer --> VolumeConfig
    FileServer -.-> VolumeWorkspace
    FileServer -.-> VolumeLogs
    
    style UserBrowser fill:#e1f5fe
    style UserCLI fill:#e1f5fe
    style ConductorContainer fill:#fff3e0
    style Supervisor fill:#fff3e0
    style Redis fill:#ffebee
    style FileServer fill:#ffebee
    style VolumeWorkspace fill:#f5f5f5
    style VolumeLogs fill:#f5f5f5
    style VolumeConfig fill:#f5f5f5
```

---

## Full Production Architecture (フルセット版)

```mermaid
graph TB
    subgraph "External Services"
        Users[Users/Developers]
        GitHub[GitHub<br/>Code Repository]
        DockerHub[Docker Hub<br/>Container Registry]
        CloudProvider[Cloud Provider<br/>AWS/GCP/Azure]
    end
    
    subgraph "Kubernetes Cluster"
        subgraph "Ingress Layer"
            Ingress[NGINX Ingress<br/>Load Balancer]
            TLS[TLS Termination<br/>HTTPS]
        end
        
        subgraph "Application Layer"
            subgraph "Orchestrator Pod"
                OrchestratorPod[Orchestrator<br/>StatefulSet]
                DashboardPod[Dashboard<br/>Deployment]
                APIPod[API Server<br/>Deployment]
            end
            
            subgraph "Agent Pool"
                AgentRS[Agent ReplicaSet<br/>3-10 replicas]
                HPA[Horizontal Pod<br/>Autoscaler]
            end
        end
        
        subgraph "Data Layer"
            Redis[(Redis Cluster<br/>Task Queue)]
            PostgreSQL[(PostgreSQL<br/>Metadata)]
            S3[(S3/MinIO<br/>Object Storage)]
        end
        
        subgraph "Service Mesh"
            ServiceMesh[Istio/Linkerd<br/>Service Mesh]
            mTLS[mTLS<br/>Inter-service]
        end
        
        subgraph "Monitoring Stack"
            Prometheus[Prometheus<br/>Metrics]
            Grafana[Grafana<br/>Visualization]
            Loki[Loki<br/>Log Aggregation]
            Jaeger[Jaeger<br/>Tracing]
        end
        
        subgraph "Storage"
            PVC1[(PVC: Workspace<br/>ReadWriteMany)]
            PVC2[(PVC: Logs<br/>ReadWriteMany)]
            PVC3[(PVC: Config<br/>ReadWriteOnce)]
        end
    end
    
    subgraph "CI/CD Pipeline"
        GitHubActions[GitHub Actions<br/>CI/CD]
        ArgoCD[ArgoCD<br/>GitOps]
    end
    
    Users --> CloudProvider
    CloudProvider --> Ingress
    Ingress --> TLS
    TLS --> DashboardPod
    TLS --> APIPod
    
    GitHub --> GitHubActions
    GitHubActions --> DockerHub
    GitHubActions --> ArgoCD
    ArgoCD --> OrchestratorPod
    ArgoCD --> AgentRS
    
    OrchestratorPod <--> ServiceMesh
    DashboardPod <--> ServiceMesh
    APIPod <--> ServiceMesh
    AgentRS <--> ServiceMesh
    
    ServiceMesh --> mTLS
    
    OrchestratorPod --> Redis
    OrchestratorPod --> PostgreSQL
    AgentRS --> S3
    
    OrchestratorPod --> PVC1
    AgentRS --> PVC1
    OrchestratorPod --> PVC2
    OrchestratorPod --> PVC3
    
    HPA --> AgentRS
    HPA <-- Prometheus
    
    OrchestratorPod --> Prometheus
    AgentRS --> Prometheus
    Prometheus --> Grafana
    
    OrchestratorPod --> Loki
    AgentRS --> Loki
    Loki --> Grafana
    
    ServiceMesh --> Jaeger
    
    style Users fill:#e1f5fe
    style Ingress fill:#ffccbc
    style TLS fill:#ffccbc
    style OrchestratorPod fill:#fff3e0
    style DashboardPod fill:#fff3e0
    style APIPod fill:#fff3e0
    style AgentRS fill:#e8f5e9
    style HPA fill:#e8f5e9
    style Redis fill:#ffebee
    style PostgreSQL fill:#ffebee
    style S3 fill:#ffebee
    style Prometheus fill:#f3e5f5
    style Grafana fill:#f3e5f5
    style ServiceMesh fill:#fce4ec
```

### フルセット版の特徴:
- **高可用性**: マルチレプリカ、自動フェイルオーバー
- **自動スケーリング**: HPA、VPA、Cluster Autoscaler
- **エンタープライズセキュリティ**: mTLS、RBAC、Network Policies
- **完全な監視**: メトリクス、ログ、トレーシング
- **GitOps**: 宣言的デプロイメント、自動同期

---

## Component Communication Flow

```mermaid
sequenceDiagram
    participant User
    participant Dashboard
    participant Orchestrator
    participant Queue
    participant Agent
    participant Storage
    
    User->>Dashboard: Submit Task
    Dashboard->>Orchestrator: Create Task Request
    Orchestrator->>Queue: Enqueue Task
    Orchestrator->>Storage: Save Task Metadata
    
    Agent->>Queue: Poll for Tasks
    Queue-->>Agent: Return Task
    Agent->>Agent: Execute Task
    Agent->>Storage: Write Results
    Agent->>Orchestrator: Report Completion
    
    Orchestrator->>Storage: Update Task Status
    Orchestrator->>Dashboard: Send Update (WebSocket)
    Dashboard-->>User: Display Results
    
    Note over Agent: Health Check Loop
    loop Every 30s
        Agent->>Orchestrator: Health Check Ping
        Orchestrator-->>Agent: Acknowledge
    end
```

---

## Deployment Evolution Path

```mermaid
graph LR
    A[Standalone<br/>Single PC] -->|Scale Up| B[Docker Compose<br/>Single Server]
    B -->|Scale Out| C[Docker Swarm<br/>Small Cluster]
    C -->|Enterprise| D[Kubernetes<br/>Production]
    
    A -->|Direct Path| D
    
    style A fill:#e8f5e9
    style B fill:#fff3e0
    style C fill:#ffebee
    style D fill:#f3e5f5
```

### 移行パス:
1. **Standalone → Docker Compose**: コンテナ化による安定性向上
2. **Docker Compose → Swarm**: 複数ノードへの展開
3. **Swarm → Kubernetes**: エンタープライズ機能の活用
4. **Direct to K8s**: 大規模展開の場合は直接移行
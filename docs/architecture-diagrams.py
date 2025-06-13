#!/usr/bin/env python3
"""
Generate architecture diagrams for Claude Conductor
Requires: pip install matplotlib networkx pygraphviz
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, FancyArrowPatch
import numpy as np

def create_standalone_architecture():
    """Create standalone architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    
    # Define colors
    colors = {
        'ui': '#E3F2FD',
        'core': '#FFF3E0',
        'agent': '#E8F5E9',
        'storage': '#F5F5F5',
        'comm': '#FCE4EC'
    }
    
    # Main container
    main_box = FancyBboxPatch((0.5, 0.5), 11, 9,
                              boxstyle="round,pad=0.1",
                              facecolor='white',
                              edgecolor='black',
                              linewidth=2)
    ax.add_patch(main_box)
    ax.text(6, 9.7, 'Local Machine - Standalone Claude Conductor', 
            ha='center', va='center', fontsize=16, fontweight='bold')
    
    # UI Layer
    ui_box = FancyBboxPatch((1, 7.5), 4.5, 1.5,
                            boxstyle="round,pad=0.05",
                            facecolor=colors['ui'],
                            edgecolor='darkblue')
    ax.add_patch(ui_box)
    ax.text(3.25, 8.6, 'User Interface', ha='center', fontweight='bold')
    ax.text(2.25, 8.1, 'Web Browser\nlocalhost:8080', ha='center', fontsize=9)
    ax.text(4.25, 8.1, 'CLI Tool\nconductor', ha='center', fontsize=9)
    
    # Core Layer
    core_box = FancyBboxPatch((1, 5), 9.5, 2,
                              boxstyle="round,pad=0.05",
                              facecolor=colors['core'],
                              edgecolor='darkorange')
    ax.add_patch(core_box)
    ax.text(5.75, 6.6, 'Claude Conductor Core', ha='center', fontweight='bold')
    
    # Core components
    components = [
        (2.5, 5.8, 'Orchestrator\nTask Management'),
        (5.75, 5.8, 'Web Dashboard\nFastAPI'),
        (9, 5.8, 'API Server\nREST API')
    ]
    for x, y, text in components:
        comp_box = Rectangle((x-0.7, y-0.3), 1.4, 0.6,
                            facecolor='white',
                            edgecolor='gray')
        ax.add_patch(comp_box)
        ax.text(x, y, text, ha='center', fontsize=8)
    
    # Agent Layer
    agent_box = FancyBboxPatch((1, 2.5), 9.5, 2,
                               boxstyle="round,pad=0.05",
                               facecolor=colors['agent'],
                               edgecolor='darkgreen')
    ax.add_patch(agent_box)
    ax.text(5.75, 4.1, 'Agent Pool (1-4 agents)', ha='center', fontweight='bold')
    
    # Agents
    agents = [
        (2.5, 3.3, 'Agent 1\nClaude Mock'),
        (5.75, 3.3, 'Agent 2\nClaude Mock'),
        (9, 3.3, 'Agent N\n(Optional)')
    ]
    for i, (x, y, text) in enumerate(agents):
        style = 'dashed' if i == 2 else 'solid'
        agent_circle = Circle((x, y), 0.6,
                             facecolor='white' if i < 2 else '#F3E5F5',
                             edgecolor='gray',
                             linestyle=style)
        ax.add_patch(agent_circle)
        ax.text(x, y, text, ha='center', fontsize=8)
    
    # Storage Layer
    storage_box = FancyBboxPatch((1, 0.5), 4.5, 1.5,
                                 boxstyle="round,pad=0.05",
                                 facecolor=colors['storage'],
                                 edgecolor='gray')
    ax.add_patch(storage_box)
    ax.text(3.25, 1.6, 'Local Storage', ha='center', fontweight='bold')
    
    # Storage components
    storages = [
        (2, 0.9, 'Config\n(YAML)'),
        (3.25, 0.9, 'Workspace\n(Files)'),
        (4.5, 0.9, 'Logs\n(Text)')
    ]
    for x, y, text in storages:
        storage_rect = Rectangle((x-0.35, y-0.2), 0.7, 0.4,
                                facecolor='white',
                                edgecolor='darkgray')
        ax.add_patch(storage_rect)
        ax.text(x, y, text, ha='center', fontsize=7)
    
    # Communication Layer
    comm_box = FancyBboxPatch((6.5, 0.5), 4, 1.5,
                              boxstyle="round,pad=0.05",
                              facecolor=colors['comm'],
                              edgecolor='darkred')
    ax.add_patch(comm_box)
    ax.text(8.5, 1.6, 'Communication', ha='center', fontweight='bold')
    
    # Communication components
    comm_components = [
        (7.5, 0.9, 'In-Memory Queue\nTask Queue'),
        (9.5, 0.9, 'Unix Socket\nAgent Communication')
    ]
    for x, y, text in comm_components:
        comm_rect = Rectangle((x-0.5, y-0.2), 1, 0.4,
                             facecolor='white',
                             edgecolor='darkgray')
        ax.add_patch(comm_rect)
        ax.text(x, y, text, ha='center', fontsize=7)
    
    # Add arrows for data flow
    # UI to Core
    arrow1 = FancyArrowPatch((3.25, 7.5), (3.25, 7),
                            connectionstyle="arc3,rad=0",
                            arrowstyle='-|>',
                            mutation_scale=20,
                            linewidth=2,
                            color='blue')
    ax.add_patch(arrow1)
    
    # Core to Agents
    arrow2 = FancyArrowPatch((5.75, 5), (5.75, 4.5),
                            connectionstyle="arc3,rad=0",
                            arrowstyle='<->',
                            mutation_scale=20,
                            linewidth=2,
                            color='orange')
    ax.add_patch(arrow2)
    
    # Core to Storage
    arrow3 = FancyArrowPatch((3.25, 5), (3.25, 2),
                            connectionstyle="arc3,rad=.3",
                            arrowstyle='<->',
                            mutation_scale=20,
                            linewidth=1.5,
                            color='gray')
    ax.add_patch(arrow3)
    
    # Agents to Communication
    arrow4 = FancyArrowPatch((8.5, 2.5), (8.5, 2),
                            connectionstyle="arc3,rad=0",
                            arrowstyle='<->',
                            mutation_scale=20,
                            linewidth=1.5,
                            color='red')
    ax.add_patch(arrow4)
    
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    plt.title('Claude Conductor - Standalone Architecture', fontsize=18, pad=20)
    plt.tight_layout()
    
    return fig

def create_kubernetes_architecture():
    """Create Kubernetes full architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    
    # Define colors
    colors = {
        'external': '#E1F5FE',
        'ingress': '#FFCCBC',
        'app': '#FFF3E0',
        'data': '#FFEBEE',
        'monitoring': '#F3E5F5',
        'mesh': '#FCE4EC',
        'storage': '#F5F5F5'
    }
    
    # Main Kubernetes cluster box
    cluster_box = FancyBboxPatch((0.5, 0.5), 15, 11,
                                boxstyle="round,pad=0.1",
                                facecolor='white',
                                edgecolor='black',
                                linewidth=3)
    ax.add_patch(cluster_box)
    ax.text(8, 11.2, 'Kubernetes Cluster - Production Claude Conductor', 
            ha='center', va='center', fontsize=18, fontweight='bold')
    
    # External layer
    external_y = 10
    external_services = [
        (2, external_y, 'Users/\nDevelopers'),
        (5, external_y, 'GitHub\nRepository'),
        (8, external_y, 'Docker Hub\nRegistry'),
        (11, external_y, 'Cloud Provider\nAWS/GCP/Azure'),
        (14, external_y, 'CI/CD\nGitHub Actions')
    ]
    
    for x, y, text in external_services:
        ext_box = FancyBboxPatch((x-0.8, y-0.4), 1.6, 0.8,
                                boxstyle="round,pad=0.05",
                                facecolor=colors['external'],
                                edgecolor='darkblue')
        ax.add_patch(ext_box)
        ax.text(x, y, text, ha='center', fontsize=9)
    
    # Ingress layer
    ingress_box = FancyBboxPatch((1, 8), 14, 1.2,
                                boxstyle="round,pad=0.05",
                                facecolor=colors['ingress'],
                                edgecolor='darkorange')
    ax.add_patch(ingress_box)
    ax.text(8, 8.6, 'Ingress Layer', ha='center', fontweight='bold')
    
    ingress_components = [
        (4, 8.3, 'NGINX Ingress\nLoad Balancer'),
        (8, 8.3, 'TLS Termination\nHTTPS'),
        (12, 8.3, 'Rate Limiting\nWAF')
    ]
    for x, y, text in ingress_components:
        ing_rect = Rectangle((x-0.8, y-0.2), 1.6, 0.4,
                            facecolor='white',
                            edgecolor='gray')
        ax.add_patch(ing_rect)
        ax.text(x, y, text, ha='center', fontsize=8)
    
    # Application layer
    app_box = FancyBboxPatch((1, 5), 7, 2.5,
                            boxstyle="round,pad=0.05",
                            facecolor=colors['app'],
                            edgecolor='darkorange')
    ax.add_patch(app_box)
    ax.text(4.5, 7.2, 'Application Layer', ha='center', fontweight='bold')
    
    # Application pods
    app_pods = [
        (2.5, 6.5, 'Orchestrator\nStatefulSet'),
        (4.5, 6.5, 'Dashboard\nDeployment'),
        (6.5, 6.5, 'API Server\nDeployment')
    ]
    for x, y, text in app_pods:
        pod_box = Rectangle((x-0.6, y-0.3), 1.2, 0.6,
                           facecolor='white',
                           edgecolor='gray')
        ax.add_patch(pod_box)
        ax.text(x, y, text, ha='center', fontsize=8)
    
    # Agent ReplicaSet
    agent_box = Rectangle((2, 5.3), 5, 0.8,
                         facecolor='#E8F5E9',
                         edgecolor='darkgreen')
    ax.add_patch(agent_box)
    ax.text(4.5, 5.7, 'Agent ReplicaSet (3-10 replicas with HPA)', ha='center', fontsize=9)
    
    # Data layer
    data_box = FancyBboxPatch((9, 5), 6, 2.5,
                             boxstyle="round,pad=0.05",
                             facecolor=colors['data'],
                             edgecolor='darkred')
    ax.add_patch(data_box)
    ax.text(12, 7.2, 'Data Layer', ha='center', fontweight='bold')
    
    # Data services
    data_services = [
        (10, 6.5, 'Redis Cluster\nTask Queue'),
        (12, 6.5, 'PostgreSQL\nMetadata'),
        (14, 6.5, 'S3/MinIO\nObject Store')
    ]
    for x, y, text in data_services:
        data_rect = Rectangle((x-0.6, y-0.3), 1.2, 0.6,
                             facecolor='white',
                             edgecolor='gray')
        ax.add_patch(data_rect)
        ax.text(x, y, text, ha='center', fontsize=8)
    
    # Service Mesh
    mesh_box = FancyBboxPatch((1, 3.5), 7, 1,
                             boxstyle="round,pad=0.05",
                             facecolor=colors['mesh'],
                             edgecolor='purple')
    ax.add_patch(mesh_box)
    ax.text(4.5, 4, 'Service Mesh (Istio/Linkerd) - mTLS, Tracing, Circuit Breaking', 
            ha='center', fontsize=9)
    
    # Monitoring Stack
    monitor_box = FancyBboxPatch((9, 2), 6, 2.5,
                                boxstyle="round,pad=0.05",
                                facecolor=colors['monitoring'],
                                edgecolor='purple')
    ax.add_patch(monitor_box)
    ax.text(12, 4.2, 'Monitoring Stack', ha='center', fontweight='bold')
    
    # Monitoring components
    monitor_components = [
        (10, 3.5, 'Prometheus\nMetrics'),
        (12, 3.5, 'Grafana\nDashboards'),
        (14, 3.5, 'Loki\nLogs'),
        (10, 2.5, 'Jaeger\nTracing'),
        (12, 2.5, 'AlertManager\nAlerts'),
        (14, 2.5, 'PagerDuty\nIncidents')
    ]
    for x, y, text in monitor_components:
        mon_rect = Rectangle((x-0.5, y-0.2), 1, 0.4,
                            facecolor='white',
                            edgecolor='gray')
        ax.add_patch(mon_rect)
        ax.text(x, y, text, ha='center', fontsize=7)
    
    # Storage layer
    storage_box = FancyBboxPatch((1, 0.8), 7, 1,
                                boxstyle="round,pad=0.05",
                                facecolor=colors['storage'],
                                edgecolor='gray')
    ax.add_patch(storage_box)
    ax.text(4.5, 1.3, 'Persistent Storage', ha='center', fontweight='bold')
    
    storage_pvcs = [
        (2.5, 1, 'PVC: Workspace\nReadWriteMany'),
        (4.5, 1, 'PVC: Logs\nReadWriteMany'),
        (6.5, 1, 'PVC: Config\nReadWriteOnce')
    ]
    for x, y, text in storage_pvcs:
        pvc_rect = Rectangle((x-0.6, y-0.15), 1.2, 0.3,
                            facecolor='white',
                            edgecolor='darkgray')
        ax.add_patch(pvc_rect)
        ax.text(x, y, text, ha='center', fontsize=7)
    
    # Add connection arrows
    # External to Ingress
    arrow1 = FancyArrowPatch((8, 9.5), (8, 9.2),
                            connectionstyle="arc3,rad=0",
                            arrowstyle='-|>',
                            mutation_scale=25,
                            linewidth=3,
                            color='blue')
    ax.add_patch(arrow1)
    
    # Ingress to App
    arrow2 = FancyArrowPatch((6, 8), (5, 7.5),
                            connectionstyle="arc3,rad=.2",
                            arrowstyle='-|>',
                            mutation_scale=20,
                            linewidth=2,
                            color='orange')
    ax.add_patch(arrow2)
    
    # App to Data
    arrow3 = FancyArrowPatch((8, 6.5), (9, 6.5),
                            connectionstyle="arc3,rad=0",
                            arrowstyle='<->',
                            mutation_scale=20,
                            linewidth=2,
                            color='red')
    ax.add_patch(arrow3)
    
    # App to Mesh
    arrow4 = FancyArrowPatch((4.5, 5), (4.5, 4.5),
                            connectionstyle="arc3,rad=0",
                            arrowstyle='<->',
                            mutation_scale=20,
                            linewidth=2,
                            color='purple')
    ax.add_patch(arrow4)
    
    # Mesh to Monitoring
    arrow5 = FancyArrowPatch((8, 4), (9, 3.5),
                            connectionstyle="arc3,rad=.3",
                            arrowstyle='-|>',
                            mutation_scale=20,
                            linewidth=1.5,
                            color='purple')
    ax.add_patch(arrow5)
    
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis('off')
    
    plt.title('Claude Conductor - Kubernetes Production Architecture', fontsize=20, pad=20)
    plt.tight_layout()
    
    return fig

def create_deployment_evolution():
    """Create deployment evolution diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    
    # Define stages
    stages = [
        (2, 4, 'Standalone\nSingle PC', '#E8F5E9', 
         '• 5 min setup\n• 1-4 agents\n• Local files\n• 2GB RAM'),
        (5.5, 4, 'Docker Compose\nSingle Server', '#FFF3E0',
         '• 10 min setup\n• 1-10 agents\n• Volumes\n• 4GB RAM'),
        (9, 4, 'Docker Swarm\nSmall Cluster', '#FFEBEE',
         '• 30 min setup\n• 10-50 agents\n• Multi-node\n• 8GB+ RAM'),
        (12.5, 4, 'Kubernetes\nProduction', '#F3E5F5',
         '• 1hr+ setup\n• Unlimited\n• Auto-scale\n• 16GB+ RAM')
    ]
    
    # Draw stages
    for i, (x, y, title, color, details) in enumerate(stages):
        # Stage box
        stage_box = FancyBboxPatch((x-1.2, y-1.5), 2.4, 3,
                                  boxstyle="round,pad=0.1",
                                  facecolor=color,
                                  edgecolor='black',
                                  linewidth=2)
        ax.add_patch(stage_box)
        
        # Title
        ax.text(x, y+1.2, title, ha='center', fontweight='bold', fontsize=11)
        
        # Details
        ax.text(x, y-0.3, details, ha='center', fontsize=8, 
                verticalalignment='center')
        
        # Complexity indicator
        complexity = '⭐' * (i + 1)
        ax.text(x, y-1.2, complexity, ha='center', fontsize=10)
    
    # Evolution arrows
    arrow_y = 4
    for i in range(3):
        x1 = stages[i][0] + 1.2
        x2 = stages[i+1][0] - 1.2
        arrow = FancyArrowPatch((x1, arrow_y), (x2, arrow_y),
                               connectionstyle="arc3,rad=0",
                               arrowstyle='-|>',
                               mutation_scale=25,
                               linewidth=3,
                               color='darkgreen')
        ax.add_patch(arrow)
        
        # Label
        mid_x = (x1 + x2) / 2
        ax.text(mid_x, arrow_y + 0.3, 'Scale Up', ha='center', fontsize=8)
    
    # Direct path arrow
    direct_arrow = FancyArrowPatch((2, 2), (12.5, 2),
                                  connectionstyle="arc3,rad=-.3",
                                  arrowstyle='-|>',
                                  mutation_scale=25,
                                  linewidth=2,
                                  linestyle='dashed',
                                  color='blue')
    ax.add_patch(direct_arrow)
    ax.text(7.25, 1.5, 'Direct Path (for large deployments)', 
            ha='center', fontsize=9, color='blue')
    
    # Title and labels
    ax.text(7.25, 6.5, 'Claude Conductor Deployment Evolution', 
            ha='center', fontsize=16, fontweight='bold')
    ax.text(7.25, 6, 'Choose based on scale, complexity, and requirements', 
            ha='center', fontsize=10, style='italic')
    
    ax.set_xlim(0, 14.5)
    ax.set_ylim(0, 7)
    ax.axis('off')
    
    plt.tight_layout()
    return fig

def save_all_diagrams():
    """Generate and save all architecture diagrams"""
    # Create diagrams
    standalone_fig = create_standalone_architecture()
    k8s_fig = create_kubernetes_architecture()
    evolution_fig = create_deployment_evolution()
    
    # Save as PNG
    standalone_fig.savefig('architecture-standalone.png', dpi=300, bbox_inches='tight')
    k8s_fig.savefig('architecture-kubernetes.png', dpi=300, bbox_inches='tight')
    evolution_fig.savefig('architecture-evolution.png', dpi=300, bbox_inches='tight')
    
    # Save as SVG for scalability
    standalone_fig.savefig('architecture-standalone.svg', format='svg', bbox_inches='tight')
    k8s_fig.savefig('architecture-kubernetes.svg', format='svg', bbox_inches='tight')
    evolution_fig.savefig('architecture-evolution.svg', format='svg', bbox_inches='tight')
    
    print("Architecture diagrams saved successfully!")
    print("Files created:")
    print("  - architecture-standalone.png/svg")
    print("  - architecture-kubernetes.png/svg")
    print("  - architecture-evolution.png/svg")

if __name__ == "__main__":
    save_all_diagrams()
    
    # Optionally display the diagrams
    # plt.show()
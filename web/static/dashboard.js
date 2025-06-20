// Claude Conductor Dashboard JavaScript

class DashboardManager {
    constructor() {
        this.ws = null;
        this.reconnectInterval = null;
        this.authToken = localStorage.getItem('auth_token');
        this.currentUser = null;
        this.notifications = [];
        
        this.initializeEventListeners();
        this.connectWebSocket();
    }
    
    initializeEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabName = e.target.textContent.toLowerCase().split(' ')[0];
                this.showTab(tabName);
            });
        });
        
        // Form submissions
        document.getElementById('login-form')?.addEventListener('submit', this.authenticate.bind(this));
        document.getElementById('task-form')?.addEventListener('submit', this.submitTask.bind(this));
        
        // Auto-refresh for stats
        setInterval(() => this.updateStats(), 30000); // Every 30 seconds
    }
    
    showNotification(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => document.body.removeChild(toast), 300);
        }, duration);
    }
    
    updateProgressBar(elementId, percentage) {
        const progressBar = document.getElementById(elementId);
        if (progressBar) {
            const fill = progressBar.querySelector('.progress-fill');
            fill.style.width = `${percentage}%`;
        }
    }
    
    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 4
        }).format(amount);
    }
    
    formatNumber(num) {
        return new Intl.NumberFormat('en-US').format(num);
    }
    
    async loadEvaluationReports() {
        try {
            const headers = {};
            if (this.authToken) {
                headers['Authorization'] = `Bearer ${this.authToken}`;
            }
            
            const response = await fetch('/api/evaluation/reports', { headers });
            if (response.ok) {
                const data = await response.json();
                this.displayEvaluationReports(data.reports);
            }
        } catch (error) {
            console.error('Error loading evaluation reports:', error);
        }
    }
    
    displayEvaluationReports(reports) {
        const container = document.getElementById('evaluation-reports');
        if (!container) return;
        
        if (reports.length === 0) {
            container.innerHTML = '<p>No evaluation reports available</p>';
            return;
        }
        
        container.innerHTML = reports.slice(0, 5).map(report => `
            <div class="metric-card fade-in">
                <div class="metric-title">Task: ${report.task_id}</div>
                <div class="metric-value">Score: ${report.overall_score.toFixed(2)}/10</div>
                <small>Evaluated: ${new Date(report.timestamp * 1000).toLocaleString()}</small>
            </div>
        `).join('');
    }
    
    async loadTokenUsage() {
        try {
            const headers = {};
            if (this.authToken) {
                headers['Authorization'] = `Bearer ${this.authToken}`;
            }
            
            const response = await fetch('/api/tokens/usage', { headers });
            if (response.ok) {
                const data = await response.json();
                this.displayTokenUsage(data);
            }
        } catch (error) {
            console.error('Error loading token usage:', error);
        }
    }
    
    displayTokenUsage(data) {
        const container = document.getElementById('cost-breakdown');
        if (!container) return;
        
        if (data.cost_breakdown) {
            const breakdown = Object.entries(data.cost_breakdown).map(([model, cost]) => `
                <div class="metric-card">
                    <div class="metric-title">${model}</div>
                    <div class="metric-value">${this.formatCurrency(cost)}</div>
                </div>
            `).join('');
            
            container.innerHTML = `
                <h4>Cost Breakdown by Model</h4>
                <div class="stats-grid">${breakdown}</div>
            `;
        }
        
        if (data.optimization_suggestions && data.optimization_suggestions.length > 0) {
            container.innerHTML += `
                <h4>Optimization Suggestions</h4>
                <ul>
                    ${data.optimization_suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                </ul>
            `;
        }
    }
    
    startPerformanceMonitoring() {
        // Monitor page performance
        if ('performance' in window) {
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.entryType === 'navigation') {
                        console.log(`Page load time: ${entry.loadEventEnd - entry.loadEventStart}ms`);
                    }
                }
            });
            observer.observe({ entryTypes: ['navigation'] });
        }
    }
    
    exportDashboardData() {
        const data = {
            timestamp: new Date().toISOString(),
            stats: this.lastStats,
            agents: this.lastAgentStatus,
            user: this.currentUser,
            logs: document.getElementById('activity-log').textContent
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `claude-conductor-dashboard-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        this.showNotification('Dashboard data exported successfully', 'success');
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboardManager = new DashboardManager();
    window.dashboardManager.startPerformanceMonitoring();
});

// Utility functions for backward compatibility
function showTab(tabName) {
    window.dashboardManager?.showTab(tabName);
}

function submitTask() {
    window.dashboardManager?.submitTask();
}

function authenticate() {
    window.dashboardManager?.authenticate();
}

function logout() {
    window.dashboardManager?.logout();
}

function clearLog() {
    document.getElementById('activity-log').textContent = '';
    window.dashboardManager?.showNotification('Activity log cleared', 'info');
}

function exportLog() {
    window.dashboardManager?.exportDashboardData();
}
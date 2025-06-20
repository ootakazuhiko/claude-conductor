#!/usr/bin/env python3
"""
セキュリティ強化されたオーケストレーター
認証・認可機能付きのオーケストレーター拡張
"""

import os
import time
import json
import uuid
import threading
import yaml
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime
from functools import wraps

from .orchestrator import Orchestrator, Task, TaskResult, create_task
from .security import (
    SecurityManager, SecurityConfig, User, APIKey, Permission, UserRole,
    require_permission, require_role, DEFAULT_SECURITY_CONFIG
)
from .exceptions import (
    ConfigurationError, AgentStartupError, CommunicationError,
    TaskExecutionError, TaskValidationError, TaskTimeoutError, ResourceError
)

logger = logging.getLogger(__name__)

@dataclass
class SecureTaskRequest:
    """セキュリティ付きタスクリクエスト"""
    task: Task
    requester_user_id: str
    requester_permissions: List[Permission]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_time: float = field(default_factory=time.time)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

@dataclass
class SecureTaskResult:
    """セキュリティ付きタスクリザルト"""
    task_result: TaskResult
    request_id: str
    authorized: bool
    authorization_time: float
    requester_user_id: str
    permissions_used: List[Permission]

class SecureOrchestrator(Orchestrator):
    """セキュリティ強化されたオーケストレーター"""
    
    def __init__(self, config_path: Optional[str] = None, security_config: Optional[SecurityConfig] = None):
        super().__init__(config_path)
        
        # セキュリティマネージャーを初期化
        self.security_config = security_config or DEFAULT_SECURITY_CONFIG
        self.security_manager = SecurityManager(self.security_config)
        
        # セキュリティ設定をメイン設定に統合
        self.config.update({
            "security_enabled": True,
            "require_authentication": True,
            "audit_logging": True
        })
        
        # セキュリティ統計
        self.security_stats = {
            "authenticated_requests": 0,
            "authorization_failures": 0,
            "api_key_requests": 0,
            "jwt_token_requests": 0,
            "security_incidents": 0
        }
        
        logger.info("Secure orchestrator initialized with authentication enabled")
    
    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """ユーザー認証とトークン生成"""
        user = self.security_manager.authenticate_user(username, password)
        if not user:
            return None
        
        self.security_stats["authenticated_requests"] += 1
        self.security_stats["jwt_token_requests"] += 1
        
        return self.security_manager.generate_token(user)
    
    def authenticate_api_key(self, api_key: str) -> Optional[tuple[User, APIKey]]:
        """APIキー認証"""
        result = self.security_manager.authenticate_api_key(api_key)
        if result:
            self.security_stats["authenticated_requests"] += 1
            self.security_stats["api_key_requests"] += 1
        
        return result
    
    def verify_token(self, token: str) -> Optional[User]:
        """JWTトークンを検証してユーザー情報を取得"""
        payload = self.security_manager.token_manager.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get('user_id')
        if not user_id:
            return None
        
        user = self.security_manager.users.get(user_id)
        if not user or not user.is_active:
            return None
        
        self.security_stats["jwt_token_requests"] += 1
        return user
    
    def execute_secure_task(
        self,
        task: Task,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SecureTaskResult:
        """セキュリティ付きタスク実行"""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 認証
        user = None
        auth_method = None
        
        if auth_token:
            user = self.verify_token(auth_token)
            auth_method = "jwt"
        elif api_key:
            auth_result = self.authenticate_api_key(api_key)
            if auth_result:
                user, key_info = auth_result
                auth_method = "api_key"
        
        if not user:
            self.security_stats["authorization_failures"] += 1
            self.security_manager.audit_logger.log_event(
                event_type="authentication",
                user_id=None,
                resource="task_execution",
                action="execute",
                result="failure",
                ip_address=ip_address,
                user_agent=user_agent,
                details={"reason": "authentication_failed", "request_id": request_id}
            )
            
            # 認証失敗の結果を返す
            return SecureTaskResult(
                task_result=TaskResult(
                    task_id=task.task_id,
                    agent_id="security",
                    status="failed",
                    result={},
                    error="Authentication required"
                ),
                request_id=request_id,
                authorized=False,
                authorization_time=time.time() - start_time,
                requester_user_id="anonymous",
                permissions_used=[]
            )
        
        # 認可チェック
        required_permission = self._determine_required_permission(task)
        if not self.security_manager.authorize_action(
            user, required_permission, "task", "execute"
        ):
            self.security_stats["authorization_failures"] += 1
            
            return SecureTaskResult(
                task_result=TaskResult(
                    task_id=task.task_id,
                    agent_id="security",
                    status="failed",
                    result={},
                    error=f"Permission denied: {required_permission.value}"
                ),
                request_id=request_id,
                authorized=False,
                authorization_time=time.time() - start_time,
                requester_user_id=user.user_id,
                permissions_used=[]
            )
        
        # セキュリティ付きタスクリクエストを作成
        secure_request = SecureTaskRequest(
            task=task,
            requester_user_id=user.user_id,
            requester_permissions=[required_permission],
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # 監査ログ
        self.security_manager.audit_logger.log_event(
            event_type="task_execution",
            user_id=user.user_id,
            resource="task",
            action="execute",
            result="authorized",
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "task_type": task.task_type,
                "task_id": task.task_id,
                "request_id": request_id,
                "auth_method": auth_method,
                "required_permission": required_permission.value
            }
        )
        
        # タスク実行
        try:
            task_result = super().execute_task(task)
            
            return SecureTaskResult(
                task_result=task_result,
                request_id=request_id,
                authorized=True,
                authorization_time=time.time() - start_time,
                requester_user_id=user.user_id,
                permissions_used=[required_permission]
            )
            
        except Exception as e:
            logger.error(f"Secure task execution failed: {e}")
            
            # エラーの監査ログ
            self.security_manager.audit_logger.log_event(
                event_type="task_execution",
                user_id=user.user_id,
                resource="task",
                action="execute",
                result="failure",
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "task_id": task.task_id,
                    "request_id": request_id,
                    "error": str(e)
                }
            )
            
            return SecureTaskResult(
                task_result=TaskResult(
                    task_id=task.task_id,
                    agent_id="orchestrator",
                    status="failed",
                    result={},
                    error=str(e)
                ),
                request_id=request_id,
                authorized=True,
                authorization_time=time.time() - start_time,
                requester_user_id=user.user_id,
                permissions_used=[required_permission]
            )
    
    def _determine_required_permission(self, task: Task) -> Permission:
        """タスクに必要な権限を決定"""
        if task.task_type == "code_review":
            return Permission.TASK_READ
        elif task.task_type in ["refactor", "test_generation"]:
            return Permission.TASK_CREATE
        elif task.task_type == "analysis":
            return Permission.TASK_READ
        elif task.task_type == "generic":
            return Permission.TASK_EXECUTE
        else:
            return Permission.TASK_EXECUTE
    
    def create_user(
        self,
        username: str,
        email: Optional[str] = None,
        roles: List[UserRole] = None,
        admin_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """ユーザー作成（管理者権限必要）"""
        # 管理者認証チェック
        if admin_token:
            admin_user = self.verify_token(admin_token)
            if not admin_user or not admin_user.has_role(UserRole.ADMIN):
                return {"error": "Administrator privileges required"}
        
        try:
            user = self.security_manager.create_user(username, email, set(roles or []))
            return {
                "success": True,
                "user_id": user.user_id,
                "username": user.username,
                "roles": [role.value for role in user.roles]
            }
        except Exception as e:
            return {"error": str(e)}
    
    def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[Permission] = None,
        expires_in_days: Optional[int] = None,
        admin_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """APIキー作成"""
        # 管理者または本人のチェック
        if admin_token:
            admin_user = self.verify_token(admin_token)
            if not admin_user or (admin_user.user_id != user_id and not admin_user.has_role(UserRole.ADMIN)):
                return {"error": "Insufficient privileges"}
        
        try:
            key_value, api_key = self.security_manager.generate_api_key(
                user_id, name, set(permissions or []), expires_in_days
            )
            
            return {
                "success": True,
                "api_key": key_value,
                "key_id": api_key.key_id,
                "expires_at": api_key.expires_at
            }
        except Exception as e:
            return {"error": str(e)}
    
    def revoke_api_key(self, key_id: str, admin_token: str) -> Dict[str, Any]:
        """APIキー無効化"""
        admin_user = self.verify_token(admin_token)
        if not admin_user or not admin_user.has_role(UserRole.ADMIN):
            return {"error": "Administrator privileges required"}
        
        success = self.security_manager.api_key_manager.revoke_api_key(key_id)
        return {"success": success}
    
    def get_security_statistics(self, admin_token: str) -> Dict[str, Any]:
        """セキュリティ統計取得"""
        admin_user = self.verify_token(admin_token)
        if not admin_user or not admin_user.has_role(UserRole.ADMIN):
            return {"error": "Administrator privileges required"}
        
        security_stats = self.security_manager.get_security_stats()
        
        return {
            "security_manager_stats": security_stats,
            "orchestrator_security_stats": self.security_stats,
            "audit_log_sample": self.security_manager.audit_logger.get_audit_log(limit=10)
        }
    
    def get_audit_log(
        self,
        admin_token: str,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """監査ログ取得"""
        admin_user = self.verify_token(admin_token)
        if not admin_user or not admin_user.has_role(UserRole.ADMIN):
            return {"error": "Administrator privileges required"}
        
        audit_events = self.security_manager.audit_logger.get_audit_log(
            user_id=user_id,
            event_type=event_type,
            limit=limit
        )
        
        return {
            "audit_events": [asdict(event) for event in audit_events],
            "total_events": len(audit_events)
        }
    
    def change_user_role(
        self,
        target_user_id: str,
        new_roles: List[UserRole],
        admin_token: str
    ) -> Dict[str, Any]:
        """ユーザーロール変更"""
        admin_user = self.verify_token(admin_token)
        if not admin_user or not admin_user.has_role(UserRole.SUPER_ADMIN):
            return {"error": "Super administrator privileges required"}
        
        target_user = self.security_manager.users.get(target_user_id)
        if not target_user:
            return {"error": "User not found"}
        
        # 古いロールをクリア
        target_user.roles.clear()
        target_user.permissions.clear()
        
        # 新しいロールを追加
        for role in new_roles:
            target_user.add_role(role)
        
        self.security_manager.audit_logger.log_event(
            event_type="user_management",
            user_id=admin_user.user_id,
            resource="user_role",
            action="change",
            result="success",
            details={
                "target_user_id": target_user_id,
                "new_roles": [role.value for role in new_roles]
            }
        )
        
        return {
            "success": True,
            "user_id": target_user_id,
            "new_roles": [role.value for role in target_user.roles],
            "new_permissions": [perm.value for perm in target_user.permissions]
        }
    
    def enable_security_monitoring(self, admin_token: str) -> Dict[str, Any]:
        """セキュリティモニタリング有効化"""
        admin_user = self.verify_token(admin_token)
        if not admin_user or not admin_user.has_role(UserRole.ADMIN):
            return {"error": "Administrator privileges required"}
        
        # セキュリティモニタリングスレッドを開始
        threading.Thread(
            target=self._security_monitoring_loop,
            daemon=True
        ).start()
        
        return {"success": True, "monitoring": "enabled"}
    
    def _security_monitoring_loop(self):
        """セキュリティモニタリングループ"""
        while True:
            try:
                # セキュリティイベントの監視
                recent_failures = len([
                    event for event in self.security_manager.audit_logger.audit_log[-100:]
                    if event.result == "failure" and 
                    time.time() - event.timestamp < 300  # 直近5分
                ])
                
                if recent_failures > 10:
                    logger.warning(f"High number of security failures detected: {recent_failures}")
                    self.security_stats["security_incidents"] += 1
                
                # 不審なAPIキー使用パターンの検出
                self._detect_suspicious_api_usage()
                
                time.sleep(60)  # 1分間隔でチェック
                
            except Exception as e:
                logger.error(f"Security monitoring error: {e}")
                time.sleep(60)
    
    def _detect_suspicious_api_usage(self):
        """不審なAPIキー使用パターンを検出"""
        current_time = time.time()
        suspicious_threshold = 100  # 1分間に100リクエスト以上
        
        for api_key in self.security_manager.api_key_manager.api_keys.values():
            if api_key.last_used and current_time - api_key.last_used < 60:
                # 1分間の使用回数が異常に多い場合
                if api_key.usage_count > suspicious_threshold:
                    logger.warning(
                        f"Suspicious API key usage detected: {api_key.key_id} "
                        f"({api_key.usage_count} requests in last minute)"
                    )
                    
                    self.security_manager.audit_logger.log_event(
                        event_type="security_alert",
                        user_id=api_key.user_id,
                        resource="api_key",
                        action="suspicious_usage",
                        result="detected",
                        details={
                            "api_key_id": api_key.key_id,
                            "usage_count": api_key.usage_count,
                            "threshold": suspicious_threshold
                        }
                    )
                    
                    self.security_stats["security_incidents"] += 1

# セキュリティミドルウェア関数
def require_authentication(func):
    """認証が必要な関数用デコレーター"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # リクエストから認証情報を取得
        auth_token = kwargs.get('auth_token')
        api_key = kwargs.get('api_key')
        
        if not auth_token and not api_key:
            raise PermissionError("Authentication required")
        
        return func(*args, **kwargs)
    return wrapper

def require_admin_role(func):
    """管理者ロールが必要な関数用デコレーター"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        admin_token = kwargs.get('admin_token')
        if not admin_token:
            raise PermissionError("Administrator token required")
        
        return func(*args, **kwargs)
    return wrapper

# セキュリティ強化されたタスク作成関数
def create_secure_task(
    task_type: str = "generic",
    description: str = "",
    files: List[str] = None,
    security_level: str = "standard",
    **kwargs
) -> Task:
    """セキュリティレベル付きタスク作成"""
    task = create_task(task_type, description, files, **kwargs)
    
    # セキュリティレベルに応じてタスクを修正
    if security_level == "high":
        task.timeout = min(task.timeout, 120.0)  # 高セキュリティは短時間で実行
        task.priority = max(task.priority, 7)    # 高優先度で実行
    elif security_level == "restricted":
        task.timeout = min(task.timeout, 60.0)   # 制限モードは1分以内
        task.files = []  # ファイルアクセス禁止
    
    return task
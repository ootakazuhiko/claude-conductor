#!/usr/bin/env python3
"""
セキュリティ強化 - 認証・認可システム
Claude Conductor用の包括的なセキュリティフレームワーク
"""

import hashlib
import hmac
import jwt
import time
import secrets
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable, Union
from enum import Enum
import logging
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

class AuthenticationMethod(Enum):
    """認証方式"""
    JWT_TOKEN = "jwt_token"
    API_KEY = "api_key"
    HMAC_SIGNATURE = "hmac_signature"
    MUTUAL_TLS = "mutual_tls"
    BASIC_AUTH = "basic_auth"

class Permission(Enum):
    """権限定義"""
    # オーケストレーター権限
    ORCHESTRATOR_ADMIN = "orchestrator:admin"
    ORCHESTRATOR_READ = "orchestrator:read"
    ORCHESTRATOR_WRITE = "orchestrator:write"
    
    # エージェント権限
    AGENT_CREATE = "agent:create"
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_CONTROL = "agent:control"
    
    # タスク権限
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_EXECUTE = "task:execute"
    
    # システム権限
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
    
    # 評価権限
    EVALUATION_READ = "evaluation:read"
    EVALUATION_ADMIN = "evaluation:admin"

class UserRole(Enum):
    """ユーザーロール"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATOR = "operator"
    AGENT_MANAGER = "agent_manager"
    TASK_MANAGER = "task_manager"
    VIEWER = "viewer"
    API_CLIENT = "api_client"

@dataclass
class User:
    """ユーザー情報"""
    user_id: str
    username: str
    email: Optional[str] = None
    roles: Set[UserRole] = field(default_factory=set)
    permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, permission: Permission) -> bool:
        """権限チェック"""
        return permission in self.permissions
    
    def has_role(self, role: UserRole) -> bool:
        """ロールチェック"""
        return role in self.roles
    
    def add_role(self, role: UserRole):
        """ロール追加"""
        self.roles.add(role)
        # ロールに基づいて権限を自動付与
        self.permissions.update(get_role_permissions(role))
    
    def remove_role(self, role: UserRole):
        """ロール削除"""
        self.roles.discard(role)
        # 権限を再計算
        self.permissions = get_user_permissions(self.roles)

@dataclass
class APIKey:
    """APIキー情報"""
    key_id: str
    key_hash: str
    user_id: str
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    expires_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    last_used: Optional[float] = None
    usage_count: int = 0
    rate_limit: Optional[int] = None  # requests per hour
    
    def is_expired(self) -> bool:
        """有効期限チェック"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def is_valid(self) -> bool:
        """有効性チェック"""
        return self.is_active and not self.is_expired()

@dataclass
class SecurityConfig:
    """セキュリティ設定"""
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    api_key_length: int = 32
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
    session_timeout_hours: int = 8
    require_2fa: bool = False
    allowed_origins: List[str] = field(default_factory=list)
    rate_limit_requests_per_hour: int = 1000
    audit_log_enabled: bool = True

@dataclass
class SecurityAuditEvent:
    """セキュリティ監査イベント"""
    event_id: str
    event_type: str
    user_id: Optional[str]
    resource: str
    action: str
    result: str  # success, failure, denied
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

def get_role_permissions(role: UserRole) -> Set[Permission]:
    """ロール別権限定義"""
    role_permissions = {
        UserRole.SUPER_ADMIN: {
            Permission.ORCHESTRATOR_ADMIN,
            Permission.AGENT_CREATE, Permission.AGENT_READ, Permission.AGENT_UPDATE, 
            Permission.AGENT_DELETE, Permission.AGENT_CONTROL,
            Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_UPDATE, 
            Permission.TASK_DELETE, Permission.TASK_EXECUTE,
            Permission.SYSTEM_ADMIN, Permission.SYSTEM_MONITOR, Permission.SYSTEM_CONFIG,
            Permission.EVALUATION_READ, Permission.EVALUATION_ADMIN
        },
        UserRole.ADMIN: {
            Permission.ORCHESTRATOR_READ, Permission.ORCHESTRATOR_WRITE,
            Permission.AGENT_READ, Permission.AGENT_UPDATE, Permission.AGENT_CONTROL,
            Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_UPDATE, 
            Permission.TASK_EXECUTE,
            Permission.SYSTEM_MONITOR, Permission.SYSTEM_CONFIG,
            Permission.EVALUATION_READ, Permission.EVALUATION_ADMIN
        },
        UserRole.OPERATOR: {
            Permission.ORCHESTRATOR_READ,
            Permission.AGENT_READ, Permission.AGENT_CONTROL,
            Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_EXECUTE,
            Permission.SYSTEM_MONITOR,
            Permission.EVALUATION_READ
        },
        UserRole.AGENT_MANAGER: {
            Permission.AGENT_CREATE, Permission.AGENT_READ, Permission.AGENT_UPDATE, 
            Permission.AGENT_DELETE, Permission.AGENT_CONTROL,
            Permission.TASK_READ,
            Permission.SYSTEM_MONITOR
        },
        UserRole.TASK_MANAGER: {
            Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_UPDATE, 
            Permission.TASK_DELETE, Permission.TASK_EXECUTE,
            Permission.AGENT_READ,
            Permission.EVALUATION_READ
        },
        UserRole.VIEWER: {
            Permission.ORCHESTRATOR_READ,
            Permission.AGENT_READ,
            Permission.TASK_READ,
            Permission.SYSTEM_MONITOR,
            Permission.EVALUATION_READ
        },
        UserRole.API_CLIENT: {
            Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_EXECUTE,
            Permission.AGENT_READ
        }
    }
    return role_permissions.get(role, set())

def get_user_permissions(roles: Set[UserRole]) -> Set[Permission]:
    """ユーザーロールから権限を計算"""
    permissions = set()
    for role in roles:
        permissions.update(get_role_permissions(role))
    return permissions

class PasswordHasher:
    """パスワードハッシュ化（簡易版）"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """パスワードをハッシュ化"""
        salt = secrets.token_hex(16)
        return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """パスワードを検証"""
        try:
            salt, hash_value = hashed.split(":", 1)
            return hash_value == hashlib.sha256((salt + password).encode()).hexdigest()
        except ValueError:
            return False

class TokenManager:
    """JWTトークン管理"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def generate_token(self, user: User) -> str:
        """JWTトークンを生成"""
        payload = {
            'user_id': user.user_id,
            'username': user.username,
            'roles': [role.value for role in user.roles],
            'permissions': [perm.value for perm in user.permissions],
            'iat': time.time(),
            'exp': time.time() + (self.config.jwt_expiration_hours * 3600),
            'jti': str(uuid.uuid4())  # JWT ID for revocation
        }
        
        return jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """JWTトークンを検証"""
        try:
            payload = jwt.decode(
                token, 
                self.config.jwt_secret, 
                algorithms=[self.config.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def refresh_token(self, token: str) -> Optional[str]:
        """トークンをリフレッシュ"""
        payload = self.verify_token(token)
        if not payload:
            return None
        
        # 新しいトークンを生成（ユーザー情報は維持）
        new_payload = payload.copy()
        new_payload['iat'] = time.time()
        new_payload['exp'] = time.time() + (self.config.jwt_expiration_hours * 3600)
        new_payload['jti'] = str(uuid.uuid4())
        
        return jwt.encode(new_payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)

class APIKeyManager:
    """APIキー管理"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.api_keys: Dict[str, APIKey] = {}
    
    def generate_api_key(
        self, 
        user_id: str, 
        name: str, 
        permissions: Set[Permission] = None,
        expires_in_days: Optional[int] = None
    ) -> tuple[str, APIKey]:
        """APIキーを生成"""
        key_value = secrets.token_urlsafe(self.config.api_key_length)
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        key_id = str(uuid.uuid4())
        
        expires_at = None
        if expires_in_days:
            expires_at = time.time() + (expires_in_days * 24 * 3600)
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            name=name,
            permissions=permissions or set(),
            expires_at=expires_at,
            rate_limit=self.config.rate_limit_requests_per_hour
        )
        
        self.api_keys[key_id] = api_key
        return key_value, api_key
    
    def verify_api_key(self, key_value: str) -> Optional[APIKey]:
        """APIキーを検証"""
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        
        for api_key in self.api_keys.values():
            if api_key.key_hash == key_hash and api_key.is_valid():
                # 使用回数とラストアクセスを更新
                api_key.usage_count += 1
                api_key.last_used = time.time()
                return api_key
        
        return None
    
    def revoke_api_key(self, key_id: str) -> bool:
        """APIキーを無効化"""
        if key_id in self.api_keys:
            self.api_keys[key_id].is_active = False
            return True
        return False

class RateLimiter:
    """レート制限"""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, identifier: str, limit: int, window_seconds: int = 3600) -> bool:
        """レート制限チェック"""
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # 古いリクエストを削除
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier] 
                if req_time > window_start
            ]
        else:
            self.requests[identifier] = []
        
        # 制限チェック
        if len(self.requests[identifier]) >= limit:
            return False
        
        # リクエストを記録
        self.requests[identifier].append(current_time)
        return True

class SecurityAuditLogger:
    """セキュリティ監査ログ"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.audit_log: List[SecurityAuditEvent] = []
    
    def log_event(
        self,
        event_type: str,
        user_id: Optional[str],
        resource: str,
        action: str,
        result: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Dict[str, Any] = None
    ):
        """監査イベントをログ"""
        if not self.config.audit_log_enabled:
            return
        
        event = SecurityAuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            user_id=user_id,
            resource=resource,
            action=action,
            result=result,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {}
        )
        
        self.audit_log.append(event)
        
        # ログレベルに基づいて出力
        if result == "failure" or result == "denied":
            logger.warning(f"Security event: {event_type} - {action} on {resource} by {user_id}: {result}")
        else:
            logger.info(f"Security event: {event_type} - {action} on {resource} by {user_id}: {result}")
    
    def get_audit_log(
        self, 
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[SecurityAuditEvent]:
        """監査ログを取得"""
        filtered_log = self.audit_log
        
        if user_id:
            filtered_log = [event for event in filtered_log if event.user_id == user_id]
        
        if event_type:
            filtered_log = [event for event in filtered_log if event.event_type == event_type]
        
        if start_time:
            filtered_log = [event for event in filtered_log if event.timestamp >= start_time]
        
        if end_time:
            filtered_log = [event for event in filtered_log if event.timestamp <= end_time]
        
        # 最新から順にソート
        filtered_log.sort(key=lambda x: x.timestamp, reverse=True)
        
        return filtered_log[:limit]

class SecurityManager:
    """セキュリティマネージャー - 中央セキュリティ制御"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.users: Dict[str, User] = {}
        self.token_manager = TokenManager(config)
        self.api_key_manager = APIKeyManager(config)
        self.rate_limiter = RateLimiter()
        self.audit_logger = SecurityAuditLogger(config)
        self.failed_login_attempts: Dict[str, List[float]] = {}
        
        # デフォルトのスーパーアドミンユーザーを作成
        self._create_default_admin()
    
    def _create_default_admin(self):
        """デフォルトの管理者ユーザーを作成"""
        admin_user = User(
            user_id="admin",
            username="admin",
            email="admin@conductor.local"
        )
        admin_user.add_role(UserRole.SUPER_ADMIN)
        self.users["admin"] = admin_user
    
    def create_user(
        self, 
        username: str, 
        email: Optional[str] = None,
        roles: Set[UserRole] = None
    ) -> User:
        """ユーザーを作成"""
        user_id = str(uuid.uuid4())
        user = User(
            user_id=user_id,
            username=username,
            email=email
        )
        
        if roles:
            for role in roles:
                user.add_role(role)
        
        self.users[user_id] = user
        
        self.audit_logger.log_event(
            event_type="user_management",
            user_id=None,  # システムによる作成
            resource="user",
            action="create",
            result="success",
            details={"created_user_id": user_id, "username": username}
        )
        
        return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """ユーザー認証（パスワードベース）"""
        # この例では簡略化のため、実際の実装では
        # パスワードハッシュの検証が必要
        user = next((u for u in self.users.values() if u.username == username), None)
        
        if not user or not user.is_active:
            self.audit_logger.log_event(
                event_type="authentication",
                user_id=username,
                resource="login",
                action="authenticate",
                result="failure",
                details={"reason": "user_not_found_or_inactive"}
            )
            return None
        
        # 失敗回数チェック
        if self._is_user_locked_out(username):
            self.audit_logger.log_event(
                event_type="authentication",
                user_id=user.user_id,
                resource="login",
                action="authenticate",
                result="denied",
                details={"reason": "account_locked"}
            )
            return None
        
        # TODO: パスワード検証をここに実装
        # if not PasswordHasher.verify_password(password, user.password_hash):
        #     self._record_failed_login(username)
        #     return None
        
        # 認証成功
        user.last_login = time.time()
        self._clear_failed_login_attempts(username)
        
        self.audit_logger.log_event(
            event_type="authentication",
            user_id=user.user_id,
            resource="login",
            action="authenticate",
            result="success"
        )
        
        return user
    
    def authenticate_api_key(self, api_key: str) -> Optional[tuple[User, APIKey]]:
        """APIキー認証"""
        key_info = self.api_key_manager.verify_api_key(api_key)
        if not key_info:
            self.audit_logger.log_event(
                event_type="authentication",
                user_id=None,
                resource="api_key",
                action="authenticate",
                result="failure",
                details={"reason": "invalid_api_key"}
            )
            return None
        
        user = self.users.get(key_info.user_id)
        if not user or not user.is_active:
            self.audit_logger.log_event(
                event_type="authentication",
                user_id=key_info.user_id,
                resource="api_key",
                action="authenticate",
                result="failure",
                details={"reason": "user_not_found_or_inactive"}
            )
            return None
        
        # レート制限チェック
        if key_info.rate_limit and not self.rate_limiter.is_allowed(
            key_info.key_id, key_info.rate_limit
        ):
            self.audit_logger.log_event(
                event_type="rate_limit",
                user_id=user.user_id,
                resource="api_key",
                action="request",
                result="denied",
                details={"api_key_id": key_info.key_id}
            )
            return None
        
        self.audit_logger.log_event(
            event_type="authentication",
            user_id=user.user_id,
            resource="api_key",
            action="authenticate",
            result="success",
            details={"api_key_id": key_info.key_id}
        )
        
        return user, key_info
    
    def authorize_action(
        self, 
        user: User, 
        permission: Permission, 
        resource: str = "",
        action: str = ""
    ) -> bool:
        """アクション認可"""
        if not user.is_active:
            self.audit_logger.log_event(
                event_type="authorization",
                user_id=user.user_id,
                resource=resource,
                action=action,
                result="denied",
                details={"reason": "user_inactive", "required_permission": permission.value}
            )
            return False
        
        has_permission = user.has_permission(permission)
        
        self.audit_logger.log_event(
            event_type="authorization",
            user_id=user.user_id,
            resource=resource,
            action=action,
            result="success" if has_permission else "denied",
            details={"required_permission": permission.value}
        )
        
        return has_permission
    
    def _is_user_locked_out(self, username: str) -> bool:
        """ユーザーロックアウト状態チェック"""
        if username not in self.failed_login_attempts:
            return False
        
        current_time = time.time()
        lockout_window = self.config.lockout_duration_minutes * 60
        window_start = current_time - lockout_window
        
        # ウィンドウ内の失敗回数をカウント
        recent_failures = [
            attempt for attempt in self.failed_login_attempts[username]
            if attempt > window_start
        ]
        
        return len(recent_failures) >= self.config.max_login_attempts
    
    def _record_failed_login(self, username: str):
        """ログイン失敗を記録"""
        if username not in self.failed_login_attempts:
            self.failed_login_attempts[username] = []
        
        self.failed_login_attempts[username].append(time.time())
    
    def _clear_failed_login_attempts(self, username: str):
        """ログイン失敗記録をクリア"""
        if username in self.failed_login_attempts:
            del self.failed_login_attempts[username]
    
    def generate_token(self, user: User) -> str:
        """認証トークンを生成"""
        return self.token_manager.generate_token(user)
    
    def generate_api_key(
        self, 
        user_id: str, 
        name: str, 
        permissions: Set[Permission] = None,
        expires_in_days: Optional[int] = None
    ) -> tuple[str, APIKey]:
        """APIキーを生成"""
        return self.api_key_manager.generate_api_key(
            user_id, name, permissions, expires_in_days
        )
    
    def get_security_stats(self) -> Dict[str, Any]:
        """セキュリティ統計を取得"""
        current_time = time.time()
        last_24h = current_time - 86400
        
        recent_events = [
            event for event in self.audit_logger.audit_log
            if event.timestamp > last_24h
        ]
        
        failed_auth = len([
            event for event in recent_events
            if event.event_type == "authentication" and event.result == "failure"
        ])
        
        denied_auth = len([
            event for event in recent_events
            if event.event_type == "authorization" and event.result == "denied"
        ])
        
        return {
            "total_users": len(self.users),
            "active_users": len([u for u in self.users.values() if u.is_active]),
            "total_api_keys": len(self.api_key_manager.api_keys),
            "active_api_keys": len([k for k in self.api_key_manager.api_keys.values() if k.is_valid()]),
            "recent_events_24h": len(recent_events),
            "failed_authentications_24h": failed_auth,
            "denied_authorizations_24h": denied_auth,
            "locked_users": len([
                username for username in self.failed_login_attempts
                if self._is_user_locked_out(username)
            ])
        }

def require_permission(permission: Permission):
    """権限要求デコレーター"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 実際の実装では、リクエストコンテキストから
            # セキュリティマネージャーとユーザー情報を取得
            security_manager = kwargs.get('security_manager')
            user = kwargs.get('current_user')
            
            if not security_manager or not user:
                raise PermissionError("Authentication required")
            
            if not security_manager.authorize_action(
                user, permission, 
                resource=func.__name__, 
                action="execute"
            ):
                raise PermissionError(f"Permission denied: {permission.value}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(role: UserRole):
    """ロール要求デコレーター"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            
            if not user or not user.has_role(role):
                raise PermissionError(f"Role required: {role.value}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# セキュリティ設定のデフォルト値
DEFAULT_SECURITY_CONFIG = SecurityConfig(
    jwt_secret="your-secret-key-change-in-production",
    jwt_algorithm="HS256",
    jwt_expiration_hours=24,
    api_key_length=32,
    password_min_length=8,
    max_login_attempts=5,
    lockout_duration_minutes=30,
    session_timeout_hours=8,
    require_2fa=False,
    allowed_origins=["http://localhost:3000", "http://localhost:8000"],
    rate_limit_requests_per_hour=1000,
    audit_log_enabled=True
)
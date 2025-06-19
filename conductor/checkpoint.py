#!/usr/bin/env python3
"""
チェックポイント・復旧メカニズムの実装
"""

import os
import json
import time
import pickle
import shutil
import threading
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CheckpointState(Enum):
    """チェックポイントの状態"""
    CREATED = "created"
    VALIDATING = "validating"
    VALIDATED = "validated"
    CORRUPTED = "corrupted"
    RESTORED = "restored"

@dataclass
class Checkpoint:
    """チェックポイントデータ"""
    checkpoint_id: str
    task_id: str
    agent_id: str
    timestamp: float
    state: CheckpointState
    progress: float  # 0.0 - 1.0
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['state'] = self.state.value
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        data['state'] = CheckpointState(data['state'])
        return cls(**data)

@dataclass
class RecoveryOptions:
    """復旧オプション"""
    retry_from_checkpoint: bool = True
    max_retry_attempts: int = 3
    restore_workspace: bool = True
    notify_on_recovery: bool = True
    cleanup_on_success: bool = True
    preserve_failed_state: bool = False

class CheckpointManager:
    """チェックポイント管理システム"""
    
    def __init__(
        self,
        storage_path: str = "/tmp/claude_checkpoints",
        storage_backend: str = "filesystem",  # "filesystem" or "redis"
        redis_config: Optional[Dict[str, Any]] = None
    ):
        self.storage_path = storage_path
        self.storage_backend = storage_backend
        self.redis_config = redis_config
        
        # ストレージバックエンドの初期化
        if storage_backend == "filesystem":
            os.makedirs(storage_path, exist_ok=True)
            self._storage = FilesystemCheckpointStorage(storage_path)
        elif storage_backend == "redis":
            if not redis_config:
                raise ValueError("Redis config required for redis backend")
            self._storage = RedisCheckpointStorage(redis_config)
        else:
            raise ValueError(f"Unknown storage backend: {storage_backend}")
            
        # チェックポイント管理
        self.active_checkpoints: Dict[str, List[Checkpoint]] = {}
        self.checkpoint_interval: float = 60.0  # デフォルト60秒
        self.max_checkpoints_per_task: int = 10
        self._checkpoint_threads: Dict[str, threading.Thread] = {}
        self._stop_flags: Dict[str, threading.Event] = {}
        
    def enable_auto_checkpoint(
        self,
        task_id: str,
        interval: float,
        checkpoint_func: Callable[[], Dict[str, Any]]
    ):
        """自動チェックポイントを有効化"""
        if task_id in self._checkpoint_threads:
            logger.warning(f"Auto checkpoint already enabled for task {task_id}")
            return
            
        stop_flag = threading.Event()
        self._stop_flags[task_id] = stop_flag
        
        def checkpoint_loop():
            while not stop_flag.is_set():
                try:
                    # チェックポイントデータを取得
                    data = checkpoint_func()
                    if data:
                        self.create_checkpoint(
                            task_id=task_id,
                            agent_id=data.get("agent_id", "unknown"),
                            progress=data.get("progress", 0.0),
                            data=data
                        )
                except Exception as e:
                    logger.error(f"Auto checkpoint failed for task {task_id}: {e}")
                    
                # インターバル待機
                stop_flag.wait(interval)
                
        thread = threading.Thread(
            target=checkpoint_loop,
            name=f"checkpoint_{task_id}",
            daemon=True
        )
        thread.start()
        self._checkpoint_threads[task_id] = thread
        
        logger.info(f"Auto checkpoint enabled for task {task_id} with interval {interval}s")
        
    def disable_auto_checkpoint(self, task_id: str):
        """自動チェックポイントを無効化"""
        if task_id in self._stop_flags:
            self._stop_flags[task_id].set()
            
        if task_id in self._checkpoint_threads:
            thread = self._checkpoint_threads[task_id]
            thread.join(timeout=5.0)
            del self._checkpoint_threads[task_id]
            
        if task_id in self._stop_flags:
            del self._stop_flags[task_id]
            
        logger.info(f"Auto checkpoint disabled for task {task_id}")
        
    def create_checkpoint(
        self,
        task_id: str,
        agent_id: str,
        progress: float,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Checkpoint:
        """チェックポイントを作成"""
        checkpoint_id = f"{task_id}_{int(time.time() * 1000)}"
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            agent_id=agent_id,
            timestamp=time.time(),
            state=CheckpointState.CREATED,
            progress=progress,
            data=data,
            metadata=metadata or {}
        )
        
        # ストレージに保存
        try:
            self._storage.save(checkpoint)
            checkpoint.state = CheckpointState.VALIDATED
            
            # アクティブチェックポイントリストに追加
            if task_id not in self.active_checkpoints:
                self.active_checkpoints[task_id] = []
            self.active_checkpoints[task_id].append(checkpoint)
            
            # 古いチェックポイントを削除
            self._cleanup_old_checkpoints(task_id)
            
            logger.info(
                f"Checkpoint created: {checkpoint_id} "
                f"(task: {task_id}, progress: {progress:.1%})"
            )
            
        except Exception as e:
            checkpoint.state = CheckpointState.CORRUPTED
            logger.error(f"Failed to save checkpoint {checkpoint_id}: {e}")
            raise
            
        return checkpoint
        
    def get_latest_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """最新のチェックポイントを取得"""
        checkpoints = self._storage.list_checkpoints(task_id)
        if not checkpoints:
            return None
            
        # タイムスタンプでソート
        checkpoints.sort(key=lambda c: c.timestamp, reverse=True)
        
        # 検証済みのチェックポイントを返す
        for checkpoint in checkpoints:
            if checkpoint.state == CheckpointState.VALIDATED:
                return checkpoint
                
        return None
        
    def restore_checkpoint(
        self,
        checkpoint_id: str,
        options: Optional[RecoveryOptions] = None
    ) -> Dict[str, Any]:
        """チェックポイントから復元"""
        if options is None:
            options = RecoveryOptions()
            
        try:
            # チェックポイントを読み込み
            checkpoint = self._storage.load(checkpoint_id)
            if not checkpoint:
                raise ValueError(f"Checkpoint {checkpoint_id} not found")
                
            # チェックポイントの検証
            if checkpoint.state != CheckpointState.VALIDATED:
                raise ValueError(
                    f"Checkpoint {checkpoint_id} is not validated "
                    f"(state: {checkpoint.state.value})"
                )
                
            # 復元処理
            recovery_result = {
                "checkpoint_id": checkpoint_id,
                "task_id": checkpoint.task_id,
                "agent_id": checkpoint.agent_id,
                "progress": checkpoint.progress,
                "data": checkpoint.data,
                "metadata": checkpoint.metadata,
                "restored_at": time.time()
            }
            
            # ワークスペースの復元
            if options.restore_workspace and "workspace_snapshot" in checkpoint.data:
                workspace_result = self._restore_workspace(
                    checkpoint.data["workspace_snapshot"]
                )
                recovery_result["workspace_restored"] = workspace_result
                
            # 状態を更新
            checkpoint.state = CheckpointState.RESTORED
            self._storage.update_state(checkpoint_id, CheckpointState.RESTORED)
            
            logger.info(
                f"Checkpoint restored: {checkpoint_id} "
                f"(progress: {checkpoint.progress:.1%})"
            )
            
            return recovery_result
            
        except Exception as e:
            logger.error(f"Failed to restore checkpoint {checkpoint_id}: {e}")
            raise
            
    def recover_task(
        self,
        task_id: str,
        recovery_handler: Callable[[Dict[str, Any]], Any],
        options: Optional[RecoveryOptions] = None
    ) -> Optional[Any]:
        """タスクを復旧"""
        if options is None:
            options = RecoveryOptions()
            
        # 最新のチェックポイントを取得
        checkpoint = self.get_latest_checkpoint(task_id)
        if not checkpoint:
            logger.warning(f"No checkpoint found for task {task_id}")
            return None
            
        logger.info(
            f"Recovering task {task_id} from checkpoint {checkpoint.checkpoint_id} "
            f"(progress: {checkpoint.progress:.1%})"
        )
        
        # リトライループ
        attempts = 0
        last_error = None
        
        while attempts < options.max_retry_attempts:
            attempts += 1
            
            try:
                # チェックポイントから復元
                recovery_data = self.restore_checkpoint(
                    checkpoint.checkpoint_id,
                    options
                )
                
                # 復旧ハンドラーを実行
                result = recovery_handler(recovery_data)
                
                # 成功時のクリーンアップ
                if options.cleanup_on_success:
                    self.cleanup_task_checkpoints(task_id)
                    
                logger.info(
                    f"Task {task_id} recovered successfully "
                    f"(attempts: {attempts})"
                )
                
                return result
                
            except Exception as e:
                last_error = e
                logger.error(
                    f"Recovery attempt {attempts} failed for task {task_id}: {e}"
                )
                
                if attempts < options.max_retry_attempts:
                    # 指数バックオフで待機
                    wait_time = 2 ** attempts
                    time.sleep(wait_time)
                    
        # すべての試行が失敗
        if options.preserve_failed_state:
            self._preserve_failed_state(task_id, checkpoint, last_error)
            
        raise RuntimeError(
            f"Failed to recover task {task_id} after {attempts} attempts: {last_error}"
        )
        
    def cleanup_task_checkpoints(self, task_id: str):
        """タスクのチェックポイントをクリーンアップ"""
        try:
            # 自動チェックポイントを停止
            self.disable_auto_checkpoint(task_id)
            
            # ストレージからチェックポイントを削除
            self._storage.delete_task_checkpoints(task_id)
            
            # メモリから削除
            if task_id in self.active_checkpoints:
                del self.active_checkpoints[task_id]
                
            logger.info(f"Cleaned up checkpoints for task {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup checkpoints for task {task_id}: {e}")
            
    def get_checkpoint_history(
        self,
        task_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """チェックポイント履歴を取得"""
        checkpoints = self._storage.list_checkpoints(task_id)
        
        # タイムスタンプでソート
        checkpoints.sort(key=lambda c: c.timestamp, reverse=True)
        
        # 制限数まで取得
        checkpoints = checkpoints[:limit]
        
        # 辞書形式に変換
        return [c.to_dict() for c in checkpoints]
        
    def _cleanup_old_checkpoints(self, task_id: str):
        """古いチェックポイントを削除"""
        if task_id not in self.active_checkpoints:
            return
            
        checkpoints = self.active_checkpoints[task_id]
        
        # 制限数を超えている場合、古いものを削除
        if len(checkpoints) > self.max_checkpoints_per_task:
            # タイムスタンプでソート
            checkpoints.sort(key=lambda c: c.timestamp)
            
            # 削除対象
            to_delete = checkpoints[:-self.max_checkpoints_per_task]
            
            for checkpoint in to_delete:
                try:
                    self._storage.delete(checkpoint.checkpoint_id)
                    checkpoints.remove(checkpoint)
                except Exception as e:
                    logger.error(
                        f"Failed to delete old checkpoint "
                        f"{checkpoint.checkpoint_id}: {e}"
                    )
                    
    def _restore_workspace(self, snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
        """ワークスペースを復元"""
        # ワークスペースの復元ロジック（実装は環境に依存）
        result = {
            "restored": True,
            "snapshot_id": snapshot_data.get("snapshot_id"),
            "restored_files": snapshot_data.get("files", [])
        }
        
        # TODO: 実際のワークスペース復元処理を実装
        
        return result
        
    def _preserve_failed_state(
        self,
        task_id: str,
        checkpoint: Checkpoint,
        error: Exception
    ):
        """失敗状態を保存"""
        failed_state = {
            "task_id": task_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": time.time(),
            "checkpoint_data": checkpoint.to_dict()
        }
        
        # 失敗状態を別途保存
        failed_path = os.path.join(
            self.storage_path,
            "failed_states",
            f"{task_id}_{int(time.time())}.json"
        )
        
        os.makedirs(os.path.dirname(failed_path), exist_ok=True)
        
        with open(failed_path, 'w') as f:
            json.dump(failed_state, f, indent=2)
            
        logger.info(f"Preserved failed state for task {task_id}: {failed_path}")


class FilesystemCheckpointStorage:
    """ファイルシステムベースのチェックポイントストレージ"""
    
    def __init__(self, base_path: str):
        self.base_path = base_path
        
    def save(self, checkpoint: Checkpoint):
        """チェックポイントを保存"""
        task_dir = os.path.join(self.base_path, checkpoint.task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        file_path = os.path.join(task_dir, f"{checkpoint.checkpoint_id}.pkl")
        
        with open(file_path, 'wb') as f:
            pickle.dump(checkpoint, f)
            
    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """チェックポイントを読み込み"""
        # すべてのタスクディレクトリを検索
        for task_id in os.listdir(self.base_path):
            task_dir = os.path.join(self.base_path, task_id)
            if not os.path.isdir(task_dir):
                continue
                
            file_path = os.path.join(task_dir, f"{checkpoint_id}.pkl")
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    return pickle.load(f)
                    
        return None
        
    def list_checkpoints(self, task_id: str) -> List[Checkpoint]:
        """タスクのチェックポイント一覧を取得"""
        task_dir = os.path.join(self.base_path, task_id)
        if not os.path.exists(task_dir):
            return []
            
        checkpoints = []
        for filename in os.listdir(task_dir):
            if filename.endswith('.pkl'):
                file_path = os.path.join(task_dir, filename)
                try:
                    with open(file_path, 'rb') as f:
                        checkpoint = pickle.load(f)
                        checkpoints.append(checkpoint)
                except Exception as e:
                    logger.error(f"Failed to load checkpoint {file_path}: {e}")
                    
        return checkpoints
        
    def delete(self, checkpoint_id: str):
        """チェックポイントを削除"""
        # すべてのタスクディレクトリを検索
        for task_id in os.listdir(self.base_path):
            task_dir = os.path.join(self.base_path, task_id)
            if not os.path.isdir(task_dir):
                continue
                
            file_path = os.path.join(task_dir, f"{checkpoint_id}.pkl")
            if os.path.exists(file_path):
                os.remove(file_path)
                return
                
    def delete_task_checkpoints(self, task_id: str):
        """タスクのすべてのチェックポイントを削除"""
        task_dir = os.path.join(self.base_path, task_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
            
    def update_state(self, checkpoint_id: str, state: CheckpointState):
        """チェックポイントの状態を更新"""
        checkpoint = self.load(checkpoint_id)
        if checkpoint:
            checkpoint.state = state
            self.save(checkpoint)


class RedisCheckpointStorage:
    """Redisベースのチェックポイントストレージ"""
    
    def __init__(self, redis_config: Dict[str, Any]):
        import redis
        self.redis_client = redis.Redis(**redis_config)
        self.key_prefix = "checkpoint:"
        self.ttl = 86400  # 24時間
        
    def save(self, checkpoint: Checkpoint):
        """チェックポイントを保存"""
        key = f"{self.key_prefix}{checkpoint.checkpoint_id}"
        data = pickle.dumps(checkpoint)
        self.redis_client.setex(key, self.ttl, data)
        
        # タスクインデックスに追加
        task_key = f"{self.key_prefix}task:{checkpoint.task_id}"
        self.redis_client.sadd(task_key, checkpoint.checkpoint_id)
        self.redis_client.expire(task_key, self.ttl)
        
    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """チェックポイントを読み込み"""
        key = f"{self.key_prefix}{checkpoint_id}"
        data = self.redis_client.get(key)
        if data:
            return pickle.loads(data)
        return None
        
    def list_checkpoints(self, task_id: str) -> List[Checkpoint]:
        """タスクのチェックポイント一覧を取得"""
        task_key = f"{self.key_prefix}task:{task_id}"
        checkpoint_ids = self.redis_client.smembers(task_key)
        
        checkpoints = []
        for checkpoint_id in checkpoint_ids:
            checkpoint = self.load(checkpoint_id.decode())
            if checkpoint:
                checkpoints.append(checkpoint)
                
        return checkpoints
        
    def delete(self, checkpoint_id: str):
        """チェックポイントを削除"""
        key = f"{self.key_prefix}{checkpoint_id}"
        self.redis_client.delete(key)
        
    def delete_task_checkpoints(self, task_id: str):
        """タスクのすべてのチェックポイントを削除"""
        task_key = f"{self.key_prefix}task:{task_id}"
        checkpoint_ids = self.redis_client.smembers(task_key)
        
        # 各チェックポイントを削除
        for checkpoint_id in checkpoint_ids:
            self.delete(checkpoint_id.decode())
            
        # タスクインデックスを削除
        self.redis_client.delete(task_key)
        
    def update_state(self, checkpoint_id: str, state: CheckpointState):
        """チェックポイントの状態を更新"""
        checkpoint = self.load(checkpoint_id)
        if checkpoint:
            checkpoint.state = state
            self.save(checkpoint)
# Claude Code Multi-Agent Orchestrator 開発引き継ぎ文書

## 1. プロジェクト概要

### 目的
複数のClaude Codeインスタンスをヘッドレスモードで並列実行し、Agent2Agentプロトコルで協調動作させるシステムの開発。

### 技術スタック
- **言語**: Python 3.10+
- **コンテナ**: Podman
- **通信**: Unix Socket / Redis (将来)
- **並列処理**: ThreadPoolExecutor

### アーキテクチャ概要
```
[Orchestrator] (中央制御)
    ├── [Agent Manager] (エージェント管理)
    │   ├── Claude Code Agent 1 (Podmanコンテナ)
    │   ├── Claude Code Agent 2 (Podmanコンテナ)
    │   └── Claude Code Agent N (Podmanコンテナ)
    │
    ├── [Message Broker] (メッセージ仲介)
    │   └── Agent2Agent Protocol Handler
    │
    └── [Task Queue] (タスク管理)
```

## 2. プロジェクトセットアップ

### 2.1 初期ディレクトリ構造作成

```bash
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
```

## 3. ソースコード

### 3.1 Claude Code Wrapper (src/claude_code_wrapper.py)

```python
#!/usr/bin/env python3
"""
Claude Code Wrapper - ヘッドレスモード動作確認とプロセス制御
"""

import subprocess
import threading
import queue
import time
import json
import os
import signal
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """エージェント設定"""
    agent_id: str
    container_name: str
    work_dir: str
    podman_image: str = "ubuntu:22.04"
    memory_limit: str = "2g"
    cpu_limit: str = "1.0"
    
@dataclass
class CommandResult:
    """コマンド実行結果"""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    timestamp: float

class ClaudeCodeWrapper:
    """Claude Codeプロセスのラッパー"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.container_id: Optional[str] = None
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self.is_running = False
        
    def setup_container(self) -> str:
        """Podmanコンテナのセットアップ"""
        logger.info(f"Setting up container for agent {self.config.agent_id}")
        
        # 既存コンテナのクリーンアップ
        self._cleanup_existing_container()
        
        # コンテナ作成コマンド
        cmd = [
            "podman", "run", "-d",
            "--name", self.config.container_name,
            "-v", f"{self.config.work_dir}:/workspace:Z",
            "-w", "/workspace",
            "--memory", self.config.memory_limit,
            "--cpus", self.config.cpu_limit,
            "--userns=keep-id",
            self.config.podman_image,
            "sleep", "infinity"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Container creation failed: {result.stderr}")
                
            self.container_id = result.stdout.strip()
            logger.info(f"Container created: {self.container_id[:12]}")
            
            # 基本ツールのインストール
            self._install_base_tools()
            
            # Claude Codeのインストール
            self._install_claude_code()
            
            return self.container_id
            
        except Exception as e:
            logger.error(f"Container setup failed: {e}")
            raise
            
    def _cleanup_existing_container(self):
        """既存のコンテナをクリーンアップ"""
        subprocess.run(
            ["podman", "rm", "-f", self.config.container_name],
            capture_output=True
        )
        
    def _install_base_tools(self):
        """基本ツールのインストール"""
        commands = [
            "apt-get update",
            "apt-get install -y curl git python3 python3-pip",
        ]
        
        for cmd in commands:
            result = self.exec_in_container(cmd)
            if result.exit_code != 0:
                logger.warning(f"Command failed: {cmd}")
                
    def _install_claude_code(self):
        """コンテナ内にClaude Codeをセットアップ"""
        # TODO: 実際のClaude Codeインストール手順に置き換える
        # 現在はダミースクリプトを配置
        dummy_script = '''#!/usr/bin/env python3
import sys
import json
import time
import random

def process_command(cmd):
    time.sleep(random.uniform(0.5, 2.0))
    
    if cmd.startswith("review"):
        return {"type": "review", "issues": random.randint(0, 5)}
    elif cmd.startswith("refactor"):
        return {"type": "refactor", "changes": random.randint(1, 3)}
    else:
        return {"type": "generic", "status": "completed"}

if "--headless" in sys.argv:
    while True:
        try:
            line = sys.stdin.readline().strip()
            if not line:
                continue
            result = process_command(line)
            print(json.dumps(result))
            sys.stdout.flush()
        except:
            break
'''
        
        # ダミースクリプトを作成
        self.exec_in_container(f"cat > /usr/local/bin/claude-code << 'EOF'\n{dummy_script}\nEOF")
        self.exec_in_container("chmod +x /usr/local/bin/claude-code")
            
    def exec_in_container(self, command: str) -> CommandResult:
        """コンテナ内でコマンドを実行"""
        cmd = ["podman", "exec", self.config.container_name, "bash", "-c", command]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return CommandResult(
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            timestamp=time.time()
        )
        
    def start_claude_code(self, headless: bool = True):
        """Claude Codeプロセスを開始"""
        logger.info(f"Starting Claude Code for agent {self.config.agent_id}")
        
        # Claude Codeの実行コマンド
        claude_cmd = "claude-code"
        if headless:
            claude_cmd += " --headless"
            
        # プロセスを開始
        cmd = [
            "podman", "exec", "-i",
            self.config.container_name,
            claude_cmd
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        self.is_running = True
        
        # 出力読み取りスレッドを開始
        self._start_output_readers()
        
    def _start_output_readers(self):
        """stdout/stderrの読み取りスレッドを開始"""
        def read_stdout():
            while self.is_running and self.process:
                try:
                    line = self.process.stdout.readline()
                    if line:
                        self.output_queue.put(("stdout", line.strip()))
                except:
                    break
                    
        def read_stderr():
            while self.is_running and self.process:
                try:
                    line = self.process.stderr.readline()
                    if line:
                        self.output_queue.put(("stderr", line.strip()))
                except:
                    break
                    
        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()
        
    def send_command(self, command: str):
        """Claude Codeにコマンドを送信"""
        if not self.process or not self.is_running:
            raise Exception("Claude Code is not running")
            
        logger.info(f"Sending command: {command}")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        
    def read_output(self, timeout: float = 1.0) -> List[tuple]:
        """出力を読み取る"""
        outputs = []
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                output = self.output_queue.get(timeout=0.1)
                outputs.append(output)
            except queue.Empty:
                if not outputs:
                    continue
                else:
                    break
                    
        return outputs
        
    def stop(self):
        """プロセスを停止"""
        logger.info(f"Stopping agent {self.config.agent_id}")
        self.is_running = False
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                
    def cleanup_container(self):
        """コンテナをクリーンアップ"""
        if self.container_id:
            subprocess.run(["podman", "stop", self.config.container_name])
            subprocess.run(["podman", "rm", self.config.container_name])
            logger.info(f"Container {self.config.container_name} cleaned up")
            
    def __enter__(self):
        self.setup_container()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.cleanup_container()
```

### 3.2 エージェント間通信 (src/agent_communication.py)

```python
#!/usr/bin/env python3
"""
Agent2Agent Communication Protocol Implementation
"""

import json
import time
import socket
import threading
import queue
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    """メッセージタイプ"""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    COORDINATION = "coordination"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

@dataclass
class AgentMessage:
    """エージェント間メッセージ"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: float
    correlation_id: Optional[str] = None
    
    def to_json(self) -> str:
        data = asdict(self)
        data['message_type'] = self.message_type.value
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentMessage':
        data = json.loads(json_str)
        data['message_type'] = MessageType(data['message_type'])
        return cls(**data)

class UnixSocketChannel:
    """Unix Socket を使った通信チャネル"""
    
    def __init__(self, socket_path: str, is_server: bool = False):
        self.socket_path = socket_path
        self.is_server = is_server
        self.socket = None
        self.receive_queue = queue.Queue()
        self.is_running = False
        self.clients = []  # サーバーモードでのクライアント管理
        
        if is_server:
            self._start_server()
        else:
            self._connect_client()
            
    def _start_server(self):
        """サーバーソケットを開始"""
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
            
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.socket_path)
        self.socket.listen(5)
        self.is_running = True
        
        threading.Thread(target=self._accept_connections, daemon=True).start()
        logger.info(f"Unix socket server started at {self.socket_path}")
        
    def _accept_connections(self):
        """クライアント接続を受け付ける"""
        while self.is_running:
            try:
                client_socket, _ = self.socket.accept()
                self.clients.append(client_socket)
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                ).start()
            except Exception as e:
                if self.is_running:
                    logger.error(f"Accept error: {e}")
                    
    def _handle_client(self, client_socket):
        """クライアントからのメッセージを処理"""
        while self.is_running:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                    
                message = AgentMessage.from_json(data.decode())
                self.receive_queue.put(message)
                
                # ブロードキャスト処理
                if message.receiver_id == "broadcast":
                    self._broadcast_message(message, exclude_socket=client_socket)
                    
            except Exception as e:
                logger.error(f"Client handling error: {e}")
                break
                
        client_socket.close()
        self.clients.remove(client_socket)
        
    def _broadcast_message(self, message: AgentMessage, exclude_socket=None):
        """全クライアントにメッセージをブロードキャスト"""
        data = message.to_json().encode()
        for client in self.clients:
            if client != exclude_socket:
                try:
                    client.sendall(data)
                except:
                    pass
                    
    def _connect_client(self):
        """クライアントとして接続"""
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(self.socket_path)
        self.is_running = True
        
        threading.Thread(target=self._receive_messages, daemon=True).start()
        logger.info(f"Connected to Unix socket at {self.socket_path}")
        
    def _receive_messages(self):
        """メッセージを受信"""
        while self.is_running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                    
                message = AgentMessage.from_json(data.decode())
                self.receive_queue.put(message)
                
            except Exception as e:
                if self.is_running:
                    logger.error(f"Receive error: {e}")
                    
    def send(self, message: AgentMessage):
        """メッセージを送信"""
        if not self.socket:
            raise Exception("Socket not connected")
            
        data = message.to_json().encode()
        self.socket.sendall(data)
        
    def receive(self, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """メッセージを受信"""
        try:
            return self.receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None
            
    def close(self):
        """接続を閉じる"""
        self.is_running = False
        if self.socket:
            self.socket.close()
        if self.is_server and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

class Agent2AgentProtocol:
    """Agent2Agentプロトコルの実装"""
    
    def __init__(self, agent_id: str, channel: UnixSocketChannel):
        self.agent_id = agent_id
        self.channel = channel
        self.pending_requests: Dict[str, AgentMessage] = {}
        self.response_handlers: Dict[str, Callable] = {}
        self.message_handlers: Dict[MessageType, Callable] = {}
        
    def register_handler(self, message_type: MessageType, handler: Callable):
        """メッセージハンドラーを登録"""
        self.message_handlers[message_type] = handler
        
    def send_task_request(
        self,
        receiver_id: str,
        task: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> str:
        """タスクリクエストを送信"""
        message_id = f"{self.agent_id}_{int(time.time()*1000)}"
        
        message = AgentMessage(
            message_id=message_id,
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=MessageType.TASK_REQUEST,
            payload=task,
            timestamp=time.time()
        )
        
        self.pending_requests[message_id] = message
        if callback:
            self.response_handlers[message_id] = callback
            
        self.channel.send(message)
        return message_id
        
    def send_task_response(
        self,
        request_message: AgentMessage,
        result: Dict[str, Any]
    ):
        """タスクレスポンスを送信"""
        response = AgentMessage(
            message_id=f"{self.agent_id}_{int(time.time()*1000)}",
            sender_id=self.agent_id,
            receiver_id=request_message.sender_id,
            message_type=MessageType.TASK_RESPONSE,
            payload=result,
            timestamp=time.time(),
            correlation_id=request_message.message_id
        )
        
        self.channel.send(response)
        
    def process_messages(self):
        """受信メッセージを処理"""
        message = self.channel.receive(timeout=0.1)
        if not message:
            return
            
        if message.message_type == MessageType.TASK_RESPONSE:
            if message.correlation_id in self.response_handlers:
                handler = self.response_handlers[message.correlation_id]
                handler(message)
                del self.response_handlers[message.correlation_id]
                del self.pending_requests[message.correlation_id]
                
        elif message.message_type in self.message_handlers:
            handler = self.message_handlers[message.message_type]
            handler(message)
```

### 3.3 オーケストレーター (src/orchestrator.py)

```python
#!/usr/bin/env python3
"""
Claude Code Multi-Agent Orchestrator
"""

import os
import time
import json
import uuid
import threading
import yaml
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime

# 前述のモジュールをインポート
from .claude_code_wrapper import ClaudeCodeWrapper, AgentConfig
from .agent_communication import (
    AgentMessage, MessageType, UnixSocketChannel,
    Agent2AgentProtocol
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Task:
    """タスク定義"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = "generic"
    description: str = ""
    files: List[str] = field(default_factory=list)
    parallel: bool = False
    subtasks: Optional[List[Dict[str, Any]]] = None
    priority: int = 5  # 1-10, 10が最高
    timeout: float = 300.0  # 5分
    
@dataclass
class TaskResult:
    """タスク実行結果"""
    task_id: str
    agent_id: str
    status: str  # "success", "failed", "timeout", "partial"
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)

class ClaudeAgent:
    """Claude Codeエージェント"""
    
    def __init__(self, agent_id: str, orchestrator: 'Orchestrator'):
        self.agent_id = agent_id
        self.orchestrator = orchestrator
        
        # Podmanコンテナ設定
        self.config = AgentConfig(
            agent_id=agent_id,
            container_name=f"claude_agent_{agent_id}",
            work_dir=f"/tmp/claude_workspace_{agent_id}"
        )
        
        # コンポーネント
        self.wrapper: Optional[ClaudeCodeWrapper] = None
        self.protocol: Optional[Agent2AgentProtocol] = None
        self.channel: Optional[UnixSocketChannel] = None
        
        # 状態
        self.is_running = False
        self.current_task: Optional[Task] = None
        self.health_check_failed = 0
        
    def start(self):
        """エージェントを起動"""
        logger.info(f"Starting agent {self.agent_id}")
        
        try:
            # ワークスペース作成
            os.makedirs(self.config.work_dir, exist_ok=True)
            
            # Wrapperの初期化
            self.wrapper = ClaudeCodeWrapper(self.config)
            self.wrapper.setup_container()
            
            # 通信チャネルの初期化
            socket_path = f"/tmp/claude_agent_{self.agent_id}.sock"
            self.channel = UnixSocketChannel(socket_path, is_server=False)
            self.protocol = Agent2AgentProtocol(self.agent_id, self.channel)
            
            # メッセージハンドラー登録
            self.protocol.register_handler(
                MessageType.TASK_REQUEST,
                self._handle_task_request
            )
            
            # Claude Code起動
            self.wrapper.start_claude_code(headless=True)
            self.is_running = True
            
            # メッセージ処理スレッド
            threading.Thread(target=self._process_messages, daemon=True).start()
            
            # ヘルスチェックスレッド
            threading.Thread(target=self._health_check_loop, daemon=True).start()
            
            logger.info(f"Agent {self.agent_id} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start agent {self.agent_id}: {e}")
            raise
            
    def stop(self):
        """エージェントを停止"""
        logger.info(f"Stopping agent {self.agent_id}")
        self.is_running = False
        
        if self.wrapper:
            self.wrapper.stop()
            self.wrapper.cleanup_container()
            
        if self.channel:
            self.channel.close()
            
    def execute_task(self, task: Task) -> TaskResult:
        """タスクを実行"""
        self.current_task = task
        start_time = time.time()
        
        try:
            logger.info(f"Agent {self.agent_id} executing task {task.task_id}")
            
            # タスクタイプに応じた処理
            if task.task_type == "code_review":
                result = self._execute_code_review(task)
            elif task.task_type == "refactor":
                result = self._execute_refactor(task)
            elif task.task_type == "test_generation":
                result = self._execute_test_generation(task)
            elif task.task_type == "analysis":
                result = self._execute_analysis(task)
            else:
                result = self._execute_generic_task(task)
                
            execution_time = time.time() - start_time
            
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status="success",
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status="failed",
                result={},
                error=str(e),
                execution_time=time.time() - start_time
            )
        finally:
            self.current_task = None
            
    def _execute_code_review(self, task: Task) -> Dict[str, Any]:
        """コードレビュータスクの実行"""
        results = {}
        total_issues = 0
        
        for file_path in task.files:
            # ファイルをコンテナにコピー
            self._copy_file_to_container(file_path)
            
            # レビューコマンド送信
            command = f"review {os.path.basename(file_path)}"
            self.wrapper.send_command(command)
            
            # 結果を収集
            outputs = self.wrapper.read_output(timeout=10.0)
            
            # 結果をパース（実装に応じて調整）
            review_result = self._parse_review_output(outputs)
            results[file_path] = review_result
            total_issues += review_result.get("issue_count", 0)
            
        return {
            "files_reviewed": len(task.files),
            "total_issues": total_issues,
            "details": results
        }
        
    def _execute_refactor(self, task: Task) -> Dict[str, Any]:
        """リファクタリングタスクの実行"""
        # ファイルをコンテナにコピー
        for file_path in task.files:
            self._copy_file_to_container(file_path)
            
        # リファクタリングコマンド
        command = f"refactor {' '.join([os.path.basename(f) for f in task.files])}"
        if task.description:
            command += f" --description '{task.description}'"
            
        self.wrapper.send_command(command)
        
        # 結果を収集（タイムアウトを長めに）
        outputs = self.wrapper.read_output(timeout=30.0)
        
        return {
            "refactored": True,
            "files_affected": len(task.files),
            "output": self._format_output(outputs)
        }
        
    def _execute_test_generation(self, task: Task) -> Dict[str, Any]:
        """テスト生成タスクの実行"""
        results = {}
        total_tests = 0
        
        for file_path in task.files:
            self._copy_file_to_container(file_path)
            
            command = f"generate-tests {os.path.basename(file_path)}"
            self.wrapper.send_command(command)
            
            outputs = self.wrapper.read_output(timeout=20.0)
            test_result = self._parse_test_output(outputs)
            results[file_path] = test_result
            total_tests += test_result.get("test_count", 0)
            
        return {
            "files_processed": len(task.files),
            "total_tests_generated": total_tests,
            "details": results
        }
        
    def _execute_analysis(self, task: Task) -> Dict[str, Any]:
        """分析タスクの実行"""
        command = f"analyze {task.description}"
        self.wrapper.send_command(command)
        
        outputs = self.wrapper.read_output(timeout=task.timeout)
        
        return {
            "analysis_type": task.description,
            "result": self._format_output(outputs)
        }
        
    def _execute_generic_task(self, task: Task) -> Dict[str, Any]:
        """汎用タスクの実行"""
        command = task.description
        self.wrapper.send_command(command)
        
        outputs = self.wrapper.read_output(timeout=task.timeout)
        
        return {"output": self._format_output(outputs)}
        
    def _handle_task_request(self, message: AgentMessage):
        """他のエージェントからのタスクリクエストを処理"""
        logger.info(f"Agent {self.agent_id} received task request from {message.sender_id}")
        
        # タスクを作成
        task = Task(**message.payload)
        
        # タスクを実行
        result = self.execute_task(task)
        
        # レスポンスを送信
        self.protocol.send_task_response(message, asdict(result))
        
    def _copy_file_to_container(self, file_path: str):
        """ファイルをコンテナにコピー"""
        if os.path.exists(file_path):
            dest_path = os.path.join(self.config.work_dir, os.path.basename(file_path))
            subprocess.run([
                "cp", file_path, dest_path
            ])
            
    def _parse_review_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """レビュー出力をパース"""
        # TODO: 実際のClaude Code出力形式に合わせて実装
        text = "\n".join([line for _, line in outputs])
        try:
            return json.loads(text)
        except:
            return {"raw_output": text, "issue_count": 0}
            
    def _parse_test_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """テスト生成出力をパース"""
        # TODO: 実際のClaude Code出力形式に合わせて実装
        text = "\n".join([line for _, line in outputs])
        try:
            return json.loads(text)
        except:
            return {"raw_output": text, "test_count": 0}
            
    def _format_output(self, outputs: List[tuple]) -> str:
        """出力をフォーマット"""
        return "\n".join([f"[{stream}] {line}" for stream, line in outputs])
        
    def _process_messages(self):
        """メッセージを処理"""
        while self.is_running:
            try:
                self.protocol.process_messages()
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                
    def _health_check_loop(self):
        """定期的なヘルスチェック"""
        while self.is_running:
            time.sleep(30)  # 30秒ごと
            
            try:
                # 簡単なコマンドを送信してレスポンスを確認
                self.wrapper.send_command("echo health_check")
                outputs = self.wrapper.read_output(timeout=5.0)
                
                if outputs:
                    self.health_check_failed = 0
                else:
                    self.health_check_failed += 1
                    
                if self.health_check_failed > 3:
                    logger.error(f"Agent {self.agent_id} health check failed")
                    # TODO: 自動復旧処理
                    
            except Exception as e:
                logger.error(f"Health check error: {e}")
                self.health_check_failed += 1

class Orchestrator:
    """マルチエージェントオーケストレーター"""
    
    def __init__(self, config_path: Optional[str] = None):
        # 設定読み込み
        self.config = self._load_config(config_path)
        
        # コンポーネント
        self.agents: Dict[str, ClaudeAgent] = {}
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 10)
        )
        self.task_queue: List[Task] = []
        self.results: Dict[str, TaskResult] = {}
        
        # 統計情報
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0
        }
        
        # 通信用ソケット
        self.broker_socket_path = "/tmp/claude_orchestrator.sock"
        self.broker_channel: Optional[UnixSocketChannel] = None
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        default_config = {
            "num_agents": 3,
            "max_workers": 10,
            "task_timeout": 300,
            "log_level": "INFO"
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
                
        return default_config
        
    def start(self):
        """オーケストレーターを起動"""
        logger.info(f"Starting orchestrator with {self.config['num_agents']} agents")
        
        # ブローカーチャネル起動
        self.broker_channel = UnixSocketChannel(
            self.broker_socket_path,
            is_server=True
        )
        
        # エージェントの起動
        for i in range(self.config["num_agents"]):
            agent_id = f"agent_{i:03d}"
            agent = ClaudeAgent(agent_id, self)
            
            try:
                agent.start()
                self.agents[agent_id] = agent
                logger.info(f"Agent {agent_id} added to orchestrator")
                
            except Exception as e:
                logger.error(f"Failed to start agent {agent_id}: {e}")
                
        logger.info(f"Orchestrator started with {len(self.agents)} active agents")
        
        # 統計情報スレッド
        threading.Thread(target=self._stats_reporter, daemon=True).start()
        
    def stop(self):
        """オーケストレーターを停止"""
        logger.info("Stopping orchestrator")
        
        # 全エージェントを停止
        for agent in self.agents.values():
            try:
                agent.stop()
            except Exception as e:
                logger.error(f"Error stopping agent: {e}")
                
        # ブローカーチャネルを閉じる
        if self.broker_channel:
            self.broker_channel.close()
            
        # Executorをシャットダウン
        self.executor.shutdown(wait=True)
        
        # 統計情報を出力
        self._print_final_stats()
        
        logger.info("Orchestrator stopped")
        
    def execute_task(self, task: Task) -> TaskResult:
        """単一タスクを実行"""
        # 優先度キューに追加（簡易実装）
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda t: t.priority, reverse=True)
        
        # 利用可能なエージェントを選択
        agent = self._get_available_agent()
        if not agent:
            return TaskResult(
                task_id=task.task_id,
                agent_id="none",
                status="failed",
                result={},
                error="No available agents"
            )
            
        # タスクを実行
        future = self.executor.submit(agent.execute_task, task)
        
        try:
            result = future.result(timeout=task.timeout)
        except TimeoutError:
            result = TaskResult(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                status="timeout",
                result={},
                error="Task execution timeout"
            )
            
        self._update_stats(result)
        self.results[task.task_id] = result
        
        return result
        
    def execute_parallel_task(self, task: Task) -> List[TaskResult]:
        """並列タスクを実行"""
        if not task.subtasks:
            return [self.execute_task(task)]
            
        futures: List[Future] = []
        results: List[TaskResult] = []
        
        # サブタスクを並列実行
        for i, subtask_def in enumerate(task.subtasks):
            subtask = Task(
                task_id=f"{task.task_id}_sub{i}",
                task_type=subtask_def.get("type", task.task_type),
                description=subtask_def.get("description", ""),
                files=subtask_def.get("files", []),
                priority=task.priority,
                timeout=subtask_def.get("timeout", task.timeout)
            )
            
            agent = self._get_available_agent()
            if agent:
                future = self.executor.submit(agent.execute_task, subtask)
                futures.append((future, agent.agent_id, subtask))
                
        # 結果を収集
        for future, agent_id, subtask in futures:
            try:
                result = future.result(timeout=subtask.timeout)
            except Exception as e:
                result = TaskResult(
                    task_id=subtask.task_id,
                    agent_id=agent_id,
                    status="failed",
                    result={},
                    error=str(e)
                )
                
            results.append(result)
            self._update_stats(result)
            self.results[result.task_id] = result
            
        return results
        
    def _get_available_agent(self) -> Optional[ClaudeAgent]:
        """利用可能なエージェントを取得"""
        # 現在タスクを実行していないエージェントを探す
        for agent in self.agents.values():
            if agent.is_running and agent.current_task is None:
                return agent
                
        # 全てビジーの場合は、最も負荷の低いエージェントを選択
        # （簡易実装：ランダムに選択）
        if self.agents:
            return list(self.agents.values())[0]
            
        return None
        
    def _update_stats(self, result: TaskResult):
        """統計情報を更新"""
        if result.status == "success":
            self.stats["tasks_completed"] += 1
        else:
            self.stats["tasks_failed"] += 1
            
        self.stats["total_execution_time"] += result.execution_time
        
    def _stats_reporter(self):
        """定期的に統計情報を報告"""
        while True:
            time.sleep(60)  # 1分ごと
            
            logger.info(
                f"Stats - Completed: {self.stats['tasks_completed']}, "
                f"Failed: {self.stats['tasks_failed']}, "
                f"Avg time: {self._get_avg_execution_time():.2f}s"
            )
            
    def _get_avg_execution_time(self) -> float:
        """平均実行時間を取得"""
        total_tasks = self.stats["tasks_completed"] + self.stats["tasks_failed"]
        if total_tasks == 0:
            return 0.0
        return self.stats["total_execution_time"] / total_tasks
        
    def _print_final_stats(self):
        """最終統計情報を出力"""
        print("\n=== Final Statistics ===")
        print(f"Total tasks completed: {self.stats['tasks_completed']}")
        print(f"Total tasks failed: {self.stats['tasks_failed']}")
        print(f"Average execution time: {self._get_avg_execution_time():.2f}s")
        print(f"Total execution time: {self.stats['total_execution_time']:.2f}s")
        
    def get_agent_status(self) -> Dict[str, Any]:
        """全エージェントのステータスを取得"""
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                "running": agent.is_running,
                "current_task": agent.current_task.task_id if agent.current_task else None,
                "health_check_failed": agent.health_check_failed
            }
        return status
        
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """タスク結果を取得"""
        return self.results.get(task_id)


# CLIエントリーポイント
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Multi-Agent Orchestrator")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--agents", type=int, help="Number of agents")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # 設定を準備
    config_path = args.config
    
    # オーケストレーター作成
    orchestrator = Orchestrator(config_path)
    
    if args.agents:
        orchestrator.config["num_agents"] = args.agents
        
    try:
        # 起動
        orchestrator.start()
        
        # 簡単なREPL
        print("\nClaude Code Orchestrator started")
        print("Commands: status, task <type> <description>, quit")
        
        while True:
            try:
                cmd = input("\n> ").strip()
                
                if cmd == "quit":
                    break
                elif cmd == "status":
                    status = orchestrator.get_agent_status()
                    print(json.dumps(status, indent=2))
                elif cmd.startswith("task"):
                    parts = cmd.split(maxsplit=2)
                    if len(parts) >= 3:
                        task_type = parts[1]
                        description = parts[2]
                        
                        task = Task(
                            task_type=task_type,
                            description=description
                        )
                        
                        result = orchestrator.execute_task(task)
                        print(f"Task {result.task_id}: {result.status}")
                        
            except KeyboardInterrupt:
                break
                
    finally:
        orchestrator.stop()


if __name__ == "__main__":
    main()
```

### 3.4 追加ファイル

#### src/__init__.py
```python
# Empty file to make src a Python package
```

#### config/config.yaml
```yaml
# Orchestrator configuration
orchestrator:
  num_agents: 3
  max_workers: 10
  task_timeout: 300
  log_level: INFO

# Agent configuration
agent:
  container_memory: "2g"
  container_cpu: "1.0"
  health_check_interval: 30
  startup_timeout: 60

# Communication settings
communication:
  socket_path: "/tmp/claude_orchestrator.sock"
  message_timeout: 5.0
  retry_count: 3

# Task queue settings
task_queue:
  max_size: 1000
  priority_levels: 10
```

## 4. テストファイル

### tests/test_integration.py
```python
import pytest
import time
import os
from src.orchestrator import Orchestrator, Task
from src.claude_code_wrapper import AgentConfig, ClaudeCodeWrapper

def test_orchestrator_startup():
    """オーケストレーターの起動テスト"""
    orchestrator = Orchestrator()
    orchestrator.config["num_agents"] = 1
    
    orchestrator.start()
    time.sleep(2)
    
    status = orchestrator.get_agent_status()
    assert len(status) == 1
    assert list(status.values())[0]["running"] == True
    
    orchestrator.stop()

def test_simple_task_execution():
    """簡単なタスク実行テスト"""
    orchestrator = Orchestrator()
    orchestrator.config["num_agents"] = 1
    
    orchestrator.start()
    time.sleep(2)
    
    task = Task(
        task_type="generic",
        description="echo 'Hello, World!'"
    )
    
    result = orchestrator.execute_task(task)
    
    assert result.status in ["success", "failed"]
    assert result.task_id == task.task_id
    
    orchestrator.stop()

@pytest.mark.skipif(
    not os.path.exists("/usr/bin/podman"),
    reason="Podman not installed"
)
def test_container_lifecycle():
    """コンテナライフサイクルテスト"""
    config = AgentConfig(
        agent_id="test_001",
        container_name="test_container_001",
        work_dir="/tmp/test_workspace"
    )
    
    with ClaudeCodeWrapper(config) as wrapper:
        # コンテナが作成されたことを確認
        result = wrapper.exec_in_container("echo 'Container is running'")
        assert result.exit_code == 0
        assert "Container is running" in result.stdout
```

### tests/run_tests.sh
```bash
#!/bin/bash
cd $(dirname $0)/..
source venv/bin/activate

# Unit tests
echo "Running unit tests..."
python -m pytest tests/ -v --tb=short

# Coverage report
echo "Generating coverage report..."
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term
```

## 5. 実行用スクリプト

### examples/example_usage.py
```python
#!/usr/bin/env python3
"""
Example usage of Claude Code Orchestrator
"""

import time
from src.orchestrator import Orchestrator, Task

def main():
    # オーケストレーターを作成
    orchestrator = Orchestrator()
    
    # 2つのエージェントで起動
    orchestrator.config["num_agents"] = 2
    orchestrator.start()
    
    print("Orchestrator started with 2 agents")
    time.sleep(3)
    
    # タスク1: 単一ファイルのレビュー
    print("\n--- Task 1: Single file review ---")
    task1 = Task(
        task_type="code_review",
        description="Review Python file for style and bugs",
        files=["examples/sample_code.py"]
    )
    
    result1 = orchestrator.execute_task(task1)
    print(f"Result: {result1.status}")
    print(f"Execution time: {result1.execution_time:.2f}s")
    
    # タスク2: 並列レビュー
    print("\n--- Task 2: Parallel review ---")
    task2 = Task(
        task_type="code_review",
        description="Review multiple files in parallel",
        parallel=True,
        subtasks=[
            {
                "type": "code_review",
                "description": "Review frontend code",
                "files": ["frontend/app.js", "frontend/utils.js"]
            },
            {
                "type": "code_review",
                "description": "Review backend code",
                "files": ["backend/server.py", "backend/database.py"]
            }
        ]
    )
    
    results2 = orchestrator.execute_parallel_task(task2)
    print(f"Completed {len(results2)} subtasks")
    for result in results2:
        print(f"  - {result.task_id}: {result.status}")
        
    # エージェントステータス確認
    print("\n--- Agent Status ---")
    status = orchestrator.get_agent_status()
    for agent_id, info in status.items():
        print(f"{agent_id}: running={info['running']}, task={info['current_task']}")
        
    # クリーンアップ
    orchestrator.stop()
    print("\nOrchestrator stopped")

if __name__ == "__main__":
    main()
```

### examples/sample_code.py
```python
# Sample code for testing
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total

def main():
    numbers = [1, 2, 3, 4, 5]
    result = calculate_sum(numbers)
    print(f"Sum: {result}")

if __name__ == "__main__":
    main()
```

## 6. 開発タスクリスト

### 優先度1: Claude Code統合
1. Claude Code CLIの実際のインターフェース調査
2. ヘッドレスモードのコマンド形式確認
3. レスポンスフォーマットの解析
4. エラーパターンの把握

### 優先度2: エラーハンドリング
1. プロセスクラッシュ時の自動復旧
2. ネットワークエラーのリトライ
3. タイムアウト処理の改善
4. デッドロック検出と回避

### 優先度3: パフォーマンス最適化
1. リソース使用量のモニタリング
2. 並列度の動的調整
3. タスクスケジューリングの最適化
4. キャッシング機構の実装

### 優先度4: 本番対応
1. Kubernetes対応
2. 分散デプロイメント
3. ログ集約とモニタリング
4. セキュリティ強化

## 7. Claude Codeでの作業開始コマンド

```bash
# プロジェクトディレクトリで Claude Code を起動
cd ~/claude-code-orchestrator
claude-code

# Claude Code内で実行するコマンド例
analyze the project structure and understand the orchestrator architecture
investigate actual claude-code CLI interface and update the wrapper
implement proper error handling and retry logic
create comprehensive test suite
run tests and fix any issues
```

## 8. トラブルシューティング

### Podman権限エラー
```bash
# rootlessモード設定確認
podman info | grep rootless

# 一時的な解決策
sudo podman ...
```

### ソケット通信エラー
```bash
# ソケットファイル削除
rm -f /tmp/claude_*.sock

# 権限確認
ls -la /tmp/ | grep sock
```

### コンテナリソース不足
```bash
# リソース制限の調整
podman update --memory 4g --cpus 2 <container_name>
```

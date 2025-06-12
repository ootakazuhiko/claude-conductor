#!/usr/bin/env python3
"""
Claude Agent - Container wrapper and agent management
"""

import subprocess
import threading
import queue
import time
import json
import os
import signal
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import logging

from .protocol import Agent2AgentProtocol, UnixSocketChannel, AgentMessage, MessageType

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

@dataclass
class Task:
    """タスク定義"""
    task_id: str
    task_type: str = "generic"
    description: str = ""
    files: List[str] = None
    parallel: bool = False
    subtasks: Optional[List[Dict[str, Any]]] = None
    priority: int = 5  # 1-10, 10が最高
    timeout: float = 300.0  # 5分
    
    def __post_init__(self):
        if self.files is None:
            self.files = []

@dataclass
class TaskResult:
    """タスク実行結果"""
    task_id: str
    agent_id: str
    status: str  # "success", "failed", "timeout", "partial"
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

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
            "apt-get install -y curl git python3 python3-pip nodejs npm",
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
        return {"type": "review", "issues": random.randint(0, 5), "suggestions": ["Use type hints", "Add docstrings"]}
    elif cmd.startswith("refactor"):
        return {"type": "refactor", "changes": random.randint(1, 3), "files_modified": ["main.py"]}
    elif cmd.startswith("generate-tests"):
        return {"type": "test_generation", "test_count": random.randint(3, 8), "coverage": "85%"}
    elif cmd.startswith("analyze"):
        return {"type": "analysis", "complexity": "moderate", "maintainability": "good"}
    else:
        return {"type": "generic", "status": "completed", "message": f"Processed: {cmd}"}

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
            subprocess.run(["podman", "stop", self.config.container_name], capture_output=True)
            subprocess.run(["podman", "rm", self.config.container_name], capture_output=True)
            logger.info(f"Container {self.config.container_name} cleaned up")
            
    def __enter__(self):
        self.setup_container()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.cleanup_container()

class ClaudeAgent:
    """Claude Codeエージェント"""
    
    def __init__(self, agent_id: str, orchestrator_socket_path: str = "/tmp/claude_orchestrator.sock"):
        self.agent_id = agent_id
        self.orchestrator_socket_path = orchestrator_socket_path
        
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
            try:
                self.channel = UnixSocketChannel(self.orchestrator_socket_path, is_server=False)
                self.protocol = Agent2AgentProtocol(self.agent_id, self.channel)
                
                # メッセージハンドラー登録
                self.protocol.register_handler(
                    MessageType.TASK_REQUEST,
                    self._handle_task_request
                )
            except Exception as e:
                logger.warning(f"Failed to connect to orchestrator: {e}")
                # オーケストレーターに接続できない場合はスタンドアローンモードで動作
                self.channel = None
                self.protocol = None
            
            # Claude Code起動
            self.wrapper.start_claude_code(headless=True)
            self.is_running = True
            
            # メッセージ処理スレッド
            if self.protocol:
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
            
            # 結果をパース
            review_result = self._parse_review_output(outputs)
            results[file_path] = review_result
            total_issues += review_result.get("issues", 0)
            
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
        
        # 結果を収集
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
        task_data = message.payload
        task = Task(
            task_id=task_data.get("task_id", "unknown"),
            task_type=task_data.get("task_type", "generic"),
            description=task_data.get("description", ""),
            files=task_data.get("files", []),
            parallel=task_data.get("parallel", False),
            subtasks=task_data.get("subtasks"),
            priority=task_data.get("priority", 5),
            timeout=task_data.get("timeout", 300.0)
        )
        
        # タスクを実行
        result = self.execute_task(task)
        
        # レスポンスを送信
        if self.protocol:
            self.protocol.send_task_response(message, asdict(result))
        
    def _copy_file_to_container(self, file_path: str):
        """ファイルをコンテナにコピー"""
        if os.path.exists(file_path):
            dest_path = os.path.join(self.config.work_dir, os.path.basename(file_path))
            try:
                subprocess.run([
                    "cp", file_path, dest_path
                ], check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to copy file {file_path}: {e}")
            
    def _parse_review_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """レビュー出力をパース"""
        text = "\n".join([line for _, line in outputs])
        try:
            return json.loads(text)
        except:
            return {"raw_output": text, "issues": 0}
            
    def _parse_test_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """テスト生成出力をパース"""
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
                if self.protocol:
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
                if self.wrapper and self.wrapper.is_running:
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
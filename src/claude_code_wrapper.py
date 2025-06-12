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
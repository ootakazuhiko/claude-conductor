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
from typing import Optional, Dict, Any, List, Tuple
import logging
import asyncio

from .protocol import Agent2AgentProtocol, UnixSocketChannel, AgentMessage, MessageType
from .workspace_isolation import WorkspaceIsolationManager, WorkspaceContainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Agent configuration"""
    agent_id: str
    container_name: str
    work_dir: str
    podman_image: str = "ubuntu:22.04"
    memory_limit: str = "2g"
    cpu_limit: str = "1.0"
    use_isolated_workspace: bool = False
    workspace_environment: str = "minimal"
    enable_snapshots: bool = True
    
@dataclass
class CommandResult:
    """Command execution result"""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    timestamp: float

@dataclass
class Task:
    """Task definition"""
    task_id: str
    task_type: str = "generic"
    description: str = ""
    files: List[str] = None
    parallel: bool = False
    subtasks: Optional[List[Dict[str, Any]]] = None
    priority: int = 5  # 1-10, 10 is highest
    timeout: float = 300.0  # 5 minutes
    
    def __post_init__(self):
        if self.files is None:
            self.files = []

@dataclass
class TaskResult:
    """Task execution result"""
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
    """Wrapper for Claude Code processes"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.container_id: Optional[str] = None
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self.is_running = False
        
    def setup_container(self) -> str:
        """Set up Podman container"""
        logger.info(f"Setting up container for agent {self.config.agent_id}")
        
        # Clean up existing container
        self._cleanup_existing_container()
        
        # Container creation command
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
            
            # Install basic tools
            self._install_base_tools()
            
            # Install Claude Code
            self._install_claude_code()
            
            return self.container_id
            
        except Exception as e:
            logger.error(f"Container setup failed: {e}")
            raise
            
    def _cleanup_existing_container(self):
        """Clean up existing container"""
        subprocess.run(
            ["podman", "rm", "-f", self.config.container_name],
            capture_output=True
        )
        
    def _install_base_tools(self):
        """Install basic tools"""
        commands = [
            "apt-get update",
            "apt-get install -y curl git python3 python3-pip nodejs npm",
        ]
        
        for cmd in commands:
            result = self.exec_in_container(cmd)
            if result.exit_code != 0:
                logger.warning(f"Command failed: {cmd}")
                
    def _install_claude_code(self):
        """Set up Claude Code in container"""
        # TODO: Replace with actual Claude Code installation procedure
        # Currently placing dummy script
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
        
        # Create dummy script
        self.exec_in_container(f"cat > /usr/local/bin/claude-code << 'EOF'\n{dummy_script}\nEOF")
        self.exec_in_container("chmod +x /usr/local/bin/claude-code")
            
    def exec_in_container(self, command: str) -> CommandResult:
        """Execute command in container"""
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
        """Start Claude Code process"""
        logger.info(f"Starting Claude Code for agent {self.config.agent_id}")
        
        # Claude Code execution command
        claude_cmd = "claude-code"
        if headless:
            claude_cmd += " --headless"
            
        # Start process
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
        
        # Start output reading threads
        self._start_output_readers()
        
    def _start_output_readers(self):
        """Start stdout/stderr reading threads"""
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
        """Send command to Claude Code"""
        if not self.process or not self.is_running:
            raise Exception("Claude Code is not running")
            
        logger.info(f"Sending command: {command}")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        
    def read_output(self, timeout: float = 1.0) -> List[tuple]:
        """Read output"""
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
        """Stop process"""
        logger.info(f"Stopping agent {self.config.agent_id}")
        self.is_running = False
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                
    def cleanup_container(self):
        """Clean up container"""
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
    """Claude Code agent"""
    
    def __init__(self, agent_id: str, orchestrator_socket_path: str = "/tmp/claude_orchestrator.sock",
                 config: Optional[Dict[str, Any]] = None):
        self.agent_id = agent_id
        self.orchestrator_socket_path = orchestrator_socket_path
        self.full_config = config or {}
        
        # Check isolated workspace configuration
        isolated_config = self.full_config.get('isolated_workspace', {})
        use_isolation = isolated_config.get('enabled', False)
        
        # Podman container configuration
        self.config = AgentConfig(
            agent_id=agent_id,
            container_name=f"claude_agent_{agent_id}",
            work_dir=f"/tmp/claude_workspace_{agent_id}",
            use_isolated_workspace=use_isolation,
            workspace_environment=isolated_config.get('agent_containers', {}).get('base_image', 'minimal'),
            enable_snapshots=isolated_config.get('mode', 'sandbox') == 'sandbox'
        )
        
        # Components
        self.wrapper: Optional[ClaudeCodeWrapper] = None
        self.protocol: Optional[Agent2AgentProtocol] = None
        self.channel: Optional[UnixSocketChannel] = None
        self.workspace_manager: Optional[WorkspaceIsolationManager] = None
        self.isolated_container: Optional[WorkspaceContainer] = None
        
        # State
        self.is_running = False
        self.current_task: Optional[Task] = None
        self.health_check_failed = 0
        
    def start(self):
        """Start agent"""
        logger.info(f"Starting agent {self.agent_id}")
        
        try:
            # Set up isolated workspace
            if self.config.use_isolated_workspace:
                asyncio.run(self._setup_isolated_workspace())
            else:
                # Create normal workspace
                os.makedirs(self.config.work_dir, exist_ok=True)
                
                # Initialize wrapper
                self.wrapper = ClaudeCodeWrapper(self.config)
                self.wrapper.setup_container()
            
            # Initialize communication channel
            try:
                self.channel = UnixSocketChannel(self.orchestrator_socket_path, is_server=False)
                self.protocol = Agent2AgentProtocol(self.agent_id, self.channel)
                
                # Register message handler
                self.protocol.register_handler(
                    MessageType.TASK_REQUEST,
                    self._handle_task_request
                )
            except Exception as e:
                logger.warning(f"Failed to connect to orchestrator: {e}")
                # Run in standalone mode if unable to connect to orchestrator
                self.channel = None
                self.protocol = None
            
            # Start Claude Code
            self.wrapper.start_claude_code(headless=True)
            self.is_running = True
            
            # Message processing thread
            if self.protocol:
                threading.Thread(target=self._process_messages, daemon=True).start()
            
            # Health check thread
            threading.Thread(target=self._health_check_loop, daemon=True).start()
            
            logger.info(f"Agent {self.agent_id} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start agent {self.agent_id}: {e}")
            raise
            
    def stop(self):
        """Stop agent"""
        logger.info(f"Stopping agent {self.agent_id}")
        self.is_running = False
        
        if self.config.use_isolated_workspace and self.workspace_manager:
            asyncio.run(self._cleanup_isolated_workspace())
        else:
            if self.wrapper:
                self.wrapper.stop()
                self.wrapper.cleanup_container()
            
        if self.channel:
            self.channel.close()
            
    def execute_task(self, task: Task) -> TaskResult:
        """Execute task"""
        self.current_task = task
        start_time = time.time()
        
        try:
            logger.info(f"Agent {self.agent_id} executing task {task.task_id}")
            
            # Process according to task type
            if task.task_type == "code_review":
                result = self._execute_code_review(task)
            elif task.task_type == "refactor":
                result = self._execute_refactor(task)
            elif task.task_type == "test_generation":
                result = self._execute_test_generation(task)
            elif task.task_type == "analysis":
                result = self._execute_analysis(task)
            elif task.task_type == "isolated_execution":
                result = self._execute_isolated_task(task)
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
        """Execute code review task"""
        results = {}
        total_issues = 0
        
        for file_path in task.files:
            # Copy file to container
            self._copy_file_to_container(file_path)
            
            # Send review command
            command = f"review {os.path.basename(file_path)}"
            self.wrapper.send_command(command)
            
            # Collect results
            outputs = self.wrapper.read_output(timeout=10.0)
            
            # Parse results
            review_result = self._parse_review_output(outputs)
            results[file_path] = review_result
            total_issues += review_result.get("issues", 0)
            
        return {
            "files_reviewed": len(task.files),
            "total_issues": total_issues,
            "details": results
        }
        
    def _execute_refactor(self, task: Task) -> Dict[str, Any]:
        """Execute refactoring task"""
        # Copy files to container
        for file_path in task.files:
            self._copy_file_to_container(file_path)
            
        # Refactoring command
        command = f"refactor {' '.join([os.path.basename(f) for f in task.files])}"
        if task.description:
            command += f" --description '{task.description}'"
            
        self.wrapper.send_command(command)
        
        # Collect results
        outputs = self.wrapper.read_output(timeout=30.0)
        
        return {
            "refactored": True,
            "files_affected": len(task.files),
            "output": self._format_output(outputs)
        }
        
    def _execute_test_generation(self, task: Task) -> Dict[str, Any]:
        """Execute test generation task"""
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
        """Execute analysis task"""
        command = f"analyze {task.description}"
        self.wrapper.send_command(command)
        
        outputs = self.wrapper.read_output(timeout=task.timeout)
        
        return {
            "analysis_type": task.description,
            "result": self._format_output(outputs)
        }
        
    def _execute_generic_task(self, task: Task) -> Dict[str, Any]:
        """Execute generic task"""
        command = task.description
        self.wrapper.send_command(command)
        
        outputs = self.wrapper.read_output(timeout=task.timeout)
        
        return {"output": self._format_output(outputs)}
        
    def _handle_task_request(self, message: AgentMessage):
        """Handle task request from other agents"""
        logger.info(f"Agent {self.agent_id} received task request from {message.sender_id}")
        
        # Create task
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
        
        # Execute task
        result = self.execute_task(task)
        
        # Send response
        if self.protocol:
            self.protocol.send_task_response(message, asdict(result))
        
    def _copy_file_to_container(self, file_path: str):
        """Copy file to container"""
        if os.path.exists(file_path):
            dest_path = os.path.join(self.config.work_dir, os.path.basename(file_path))
            try:
                subprocess.run([
                    "cp", file_path, dest_path
                ], check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to copy file {file_path}: {e}")
            
    def _parse_review_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """Parse review output"""
        text = "\n".join([line for _, line in outputs])
        try:
            return json.loads(text)
        except:
            return {"raw_output": text, "issues": 0}
            
    def _parse_test_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """Parse test generation output"""
        text = "\n".join([line for _, line in outputs])
        try:
            return json.loads(text)
        except:
            return {"raw_output": text, "test_count": 0}
            
    def _format_output(self, outputs: List[tuple]) -> str:
        """Format output"""
        return "\n".join([f"[{stream}] {line}" for stream, line in outputs])
        
    def _process_messages(self):
        """Process messages"""
        while self.is_running:
            try:
                if self.protocol:
                    self.protocol.process_messages()
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                
    def _health_check_loop(self):
        """Periodic health check"""
        while self.is_running:
            time.sleep(30)  # Every 30 seconds
            
            try:
                # Send simple command and check response
                if self.wrapper and self.wrapper.is_running:
                    self.wrapper.send_command("echo health_check")
                    outputs = self.wrapper.read_output(timeout=5.0)
                    
                    if outputs:
                        self.health_check_failed = 0
                    else:
                        self.health_check_failed += 1
                        
                    if self.health_check_failed > 3:
                        logger.error(f"Agent {self.agent_id} health check failed")
                        # TODO: Auto-recovery process
                        
            except Exception as e:
                logger.error(f"Health check error: {e}")
                self.health_check_failed += 1
    
    async def _setup_isolated_workspace(self):
        """Set up isolated workspace"""
        logger.info(f"Setting up isolated workspace for agent {self.agent_id}")
        
        # Initialize workspace manager
        self.workspace_manager = WorkspaceIsolationManager(self.full_config)
        
        # Determine environment name
        env_name = self.config.workspace_environment
        if self.current_task and hasattr(self.current_task, 'environment'):
            env_name = self.current_task.environment
        
        # Create workspace container
        self.isolated_container = await self.workspace_manager.create_workspace(
            self.agent_id, env_name
        )
        
        # Create snapshot (if enabled)
        if self.config.enable_snapshots:
            await self.workspace_manager.create_snapshot(
                self.agent_id, "initial"
            )
        
        logger.info(f"Isolated workspace created: {self.isolated_container.container_id}")
    
    async def _cleanup_isolated_workspace(self):
        """Clean up isolated workspace"""
        if self.workspace_manager and self.isolated_container:
            # Handle task failure case
            if self.current_task and self.config.enable_snapshots:
                if self.full_config.get('task_execution', {}).get('isolation', {}).get('preserve_on_error', True):
                    logger.info(f"Preserving workspace for debugging: {self.agent_id}")
                    return
            
            # Cleanup
            await self.workspace_manager.cleanup_workspace(
                self.agent_id, 
                preserve_volumes=False
            )
    
    async def execute_in_isolated_workspace(self, command: List[str]) -> Tuple[int, str, str]:
        """Execute command in isolated workspace"""
        if not self.workspace_manager or not self.isolated_container:
            raise RuntimeError("Isolated workspace not initialized")
        
        return await self.workspace_manager.execute_in_workspace(
            self.agent_id, command
        )
    
    def _execute_isolated_task(self, task: Task) -> Dict[str, Any]:
        """Execute task in isolated workspace"""
        if not self.config.use_isolated_workspace:
            return self._execute_generic_task(task)
        
        try:
            # Pre-task snapshot
            if self.config.enable_snapshots:
                asyncio.run(self.workspace_manager.create_snapshot(
                    self.agent_id, f"pre-task-{task.task_id}"
                ))
            
            # Execute commands
            commands = []
            if hasattr(task, 'commands'):
                commands = task.commands
            else:
                commands = [task.description]
            
            results = []
            for cmd in commands:
                if isinstance(cmd, str):
                    cmd_list = cmd.split()
                else:
                    cmd_list = cmd
                
                exit_code, stdout, stderr = asyncio.run(
                    self.execute_in_isolated_workspace(cmd_list)
                )
                
                results.append({
                    'command': ' '.join(cmd_list),
                    'exit_code': exit_code,
                    'stdout': stdout,
                    'stderr': stderr
                })
                
                if exit_code != 0:
                    # Handle error case
                    if self.config.enable_snapshots and \
                       self.full_config.get('task_execution', {}).get('isolation', {}).get('restore_on_error', True):
                        asyncio.run(self.workspace_manager.restore_snapshot(
                            self.agent_id, f"pre-task-{task.task_id}"
                        ))
                    break
            
            # Post-task snapshot (on success)
            if all(r['exit_code'] == 0 for r in results) and self.config.enable_snapshots:
                asyncio.run(self.workspace_manager.create_snapshot(
                    self.agent_id, f"post-task-{task.task_id}"
                ))
            
            # Get workspace information
            workspace_info = self.workspace_manager.get_workspace_info(self.agent_id)
            
            return {
                'results': results,
                'workspace_info': workspace_info,
                'success': all(r['exit_code'] == 0 for r in results)
            }
            
        except Exception as e:
            logger.error(f"Failed to execute isolated task: {e}")
            return {
                'error': str(e),
                'success': False
            }
#!/usr/bin/env python3
"""
Workspace Isolation Module for Claude Conductor
Provides Podman-based isolated development environments for agents
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .utils import get_timestamp

logger = logging.getLogger(__name__)


@dataclass
class ContainerConfig:
    """Configuration for an isolated container workspace"""
    name: str
    image: str
    agent_id: str
    memory_limit: str = "2g"
    cpu_limit: str = "1.0"
    volumes: Dict[str, str] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    capabilities_add: List[str] = field(default_factory=list)
    capabilities_drop: List[str] = field(default_factory=list)
    network_mode: str = "bridge"
    privileged: bool = False
    user: Optional[str] = None


@dataclass
class WorkspaceContainer:
    """Represents an isolated workspace container"""
    container_id: str
    config: ContainerConfig
    created_at: datetime
    status: str = "created"
    workspace_path: str = ""
    ports: Dict[str, int] = field(default_factory=dict)


class WorkspaceIsolationManager:
    """Manages isolated workspaces for agents using Podman"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.isolated_config = config.get('isolated_workspace', {})
        self.podman_config = config.get('podman_config', {})
        self.containers: Dict[str, WorkspaceContainer] = {}
        self.workspace_base = Path(config['storage']['isolated_workspaces_path']).expanduser()
        self.workspace_base.mkdir(parents=True, exist_ok=True)
        
        # Verify Podman is available
        self._verify_podman()
        
        # Initialize network if needed
        if self.isolated_config.get('enabled', False):
            self._init_network()
    
    def _verify_podman(self) -> None:
        """Verify Podman is installed and accessible"""
        try:
            result = subprocess.run(['podman', 'version'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError("Podman not available")
            logger.info(f"Podman version: {result.stdout.split()[2]}")
        except FileNotFoundError:
            raise RuntimeError("Podman not found. Please install Podman.")
    
    def _init_network(self) -> None:
        """Initialize Podman network for isolated containers"""
        network_config = self.podman_config.get('network', {})
        network_name = network_config.get('name', 'claude-dev-net')
        
        # Check if network exists
        result = subprocess.run(['podman', 'network', 'ls', '--format', 'json'],
                              capture_output=True, text=True)
        networks = json.loads(result.stdout) if result.stdout else []
        
        if not any(net.get('Name') == network_name for net in networks):
            # Create network
            cmd = [
                'podman', 'network', 'create',
                '--subnet', network_config.get('subnet', '10.89.0.0/24'),
                network_name
            ]
            subprocess.run(cmd, check=True)
            logger.info(f"Created Podman network: {network_name}")
    
    async def create_workspace(self, agent_id: str, 
                             environment: str = "minimal") -> WorkspaceContainer:
        """Create an isolated workspace container for an agent"""
        # Get environment configuration
        env_config = self._get_environment_config(environment)
        
        # Create workspace directory
        workspace_dir = self.workspace_base / f"agent_{agent_id}"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate container name
        container_name = f"claude-agent-{agent_id}-{uuid.uuid4().hex[:8]}"
        
        # Prepare volumes
        volumes = {
            str(workspace_dir): "/workspace",
            str(workspace_dir / "cache"): "/cache"
        }
        
        # Add environment-specific volumes
        if 'volumes' in env_config:
            for vol in env_config['volumes']:
                src, dst = vol.split(':')
                volumes[str(workspace_dir / src)] = dst
        
        # Create container config
        config = ContainerConfig(
            name=container_name,
            image=env_config.get('image', 'ubuntu:22.04'),
            agent_id=agent_id,
            memory_limit=self.isolated_config.get('agent_containers', {})
                                            .get('resources', {})
                                            .get('limits', {})
                                            .get('memory', '2Gi'),
            cpu_limit=self.isolated_config.get('agent_containers', {})
                                         .get('resources', {})
                                         .get('limits', {})
                                         .get('cpu', '1.0'),
            volumes=volumes,
            environment={
                'AGENT_ID': agent_id,
                'WORKSPACE': '/workspace',
                'CLAUDE_ENV': environment
            },
            capabilities_add=['SYS_PTRACE'],  # For debugging
            network_mode=self.podman_config.get('network', {}).get('name', 'bridge')
        )
        
        # Create and start container
        container_id = await self._create_container(config, env_config)
        
        # Initialize development environment
        await self._init_dev_environment(container_id, env_config)
        
        # Create workspace container object
        workspace = WorkspaceContainer(
            container_id=container_id,
            config=config,
            created_at=datetime.now(),
            status="running",
            workspace_path=str(workspace_dir)
        )
        
        self.containers[agent_id] = workspace
        logger.info(f"Created isolated workspace for agent {agent_id}: {container_id}")
        
        return workspace
    
    def _get_environment_config(self, environment: str) -> Dict[str, Any]:
        """Get configuration for a specific environment"""
        # Check predefined environments
        for env in self.isolated_config.get('agent_containers', {}).get('environments', []):
            if env['name'] == environment:
                return env
        
        # Check presets
        for preset in self.config.get('dev_environments', {}).get('presets', []):
            if preset['name'] == environment:
                return preset
        
        # Default minimal environment
        return {
            'name': 'minimal',
            'image': 'alpine:latest',
            'packages': ['git', 'curl']
        }
    
    async def _create_container(self, config: ContainerConfig, 
                               env_config: Dict[str, Any]) -> str:
        """Create a Podman container"""
        # Build custom image if dockerfile is provided
        if 'dockerfile' in env_config:
            image_name = await self._build_custom_image(config.agent_id, env_config)
            config.image = image_name
        
        # Prepare Podman run command
        cmd = ['podman', 'run', '-d', '--name', config.name]
        
        # Add resource limits
        cmd.extend(['--memory', config.memory_limit])
        cmd.extend(['--cpus', config.cpu_limit])
        
        # Add volumes
        for src, dst in config.volumes.items():
            Path(src).mkdir(parents=True, exist_ok=True)
            cmd.extend(['-v', f"{src}:{dst}:Z"])
        
        # Add environment variables
        for key, value in config.environment.items():
            cmd.extend(['-e', f"{key}={value}"])
        
        # Add capabilities
        for cap in config.capabilities_add:
            cmd.extend(['--cap-add', cap])
        for cap in config.capabilities_drop:
            cmd.extend(['--cap-drop', cap])
        
        # Add network
        cmd.extend(['--network', config.network_mode])
        
        # Add security options
        if self.podman_config.get('security', {}).get('userns'):
            cmd.extend(['--userns', self.podman_config['security']['userns']])
        
        # Add work directory
        cmd.extend(['-w', '/workspace'])
        
        # Add image and command
        cmd.append(config.image)
        cmd.extend(['sleep', 'infinity'])  # Keep container running
        
        # Run container
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create container: {stderr.decode()}")
        
        container_id = stdout.decode().strip()
        return container_id
    
    async def _build_custom_image(self, agent_id: str, 
                                 env_config: Dict[str, Any]) -> str:
        """Build a custom Docker image from Dockerfile content"""
        image_name = f"claude-env-{env_config['name']}-{agent_id}"
        
        # Create temporary directory for build context
        with tempfile.TemporaryDirectory() as build_dir:
            # Write Dockerfile
            dockerfile_path = Path(build_dir) / "Dockerfile"
            dockerfile_path.write_text(env_config['dockerfile'])
            
            # Build image
            cmd = ['podman', 'build', '-t', image_name, build_dir]
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to build image: {stderr.decode()}")
            
            logger.info(f"Built custom image: {image_name}")
            return image_name
    
    async def _init_dev_environment(self, container_id: str, 
                                   env_config: Dict[str, Any]) -> None:
        """Initialize development environment in container"""
        # Install packages if specified
        packages = env_config.get('packages', [])
        if packages:
            # Detect package manager
            image = env_config.get('image', '')
            if 'alpine' in image:
                pkg_cmd = ['apk', 'add', '--no-cache'] + packages
            elif 'ubuntu' in image or 'debian' in image:
                pkg_cmd = ['apt-get', 'update', '&&', 'apt-get', 'install', '-y'] + packages
            elif 'python' in image:
                pkg_cmd = ['pip', 'install'] + packages
            elif 'node' in image:
                pkg_cmd = ['npm', 'install', '-g'] + packages
            else:
                logger.warning(f"Unknown image type: {image}, skipping package installation")
                return
            
            # Execute package installation
            exec_cmd = ['podman', 'exec', container_id, 'sh', '-c', ' '.join(pkg_cmd)]
            result = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(f"Failed to install packages: {stderr.decode()}")
            else:
                logger.info(f"Installed packages in container {container_id}")
    
    async def execute_in_workspace(self, agent_id: str, 
                                  command: List[str]) -> Tuple[int, str, str]:
        """Execute a command in an agent's isolated workspace"""
        if agent_id not in self.containers:
            raise ValueError(f"No workspace found for agent {agent_id}")
        
        container = self.containers[agent_id]
        
        # Execute command in container
        exec_cmd = ['podman', 'exec', container.container_id] + command
        result = await asyncio.create_subprocess_exec(
            *exec_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        return result.returncode, stdout.decode(), stderr.decode()
    
    async def create_snapshot(self, agent_id: str, 
                            snapshot_name: Optional[str] = None) -> str:
        """Create a snapshot of the current workspace state"""
        if agent_id not in self.containers:
            raise ValueError(f"No workspace found for agent {agent_id}")
        
        container = self.containers[agent_id]
        snapshot_name = snapshot_name or f"snapshot-{get_timestamp()}"
        
        # Commit container to create image
        cmd = ['podman', 'commit', container.container_id, 
               f"{container.config.name}:{snapshot_name}"]
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create snapshot: {stderr.decode()}")
        
        logger.info(f"Created snapshot for agent {agent_id}: {snapshot_name}")
        return snapshot_name
    
    async def restore_snapshot(self, agent_id: str, snapshot_name: str) -> None:
        """Restore a workspace from a snapshot"""
        if agent_id not in self.containers:
            raise ValueError(f"No workspace found for agent {agent_id}")
        
        old_container = self.containers[agent_id]
        
        # Stop and remove current container
        await self.cleanup_workspace(agent_id, preserve_volumes=True)
        
        # Create new container from snapshot
        config = old_container.config
        config.image = f"{config.name}:{snapshot_name}"
        
        # Recreate container
        container_id = await self._create_container(config, {})
        
        # Update workspace container
        workspace = WorkspaceContainer(
            container_id=container_id,
            config=config,
            created_at=datetime.now(),
            status="running",
            workspace_path=old_container.workspace_path
        )
        
        self.containers[agent_id] = workspace
        logger.info(f"Restored workspace for agent {agent_id} from snapshot {snapshot_name}")
    
    async def cleanup_workspace(self, agent_id: str, 
                              preserve_volumes: bool = False) -> None:
        """Clean up an agent's isolated workspace"""
        if agent_id not in self.containers:
            return
        
        container = self.containers[agent_id]
        
        # Stop container
        stop_cmd = ['podman', 'stop', container.container_id]
        await asyncio.create_subprocess_exec(*stop_cmd)
        
        # Remove container
        rm_cmd = ['podman', 'rm', container.container_id]
        await asyncio.create_subprocess_exec(*rm_cmd)
        
        # Clean up volumes if requested
        if not preserve_volumes:
            workspace_path = Path(container.workspace_path)
            if workspace_path.exists():
                shutil.rmtree(workspace_path)
        
        del self.containers[agent_id]
        logger.info(f"Cleaned up workspace for agent {agent_id}")
    
    async def cleanup_old_containers(self, max_age_hours: int = 24) -> None:
        """Clean up containers older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for agent_id, container in list(self.containers.items()):
            if container.created_at < cutoff_time:
                await self.cleanup_workspace(agent_id)
                logger.info(f"Cleaned up old container for agent {agent_id}")
    
    def get_workspace_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get information about an agent's workspace"""
        if agent_id not in self.containers:
            return None
        
        container = self.containers[agent_id]
        
        # Get container stats
        stats_cmd = ['podman', 'stats', '--no-stream', '--format', 'json', 
                     container.container_id]
        result = subprocess.run(stats_cmd, capture_output=True, text=True)
        
        stats = {}
        if result.returncode == 0 and result.stdout:
            stats_data = json.loads(result.stdout)
            if stats_data:
                stats = stats_data[0]
        
        return {
            'container_id': container.container_id,
            'agent_id': agent_id,
            'status': container.status,
            'created_at': container.created_at.isoformat(),
            'workspace_path': container.workspace_path,
            'image': container.config.image,
            'memory_limit': container.config.memory_limit,
            'cpu_limit': container.config.cpu_limit,
            'stats': stats
        }
    
    async def list_workspaces(self) -> List[Dict[str, Any]]:
        """List all active workspaces"""
        workspaces = []
        for agent_id in self.containers:
            info = self.get_workspace_info(agent_id)
            if info:
                workspaces.append(info)
        return workspaces
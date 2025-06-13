# workspace_isolation

Workspace Isolation Module for Claude Conductor
Provides Podman-based isolated development environments for agents

## Classes

### ContainerConfig

Configuration for an isolated container workspace

#### Attributes

- `name` (str)
- `image` (str)
- `agent_id` (str)
- `memory_limit` (str)
- `cpu_limit` (str)
- `volumes` (Dict[(str, str)])
- `environment` (Dict[(str, str)])
- `capabilities_add` (List[str])
- `capabilities_drop` (List[str])
- `network_mode` (str)
- `privileged` (bool)
- `user` (Optional[str])

### WorkspaceContainer

Represents an isolated workspace container

#### Attributes

- `container_id` (str)
- `config` (ContainerConfig)
- `created_at` (datetime)
- `status` (str)
- `workspace_path` (str)
- `ports` (Dict[(str, int)])

### WorkspaceIsolationManager

Manages isolated workspaces for agents using Podman

#### Methods

##### get_workspace_info

`get_workspace_info(agent_id: str)` -> Optional[Dict[(str, Any)]]

Get information about an agent's workspace

**Parameters:**
- `agent_id` (str)

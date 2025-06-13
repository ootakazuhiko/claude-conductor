# Claude Conductor Security Guide

## Overview

This document outlines the security measures implemented in Claude Conductor and provides guidance for secure deployment and operation.

## Container Security

### Security Hardening Implemented

#### 1. User and Privilege Management
- **Non-root execution**: All containers run as user ID 1000 (claude user)
- **No sudo access**: Removed sudo privileges from container users
- **Privilege escalation prevention**: `allowPrivilegeEscalation: false`
- **No new privileges**: `security-opt no-new-privileges:true`

#### 2. Capability Management
- **All capabilities dropped**: `cap-drop: ALL`
- **No dangerous capabilities**: Removed SYS_PTRACE and other debug capabilities
- **Minimal capability set**: Only essential capabilities if absolutely required

#### 3. Filesystem Security
- **Read-only root filesystem**: `readOnlyRootFilesystem: true`
- **Secure tmpfs mounts**: 
  - `/tmp`: `rw,noexec,nosuid,size=100m`
  - `/var/tmp`: `rw,noexec,nosuid,size=50m`
- **Volume mount restrictions**: No host path mounts, secure volume permissions

#### 4. Resource Limits
- **Process limits**: `ulimit nproc=1024`
- **File descriptor limits**: `ulimit nofile=1024`
- **PID limits**: `pids-limit=100`
- **Memory limits**: Configurable memory constraints
- **CPU limits**: Configurable CPU constraints

#### 5. System Call Restrictions
- **Seccomp profiles**: Default seccomp profile applied
- **Core dump prevention**: `ulimit core=0`
- **System call filtering**: Runtime default security profiles

### Docker/Podman Security Configuration

#### Container Runtime Security Options
```bash
# Security options applied to all containers
--security-opt no-new-privileges:true
--security-opt seccomp=default
--read-only
--user 1000:1000
--cap-drop ALL
--tmpfs /tmp:rw,noexec,nosuid,size=100m
--tmpfs /var/tmp:rw,noexec,nosuid,size=50m
--ulimit nproc=1024
--ulimit nofile=1024
--ulimit core=0
--pids-limit 100
```

#### Volume Mount Security
```yaml
# Secure volume mounting practices
volumes:
  - source:/destination:ro      # Read-only when possible
  - workspace:/workspace:rw,Z   # SELinux labels for isolation
  # NEVER mount Docker socket: /var/run/docker.sock
```

## Kubernetes Security

### Pod Security Standards

#### Security Context Configuration
```yaml
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
  capabilities:
    drop:
    - ALL
    add: []
```

#### Network Security

##### Network Policies
- **Default deny**: All traffic denied by default
- **Ingress restrictions**: Only authorized pod-to-pod communication
- **Egress limitations**: Minimal outbound access (DNS, HTTPS for APIs)
- **Namespace isolation**: Traffic restricted within claude-conductor namespace

##### Applied Network Policies
1. `claude-conductor-network-policy`: Main orchestrator traffic rules
2. `claude-conductor-agent-network-policy`: Agent-specific restrictions
3. `default-deny-all`: Default deny policy for namespace

#### RBAC Security

##### Principle of Least Privilege
- **Read-only access**: Most operations limited to read-only
- **Resource-specific permissions**: Limited to claude-conductor resources
- **Namespace-scoped**: No cluster-wide permissions where possible
- **No secret access**: ConfigMaps only, no secret reading permissions

##### Service Account Permissions
```yaml
# Restricted RBAC permissions
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]  # No create/delete
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "watch"]  # No secrets access
```

#### Pod Security Policy
- **Privileged containers**: Forbidden
- **Host access**: No host network, PID, or IPC access
- **Volume restrictions**: Limited to safe volume types
- **Seccomp enforcement**: Runtime default profile required

## Network Security

### Communication Security

#### Inter-component Communication
- **Unix socket communication**: Secure local socket communication
- **TLS encryption**: HTTPS for web dashboard (when configured)
- **No plain HTTP**: All external communication over HTTPS

#### Network Isolation
- **Container networking**: Isolated bridge networks
- **Port restrictions**: Minimal exposed ports
- **Firewall rules**: Network policies for pod-to-pod communication

### External Dependencies
- **Package verification**: APT package signature verification
- **Base image security**: Regular base image updates
- **Vulnerability scanning**: Container image scanning (recommended)

## Deployment Security

### Production Deployment Checklist

#### Before Deployment
- [ ] Remove all debug capabilities (SYS_PTRACE, etc.)
- [ ] Verify no sudo access in containers
- [ ] Confirm read-only root filesystem
- [ ] Check Docker socket is not mounted
- [ ] Validate RBAC permissions are minimal
- [ ] Ensure network policies are applied
- [ ] Verify security contexts are configured

#### Container Image Security
- [ ] Base image vulnerability scan completed
- [ ] No hardcoded secrets in images
- [ ] Multi-stage build with minimal final image
- [ ] Image signed and verified
- [ ] Regular image updates scheduled

#### Runtime Security
- [ ] Security monitoring enabled
- [ ] Log aggregation configured
- [ ] Intrusion detection system (optional)
- [ ] Regular security audits scheduled

### Security Monitoring

#### Container Security Monitoring
```bash
# Runtime security validation commands
podman inspect $CONTAINER_ID --format '{{.HostConfig.Privileged}}'  # Should be false
podman inspect $CONTAINER_ID --format '{{.Config.User}}'             # Should be 1000:1000
podman inspect $CONTAINER_ID --format '{{.HostConfig.ReadonlyRootfs}}' # Should be true
```

#### Kubernetes Security Monitoring
```bash
# Security validation commands
kubectl get pods -o jsonpath='{.items[*].spec.securityContext.runAsUser}'
kubectl get networkpolicies -n claude-conductor
kubectl auth can-i --list --as=system:serviceaccount:claude-conductor:claude-conductor-orchestrator
```

## Security Best Practices

### Development Security
1. **No development tools in production**: Remove debugging tools from production images
2. **Secure defaults**: All security features enabled by default
3. **Principle of least privilege**: Minimal permissions for all components
4. **Defense in depth**: Multiple layers of security controls

### Operational Security
1. **Regular updates**: Keep base images and dependencies updated
2. **Security scanning**: Regular vulnerability assessments
3. **Access control**: Limit human access to production environments
4. **Audit logging**: Comprehensive security event logging

### Incident Response
1. **Security monitoring**: Real-time security event detection
2. **Incident procedures**: Documented response procedures
3. **Container isolation**: Ability to quickly isolate compromised containers
4. **Backup and recovery**: Secure backup and recovery procedures

## Security Contacts

For security issues or questions:
- Review this security guide
- Check the troubleshooting documentation
- Report security vulnerabilities through appropriate channels

## Compliance

This security configuration addresses common compliance requirements:
- **CIS Kubernetes Benchmark**: Pod security standards alignment
- **NIST Cybersecurity Framework**: Security controls implementation
- **SOC 2**: Security control objectives
- **PCI DSS**: Data protection measures (where applicable)

## Version History

- v1.0.0: Initial security hardening implementation
  - Removed sudo access from containers
  - Implemented read-only root filesystem
  - Added comprehensive capability dropping
  - Created network policies
  - Restricted RBAC permissions
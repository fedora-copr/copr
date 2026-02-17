# Run Copr infra with podman kube play

Run the full COPR infrastructure locally using `podman kube play` with Kubernetes
manifests. Designed for development, testing, and as the foundation for
OpenShift deployment.

## Quick Start

```bash
cd deployment/
just up          # Start with @copr/copr-dev packages (latest main)
```

## Prerequisites

- `podman` (with aardvark-dns for inter-pod DNS resolution)
- `just` (command runner — `dnf install just`)

Enable the rootless podman socket (needed for dynamic builder provisioning):
```bash
systemctl --user enable --now podman.socket
```

## Modes

| Mode      | Command                  | RPM Source                              |
| --------- | ------------------------ | --------------------------------------- |
| `dev`     | `just up`                | `@copr/copr-dev` packages (latest main) |
| `release` | `just up-release`        | Stable Fedora RPMs only                 |
| `pr`      | `just up-pr <PR_NUMBER>` | PR packages overlaid on dev             |
| `local`   | `just up-local`          | Dev RPMs + local source mounted         |

### Local Development

```bash
just up-local                    # Start with source mounted at /opt/copr
vim ../frontend/coprs_frontend/  # Edit code
just restart frontend            # Pick up changes
```

### Testing a Pull Request

```bash
just up-pr 3127                  # Start with RPMs from PR #3127
```

## Architecture

Builders are provisioned **dynamically** by resalloc as podman containers
on the shared `copr` network. This means:

- Multiple builds can run concurrently (configurable via `pools.yaml`)
- Each builder is an isolated container
- Builders are created on-demand and destroyed after use
- The approach mirrors production deployment patterns

### Manifest Structure

```
manifests/
  pods/             # Individual pod definitions (source of truth)
    backend.yaml
    backend-httpd.yaml
    builder.yaml    # Template for dynamic builders (not deployed directly)
    database.yaml
    distgit.yaml
    frontend.yaml
    keygen.yaml
    redis.yaml
    resalloc.yaml
  local/            # Local dev overrides (add source code mounts)
    backend.yaml
    distgit.yaml
    frontend.yaml
    keygen.yaml
  configmaps.yaml   # ConfigMap placeholders (for OpenShift overrides)
  volumes.yaml      # PersistentVolumeClaim definitions
```

Individual pod manifests in `pods/` are the **single source of truth**.
The justfile concatenates them for `podman kube play`. For OpenShift,
these same files can be applied directly with `oc apply -f manifests/pods/`.

### Access Points

| Service         | URL                   |
| --------------- | --------------------- |
| Frontend        | http://localhost:5000 |
| DistGit         | http://localhost:5001 |
| Backend Results | http://localhost:5002 |
| Resalloc WebUI  | http://localhost:5005 |
| Database        | localhost:5009        |

## Commands

```bash
just              # Show all available commands
just up           # Build and start (dev mode)
just up-release   # Build and start (stable RPMs)
just up-pr 1234   # Build and start (PR RPMs)
just up-local     # Build and start (local source mounted)
just down         # Stop everything (including dynamic builders)
just status       # Show pod and container status
just logs frontend    # View logs for a service
just logs-f backend   # Follow logs
just shell frontend   # Open shell in container
just restart frontend # Restart a service
just clean        # Stop and remove images
just clean-all    # Remove everything (images, volumes, keys, network)
```

## Future: OpenShift Deployment

This setup is designed as the foundation for OpenShift deployment:

- Individual pod manifests in `pods/` map directly to OpenShift resources
- Service definitions are included for OpenShift service discovery
- ConfigMaps and PVCs are defined as separate resources
- Container images use standard patterns (non-root users, health checks)
- Dynamic builder provisioning translates to OpenShift Jobs
- The `containers/` directory is shared between local and OpenShift deployments
- `manifests/local/` demonstrates the overlay pattern (Kustomize in OpenShift)

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

Manifests use [Kustomize](https://kustomize.io/) with a base + overlay
pattern. The justfile renders the selected overlay via `kustomize build`
and pipes the result to `podman kube play`.

## Commands

Run `just` to see all available commands.

## Future: OpenShift Deployment

This setup is designed as the foundation for OpenShift deployment:

- Deployment manifests in `base/` map directly to OpenShift resources
- Service definitions are included for OpenShift service discovery
- ConfigMaps and PVCs are defined as separate resources
- Container images use standard patterns (non-root users, health checks)
- Dynamic builder provisioning translates to OpenShift Jobs
- The `containers/` directory is shared between local and OpenShift deployments
- Kustomize overlays demonstrate the pattern used in OpenShift

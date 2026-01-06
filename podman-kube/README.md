# Run Copr infra with podman kube play

Run COPR infrastructure locally using `podman kube play` with Kubernetes manifests.

## Quick Start

```bash
just up        # Start with dev packages
just up-local  # Start with local source code mounted
```

## Usage

```bash
just help      # Show all commands
```

## Modes

| Mode      | Command              | Description                             |
| --------- | -------------------- | --------------------------------------- |
| `dev`     | `just up`            | Uses `@copr/copr-dev` packages (main)   |
| `release` | `just build release` | Uses Fedora packages only               |
| `local`   | `just up-local`      | Mounts repo source code for development |

### Local Development

```bash
just up-local                    # Start with source mounted at /opt/copr
vim ../frontend/coprs_frontend/  # Edit code
just restart frontend            # Pick up changes
```

## Access Points

| Service         | URL                   |
| --------------- | --------------------- |
| Frontend        | http://localhost:5000 |
| DistGit         | http://localhost:5001 |
| Backend Results | http://localhost:5002 |
| Resalloc WebUI  | http://localhost:5005 |
| Database        | localhost:5009        |

## Host Entries (optional)

Add to `/etc/hosts` for internal URL resolution:

```
127.0.0.1   frontend backend-httpd distgit keygen resalloc
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         localhost                                │
├──────────┬──────────┬──────────┬──────────┬──────────┬─────────┤
│  :5000   │  :5001   │  :5002   │  :5005   │  :5009   │         │
│ Frontend │ DistGit  │ Results  │ Resalloc │ Database │  Redis  │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬────┘
     │          │          │          │          │          │
     └──────────┴──────────┴──────────┴──────────┴──────────┘
                              │
                    ┌─────────┴─────────┐
                    │  Backend Workers  │
                    │  (log/build/action)│
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │     Builder       │
                    │   (mock builds)   │
                    └───────────────────┘
```

## Future Improvements

Potential enhancements for this infrastructure:

### Short-term

- [ ] Kustomize overlays for dev/staging/prod
- [ ] Resource limits (CPU/memory) in manifests
- [ ] Readiness/liveness probes for all services
- [ ] Secrets management (not hardcoded passwords)
- [ ] Network policies for service isolation

### Medium-term

- [ ] Helm chart for parameterized deployment
- [ ] CI/CD pipeline to build and push images to registry
- [ ] OpenShift-compatible manifests (Routes, DeploymentConfigs)
- [ ] Horizontal pod autoscaling configs
- [ ] Prometheus metrics endpoints

### Long-term

- [ ] Multi-node deployment support
- [ ] External database/redis support
- [ ] S3-compatible storage for results
- [ ] Pulp integration for content management
- [ ] GitOps workflow with ArgoCD/Flux

## Requirements

- podman
- just (`dnf install just`)

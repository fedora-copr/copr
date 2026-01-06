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

## Future: OpenShift Deployment

This podman-kube setup is designed to be portable to OpenShift:

- Kubernetes manifests are compatible with OpenShift
- Container images use standard patterns
- Secrets and ConfigMaps can be managed separately

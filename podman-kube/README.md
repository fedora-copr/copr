# Run Copr infra with podman kube play

Run COPR infrastructure locally using `podman kube play` with Kubernetes manifests.

## Quick Start

```bash
# Run with dev packages
just up

# Run with local source code (for development)
just up-local
```

## Usage

See the manual from just:

```bash
just --list
```

## Modes

| Mode      | Command              | Description                             |
| --------- | -------------------- | --------------------------------------- |
| `dev`     | `just up`            | Uses `@copr/copr-dev` packages (main)   |
| `release` | `just build release` | Uses Fedora packages only               |
| `local`   | `just up-local`      | Mounts repo source code for development |

### Local Development Mode

`just up-local` mounts the repository at `/opt/copr` inside containers with appropriate `PYTHONPATH` settings. Edit code locally, then restart the service:

```bash
# Edit frontend code...
vim ../frontend/coprs_frontend/coprs/views/misc.py

# Restart frontend to pick up changes
just restart frontend
```

## Access Points

After starting, the following services are available:

| Service         | URL                   |
| --------------- | --------------------- |
| Frontend        | http://localhost:5000 |
| DistGit         | http://localhost:5001 |
| Backend Results | http://localhost:5002 |
| Resalloc WebUI  | http://localhost:5005 |
| Database        | localhost:5009        |

## Host Entries (optional)

To make internal URLs work in your browser, add to `/etc/hosts`:

```
127.0.0.1   frontend backend-httpd distgit keygen resalloc
```

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

## Local OpenShift (CRC MicroShift)

Run Copr on a local OpenShift cluster using CRC
with the MicroShift preset.

### Setup

```bash
crc setup
crc config set preset microshift
crc config set cpus 12
crc config set memory 24576
crc config set disk-size 80
crc start
```

### Deploy

```bash
just up-openshift       # Build images, push to CRC, apply manifests
just status-openshift   # Check pod status
just down-openshift     # Tear down
```

Images are built locally with `podman`, transferred into the CRC VM via
`podman save | ssh podman load`, and referenced as `localhost/copr-*` with
`imagePullPolicy: Never`. The `overlays/openshift/` kustomization handles
image name prefixing, pull policy, security contexts, and resalloc pool
sizing.

### Running tests

TODO: still needs some tweaks... will fill out after https://github.com/fedora-copr/copr/pull/4305

### Useful URLs

| Service | URL |
|---------|-----|
| Frontend | http://copr-frontend-copr.apps.crc.testing |
| Backend results | http://copr-backend-copr.apps.crc.testing |
| Dist-git | http://copr-distgit-copr.apps.crc.testing |
| Resalloc WebUI | http://copr-resalloc-copr.apps.crc.testing/pools |

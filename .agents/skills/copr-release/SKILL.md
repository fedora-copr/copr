---
name: copr-release
description: >-
  Release Copr RPM packages to Fedora infrastructure. Use when the user asks to
  release, tag, deploy, or do a mini release of Copr packages. Covers the full
  lifecycle: pre-release testing, tagging, Koji builds, infra tags, and
  deployment.
docs: https://docs.copr.fedorainfracloud.org/how_to_release_copr.html
---

# Copr Release

Full release documentation: `doc/how_to_release_copr.rst`
Hotfix documentation: `doc/how_to_build_hotfix.rst`

This skill adds agent-specific behavior on top of the docs: what to automate,
what to ask the user, what NOT to run yourself, and how to poll for results.

## Key Principle

**Test before tagging.** Never create tags or push them until sanity tests
pass on dev machines. Never push to production without explicit user
confirmation.

## Git Remotes

Verify with `git remote -v`. Commands below assume `upstream` → `fedora-copr/copr`.

---

## Phase 0: Verify clean state

Before starting, check the repo is ready:

```bash
git branch --show-current        # must be main (or hotfix-$DATE)
git status --porcelain           # must be empty
git remote -v                    # identify which remote is fedora-copr/copr
```

If dirty or wrong branch, stop and tell the user.

---

## Phase 1: Pre-release Testing

### 1.1 Rebuild @copr/copr-dev

```bash
git checkout main && git pull --rebase upstream main
./build_aux/rebuild-copr-stack
```

Poll builds until all succeed:

```bash
copr list-builds @copr/copr-dev --output-format text-row | head -10
```

Keep checking every ~60s. Do NOT proceed until all builds show `succeeded`.
If any build fails, read the build log, tell the user, and stop.

### 1.2 Deploy to dev machines

**Ask the user** to run the relevant playbooks on batcave01 (you don't have
SSH access). For a mini release (e.g. backend-only), only the relevant playbook
is needed. See `doc/how_to_release_copr.rst` → "Upgrade -dev machines".

### 1.3 Verify + test

Tell the user to verify versions and run sanity tests. See `doc/sanity_tests.rst`
for details, or `testing-farm/all-on-single-host.sh` for the single-host variant.

```bash
./releng/run-on-all-infra --devel 'rpm -qa | grep copr'
```

**Do NOT proceed to tagging until the user confirms tests pass.**

---

## Phase 2: Tag

Follow `doc/how_to_release_copr.rst` → "Tag untagged packages". You can run
`tito report --untagged-commits` and `tito tag` yourself.

After tito generates the changelog, clean it up — amend the tag commit with
the polished changelog, then `git tag -f <tag>`.

Push: `git push --follow-tags upstream`

---

## Phase 3: Build and Release to Koji

### 3.1 Build into @copr/copr

For each tagged package:

```bash
copr build-package @copr/copr --nowait --name <package-name>
```

Poll with `copr-cli status <BUILD_ID>` until all succeed.

### 3.2 Release to Fedora dist-git / Koji

**Do NOT run `tito release` yourself** — it requires interactive prompts
(Kerberos auth, branch confirmations). Print the commands for the user.
See `doc/how_to_release_copr.rst` → "Build packages for production" for
the package→releaser mapping and known issues (Bodhi overrides, backend
DistGit sources file).

Before printing commands, run `klist` yourself. If no valid `FEDORAPROJECT.ORG`
ticket exists, stop and tell the user to run `fkinit -u <FAS_USERNAME>` first.

### 3.3 Determine NVRs for infra tags

After the user confirms tito release is done, **ask: "Which Fedora version are
the Copr servers running on?"**

Look up NVR and arch from Koji:

```bash
koji taskinfo <TASK_ID> | grep "^Build:"
koji buildinfo <BUILD_ID>   # check RPMs section for arch (noarch vs x86_64)
```

Most Copr packages are `noarch`; `copr-rpmbuild` is the exception (per-arch).
Use `koji buildinfo` to confirm the arch when constructing the RPM filename
for `koji-infratag-available`.

---

## Phase 4: Infra Tags and Production Deploy

Follow `doc/how_to_release_copr.rst` → "Submit packages into stg infra tags"
through "Upgrade production machines". The releng scripts to use:

```bash
./releng/koji-infratag-staging <NVR> ...
./releng/koji-infratag-available --stg --wait <NVR>.<arch>.rpm
./releng/koji-infratag-move-prod <NVR> ...
./releng/koji-infratag-available --prod --wait <NVR>.<arch>.rpm
```

**Koji race condition:** There is a long-term race in Koji repo regeneration.
When submitting multiple NVRs, submit all **but one** first, wait a few minutes,
then submit the last one to "poke through" a potentially broken repo. This
applies to both staging and production infra tags.

Agent-specific checkpoints:

1. After staging verification, **ask: "Staging looks good. Ready to push to production?"** Wait for explicit confirmation.
2. Tell the user to run upgrade playbooks on batcave01. Advise stopping `copr-backend.target` first.
3. After production upgrade, ask user to run `runtest-production.sh` or submit a test build.

---

## Phase 5: Post-release

Print the post-release checklist from `doc/how_to_release_copr.rst` →
"Post-release" for the user. These are all manual steps (PyPI, Bodhi,
Bugzilla, ReadTheDocs, release notes, outage announcement).

---

## Hotfix

See `doc/how_to_build_hotfix.rst`. Key difference: work on a `hotfix-$DATE`
branch, cherry-pick fixes, use `.hotfix.N` versions.

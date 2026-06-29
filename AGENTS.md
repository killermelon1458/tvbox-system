# TVBox Repository Instructions

These instructions apply to work in the `/opt/tvbox-system` repository for the TVBox Raspberry Pi appliance.

## Core Rule

The repo is the source of truth.

Do not treat live files under `/usr/local/bin`, `~/.config`, `~/.kodi`, `/etc/systemd`, or other system paths as authoritative unless the user explicitly asks to inspect live state. Prefer editing repo files, then documenting how they deploy.

Do not edit live appliance paths directly unless explicitly instructed. If a live emergency patch is required, document it in the development note and then backport the final version into the repo.

## Documentation Policy

Development documentation goes in:

```text
docs/development/
```

Use one file per change or feature:

```text
docs/development/YYYY-MM-DD-short-feature-name.md
```

The development note is the working log. It should include:

```text
Goal
Current behavior
Problem being solved
Files expected to change
Proposed implementation
Commands used
Validation checklist
Test results
Known risks
Rollback notes
Status: draft / implemented / validated / abandoned
```

For documentation-only edits that do not change current behavior, a development note is optional. Still run `git status --short`, keep edits scoped, and report validation if applicable.

Current-state documentation goes in the existing current-state docs, especially:

```text
docs/current-system-redeploy.md
```

Only update current-state docs after the change has been tested and validated. Current-state docs must describe what is now true, not what is planned.

Do not mix speculative plans into current-state documentation. Speculative or unfinished work belongs only in `docs/development/` or in explicitly named plan docs.

Untracked speculative plan docs may remain untracked unless the user explicitly asks to track them. Project documentation that describes current behavior or validated workflow should be tracked.

## Required Workflow

Before editing, run:

```bash
git status --short
```

If the working tree is dirty, summarize what is already modified. If dirty files are directly related to the requested change, continue unless there is ambiguity. If they are unrelated, ask before touching them.

When asked to implement a code/config behavior change, start by proposing the development document name and the validation checklist before editing files.

Before code/config changes, create or update the matching development document in `docs/development/`.

Make the smallest reasonable code/config change.

Validate the change using relevant checks:

```text
Shell scripts: bash -n
Kodi add-on XML: XML parser
Systemd units/drop-ins: systemd-analyze verify when possible
Other config: the safest available parser or dry-run check
```

Separate validation into:

```text
repo validation: syntax, XML, static checks
deploy validation: installer, service restart, reboot, or live appliance test
```

If deploy validation was not run, state that clearly and do not update current-state docs beyond repo-owned facts.

Record validation results in the development document.

Only after validation, update current-state documentation to reflect the new known-good state.

Show the user:

```text
git status --short
git diff --stat
key diffs or a summary of exact file changes
validation commands and results
recommended commit message
```

Do not commit unless explicitly told to commit.

Do not push unless explicitly told to push.

If the user says to commit, stage related implementation files and documentation together. The commit should include:

```text
code/config changes
the matching docs/development/... note
updated current-state docs if the change was validated
```

If the user says to push, push only after confirming the commit succeeded and the working tree is clean except for intentionally unrelated files.

## Deploy Safety

Do not run `install.sh`, restart services, reboot, or alter live system state unless explicitly asked or clearly required for validation and approved.

When a change introduces or discovers an OS/package/runtime dependency, document it in the development note. After validation, update current-state redeploy docs.

For installer, systemd, labwc, Home/F12, or Kodi launch changes, rollback notes must include the exact file or symlink restoration path.

## TVBox Safety Rules

Do not commit secrets, tokens, credentials, browser profiles, cache directories, logs, runtime state, `.codex`, or `~/.codex`.

Do not broad-kill or rewrite unrelated TVBox components.

Do not replace existing TVBox architecture without calling out the conflict first.

Keep Home/F12 recovery and Kodi launch behavior safe.

Preserve the distinction between safe Home behavior and destructive Exit behavior, especially for Moonlight/Sunshine.

Do not invent validated behavior. If something was not tested, mark it untested.

Prefer boring, recoverable changes over clever changes.

## Shell Style

For shell scripts, prefer `set -u` or `set -euo pipefail` where compatible with existing behavior.

Quote variables unless word splitting is intentional.

Use Bash consistently for scripts with `#!/bin/bash`. Only write POSIX shell when a script declares `#!/bin/sh`.

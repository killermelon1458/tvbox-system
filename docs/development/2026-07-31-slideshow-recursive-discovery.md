# Slideshow Recursive Discovery

Date: 2026-07-31

Status: implemented; repository validated

## Goal

Treat the configured slideshow root and every eligible nested directory as one
combined, bounded image collection on every scan.

## Current behavior

The deployed configuration enables an existing recursive scan, and the scanner
already avoids following directory symlinks and skips hidden/Syncthing internal
paths. Coverage is limited, directory scan failures are silent, duplicate file
identities are not removed, and configuration still presents recursion as an
optional switch.

## Problem being solved

Recursive discovery must be the canonical runtime behavior, safely tolerate a
changing or partially inaccessible photo tree, and make its guarantees explicit
and tested.

## Files expected to change

- `lib/tvbox/screensaver/slideshow.py`
- `lib/tvbox/screensaver/schedule.py`
- `config/screensaver.toml`
- `tests/test_slideshow.py`
- schedule/config tests where required
- current screensaver documentation

## Proposed implementation

Keep the current bounded scanner and ordering/shuffle pipeline, but make runtime
recursion mandatory, isolate and log per-directory traversal errors, retain
non-following stat behavior, deduplicate candidates by device/inode, and expand
focused tests. Hidden paths and Syncthing internal directories remain pruned.

## Commands used

```text
git status --short
git log -6 --oneline --decorate
inspect slideshow scanner, renderer, config, tests, and deployment docs
```

## Validation checklist

- [x] Root and multiple nested levels form one collection.
- [x] Directory depth adds no weighting or separate collection behavior.
- [x] Directory symlinks are not followed and loops are impossible.
- [x] Hidden/system directories remain pruned.
- [x] Inaccessible/bad subdirectories are logged and skipped.
- [x] Duplicate file identities are removed where available.
- [x] Unsupported files and empty recursive trees produce no candidates.
- [x] Periodic renderer rescans use recursive discovery.
- [x] Existing filtering, decode, orientation, preload, ordering/shuffle, memory bounds, and black fallback remain unchanged.
- [x] Focused and full test suites pass.
- [x] Shell/Python/static validation and `git diff --check` pass.

## Test results

```text
python3 -m unittest tests.test_slideshow tests.test_screensaver_schedule -v
Ran 26 tests ... OK

python3 -m unittest discover -s tests -v
Ran 122 tests ... OK

python3 -m compileall -q lib/tvbox/screensaver bin/tvbox-render-slideshow
git diff --check
```

The focused tests cover root images, two nested levels, directory symlinks and
a loop-shaped symlink, hard-link deduplication, deterministic inaccessible
subdirectory failure, hidden/unsupported-only recursive results, the production
renderer's mandatory recursive call, and rejection of `recursive = false`.

Deploy validation was not run because this request did not authorize running
the installer or restarting services. The established `/usr/local/bin` launcher
is a repository symlink, but no live renderer was started or disturbed.

## Known risks

Permission behavior is environment-dependent, so automated inaccessible-folder
coverage uses a deterministic injected `scandir` failure.

## Rollback notes

Restore the prior slideshow scanner/config parser and redeploy through
`/opt/tvbox-system/install.sh`. No scheduling, overlay, idle, or application
lifecycle service is changed by this work.

# Register-Job Privilege Separation — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the privileged `register` job from executing contributor code, and give each job least-privilege permissions, without changing the post-merge registration behaviour.

**Architecture:** Add a read-only `lb_has_player.py` existence check; rewrite the addition path of `register-player.yml` to use it instead of importing the player; move permissions from workflow level to per-job least privilege.

**Tech Stack:** GitHub Actions YAML, Python (PyYAML), pytest.

Spec: `docs/specs/2026-06-11-register-job-privilege-separation-design.md`

---

### Task 1: Add `lb_has_player.py` existence-check script (TDD)

**Files:**

- Create: `.github/scripts/lb_has_player.py`
- Test: `tests/test_lb_has_player.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".github/scripts/lb_has_player.py"


def _run(stem: str, lb: dict, tmp_path: Path) -> str:
    lb_path = tmp_path / "leaderboard.yaml"
    lb_path.write_text(yaml.dump(lb, default_flow_style=False, sort_keys=False))
    result = subprocess.run(
        ["uv", "run", "python", str(SCRIPT), stem],
        cwd=str(tmp_path),
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_present_exact(tmp_path):
    lb = {"players": {"Topper": {"github_username": "alice"}}}
    assert _run("Topper", lb, tmp_path) == "true"


def test_present_case_insensitive(tmp_path):
    lb = {"players": {"Topper": {"github_username": "alice"}}}
    assert _run("topper", lb, tmp_path) == "true"


def test_absent(tmp_path):
    lb = {"players": {"Topper": {"github_username": "alice"}}}
    assert _run("pyro", lb, tmp_path) == "false"


def test_no_players_key(tmp_path):
    assert _run("topper", {}, tmp_path) == "false"


def test_missing_file(tmp_path):
    result = subprocess.run(
        ["uv", "run", "python", str(SCRIPT), "topper"],
        cwd=str(tmp_path),  # no leaderboard.yaml here
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "false"
    assert result.returncode == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_lb_has_player.py -v`
Expected: FAIL (script does not exist yet).

- [ ] **Step 3: Write the script**

```python
#!/usr/bin/env python3
"""Print "true" if a player whose class name matches the given file stem
(case-insensitive) is already in leaderboard.yaml, else "false".

The leaderboard is keyed by class name, and the player contract guarantees the
class name equals the filename stem (case-insensitive), so this is a pure-data
uniqueness check that never imports the player file.

Usage: lb_has_player.py <stem>
Always exits 0.
"""

import sys

import yaml

stem = sys.argv[1]
try:
    with open("leaderboard.yaml") as f:
        data = yaml.safe_load(f) or {}
    for key in data.get("players", {}):
        if key.lower() == stem.lower():
            print("true")
            sys.exit(0)
except Exception:
    pass
print("false")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_lb_has_player.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add .github/scripts/lb_has_player.py tests/test_lb_has_player.py
git commit -m "feat(scripts): add lb_has_player.py read-only uniqueness check"
```

---

### Task 2: Remove player-code execution from the `register` job's addition path

**Files:**

- Modify: `.github/workflows/register-player.yml` (addition path, lines ~145-165)

- [ ] **Step 1: Replace the addition block**

Replace the current addition path:

```yaml
          # ── Addition ──
          if [ "$n_added" -eq 1 ] && [ "$n_modified" -eq 0 ] && [ "$n_deleted" -eq 0 ]; then
            player_file="$added"
            # Validate against a temp leaderboard — don't write to the real one pre-merge
            tmp_lb=$(mktemp)
            cp leaderboard.yaml "$tmp_lb"
            if ! output=$(PLAYER_FILE="$player_file" GITHUB_USERNAME="$ACTOR" \
              LEADERBOARD_PATH="$tmp_lb" \
              uv run python .github/scripts/register_player.py 2>&1); then
              echo "$output"
              rm -f "$tmp_lb"
              post_rejection "Player validation failed:\`\`\`${output}\`\`\`"
            fi
            rm -f "$tmp_lb"
            echo "$output"
            if echo "$output" | grep -qi "already registered"; then
              post_rejection "A player with that class name already exists. Please choose a unique class name."
            fi
            gh pr merge "$PR_NUMBER" --auto --squash
            exit 0
          fi
```

with (the player file is NOT imported here; `validate` already vetted it):

```yaml
# ── Addition ──
# The validate job (needs: validate) already imported and vetted the
# player file. This privileged step must NOT execute player code, so
# it only checks uniqueness against leaderboard.yaml by class name.
if [ "$n_added" -eq 1 ] && [ "$n_modified" -eq 0 ] && [ "$n_deleted" -eq 0 ]; then
player_file="$added"
cls_stem=$(basename "$player_file" .py)
exists=$(uv run python .github/scripts/lb_has_player.py "$cls_stem")
if [ "$exists" = "true" ]; then
post_rejection "A player with that class name already exists. Please choose a unique class name."
fi
gh pr merge "$PR_NUMBER" --auto --squash
exit 0
fi
```

- [ ] **Step 2: Verify the file still parses as YAML**

Run:

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/register-player.yml')); print('YAML OK')"
```

Expected: `YAML OK`

- [ ] **Step 3: Confirm no remaining player-code execution in the register job**

Run: `grep -n "register_player.py\|exec_module\|game.validate" .github/workflows/register-player.yml`
Expected: no matches inside the `register` job (the `validate` job's `game.validate` line is the only player-executing call and lives in that job).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/register-player.yml
git commit -m "fix(workflows): stop register job from executing contributor code"
```

---

### Task 3: Per-job least-privilege permissions

**Files:**

- Modify: `.github/workflows/register-player.yml` (top-level `permissions` block + both jobs)

- [ ] **Step 1: Remove the workflow-level permissions block**

Delete:

```yaml
permissions:
  contents: write
  pull-requests: write
```

(Leave the `on:` and `env:` blocks intact.)

- [ ] **Step 2: Add a job-level permissions block to `validate`**

Immediately under `  validate:` and before `    if:` / `    runs-on:`, add:

```yaml
permissions:
  contents: read
  pull-requests: write
```

- [ ] **Step 3: Add a job-level permissions block to `register`**

Immediately under `  register:` and before `    needs:` / `    if:`, add:

```yaml
permissions:
  contents: read
```

- [ ] **Step 4: Verify YAML parses and permissions are per-job**

Run:

```bash
uv run python - <<'PY'
import yaml
d = yaml.safe_load(open('.github/workflows/register-player.yml'))
assert 'permissions' not in d, "workflow-level permissions should be gone"
assert d['jobs']['validate']['permissions'] == {'contents': 'read', 'pull-requests': 'write'}
assert d['jobs']['register']['permissions'] == {'contents': 'read'}
print("permissions OK")
PY
```

Expected: `permissions OK`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/register-player.yml
git commit -m "fix(workflows): scope register-player jobs to least privilege"
```

---

### Task 4: Full suite + final review

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest`
Expected: all pass (existing 96 + new `lb_has_player` tests).

- [ ] **Step 2: Re-read the final `register-player.yml` diff**

Run: `git diff main -- .github/workflows/register-player.yml`
Confirm: addition path uses `lb_has_player.py`; no `register_player.py` in the
`register` job; per-job permissions present; `validate` job unchanged except its
new permissions block.

- [ ] **Step 3: Push and open PR (base `main`)**

This PR touches non-`players/` files, so it will not auto-merge — it needs owner
review/merge (the `check-files` guard passes for admins). Note in the PR body
that end-to-end verification is a throwaway player PR after merge.

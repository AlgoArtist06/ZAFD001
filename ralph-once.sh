#!/usr/bin/env bash
set -euo pipefail

#########################################
# Ralph Loop (one issue only)
#
# Issues live as local markdown files in this repo's tracker:
#   .scratch/<feature-slug>/issues/<NN>-<slug>.md
# Each carries a `Status:` line (see docs/agents/triage-labels.md).
# This script picks the next `ready-for-agent` issue, implements it,
# and marks it `done`. No GitHub issues, no `gh`/`jq` required.
#
# !! DANGER / SAFE-RUN NOTES (security finding H4) !!
# This runs a coding agent with ALL safety gates OFF
# (--dangerously-skip-permissions / --dangerously-bypass-approvals-and-sandbox)
# on UNTRUSTED issue-file content. That is the tool's intended design, but it
# means a malicious or accidental issue file is a path to arbitrary code
# execution, and the agent inherits this process's environment (any sourced
# .env secrets are in its reach).
#   - Run ONLY in a disposable / sandboxed VM or container.
#   - Use NO production credentials in the environment or in .env.
#   - Auto-push is opt-in: set RALPH_AUTO_PUSH=1 to push (default: do not push,
#     so unreviewed code cannot land on origin).
#   - Set RALPH_REQUIRE_SANDBOX=1 to hard-refuse to run when live .env secrets
#     are already exported into this environment.
#
# Exit codes:
#   0  one issue implemented and committed
#   2  no `ready-for-agent` issues remain (loop should stop)
#   1  error (dirty tree, missing config, no commit, ...)
#########################################

READY_STATUS="ready-for-agent"
DONE_STATUS="done"
RALPH_AGENT="${RALPH_AGENT:-claude}"

# -----------------------------
# Guard against sourced live secrets (finding H4)
#
# The agent runs unsandboxed and inherits this environment. If a real .env
# exists AND its variables are already exported here, they are in the agent's
# reach. Warn (or hard-refuse with RALPH_REQUIRE_SANDBOX=1) and recommend a
# disposable VM. ponytail: name-match heuristic; enough to catch a sourced .env.
# -----------------------------
if [ -f .env ]; then
    LEAKED=""
    while IFS= read -r name; do
        if [ -n "${!name:-}" ]; then
            LEAKED="$LEAKED $name"
        fi
    done < <(grep -E '^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=' .env \
                 | sed -E 's/^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=.*/\1/')

    if [ -n "$LEAKED" ]; then
        echo
        echo "WARNING: a real .env is present and these of its secrets are already"
        echo "exported in this environment:${LEAKED}"
        echo "The unsandboxed agent will INHERIT them. Run Ralph only in a disposable,"
        echo "sandboxed VM/container with no production credentials."
        if [ "${RALPH_REQUIRE_SANDBOX:-0}" = "1" ]; then
            echo "RALPH_REQUIRE_SANDBOX=1 set; refusing to run."
            exit 1
        fi
        echo
    fi
fi

# -----------------------------
# Ensure git repository exists
# -----------------------------
if [ ! -d ".git" ]; then
    echo "Initializing git repository..."
    git init
fi

# -----------------------------
# Ensure git user configured
# -----------------------------
if ! git config user.name >/dev/null; then
    echo "Git user.name is not configured."
    exit 1
fi

if ! git config user.email >/dev/null; then
    echo "Git user.email is not configured."
    exit 1
fi

# -----------------------------
# Initial commit if necessary
# -----------------------------
if ! git rev-parse HEAD >/dev/null 2>&1; then
    # B-C4: on a fresh init there is no .gitignore yet, so `git add .` could
    # stage a live .env into the very first commit. Ensure .env is ignored
    # first (this also protects every later commit the agent makes).
    if [ ! -f .gitignore ] || ! grep -qxF '.env' .gitignore; then
        printf '%s\n' '.env' '.env.*' '!.env.example' >> .gitignore
    fi
    touch .gitkeep
    git add .
    git commit -m "chore: initial commit"
fi

# -----------------------------
# Working tree must be clean
#
# Use porcelain so UNTRACKED files also count as dirty. A killed coding-agent
# session can leave new (uncommitted, untracked) source files behind;
# `git diff` ignores those, which let leftover state silently leak into
# the next iteration. Porcelain respects .gitignore, so build caches
# (__pycache__, .pytest_cache, ...) are not flagged.
# -----------------------------
if [ -n "$(git status --porcelain)" ]; then
    echo
    echo "Working tree is dirty (tracked or untracked changes):"
    git status --short
    echo
    echo "Commit, stash, or clean these before running Ralph."
    exit 1
fi

OLD_COMMIT=$(git rev-parse HEAD)

# -----------------------------
# Fetch next local issue
#
# Lowest-numbered `ready-for-agent` issue across all feature slugs.
# We only consider files under an `issues/` directory so the PRD
# (which may also be marked ready) is never picked up.
# -----------------------------
ISSUE_FILE=""
while IFS= read -r f; do
    if grep -qiE "^Status:[[:space:]]*${READY_STATUS}[[:space:]]*$" "$f"; then
        ISSUE_FILE="$f"
        break
    fi
done < <(find .scratch -type f -path '*/issues/*.md' | sort)

if [ -z "$ISSUE_FILE" ]; then
    echo "No '${READY_STATUS}' issues remain in .scratch/."
    exit 2
fi

TITLE=$(grep -m1 '^# ' "$ISSUE_FILE" | sed 's/^# //')
BODY=$(cat "$ISSUE_FILE")
STATUS_LABEL=$(grep -m1 -iE '^Status:' "$ISSUE_FILE" | sed -E 's/^Status:[[:space:]]*//I')

echo
echo "======================================"
echo "Implementing $ISSUE_FILE"
echo "$TITLE"
echo "Triage label: ${STATUS_LABEL}"
echo "======================================"
echo

PROMPT=$(cat <<EOF
Implement the local issue tracked in this repository at:
  $ISSUE_FILE

Title:
$TITLE

Full issue file:
---
$BODY
---

Requirements:

- Immediately invoke /tdd.
- Work ONLY on this issue.
- Follow Red -> Green -> Refactor.
- Keep implementation minimal.
- Do not modify unrelated files or other issue files.
- Satisfy the issue's acceptance criteria.
- Run all project tests.
- Run lint (if configured).
- Run typecheck (if configured).
- Update the issue file's "Status:" line to "${DONE_STATUS}".
- Append a short "## Comments" note to the issue file summarizing what you built.
- Stage all modified files.
- Create ONE conventional git commit.
- Do NOT begin another issue.
- Exit after committing.
EOF
)

# -----------------------------
# Launch the selected coding agent
# -----------------------------
case "$RALPH_AGENT" in
    claude)
        claude -p --verbose --dangerously-skip-permissions "$PROMPT"
        ;;
    codex)
        codex exec \
            --dangerously-bypass-approvals-and-sandbox \
            --cd "$PWD" \
            "$PROMPT"
        ;;
    *)
        echo "Unsupported RALPH_AGENT: $RALPH_AGENT"
        exit 1
        ;;
esac

# -----------------------------
# Verify the coding agent committed
# -----------------------------
NEW_COMMIT=$(git rev-parse HEAD)

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    echo
    echo "$RALPH_AGENT did not create a commit for:"
    echo "  $ISSUE_FILE"
    echo
    echo "Any work it left behind is uncommitted and shown below."
    echo "Inspect, then either commit it and mark the issue 'done', or"
    echo "discard it (git checkout -- . ; git clean -fd) before re-running."
    echo
    git status --short
    exit 1
fi

# -----------------------------
# Ensure the issue is marked done (fallback if the coding agent forgot).
# Guarantees the loop makes progress and never re-picks this issue.
# -----------------------------
if grep -qiE "^Status:[[:space:]]*${READY_STATUS}[[:space:]]*$" "$ISSUE_FILE"; then
    echo
    echo "Issue still marked '${READY_STATUS}'; marking '${DONE_STATUS}'."
    sed -i.bak -E "s/^Status:[[:space:]]*${READY_STATUS}[[:space:]]*$/Status: ${DONE_STATUS}/I" "$ISSUE_FILE"
    rm -f "${ISSUE_FILE}.bak"
    git add "$ISSUE_FILE"
    git commit -m "chore: mark $(basename "$ISSUE_FILE" .md) ${DONE_STATUS}"
fi

CURRENT_BRANCH=$(git branch --show-current)

# -----------------------------
# Push to the existing remote (opt-in; finding H4).
# Default is NOT to push, so unreviewed agent commits never land on origin
# automatically. Set RALPH_AUTO_PUSH=1 to enable. We never create a remote.
# -----------------------------
if [ "${RALPH_AUTO_PUSH:-0}" != "1" ]; then
    echo
    echo "Skipping push (set RALPH_AUTO_PUSH=1 to enable). Commit is saved locally."
elif git remote get-url origin >/dev/null 2>&1; then
    echo
    echo "Pushing latest commit..."
    if ! git push --set-upstream origin "$CURRENT_BRANCH"; then
        echo "Push failed (continuing; commit is saved locally)."
    fi
else
    echo
    echo "No 'origin' remote configured; skipping push."
fi

echo
echo "======================================"
echo "Ralph iteration complete!"
echo "======================================"

FINAL_LABEL=$(grep -m1 -iE '^Status:' "$ISSUE_FILE" | sed -E 's/^Status:[[:space:]]*//I')

echo
echo "Issue: $ISSUE_FILE"
echo "Triage label: ${STATUS_LABEL} -> ${FINAL_LABEL}"

echo
echo "Latest commit:"
git --no-pager log --oneline -1

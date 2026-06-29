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
# Exit codes:
#   0  one issue implemented and committed
#   2  no `ready-for-agent` issues remain (loop should stop)
#   1  error (dirty tree, missing config, no commit, ...)
#########################################

READY_STATUS="ready-for-agent"
DONE_STATUS="done"

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
    touch .gitkeep
    git add .
    git commit -m "chore: initial commit"
fi

# -----------------------------
# Working tree must be clean
#
# Use porcelain so UNTRACKED files also count as dirty. A killed Claude
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
# Launch Claude
# -----------------------------
claude -p --verbose --dangerously-skip-permissions "$PROMPT"

# -----------------------------
# Verify Claude committed
# -----------------------------
NEW_COMMIT=$(git rev-parse HEAD)

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    echo
    echo "Claude did not create a commit for:"
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
# Ensure the issue is marked done (fallback if Claude forgot).
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
# Push to the existing remote (best effort).
# We never create a remote automatically.
# -----------------------------
if git remote get-url origin >/dev/null 2>&1; then
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

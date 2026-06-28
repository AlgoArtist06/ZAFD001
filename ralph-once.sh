#!/usr/bin/env bash
set -euo pipefail

#########################################
# Ralph Loop (one issue only)
#########################################

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
# -----------------------------
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo
    echo "Working tree is dirty."
    echo "Commit or stash your changes before running Ralph."
    exit 1
fi

OLD_COMMIT=$(git rev-parse HEAD)

# -----------------------------
# Fetch next GitHub issue
# -----------------------------
ISSUE=$(gh issue list \
    --state open \
    --limit 1 \
    --json number,title,body \
    | jq '.[0]')

if [ "$ISSUE" = "null" ]; then
    echo "No open GitHub issues."
    exit 0
fi

NUMBER=$(echo "$ISSUE" | jq -r '.number')
TITLE=$(echo "$ISSUE" | jq -r '.title')
BODY=$(echo "$ISSUE" | jq -r '.body')

echo
echo "======================================"
echo "Implementing Issue #$NUMBER"
echo "$TITLE"
echo "======================================"
echo

PROMPT=$(cat <<EOF
Implement GitHub Issue #$NUMBER.

Title:
$TITLE

Description:
$BODY

Requirements:

- Immediately invoke /tdd.
- Work ONLY on this issue.
- Follow Red → Green → Refactor.
- Keep implementation minimal.
- Do not modify unrelated files.
- Run all project tests.
- Run lint.
- Run typecheck.
- Stage all modified files.
- Create ONE conventional git commit.
- Do NOT begin another issue.
- Exit after committing.
EOF
)

# -----------------------------
# Launch Claude
# -----------------------------
claude "$PROMPT"

# -----------------------------
# Verify Claude committed
# -----------------------------
NEW_COMMIT=$(git rev-parse HEAD)

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    echo
    echo "Claude did not create a commit."
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)

# -----------------------------
# Ensure GitHub remote exists
# -----------------------------
if ! git remote get-url origin >/dev/null 2>&1; then

    REPO_NAME=$(basename "$PWD")

    echo
    echo "Creating private GitHub repository '$REPO_NAME'..."

    gh repo create "$REPO_NAME" \
        --private \
        --source=. \
        --remote=origin \
        --push

else

    echo
    echo "Pushing latest commit..."

    git push --set-upstream origin "$CURRENT_BRANCH"

fi

echo
echo "======================================"
echo "Ralph iteration complete!"
echo "======================================"

echo
echo "Latest commit:"
git --no-pager log --oneline -1

echo
echo "GitHub:"
gh repo view --web
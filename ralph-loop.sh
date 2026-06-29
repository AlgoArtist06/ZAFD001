#!/usr/bin/env bash
set -euo pipefail

#########################################
# Ralph Continuous Loop
#########################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RALPH_ONCE="$SCRIPT_DIR/ralph-once.sh"

if [ ! -x "$RALPH_ONCE" ]; then
    echo "Cannot find executable:"
    echo "$RALPH_ONCE"
    exit 1
fi

ITERATION=1

echo "===================================="
echo "Starting Ralph Loop"
echo "===================================="

while true; do

    echo
    echo "------------------------------------"
    echo "Iteration $ITERATION"
    echo "------------------------------------"

    set +e
    "$RALPH_ONCE"
    STATUS=$?
    set -e

    case $STATUS in

        0)
            echo
            echo "Iteration $ITERATION completed successfully."

            ITERATION=$((ITERATION + 1))

            echo
            echo "Sleeping for 5 seconds before next issue..."
            sleep 5
            ;;

        2)
            echo
            echo "No remaining 'ready-for-agent' issues in .scratch/."
            echo "Ralph loop complete."
            exit 0
            ;;

        *)
            echo
            echo "Ralph stopped on iteration $ITERATION because an error occurred."
            echo "Exit code: $STATUS"
            echo
            echo "Common causes:"
            echo "  - Claude finished without committing (it printed the leftover"
            echo "    files above); recover or discard them before re-running."
            echo "  - The working tree was already dirty at the start of the run."
            echo
            echo "The loop halts here on purpose so leftover state does not leak"
            echo "into the next issue. Fix the cause, then re-run ./ralph-loop.sh."
            exit $STATUS
            ;;

    esac

done
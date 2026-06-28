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
            echo "No remaining GitHub issues."
            echo "Ralph loop complete."
            exit 0
            ;;

        *)
            echo
            echo "Ralph stopped because an error occurred."
            echo "Exit code: $STATUS"
            exit $STATUS
            ;;

    esac

done
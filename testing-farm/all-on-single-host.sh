#! /bin/bash

toplevel=$(readlink -f "$(dirname "$0")")
tests_dir=$toplevel/../beaker-tests/Sanity/copr-cli-basic-operations
export PATH=$PATH:$tests_dir
cd "$tests_dir" || exit 1

OWNER=$(copr-cli whoami)
export OWNER

FRONTEND_PUBLIC_HOST=$(curl -4 ifconfig.me)
# copr-frontend thinks it's hosting publicly, this e.g., affects how .repo files
# are generated.
export FRONTEND_PUBLIC_HOST
# we do access Frontend on localhost
export FRONTEND_HOST=127.0.0.1
export FRONTEND_URL=https://$FRONTEND_HOST
export BACKEND_URL=$FRONTEND_URL
export VENDOR="Testing Copr - user single-host-testing"

SCRIPT_DIR="."
LOG_DIR="./logs"

PIDS=()
# Global map to store the script name indexed by its PID
declare -A PID_TO_NAME

# Counter for tracking total jobs launched
JOB_COUNT=0
FAILURE_COUNT=0
FINAL_EXIT_CODE=0

mkdir -p "$LOG_DIR"
echo "--- Starting Event-Driven Parallel Execution ---"

if test $# -eq 0; then
    # list all scripts
    set -- "$SCRIPT_DIR"/*.sh
fi

for script; do
    case $script in
    *all-in-tmux*|*runtest-production.sh|*upload_authentication.sh)
        continue
        ;;
    *runtest-storage*)
        continue
        ;;
    esac

    if ! test -e "$script"; then
        echo -e "❌ FAILED: wrong $script file"
        find "$SCRIPT_DIR" -name '*.sh'
        exit 1
    fi

    script_name=$(basename "$script")
    LOG_FILE="$LOG_DIR/${script_name}.log"

    echo "Launching: $script_name (Logs: $LOG_FILE)"

    # Run in background and redirect output
    bash "$script" > "$LOG_FILE" 2>&1 &

    # Store PID and map the PID to the script name
    PIDS+=($!)
    PID_TO_NAME[$!]="$script_name"
    JOB_COUNT=$((JOB_COUNT + 1))
done

echo -e "\n--- Processing Results (Order of Completion) ---\n"

FAILED_JOBS=()

# Loop while there are active background jobs (PIDs array is not empty)
while (( JOB_COUNT > 0 )); do
    # Use wait -n to wait for *any* job to finish and get its PID
    # -n will block until at least one job changes state.
    wait -n -p finished_pid
    exit_code=$?

    # Retrieve the name and log file path using the PID
    script_name="${PID_TO_NAME[$finished_pid]}"
    LOG_FILE="$LOG_DIR/${script_name}.log"

    JOB_COUNT=$((JOB_COUNT - 1))

    if [ $exit_code -ne 0 ]; then
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        FINAL_EXIT_CODE=1  # Set final exit code to 1 if any script failed

        echo -e "❌ FAILED: $script_name (Exit Code: $exit_code, log $LOG_FILE) - Completed at $(date +%H:%M:%S)"
        FAILED_JOBS+=( "$script_name" )
        # print the log early, we can react to failure ASAP (while the rest of
        # tests is finishing).
        cat "$LOG_FILE"
    else
        echo -e "✅ SUCCESS: $script_name - Completed at $(date +%H:%M:%S)"
    fi

    # Unset the entry from the map to clean up
    unset "PID_TO_NAME[$finished_pid]"
done

for job in "${FAILED_JOBS[@]}"; do
    echo -e "❌ FAILED: $job"
done

echo -e "\n--- FINAL REPORT ---"
echo "Total Scripts: ${#PIDS[@]}"
echo "Successful: $(( ${#PIDS[@]} - FAILURE_COUNT ))"
echo "Failed: $FAILURE_COUNT"

if [ $FINAL_EXIT_CODE -ne 0 ]; then
    echo -e "\n🚨 ONE OR MORE SCRIPTS FAILED. EXITING WITH CODE 1."
    exit 1
else
    echo -e "\n🎉 ALL SCRIPTS COMPLETED SUCCESSFULLY."
    exit 0
fi

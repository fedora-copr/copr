#!/bin/sh -eux

RESULTS_DIR=/var/lib/copr/public_html/results
BUILD_LOGS_DIR=/var/tmp/copr-build-logs

# Copy builder-live.log, backend.log, etc. out of the results directory.  The
# tests delete their projects (and thus the logs) in the cleanup phase, so we
# need to grab them while the tests are still running.  Never delete anything
# from BUILD_LOGS_DIR.
snapshot_build_logs()
{
    rsync -a --prune-empty-dirs \
        --include='*/' --include='*.log' --include='*.log.gz' --exclude='*' \
        "$RESULTS_DIR/" "$BUILD_LOGS_DIR/" &>/dev/null || :
}

# Store service logs into $TMT_TEST_DATA, tmt syncs that directory into the
# Testing Farm artifacts.  The test machine is thrown away after the run, so
# this is the only chance to get data for debugging the failures.
collect_logs()
{
    if test -n "${SNAPSHOT_PID:-}"; then
        kill "$SNAPSHOT_PID" || :
        wait "$SNAPSHOT_PID" || :
    fi
    test -n "${TMT_TEST_DATA:-}" || return 0
    snapshot_build_logs
    mkdir -p "$TMT_TEST_DATA"
    tar -czf "$TMT_TEST_DATA/build-logs.tar.gz" -C "$BUILD_LOGS_DIR" . || :
    tar -czf "$TMT_TEST_DATA/service-logs.tar.gz" --ignore-failed-read \
        /var/log/copr-backend \
        /var/log/copr-frontend \
        /var/log/copr-keygen \
        /var/log/copr-dist-git \
        /var/log/httpd \
        /var/log/resallocserver \
        ./beaker-tests/Sanity/copr-cli-basic-operations/logs \
        || :
    journalctl -b --no-pager | gzip > "$TMT_TEST_DATA/journal.txt.gz" || :
}

cd "$(git rev-parse --show-toplevel)"
trap collect_logs EXIT

mkdir -p "$BUILD_LOGS_DIR"
(
    set +x
    trap 'exit 0' TERM
    while :; do
        snapshot_build_logs
        sleep 10
    done
) &
SNAPSHOT_PID=$!

rpm -qa | grep copr

lscpu || :
lsmem || :
swapon || :
dnf copr list
cat /etc/yum.repos.d/*.repo

./testing-farm/all-on-single-host.sh

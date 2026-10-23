#!/bin/sh -eux

RESULTS_DIR=/var/lib/copr/public_html/results
BUILD_LOGS_DIR=/var/tmp/copr-build-logs
BEAKER_LOGS_DIR=./beaker-tests/Sanity/copr-cli-basic-operations/logs

# Copy builder-live.log, backend.log, etc. out of the results directory.  The
# tests delete their projects (and thus the logs) in the cleanup phase, so we
# need to grab them while the tests are still running.  Never delete anything
# from BUILD_LOGS_DIR - it is the accumulator that keeps the logs of the
# already deleted projects, the rsync below never removes files.
snapshot_build_logs()
{
    rsync -a --prune-empty-dirs \
        --include='*/' --include='*.log' --include='*.log.gz' --exclude='*' \
        "$RESULTS_DIR/" "$BUILD_LOGS_DIR/" &>/dev/null || :
}

# Incrementally sync the build logs and the beaker test logs into
# $TMT_TEST_DATA as plain files (tmt syncs that directory into the Testing
# Farm artifacts).  The test machine is thrown away after the run, so this
# is the only chance to get data for debugging the failures.  Yes, this
# creates hundreds to thousands of files in the data directory - that is
# fine, and it keeps the logs browsable one by one in the artifacts.
sync_data_logs()
{
    test -n "${TMT_TEST_DATA:-}" || return 0
    mkdir -p "$TMT_TEST_DATA"
    rsync -a "$BUILD_LOGS_DIR/" "$TMT_TEST_DATA/build-logs/" || :
    rsync -a "$BEAKER_LOGS_DIR/" "$TMT_TEST_DATA/beaker-test-logs/" || :
}

# The service logs are appended to, so every sync re-copies the grown files
# whole - sync them on a coarser cadence than sync_data_logs.  Note rsync
# does not create intermediate destination directories, only the last
# component - the service-logs/ parent has to exist beforehand.
sync_service_logs()
{
    test -n "${TMT_TEST_DATA:-}" || return 0
    mkdir -p "$TMT_TEST_DATA/service-logs"
    rsync -a /var/log/copr-backend/ "$TMT_TEST_DATA/service-logs/copr-backend/" || :
    rsync -a /var/log/copr-frontend/ "$TMT_TEST_DATA/service-logs/copr-frontend/" || :
    rsync -a /var/log/copr-keygen/ "$TMT_TEST_DATA/service-logs/copr-keygen/" || :
    rsync -a /var/log/copr-dist-git/ "$TMT_TEST_DATA/service-logs/copr-dist-git/" || :
    rsync -a /var/log/httpd/ "$TMT_TEST_DATA/service-logs/httpd/" || :
    rsync -a /var/log/resallocserver/ "$TMT_TEST_DATA/service-logs/resallocserver/" || :
}

# The journal cannot be rsynced, it has to be exported (and compressed) as
# a whole.  Never write into the final file name directly - tmt may be
# pulling the directory at the very moment we are writing - write into a
# temporary file and rename.
update_journal_archive()
{
    test -n "${TMT_TEST_DATA:-}" || return 0
    mkdir -p "$TMT_TEST_DATA"
    if (set -o pipefail; journalctl -b --no-pager 2>/dev/null \
        | gzip -1 > "$TMT_TEST_DATA/journal.txt.gz.tmp"); then
        mv "$TMT_TEST_DATA/journal.txt.gz.tmp" "$TMT_TEST_DATA/journal.txt.gz"
    else
        rm -f "$TMT_TEST_DATA/journal.txt.gz.tmp"
    fi
}

# Final refresh of everything, for the normal (not killed) test exit.
# All the output goes into $DUMPER_LOG - it must never leak into the test
# output (tmt's output.txt).
collect_logs()
{
    if test -n "${SNAPSHOT_PID:-}"; then
        kill "$SNAPSHOT_PID" || :
        wait "$SNAPSHOT_PID" || :
    fi
    {
        snapshot_build_logs
        sync_data_logs
        sync_service_logs
        update_journal_archive
    } >>"$DUMPER_LOG" 2>&1
}

cd "$(git rev-parse --show-toplevel)"

# Everything the background log dumper below prints (rsync warnings about
# files vanishing when the tests delete their projects, etc.) must stay out
# of the test output - keep it in a separate log file, inside $TMT_TEST_DATA
# so that it is synced into the Testing Farm artifacts, too.  Defined
# before the traps, so that collect_logs can never run with it unset.
if test -n "${TMT_TEST_DATA:-}"; then
    mkdir -p "$TMT_TEST_DATA"
    DUMPER_LOG=$TMT_TEST_DATA/log-dumper.log
else
    DUMPER_LOG=/var/tmp/copr-test-log-dumper.log
fi
: > "$DUMPER_LOG"

# tmt enforces the test duration limit by SIGKILL-ing the whole process group
# of the test command (see Command.run() in tmt/utils/__init__.py) - no signal
# that a trap could catch is ever delivered to this script, so on the duration
# limit the traps below have no chance to run and all the logs would be lost.
# To get the logs out of a killed test, keep fresh copies of the logs in
# $TMT_TEST_DATA at all times:  tmt pulls the data directory even after it
# kills the test, and picks up whatever we managed to sync.  The traps are
# still kept as a best effort for the cases where the script does get a
# catchable signal (manual runs, TERM before the hard kill, HUP from the
# torn-down pty).
trap collect_logs EXIT
trap 'exit 143' TERM HUP

mkdir -p "$BUILD_LOGS_DIR"
# The beaker test logs dir is normally created by all-on-single-host.sh a
# bit later - create it upfront so the rsync in the dumper loop below does
# not warn about a missing source directory in the first iterations.
mkdir -p "$BEAKER_LOGS_DIR"

(
    set +x
    trap 'exit 0' TERM HUP
    i=0
    while :; do
        snapshot_build_logs
        sync_data_logs
        i=$((i + 1))
        # The service logs every ~5 minutes and the journal (the largest
        # and the slowest one to export) every ~10 minutes.
        if test $((i % 30)) -eq 0; then
            sync_service_logs
        fi
        if test $((i % 60)) -eq 0; then
            update_journal_archive
        fi
        sleep 10
    done
) >>"$DUMPER_LOG" 2>&1 &
SNAPSHOT_PID=$!

rpm -qa | grep copr

lscpu || :
lsmem || :
swapon || :
dnf copr list
cat /etc/yum.repos.d/*.repo

./testing-farm/all-on-single-host.sh

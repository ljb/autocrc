#!/usr/bin/env bash
# One pass over every scenario, comparing the exit status against what README.md
# says it should be. The symlink loop is skipped: with -L it never terminates.
set -u

cd "$(dirname "$0")/scenarios" || exit 1

pass=0
fail=0

run() {
    local expected=$1 dir=$2
    shift 2
    local output status
    output=$(cd "$dir" && autocrc "$@" 2>&1)
    status=$?

    if [ "$status" -eq "$expected" ]; then
        printf '\033[32m  ok  \033[0m exit=%-3s %s %s\n' "$status" "$dir" "$*"
        pass=$((pass + 1))
    else
        printf '\033[31m FAIL \033[0m exit=%-3s (expected %s) %s %s\n' "$status" "$expected" "$dir" "$*"
        printf '%s\n' "$output" | sed 's/^/        /'
        fail=$((fail + 1))
    fi
}

echo "CRC sources"
run 1 01-filename-crcs
run 3 02-sfv-basic

echo
echo "Flags that change how sfv paths are read"
run 2 03-sfv-windows-paths
run 0 03-sfv-windows-paths -x
run 2 04-sfv-ignore-case
run 0 04-sfv-ignore-case -i

echo
echo "Permissions and unusual files"
if [ "$(id -u)" -eq 0 ]; then
    echo "  (skipped: running as root bypasses the permission bits)"
else
    run 4 05-permissions
    run 4 05-permissions -r .
fi
run 3 06-empty-and-missing
run 8 11-odd-arguments a-fifo
run 8 11-odd-arguments typo.sfv

echo
echo "Links and traversal"
run 0 07-symlinks
run 0 07-symlinks -r .
run 0 07-symlinks -r -L .
run 0 08-recursive -r .

echo
echo "Exit status bits"
run 1 09-exit-codes/status-1-mismatch
run 2 09-exit-codes/status-2-missing
if [ "$(id -u)" -ne 0 ]; then
    run 4 09-exit-codes/status-4-read-error
    run 7 09-exit-codes/status-7-everything
fi

echo
echo "Quiet mode says nothing when a directory is clean"
run 0 08-recursive -q -r alpha

echo
printf '%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]

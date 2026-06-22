#!/usr/bin/env bash

pass() {
    echo "PASS: $*"
}

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

assert_file_exists() {

    local f="$1"

    [[ -f "$f" ]] \
        && pass "file exists: $f" \
        || fail "missing file: $f"
}

assert_dir_exists() {

    local d="$1"

    [[ -d "$d" ]] \
        && pass "dir exists: $d" \
        || fail "missing dir: $d"
}

assert_contains() {

    local file="$1"
    local pattern="$2"

    grep -qE "$pattern" "$file" \
        && pass "$file contains $pattern" \
        || fail "$file missing $pattern"
}

assert_not_empty() {

    local file="$1"

    [[ -s "$file" ]] \
        && pass "$file not empty" \
        || fail "$file empty"
}

assert_equals() {

    local expected="$1"
    local actual="$2"

    [[ "$expected" == "$actual" ]] \
        && pass "$expected == $actual" \
        || fail "expected=$expected actual=$actual"
}

assert_rc() {

    local expected="$1"

    shift

    set +e
    "$@"
    local rc=$?
    set -e

    [[ "$rc" -eq "$expected" ]] \
        && pass "rc=$rc" \
        || fail "expected rc=$expected actual=$rc"
}

assert_json_key() {

    local file="$1"
    local key="$2"

    local filter

    if [[ "$key" =~ ^\. ]]
    then
        filter="$key"
    else
        filter=".$key"
    fi

    jq -e "$filter" "$file" >/dev/null \
        && pass "json key exists: $key" \
        || fail "json key missing: $key"
}

assert_json_value() {

    local file="$1"
    local key="$2"
    local expected="$3"

    local actual

    actual=$(
        jq -r ".${key}" "$file"
    )

    [[ "$actual" == "$expected" ]] \
        && pass "$key=$expected" \
        || fail "$key expected=$expected actual=$actual"
}

assert_tsv_rows() {

    local file="$1"
    local expected="$2"

    local rows

    rows=$(
        tail -n +2 "$file" | wc -l
    )

    [[ "$rows" -eq "$expected" ]] \
        && pass "rows=$rows" \
        || fail "expected rows=$expected actual=$rows"
}

assert_grep_count() {

    local file="$1"
    local pattern="$2"
    local expected="$3"

    local actual

    actual=$(
        grep -cE "$pattern" "$file" || true
    )

    [[ "$actual" -eq "$expected" ]] \
        && pass "count=$actual pattern=$pattern" \
        || fail "expected count=$expected actual=$actual"
}

assert_file_not_exists() {

    local f="$1"

    [[ ! -e "$f" ]] \
        && pass "not exists: $f" \
        || fail "unexpected file: $f"
}

assert_not_exists() {

    local f="$1"

    [[ ! -e "$f" ]] \
        && pass "not exists: $f" \
        || fail "exists: $f"
}

assert_stdout_contains() {

    local text="$1"
    local pattern="$2"

    echo "$text" \
        | grep -q -- "$pattern"

    pass "stdout contains: $pattern"
}

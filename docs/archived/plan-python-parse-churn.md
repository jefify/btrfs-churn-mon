# Plan: Replace parse-churn.awk with Python

## Goal

Replace `lib/parse-churn.awk` with `lib/parse_churn.py` — unify data processing
in a single language (Python), improve testability, and prepare for future extensions
(rename, truncate, richer aggregation).

## Contract (derived from AWK behavior)

### Input

Text file from `btrfs receive --dump` output. One operation per line.
Relevant line formats:

```
write ./path/to/file offset=0 len=1234
clone ./path/to/file offset=0 len=5678 from=./other clone_offset=0 clone_len=5678
```

### Processing Rules

1. Match lines starting with `write ` or `clone ` (at column 0)
2. Extract path from field 2 (space-separated)
3. Strip `./` prefix from path
4. Extract bytes from `len=(\d+)` anywhere in the line
5. Lines without `len=` → skip silently
6. Unrecognized operations → skip silently
7. Aggregate: sum bytes per unique path

### Output

Tab-separated, unsorted, no header:
```
BYTES\tPATH
```
(Sorting is done by the caller: `| sort -nr`)

### Interface

**CLI (drop-in for AWK):**
```bash
python3 lib/parse_churn.py DUMPFILE
# or
cat DUMPFILE | python3 lib/parse_churn.py -
```

**Library (for pytest):**
```python
from lib.parse_churn import parse_line, aggregate, format_output
```

### Edge Cases

| Case | Behavior |
|------|----------|
| Empty file | No output (exit 0) |
| Lines without `len=` | Skip |
| Unknown operations (rename, mkfile, etc) | Skip |
| Multiple writes to same path | Sum bytes |
| Path with `./` prefix | Strip |
| Path with spaces | Known limitation (field split at space) — document, match AWK behavior |
| Very large files (>100MB dump) | Stream line-by-line, O(unique_paths) memory |

## Test Strategy

- **Location:** `tests/test_parse_churn.py` (pytest)
- **Config:** `pyproject.toml` with `[tool.pytest.ini_options]`
- **Fixtures:** inline strings (same as AWK unit tests use)

### Test Cases

1. `test_parse_write_line` — single write line parsed correctly
2. `test_parse_clone_line` — single clone line parsed correctly
3. `test_skip_unknown_operation` — mkfile, rename, etc ignored
4. `test_skip_line_without_len` — no len= → skip
5. `test_strip_dot_slash_prefix` — `./foo` → `foo`
6. `test_aggregate_multiple_writes_same_path` — sum bytes
7. `test_aggregate_mixed_ops` — write + clone on same path
8. `test_empty_input` — no lines → empty dict
9. `test_format_output` — dict → tab-separated string
10. `test_cli_invocation` — subprocess call matches AWK output on same fixture

## Migration Steps

1. Create `tests/test_parse_churn.py` (RED — tests fail, no implementation)
2. Create `lib/parse_churn.py` (GREEN — tests pass)
3. Create `pyproject.toml` with pytest config
4. Verify: `pytest tests/test_parse_churn.py` all pass
5. Update `analyse-churn.sh` to call Python instead of AWK
6. Verify: `bin/test-ci.sh` still GREEN (integration tests use the parser)
7. Remove `lib/parse-churn.awk`
8. Commit: `refactor: replace parse-churn.awk with Python`

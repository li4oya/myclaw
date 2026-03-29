---
name: verification-command-execution-verification-shell-1-2-verification-3-verification-script
description: Auto-evolved skill for 帮我阅读paper下的pdf获取论文中表四的所有文章，并且要 获取到对应参考文献的完整标题。可以分成两个任务，一个任务提取表格4中的信息及其序号，另一个任务获取
---

```markdown
---
name: verification-execution
description: >
  Enables proper automated verification of task outputs. Use when tasks require
  validation of extracted data, JSON structure verification, file content checks,
  or any verification that currently fails with "command not found" errors. Triggers
  on verification failures, pending verification statuses, or when setting up
  verification for data extraction tasks.
---

# Verification Execution Skill

## Problem: Verification Commands Treated as Shell Commands

The `verification` field in task definitions should NOT be executed as shell commands.
It's meant to be a **description** of what to verify, not an executable command.

**❌ WRONG - Causes "command not found":**
```json
{
  "verification": "检查JSON输出是否包含49条记录，每条记录是否包含所有必需字段"
}
```

**✅ CORRECT - Use executable verification:**
```json
{
  "verification_script": "scripts/verify_json.js",
  "verification": "JSON file should contain 49 records with required fields"
}
```

## Verification Workflow

### 1. For Simple Checks: Use Shell Commands

```bash
# Check file exists
test -f /path/to/file.json && echo "EXISTS"

# Count lines/records
jq 'length' /path/to/file.json

# Check required fields
jq 'all(has("field1", "field2", "field3"))' /path/to/file.json
```

### 2. For Complex Checks: Use Verification Scripts

Create reusable scripts in `scripts/` directory.

### 3. Standard Verification Script Pattern

```python
#!/usr/bin/env python3
"""scripts/verify_extraction.py - Verify data extraction results"""

import json
import sys

def verify(output_file, expected_count, required_fields):
    """Verify extracted data meets criteria."""
    try:
        with open(output_file) as f:
            data = json.load(f)
        
        # Check record count
        if len(data) != expected_count:
            print(f"FAIL: Expected {expected_count} records, got {len(data)}")
            return False
        
        # Check required fields
        missing = []
        for i, record in enumerate(data):
            for field in required_fields:
                if field not in record:
                    missing.append(f"Record {i+1}: missing '{field}'")
        
        if missing:
            print(f"FAIL: Missing fields:\n" + "\n".join(missing))
            return False
        
        print("PASS: All verification checks passed")
        return True
    except FileNotFoundError:
        print(f"FAIL: File not found: {output_file}")
        return False
    except json.JSONDecodeError as e:
        print(f"FAIL: Invalid JSON: {e}")
        return False

if __name__ == "__main__":
    # Task-specific parameters
    output = sys.argv[1] if len(sys.argv) > 1 else "table4_complete.json"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 49
    fields = ["seq", "benchmark", "ref_num", "title", "authors", "year"]
    
    success = verify(output, count, fields)
    sys.exit(0 if success else 1)
```

### 4. Running Verification

```bash
# Direct script execution
python3 scripts/verify_extraction.py table4_complete.json 49

# With jq for quick checks
jq '[.[] | select(.ref_num != null)] | length' table4_complete.json
```

## Bundled Verification Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `verify_json.js` | Generic JSON structure validation | `node scripts/verify_json.js <file> <expected_count>` |
| `verify_matching.js` | Verify matching between two JSON files | `node scripts/verify_matching.js <file1> <file2>` |
| `verify_refs.py` | Verify reference mappings | `python3 scripts/verify_refs.py table4.json refs.json` |

See [scripts/README.md](scripts/README.md) for detailed script documentation.

## Task Verification Template

When creating tasks that need verification:

```json
{
  "id": 12,
  "subject": "Extract Table 4 benchmarks",
  "verification": "JSON should contain 49 benchmark records with seq, name, ref_num fields",
  "verification_script": "scripts/verify_json.js",
  "verification_params": {
    "expected_count": 49,
    "required_fields": ["seq", "benchmark", "ref_num", "domain", "modality"]
  }
}
```

## Common Verification Patterns

### Verify Record Count
```bash
jq 'length' output.json
```

### Verify All Records Have Required Fields
```bash
jq '[.[] | select(has("field1") and has("field2"))] | length == length' output.json
```

### Verify Field Values Match Pattern
```bash
jq '[.[] | select(.ref_num | test("^\\[\\d+\\]$"))] | length' output.json
```

### Cross-Reference Verification
```python
# Python example for matching verification
def verify_matching(table4_file, refs_file):
    with open(table4_file) as f:
        table4 = json.load(f)
    with open(refs_file) as f:
        refs = json.load(f)
    
    ref_nums = {r["ref_num"] for r in table4}
    available_refs = set(refs.keys())
    
    missing = ref_nums - available_refs
    if missing:
        print(f"Missing refs: {missing}")
        return False
    return True
```

## Output Verification Results

Always output structured verification results:

```json
{
  "verification_status": "passed",
  "verification_results": {
    "record_count": {"expected": 49, "actual": 49, "passed": true},
    "field_completeness": {"missing_fields": [], "passed": true},
    "reference_matching": {"matched": 49, "unmatched": [], "passed": true}
  },
  "verification_summary": "All 49 records verified successfully"
}
```
```
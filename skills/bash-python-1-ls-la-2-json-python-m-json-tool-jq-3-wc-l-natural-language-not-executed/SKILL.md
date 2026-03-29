---
name: bash-python-1-ls-la-2-json-python-m-json-tool-jq-3-wc-l-natural-language-not-executed
description: Auto-evolved skill for 帮我阅读paper下的pdf获取论文中表四的所有文章，并且要 获取到对应参考文献的完整标题。可以分成两个任务，一个任务提取表格4中的信息及其序号，另一个任务获取
---

```markdown
---
name: pdf-table-reference-extractor
description: Extract tables and references from PDF papers, build mappings between them, with mandatory verification. Use when user wants to extract specific tables (like Table 4) from academic PDFs and match entries with their complete reference information. Triggers on requests involving PDF extraction, table parsing, reference matching, or JSON output generation from papers.
---

# PDF Table & Reference Extractor

Extract structured data from academic PDFs with verified outputs.

## Workflow

### Phase 1: Extraction

1. **Read PDF** using pdfplumber or pymupdf
2. **Extract target table** (e.g., Table 4) with all columns including reference numbers
3. **Extract all references** section with sequential numbering

### Phase 2: Output Generation

Generate output files:
- `{table_name}_benchmarks.json` - Extracted table data with reference numbers
- `complete_references.json` - All references as `{number}: {full citation}`
- `{table_name}_with_references.json` - Mapped data with reference titles

### Phase 3: MANDATORY Verification (NEVER SKIP)

After each extraction task, **MUST** run actual verification commands:

```bash
# 1. Check file exists
ls -la paper/{filename}.json

# 2. Validate JSON format
python3 -m json.tool paper/{filename}.json > /dev/null && echo "JSON valid"

# 3. Count records
python3 -c "import json; print(len(json.load(open('paper/{filename}.json'))))"

# 4. Verify reference number range
python3 -c "import json; data=json.load(open('paper/{filename}.json')); refs=[r.get('ref_number') for r in data if r.get('ref_number')]; print(f'Refs: {min(refs)}-{max(refs)}, count: {len(refs)}')"
```

### Phase 4: Cross-Reference Verification

```bash
# Verify benchmark references exist in complete_references
python3 << 'EOF'
import json

benchmarks = json.load(open('paper/table4_benchmarks.json'))
refs = json.load(open('paper/complete_references.json'))

missing = []
for b in benchmarks:
    for ref_num in b.get('ref_numbers', []):
        if str(ref_num) not in refs:
            missing.append((b['name'], ref_num))

if missing:
    print(f"ERROR: {len(missing)} missing references")
    for name, ref in missing[:5]:
        print(f"  - {name}: ref {ref}")
else:
    print(f"OK: All {len(benchmarks)} benchmarks matched to references")
EOF
```

## Verification Checklist

| Check | Command | Success Criteria |
|-------|---------|-------------------|
| File exists | `ls -la` | File size > 0 |
| JSON valid | `python3 -m json.tool` | No syntax errors |
| Record count | Python count | Matches expected (e.g., 49 benchmarks) |
| Ref range | Python min/max | Matches table source |
| Cross-ref | Python lookup | 100% match rate |

## Common Issues

**Issue**: "Two-column layout causes formatting problems"
**Fix**: Post-process extracted text to merge split entries

**Issue**: "Reference numbers inconsistent"
**Fix**: Always verify against original PDF table; update expectations accordingly

**Issue**: "Verification not executed"
**Fix**: NEVER mark verification as complete without running actual commands. "(natural language - not executed)" is INVALID.

## Output Format Templates

### Benchmarks JSON
```json
[
  {
    "id": 1,
    "name": "Benchmark Name",
    "category": "Reasoning",
    "ref_numbers": [295, 296],
    "modalities": ["text"],
    "task_format": "QA"
  }
]
```

### Complete References JSON
```json
{
  "295": "Author(s). (Year). Title of paper. Conference/Journal.",
  "296": "Author(s). (Year). Another title. Conference/Journal."
}
```

### Mapped Output JSON
```json
[
  {
    "benchmark_name": "MMLU-Pro",
    "category": "Reasoning",
    "ref_numbers": [295],
    "references": [
      {
        "number": 295,
        "title": "Full Title of Reference Paper"
      }
    ]
  }
]
```

## Key Rule

**Verification is NOT complete until actual bash/python commands return successful results.** Never mark a task as "verified" based on natural language descriptions alone.
```
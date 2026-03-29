---
name: natural-language
description: Auto-evolved skill for 帮我阅读paper下的pdf获取论文中表四的所有文章，并且要 获取到对应参考文献的完整标题。可以分成两个任务，一个任务提取表格4中的信息及其序号，另一个任务获取
---

```markdown
---
name: pdf-table-extractor
description: Extract tables and references from academic PDFs. Use when user asks to extract data from tables in papers, match benchmarks with references, or process structured data from PDF documents. Handles multi-column layouts and builds data relationships.
---

# PDF Table and Reference Extractor

Extract structured data (tables, references) from academic PDFs with verification.

## Workflow

### Phase 1: Extract Table Data

```bash
# Use pdfplumber for table extraction
python3 << 'EOF'
import pdfplumber
import json

pdf_path = "paper/2026_A_Survey_of_Self_Evolving_Agents.pdf"

with pdfplumber.open(pdf_path) as pdf:
    # Find table 4 - typically around page 25-30 in survey papers
    for i, page in enumerate(pdf.pages[20:35], start=21):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            if table and len(table) > 5:
                print(f"Page {i}, Table {j}: {len(table)} rows")
EOF
```

For two-column layouts, extract raw text and parse:
```python
def extract_two_column_table(page):
    text = page.extract_text()
    lines = text.split('\n')
    # Parse based on layout patterns
    return parsed_data
```

### Phase 2: Extract References

```python
def extract_references(pdf_path, start_ref=295, end_ref=339):
    with pdfplumber.open(pdf_path) as pdf:
        # References typically in last 10-15 pages
        for page in pdf.pages[-15:]:
            text = page.extract_text()
            # Parse [N] format references
            refs = parse_reference_format(text)
    return references
```

### Phase 3: Build Relationships

```python
# Match table entries to references
def match_benchmarks_to_references(benchmarks, references):
    matched = []
    for bench in benchmarks:
        ref_nums = bench['ref_numbers']
        full_refs = [references.get(n) for n in ref_nums if n in references]
        matched.append({
            **bench,
            'reference_titles': [extract_title(r) for r in full_refs]
        })
    return matched
```

### Phase 4: Verify Output (MANDATORY)

After each extraction, verify file contents:

```bash
# Verify JSON files
python3 << 'EOF'
import json

# Check table4_benchmarks.json
with open('paper/table4_benchmarks.json') as f:
    data = json.load(f)
    assert isinstance(data, list), "Should be list"
    assert len(data) >= 40, f"Expected ~49 entries, got {len(data)}"
    for item in data:
        assert 'name' in item, "Missing name field"
        assert 'ref_numbers' in item, "Missing ref_numbers"
        assert all(295 <= n <= 339 for n in item['ref_numbers']), "Ref out of range"

# Check references
with open('paper/complete_references.json') as f:
    refs = json.load(f)
    for num in range(295, 340):
        assert str(num) in refs, f"Missing ref {num}"
        assert len(refs[str(num)]) > 10, f"Ref {num} too short"

print("✓ All verifications passed")
EOF
```

## Output Format

**table4_benchmarks.json**:
```json
[
  {
    "id": 1,
    "name": "GSM8K",
    "category": "Reasoning",
    "ref_numbers": [298, 312],
    "modality": "Text"
  }
]
```

**table4_benchmarks_with_references.json**:
```json
[
  {
    "name": "GSM8K",
    "category": "Reasoning",
    "ref_numbers": [298, 312],
    "references": [
      {"number": 298, "title": "Chain-of-thought prompting..."},
      {"number": 312, "title": "Solving math word problems..."}
    ]
  }
]
```

## Verification Checklist

- [ ] File exists and is valid JSON
- [ ] Entry count matches expected (table 4 = 49 benchmarks)
- [ ] Reference numbers in correct range [295-339]
- [ ] All references have titles
- [ ] Sampling check: verify 3-5 random entries match correctly

## Error Handling

| Issue | Solution |
|-------|----------|
| Two-column layout broken | Use `page.extract_text()` raw mode, parse line-by-line |
| Missing references | Check adjacent pages, refs may span multiple pages |
| Incomplete titles | Use regex to extract content between author and year/venue |
```
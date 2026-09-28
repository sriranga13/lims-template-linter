# lims-template-linter

Lint lab template (entity schema) JSON definitions against governance rules, before bad templates become bad data.

In regulated lab systems (LIMS, ELN, Benchling-style registries), templates define what a sample, batch, or assay record *must* look like. A template with an unknown field type, a lookup pointing at a nonexistent entity, an enum with no allowed values, or names that drift out of convention ships quietly and fails loudly: failed imports, broken integrations, audit findings. This tool catches those problems in CI, in seconds, with zero dependencies.

## Install

```bash
pip install lims-template-linter
```

Or from source:

```bash
git clone https://github.com/sriranga13/lims-template-linter
cd lims-template-linter
pip install -e ".[dev]"   # dev extra not required; pytest is the only dev dep
```

## Template format

One JSON file per entity, with a top-level `entity` object:

```json
{
  "entity": {
    "id": "ENT_SAMPLE",
    "name": "sample",
    "description": "A collected specimen routed through QC.",
    "fields": [
      {"name": "sample_id", "type": "string", "required": true,
       "description": "Lab-assigned identifier", "pattern": "^S-[0-9]{6}$"},
      {"name": "status", "type": "enum", "required": true,
       "description": "Workflow state",
       "allowed_values": ["collected", "in_progress", "released"]},
      {"name": "source_batch", "type": "lookup", "required": false,
       "description": "Batch this sample came from", "lookup_target": "ENT_BATCH"}
    ]
  }
}
```

Known field types: `string`, `text`, `integer`, `number`, `boolean`, `datetime`, `date`, `enum`, `multiselect`, `lookup`, `file`, `url`.

## Usage

```bash
lims-template-lint templates/
lims-template-lint batch.json sample.json --format json
lims-template-lint templates/ --strict   # warnings fail the build too
lims-template-lint templates/ --quiet    # summary line only
```

Sample output:

```
ERROR   FIELD-004  bad/assay_result.json[ENT_ASSAY].AssayID: unknown field type 'dropdown'; expected one of: boolean, date, datetime, enum, file, integer, lookup, multiselect, number, string, text, url
ERROR   FIELD-013  bad/assay_result.json[ENT_ASSAY].AssayID: 'required' must be true/false, got 'yes'
ERROR   FIELD-006  bad/assay_result.json[ENT_ASSAY].outcome: type 'enum' requires a non-empty 'allowed_values' list
ERROR   FIELD-011  bad/assay_result.json[ENT_ASSAY].analyst: type 'lookup' requires a 'lookup_target' entity id
WARNING ENT-004    bad/assay_result.json[ENT_ASSAY]: entity name 'Assay Result' is not snake_case
WARNING FIELD-002  bad/assay_result.json[ENT_ASSAY].AssayID: field name 'AssayID' is not snake_case
2 file(s), 2 entit(y/ies) checked: 4 error(s), 2 warning(s)
```

Exit codes: `0` clean, `1` findings that fail the build, `2` usage errors.

## Rules

| Code | Severity | What it checks |
|------|----------|----------------|
| FILE-001 | error | file is valid, readable JSON |
| ENT-001 | error | entity has a non-empty `id` |
| ENT-002 | error | entity `id` is unique across all files |
| ENT-003 | error | entity has a non-empty `name` |
| ENT-004 | warning | entity `name` is snake_case |
| ENT-005 | warning | entity has a `description` |
| ENT-006 | error | `fields` is a list when present |
| FIELD-001 | error | field has a non-empty `name` |
| FIELD-002 | warning | field `name` is snake_case |
| FIELD-003 | error | field names are unique within an entity (case-insensitive) |
| FIELD-004 | error | field `type` is one of the known types |
| FIELD-005 | warning | field has a `description` |
| FIELD-006 | error | `enum`/`multiselect` fields define a non-empty `allowed_values` list |
| FIELD-007 | warning | `allowed_values` on a non-enum type is ignored |
| FIELD-008 | error | no duplicate entries in `allowed_values` |
| FIELD-009 | error | `allowed_values` is a list of strings |
| FIELD-010 | error | `pattern` compiles as a regular expression |
| FIELD-011 | error | `lookup` fields declare a `lookup_target` |
| FIELD-012 | error | `lookup_target` resolves to an entity id in the template set |
| FIELD-013 | error | `required` is a boolean |
| CROSS-001 | warning | no two entities share a name differing only by case |

Cross-file checks (`ENT-002`, `FIELD-012`) work when you lint the whole template directory at once, which is how it is meant to run in CI.

## Use as a library

```python
from template_linter import lint_files, format_text

report = lint_files(["templates/batch.json", "templates/sample.json"])
print(format_text(report))
print("errors:", len(report.errors), "warnings:", len(report.warnings))
```

## CI example

```yaml
- name: Lint lab templates
  run: |
    pip install lims-template-linter
    lims-template-lint templates/ --strict
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest
pytest -q
```

35 tests, all green. The package itself is stdlib-only; pytest is only needed to run the suite.

## License

MIT. See [LICENSE](LICENSE).

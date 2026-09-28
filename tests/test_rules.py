"""Tests for the lint rules."""
from template_linter.rules import lint_documents
from template_linter.schema import TemplateDocument, TemplateEntity, TemplateField


def _doc(entity_dict=None, path="t.json", parse_ok=True):
    ent = None
    if entity_dict is not None:
        fields = [TemplateField(**f) if isinstance(f, dict) else f
                  for f in entity_dict.get("fields", [])]
        ent = TemplateEntity(
            id=entity_dict.get("id"),
            name=entity_dict.get("name"),
            description=entity_dict.get("description"),
            fields=fields,
            raw={"fields": entity_dict.get("fields", [])}
            | ({"description": entity_dict["description"]}
               if "description" in entity_dict else {}),
        )
    return TemplateDocument(path=path, parse_ok=parse_ok, entity=ent)


def _field(**kw):
    base = {"name": "f1", "type": "string", "description": "a field"}
    base.update(kw)
    base["raw"] = {k: v for k, v in base.items() if k != "raw"}
    return TemplateField(**base)


def _codes(report):
    return [(f.code, f.severity) for f in report.findings]


def good_entity(**kw):
    ent = {
        "id": "ENT_SAMPLE",
        "name": "sample",
        "description": "A collected specimen.",
        "fields": [
            _field(name="sample_id", type="string", required=True,
                   pattern="^S-[0-9]{6}$"),
            _field(name="status", type="enum",
                   allowed_values=["collected", "released"]),
        ],
    }
    ent.update(kw)
    return ent


def test_clean_template_has_no_findings():
    r = lint_documents([_doc(good_entity())])
    assert r.findings == []
    assert r.ok()
    assert r.entities_checked == 1


def test_malformed_file_is_error():
    doc = TemplateDocument(path="bad.json", parse_ok=False,
                           parse_error="invalid JSON: boom")
    r = lint_documents([doc])
    assert _codes(r) == [("FILE-001", "error")]
    assert not r.ok()


def test_missing_entity_id():
    r = lint_documents([_doc(good_entity(id=None))])
    assert ("ENT-001", "error") in _codes(r)


def test_duplicate_entity_id_across_files():
    r = lint_documents([_doc(good_entity(), path="a.json"),
                        _doc(good_entity(), path="b.json")])
    assert ("ENT-002", "error") in _codes(r)


def test_entity_name_not_snake_case_is_warning():
    r = lint_documents([_doc(good_entity(name="Sample Name"))])
    assert ("ENT-004", "warning") in _codes(r)
    assert r.ok()  # warnings alone do not fail
    assert not r.ok(strict=True)


def test_entity_missing_description_is_warning():
    r = lint_documents([_doc(good_entity(description=None))])
    assert ("ENT-005", "warning") in _codes(r)


def test_unknown_field_type():
    r = lint_documents([_doc(good_entity(
        fields=[_field(type="dropdown")]))])
    assert ("FIELD-004", "error") in _codes(r)


def test_duplicate_field_names_case_insensitive():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="sample_id"), _field(name="SAMPLE_ID")]))])
    assert ("FIELD-003", "error") in _codes(r)


def test_enum_without_allowed_values():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="status", type="enum", allowed_values=None)]))])
    assert ("FIELD-006", "error") in _codes(r)


def test_enum_empty_allowed_values():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="status", type="enum", allowed_values=[])]))])
    assert ("FIELD-006", "error") in _codes(r)


def test_duplicate_allowed_values():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="status", type="enum",
                       allowed_values=["a", "b", "a"])]))])
    assert ("FIELD-008", "error") in _codes(r)


def test_allowed_values_on_non_enum_is_warning():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="n", allowed_values=["a"])]))])
    assert ("FIELD-007", "warning") in _codes(r)


def test_invalid_regex_pattern():
    r = lint_documents([_doc(good_entity(
        fields=[_field(pattern="([unclosed")]))])
    assert ("FIELD-010", "error") in _codes(r)


def test_lookup_without_target():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="batch", type="lookup", lookup_target=None)]))])
    assert ("FIELD-011", "error") in _codes(r)


def test_lookup_target_must_resolve():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="batch", type="lookup",
                       lookup_target="ENT_NOPE")]))])
    assert ("FIELD-012", "error") in _codes(r)


def test_lookup_target_resolves_across_files():
    batch = _doc(good_entity(id="ENT_BATCH", name="batch"), path="batch.json")
    sample = _doc(good_entity(
        fields=[_field(name="batch", type="lookup",
                       lookup_target="ENT_BATCH")]), path="sample.json")
    r = lint_documents([batch, sample])
    assert ("FIELD-012", "error") not in _codes(r)
    assert r.ok()


def test_required_must_be_boolean():
    bad = _field(required="yes")
    bad.raw = {"required": "yes"}
    r = lint_documents([_doc(good_entity(fields=[bad]))])
    assert ("FIELD-013", "error") in _codes(r)


def test_case_only_entity_name_collision_is_warning():
    r = lint_documents([
        _doc(good_entity(id="ENT_A", name="sample"), path="a.json"),
        _doc(good_entity(id="ENT_B", name="Sample"), path="b.json"),
    ])
    assert ("CROSS-001", "warning") in _codes(r)


def test_field_missing_name():
    bad = TemplateField(name=None, type="string", raw={})
    r = lint_documents([_doc(good_entity(fields=[bad]))])
    assert ("FIELD-001", "error") in _codes(r)


def test_field_missing_description_is_warning():
    r = lint_documents([_doc(good_entity(
        fields=[_field(description=None)]))])
    assert ("FIELD-005", "warning") in _codes(r)


def test_fields_not_a_list():
    ent = good_entity()
    doc = _doc(ent)
    doc.entity.raw = {"fields": "not-a-list"}
    r = lint_documents([doc])
    assert ("ENT-006", "error") in _codes(r)


def test_multiselect_requires_allowed_values():
    r = lint_documents([_doc(good_entity(
        fields=[_field(name="tags", type="multiselect",
                       allowed_values=["a", "b"])]))])
    assert r.ok()


def test_report_counts():
    r = lint_documents([_doc(good_entity(), path="a.json"),
                        _doc(good_entity(), path="b.json")])
    assert r.files_checked == 2
    assert r.entities_checked == 2
    assert len(r.errors) == 1  # ENT-002

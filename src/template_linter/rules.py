"""Governance lint rules for lab template definitions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from template_linter.schema import TemplateDocument, load_document

#: Field types the linter understands. Everything else is FIELD-004.
KNOWN_TYPES = {
    "string",
    "text",
    "integer",
    "number",
    "boolean",
    "datetime",
    "date",
    "enum",
    "multiselect",
    "lookup",
    "file",
    "url",
}

_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _is_snake(name: object) -> bool:
    return isinstance(name, str) and bool(_SNAKE_RE.match(name))


@dataclass
class Finding:
    code: str
    severity: str  # "error" or "warning"
    file: str | None
    entity: str | None
    field: str | None
    message: str


@dataclass
class LintReport:
    findings: list = dc_field(default_factory=list)
    files_checked: int = 0
    entities_checked: int = 0

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list:
        return [f for f in self.findings if f.severity == "warning"]

    def ok(self, strict: bool = False) -> bool:
        if self.errors:
            return False
        return not (strict and self.warnings)


def lint_documents(docs: list[TemplateDocument]) -> LintReport:
    report = LintReport()
    report.files_checked = len(docs)

    # First pass: register entity ids to support cross-file lookups.
    id_to_doc: dict[str, TemplateDocument] = {}
    for doc in docs:
        if not doc.parse_ok or doc.entity is None:
            report.findings.append(
                Finding(
                    code="FILE-001",
                    severity="error",
                    file=doc.path,
                    entity=None,
                    field=None,
                    message=f"could not parse template: {doc.parse_error}",
                )
            )
            continue
        ent = doc.entity
        report.entities_checked += 1
        ent_id = ent.id
        if not isinstance(ent_id, str) or not ent_id.strip():
            report.findings.append(
                Finding(
                    code="ENT-001",
                    severity="error",
                    file=doc.path,
                    entity=None,
                    field=None,
                    message="entity is missing a non-empty 'id'",
                )
            )
        elif ent_id in id_to_doc:
            report.findings.append(
                Finding(
                    code="ENT-002",
                    severity="error",
                    file=doc.path,
                    entity=ent_id,
                    field=None,
                    message=(
                        f"duplicate entity id '{ent_id}' "
                        f"(also defined in {id_to_doc[ent_id].path})"
                    ),
                )
            )
        else:
            id_to_doc[ent_id] = doc

    # Second pass: per-entity and per-field rules.
    for doc in docs:
        if not doc.parse_ok or doc.entity is None:
            continue
        _lint_entity(doc, report)

    # Cross-entity naming collision: same name modulo case.
    seen: dict[str, tuple[str, str]] = {}
    for doc in docs:
        if not doc.parse_ok or doc.entity is None:
            continue
        name = doc.entity.name
        if isinstance(name, str) and name:
            key = name.lower()
            if key in seen and seen[key][0] != name:
                report.findings.append(
                    Finding(
                        code="CROSS-001",
                        severity="warning",
                        file=doc.path,
                        entity=str(doc.entity.id),
                        field=None,
                        message=(
                            f"entity name '{name}' differs only by case from "
                            f"'{seen[key][0]}' in {seen[key][1]}; "
                            "case-only differences confuse integrations"
                        ),
                    )
                )
            else:
                seen.setdefault(key, (name, doc.path))

    # Lookup targets must resolve to a known entity id.
    for doc in docs:
        if not doc.parse_ok or doc.entity is None:
            continue
        for fld in doc.entity.fields:
            if fld.type == "lookup":
                target = fld.lookup_target
                if isinstance(target, str) and target and target not in id_to_doc:
                    report.findings.append(
                        Finding(
                            code="FIELD-012",
                            severity="error",
                            file=doc.path,
                            entity=str(doc.entity.id),
                            field=str(fld.name),
                            message=(
                                f"lookup_target '{target}' does not match any "
                                "entity id in the template set"
                            ),
                        )
                    )
    return report


def _lint_entity(doc: TemplateDocument, report: LintReport) -> None:
    ent = doc.entity
    ent_label = str(ent.id) if ent.id else None

    name = ent.name
    if not isinstance(name, str) or not name.strip():
        report.findings.append(
            Finding("ENT-003", "error", doc.path, ent_label, None,
                    "entity is missing a non-empty 'name'")
        )
    elif not _is_snake(name):
        report.findings.append(
            Finding("ENT-004", "warning", doc.path, ent_label, None,
                    f"entity name '{name}' is not snake_case")
        )
    if not isinstance(ent.description, str) or not ent.description.strip():
        report.findings.append(
            Finding("ENT-005", "warning", doc.path, ent_label, None,
                    "entity has no description; every template needs one")
        )

    raw_fields = ent.raw.get("fields")
    if "fields" in ent.raw and not isinstance(raw_fields, list):
        report.findings.append(
            Finding("ENT-006", "error", doc.path, ent_label, None,
                    "'fields' must be a list of field objects")
        )
        return

    seen_fields: dict[str, str] = {}
    for fld in ent.fields:
        _lint_field(doc, ent_label, fld, report, seen_fields)


def _lint_field(doc, ent_label, fld, report, seen_fields) -> None:
    fname = fld.name
    if not isinstance(fname, str) or not fname.strip():
        report.findings.append(
            Finding("FIELD-001", "error", doc.path, ent_label, None,
                    "a field is missing a non-empty 'name'")
        )
        return
    if not _is_snake(fname):
        report.findings.append(
            Finding("FIELD-002", "warning", doc.path, ent_label, fname,
                    f"field name '{fname}' is not snake_case")
        )
    key = fname.lower()
    if key in seen_fields:
        report.findings.append(
            Finding("FIELD-003", "error", doc.path, ent_label, fname,
                    f"duplicate field name '{fname}' "
                    f"(case-insensitive match with '{seen_fields[key]}')")
        )
    else:
        seen_fields[key] = fname

    ftype = fld.type
    if not isinstance(ftype, str) or ftype not in KNOWN_TYPES:
        report.findings.append(
            Finding("FIELD-004", "error", doc.path, ent_label, fname,
                    f"unknown field type {ftype!r}; "
                    f"expected one of: {', '.join(sorted(KNOWN_TYPES))}")
        )
    if not isinstance(fld.description, str) or not fld.description.strip():
        report.findings.append(
            Finding("FIELD-005", "warning", doc.path, ent_label, fname,
                    "field has no description; document what it means")
        )
    if "required" in fld.raw and not isinstance(fld.required, bool):
        report.findings.append(
            Finding("FIELD-013", "error", doc.path, ent_label, fname,
                    f"'required' must be true/false, got {fld.required!r}")
        )

    allowed = fld.allowed_values
    if ftype in ("enum", "multiselect"):
        if not isinstance(allowed, list) or not allowed:
            report.findings.append(
                Finding("FIELD-006", "error", doc.path, ent_label, fname,
                        f"type '{ftype}' requires a non-empty 'allowed_values' list")
            )
        else:
            if any(not isinstance(v, str) for v in allowed):
                report.findings.append(
                    Finding("FIELD-009", "error", doc.path, ent_label, fname,
                            "'allowed_values' must be a list of strings")
                )
            dupes = sorted({v for v in allowed if isinstance(v, str)
                            and allowed.count(v) > 1})
            if dupes:
                report.findings.append(
                    Finding("FIELD-008", "error", doc.path, ent_label, fname,
                            f"duplicate allowed_values: {', '.join(dupes)}")
                )
    elif allowed is not None:
        report.findings.append(
            Finding("FIELD-007", "warning", doc.path, ent_label, fname,
                    f"'allowed_values' is ignored for type '{ftype}'")
        )

    pattern = fld.pattern
    if pattern is not None:
        try:
            re.compile(pattern)
        except re.error as exc:
            report.findings.append(
                Finding("FIELD-010", "error", doc.path, ent_label, fname,
                        f"'pattern' is not a valid regex: {exc}")
            )

    if ftype == "lookup" and (
        not isinstance(fld.lookup_target, str) or not fld.lookup_target.strip()
    ):
        report.findings.append(
            Finding("FIELD-011", "error", doc.path, ent_label, fname,
                    "type 'lookup' requires a 'lookup_target' entity id")
        )


def lint_files(paths: list[str]) -> LintReport:
    """Lint template files given as paths. Never raises on bad files."""
    docs = [load_document(p) for p in paths]
    return lint_documents(docs)


def lint_templates(paths: list[str]) -> LintReport:
    """Alias kept for a friendlier public API name."""
    return lint_files(paths)


def finding_to_dict(f: Finding) -> dict:
    return {
        "code": f.code,
        "severity": f.severity,
        "file": f.file,
        "entity": f.entity,
        "field": f.field,
        "message": f.message,
    }


def format_text(report: LintReport) -> str:
    lines: list[str] = []
    for f in report.findings:
        loc = f.file or "<unknown>"
        scope = f"[{f.entity}]" if f.entity else ""
        scope += f".{f.field}" if f.field else ""
        lines.append(f"{f.severity.upper():7} {f.code:10} {loc}{scope}: {f.message}")
    summary = (
        f"{report.files_checked} file(s), {report.entities_checked} entit(y/ies) "
        f"checked: {len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )
    lines.append(summary)
    return "\n".join(lines)

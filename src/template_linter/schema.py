"""Parsing and normalization of template JSON documents.

A template file is JSON with a top-level ``entity`` object::

    {
      "entity": {
        "id": "ENT_SAMPLE",
        "name": "sample",
        "description": "A collected specimen ...",
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
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path


@dataclass
class TemplateField:
    name: object = None
    type: object = None
    required: object = None
    description: object = None
    allowed_values: object = None
    pattern: object = None
    lookup_target: object = None
    raw: dict = dc_field(default_factory=dict)


@dataclass
class TemplateEntity:
    id: object = None
    name: object = None
    description: object = None
    fields: list = dc_field(default_factory=list)
    raw: dict = dc_field(default_factory=dict)


@dataclass
class TemplateDocument:
    path: str
    parse_ok: bool
    parse_error: str = ""
    entity: TemplateEntity | None = None


def load_document(path: str | Path) -> TemplateDocument:
    """Load and lightly normalize one template file. Never raises."""
    p = Path(path)
    doc = TemplateDocument(path=str(p), parse_ok=False)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        doc.parse_error = f"cannot read file: {exc}"
        return doc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        doc.parse_error = f"invalid JSON: {exc}"
        return doc
    if not isinstance(data, dict):
        doc.parse_error = "top-level value must be a JSON object"
        return doc

    entity = TemplateEntity()
    ent = data.get("entity")
    if isinstance(ent, dict):
        entity.id = ent.get("id")
        entity.name = ent.get("name")
        entity.description = ent.get("description")
        raw_fields = ent.get("fields", [])
        if isinstance(raw_fields, list):
            for f in raw_fields:
                if isinstance(f, dict):
                    entity.fields.append(
                        TemplateField(
                            name=f.get("name"),
                            type=f.get("type"),
                            required=f.get("required"),
                            description=f.get("description"),
                            allowed_values=f.get("allowed_values"),
                            pattern=f.get("pattern"),
                            lookup_target=f.get("lookup_target"),
                            raw=f,
                        )
                    )
                else:
                    entity.fields.append(TemplateField(raw={"_invalid": f}))
        entity.raw = ent
    doc.entity = entity
    doc.parse_ok = True
    return doc

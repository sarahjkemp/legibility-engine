from __future__ import annotations

import json
from pathlib import Path

from .models import AuditRecord


def save_record(record: AuditRecord, audits_dir: Path) -> Path:
    audits_dir.mkdir(parents=True, exist_ok=True)
    path = audits_dir / f"{record.audit_id}.json"
    path.write_text(json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path


def load_record(path: Path) -> AuditRecord:
    return AuditRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_records(audits_dir: Path) -> list[AuditRecord]:
    if not audits_dir.exists():
        return []
    records: list[AuditRecord] = []
    for path in sorted(audits_dir.glob("*.json"), reverse=True):
        try:
            records.append(load_record(path))
        except Exception:
            continue
    return records


def find_record(audits_dir: Path, audit_id: str) -> AuditRecord | None:
    path = audits_dir / f"{audit_id}.json"
    if not path.exists():
        return None
    return load_record(path)

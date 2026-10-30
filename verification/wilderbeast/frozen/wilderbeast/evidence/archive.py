"""Persistent Discovery Archive — long-horizon computational discovery store.

Persists DiscoveryReceipt objects across sessions (JSON or sqlite-backed),
enabling incremental discovery where past findings seed future search horizons.
Intermediate findings (not yet promotable to MethodCatalog) are stored here
so discovery can resume, compose, and generalize over time.

Design principles:
- Append-only: discoveries are never deleted, only superseded.
- Indexed by kind, novelty, target_representation for fast retrieval.
- Single-writer JSON persistence with atomic replacement.
- Seeding: query() returns DiscoveryReceipt objects suitable for seeding new
  discovery runs; callers must verify candidates in their new context.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from wilderbeast.evidence.discovery import DiscoveryKind, DiscoveryReceipt
from wilderbeast.evidence.finding import NoveltyClass, UsefulnessClass


@dataclass
class ArchiveRecord:
    """Wrapper around a DiscoveryReceipt with persistence metadata."""
    archive_id: str
    recorded_at: str               # ISO-8601 UTC timestamp
    session_id: str
    receipt: DiscoveryReceipt

    def to_dict(self) -> dict:
        return {
            "archive_id": self.archive_id,
            "recorded_at": self.recorded_at,
            "session_id": self.session_id,
            "receipt": self.receipt.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArchiveRecord":
        r = data["receipt"]
        receipt = DiscoveryReceipt(
            kind=DiscoveryKind(r["kind"]),
            title=r["title"],
            target_representation=r["target_representation"],
            statement=r["statement"],
            formal_proof_or_witness=r["formal_proof_or_witness"],
            novelty=NoveltyClass(r.get("novelty", "N0")),
            usefulness=UsefulnessClass(r.get("usefulness", "U1")),
            reproducibility=r.get("reproducibility", {}),
            provenance=r.get("provenance", []),
        )
        return cls(
            archive_id=data["archive_id"],
            recorded_at=data["recorded_at"],
            session_id=data["session_id"],
            receipt=receipt,
        )


class DiscoveryArchive:
    """Append-only persistent store for all DiscoveryReceipt objects.

    Usage::

        archive = DiscoveryArchive("wilderbeast_archive.json")
        archive.record(receipt)
        past = archive.query(kind=DiscoveryKind.IDENTITY, min_novelty="N1")
    """

    def __init__(
        self,
        storage_path: Optional[Path | str] = None,
        session_id: Optional[str] = None,
    ):
        self.storage_path = Path(storage_path) if storage_path else None
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._records: Dict[str, ArchiveRecord] = {}
        if self.storage_path and self.storage_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def record(self, receipt: DiscoveryReceipt) -> ArchiveRecord:
        """Persist a new discovery. Returns the created ArchiveRecord."""
        return self.record_all([receipt])[0]

    def record_all(self, receipts: Sequence[DiscoveryReceipt]) -> List[ArchiveRecord]:
        """Batch record multiple discoveries atomically."""
        previous = self._records.copy()
        new_recs: List[ArchiveRecord] = []
        for receipt in receipts:
            rec = ArchiveRecord(
                archive_id=str(uuid.uuid4()),
                recorded_at=datetime.now(tz=timezone.utc).isoformat(),
                session_id=self.session_id,
                receipt=receipt,
            )
            self._records[rec.archive_id] = rec
            new_recs.append(rec)
        try:
            self._save()
        except Exception:
            self._records = previous
            raise
        return new_recs

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    _NOVELTY_ORDER = ["N0", "N1", "N2", "N3", "N4"]
    _USEFULNESS_ORDER = ["U0", "U1", "U2", "U3", "U4"]

    def query(
        self,
        kind: Optional[DiscoveryKind] = None,
        target_representation: Optional[str] = None,
        min_novelty: str = "N0",
        min_usefulness: str = "U0",
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ArchiveRecord]:
        """Return records matching filter criteria, most recent first."""
        n_thresh = self._NOVELTY_ORDER.index(min_novelty)
        u_thresh = self._USEFULNESS_ORDER.index(min_usefulness)

        results: List[ArchiveRecord] = []
        for rec in self._records.values():
            r = rec.receipt
            if kind is not None and r.kind != kind:
                continue
            if target_representation is not None and r.target_representation != target_representation:
                continue
            if self._NOVELTY_ORDER.index(r.novelty.value) < n_thresh:
                continue
            if self._USEFULNESS_ORDER.index(r.usefulness.value) < u_thresh:
                continue
            if session_id is not None and rec.session_id != session_id:
                continue
            results.append(rec)

        # Most recent first
        results.reverse()  # Later inserts win timestamp ties.
        results.sort(key=lambda x: x.recorded_at, reverse=True)
        return results[:limit]

    def seed_candidates(
        self,
        kind: Optional[DiscoveryKind] = None,
        limit: int = 10,
    ) -> List[str]:
        """Return recent discovery statements suitable for seeding new searches."""
        records = self.query(kind=kind, min_novelty="N0", min_usefulness="U1", limit=limit)
        return [r.receipt.statement for r in records]

    def all_records(self) -> List[ArchiveRecord]:
        """Return all stored records, most recent first."""
        return sorted(reversed(list(self._records.values())), key=lambda x: x.recorded_at, reverse=True)

    def __len__(self) -> int:
        return len(self._records)

    def summary(self) -> dict:
        """Return a summary dict of archive contents by kind."""
        counts: Dict[str, int] = {}
        for rec in self._records.values():
            k = rec.receipt.kind.value
            counts[k] = counts.get(k, 0) + 1
        return {"total": len(self._records), "by_kind": counts, "session": self.session_id}

    # ------------------------------------------------------------------
    # Persistence (atomic JSON write)
    # ------------------------------------------------------------------

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [rec.to_dict() for rec in self._records.values()]
        # Atomic write via temp file + rename
        fd, tmp_path = tempfile.mkstemp(
            dir=self.storage_path.parent, suffix=".tmp", prefix=".wb_archive_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp_path, self.storage_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("archive root must be a list")
            records = {}
            for item in raw:
                rec = ArchiveRecord.from_dict(item)
                records[rec.archive_id] = rec
            self._records = records
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid discovery archive: {self.storage_path}") from exc


# Global session archive (in-memory only unless a path is set)
_GLOBAL_ARCHIVE: Optional[DiscoveryArchive] = None


def get_default_archive(storage_path: Optional[Path | str] = None) -> DiscoveryArchive:
    """Return (or create) the process-wide default DiscoveryArchive."""
    global _GLOBAL_ARCHIVE
    if _GLOBAL_ARCHIVE is None:
        _GLOBAL_ARCHIVE = DiscoveryArchive(storage_path=storage_path)
    return _GLOBAL_ARCHIVE

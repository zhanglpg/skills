#!/usr/bin/env python3
"""SQLite storage layer for the paper queue."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class QueueDB:
    """SQLite-backed paper queue storage."""

    VALID_STATUSES = ("to-read", "reading", "digested")

    def __init__(self, db_path: str):
        db_path = os.path.expandvars(os.path.expanduser(db_path))
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                arxiv_id      TEXT UNIQUE,
                title         TEXT NOT NULL,
                authors       TEXT,
                abstract      TEXT,
                url           TEXT,
                source        TEXT,
                source_meta   TEXT,
                status        TEXT NOT NULL DEFAULT 'to-read',
                priority_score REAL NOT NULL DEFAULT 0,
                citation_count INTEGER NOT NULL DEFAULT 0,
                topics        TEXT,
                added_at      TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                digest_path   TEXT,
                notes         TEXT
            );

            CREATE TABLE IF NOT EXISTS score_components (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id  INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                component TEXT NOT NULL,
                value     REAL NOT NULL,
                detail    TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status);
            CREATE INDEX IF NOT EXISTS idx_papers_priority ON papers(priority_score DESC);
            CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
            CREATE INDEX IF NOT EXISTS idx_score_paper_id ON score_components(paper_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in ("topics", "source_meta"):
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_paper(
        self,
        title: str,
        arxiv_id: Optional[str] = None,
        authors: Optional[str] = None,
        abstract: Optional[str] = None,
        url: Optional[str] = None,
        source: Optional[str] = None,
        source_meta: Optional[dict] = None,
        topics: Optional[list] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Insert a paper. Returns paper id. Raises if arxiv_id already exists."""
        now = self._now()
        cur = self._conn.execute(
            """INSERT INTO papers
               (title, arxiv_id, authors, abstract, url, source, source_meta,
                topics, notes, added_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title,
                arxiv_id,
                authors,
                abstract,
                url,
                source,
                json.dumps(source_meta) if source_meta else None,
                json.dumps(topics) if topics else None,
                notes,
                now,
                now,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_paper(self, paper_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_papers(
        self,
        status: Optional[str] = None,
        topic: Optional[str] = None,
        sort_by: str = "priority_score",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM papers WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if topic:
            query += " AND topics LIKE ?"
            params.append(f"%{topic}%")

        allowed_sorts = {
            "priority_score": "priority_score DESC",
            "added_at": "added_at DESC",
            "citation_count": "citation_count DESC",
            "title": "title ASC",
        }
        query += f" ORDER BY {allowed_sorts.get(sort_by, 'priority_score DESC')}"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_status(self, paper_id: int, status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {self.VALID_STATUSES}")
        self._conn.execute(
            "UPDATE papers SET status = ?, updated_at = ? WHERE id = ?",
            (status, self._now(), paper_id),
        )
        self._conn.commit()

    def update_score(
        self, paper_id: int, score: float, components: List[Dict[str, Any]]
    ) -> None:
        now = self._now()
        self._conn.execute(
            "UPDATE papers SET priority_score = ?, updated_at = ? WHERE id = ?",
            (score, now, paper_id),
        )
        self._conn.execute(
            "DELETE FROM score_components WHERE paper_id = ?", (paper_id,)
        )
        for comp in components:
            self._conn.execute(
                """INSERT INTO score_components (paper_id, component, value, detail)
                   VALUES (?, ?, ?, ?)""",
                (paper_id, comp["component"], comp["value"], comp.get("detail")),
            )
        self._conn.commit()

    def update_citation_count(self, paper_id: int, count: int) -> None:
        self._conn.execute(
            "UPDATE papers SET citation_count = ?, updated_at = ? WHERE id = ?",
            (count, self._now(), paper_id),
        )
        self._conn.commit()

    def update_digest_path(self, paper_id: int, path: str) -> None:
        self._conn.execute(
            "UPDATE papers SET digest_path = ?, status = 'digested', updated_at = ? WHERE id = ?",
            (path, self._now(), paper_id),
        )
        self._conn.commit()

    def search(self, query: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT * FROM papers
               WHERE title LIKE ? OR abstract LIKE ?
               ORDER BY priority_score DESC""",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_score_components(self, paper_id: int) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM score_components WHERE paper_id = ?", (paper_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_topics(self) -> List[str]:
        """Get all unique topics across papers in the queue."""
        rows = self._conn.execute(
            "SELECT topics FROM papers WHERE topics IS NOT NULL"
        ).fetchall()
        all_topics: set = set()
        for row in rows:
            try:
                topics = json.loads(row["topics"])
                if isinstance(topics, list):
                    all_topics.update(t.lower() for t in topics)
            except (json.JSONDecodeError, TypeError):
                pass
        return sorted(all_topics)

    def get_stats(self) -> Dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        by_status = {}
        for row in self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM papers GROUP BY status"
        ).fetchall():
            by_status[row["status"]] = row["cnt"]
        avg_score = self._conn.execute(
            "SELECT AVG(priority_score) FROM papers WHERE status = 'to-read'"
        ).fetchone()[0]
        return {
            "total": total,
            "by_status": by_status,
            "avg_priority_to_read": round(avg_score, 2) if avg_score else 0,
            "topics": self.get_all_topics(),
        }

    def close(self) -> None:
        self._conn.close()

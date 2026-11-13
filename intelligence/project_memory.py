"""Aegis Intelligence - Persistent Project Memory Module

Maintains project architecture, technical decisions, milestone history,
and developer instructions with keyword and category retrieval.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from storage.database import db_session, row_to_dict, rows_to_dict_list

VALID_CATEGORIES = {
    "architecture", "decision", "discussion", "feature",
    "issue", "milestone", "instruction", "summary", "general"
}

VALID_CONFIDENCE = {"verified", "inferred", "hypothesized"}

class ProjectMemory:
    """Persistent project memory store with relevance ranking and retrieval."""

    @classmethod
    def record_memory(
        cls,
        project_id: str,
        title: str,
        content: str,
        category: str = "general",
        source: str = "user",
        confidence: str = "verified"
    ) -> dict:
        """Store a new piece of persistent project knowledge."""
        if not title or not title.strip():
            raise ValueError("Memory title is required.")
        if not content or not content.strip():
            raise ValueError("Memory content cannot be empty.")

        category = category.lower().strip()
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}")

        confidence = confidence.lower().strip()
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Invalid confidence '{confidence}'. Must be one of: {', '.join(sorted(VALID_CONFIDENCE))}")

        memory_id = f"mem_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO project_memory (
                    id, project_id, category, title, content, source,
                    confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id, project_id, category, title.strip(), content.strip(),
                    source.strip(), confidence, now_iso, now_iso
                )
            )

        return cls.get_memory(memory_id)

    @classmethod
    def get_memory(cls, memory_id: str) -> Optional[dict]:
        """Retrieve memory entry by ID."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM project_memory WHERE id = ?", (memory_id,)).fetchone()
            return row_to_dict(row) if row else None

    @classmethod
    def update_memory(cls, memory_id: str, **updates) -> dict:
        """Update/correct an existing memory entry."""
        current = cls.get_memory(memory_id)
        if not current:
            raise ValueError(f"Memory '{memory_id}' not found.")

        allowed_fields = {"title", "content", "category", "source", "confidence"}
        set_clauses = []
        params = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for field, val in updates.items():
            if field not in allowed_fields or val is None:
                continue

            if field == "category":
                val = val.lower().strip()
                if val not in VALID_CATEGORIES:
                    raise ValueError(f"Invalid category '{val}'.")

            elif field == "confidence":
                val = val.lower().strip()
                if val not in VALID_CONFIDENCE:
                    raise ValueError(f"Invalid confidence '{val}'.")

            set_clauses.append(f"{field} = ?")
            params.append(val)

        if not set_clauses:
            return current

        set_clauses.append("updated_at = ?")
        params.append(now_iso)
        params.append(memory_id)

        sql = f"UPDATE project_memory SET {', '.join(set_clauses)} WHERE id = ?"
        with db_session() as conn:
            conn.execute(sql, params)

        return cls.get_memory(memory_id)

    @classmethod
    def delete_memory(cls, memory_id: str) -> bool:
        """Delete a memory entry."""
        with db_session() as conn:
            cur = conn.execute("DELETE FROM project_memory WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    @classmethod
    def search_memory(
        cls,
        project_id: str,
        query: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50
    ) -> list[dict]:
        """Search project memory with keyword relevance scoring and date/category filters."""
        sql = "SELECT * FROM project_memory WHERE project_id = ?"
        params = [project_id]

        if category:
            sql += " AND category = ?"
            params.append(category.lower().strip())

        if start_date:
            sql += " AND created_at >= ?"
            params.append(start_date)

        if end_date:
            sql += " AND created_at <= ?"
            params.append(end_date)

        sql += " ORDER BY created_at DESC LIMIT ?"
        # Fetch slightly more to rank if keyword filtering
        params.append(limit * 2 if query else limit)

        with db_session() as conn:
            rows = conn.execute(sql, params).fetchall()
            items = rows_to_dict_list(rows)

        if not query or not query.strip():
            return items[:limit]

        # Calculate relevance score based on keyword frequency in title vs content
        keywords = [k.lower() for k in query.strip().split() if len(k) > 1]
        if not keywords:
            return items[:limit]

        scored_items = []
        for item in items:
            title_lower = item.get("title", "").lower()
            content_lower = item.get("content", "").lower()
            score = 0
            for kw in keywords:
                # Title matches have higher weight
                if kw in title_lower:
                    score += 5 + title_lower.count(kw) * 2
                if kw in content_lower:
                    score += 1 + content_lower.count(kw)

            if score > 0:
                item["_relevance_score"] = score
                scored_items.append(item)

        scored_items.sort(key=lambda x: x["_relevance_score"], reverse=True)
        return scored_items[:limit]

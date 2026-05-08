"""
Discard Queries — funciones de consulta para RelationDiscard.

Implementa C2d (extensión cs_get_alerts) y C2e (tool cs_get_discards)
del PLAN_MULTISESION_F47_relaciones_no_descarte_v2.md.

Queries sobre tabla graph_relationdiscard (creada en migración 0007).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from db import get_session


# ════════════════════════════════════════════════════════════════
# CONFIGURACIÓN: Umbrales parametrizables
# ════════════════════════════════════════════════════════════════

CS_DISCARD_STALE_DAYS = int(os.getenv("CS_DISCARD_STALE_DAYS", "7"))
CS_DISCARD_PROMO_OCCURRENCES = int(os.getenv("CS_DISCARD_PROMO_OCCURRENCES", "3"))
CS_DISCARD_PROMO_AGENTS = int(os.getenv("CS_DISCARD_PROMO_AGENTS", "2"))


# ════════════════════════════════════════════════════════════════
# C2d: Summary de discards para cs_get_alerts
# ════════════════════════════════════════════════════════════════

DISCARDS_SUMMARY_SQL = """
WITH discard_counts AS (
    SELECT
        reason,
        COUNT(*) as total,
        MIN(discarded_at) as oldest
    FROM graph_relationdiscard
    WHERE resolution_status = 'pending'
    GROUP BY reason
),
type_stats AS (
    SELECT
        relation_type_raw,
        COUNT(*) as occurrences,
        COUNT(DISTINCT SUBSTRING(session_id FROM 1 FOR 18)) as sessions,
        -- Extract agent suffix from session_id (formato: YYYY-MM-DD-NNN-Agent)
        COUNT(DISTINCT
            CASE
                WHEN session_id ~ '-[A-Za-z]+$'
                THEN SUBSTRING(session_id FROM '-([A-Za-z]+)$')
                ELSE 'unknown'
            END
        ) as agents
    FROM graph_relationdiscard
    WHERE resolution_status = 'pending'
      AND reason = 'unknown_type'
    GROUP BY relation_type_raw
    ORDER BY occurrences DESC
    LIMIT 3
)
SELECT
    (SELECT COALESCE(SUM(total), 0) FROM discard_counts) as total_pending,
    (SELECT COALESCE(SUM(total), 0) FROM discard_counts WHERE reason = 'unknown_type') as unknown_type_count,
    (SELECT COALESCE(SUM(total), 0) FROM discard_counts WHERE reason = 'target_not_found') as target_not_found_count,
    (SELECT MIN(oldest) FROM discard_counts) as oldest_pending,
    (SELECT json_agg(
        json_build_object(
            'type', relation_type_raw,
            'occurrences', occurrences,
            'sessions', sessions,
            'agents', agents
        ) ORDER BY occurrences DESC
    ) FROM type_stats) as top_types
"""


def get_discards_summary(project: Optional[str] = None) -> dict:
    """Retorna summary de RelationDiscard pending para cs_get_alerts.

    Usado en C2d (extensión de alertas Humandato).

    Returns:
        dict con: total_pending, by_reason, top_invalid_types, oldest_pending_days,
        types_meeting_promo_rule (según regla B1.2)
    """
    session = get_session()
    try:
        sql = DISCARDS_SUMMARY_SQL
        params = {}

        # Filtro por proyecto (si aplica)
        if project:
            sql = sql.replace(
                "WHERE resolution_status",
                "WHERE session_id LIKE :project_prefix AND resolution_status"
            )
            params["project_prefix"] = f"{project}-%"

        row = session.execute(text(sql), params).fetchone()

        if not row or row.total_pending == 0:
            return {
                "total_pending": 0,
                "by_reason": {"unknown_type": 0, "target_not_found": 0},
                "top_invalid_types": [],
                "oldest_pending_days": None,
                "types_meeting_promo_rule": 0,
            }

        # Calcular días desde el más antiguo
        oldest_days = None
        if row.oldest_pending:
            delta = datetime.now(timezone.utc) - row.oldest_pending.replace(tzinfo=timezone.utc)
            oldest_days = delta.days

        # Filtrar tipos que cumplen regla B1.2
        top_types = row.top_types or []
        meeting_rule = sum(
            1 for t in top_types
            if t["occurrences"] >= CS_DISCARD_PROMO_OCCURRENCES
            and t["agents"] >= CS_DISCARD_PROMO_AGENTS
        )

        return {
            "total_pending": row.total_pending,
            "by_reason": {
                "unknown_type": row.unknown_type_count,
                "target_not_found": row.target_not_found_count,
            },
            "top_invalid_types": top_types[:3],  # Top 3
            "oldest_pending_days": oldest_days,
            "types_meeting_promo_rule": meeting_rule,
        }

    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# C2e: Query detallada para cs_get_discards tool
# ════════════════════════════════════════════════════════════════

DISCARDS_DETAIL_SQL = """
SELECT
    rd.id as discard_id,
    rd.session_id,
    c.slug as source_concept_slug,
    rd.source_name_raw,
    rd.target_name_raw,
    rd.relation_type_raw,
    rd.reason,
    rd.resolution_status,
    rd.resolution_notes,
    rd.discarded_at,
    rd.resolved_at,
    rd.resolved_by,
    -- Determinar si target es reconciliable vía slug
    CASE
        WHEN rd.reason = 'target_not_found' THEN
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM graph_concept tc
                    WHERE tc.slug = LOWER(REGEXP_REPLACE(rd.target_name_raw, '[^a-zA-Z0-9]+', '-', 'g'))
                    LIMIT 1
                ) THEN 'slug_reconcilable'
                ELSE 'target_not_found'
            END
        ELSE NULL
    END as target_match_type
FROM graph_relationdiscard rd
LEFT JOIN graph_concept c ON c.id = rd.source_concept_id
WHERE 1=1
"""


def get_discards_detail(
    reason: Optional[str] = None,
    status: Optional[str] = "pending",
    project: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Retorna lista detallada de RelationDiscard con filtros.

    Implementa C2e (tool cs_get_discards). Campos diseñados para
    visualización según decisión Guardian B3.3 delta (contrato F47).

    Args:
        reason: filtro por Reason enum ("unknown_type" | "target_not_found")
        status: filtro por ResolutionStatus (default "pending")
        project: filtro por session_id prefix
        limit: máximo de resultados (default 50)

    Returns:
        dict con: discards (array), summary
    """
    session = get_session()
    try:
        sql = DISCARDS_DETAIL_SQL
        params = {"limit": limit}

        # Aplicar filtros
        if reason:
            sql += " AND rd.reason = :reason"
            params["reason"] = reason

        if status:
            sql += " AND rd.resolution_status = :status"
            params["status"] = status

        if project:
            sql += " AND rd.session_id LIKE :project_prefix"
            params["project_prefix"] = f"{project}-%"

        sql += " ORDER BY rd.discarded_at DESC LIMIT :limit"

        rows = session.execute(text(sql), params).fetchall()

        discards = []
        for row in rows:
            entry = {
                "discard_id": row.discard_id,
                "session_id": row.session_id,
                "source_concept_slug": row.source_concept_slug,
                "source_name_raw": row.source_name_raw,
                "target_name_raw": row.target_name_raw,
                "relation_type_raw": row.relation_type_raw,
                "reason": row.reason,
                "resolution_status": row.resolution_status,
                "discarded_at": row.discarded_at.isoformat() if row.discarded_at else None,
                "target_match_type": row.target_match_type,
                "alias_proposal": None,  # TODO: fuzzy match si reason=unknown_type
            }

            # TODO: Implementar fuzzy match para alias_proposal
            # Requiere query adicional contra RelationAlias + difflib
            # Por ahora: None

            discards.append(entry)

        # Summary agregado
        by_reason = {}
        by_status = {}
        for d in discards:
            by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
            by_status[d["resolution_status"]] = by_status.get(d["resolution_status"], 0) + 1

        oldest_days = None
        if discards and discards[-1]["discarded_at"]:
            oldest = datetime.fromisoformat(discards[-1]["discarded_at"])
            delta = datetime.now(timezone.utc) - oldest.replace(tzinfo=timezone.utc)
            oldest_days = delta.days

        return {
            "discards": discards,
            "summary": {
                "total": len(discards),
                "by_reason": by_reason,
                "by_status": by_status,
                "oldest_pending_days": oldest_days,
            }
        }

    finally:
        session.close()

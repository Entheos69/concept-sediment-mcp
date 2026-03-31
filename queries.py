"""
Concept Sediment MCP — Queries

Queries SQL para los 5 tools del MCP Server.
Usa SQLAlchemy text() para queries raw (pgvector requiere SQL directo).
Cada función abre y cierra su propia sesión (stateless).
"""
import json
import logging
import os
from datetime import date
from typing import Optional

from sqlalchemy import text

from db import get_session

logger = logging.getLogger(__name__)

# ── Embeddings (para búsqueda semántica) ──
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")


def _generate_query_embedding(query_text: str) -> list | None:
    """Genera embedding para un query de búsqueda."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query_text.strip(),
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning("Embedding generation failed: %s", e)
        return None


def _format_concept_row(row) -> dict:
    """Formatea una fila de concepto para JSON de salida."""
    return {
        "name": row.name,
        "type": row.type,
        "status": row.status,
        "description": (row.description or "")[:300],
        "weight": round(row.weight, 1),
        "last_seen": row.last_seen_at.strftime("%Y-%m-%d") if row.last_seen_at else None,
        "domains": row.domains_list if hasattr(row, "domains_list") else [],
        "projects": row.projects or [],
    }


# ════════════════════════════════════════════════════════════════
# TOOL 1: search_concepts
# ════════════════════════════════════════════════════════════════

def search_concepts_by_embedding(query: str, domain: str = None,
                                  project: str = None, limit: int = 10) -> list:
    """Búsqueda semántica por embedding en pgvector."""
    embedding = _generate_query_embedding(query)
    if not embedding:
        return []

    vec_str = "[" + ",".join(str(f) for f in embedding) + "]"

    sql = """
        SELECT
            c.id, c.name, c.type, c.status, c.description,
            c.weight, c.last_seen_at, c.projects,
            1 - (c.embedding <=> CAST(:vec AS vector)) AS similarity,
            ARRAY_AGG(DISTINCT d.slug) FILTER (WHERE d.slug IS NOT NULL) AS domains_list
        FROM graph_concept c
        LEFT JOIN graph_concept_domains cd ON cd.concept_id = c.id
        LEFT JOIN graph_domain d ON d.id = cd.domain_id
        WHERE c.embedding IS NOT NULL
          AND c.status != 'archived'
    """
    params = {"vec": vec_str, "limit": limit}

    if domain:
        sql += " AND d.slug = :domain"
        params["domain"] = domain

    if project:
        sql += " AND :project = ANY(c.projects)"
        params["project"] = project

    sql += """
        GROUP BY c.id
        HAVING 1 - (c.embedding <=> CAST(:vec AS vector)) >= 0.3
        ORDER BY c.embedding <=> CAST(:vec AS vector) ASC
        LIMIT :limit
    """

    session = get_session()
    try:
        rows = session.execute(text(sql), params).fetchall()
        results = []
        for row in rows:
            r = {
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "description": (row.description or "")[:300],
                "weight": round(row.weight, 1),
                "similarity": round(row.similarity, 4),
                "last_seen": row.last_seen_at.strftime("%Y-%m-%d") if row.last_seen_at else None,
                "domains": row.domains_list or [],
                "projects": row.projects or [],
            }
            results.append(r)
        return results
    except Exception as e:
        logger.error("Embedding search failed: %s", e)
        return []
    finally:
        session.close()


def search_concepts_by_text(query: str, domain: str = None,
                             project: str = None, limit: int = 10) -> list:
    """Búsqueda por texto (ILIKE) como fallback."""
    sql = """
        SELECT
            c.id, c.name, c.type, c.status, c.description,
            c.weight, c.last_seen_at, c.projects,
            ARRAY_AGG(DISTINCT d.slug) FILTER (WHERE d.slug IS NOT NULL) AS domains_list
        FROM graph_concept c
        LEFT JOIN graph_concept_domains cd ON cd.concept_id = c.id
        LEFT JOIN graph_domain d ON d.id = cd.domain_id
        WHERE c.status != 'archived'
          AND (c.name ILIKE :pattern OR c.description ILIKE :pattern)
    """
    params = {"pattern": f"%{query}%", "limit": limit}

    if domain:
        sql += " AND d.slug = :domain"
        params["domain"] = domain

    if project:
        sql += " AND :project = ANY(c.projects)"
        params["project"] = project

    sql += """
        GROUP BY c.id
        ORDER BY c.weight DESC
        LIMIT :limit
    """

    session = get_session()
    try:
        rows = session.execute(text(sql), params).fetchall()
        results = []
        for row in rows:
            results.append({
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "description": (row.description or "")[:300],
                "weight": round(row.weight, 1),
                "last_seen": row.last_seen_at.strftime("%Y-%m-%d") if row.last_seen_at else None,
                "domains": row.domains_list or [],
                "projects": row.projects or [],
            })
        return results
    except Exception as e:
        logger.error("Text search failed: %s", e)
        return []
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# TOOL 2: get_active_concepts
# ════════════════════════════════════════════════════════════════

def get_active_concepts(domain: str = None, project: str = None,
                        concept_type: str = None, limit: int = 15) -> dict:
    """Conceptos activos agrupados por tipo."""
    sql = """
        SELECT
            c.id, c.name, c.type, c.status, c.description,
            c.weight, c.last_seen_at, c.projects,
            ARRAY_AGG(DISTINCT d.slug) FILTER (WHERE d.slug IS NOT NULL) AS domains_list
        FROM graph_concept c
        LEFT JOIN graph_concept_domains cd ON cd.concept_id = c.id
        LEFT JOIN graph_domain d ON d.id = cd.domain_id
        WHERE c.status = 'active'
    """
    params = {}

    if domain:
        sql += " AND d.slug = :domain"
        params["domain"] = domain

    if project:
        sql += " AND :project = ANY(c.projects)"
        params["project"] = project

    if concept_type:
        sql += " AND c.type = :concept_type"
        params["concept_type"] = concept_type

    sql += """
        GROUP BY c.id
        ORDER BY c.weight DESC
    """

    session = get_session()
    try:
        rows = session.execute(text(sql), params).fetchall()

        grouped = {"principles": [], "patterns": [], "events": []}
        counts = {"principles": 0, "patterns": 0, "events": 0}

        for row in rows:
            bucket = {
                "principle": "principles",
                "pattern": "patterns",
                "event": "events",
            }.get(row.type, "events")

            if counts[bucket] < limit:
                grouped[bucket].append({
                    "name": row.name,
                    "description": (row.description or "")[:300],
                    "weight": round(row.weight, 1),
                    "last_seen": row.last_seen_at.strftime("%Y-%m-%d") if row.last_seen_at else None,
                    "domains": row.domains_list or [],
                })
                counts[bucket] += 1

        total = sum(counts.values())
        return {
            "total": total,
            "generated": date.today().isoformat(),
            **grouped,
        }
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# TOOL 3: get_concept_graph
# ════════════════════════════════════════════════════════════════

def get_concept_with_relations(concept_name: str, depth: int = 1) -> dict | None:
    """Concepto central + relaciones (profundidad configurable)."""
    session = get_session()
    try:
        # Buscar concepto central
        concept_row = session.execute(text("""
            SELECT
                c.id, c.name, c.type, c.status, c.description,
                c.weight, c.last_seen_at, c.projects,
                ARRAY_AGG(DISTINCT d.slug) FILTER (WHERE d.slug IS NOT NULL) AS domains_list
            FROM graph_concept c
            LEFT JOIN graph_concept_domains cd ON cd.concept_id = c.id
            LEFT JOIN graph_domain d ON d.id = cd.domain_id
            WHERE c.name ILIKE :pattern
            GROUP BY c.id
            ORDER BY c.weight DESC
            LIMIT 1
        """), {"pattern": f"%{concept_name}%"}).fetchone()

        if not concept_row:
            return None

        concept_id = concept_row.id

        # Relaciones salientes
        outgoing = session.execute(text("""
            SELECT
                r.relation_type, r.strength,
                t.name AS target_name, t.type AS target_type,
                t.weight AS target_weight
            FROM graph_conceptrelation r
            JOIN graph_concept t ON t.id = r.target_id
            WHERE r.source_id = :cid
            ORDER BY r.strength DESC
        """), {"cid": concept_id}).fetchall()

        # Relaciones entrantes
        incoming = session.execute(text("""
            SELECT
                r.relation_type, r.strength,
                s.name AS source_name, s.type AS source_type,
                s.weight AS source_weight
            FROM graph_conceptrelation r
            JOIN graph_concept s ON s.id = r.source_id
            WHERE r.target_id = :cid
            ORDER BY r.strength DESC
        """), {"cid": concept_id}).fetchall()

        # Ocurrencias recientes
        occurrences = session.execute(text("""
            SELECT session_id, session_date, depth, project
            FROM graph_conceptoccurrence
            WHERE concept_id = :cid
            ORDER BY session_date DESC
            LIMIT 5
        """), {"cid": concept_id}).fetchall()

        return {
            "concept": {
                "name": concept_row.name,
                "type": concept_row.type,
                "status": concept_row.status,
                "description": concept_row.description or "",
                "weight": round(concept_row.weight, 1),
                "last_seen": concept_row.last_seen_at.strftime("%Y-%m-%d") if concept_row.last_seen_at else None,
                "domains": concept_row.domains_list or [],
                "projects": concept_row.projects or [],
            },
            "outgoing_relations": [
                {
                    "relation": r.relation_type,
                    "target": r.target_name,
                    "target_type": r.target_type,
                    "strength": round(r.strength, 1),
                }
                for r in outgoing
            ],
            "incoming_relations": [
                {
                    "relation": r.relation_type,
                    "source": r.source_name,
                    "source_type": r.source_type,
                    "strength": round(r.strength, 1),
                }
                for r in incoming
            ],
            "recent_occurrences": [
                {
                    "session": o.session_id,
                    "date": o.session_date.isoformat(),
                    "depth": o.depth,
                    "project": o.project,
                }
                for o in occurrences
            ],
        }
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# TOOL 4: get_domain_summary
# ════════════════════════════════════════════════════════════════

def get_domain_summary_data(domain: str) -> dict | None:
    """Resumen completo de un dominio."""
    session = get_session()
    try:
        # Verificar dominio existe
        dom = session.execute(text("""
            SELECT id, name, slug, description
            FROM graph_domain
            WHERE slug = :slug
        """), {"slug": domain}).fetchone()

        if not dom:
            return None

        # Distribución por tipo y status
        stats = session.execute(text("""
            SELECT c.type, c.status, COUNT(*) as cnt
            FROM graph_concept c
            JOIN graph_concept_domains cd ON cd.concept_id = c.id
            JOIN graph_domain d ON d.id = cd.domain_id
            WHERE d.slug = :slug
            GROUP BY c.type, c.status
            ORDER BY c.type, c.status
        """), {"slug": domain}).fetchall()

        # Top conceptos
        top = session.execute(text("""
            SELECT c.name, c.type, c.weight, c.status
            FROM graph_concept c
            JOIN graph_concept_domains cd ON cd.concept_id = c.id
            JOIN graph_domain d ON d.id = cd.domain_id
            WHERE d.slug = :slug AND c.status = 'active'
            ORDER BY c.weight DESC
            LIMIT 10
        """), {"slug": domain}).fetchall()

        # Actividad reciente (sesiones del dominio)
        recent_sessions = session.execute(text("""
            SELECT session_id, session_date, concepts_count
            FROM graph_sessionlog
            WHERE :slug = ANY(domains_active)
            ORDER BY session_date DESC
            LIMIT 5
        """), {"slug": domain}).fetchall()

        distribution = {}
        total = 0
        for s in stats:
            key = f"{s.type}_{s.status}"
            distribution[key] = s.cnt
            total += s.cnt

        return {
            "domain": {
                "name": dom.name,
                "slug": dom.slug,
                "description": dom.description,
            },
            "total_concepts": total,
            "distribution": distribution,
            "top_concepts": [
                {
                    "name": c.name,
                    "type": c.type,
                    "weight": round(c.weight, 1),
                }
                for c in top
            ],
            "recent_sessions": [
                {
                    "session": s.session_id,
                    "date": s.session_date.isoformat(),
                    "concepts": s.concepts_count,
                }
                for s in recent_sessions
            ],
        }
    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# TOOL 5: get_session_context (filtrado inteligente)
# ════════════════════════════════════════════════════════════════

def get_session_context_data(project: str = None, domains: list = None,
                              limit: int = 20, output_format: str = "markdown") -> str:
    """
    Genera contexto filtrado para sesión de trabajo.

    Optimización clave: si se especifican dominios, solo retorna conceptos
    relevantes para esos dominios. Reduce tokens de ~13.6k (todo) a ~3-5k
    (filtrado).
    """
    sql = """
        SELECT
            c.id, c.name, c.type, c.status, c.description,
            c.weight, c.last_seen_at, c.projects,
            ARRAY_AGG(DISTINCT d.slug) FILTER (WHERE d.slug IS NOT NULL) AS domains_list
        FROM graph_concept c
        LEFT JOIN graph_concept_domains cd ON cd.concept_id = c.id
        LEFT JOIN graph_domain d ON d.id = cd.domain_id
        WHERE c.status = 'active'
    """
    params = {}

    if project:
        sql += " AND :project = ANY(c.projects)"
        params["project"] = project

    if domains:
        sql += " AND d.slug = ANY(:domains)"
        params["domains"] = domains

    sql += """
        GROUP BY c.id
        ORDER BY
            CASE c.type
                WHEN 'principle' THEN 0
                WHEN 'pattern' THEN 1
                WHEN 'event' THEN 2
            END,
            c.weight DESC
        LIMIT :limit
    """
    params["limit"] = limit

    session = get_session()
    try:
        rows = session.execute(text(sql), params).fetchall()

        if output_format == "json":
            concepts = []
            for row in rows:
                concepts.append({
                    "name": row.name,
                    "type": row.type,
                    "description": (row.description or "")[:300],
                    "weight": round(row.weight, 1),
                    "domains": row.domains_list or [],
                })
            return json.dumps({
                "total": len(concepts),
                "generated": date.today().isoformat(),
                "concepts": concepts,
            }, ensure_ascii=False, indent=2)

        # Formato Markdown (para CONCEPTOS_ACTIVOS.md / LLM)
        lines = []
        domain_label = ", ".join(domains) if domains else "todos"
        lines.append(f"# Contexto de Sesión{' - ' + project.upper() if project else ''}")
        lines.append(f"# Generado: {date.today().isoformat()} | "
                      f"Dominios: {domain_label} | Conceptos: {len(rows)}")
        lines.append("")

        current_type = None
        type_headers = {
            "principle": "## Principios (nunca decaen)",
            "pattern": "## Patrones (consolidados)",
            "event": "## Eventos recientes",
        }

        for row in rows:
            if row.type != current_type:
                if current_type is not None:
                    lines.append("")
                current_type = row.type
                lines.append(type_headers.get(row.type, f"## {row.type}"))

            doms = ", ".join(row.domains_list or [])
            desc = (row.description or "").strip()
            if len(desc) > 200:
                desc = desc[:200] + "..."

            lines.append(f"- **{row.name}**: {desc}")
            lines.append(f"  Dominios: {doms or 'sin dominio'} | "
                          f"Weight: {row.weight:.1f}")

        lines.append("")
        return "\n".join(lines)

    finally:
        session.close()

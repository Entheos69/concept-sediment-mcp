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

# Corte de `description` en los payloads de busqueda (no en cs_get_concept_graph,
# que devuelve la description completa).
DESC_MAX = 300


def _desc(raw: str, limit: int = DESC_MAX) -> tuple[str, bool]:
    """Recorta description declarando el corte.

    Auditoria 2026-07-14 (H5): se truncaba a 300 chars SIN marcador, asi que el
    consumidor recibia un texto cortado con aspecto de completo. Importa mas de
    lo que parece: CodeCS sedimento el mismo dia que un corolario sepultado en
    la `description` se cita como si fuera nodo — si ademas el corolario cae
    detras del corte, es invisible y nadie sabe que hay un mas alla.

    Returns:
        (texto, truncado)
    """
    text_ = (raw or "").strip()
    if len(text_) <= limit:
        return text_, False
    return text_[:limit].rstrip() + "...", True

# ════════════════════════════════════════════════════════════════
# Impugnaciones: el nodo corregido no puede servirse como incolume
# ════════════════════════════════════════════════════════════════
# HANDOFF CodeCS->CodeMCP (2026-07-16). La `description` de un nodo sale SOLO
# del YAML que lo DECLARA; la enmienda de quien lo corrige vive en la ARISTA.
# Como ninguna de las dos busquedas tocaba graph_conceptrelation, un nodo con
# `contradicts` entrante se servia sin una sola senal de estar impugnado — y en
# el caso que origino esto, la description servida era literalmente falsa.
#
# NO es la forma "el dato correcto se calcula y se tira" (auditoria 2026-07-14):
# aqui el dato NUNCA se calculaba. Remedio opuesto: no es dejar de tirar, es
# empezar a preguntar.
#
# Medicion in-vivo (2026-07-16, 672 conceptos servidos, 2394 relaciones):
#   21 aristas impugnantes -> 11 nodos servidos impugnados -> 5 con retador VIVO.
#   16 de las 21 vienen de un retador `archived`. Por eso NO colapsamos: una
#   bandera cruda marcaria 11 nodos con 6 disputas muertas dentro (55% ruido).
CHALLENGE_RELATIONS = ("contradicts", "supersedes")

_CONTESTED_NOTE_ACTIVE = (
    "Este concepto tiene impugnaciones ENTRANTES de conceptos vigentes. NO "
    "significa que sea falso: significa que hay DISPUTA, y la enmienda vive en "
    "la arista, no en esta description. El impugnante tambien podria ser el "
    "equivocado. Pide cs_get_concept_graph(<name>) y leela antes de citarlo."
)
_CONTESTED_NOTE_ARCHIVED = (
    "Impugnado solo por conceptos 'archived'. La disputa pudo haberse RESUELTO "
    "o pudo simplemente haber DECAIDO por desuso: el grafo no distingue esos "
    "dos casos. Menor prioridad, no nula."
)
_CONTESTED_NOTE_ERROR = (
    "La ausencia de bandera NO es evidencia de que no haya disputa: la "
    "verificacion de impugnaciones NO PUDO EJECUTARSE. Si el concepto importa, "
    "pide cs_get_concept_graph(<name>) y mira sus relaciones entrantes."
)


def _fetch_contested(session, concept_ids: list) -> dict | None:
    """Retadores por concepto: UNA query agregada por lote, no una por nodo.

    OJO: `None` NO significa "sin impugnaciones", significa "no pude preguntar".
    Quien llame debe PROPAGAR esa distincion — es el mismo error que H1
    (auditoria 2026-07-14): devolver vacio ante un fallo convierte una caida de
    infraestructura en un "esta limpio".

    Returns:
        {target_id: (nombres_retadores_vivos, cuenta_retadores_archived)},
        o None si la consulta fallo.
    """
    if not concept_ids:
        return {}
    try:
        rows = session.execute(text("""
            SELECT r.target_id,
                   ARRAY_AGG(s.name || ' [' || r.relation_type || ']')
                       FILTER (WHERE s.status != 'archived') AS vivos,
                   COUNT(*) FILTER (WHERE s.status = 'archived') AS archivados
            FROM graph_conceptrelation r
            JOIN graph_concept s ON s.id = r.source_id
            WHERE r.target_id = ANY(:ids)
              AND r.relation_type = ANY(:tipos)
            GROUP BY r.target_id
        """), {
            "ids": list(concept_ids),
            "tipos": list(CHALLENGE_RELATIONS),
        }).fetchall()
    except Exception as e:
        logger.error("[CONTESTED] no se pudo verificar impugnaciones: %s", e)
        return None
    return {r.target_id: (r.vivos or [], r.archivados or 0) for r in rows}


def _contested_payload(vivos: list, archivados: int) -> dict:
    """Paquete por concepto. La nota informa, NO adjudica quien tiene razon."""
    return {
        "by_active": vivos,
        "by_archived": archivados,
        "note": _CONTESTED_NOTE_ACTIVE if vivos else _CONTESTED_NOTE_ARCHIVED,
    }


def _annotate_contested(session, ids: list, results: list) -> None:
    """Anade `contested` a cada result (in-place). Contrato de TRES valores:

        False        -> se pregunto y esta limpio
        {by_active..}-> se pregunto y hay disputa
        {error: ...} -> NO se pudo preguntar

    Nunca None/null: un consumidor LLM lee null como "no". El caso de fallo
    tiene que ser ruidoso, no falsy — si no, reintroduce el bug que este mismo
    campo existe para cerrar.
    """
    mapa = _fetch_contested(session, ids)

    if mapa is None:
        for r in results:
            r["contested"] = {
                "error": "no se pudo verificar impugnaciones entrantes",
                "note": _CONTESTED_NOTE_ERROR,
            }
        return

    for cid, r in zip(ids, results):
        entry = mapa.get(cid)
        r["contested"] = _contested_payload(*entry) if entry else False


# ── Embeddings (para búsqueda semántica) ──
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
# H1 auditoria 2026-07-05: sin timeout, el default del SDK (~600s + 2 retries)
# cuelga el tool MCP mas alla de sus 180s y el fallback ILIKE nunca dispara
# (solo cubre fallo, no lentitud). Acotamos: timeout corto + 1 retry.
EMBEDDING_TIMEOUT_S = float(os.environ.get("EMBEDDING_TIMEOUT_S", "8"))

_openai_client = None  # cliente unico a nivel modulo (no uno por query)


def _get_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=EMBEDDING_TIMEOUT_S,
            max_retries=1,
        )
    return _openai_client


def _generate_query_embedding(query_text: str) -> list | None:
    """Genera embedding para un query de búsqueda.

    Retorna None si falla O si excede EMBEDDING_TIMEOUT_S: en ambos casos
    el caller (cs_search_concepts) cae a busqueda ILIKE. Degradacion
    explicita en vez de cuelgue.

    OJO: "None" NO significa "sin resultados", significa "no pude preguntar".
    Quien lo llame debe PROPAGAR esa distincion al consumidor — ver
    search_concepts(). Loguearla y devolver una lista vacia convierte un fallo
    de infraestructura en un "no existe" (auditoria 2026-07-14, H1).
    """
    if not OPENAI_API_KEY:
        logger.warning("[SEARCH] Sin OPENAI_API_KEY: la busqueda sera lexica, no semantica")
        return None
    try:
        response = _get_client().embeddings.create(
            model=EMBEDDING_MODEL,
            input=query_text.strip(),
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning("Embedding generation failed (fallback a ILIKE): %s", e)
        return None


# Motores de busqueda posibles, tal como se le declaran al consumidor.
SEARCH_MODE_EMBEDDING = "embedding"          # semantica, sana
SEARCH_MODE_TEXT = "text"                    # lexica: el semantico no dio hits
SEARCH_MODE_TEXT_DEGRADED = "text_degraded"  # lexica: el semantico NO PUDO correr

DEGRADED_WARNING = (
    "BUSQUEDA DEGRADADA: el motor semantico (embeddings) no pudo ejecutarse "
    "-- sin API key, fallo del proveedor o timeout. Se respondio con busqueda "
    "LEXICA (ILIKE), que matchea la frase literal: una query en lenguaje "
    "natural puede devolver 0 resultados AUNQUE EL CONCEPTO EXISTA. "
    "Un vacio bajo este modo NO es evidencia de ausencia."
)


def search_concepts(query: str, domain: str = None, project: str = None,
                    limit: int = 10) -> dict:
    """Busqueda de conceptos que DECLARA con que motor respondio.

    Antes (auditoria 2026-07-14, H1) el fallback era mudo: si el embedding no
    podia generarse, se devolvia [] y el caller caia a ILIKE sin decirselo a
    nadie. Como ILIKE busca la frase literal, una query en lenguaje natural
    devolvia 0 resultados — indistinguible de "el concepto no existe". El
    sistema SABIA que habia degradado (lo logueaba) y no lo entregaba.

    Returns:
        dict con: concepts, count, search_mode, degraded (bool) y, si degraded,
        warning explicito.
    """
    embedding = _generate_query_embedding(query)

    if embedding is None:
        # No es que no haya resultados: es que no se pudo preguntar.
        concepts = search_concepts_by_text(query, domain, project, limit)
        return {
            "concepts": concepts,
            "count": len(concepts),
            "search_mode": SEARCH_MODE_TEXT_DEGRADED,
            "degraded": True,
            "warning": DEGRADED_WARNING,
        }

    concepts = _search_by_embedding_vec(embedding, domain, project, limit)
    if concepts:
        return {
            "concepts": concepts,
            "count": len(concepts),
            "search_mode": SEARCH_MODE_EMBEDDING,
            "degraded": False,
        }

    # El semantico corrio y no encontro nada: el fallback lexico es un intento
    # extra legitimo, no una degradacion.
    concepts = search_concepts_by_text(query, domain, project, limit)
    return {
        "concepts": concepts,
        "count": len(concepts),
        "search_mode": SEARCH_MODE_TEXT,
        "degraded": False,
    }


# ════════════════════════════════════════════════════════════════
# TOOL 1: search_concepts
# ════════════════════════════════════════════════════════════════

def search_concepts_by_embedding(query: str, domain: str = None,
                                  project: str = None, limit: int = 10) -> list:
    """Búsqueda semántica por embedding en pgvector.

    COMPATIBILIDAD: devuelve [] tanto si el embedding fallo como si no hubo
    hits — esa ambiguedad es justo el bug H1. Preferir search_concepts(), que
    declara el modo. Se conserva porque hay callers que solo quieren la lista.
    """
    embedding = _generate_query_embedding(query)
    if not embedding:
        return []
    return _search_by_embedding_vec(embedding, domain, project, limit)


def _search_by_embedding_vec(embedding: list, domain: str = None,
                             project: str = None, limit: int = 10) -> list:
    """Consulta pgvector con un embedding YA generado.

    Separado de la generacion para que el caller pueda distinguir
    "no pude preguntar" de "pregunte y no hay nada".
    """
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
        ids = []
        for row in rows:
            desc, truncated = _desc(row.description)
            r = {
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "description": desc,
                "description_truncated": truncated,
                "weight": round(row.weight, 1),
                "similarity": round(row.similarity, 4),
                "last_seen": row.last_seen_at.strftime("%Y-%m-%d") if row.last_seen_at else None,
                "domains": row.domains_list or [],
                "projects": row.projects or [],
            }
            results.append(r)
            ids.append(row.id)
        _annotate_contested(session, ids, results)
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
        ids = []
        for row in rows:
            desc, truncated = _desc(row.description)
            results.append({
                "name": row.name,
                "type": row.type,
                "status": row.status,
                "description": desc,
                "description_truncated": truncated,
                "weight": round(row.weight, 1),
                # Explicito: ILIKE no puntua. Antes el campo simplemente NO
                # estaba, y cs_session_open lo leia como 0.0 al rankear, hundiendo
                # los hits lexicos contra los semanticos sin decirlo (H3).
                "similarity": None,
                "last_seen": row.last_seen_at.strftime("%Y-%m-%d") if row.last_seen_at else None,
                "domains": row.domains_list or [],
                "projects": row.projects or [],
            })
            ids.append(row.id)
        _annotate_contested(session, ids, results)
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

        # depth > 1: expandir transitivamente. Auditoria 2026-07-14 (H2): el
        # parametro se aceptaba (1-3, "1=directas, 2=transitivas" en la
        # docstring y en el skill) y NO SE USABA — depth=3 devolvia exactamente
        # lo mismo que depth=1. Parametro fantasma: el consumidor pedia
        # profundidad y recibia otra cosa, sin aviso.
        transitive = []
        if depth > 1:
            frontier = {concept_id}
            visited = {concept_id}
            for nivel in range(2, depth + 1):
                if not frontier:
                    break
                vecinos = session.execute(text("""
                    SELECT
                        r.relation_type, r.strength,
                        s.id AS source_id, s.name AS source_name,
                        t.id AS target_id, t.name AS target_name,
                        t.type AS target_type, t.weight AS target_weight
                    FROM graph_conceptrelation r
                    JOIN graph_concept s ON s.id = r.source_id
                    JOIN graph_concept t ON t.id = r.target_id
                    WHERE (r.source_id = ANY(:ids) OR r.target_id = ANY(:ids))
                    ORDER BY r.strength DESC
                """), {"ids": list(frontier)}).fetchall()

                nueva_frontera = set()
                for v in vecinos:
                    for extremo_id, extremo_name in (
                        (v.source_id, v.source_name),
                        (v.target_id, v.target_name),
                    ):
                        if extremo_id in visited:
                            continue
                        visited.add(extremo_id)
                        nueva_frontera.add(extremo_id)
                        transitive.append({
                            "level": nivel,
                            "concept": extremo_name,
                            "via_relation": v.relation_type,
                            "strength": round(v.strength, 1),
                        })
                frontier = nueva_frontera

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
            "depth_requested": depth,
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
            # Vacio cuando depth=1: el nivel 1 YA esta en outgoing/incoming.
            "transitive_relations": transitive,
            "recent_occurrences": [
                {
                    "session": o.session_id,
                    "date": o.session_date.isoformat(),
                    "depth": o.depth,
                    "project": o.project,
                }
                for o in occurrences
            ],
            "occurrences_shown": len(occurrences),
            "occurrences_note": "solo las 5 mas recientes",
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

        # H6 (auditoria 2026-07-14): si el LIMIT recorto, decirlo. Antes se
        # reportaba "Conceptos: N" a secas, y N era lo devuelto, no lo que hay:
        # el agente que abre sesion creia estar viendo su dominio entero.
        posible_recorte = len(rows) == limit

        # Impugnaciones (HANDOFF 2026-07-16). Este tool lo lee TODO agente al
        # abrir sesion: es el canal de consumo mas ancho del grafo, mas que la
        # busqueda. Servir aqui un nodo corregido como incolume es peor.
        contested = _fetch_contested(session, [r.id for r in rows])

        def _flag(row_id):
            if contested is None:
                return {"error": "no se pudo verificar impugnaciones entrantes",
                        "note": _CONTESTED_NOTE_ERROR}
            entry = contested.get(row_id)
            return _contested_payload(*entry) if entry else False

        if output_format == "json":
            concepts = []
            for row in rows:
                desc, truncated = _desc(row.description)
                concepts.append({
                    "name": row.name,
                    "type": row.type,
                    "description": desc,
                    "description_truncated": truncated,
                    "weight": round(row.weight, 1),
                    "domains": row.domains_list or [],
                    "contested": _flag(row.id),
                })
            return json.dumps({
                "total": len(concepts),
                "limit": limit,
                "possibly_truncated": posible_recorte,
                "generated": date.today().isoformat(),
                "concepts": concepts,
            }, ensure_ascii=False, indent=2)

        # Formato Markdown (para CONCEPTOS_ACTIVOS.md / LLM)
        lines = []
        domain_label = ", ".join(domains) if domains else "todos"
        lines.append(f"# Contexto de Sesión{' - ' + project.upper() if project else ''}")
        lines.append(f"# Generado: {date.today().isoformat()} | "
                      f"Dominios: {domain_label} | Conceptos: {len(rows)}")
        if posible_recorte:
            lines.append(f"# [AVISO] Se alcanzo el limite ({limit}): puede haber "
                          f"MAS conceptos sin mostrar. Esto no es el dominio completo.")
        if contested is None:
            lines.append("# [AVISO] No se pudo verificar impugnaciones entrantes. "
                          "NINGUN concepto de abajo esta marcado como impugnado, y eso "
                          "NO es evidencia de que no lo este.")
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

            flag = _flag(row.id)
            if isinstance(flag, dict) and flag.get("by_active"):
                lines.append(f"  [IMPUGNADO] por: {'; '.join(flag['by_active'])}")
                lines.append(f"  [IMPUGNADO] la enmienda vive en la arista, NO en la "
                              f"description de arriba. Pide "
                              f"cs_get_concept_graph(\"{row.name[:60]}\") antes de citarlo.")
            elif isinstance(flag, dict) and flag.get("by_archived"):
                lines.append(f"  [impugnado] por {flag['by_archived']} concepto(s) "
                              f"archived: la disputa pudo resolverse o solo decaer.")

        lines.append("")
        return "\n".join(lines)

    finally:
        session.close()

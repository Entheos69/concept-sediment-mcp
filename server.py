"""
Concept Sediment — MCP Server

Servidor MCP con transporte Streamable HTTP (stateless, JSON responses)
para exponer el grafo de conceptos a claude.ai y otros consumidores MCP.

8 Tools:
  - cs_search_concepts:      búsqueda semántica por query
  - cs_get_active_concepts:  conceptos activos por dominio/proyecto
  - cs_get_concept_graph:    grafo alrededor de un concepto
  - cs_get_domain_summary:   resumen narrativo de un dominio
  - cs_get_session_context:  contexto filtrado para iniciar sesión
  - cs_get_alerts:           alertas inmunológicas (fracturas + vacunas)
  - cs_session_open:         apertura MTV (multi-query + alerts en 1 call)
  - cs_audit_thread:         cobertura batch de un hilo de conceptos (D-T4)

Uso:
  python server.py                            # Streamable HTTP en :8000
  MCP_PORT=9000 python server.py              # Puerto custom
  DATABASE_URL=postgresql://... python server.py

Compatibilidad con claude.ai:
  URL: https://<domain>/mcp
  claude.ai soporta Streamable HTTP con SSE fallback.
"""
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from db import get_engine, get_session, dispose_engine
from queries import (
    search_concepts_by_embedding,
    search_concepts_by_text,
    get_active_concepts,
    get_concept_with_relations,
    get_domain_summary_data,
    get_session_context_data,
)
from humandato_queries import get_all_alerts

# ── Configuración ──
MCP_PORT = int(os.environ.get("MCP_PORT", os.environ.get("PORT", "8000")))
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")


# ── Lifespan: conexión a DB ──
@asynccontextmanager
async def app_lifespan(server):
    """Inicializa pool de conexiones al arrancar, cierra al parar."""
    engine = get_engine()
    yield {"engine": engine}
    dispose_engine()


# ── Server MCP ──
mcp = FastMCP(
    "concept_sediment_mcp",
    lifespan=app_lifespan,
)


# ════════════════════════════════════════════════════════════════
# TOOL 1: cs_search_concepts
# ════════════════════════════════════════════════════════════════

class SearchConceptsInput(BaseModel):
    """Parámetros para búsqueda semántica de conceptos."""
    query: str = Field(
        ...,
        description="Texto de búsqueda (nombre, descripción o tema)",
        min_length=1,
        max_length=500,
    )
    domain: Optional[str] = Field(
        default=None,
        description="Filtrar por slug de dominio (ej: 'django_patterns')",
    )
    project: Optional[str] = Field(
        default=None,
        description="Filtrar por tag de proyecto (ej: 'inducop')",
    )
    limit: int = Field(default=10, ge=1, le=50)


@mcp.tool(
    name="cs_search_concepts",
    annotations={
        "title": "Search Concepts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_search_concepts(params: SearchConceptsInput) -> str:
    """Busca conceptos en el grafo semántico.

    Usa embeddings para búsqueda por similaridad cuando están disponibles,
    con fallback a búsqueda por texto (ILIKE). Retorna conceptos con
    dominios, tipo, status, weight y similaridad.
    """
    results = search_concepts_by_embedding(
        query=params.query,
        domain=params.domain,
        project=params.project,
        limit=params.limit,
    )

    if not results:
        results = search_concepts_by_text(
            query=params.query,
            domain=params.domain,
            project=params.project,
            limit=params.limit,
        )

    return json.dumps({
        "count": len(results),
        "query": params.query,
        "concepts": results,
    }, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════════════
# TOOL 2: cs_get_active_concepts
# ════════════════════════════════════════════════════════════════

class GetActiveConceptsInput(BaseModel):
    """Parámetros para obtener conceptos activos."""
    domain: Optional[str] = Field(
        default=None,
        description="Filtrar por slug de dominio",
    )
    project: Optional[str] = Field(
        default=None,
        description="Filtrar por tag de proyecto",
    )
    concept_type: Optional[str] = Field(
        default=None,
        description="Filtrar por tipo: 'principle', 'pattern', 'event'",
    )
    limit: int = Field(default=15, ge=1, le=50)


@mcp.tool(
    name="cs_get_active_concepts",
    annotations={
        "title": "Get Active Concepts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_get_active_concepts(params: GetActiveConceptsInput) -> str:
    """Obtiene conceptos activos organizados por nivel de sedimentación.

    Retorna conceptos con status='active' agrupados en: principios
    (nunca decaen), patrones (consolidados), eventos (recientes).
    Soporta filtrado por dominio, proyecto y tipo.
    """
    data = get_active_concepts(
        domain=params.domain,
        project=params.project,
        concept_type=params.concept_type,
        limit=params.limit,
    )
    return json.dumps(data, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════════════
# TOOL 3: cs_get_concept_graph
# ════════════════════════════════════════════════════════════════

class GetConceptGraphInput(BaseModel):
    """Parámetros para obtener grafo local de un concepto."""
    concept_name: str = Field(
        ...,
        description="Nombre del concepto (búsqueda parcial, case-insensitive)",
        min_length=1,
    )
    depth: int = Field(
        default=1,
        description="Profundidad: 1=directas, 2=transitivas",
        ge=1, le=3,
    )


@mcp.tool(
    name="cs_get_concept_graph",
    annotations={
        "title": "Get Concept Graph",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_get_concept_graph(params: GetConceptGraphInput) -> str:
    """Obtiene un concepto con su grafo local de relaciones.

    Retorna el concepto central con relaciones salientes y entrantes,
    tipo de relación, strength, y datos del concepto relacionado.
    """
    data = get_concept_with_relations(
        concept_name=params.concept_name,
        depth=params.depth,
    )
    if not data:
        return json.dumps({
            "error": f"Concepto no encontrado: '{params.concept_name}'",
            "suggestion": "Usa cs_search_concepts para buscar por texto.",
        })
    return json.dumps(data, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════════════
# TOOL 4: cs_get_domain_summary
# ════════════════════════════════════════════════════════════════

class GetDomainSummaryInput(BaseModel):
    """Parámetros para resumen de dominio."""
    domain: str = Field(
        ...,
        description="Slug del dominio (ej: 'django_patterns', 'frontend')",
        min_length=1,
    )


@mcp.tool(
    name="cs_get_domain_summary",
    annotations={
        "title": "Get Domain Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_get_domain_summary(params: GetDomainSummaryInput) -> str:
    """Resumen del estado actual de un dominio de conocimiento.

    Incluye: total de conceptos, distribución por tipo/status,
    top conceptos por weight, relaciones más fuertes, actividad reciente.
    """
    data = get_domain_summary_data(domain=params.domain)
    if not data:
        return json.dumps({"error": f"Dominio no encontrado: '{params.domain}'"})
    return json.dumps(data, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════════════
# TOOL 5: cs_get_session_context
# ════════════════════════════════════════════════════════════════

class GetSessionContextInput(BaseModel):
    """Parámetros para contexto de sesión (filtrado inteligente)."""
    project: Optional[str] = Field(
        default=None,
        description="Filtrar por proyecto",
    )
    domains: Optional[list[str]] = Field(
        default=None,
        description="Dominios que se van a trabajar (filtra conceptos relevantes)",
    )
    limit: int = Field(default=20, ge=5, le=50)
    format: str = Field(
        default="markdown",
        description="'markdown' para LLM, 'json' para programático",
    )


@mcp.tool(
    name="cs_get_session_context",
    annotations={
        "title": "Get Session Context",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_get_session_context(params: GetSessionContextInput) -> str:
    """Genera contexto filtrado para iniciar una sesión de trabajo.

    A diferencia de get_active_concepts (que retorna todo), este tool
    filtra por los dominios que se van a trabajar, priorizando conceptos
    relevantes y reduciendo tokens innecesarios.

    Soporta formato markdown (para CONCEPTOS_ACTIVOS.md / LLM) o JSON.
    """
    data = get_session_context_data(
        project=params.project,
        domains=params.domains,
        limit=params.limit,
        output_format=params.format,
    )
    return data


# ════════════════════════════════════════════════════════════════
# TOOL 6: cs_get_alerts
# ════════════════════════════════════════════════════════════════

class GetAlertsInput(BaseModel):
    """Parámetros para alertas del Humandato."""
    project: Optional[str] = Field(
        default=None,
        description="Filtrar por proyecto (ej: 'inducop')",
    )


@mcp.tool(
    name="cs_get_alerts",
    annotations={
        "title": "Get Humandato Alerts",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_get_alerts(params: GetAlertsInput) -> str:
    """Alertas inmunológicas del Humandato.

    Retorna dos tipos de alerta:
    1. Fracturas: conceptos debilitados con dependientes activos
       (señal predictiva de fallo)
    2. Vacunas faltantes: directivas conocidas sin representación
       en el grafo (riesgo de violación recurrente)

    Invocar al inicio de cada sesión, después de cs_get_session_context.
    """
    alerts = get_all_alerts(project=params.project)

    # Formato narrativo para el LLM
    lines = []
    summary = alerts["summary"]

    if summary["status"] == "stable":
        lines.append("Humandato: sistema inmunologico estable. Sin alertas.")
        return "\n".join(lines)

    lines.append(
        f"Humandato: {summary['critical_alerts']} alerta(s) critica(s)"
    )
    lines.append("")

    if alerts["fractures"]["total"] > 0:
        lines.append("FRACTURAS (conceptos debilitados con dependientes activos):")

        # Críticas
        for f in alerts["fractures"]["criticas"]:
            deps = ", ".join(d["name"] for d in f["active_dependents"])
            lines.append(
                f"  [CRITICA] {f['concept']} [{f['status']}]: "
                f"dependientes activos: {deps}"
            )

        # Moderadas
        for f in alerts["fractures"]["moderadas"]:
            deps = ", ".join(d["name"] for d in f["active_dependents"])
            lines.append(
                f"  [MODERADA] {f['concept']} [{f['status']}]: "
                f"dependientes activos: {deps}"
            )

        # Bajas
        for f in alerts["fractures"]["bajas"]:
            deps = ", ".join(d["name"] for d in f["active_dependents"])
            lines.append(
                f"  [BAJA] {f['concept']} [{f['status']}]: "
                f"dependientes activos: {deps}"
            )

        lines.append("")

    if alerts["missing_vaccines"]:
        lines.append("VACUNAS FALTANTES (directivas sin representacion):")
        for v in alerts["missing_vaccines"]:
            sev = v["severity"].upper()
            lines.append(f"  [{sev}] {v['category']}: {v['directive']}")
            if v.get("failure_history"):
                lines.append(f"    Historial: {v['failure_history']}")
        lines.append("")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# TOOL 7: cs_session_open
# ════════════════════════════════════════════════════════════════

class SessionOpenInput(BaseModel):
    """Parámetros para apertura asistida de sesión via Marco Teórico Vivo."""
    topic: str = Field(
        ...,
        description="Tema de la sesión (label informativo, no afecta búsqueda)",
        min_length=1,
        max_length=300,
    )
    queries: list[str] = Field(
        ...,
        description=(
            "2-3 queries que reflejan el tema desde ángulos distintos. "
            "Cada query se ejecuta como cs_search_concepts y los "
            "resultados se deduplican por nombre."
        ),
        min_length=1,
        max_length=5,
    )
    domain: Optional[str] = Field(
        default=None,
        description="Filtro opcional de dominio (slug). Aplica a todas las queries.",
    )
    project: Optional[str] = Field(
        default=None,
        description="Filtro opcional de proyecto. Aplica a queries y a alertas.",
    )
    limit_per_query: int = Field(default=5, ge=1, le=15)


@mcp.tool(
    name="cs_session_open",
    annotations={
        "title": "Open Session with Living Theoretical Framework (MTV)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_session_open(params: SessionOpenInput) -> str:
    """Apertura asistida de sesión via Marco Teórico Vivo (MTV).

    Compone múltiples cs_search_concepts (uno por query) + cs_get_alerts
    en una sola invocación. Devuelve paquete de apertura con:
      - concepts_ranked: conceptos deduplicados por nombre, rankeados
        por mejor similaridad observada entre las queries.
      - concepts_per_query: resultados crudos por query, para distinguir
        qué ángulo trajo qué.
      - alerts: alertas inmunológicas activas.

    Diseñado para reducir fricción del protocolo MTV de 3-5 tool calls
    a 1. Caller provee las queries desde ángulos distintos del tema —
    el tool NO genera ángulos internamente porque cada agente conoce
    mejor qué ángulos importan para su dominio.

    No toma decisiones metodológicas: solo compone tools existentes.
    """
    per_query_results = {}
    all_concepts = {}  # name -> mejor result observado entre queries

    for q in params.queries:
        results = search_concepts_by_embedding(
            query=q,
            domain=params.domain,
            project=params.project,
            limit=params.limit_per_query,
        )
        if not results:
            results = search_concepts_by_text(
                query=q,
                domain=params.domain,
                project=params.project,
                limit=params.limit_per_query,
            )
        per_query_results[q] = results

        for r in results:
            name = r["name"]
            sim = r.get("similarity", 0.0) or 0.0
            existing = all_concepts.get(name)
            existing_sim = (existing.get("similarity", 0.0) or 0.0) if existing else -1
            if sim > existing_sim:
                all_concepts[name] = r

    deduped_ranked = sorted(
        all_concepts.values(),
        key=lambda r: r.get("similarity", 0.0) or 0.0,
        reverse=True,
    )

    alerts = get_all_alerts(project=params.project)

    return json.dumps({
        "topic": params.topic,
        "queries_count": len(params.queries),
        "concepts_total_unique": len(deduped_ranked),
        "concepts_ranked": deduped_ranked,
        "concepts_per_query": per_query_results,
        "alerts": alerts,
    }, ensure_ascii=False, indent=2, default=str)


# ════════════════════════════════════════════════════════════════
# TOOL 8: cs_audit_thread
# ════════════════════════════════════════════════════════════════

class AuditThreadInput(BaseModel):
    """Parámetros para auditar cobertura de un hilo de conceptos en el grafo."""
    concepts: list[str] = Field(
        ...,
        description=(
            "Nombres (o substrings) de los conceptos del hilo que se "
            "quieren verificar. Búsqueda por texto ILIKE — útil cuando "
            "se conocen los nombres exactos o aproximados, a diferencia "
            "de cs_search_concepts que usa embeddings."
        ),
        min_length=1,
        max_length=20,
    )
    project: Optional[str] = Field(
        default=None,
        description="Filtra por proyecto (aplica a todas las búsquedas)",
    )
    include_graph: bool = Field(
        default=True,
        description=(
            "Si True, para el top match de cada concepto agrega "
            "relaciones entrantes/salientes (top 5) y ocurrencias "
            "recientes (top 3). Si False, solo presencia y metadata."
        ),
    )


@mcp.tool(
    name="cs_audit_thread",
    annotations={
        "title": "Audit Thread Coverage",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def cs_audit_thread(params: AuditThreadInput) -> str:
    """Audita en una sola llamada la cobertura de un hilo de conceptos.

    Para cada nombre de concepto en la lista:
      - Busca por texto ILIKE (top 3 matches)
      - Reporta status, weight, type, dominios, last_seen del top match
      - Lista alternative matches por nombre
      - Si include_graph: agrega relaciones y ocurrencias del top match

    Sustituye los pasos manuales de Tactic 011 (auditoría manual de hilo).
    Diseñado para implementar la norma D-T4 (chequeo recursivo pre-sesión).

    Caller provee la lista de conceptos esperados — el tool no infiere
    el hilo, solo verifica la presencia y trayectoria de lo que se pide.
    No toma decisiones metodológicas: solo compone tools existentes.
    """
    coverage = []
    by_status = {
        "active": 0,
        "dormant": 0,
        "archived": 0,
        "no_encontrado": 0,
    }

    for concept_name in params.concepts:
        results = search_concepts_by_text(
            query=concept_name,
            project=params.project,
            limit=3,
        )

        if not results:
            coverage.append({
                "thread_name": concept_name,
                "status": "no_encontrado",
                "matches": [],
            })
            by_status["no_encontrado"] += 1
            continue

        top = results[0]
        entry = {
            "thread_name": concept_name,
            "matched_concept": top["name"],
            "status": top["status"],
            "weight": top["weight"],
            "type": top["type"],
            "domains": top["domains"],
            "last_seen": top.get("last_seen"),
            "alt_matches": [r["name"] for r in results[1:]],
        }
        by_status[top["status"]] = by_status.get(top["status"], 0) + 1

        if params.include_graph:
            graph_data = get_concept_with_relations(
                concept_name=top["name"],
                depth=1,
            )
            if graph_data:
                entry["outgoing_relations"] = graph_data["outgoing_relations"][:5]
                entry["incoming_relations"] = graph_data["incoming_relations"][:5]
                entry["recent_occurrences"] = graph_data["recent_occurrences"][:3]

        coverage.append(entry)

    return json.dumps({
        "summary": {
            "total_thread_items": len(params.concepts),
            "found_in_graph": len(params.concepts) - by_status["no_encontrado"],
            "missing_from_graph": by_status["no_encontrado"],
            "by_status": by_status,
        },
        "coverage": coverage,
    }, ensure_ascii=False, indent=2, default=str)


# ── App con health check + MCP ──
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

async def health(request):
    return JSONResponse({
        "status": "ok",
        "service": "concept_sediment_mcp",
        "version": "1.0.0",
    })

mcp_http = mcp.http_app()

app = Starlette(
    routes=[
        Route("/health", health),
    ],
    lifespan=mcp_http.lifespan,
)
app.mount("/", mcp_http)

if __name__ == "__main__":
    import uvicorn
    print(f"Concept Sediment MCP — on {MCP_HOST}:{MCP_PORT}")
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)

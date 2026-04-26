# Stack Técnico del MCP Server (CodeMCP)

Hallazgos de infraestructura física del `concept-sediment-mcp` server. Complementa `stack-cs.md` (que cubre arquitectura conceptual del grafo).

**Última actualización:** 2026-04-25 (sesión que diseñó PASO 3b — write tools).

---

## 1. Base de datos: instancia Postgres compartida con Django

**Hallazgo crítico (2026-04-25):** el MCP server y la app Django `concept-sediment` usan la **misma instancia Postgres**. Declaración explícita en `concept-sediment-mcp/.env.example` línea 12:

```
DATABASE_URL=postgresql://user:password@host:port/concept_sediment
# PostgreSQL (misma instancia que concept-sediment Django)
```

**Implicaciones operativas:**

- Cualquier tabla Django (`graph_concept`, `graph_domain`, `graph_measurement`, `graph_concept_relation`, etc.) es directamente accesible desde el MCP via SQL raw.
- Migraciones Django (`graph/migrations/`) modifican el schema que el MCP consume. Una migración aplicada en Django se ve inmediatamente desde el MCP — NO hay copia ni sync.
- El MCP **puede** crear tablas propias en la misma DB (ej: `mcp_audit_log`). Convención: prefijo `mcp_*` para distinguir del dominio del grafo conceptual (`graph_*`).
- Si Django renombra/borra una tabla `graph_*`, las queries del MCP que la usan se rompen sin warning. **Riesgo de fractura silenciosa cross-repo.**
- pgvector extension habilitada en migration `0002_add_pgvector.py` de Django — el MCP la consume vía SQL raw.

**Mitigación de fractura cross-repo:** el MCP debería tener un health-check al startup que ejecute `SELECT 1 FROM graph_concept LIMIT 1` y similares para detectar schema drift. **No implementado actualmente.** Deuda potencial.

---

## 2. Convención de naming de tablas

| Prefijo | Origen | Propósito | Quién migra |
|---------|--------|-----------|-------------|
| `graph_*` | Django app `graph` | Modelos del grafo conceptual (Concept, Domain, ConceptRelation, Measurement) | CodeCS via Django migrations |
| `mcp_*` | MCP server (SQL directo) | Estado del MCP, NO del grafo conceptual (audit logs, caches, sessions, etc.) | CodeMCP via `migrations/*.sql` ejecutado al startup |

**Regla:** si una tabla representa un concepto-del-grafo o un atributo de un concepto, va en `graph_*` y la maneja Django. Si representa estado-del-MCP (telemetría, audit, cache), va en `mcp_*` y la maneja el MCP server directamente.

**Razón estructural:** evita confundir mantenimiento (Django migrations vs MCP startup SQL) y deja claro al inspeccionar la DB cuál sistema posee qué.

---

## 3. Patrón SQL del MCP

**`db.py` — engine singleton + session stateless:**

```python
_engine = create_engine(
    _get_database_url(),
    pool_size=5,
    max_overflow=10,
    pool_recycle=600,       # recicla conexiones cada 10 min (Railway puede cerrar idle)
    pool_pre_ping=True,     # valida conexión antes de usar (defensa contra conexiones zombie)
    echo=False,
)
_SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
```

**`get_session()` stateless:** cada función abre y cierra su propia sesión. NO hay session compartida entre tools. Caller es responsable de cerrarla (con context manager o try/finally).

**Conversión URL automática (db.py:25-26):**
```python
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)
```
Razón: Railway/Heroku entregan URLs con `postgres://`; SQLAlchemy 2.0+ requiere `postgresql://`. NO eliminar este wrapper.

---

## 4. UUID generation: Python, no SQL

**Hallazgo:** el modelo Django `Measurement` usa `uuid.uuid4` desde Python (no `gen_random_uuid()` SQL). Las migrations no asumen extensiones `pgcrypto` o `uuid-ossp`.

**Regla operativa para write tools del MCP:**

```python
import uuid

def record_measurement(...) -> dict:
    measurement_id = uuid.uuid4()
    session.execute(
        text("INSERT INTO graph_measurement (id, contexto, ...) VALUES (:id, :contexto, ...)"),
        {"id": measurement_id, "contexto": ..., ...}
    )
```

**NO usar:**
- `gen_random_uuid()` en SQL — requiere `pgcrypto` extension, no garantizada.
- `uuid_generate_v4()` en SQL — requiere `uuid-ossp` extension, no garantizada.
- DEFAULT en CREATE TABLE — funciona solo si la extensión está cargada.

**Sí usar:** generar UUID en Python con `uuid.uuid4()` y pasarlo como parámetro al INSERT. Idéntico patrón a Django, portabilidad garantizada.

---

## 5. SQL raw via SQLAlchemy `text()` (no ORM)

`queries.py` y `humandato_queries.py` usan SQL raw con SQLAlchemy `text()`. **No usar el ORM de SQLAlchemy.** Razones:

1. **pgvector requiere SQL directo** — operadores de similitud (`<=>`, `<#>`) no están en el ORM.
2. **No replicar modelos Django en SQLAlchemy** — fuente única de verdad de schema es Django; el MCP solo consume.
3. **Performance predecible** — sin overhead de ORM, queries son SQL inspeccionable.

**Patrón:**
```python
from sqlalchemy import text
from db import get_session

def my_query(arg: str):
    session = get_session()
    try:
        result = session.execute(
            text("SELECT * FROM graph_concept WHERE name = :name"),
            {"name": arg}
        )
        return [dict(row._mapping) for row in result]
    finally:
        session.close()
```

---

## 6. Embeddings: OpenAI `text-embedding-3-small`

**Generación de embeddings (queries.py:22):**
```python
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
```

**Características:**
- Modelo: `text-embedding-3-small` (default, configurable via env).
- Costo: ~$0.02 por millón de tokens. Una sesión típica < $0.01.
- Backfill empírico (concepto del grafo, w:0.7): 256 conceptos = ~$0.0005, ~3 minutos.
- Cobertura: `verify_embeddings` (Django management command) reporta % por status/type.

**Implicación para write tools nuevos:** si una write tool genera contenido sedimentable (no es el caso de `cs_record_measurement` — measurements no se sedimentan), debería disparar generación de embedding. Para measurements: NO hay embedding por diseño (son tabla aparte, no entrar al espacio semántico del grafo conceptual).

---

## 7. Migrations existentes (Django app `graph/`)

| # | Nombre | Descripción | Fecha |
|---|--------|-------------|-------|
| 0001 | `initial` | Modelos base: Concept, Domain, ConceptRelation, etc. | inicial |
| 0002 | `add_pgvector` | Habilita extension pgvector + columna `embedding` en Concept | inicial |
| 0003 | `alter_conceptrelation_relation_type` | Ajuste de choices del campo relation_type | 2026-XX |
| 0004 | `alter_conceptrelation_relation_type` | Segundo ajuste de relation_type (11 tipos finales) | 2026-04-10 |
| 0005 | `add_measurements` | Modelo `Measurement` (PASO 3a del plan CS006) | 2026-04-25 20:51 |

**Si CodeMCP necesita una tabla nueva del dominio del grafo:** abrir issue/handoff a CodeCS. **Si necesita una tabla del dominio del MCP** (`mcp_*`): hacerla via SQL directo desde startup del server (pattern a establecer en PASO 3b — archivo `migrations/001_audit_log.sql`).

---

## 8. Duplicación parcial: `humandato_queries.py` en 2 repos

**Hallazgo:** existe `humandato_queries.py` en AMBOS:
- `concept-sediment/graph/humandato_queries.py` (Django app)
- `concept-sediment-mcp/humandato_queries.py` (MCP server)

**Por verificar (deuda):** ¿son idénticos? ¿Uno es port del otro? ¿Cuál es la fuente de verdad?

**Riesgo:** si CodeCS modifica el de Django pero no el del MCP (o viceversa), comportamiento divergente entre Django shell y queries del MCP.

**Recomendación pendiente de discusión:** unificar via import (el MCP importa el de Django como módulo si ambos están en el mismo PYTHONPATH al deploy) o documentar explícitamente que son copias mantenidas en paralelo + checklist de sync al modificar.

---

## 9. Auto-deploy GitHub → Railway

**Concepto activo en grafo (w:0.7, 2026-04-25):** "auto-deploy GitHub a Railway verificado end-to-end en concept-sediment-mcp". Push a `master` dispara deploy automático Railway en ~5 min, sin acción CLI.

**Implicación operativa:** cualquier commit a master deploya. **Esto rompe sesiones MCP activas de otros agentes** (concepto activo "protocolo de reconexión MCP post-deploy Railway", w:1.0).

**Política asociada (sedimentada hoy en YAML 004-CodeMCP draft):** no deploy mientras hay sesión MCP activa de otro agente, salvo confirmación Guardian explícita.

**Estrategia para PASO 3b:** trabajar en branch `feat/cs-record-measurement`, merge a master solo cuando ventana confirmada.

---

## 10. Endpoint y autenticación

| Item | Valor |
|------|-------|
| Endpoint público | `https://mcp-server-production-994a.up.railway.app/mcp` |
| Protocolo | MCP over Streamable HTTP (FastMCP) |
| Auth | OAuth (gestionado por Claude AI Desktop / cliente MCP) |
| Reverse proxy | Starlette + uvicorn (en `server.py`) |
| Container | Docker (`Dockerfile`: python:3.12-slim + libpq-dev) |
| Deploy config | `railway.toml` |

**Variables de entorno requeridas (al deploy Railway):**
- `DATABASE_URL` — Postgres compartido con Django
- `OPENAI_API_KEY` — para generación de embeddings

**Variables opcionales:**
- `MCP_PORT` — Railway inyecta `PORT` automáticamente
- `MCP_HOST` — default `0.0.0.0`
- `EMBEDDING_MODEL` — default `text-embedding-3-small`

---

## 11. Pattern de tools registrados en server.py

```python
@mcp.tool()
def cs_get_session_context(params: SessionContextParams) -> dict:
    """Docstring que se expone como description del tool."""
    return get_session_context(...)
```

- Cada tool tiene un Pydantic model de params (TypeScript-friendly).
- El docstring del decorador `@mcp.tool()` se expone como description de la tool al cliente MCP.
- Las funciones de lógica viven en módulos separados (`queries.py`, `humandato_queries.py`); `server.py` solo registra y delega.

**Para PASO 3b — write tools** seguir el mismo pattern: lógica en `write_queries.py`, registro en `server.py` con bloque visualmente separado de las read tools.

---

## Referencias

- `db.py` (engine singleton + session stateless)
- `queries.py` (SQL raw para 5 read tools del grafo)
- `humandato_queries.py` (SQL para alertas + VCM)
- `.env.example` (declaración de DB compartida)
- `Dockerfile` (python:3.12-slim + libpq-dev)
- `railway.toml` (config deploy)
- `concept-sediment/graph/migrations/` (migrations Django, fuente de schema)

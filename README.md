# Concept Sediment MCP Server

**MCP Server** que expone el grafo de conocimiento de Concept Sediment vía protocolo [Model Context Protocol](https://modelcontextprotocol.io/).

Diseñado para proveer memoria semántica persistente a agentes AI (Claude Code, Claude Web, Claude Cowork) trabajando en proyectos de largo plazo.

---

## 🎯 Propósito

**Concept Sediment** es un sistema de memoria semántica que captura y consolida conceptos técnicos a través de sesiones de trabajo. Este servidor MCP expone ese conocimiento sedimentado para que los agentes AI puedan:

- **Consultar conceptos previos** antes de tomar decisiones arquitectónicas
- **Detectar fracturas** (conceptos debilitados con dependientes activos)
- **Identificar vacunas faltantes** (directivas conocidas sin representación en el grafo)
- **Buscar semánticamente** conceptos relacionados por embeddings
- **Obtener contexto filtrado** por dominio/proyecto al inicio de sesión

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│  Railway: mcp-server (production)                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  FastMCP + Uvicorn (Python 3.12)                            │
│  └─> 10 MCP Tools (9 read + 1 write con audit log)          │
│                                                              │
│  ┌────────────────────┐         ┌──────────────────────┐    │
│  │  queries.py        │────────>│  PostgreSQL 14+      │    │
│  │  (5 query fns)     │         │  + pgvector          │    │
│  ├────────────────────┤         │                      │    │
│  │  humandato_queries │         │  Database:           │    │
│  │  (alerts)          │         │  concept_sediment    │    │
│  ├────────────────────┤         │                      │    │
│  │  server.py         │         │                      │    │
│  │  (cs_session_open) │         │                      │    │
│  └────────────────────┘         └──────────────────────┘    │
│           │                                                  │
│           └────> OpenAI API (embeddings)                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
        │
        │ HTTPS (Streamable HTTP / SSE)
        │
        ▼
┌───────────────────────┐
│  Clientes MCP:        │
│  - Claude Code        │
│  - Claude Web         │
│  - Claude Cowork      │
└───────────────────────┘
```

**Base de datos compartida:** El servidor MCP comparte la misma instancia PostgreSQL que el proyecto Django `concept-sediment`.

**Política de escritura:** El servidor escribe al grafo solo a través de tools `cs_record_*` y `cs_promote_*`, con audit log append-only obligatorio (tabla `mcp_audit_log`). Las tools de lectura no modifican estado. Cada invocación de write tool registra timestamp, agent, payload y target_id en `mcp_audit_log`.

### Inventario de tools por categoría

**Tools de lectura (no modifican estado):**
- `cs_search_concepts`
- `cs_get_active_concepts`
- `cs_get_concept_graph`
- `cs_get_domain_summary`
- `cs_get_session_context`
- `cs_get_alerts`
- `cs_session_open`
- `cs_audit_thread`
- `cs_get_audit_log`

**Tools de escritura (con audit log obligatorio):**
- `cs_record_measurement`

---

## 🔧 MCP Tools disponibles

### 1. `cs_search_concepts`
Búsqueda semántica por embeddings (OpenAI `text-embedding-3-small`).

**Parámetros:**
- `query` (string, required): Texto de búsqueda
- `domain` (string, optional): Filtrar por dominio (ej: `django_patterns`)
- `project` (string, optional): Filtrar por proyecto (ej: `inducop`)
- `limit` (int, default=10): Máximo de resultados

**Retorna:** Conceptos ordenados por similaridad semántica (threshold >= 0.3).

---

### 2. `cs_get_session_context`
Contexto filtrado para iniciar una sesión de trabajo.

**Parámetros:**
- `project` (string, optional): Filtrar por proyecto
- `domains` (list[string], optional): Dominios que se van a trabajar
- `limit` (int, default=20): Máximo de conceptos
- `format` (string, default="markdown"): `markdown` o `json`

**Retorna:** Conceptos activos priorizados por tipo (principles > patterns > events) y weight.

**Optimización clave:** Filtrando por dominios, reduce tokens de ~13.6k (todo el grafo) a ~3-5k (solo relevante).

---

### 3. `cs_get_active_concepts`
Conceptos activos agrupados por tipo.

**Parámetros:**
- `domain` (string, optional): Filtrar por dominio
- `project` (string, optional): Filtrar por proyecto
- `concept_type` (string, optional): `principle`, `pattern`, o `event`
- `limit` (int, default=15): Máximo por tipo

**Retorna:** Objeto con `principles`, `patterns`, `events` (listas separadas).

---

### 4. `cs_get_concept_graph`
Grafo local alrededor de un concepto.

**Parámetros:**
- `concept_name` (string, required): Nombre del concepto (búsqueda ILIKE)
- `depth` (int, default=1): Profundidad del grafo (1-3)

**Retorna:** Concepto central + relaciones salientes/entrantes + ocurrencias recientes (últimas 5 sesiones).

---

### 5. `cs_get_domain_summary`
Resumen estadístico de un dominio.

**Parámetros:**
- `domain` (string, required): Slug del dominio

**Retorna:** Distribución por tipo/status, top conceptos por weight, sesiones recientes.

---

### 6. `cs_get_alerts`
Alertas inmunológicas del Humandato (sistema de salud del grafo).

**Parámetros:**
- `project` (string, optional): Filtrar por proyecto

**Retorna:**
- **Fracturas:** Conceptos debilitados (dormant/archived) con dependientes activos. Señal predictiva de fallo.
- **Vacunas faltantes:** Directivas del VCM (Vector de Conocimiento Mínimo) sin representación suficiente en el grafo.

**Clasificación de fracturas:**
- **Crítica:** Weight > 1.0 antes de decaer, o dependientes con weight > 1.0
- **Moderada:** Dependientes activos con weight <= 1.0
- **Baja:** Dependientes con pocas ocurrencias (posible falso positivo)

**Arquitectura de vacunas (desde 2026-04-24):**

Las vacunas tienen **scope project-agnostic**:

- **Vacunas globales** (`scope: "global"`): Directivas universales que protegen a TODOS los proyectos. Si la vacuna existe sedimentada en CUALQUIER proyecto del grafo con weight suficiente, NO se reporta como faltante.
  
  Ejemplos: emoji, stdout.flush, git push, 3 intentos, delete()

- **Vacunas project-specific** (`scope: "project_specific"`): Directivas que solo aplican a proyectos declarados en `applicable_projects`. Solo se verifican cuando se consulta un proyecto aplicable.
  
  Ejemplos: YAML (solo concept-sediment), catalogo (solo inducop)

**Implicación operacional:** Una vacuna global sedimentada en proyecto "inducop" protege también a "concept-sediment". No es necesario sedimentar la misma vacuna en cada proyecto.

---

### 7. `cs_session_open`
Apertura asistida de sesión via Marco Teórico Vivo (MTV). Compone múltiples `cs_search_concepts` + `cs_get_alerts` en una sola invocación.

**Parámetros:**
- `topic` (string, required): Tema de la sesión (label informativo)
- `queries` (list[string], required, 1-5): Queries que reflejan el tema desde ángulos distintos. El caller las provee — el tool no genera ángulos
- `domain` (string, optional): Filtra dominio en todas las queries
- `project` (string, optional): Filtra proyecto en queries y alertas
- `limit_per_query` (int, default=5): Resultados por query

**Retorna:**
- `concepts_ranked`: conceptos deduplicados por nombre, ordenados por mejor similaridad observada entre queries
- `concepts_per_query`: resultados crudos por query (para distinguir qué ángulo trajo qué)
- `alerts`: alertas inmunológicas activas

**Diseño:** reduce fricción del protocolo MTV de 3-5 tool calls a 1. No toma decisiones metodológicas: solo compone tools existentes.

---

### 8. `cs_audit_thread`
Auditoría batch de cobertura de un hilo de conceptos en el grafo. Implementa la norma D-T4 (chequeo recursivo pre-sesión).

**Parámetros:**
- `concepts` (list[string], required, 1-20): Nombres (o substrings) de los conceptos del hilo a verificar. Búsqueda por texto ILIKE (tilde-sensitive)
- `project` (string, optional): Filtrar por proyecto en todas las búsquedas
- `include_graph` (bool, default=true): Si true, agrega relaciones (top 5) y ocurrencias recientes (top 3) del top match

**Retorna:**
- `summary`: total, encontrados/faltantes, distribución por status
- `coverage`: por cada thread_name → matched_concept, status, weight, type, domains, last_seen, alt_matches, (opcional) outgoing_relations + incoming_relations + recent_occurrences

**Limitación documentada:** búsqueda ILIKE es tilde-sensitive. Si un concepto del hilo tiene tildes, incluir variantes con/sin tilde.

---

### 9. `cs_record_measurement` *(write)*
Registra una medición compuesta IA-humano en `graph_measurement`. Per protocolo Estratega §4 y schema D2 agnóstico al operador.

**Parámetros:**
- `contexto` (string, required, no vacío): Descripción del problema/sesión donde ocurrió la medición
- `outcome` (string, required): Uno de `resolvio`, `resolvio_parcial`, `no_resolvio`, `aun_no_observable`
- `contribucion_ia` (string, optional, default=""): Aporte de la IA (superposición propuesta)
- `contribucion_humana` (string, optional, default=""): Aporte del humano (colapso elegido + criterio)
- `project` (string, optional, default=""): Tag de proyecto
- `domains` (list[string], optional): Lista de slugs de `graph_domain`. Cada slug debe existir
- `agent` (string, default="unknown"): Caller declara su identidad para audit log

**Retorna:** `{ok, id, created_at, audit_id}` en éxito; `{ok: false, error}` en fallo de validación.

**Comportamiento clave:**
- **NO sedimenta en grafo conceptual** — measurements viven en tabla aparte (`graph_measurement`), fuera del espacio de búsqueda semántica. Esto es deliberado para evitar la patología F37.
- **Transacción atómica:** INSERT measurement + INSERT m2m domains + INSERT audit log se commitean juntos. Si algo falla, NADA queda en `graph_measurement` pero SÍ queda registro de error en `mcp_audit_log`.
- **Validaciones (per protocolo Estratega §5):** outcome ∈ enum, contexto no vacío, domain slugs existen. NO juzga "calidad" del contenido, NO infiere outcome, NO sub-categoriza.

---

### 10. `cs_get_audit_log`
Consulta read-only del audit log de write tools (`mcp_audit_log`). Base operativa de D5 (revisabilidad de matriz centaura).

**Parámetros (todos opcionales):**
- `agent` (string): Filtrar por agent (ej: `CodeMCP`, `CodeCS`)
- `tool_name` (string): Filtrar por nombre exacto del tool
- `target_id` (string UUID): Filtrar por recurso afectado
- `success` (bool): Filtrar por éxito/fracaso
- `since` (ISO datetime): Solo entradas posteriores
- `limit` (int, default=50, max=200)

**Retorna:** `{count, entries: [...]}` ordenado por timestamp DESC. Cada entry incluye id, timestamp, agent, tool_name, payload, target_id, target_table, success, error_message.

---

## 📌 Schema YAML — Relación `interpreted_under` (nueva 2026-05)

`interpreted_under` es el **único caso especial fuera de `RELATION_MAP`**. Sintaxis mínima:

```yaml
related_to:
  - target: "frame:<alias>"
    relation: interpreted_under
    notes: "<anotación opcional>"
```

Cuando el extractor (`extract_concepts.py` en concept-sediment) detecta este patrón, la cita NO va a `graph_conceptrelation` sino a la tabla separada `graph_frame_reference` (decisión gamma F45 / 2026-05-02). Candado bidireccional: `frame:` ↔ `interpreted_under` son simétricamente obligatorios; cualquier desalineación produce ERROR/WARNING + skip con audit log explícito.

**Detalle completo** (validación de archivo en `FRAMES_DIR`, candados, ground arquitectónico, referencias): [`INTERPRETED_UNDER.md`](INTERPRETED_UNDER.md).

---

## 🚀 Deployment (Railway)

**Proyecto:** `balanced-determination`
**Servicio:** `mcp-server`
**URL:** `https://mcp-server-production-994a.up.railway.app/mcp`

### Variables de entorno requeridas

```bash
DATABASE_URL=postgresql://user:pass@host:port/concept_sediment
OPENAI_API_KEY=sk-proj-***
PORT=8000  # Inyectado automáticamente por Railway
```

### Deploy desde local

```bash
cd concept-sediment-mcp/
git add .
git commit -m "mensaje"
git push origin master  # Railway auto-deploya
```

### Health check

```bash
curl https://mcp-server-production-994a.up.railway.app/health
# {"status":"ok","service":"concept_sediment_mcp","version":"1.0.0"}
```

---

## 📦 Estructura del proyecto

```
concept-sediment-mcp/
├── server.py              # FastMCP app + Uvicorn server (registra 10 tools)
├── queries.py             # SQL queries para 5 read tools del grafo
├── humandato_queries.py   # Alertas inmunológicas (VCM) — read tools
├── write_queries.py       # SQL para write tools (cs_record_*)
├── audit_queries.py       # Init mcp_audit_log + read tools sobre audit
├── migrations/
│   └── 001_audit_log.sql  # Schema mcp_audit_log (idempotente al startup)
├── db.py                  # SQLAlchemy engine + sessions stateless
├── requirements.txt       # Dependencias Python
├── Dockerfile             # Build config para Railway
├── railway.toml           # Deploy config
├── .env.example           # Template de variables de entorno
└── README.md              # Este archivo
```

---

## 🔌 Configuración en Claude Code

Agregar al archivo `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "claude_ai_Concept_Sediment": {
      "url": "https://mcp-server-production-994a.up.railway.app/mcp",
      "transport": "sse"
    }
  }
}
```

Reiniciar Claude Code para que reconozca el servidor.

---

## 🧪 Desarrollo local

```bash
# 1. Clonar repositorio
git clone https://github.com/[tu-usuario]/concept-sediment-mcp.git
cd concept-sediment-mcp/

# 2. Crear virtualenv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 5. Ejecutar servidor
python server.py
# Server en http://localhost:8000
```

---

## 📊 Base de datos (PostgreSQL + pgvector)

**Tablas principales (Django app `graph`):**
- `graph_concept`: Conceptos (name, type, status, weight, embedding)
- `graph_conceptrelation`: Relaciones entre conceptos
- `graph_domain`: Dominios de conocimiento
- `graph_sessionlog`: Log de sesiones procesadas
- `graph_conceptoccurrence`: Ocurrencias de conceptos en sesiones
- `graph_measurement`: Mediciones compuestas IA-humano (D2, ver tool 9)
- `graph_measurement_domains`: M2M measurement ↔ domain

**Tablas del MCP (no del grafo conceptual):**
- `mcp_audit_log`: Audit append-only de write tools del MCP server

**Extensión pgvector:** Habilita búsquedas semánticas con embeddings.

```sql
-- Búsqueda por similaridad coseno
SELECT name, 1 - (embedding <=> CAST(:vec AS vector)) AS similarity
FROM graph_concept
WHERE embedding IS NOT NULL
ORDER BY similarity DESC
LIMIT 10;
```

---

## 📚 Documentación relacionada

- **Concept Sediment (Django):** Procesamiento de session YAMLs → grafo
- **MCP Protocol:** https://modelcontextprotocol.io/
- **FastMCP:** Framework Python para servidores MCP
- **pgvector:** https://github.com/pgvector/pgvector

---

## 🔒 Seguridad

- **Política write/read:** El servidor escribe al grafo solo a través de tools `cs_record_*` y `cs_promote_*`, con audit log append-only obligatorio. Las tools de lectura no modifican estado.
- **Variables sensibles:** `OPENAI_API_KEY` y `DATABASE_URL` en variables de entorno (nunca en código)
- **CORS:** Configurado para aceptar conexiones desde cliente MCP oficial
- **Rate limiting:** Implementado por Railway (no en código)

---

## 📝 Changelog

### 2026-03-30
- **Fix:** Búsquedas por embedding con `CAST(:vec AS vector)` en lugar de `:vec::vector` (compatibilidad SQLAlchemy + PostgreSQL)
- **Deployment:** Servidor activo en Railway production

### 2026-03-29
- **Fix:** Iteración sobre fractures dict en `cs_get_alerts`
- Clasificación de fracturas por severidad (crítica/moderada/baja)

---

## 🤝 Contribución

Este servidor es parte del proyecto Concept Sediment. Para contribuir:

1. Fork del repositorio
2. Crear branch: `git checkout -b feature/nueva-funcionalidad`
3. Commit: `git commit -m "feat: descripción"`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Crear Pull Request

---

## 📄 Licencia

[Especificar licencia aquí]

---

## 👤 Autor

Proyecto Concept Sediment - Sistema de memoria semántica para agentes AI

**Contacto:** [Tu información de contacto]

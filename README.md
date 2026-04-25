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
│  └─> 7 MCP Tools (read-only)                                │
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

**Base de datos compartida:** El servidor MCP comparte la misma instancia PostgreSQL que el proyecto Django `concept-sediment`. El servidor es **read-only** — solo consulta el grafo, no lo modifica.

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
├── server.py              # FastMCP app + Uvicorn server
├── queries.py             # SQL queries para 5 tools MCP
├── humandato_queries.py   # Alertas inmunológicas (VCM)
├── db.py                  # SQLAlchemy engine + sessions
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

**Tablas principales:**
- `graph_concept`: Conceptos (name, type, status, weight, embedding)
- `graph_conceptrelation`: Relaciones entre conceptos
- `graph_domain`: Dominios de conocimiento
- `graph_sessionlog`: Log de sesiones procesadas
- `graph_conceptoccurrence`: Ocurrencias de conceptos en sesiones

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

- **Read-only:** El servidor NO modifica el grafo, solo consulta
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

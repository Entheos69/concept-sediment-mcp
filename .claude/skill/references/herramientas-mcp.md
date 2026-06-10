# Herramientas MCP de Concept-Sediment

Las **11 herramientas `cs_*`** expuestas por el MCP server (`concept-sediment-mcp/server.py`).

Para CodeMCP — agente que mantiene el server — cada tool es **objeto de desarrollo**: schema Pydantic, query SQL, módulo auxiliar, audit log, dependencias del grafo. La perspectiva de consumidor (cómo se usa al sedimentar/buscar) viene secundaria, ya que el dueño del MCP debe entender ambos lados con detalle.

## 0. Inventario

| # | Tool | R/W | Categoría | Linea def | Implementación principal |
|---|------|:-:|---|--:|---|
| 1 | `cs_search_concepts` | R | Búsqueda | server.py:116 | `queries.search_concepts_by_embedding` + fallback ILIKE |
| 2 | `cs_get_active_concepts` | R | Búsqueda | server.py:176 | `queries.get_active_concepts` |
| 3 | `cs_get_concept_graph` | R | Búsqueda | server.py:220 | `queries.get_concept_with_relations` |
| 4 | `cs_get_domain_summary` | R | Búsqueda | server.py:261 | `queries.get_domain_summary_data` |
| 5 | `cs_get_session_context` | R | MTV | server.py:304 | `queries.get_session_context_data` |
| 6 | `cs_get_alerts` | R | MTV | server.py:344 | `humandato_queries.get_all_alerts` + `discard_queries.get_discards_summary` |
| 7 | `cs_session_open` | R | MTV | server.py:499 | composer (queries + humandato) |
| 8 | `cs_get_discards` | R | Auditoría | server.py:593 | `discard_queries.get_discards_detail` |
| 9 | `cs_audit_thread` | R | Auditoría | server.py:657 | composer (queries) |
| 10 | `cs_record_measurement` | **W** | Write | server.py:806 | `write_queries.record_measurement` + audit log |
| 11 | `cs_get_audit_log` | R | Auditoría | server.py:885 | `audit_queries.get_audit_log` |

**MCP annotations** (declaradas en cada `@mcp.tool(...)` decorator):
- `readOnlyHint: True`, `idempotentHint: True` para 10 tools (1-9, 11).
- `readOnlyHint: False`, `idempotentHint: False` solo para `cs_record_measurement` (Tool 10).
- `destructiveHint: False`, `openWorldHint: False` en todas.

**Imports del server** (`server.py:43-54`):
```python
from queries import (
    search_concepts_by_embedding, search_concepts_by_text,
    get_active_concepts, get_concept_with_relations,
    get_domain_summary_data, get_session_context_data,
)
from humandato_queries import get_all_alerts
from discard_queries import get_discards_detail
from write_queries import record_measurement
from audit_queries import init_audit_log_table, get_audit_log
```

**Endpoint público:**
```
URL:       https://mcp-server-production-994a.up.railway.app/mcp
Health:    https://mcp-server-production-994a.up.railway.app/health
Transport: Streamable HTTP (compatible con claude.ai), SSE fallback
Mode:      stateless con JSON responses
```

---

## 1. MTV pipeline (apertura de sesión)

Las 3 tools que un agente típico ejecuta ANTES de tocar contenido. Reducen fricción del protocolo Marco Teórico Vivo.

### Tool 5 — `cs_get_session_context`

**Firma** (`server.py:277-292`):
```python
class GetSessionContextInput(BaseModel):
    project: Optional[str] = None        # filtra por tag de proyecto
    domains: Optional[list[str]] = None  # filtra dominios relevantes
    limit: int = 20                      # 5-50
    format: str = "markdown"             # 'markdown' | 'json'
```

**Implementación** (`server.py:304-319`): llama a `get_session_context_data(project, domains, limit, output_format)` en `queries.py`. Retorna directamente el texto/JSON formateado por la query (sin envolver).

**Cuándo usarlo:** primer call del protocolo de apertura. Carga conceptos activos relevantes a los dominios que se van a trabajar, evitando ruido de otros dominios.

**Notas de mantenimiento:**
- Templates markdown viven en `queries.get_session_context_data`.
- Ranking interno: weight + last_seen.
- Si `domains=None`: retorna de todos los dominios del proyecto.
- Formato `json` para procesamiento programático; `markdown` para LLM.

---

### Tool 6 — `cs_get_alerts`

**Firma** (`server.py:326-331`):
```python
class GetAlertsInput(BaseModel):
    project: Optional[str] = None
```

**Implementación** (`server.py:344-453`):
- Llama `humandato_queries.get_all_alerts(project)` (`humandato_queries.py:386`):
  - Combina `get_fractures()`, `get_missing_vaccines()`, `get_discards_summary()`.
  - Clasifica fracturas por severidad (criticas/moderadas/bajas) en `_calcular_severidad`.
  - Filtra fracturas reparadas via `_fractura_reparada` (chequea relations refines/resolves/instance_of/supersedes).
- Formato narrativo construido en `server.py`:
  - Stable-check (`server.py:365-369`): considera `total_pending_real` (F47-D1.1), no `total_pending` puro — smokes solos no rompen estable.
  - Sección "ARISTAS PENDING" (`server.py:414-451`): total, productivas (`total_real`), por reason, top 3 invalid types, antiguedad, tipos meeting promo rule.
  - Mensaje `[INFO]` cuando 100% son smokes.

**Tres tipos de alerta:**
1. **Fracturas**: conceptos `dormant`/`archived` con dependientes activos. Señal predictiva de fallo.
2. **Vacunas faltantes**: directivas VCM sin representación suficiente en el grafo. Listadas en `humandato_queries.VCM_DIRECTIVES` (`humandato_queries.py:21-121`) con scope `global` o `project_specific`.
3. **Aristas pending** (F47 C2d): RelationDiscard con tipos inválidos / targets no encontrados.

**Cuándo usarlo:** segundo call del protocolo de apertura, después de `cs_get_session_context`.

**Interpretación:**
- Sin alertas — sistema estable, proceder.
- Fracturas — reportar al Guardian; investigar por qué el concepto se debilitó.
- Vacunas faltantes — agregar concepto que represente la directiva, o mostrar al Guardian el riesgo de violación.
- Aristas pending productivas (`total_pending_real > 0`) — reconciliar (alias o promoción enum) o explicar por qué quedan pending.

**Notas de mantenimiento:**
- Umbrales del narrative parametrizados via env vars (`discard_queries.py:22-24`):
  - `CS_DISCARD_STALE_DAYS=7` (días para considerar discard "stale").
  - `CS_DISCARD_PROMO_OCCURRENCES=3` (regla B1.2 mínimo de ocurrencias).
  - `CS_DISCARD_PROMO_AGENTS=2` (regla B1.2 mínimo de agentes distintos).
- F47-D1.1 (2026-05-09): LEFT JOIN `graph_sessionlog` en CTE de discard_counts y type_stats; `total_pending_real` con FILTER `is_test=FALSE`; type_stats excluye smokes para no inflar regla B1.2.
- Agregar nueva vacuna VCM: editar `VCM_DIRECTIVES` con `scope` (`global` aplica a todos los proyectos, `project_specific` con `applicable_projects=[...]`).

---

### Tool 7 — `cs_session_open`

**Firma** (`server.py:460-486`):
```python
class SessionOpenInput(BaseModel):
    topic: str                          # label informativo, no afecta búsqueda
    queries: list[str]                  # 1-5 queries (ángulos distintos)
    domain: Optional[str] = None        # filtra search
    project: Optional[str] = None       # filtra search Y alerts
    limit_per_query: int = 5            # 1-15
```

**Implementación** (`server.py:499-559`): para cada query ejecuta `search_concepts_by_embedding` (con ILIKE fallback), deduplica concepts por nombre (mantiene mejor similarity entre las queries), y al final llama `get_all_alerts(project)`. Retorna paquete con:
- `concepts_ranked`: dedupe ordenado por similarity DESC.
- `concepts_per_query`: resultados crudos por query (qué ángulo trajo qué).
- `alerts`: alertas inmunológicas activas.

Composer puro — no toma decisiones metodológicas.

**Cuándo usarlo:** atajo del protocolo MTV. Reduce fricción de 3-5 tool calls a 1.

**Notas de mantenimiento:**
- NO genera ángulos internamente. Caller provee porque cada agente conoce mejor su dominio.
- Filtro `project` aplica a queries Y a alertas.
- Filtro `domain` solo aplica a queries (alertas no tienen filtro de dominio).
- Origen: D3 del plan MTV (sedimento active 2026-04-24).

---

## 2. Búsqueda y exploración

### Tool 1 — `cs_search_concepts`

**Firma** (`server.py:87-103`):
```python
class SearchConceptsInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    domain: Optional[str] = None
    project: Optional[str] = None
    limit: int = 10                      # 1-50
```

**Implementación** (`server.py:116-142`):
1. Intenta `search_concepts_by_embedding(query, domain, project, limit)` (modelo OpenAI text-embedding-3-small).
2. Si no hay results, fallback a `search_concepts_by_text(query, domain, project, limit)` (ILIKE).
3. Ambos en `queries.py`.

**Cuándo usarlo:**
- Verificar si un concepto ya existe antes de sedimentar duplicado.
- Recuperar discusiones relacionadas a un tema.
- 2-3 ángulos distintos al ejecutar P-MTV.

**Notas de mantenimiento:**
- Modelo OpenAI: `text-embedding-3-small`. Cambio de modelo requiere reindex de toda la tabla `concept_embedding` (no hay script batch aún — deuda).
- Threshold de similaridad y trigger del fallback ILIKE: ver `queries.search_concepts_by_embedding`.
- Costo de embedding: ~700ms por query (verificado 2026-05-08).
- **MTV cross-project**: cuando los conceptos NO pertenecen a un proyecto específico (Mirador, axiomas meta-proyecto), llamar SIN filtro `project` (sedimento active w:2.0 "MTV cross-project como vacuna de scope", 2026-05-03).

---

### Tool 2 — `cs_get_active_concepts`

**Firma** (`server.py:149-163`):
```python
class GetActiveConceptsInput(BaseModel):
    domain: Optional[str] = None
    project: Optional[str] = None
    concept_type: Optional[str] = None   # 'principle' | 'pattern' | 'event'
    limit: int = 15                      # 1-50
```

**Implementación** (`server.py:176-189`): `queries.get_active_concepts(domain, project, concept_type, limit)`.

**Cuándo usarlo:** ver SOLO principios consolidados, o patrones recurrentes, o eventos recientes — sin ruido entre niveles.

**Notas de mantenimiento:**
- `status='active'` se determina por sistema decay (no es campo manual).
- `type` se infiere por sistema (regla #4 del schema YAML: NO incluir `type` en YAMLs producidos).
- Default `limit=15` apropiado para sedimentación operativa, no para análisis exhaustivo.

---

### Tool 3 — `cs_get_concept_graph`

**Firma** (`server.py:196-207`):
```python
class GetConceptGraphInput(BaseModel):
    concept_name: str                    # búsqueda parcial case-insensitive
    depth: int = 1                       # 1-3 (BFS)
```

**Implementación** (`server.py:220-235`): `queries.get_concept_with_relations(concept_name, depth)`. Si no encuentra, retorna error con sugerencia de usar `cs_search_concepts`.

**Output:**
- Concepto central (data + dominios).
- `outgoing_relations`: `[{target, relation_type, strength, ...}, ...]`.
- `incoming_relations`: análogo.
- `recent_occurrences`: ocurrencias en sesiones recientes con session_id, depth, project.

**Cuándo usarlo:** entender contexto relacional de un concepto antes de tomar decisión de diseño. Útil para confirmar si un sedimento `dormant` realmente quedó huérfano o tiene dependientes activos.

**Notas de mantenimiento:**
- `depth=1` = vecinos directos. `depth=3` = vecinos de vecinos de vecinos (caro).
- BFS con límite de depth.
- No hay caching — cada call ejecuta SQL fresco.

---

### Tool 4 — `cs_get_domain_summary`

**Firma** (`server.py:242-248`):
```python
class GetDomainSummaryInput(BaseModel):
    domain: str                          # slug obligatorio
```

**Implementación** (`server.py:261-270`): `queries.get_domain_summary_data(domain)`.

**Output:** total conceptos, distribución type/status, top conceptos por weight, relaciones más fuertes, actividad reciente.

**Cuándo usarlo:** entender estado agregado de un dominio antes de sedimentar nuevos conceptos en él, o para reportar al Guardian el "salud" de un área del grafo.

---

## 3. Auditoría y forensia

### Tool 8 — `cs_get_discards` (F47 C2e + F47-D1.1)

**Firma** (`server.py:566-580`):
```python
class GetDiscardsInput(BaseModel):
    reason: Optional[str] = None         # 'unknown_type' | 'target_not_found'
    status: Optional[str] = "pending"    # default solo pending
    project: Optional[str] = None        # via session_id prefix
    limit: int = 50                      # 1-200
```

**Implementación** (`server.py:593-613`): `discard_queries.get_discards_detail(reason, status, project, limit)` (`discard_queries.py:176-264`).

**Output (cada entry):**
```json
{
  "discard_id": "<uuid>",
  "session_id": "<str>",
  "source_concept_slug": "<str|null>",
  "source_name_raw": "<str>",
  "target_name_raw": "<str>",
  "relation_type_raw": "<str>",
  "reason": "unknown_type | target_not_found",
  "resolution_status": "pending | mapped_to_alias | promoted_to_enum | rejected",
  "discarded_at": "<iso8601>",
  "target_match_type": "slug_reconcilable | target_not_found | null",
  "alias_proposal": null,
  "is_test": false   // F47-D1.1 (2026-05-09): COALESCE(sl.is_test, FALSE)
}
```

**Output summary:** `total`, `total_real` (F47-D1.1, excluye smokes), `by_reason`, `by_status`, `oldest_pending_days`.

**Cuándo usarlo:**
- Inspeccionar discordancias schema-YAML estructuralmente sin Django shell.
- Auditar aristas perdidas y seguimiento de resoluciones Guardian.
- Filtrar smokes via `is_test=False` client-side cuando solo quieres productivos.

**Notas de mantenimiento:**
- LEFT JOIN con `graph_sessionlog` post F47-D1.1 (`discard_queries.py:170-172`).
- `target_match_type` calculado dinámicamente via subquery SQL: `slug_reconcilable` si existe concepto cuyo slug coincide con la regex normalizada del `target_name_raw`.
- `alias_proposal`: TODO C3 (fuzzy match con `difflib.SequenceMatcher` contra `RelationAlias`, ergonomía operativa, ~15-20 LOC).

---

### Tool 9 — `cs_audit_thread` (D-T4)

**Firma** (`server.py:620-644`):
```python
class AuditThreadInput(BaseModel):
    concepts: list[str]                  # 1-20 nombres del hilo
    project: Optional[str] = None
    include_graph: bool = True           # agrega relations + occurrences del top match
```

**Implementación** (`server.py:657-730`): para cada `concept_name` busca por `search_concepts_by_text` ILIKE (top 3), reporta status/weight/type/dominios/last_seen del top match, lista alt matches por nombre. Si `include_graph=True`: agrega outgoing/incoming relations (top 5) y `recent_occurrences` (top 3) del top match via `get_concept_with_relations`.

**Output summary:** `total_thread_items`, `found_in_graph`, `missing_from_graph`, `by_status` (active/dormant/archived/no_encontrado).

**Cuándo usarlo:** chequeo recursivo pre-sesión (norma D-T4). Sustituye N pasos manuales de `cs_search_concepts` por una sola call. Útil para verificar cobertura de un plan multi-sesión.

**Notas de mantenimiento:**
- Composer puro: usa `search_concepts_by_text` (no embedding) + `get_concept_with_relations`.
- Caller provee la lista esperada — el tool NO infiere el hilo.
- Origen: D12 del Plan Multi-Sesión Estratega CS006, deployed commit 62512ba 2026-04-25.

---

### Tool 11 — `cs_get_audit_log`

**Firma** (`server.py:850-872`):
```python
class GetAuditLogInput(BaseModel):
    agent: Optional[str] = None
    tool_name: Optional[str] = None
    target_id: Optional[str] = None       # UUID del recurso afectado
    success: Optional[bool] = None
    since: Optional[str] = None           # ISO datetime
    limit: int = 50                       # 1-200
```

**Implementación** (`server.py:885-906`): `audit_queries.get_audit_log(agent, tool_name, target_id, success, since, limit)`.

**Output:** `count` + array de entries con timestamp, agent, tool_name, payload, target_id, success, error.

**Cuándo usarlo:** verificar qué agente invocó qué write tool, con qué payload, éxito/fallo. Base operativa de revisabilidad de matriz centaura (D5).

**Notas de mantenimiento:**
- Tabla `mcp_audit_log` inicializada en `app_lifespan` (`server.py:71`, `audit_queries.init_audit_log_table()`).
- Append-only por convención de código (no DELETE/UPDATE en write_queries.py).
- Origen: D2-scaffold del Plan Estratega, commit 1188870 + fix ef71d34, 2026-04-25.

---

## 4. Write tools

### Tool 10 — `cs_record_measurement` (D2)

**Firma** (`server.py:748-793`):
```python
class RecordMeasurementInput(BaseModel):
    contexto: str                        # problema/sesión, sin schema interno
    outcome: str                         # 4 valores mutuamente excluyentes
    contribucion_ia: str = ""            # superposición propuesta IA
    contribucion_humana: str = ""        # colapso humano + criterio
    project: str = ""                    # tag de proyecto, max 50
    domains: Optional[list[str]] = None  # slugs graph_domain (deben existir)
    agent: str = "unknown"               # quien invoca, max 50
```

**Annotations clave** (`server.py:798-803`):
- `readOnlyHint: False` — única tool con esto.
- `idempotentHint: False` — cada call crea nueva measurement.

**Implementación** (`server.py:806-839`): `write_queries.record_measurement(...)` envuelto en try/except ValueError. Retorna `{"ok": True, ...}` o `{"ok": False, "error": str}`.

**Validaciones (en `write_queries.record_measurement`):**
- `outcome` ∈ `{resolvio, resolvio_parcial, no_resolvio, aun_no_observable}` (mutuamente excluyentes per protocolo Estratega §3).
- `contexto` no vacío.
- Todos los `domains[i]` existen en `graph_domain` (no se crean silenciosamente).

**Audit log:** cada invocación (success o failure) deja entrada en `mcp_audit_log`. Transacción atómica: si validación falla, NADA queda en `graph_measurement` pero SÍ queda registro de error en audit log para trazabilidad.

**Disciplina (per protocolo Estratega §4-5):**
- NO sedimenta en grafo conceptual — measurements viven en tabla `graph_measurement` separada, fuera del espacio de búsqueda semántica. Deliberado para evitar la patología que F37 diagnostica (formalización reactiva).
- NO juzga calidad del contexto/contribución.
- NO infiere outcome.
- NO sub-categoriza.

**Cuándo usarlo:** registrar evento medible IA-humano (resolución compuesta) para análisis posterior. NO confundir con sedimentación conceptual (use YAMLs de cierre para eso).

---

## 5. Reglas operativas

### 5.1 Fallback `knowledge/*.yaml`

Si el MCP server no responde (deploy en curso, BD caída, restart de Railway), los conceptos siguen accesibles en disco:
```
../concept-sediment/knowledge/*.yaml
```
Lectura directa con `grep`/`cat`. No es la versión "viva" (sin embeddings frescos), pero sirve para diagnóstico y continuidad operativa.

### 5.2 Refresh de tools post-deploy via ToolSearch

Si el server agrega tools nuevas (e.g., `cs_get_discards` en F47 C2e), el cliente Claude Code puede tener cache stale del listado deferred. Solución (sedimento active 2026-05-08):

```
ToolSearch select:mcp__claude_ai_Concept_Sediment__cs_<nombre>
```

Carga el schema lazy del server. NO confiar en que el system reminder esté actualizado post-deploy.

**Caveat acotado** (verificado 2026-05-09 con F47-D1.1): para tools MODIFICADAS (output expandido sin breaking change de input schema), `ToolSearch` no es estrictamente necesario — la cache de input sigue válida y el output viene del server live. NO generaliza al caso de tools removidas o renombradas.

### 5.3 MTV cross-project

Conceptos del Mirador, grafo, axiomas meta-proyecto NO están taggeados con un proyecto específico. Para encontrarlos, llamar `cs_search_concepts` o `cs_session_open` SIN filtro `project` (sedimento active w:2.0 "MTV cross-project como vacuna de scope", 2026-05-03).

### 5.4 Regla de oro del consumo

Consultar antes de tomar decisiones que puedan repetir errores ya documentados. Conceptos con mayor `weight` y más sesiones son los más consolidados — déjalos pesar. Las relaciones `depends_on`, `derived_from`, `resolves`, `instance_of` revelan cadenas causales que explican por qué algo se hizo así.

### 5.5 Pre-push P-MTV

Cerrar YAML de sesión con P-MTV ANTES del push (memoria local `feedback_pmtv_pre_push`). Tan pronto como pushes a `concept-sediment-mcp`, Railway redeploya y los `cs_*` mueren temporalmente — P-MTV imposible post-push.

---

## 6. Consideraciones de desarrollo MCP

### 6.1 Ciclo de cambio típico

1. **Editar local** (`server.py`, `*queries.py`).
2. **Test estructural local** sin BD: imports, signatures, contenido SQL string. Ver `test_c2d_c2e.py` y `test_smoke_exclusion_mcp.py` como pattern (script Python con prints + asserts, no pytest).
3. **Test con BD** (`railway run python -c "..."`). Útil pre-push, opcional si test local cubre.
4. **Cierre YAML PRE-push** (sección 5.5).
5. **Push autorizado** por Guardian (memoria global "git push") → auto-redeploy Railway (~1-2 min, `cs_*` mueren).
6. **Validación post-deploy** vía `cs_*`.

### 6.2 Schema compatibility

- **Output JSON de tools**: agregar campos OK; remover/renombrar = breaking change que requiere coordinación inter-agente.
- **YAMLs de entrada** (consumidos por extract_concepts lado CodeCS): agregar campo opcional OK; remover/renombrar = romper YAMLs históricos.
- **Validador de status** (`extract_concepts.py:248-251` lado CodeCS): valores canónicos `draft|reviewed|processed|smoke_test`. Pre-flight de `process_session.sh` debe espejar estos valores.

### 6.3 Embeddings

- Modelo: `text-embedding-3-small` (OpenAI).
- Costo: ~700ms por embedding (verificado 2026-05-08).
- Cambio de modelo requiere reindex completo de `concept_embedding`. Sin batch script aún (deuda C3).
- `extract_concepts --skip-embeddings` (lado CodeCS) evita la llamada OpenAI; útil para smokes y tests.

### 6.4 Contratos públicos

Todos los agentes (CodeI, CodeCS, Cowork, Bibliotecario, Mirador) dependen de los `cs_*`. Cambios breaking requieren:
- Coordinación previa con Guardian.
- Heads-up al equipo de agentes via cierre YAML CodeMCP que articule el contrato nuevo.
- Migración documentada si hay impacto en YAMLs históricos.

### 6.5 F47 — Arquitectura tres-capas (axioma de no-descarte)

**Capa 1 — enum canónico** (`graph/models.py:RelationType`):
- Tipos válidos. Promociones via regla B1.2 (≥3 ocurrencias × ≥2 agentes distintos).
- Tipos agregados en C2a: `RELATED`, `COMPLEMENTS`.

**Capa 2 — RelationAlias** (`graph/models.py`):
- Typos / variantes mapeadas a tipos canónicos.
- Seeded en C2b con 5 aliases iniciales.

**Capa 3 — RelationDiscard** (`graph/models.py`):
- Aristas no procesables capturadas para auditoría futura.
- Reasons: `unknown_type` (tipo fuera de enum + sin alias), `target_not_found` (target no existe ni reconciliable).
- Resolution status: `pending | mapped_to_alias | promoted_to_enum | rejected`.

**Mantenimiento:**
- `cs_get_alerts` reporta capa 3 en sección "ARISTAS PENDING" (`server.py:414+`).
- `cs_get_discards` lista capa 3 con filtros.
- Comando `repair_discards apply` (lado CodeCS) resuelve aristas.

### 6.6 F47-D1.1 — Axioma de no-contaminación de smokes

`SessionLog.is_test=True` excluye smokes de:
- **Promoción al enum** (regla B1.2) — vía `Concept._productive_occurrences()` en model (lado CodeCS).
- **Decay** — vía `SessionLog.objects.filter(is_test=False)` en `recalculate_decay`.
- **Concept aggregates** (`weight`, `last_seen_at`, `projects`) — vía branch `if is_test:` en `Concept.add_occurrence`.
- **Queries productivas del MCP** — vía `total_pending_real` en `cs_get_alerts` y campo `is_test` en `cs_get_discards` (LEFT JOIN `graph_sessionlog`).

**Implicación para CodeMCP:** cuando agregue queries productivas nuevas que toquen `graph_relationdiscard` o `graph_concept`, considerar si el axioma `is_test` debe propagarse a la nueva query. Caso a caso, no automático.

### 6.7 Manejo de UUIDs

Generar UUIDs en Python con `uuid.uuid4()` y pasarlos como parámetro al INSERT. NO depender de `gen_random_uuid()` / `uuid_generate_v4()` — extensiones `pgcrypto` / `uuid-ossp` pueden no estar disponibles en Railway PG. Patrón consistente con Django.

### 6.8 BD compartida Django + MCP

Las dos superficies (Django `concept-sediment` y FastMCP `concept-sediment-mcp`) comparten la misma instancia Postgres en Railway:

- **Tablas `graph_*`** (e.g., `graph_concept`, `graph_conceptrelation`, `graph_relationdiscard`, `graph_sessionlog`): dominio Django. Migraciones aplicadas via `manage.py migrate`.
- **Tablas `mcp_*`** (e.g., `mcp_audit_log`): dominio MCP. Inicialización via `audit_queries.init_audit_log_table()` en lifespan.

**Implicación:** un push a `concept-sediment` (Django) puede aplicar migration que afecta tablas leídas por el MCP. El MCP server NO se restartea automáticamente — sigue corriendo el código de su último deploy. Si el cambio Django introduce columna nueva, el MCP debe actualizarse para leerla (caso F47-D1: CodeCS agregó `is_test`, CodeMCP propagó al SELECT en 2 sesiones distintas).

---

## 7. Actualización de este documento

Cuando se agregue / modifique tool en `server.py`:

1. Actualizar tabla del inventario en sección 0 (incluyendo `linea def`).
2. Agregar / modificar sub-sección con firma Pydantic + implementación + cuándo usarlo + notas.
3. Si el cambio es F47-relevant: documentar en sección 6.5 / 6.6.
4. Verificar que las líneas (`server.py:NNN`) queden correctas — un commit que reordena tools invalida todo.
5. Si se agrega categoría nueva (e.g., reasoning tools), considerar nueva sección 1-4 antes de añadir al inventario.

Convención de líneas: el `server.py:NNN` siempre apunta al `def cs_<tool>`, no al decorator. Para input class: rango `server.py:NNN-MMM` del bloque `class XInput(BaseModel)`.

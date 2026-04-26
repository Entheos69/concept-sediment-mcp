# Stack y Arquitectura de Concept-Sediment

Vista del sistema desde la perspectiva de CodeCS (mantenedor, no solo consumidor).

## Componentes

| Componente | Descripción | Ubicación |
|------------|-------------|-----------|
| **MCP Server** | Servidor FastMCP (Python) que expone `cs_*` tools | `mcp_server/` |
| **Endpoint público** | Railway deployment | `https://mcp-server-production-994a.up.railway.app/mcp` |
| **Sessions store** | YAMLs draft/reviewed producidos por agentes | `sessions/` |
| **Knowledge graph** | Grafo procesado y consolidado | `knowledge/*.yaml` |
| **WAL** | Write-ahead log JSONL durante sesión activa | `sessions/_WM_Code_*.jsonl` |
| **Convención WAL** | Spec de la convención anti-sesgo de recencia | `C:/Users/ajmon/env/Scripts/docs_inducop/organizacion/.wm/CONVENCION_WM.md` |

## Flujo de datos

```
┌──────────────┐      1. Genera YAML draft       ┌──────────────┐
│ Agente       │ ──────────────────────────────► │ sessions/    │
│ (CodeI/CodeCS │      status: draft              │  *.yaml      │
│  /Cowork)    │                                 └──────┬───────┘
└──────────────┘                                        │
                                                        │ 2. Guardian revisa
                                                        │    status: reviewed
                                                        ▼
┌──────────────┐      4. MCP sirve queries      ┌──────────────┐
│ MCP Server   │ ◄──────────────────────────── │ knowledge/   │
│ (cs_* tools) │      cs_get_*, cs_search_*    │  *.yaml      │
└──────┬───────┘                                └──────┬───────┘
       │                                               ▲
       │ 5. Agentes consumen grafo                     │ 3. Guardian procesa
       ▼                                               │    YAML → knowledge
┌──────────────┐                                       │
│ Agentes      │ ──────────────────────────────────────┘
│ (todos)      │      (ciclo)
└──────────────┘
```

**Observación meta:** CodeCS es agente *Y* mantenedor. Produce YAMLs (como cualquier agente) Y desarrolla el MCP que los procesará. Ver sección "Fallback del MCP" en SKILL.md.

## Fuente de verdad dual

Hay dos representaciones del conocimiento:

1. **MCP (viva, con embeddings):** búsqueda semántica, weights, alertas inmunológicas. Requiere que el server esté arriba.
2. **Raw YAML (en disco):** fuente canónica. Siempre disponible aunque el MCP esté caído.

**Implicación para CodeCS:** si estás desarrollando el MCP y lo rompes, NO pierdes el grafo — pierdes el índice. Usa `grep`/`cat` sobre `knowledge/` como fallback.

## Dominios del grafo

Los dominios son etiquetas que permiten filtrar conceptos. Algunos son proyecto-específicos, otros transversales.

**Transversales (usar en CodeCS):**
- `architecture_decisions` — decisiones de diseño que atraviesan proyectos
- `workflow_protocols` — colaboración Guardian-Code, sesiones, hooks
- `validation_patterns` — patrones de integridad, Patrón A+C

**Específicos de Concept-Sediment (usar en CodeCS):**
- `mcp_architecture` — FastMCP, endpoints, tools
- `yaml_schemas` — estructura YAML, validaciones, migraciones
- `graph_operations` — weights, relaciones, fracturas, vacunas
- `sediment_protocols` — WAL, anti-sobrescritura, failure modes

**Específicos de INDUCOP (NO usar en CodeCS):**
- `django_patterns`, `frontend`, `devops`, `email_system`, `api_design`, `ux_patterns`, `ai_integration`

## Relaciones (11 tipos activos desde 2026-04-10)

> **Para cuantitativos (weight, decay, dormant) y umbrales operativos** — ver [sistema-weight-decay.md](sistema-weight-decay.md).

| Relación | Semántica |
|----------|-----------|
| `depends_on` | A depende de B (eliminar B invalida A) |
| `derived_from` | A es consecuencia lógica de B |
| `contradicts` | A y B son mutuamente excluyentes |
| `refines` | A mejora B sin invalidarlo |
| `resolves` | A soluciona problema B |
| `instance_of` | A es caso específico del patrón B |
| `co_occurs` | A y B emergen juntos recurrentemente |
| `tensions_with` | A y B están en tensión/trade-off |
| `enables` | A habilita B, pero B puede existir sin A |
| `requires` | B es precondición temporal de A |
| `supersedes` | A reemplaza/depreca B completamente |

## Alertas inmunológicas

El sistema detecta dos tipos de señales predictivas de fallo:

- **🟡 Fracturas:** conceptos debilitados con dependientes activos. Weight bajo + muchos `depends_on` entrantes = riesgo.
- **🔴 Vacunas faltantes:** directivas críticas conocidas que NO tienen representación en el grafo. Gap detectable.

**Consumir alertas al inicio de sesión:** `cs_get_alerts(project="concept-sediment")`.

## Convención WAL (anti-sesgo de recencia)

**Problema resuelto:** sesiones largas sobrerrepresentaban temas recientes y subrepresentaban temas tempranos al cierre.

**Solución:** checkpoints incrementales en `_WM_Code_*.jsonl` durante la sesión. Al cierre, generar YAMLs de checkpoints con `consumed: false`.

**Specificación completa:** ver `CONVENCION_WM.md` en la ruta del Guardian (arriba en la tabla).

## Campo `layers` (opcional, granularidad bajo demanda)

Documenta conceptos con capas heterogéneas que decaen a ritmos distintos:

```yaml
layers:
  contingent: "procedimiento de recuperación offline si pipeline falla"
  operational: "process_session.sh orquesta 4 pasos"
  generative: "transferibilidad entre agentes"
```

**Reglas:**
- Solo usar cuando una fractura revela que un concepto no es atómico
- NO usar por default, NO preventivamente
- Se almacena en `raw_metadata` sin validación ni migración
- Cuando queramos queryar por capas, la información ya estará

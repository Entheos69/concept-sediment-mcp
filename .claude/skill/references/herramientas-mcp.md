# Herramientas MCP de Concept-Sediment

Las 6 herramientas `cs_*` expuestas por el MCP server. Para CodeCS, cada una tiene **dos caras**: cómo se consume (queries durante sesión) y cómo está implementada (lógica del server).

---

## cs_get_session_context

**Uso durante sesión (consumo):**
```
cs_get_session_context(
    project="concept-sediment",
    domains=["mcp_architecture", "sediment_protocols"],
    format="markdown",
    limit=20
)
```

Retorna contexto filtrado por proyecto + dominios. Formato markdown es más legible para el agente; JSON para procesamiento programático.

**Cuándo usarlo:** al inicio de cada sesión. Es el primer `cs_*` call del protocolo de apertura.

**Parámetros:**
- `project` (requerido) — string, identifica el proyecto
- `domains[]` (opcional) — filtro por dominios; si se omite, retorna de todos
- `format` — `"markdown"` | `"json"` (default: markdown)
- `limit` — número máximo de conceptos (default varía por implementación)

**Perspectiva de desarrollo (qué revisar si falla):**
- Lógica de filtrado por proyecto en el server
- Formato de salida (templates markdown)
- Integración con el índice de embeddings
- Manejo de `limit` — truncamiento vs ranking

---

## cs_get_alerts

**Uso durante sesión:**
```
cs_get_alerts(project="concept-sediment")
```

Retorna dos tipos de alertas inmunológicas:
- **Fracturas:** conceptos debilitados con dependientes activos
- **Vacunas faltantes:** directivas conocidas sin representación en el grafo

**Cuándo usarlo:** segundo call del protocolo de apertura, después de `cs_get_session_context`.

**Interpretación:**
- 🟢 Sin alertas — sistema estable, proceder normal
- 🟡 Fracturas — INFORMAR al Guardian con nombre, weight, dependientes en riesgo
- 🔴 Vacunas faltantes — INVESTIGAR por qué no está documentado, si se violó recientemente

**Perspectiva de desarrollo:**
- Algoritmo de detección de fracturas (threshold de weight, conteo de dependientes)
- Detección de vacunas faltantes (cómo se define "conocida pero no representada")
- Umbral de sensibilidad — si alertas espurias, ajustar aquí

---

## cs_search_concepts

**Uso durante sesión:**
```
cs_search_concepts(
    query="WAL anti-sesgo recencia",
    domain="sediment_protocols",
    project="concept-sediment",
    limit=10
)
```

Búsqueda semántica vía embeddings, con **fallback a ILIKE** si embeddings no disponibles o no matchean bien.

**Cuándo usarlo:** durante la sesión, para verificar si un concepto ya existe antes de crearlo nuevo, o para recuperar discusiones relacionadas.

**Perspectiva de desarrollo:**
- Modelo de embeddings usado (y cómo actualizarlo)
- Umbral de similitud semántica
- Trigger del fallback ILIKE (cuándo embeddings "fallan")
- Indexación — reindex después de procesar nuevos YAMLs

---

## cs_get_active_concepts

**Uso durante sesión:**
```
cs_get_active_concepts(
    domain="mcp_architecture",
    project="concept-sediment",
    concept_type="principle",
    limit=15
)
```

Conceptos activos agrupados por `type` (event/pattern/principle). El `type` es inferido por el sistema al procesar YAMLs.

**Cuándo usarlo:** cuando quieres ver solo principios críticos, o patrones recurrentes, o eventos específicos.

**Parámetros:**
- `concept_type` — `"event"` | `"pattern"` | `"principle"` | omitir para todos
- `limit` — cantidad por type

**Perspectiva de desarrollo:**
- Lógica de inferencia de `type` a partir de `depth` + contenido
- Definición de "activo" (últimas N sesiones? weight mínimo?)
- Agrupación en la respuesta

---

## cs_get_concept_graph

**Uso durante sesión:**
```
cs_get_concept_graph(
    concept_name="MEMORY.md no es autorización",
    depth=2
)
```

Retorna el grafo local de un concepto: relaciones salientes, entrantes, y ocurrencias recientes en sesiones.

**`depth` (1-3):** cuántos saltos explorar en el grafo. 1 = vecinos directos. 3 = vecinos de vecinos de vecinos (caro).

**Cuándo usarlo:** cuando quieres entender el contexto relacional de un concepto específico antes de tomar una decisión de diseño.

**Perspectiva de desarrollo:**
- Traversal del grafo (BFS con límite de depth)
- Ranking de ocurrencias recientes (qué cuenta como "reciente")
- Performance — depth=3 puede ser costoso, ¿hay caching?

---

## cs_get_domain_summary

**Uso durante sesión:**
```
cs_get_domain_summary(domain="sediment_protocols")
```

Resumen estadístico de un dominio: distribución de concept types, top conceptos por weight, sesiones que más contribuyeron.

**Cuándo usarlo:** cuando quieres entender el estado agregado de un dominio antes de sedimentar nuevos conceptos en él.

**Perspectiva de desarrollo:**
- Agregaciones (cuáles, y costo computacional)
- Definición de "top" (weight puro? weight*recencia?)
- Cache de summaries (invalidación al procesar YAMLs)

---

## Regla de oro del consumo

**Consultar antes de tomar decisiones que puedan repetir errores ya documentados.**

Los conceptos con mayor `weight` y más sesiones son los más consolidados — déjalos pesar. Las relaciones `depends_on`, `derived_from`, `resolves` revelan cadenas causales que explican por qué algo se hizo así.

## Consideraciones para desarrollo del MCP

Cuando modifiques el server:

1. **Probar localmente antes de deploy a Railway.** El fallback a `knowledge/*.yaml` te cubre, pero una regresión silenciosa puede pasar inadvertida.
2. **Versiones de schema del YAML de entrada y del grafo de salida deben ser compatibles.** Si agregas un campo opcional, los YAMLs viejos deben seguir procesándose.
3. **Los embeddings son costosos de recalcular.** Si cambias el modelo, planifica la migración (¿reindex incremental? ¿batch?).
4. **Los `cs_*` tools son contratos públicos.** Todos los agentes (CodeI, CodeCS, Cowork) dependen de ellos. Cambios breaking requieren coordinación.

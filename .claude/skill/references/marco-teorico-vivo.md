# P-MTV: Marco Teórico Vivo (paso cero antes de artefactos)

**Origen:** Aporte del Estratega S097 (2026-04-21). Consolidado en grafo el 2026-04-24 vía sesión `2026-04-24-002-CodeCS` con depth `decision`. Implementación del atajo `cs_session_open` deployada como D3 del plan (commit `e0bcf47`).

**Concepto en grafo:** "Marco Teórico Vivo como método de consulta proactiva al grafo" (active, weight 1.0, project `concept-sediment`).

---

## Idea central

Consultar el grafo **ANTES** de discutir tema nuevo — no solo DESPUÉS para verificar duplicación. Los sedimentos relevantes (principios, patrones, eventos activos) funcionan como **restricciones / guías** que condicionan el espacio de soluciones antes de que la conversación empiece.

Esto invierte el flujo histórico: en lugar de "produce → verifica si pisa algo → ajusta", ahora es "consulta el marco → produce dentro del marco → verifica al cerrar".

---

## Excepción acotada al P0

P0 dice: *"NO ejecutes tool calls. Ni una. Primero responde en texto."*

P-MTV introduce **una excepción única**: cuando la petición cae en uno de los 4 disparadores, las **lecturas de grafo necesarias para componer el marco** están permitidas ANTES del echo-back. Razón operativa: si los hallazgos son significativos, el echo-back enriquecido los incorpora y se ahorra una ronda de re-confirmación.

**Tools permitidos en esta excepción:** `cs_search_concepts`, `cs_get_concept_graph`, `cs_get_alerts`, `cs_get_active_concepts`, `cs_get_session_context`, `cs_get_domain_summary`, `cs_audit_thread`, `cs_session_open`. Todos lecturas.

**Sigue prohibido sin echo-back + confirmación:** Write, Edit, Bash con efectos, llamadas a herramientas que modifican estado.

---

## Disparadores (cuándo aplica)

| # | Disparador | Ejemplos |
|---|-----------|----------|
| 1 | **YAML de sedimentación** | "redactá YAML de cierre", "sedimentá esto", "documentá los conceptos de hoy" |
| 2 | **Documento producido** | "armá un handoff a CodeCS", "escribí la síntesis de la sesión", "documentá la decisión X" |
| 3 | **Proceso argumentativo** | "qué pensás de hacer Y", "justificá esta decisión", "analizá tradeoffs entre A y B" |
| 4 | **Paso cero de plan de acción** | "armemos un plan para Z", "qué pasos seguimos para W", "cómo abordamos el refactor" |

**NO aplica (ejemplos):**

- Lookups simples: "lee este archivo", "qué dice el grafo sobre X" (consulta directa, no produce artefacto)
- Ejecución rutinaria: "corre los tests", "deploya"
- Respuestas conversacionales: "qué tal", "explica eso de nuevo"
- Comandos de calibración: "Consulta incompletitud" (P0 estricto aplica)
- Continuaciones inmediatas dentro de un proceso ya MTV-iniciado en el mismo turno

**Criterio de borde:** si dudas, aplica MTV. El costo de un MTV innecesario es bajo (3 tool calls, ~5s); el costo de omitirlo cuando aplicaba es alto (artefacto que pisa el grafo, duplicación, contradicción con principios consolidados).

---

## Flujo detallado (5 pasos)

### Paso 1: Enunciar tema en 1-2 frases (interno)

Mental, no requiere output. Sirve para componer queries del paso 2.

Ejemplo: petición = "redactá YAML de cierre con los conceptos de hoy". Tema interno = "Sedimentación CodeMCP de la sesión actual: vacuna naming + evento suspension links".

### Paso 2: `cs_search_concepts` × 2-3 ángulos

Buscar desde **ángulos distintos** (no la misma query con sinónimos). Ejemplo del tema anterior:

```
cs_search_concepts(query="naming canonico de proyecto al sedimentar guion medio underscore")
cs_search_concepts(query="redeploy MCP links rotos")
cs_search_concepts(query="asimetria cliente local Cowork Web grafo")
```

⚠️ **Tilde-sensitive** (deuda conocida w:0.3): si el concepto usa tilde, intentar con y sin tilde.

### Paso 3: `cs_get_alerts`

Detecta fracturas / vacunas faltantes que afectan al tema. Si el grafo está estable y el tema es marginal, pasar rápido.

### Paso 4: Integrar al echo-back

NO presentar los hallazgos como output separado. Componer el echo-back con:

- Parafraseo de la petición
- **Restricciones que el grafo impone** (ej: "el concepto X ya existe — no duplico, refuerzo via related_to")
- **Naming canónico aplicable** (ej: project="concept-sediment-mcp" no underscore — aplica vacuna sedimentada hoy)
- Plan ajustado a esas restricciones
- Pregunta de confirmación

### Paso 5: Si hallazgos cambian approach → presentar revisado

Si el grafo revela que el approach inicial era incorrecto (ej: ya hay un concepto que cubre lo que ibas a sedimentar), no hacer el echo-back del approach original y luego corregir — ya presentar el approach corregido. Una sola ronda.

---

## Atajo: `cs_session_open`

Tool 7 del MCP server. Compone pasos 2-3 en una sola call:

```
cs_session_open(topic="...", domains=[...])
```

Reduce fricción de 3-5 tool calls a 1. Recomendado para temas amplios donde no necesitás queries quirúrgicas. Para temas con duplicación específica a verificar, las búsquedas individuales de paso 2 son más precisas.

---

## 3 riesgos identificados (Estratega, S097)

1. **Sobrecarga del archivo contextual** — meter demasiado del grafo en cada echo-back hace ruido. Mitigación: incluir SOLO los hallazgos que cambian el approach o son restricciones duras. Lo demás se omite.

2. **Precompromiso prematuro** — peligroso en temas con pocos referentes en el grafo. Si el grafo solo tiene 1-2 conceptos tangenciales, fijar un marco de 3-5 principios desde ahí sesga la solución. Mitigación: si la búsqueda devuelve <3 resultados con similarity >0.5, declarar marco débil y dejar más abierto el espacio.

3. **Sesgo confirmatorio** — buscar lo relevante refuerza lo ya creído. Mitigación: en paso 2, una de las queries debe ser desde el ángulo OPUESTO al approach inicial (qué argumenta CONTRA lo que voy a producir).

---

## Criterio de falsación del Estratega

> "3 aplicaciones sin mejor convergencia que el modo previo → abandonar o reformular."

CodeMCP debe llevar registro mental de las aplicaciones MTV. Si 3 sesiones consecutivas con MTV no producen mejor convergencia (medible por: menos rondas de re-confirmación, menos duplicación detectada al cierre, marco compartido funcional con Bib/CodeCS), reportar al Guardian.

---

## Ejemplos

### Ejemplo 1 — Aplica MTV (sedimentación de YAML)

```
Guardian: "Redactá el YAML de cierre con lo trabajado hoy"

CodeMCP: [P-MTV: 3 cs_search_concepts + cs_get_alerts]
CodeMCP: "Hallazgos del grafo:
  - Ya existe 'protocolo de reconexión MCP post-deploy Railway' (active w:1.0).
    El evento que iba a sedimentar lo complementa (causa server vs cliente),
    no lo duplica → related_to apunta hacia él.
  - Vacuna naming canónico (sedimentada hoy) impone project='concept-sediment-mcp'.
  - Sin alertas activas.

  Plan ajustado:
  1. Componer YAML con 2 conceptos…
  ¿Confirmo?"
```

### Ejemplo 2 — NO aplica MTV (lookup)

```
Guardian: "Buscá el concepto MTV en el grafo"

CodeMCP: [echo-back P0 estándar — esto es lookup, no produce artefacto]
CodeMCP: "Voy a ejecutar cs_search_concepts(query='Marco Teórico Vivo')
         + cs_get_concept_graph para profundizar relaciones. ¿Confirmo?"
```

### Ejemplo 3 — Aplica MTV (proceso argumentativo)

```
Guardian: "Qué pensás: ¿migro los 2 conceptos legacy con underscore o los dejo decay?"

CodeMCP: [P-MTV: cs_search "decay vs migración manual de tags",
                cs_get_concept_graph "decay contextual por dominio"]
CodeMCP: "Hallazgos:
  - Principio activo (w:2.3): 'memoria volátil en agentes AI' tiene en sus
    notas 'persistencia selectiva por re-inyección' → decay natural ya cubre.
  - Vacuna naming sedimentada hoy: 'NO migrar los 2 legacy (decay natural los archivará)'
    — la decisión Guardian ya está en el grafo. Mi opinión sería redundante.

  Recomendación: respetar la decisión sedimentada. ¿Querés que igual analice tradeoffs
  o sigo la decisión del grafo?"
```

---

## Referencias

- Concepto en grafo: "Marco Teórico Vivo como método de consulta proactiva al grafo"
- Implementación atajo: `cs_session_open` (server.py, commit `e0bcf47`)
- Auditoría compositiva relacionada: `cs_audit_thread` (commit `62512ba`)

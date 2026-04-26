# MTV — Guía de Propagación entre Skills

**Producido por:** CodeMCP, sesión 2026-04-25
**Audiencia:** Guardian (decisor) + Code-* y agentes que adopten MTV
**Concepto raíz en grafo:** "Marco Teórico Vivo como método de consulta proactiva al grafo" (active, w:1.0)

---

## 0. Por qué este doc existe

MTV no es un protocolo abstracto que se anuncia y se aplica. Es una **técnica de calibración** que requiere instalación deliberada en cada skill consumidor del grafo, con disparadores adaptados al dominio del agente. Este doc empaqueta la técnica para que el Guardian (o el agente mismo) la propague sin perder fidelidad.

**El doc resuelve 7 restricciones que el grafo impone:**

| # | Restricción del grafo | Decisión de diseño |
|---|----------------------|--------------------|
| R1 | Propagación de protocolos transversales = copia textual, no abstracción central (concepto active w:1.0) | Sección 2 entrega bloque pegable, no link a "skill base" |
| R2 | Lectura ≠ ejecución — gap real (concepto w:1.0, S86) | Sección 5 da triggers verificables del Guardian |
| R3 | Drift solo se detecta al cargar en entorno real (concepto w:0.7) | Sección 4 fuerza adaptación de disparadores por agente |
| R4 | SKILL.md corto + references/ bajo demanda (concepto w:0.7) | 2 bloques separados (SKILL + references) |
| R5 | Memoria volátil = principio consolidado w:2.3 — solo sobrevive lo re-inyectable | Bloque SKILL es ~50 líneas, denso, citable |
| R6 | Estabilidad ≠ eficacia (concepto w:1.0) | Sección 7 incluye criterio de falsación, no solo adopción |
| R7 | Anti-fractura declarativa: declarar uso en SKILL ≠ usar en grafo (concepto active w:1.0) | Sección 7 obliga reporte al grafo de aplicaciones |

---

## 1. Síntesis de MTV (3 párrafos)

**Qué es.** Marco Teórico Vivo: consultar el grafo ANTES de producir un artefacto, no solo DESPUÉS para verificar duplicación. Los sedimentos relevantes funcionan como restricciones que condicionan el espacio de soluciones antes de que la conversación empiece.

**Cuándo aplica (4 disparadores).** Antes de generar (1) un YAML de sedimentación, (2) un documento producido, (3) un proceso argumentativo, (4) el paso cero de un plan de acción. NO aplica a lookups simples, ejecución rutinaria, ni respuestas conversacionales.

**Cómo se relaciona con P0.** MTV introduce una excepción acotada al P0 ("NO ejecutes tool calls antes del echo-back"): cuando dispara, las lecturas de grafo necesarias son permitidas ANTES del echo-back, y los hallazgos se integran al echo-back enriquecido. Razón operativa: si los hallazgos cambian el approach, ahorra una ronda de re-confirmación.

---

## 2. Bloque pegable A — SKILL.md (~50 líneas)

> **Instrucción al adoptar:** copiar este bloque debajo de la sección P0 del SKILL.md del agente. Adaptar SOLO la sección "Disparadores" según el dominio del agente (ver Sección 4 del presente doc). NO modificar el flujo de 5 pasos ni la lista de tools permitidos sin consulta al Guardian.

```markdown
## P-MTV: Marco Teórico Vivo (paso cero antes de artefactos)

**Disparadores (4) — aplicar P-MTV ANTES del echo-back cuando la petición implica:**

1. Generar un **YAML** de sedimentación
2. Producir un **documento** (handoff, síntesis, decisión)
3. Iniciar un **proceso argumentativo** (análisis, justificación, recomendación)
4. Proponer el **paso cero de un plan de acción**

**Flujo (5 pasos):**

1. Enunciar el tema en 1-2 frases (interno, no requiere output)
2. `cs_search_concepts` con 2-3 queries desde ángulos distintos
3. `cs_get_alerts` del proyecto correspondiente
4. **Integrar hallazgos al echo-back** (parafraseo + restricciones que el grafo impone + plan ajustado)
5. Si los hallazgos cambian el approach, presentar el approach revisado en el mismo echo-back — ahorra una ronda

**Atajo:** `cs_session_open(topic, domains)` compone pasos 2-3 en una sola call.

**Tools permitidos en la excepción al P0:** cs_search_concepts, cs_get_concept_graph, cs_get_alerts, cs_get_active_concepts, cs_get_session_context, cs_get_domain_summary, cs_audit_thread, cs_session_open. Todos lecturas. Cualquier otro tool sigue prohibido sin echo-back + confirmación.

**NO aplica** a: lookups simples, Read de archivo, ejecución de tests, respuestas conversacionales, comandos de calibración como "Consulta incompletitud".

**Reporte obligatorio al grafo:** cada aplicación MTV debe quedar en el WAL como checkpoint con flag `mtv_applied: true`. Esto previene fractura declarativa (declarar uso ≠ uso real).

**Origen:** consolidado 2026-04-24. Aporte Estratega S097 del 2026-04-21.

**Detalle + criterio "amerita / no amerita" + 3 riesgos + criterio de falsación:** ver [references/marco-teorico-vivo.md](references/marco-teorico-vivo.md).
```

**Además, modificar la sección P0 existente del SKILL agregando triaje:**

```markdown
Al recibir cualquier instrucción del Guardian:

1. **Triaje MTV:** ¿la petición cae en disparador? (YAML / documento / proceso argumentativo / plan de acción)
   - **SÍ** → ejecutar **P-MTV primero** (lecturas de grafo permitidas), luego echo-back ENRIQUECIDO con hallazgos.
   - **NO** → echo-back ESTÁNDAR sin tool calls.
2. **NO ejecutes tool calls fuera de los permitidos por P-MTV.** Ni una.
3. ... [resto del P0 existente]
```

**Y agregar a Reglas Críticas:**

```markdown
N. **MTV antes de artefactos** — YAML/documento/argumentación/plan: ejecutar P-MTV antes del echo-back y enriquecer con hallazgos
```

---

## 3. Bloque pegable B — references/marco-teorico-vivo.md

Existe template completo en `concept-sediment-mcp/.claude/skill/references/marco-teorico-vivo.md` (~190 líneas). **Copiar tal cual al `references/` del skill destino.** El doc es agent-agnostic salvo:

- Línea de origen ("Aporte Estratega S097...") — mantener.
- Sección "Tools permitidos" — universal para agentes con MCP CS.
- Ejemplos — adaptar al dominio del agente (ver Sección 4).

**Anti-patrón al copiar:** si el agente NO consume el grafo (ej: skill puramente local sin MCP), MTV no aplica. NO pegar bloques sin verificar que `cs_*` tools están disponibles.

---

## 4. Matriz de disparadores por agente

Adaptación obligatoria por dominio (R3 — anti-drift):

| Agente | Dominio | Disparador #1 (YAML) | Disparador #2 (doc) | Disparador #3 (argumentativo) | Disparador #4 (plan) |
|--------|---------|---------------------|---------------------|------------------------------|---------------------|
| **CodeMCP** | MCP server, schemas, grafo | YAML CodeMCP de cierre | Handoff a CodeCS, README, refactor docs | Decisiones sobre tool nuevo, refactor del schema | Plan de feature MCP, plan de migración |
| **CodeCS** | Cerebro del grafo, semántica, sedimentación | YAML CodeCS de cierre | Síntesis CodeCS, handoff a Estratega | Decisión de consolidar concepto, fractura→reparación | Plan de cierre multi-sesión, Plan de curación |
| **CodeI** | INDUCOP / Django | NO genera YAMLs (no consume grafo directamente la mayoría de sesiones) — **disparador débil**, opcional | Documentación de feature, ADR | Decisión arquitectónica Django, refactor de modelo | Plan de feature, plan de migración Django |
| **Cowork** | Coordinación humana, customer intel | YAML Cowork de cierre | Handoff a Code, síntesis Nora/Alex | Recomendación al Guardian sobre prioridad, decisión cliente | Plan de outreach, plan de campaña |
| **Bib** | Bibliotecaria, validación | YAML Bib de cierre | Reporte de validación, handoff a Code | Decisión de aceptar/rechazar concepto | Plan de revisión, plan de curación de batch |

**Notas por agente:**

- **CodeI:** dominio principal NO está en el grafo concept-sediment, por lo que MTV se aplica sobre `project="inducop"`. Disparadores se evalúan: si el artefacto a producir afecta convenciones de inducop (modelo, vista, comando), MTV aplica con queries proyecto-específicas.
- **Cowork:** ya aplica "Ve por tus cuadernos" (concepto w:1.0). MTV es una instancia más estricta de ese principio para casos con grafo CS disponible. Cuando Cowork ya consultó cuadernos, no es necesario re-MTV en el mismo turno.
- **Bib:** valida YAMLs producidos por otros. MTV aquí significa: antes de declarar "este YAML es válido" (artefacto de validación), consultar el grafo para verificar que las relaciones declaradas existen y los conceptos no duplican.

---

## 5. Triggers verificables del Guardian (cierra gap lectura→ejecución)

R2 dice: leer ≠ ejecutar. Para cerrar el gap, el Guardian puede usar estas frases-tipo que el agente DEBE reconocer como disparador MTV:

| Frase Guardian | Disparador | Agente esperado |
|----------------|-----------|-----------------|
| "Sedimentá [X]" / "Cerrá la sesión" | #1 (YAML) | Cualquier Code-* |
| "Redactá / armá / documentá [X]" | #2 (doc) | Cualquier agente |
| "Qué pensás de [X]" / "Justificá [X]" / "Analizá [X]" | #3 (argumentativo) | Cualquier agente |
| "Armemos un plan para [X]" / "Cómo abordamos [X]" / "Por dónde empezamos [X]" | #4 (plan) | Cualquier agente |
| "Antes de [X], consultá el grafo" | Disparador explícito de cualquiera | Cualquier agente con MCP CS |

**Si el agente NO ejecuta MTV ante uno de estos, el Guardian debe responder: "MTV antes."** Es la frase corta de calibración que reactiva la regla.

**Si el agente ejecuta MTV cuando NO aplicaba (lookup, ejecución), el Guardian responde: "MTV no aplica acá, es lookup."** Esto entrena el discriminador.

---

## 6. Anti-patrones de propagación

Documentados aquí porque "Documentar lo que NO funcionó" es principio activo (w:1.0):

1. **Pegar el bloque sin adaptar disparadores.** Resultado: drift declarativo. CodeI con disparadores de CodeMCP intentará MTV cuando produce código Django y el grafo no tiene nada relevante → MTV vacío + frustración.

2. **Pegar a un agente sin acceso a MCP CS.** El bloque referencia tools `cs_*`. Si el agente no los tiene, las llamadas fallan y el agente se bloquea esperando. Verificar disponibilidad antes de copiar.

3. **Omitir el reporte al grafo (Sección 2 línea "Reporte obligatorio").** Sin reporte, no hay forma de medir adopción real (R7 — anti-fractura declarativa). Skill declara MTV pero grafo no registra → fractura silenciosa.

4. **Tratar MTV como protocolo universal "siempre aplicable".** Sobrecarga contextual + ruido. MTV es disparado, no continuo. La regla "NO aplica a lookups" es tan importante como la lista de disparadores.

5. **Propagar sin medir.** Si después de N aplicaciones no hay convergencia mejor que el modo previo, el Estratega ya definió: 3 aplicaciones sin mejora → reformular o abandonar. Ignorar esto crea paradoja del concepto estable pero inefectivo (concepto w:1.0).

6. **Copiar el bloque y eliminar la referencia al ejemplo "NO aplica".** El criterio de exclusión es la mitad de la utilidad del protocolo. Sin él, MTV se aplica a todo.

---

## 7. Mecanismo de eficacia (criterio de falsación + métrica de adopción)

### Criterio de falsación (Estratega S097)

> "3 aplicaciones sin mejor convergencia que el modo previo → abandonar o reformular."

**Convergencia mejor =** menos rondas de re-confirmación, menos duplicación detectada al cierre, menos contradicciones con principios consolidados, marco compartido funcional entre agentes.

**Cómo medir por agente:** cada agente lleva registro mental (no archivo) de sus últimas N aplicaciones MTV y reporta al Guardian si ve degradación.

### Métrica de adopción (anti-fractura declarativa)

Cada aplicación MTV genera evento WAL con flag `mtv_applied: true`. Al cierre de sesión, el YAML refleja:

```yaml
- name: "MTV aplicado para [tema]"
  depth: usage
  domains: [workflow_protocols]
  notes: |
    Disparador: [YAML/doc/arg/plan]
    Hallazgos significativos: [sí/no — describir si sí]
    Approach inicial vs final: [describir si cambió]
```

Esto permite al Guardian (o a CodeMCP en auditoría) ver a posteriori:

- ¿Cuántas MTV efectivas (cambiaron approach) vs cosméticas (no cambiaron nada)?
- ¿Qué agentes adoptan / qué agentes declaran sin aplicar?
- ¿Cuándo conviene retirar el protocolo de un agente que nunca lo activa?

---

## 8. Conexión con "Ve por tus cuadernos" (Cowork)

Cowork ya tiene un protocolo análogo: **"Ve por tus cuadernos como protocolo de consulta proactiva de skills"** (w:1.0, dormant). Modos: explícito (Guardian dice frase trigger) y proactivo (Cowork detecta contexto y consulta).

**Relación:** MTV es la versión específica para grafo CS de ese principio general. NO es novedoso conceptualmente — es la misma idea (consulta proactiva antes de actuar) instanciada sobre el sistema concept-sediment.

**Implicación para Cowork:** no necesita adoptar MTV como protocolo nuevo. Su "Ve por tus cuadernos" YA cubre el caso. Solo necesita:

1. Cuando el "cuaderno" relevante incluye al grafo concept-sediment, usar `cs_*` tools en lugar de cargar archivos manualmente.
2. Reconocer los 4 disparadores como casos donde "Ve por tus cuadernos" aplica con prioridad alta.

**Implicación para CodeMCP/CodeCS/CodeI:** son agentes que NO tenían un protocolo análogo formalizado. MTV llena ese hueco. Adopción explícita necesaria.

**Implicación para Bib:** validador. Su "consulta antes de validar" debería formalizarse con el mismo bloque MTV o con su variante propia. Decisión del Guardian.

---

## Resumen ejecutivo (1 párrafo)

MTV es una técnica de calibración que se propaga por copia textual del bloque de Sección 2 al SKILL.md del agente destino, con adaptación obligatoria de disparadores según Sección 4 y validación de tools MCP disponibles. La adopción se mide por eventos `mtv_applied` en el grafo, no por declaración en el SKILL. La eficacia se evalúa por criterio Estratega (3 aplicaciones sin convergencia mejor → reformular). Para Cowork, MTV no es protocolo nuevo — es instancia del "Ve por tus cuadernos" existente. Para Code-*, es adopción explícita. Para Bib, decisión pendiente del Guardian.

---

## Referencias

- Concepto raíz: "Marco Teórico Vivo como método de consulta proactiva al grafo" (active, w:1.0, project `concept-sediment`)
- Sedimentación origen: sesión `2026-04-24-002-CodeCS`
- Implementación atajo: `cs_session_open` (server.py, commit `e0bcf47`)
- Template references/ a copiar: `concept-sediment-mcp/.claude/skill/references/marco-teorico-vivo.md`
- Concepto análogo Cowork: "Ve por tus cuadernos como protocolo de consulta proactiva de skills" (w:1.0)
- Restricciones del grafo aplicadas en este doc: ver Sección 0 tabla R1-R7

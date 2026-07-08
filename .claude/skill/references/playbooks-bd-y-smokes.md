# Playbooks: Smoke tests e intervenciones BD

Procedimientos operativos canónicos para el ciclo desarrollo → deploy → validación → intervención BD del MCP server. Cada sección documenta un patrón ejecutable; las referencias entre corchetes (`[concepto: nombre]`) apuntan a sedimentos del grafo consultables via `cs_search_concepts` o `cs_get_concept_graph`.

## §0. Mirador en el ciclo epistémico (apertura y cierre obligatorios)

Antes de cualquier intervención BD o smoke test, **el ciclo no se abre ni se cierra sin Mirador**. Mirador no es dashboard pasivo: es instrumento de observación que detecta lo que motiva la intervención y verifica que la intervención resolvió la observación original.

### Anclajes conceptuales (sedimentos del grafo)

- **`[concepto: Mirador como instrumento epistemico, no dashboard]`** (active, weight 2.0) — El Mirador no cierra ciclo en lectura humana, guarda frames como observaciones reproducibles. *Si el ciclo solo termina cuando Guardian ve y archiva, no es ciclo cerrado epistémicamente.*

- **`[concepto: Convergencia por limite izquierda-derecha como ontologia del Mirador]`** (weight 1.0) — Mirador es convergencia de dos límites: por izquierda info de agentes via YAMLs (acto cognitivo), por derecha interpretación del Guardian (acto perceptual + curatorial). *Una intervención BD afecta el límite izquierdo; debe verificarse en el límite derecho via Mirador.*

- **`[concepto: Asimetría grafo / Mirador como axioma operativo]`** (weight 1.0) — Grafo emergente y sagrado (solo escritura via YAMLs sedimentados); Mirador modificable/regenerable/reiniciable (solo escritura via actos perceptuales del Guardian). *Cleanups BD son cambios en grafo → consecuencia inevitable en Mirador → debe verificarse.*

- **`[concepto: Mirador como herramienta del grafo, no de proyecto]`** (weight 1.0) — Mirador es herramienta DEL GRAFO, transversal. *No filtrar por proyecto al verificar el cierre del ciclo.*

- **`[concepto: Separacion contrato-de-datos vs consumo-visual como patron de dependencia inter-plan]`** (active, weight 1.0) — Plan productor (F47) expone contrato; plan consumidor (`PLAN_MULTISESION_MIRADOR_HORIZONTE`) lo visualiza. *`cs_get_discards` es el contrato; Mirador es el consumidor.*

- **`[concepto: Bucle fantasma->nodo cerrado por la herramienta como herradura epistemica entre proyeccion y grafo]`** (active, weight 1.0) — Mirador no es proyección pasiva: genera evidencia (audit log, draft YAMLs, patches reconciliación) para el Guardian. *Cierre del ciclo deja huella, no solo "miré y se ve bien".*

### Patrón canónico del ciclo

```
1. APERTURA — Mirador como detector
   Guardian observa en Mirador: anomalía visual, discordancia, fractura.
   La observación queda en frame del Mirador (acto perceptual, registrado).

2. CONFIGURACION DE LA INTERVENCION
   La observación se traduce en hipotesis tecnica (e.g., "axioma F47 incompleto").
   Sedimentar la observacion como concepto-evento del grafo si tiene weight epistemico.

3. EJECUCION
   Smoke test E2E (§1) → deploy → cleanup BD (§2 y §3).
   Cada paso documenta su propio audit (mcp_audit_log para writes; Git para code).

4. VERIFICACION DE CIERRE — Mirador como cierre
   Refrescar Mirador (regenerar frame post-cambio).
   Confirmar que la observacion original ya no aparece, o aparece transformada
   hacia el estado deseado.
   Si no: el ciclo NO cerro, hay residual o regression.

5. SEDIMENTACION
   YAML de cierre referencia: (a) observacion inicial Mirador, (b) sedimento
   de la decision arquitectonica, (c) commits, (d) verificacion Mirador post.
```

### Implicación operativa

- **No saltarse §0 nunca.** Sin Mirador como apertura, la intervención puede ser invención (no responde a problema real). Sin Mirador como cierre, no sabemos si resolvió el problema o creó otros.
- **Mirador no es opcional para cierre de Gates.** Gate 6 del plan F47 C2f (TCP 7 pasos) menciona reset MCP simétrico; Mirador post-reset es la prueba final.
- **Si el Mirador no está disponible** (build_conectoma_interactivo offline, frame regeneration falla), el ciclo queda abierto con flag explícito en YAML de cierre y memoria local. NO afirmar cierre.

---

## §1. Smoke test E2E del pipeline F47 (Gate 2)

Verificación end-to-end de que el pipeline `extract_concepts → graph_relationdiscard → cs_get_discards → cs_get_alerts narrative` funciona contra BD real.

### Pre-condiciones

1. Deploy ACTIVE del MCP server con cambios bajo prueba (verificable via Railway dashboard o `cs_get_alerts` que responde sin crash).
2. Migration pertinente aplicada (`graph_relationdiscard`, `graph_sessionlog.is_test`, etc.). Comprobar via `railway run python manage.py showmigrations graph`.
3. BD en estado conocido: `cs_get_discards()` previo para snapshot.

### YAML smoke como fixture

Convención de naming: `sessions/TEST-YYYY-MM-DD-<purpose>-smoke.yaml`. Campos:
- `session_id` con prefijo `TEST-` (filtrable en cleanup).
- `status: smoke_test` (validador `extract_concepts.py:248-251` lo acepta post F47-D1).
- `producer: TEST` (no-agente, distintivo).
- `domains_active`, conceptos, relaciones — con AL MENOS 1 discordancia intencional (relation type fuera de enum O target inexistente).
- Disclaimers explícitos en `session_note` ("NO ES UNA SESION REAL").

### Bypass cuando `process_session.sh` bloquea

`process_session.sh` pre-flight CHECK 2/6 actualmente solo acepta `reviewed` (deuda F47-D1.2 en backlog). Mientras esa brecha no se cierre, **bypass directo**:

```bash
cd /c/Users/ajmon/proyectos/concept-sediment
railway run python manage.py extract_concepts \
  --file sessions/TEST-<...>-smoke.yaml \
  --skip-embeddings -v 2
```

`--skip-embeddings` recomendado: el concept smoke se borrará en cleanup, no necesita embedding (~700ms ahorrado por concept).

### Criterios de éxito (per F47-D1.1)

- Output del extractor incluye `[SEMANTIC WARNING][smoke_test_dispatch]`.
- Log `Occurrence added (SMOKE, aggregates skipped)` confirma branch `is_test=True` en `add_occurrence`.
- `cs_get_discards()` retorna entry con `session_id="TEST-..."`, `is_test: true`.
- `summary.total_real` excluye al smoke.
- `cs_get_alerts()` narrative muestra línea `Productivas (excluyendo smokes): N` con N = `total - 1`.

### Criterios de falsación (3 rutas de falla)

| Síntoma | Diagnóstico |
|---|---|
| Crash con stack trace | Bug en extractor lado CodeCS — investigar `graph/management/commands/extract_concepts.py` |
| Procesa pero no crea RelationDiscard | Captura de discordancias rota — investigar `_capture_relation_discard` o lógica equivalente |
| RelationDiscard creado pero `cs_get_discards()` retorna `[]` o sin `is_test` | Integración BD-MCP rota: BDs distintas, deploy MCP no actualizado, o JOIN `graph_sessionlog` falla |
| Concept aggregates contaminados (weight≠0, projects no vacío) | F47-D1.1 no se honró — branch `is_test` en `add_occurrence` no funciona |

### Cierre Mirador (§0)

Post-smoke + cleanup, verificar via Mirador refrescado: el discard smoke NO aparece visualmente, los discards productivos pre-existentes SÍ siguen visibles.

---

## §2. Cleanup hard delete de smoke session

Remoción de todos los rastros BD de una sesión smoke usando management command dedicado.

### Management command canónico

**Path:** `concept-sediment/graph/management/commands/cleanup_smoke_session.py` (creado 2026-05-09 por CodeMCP, lado CodeCS).

**Argumentos:**
- `--session-id <sid>` (requerido) — session_id del smoke a limpiar.
- `--dry-run` — solo verifica, no elimina nada.
- `--force` — elimina aunque (a) `is_test=False` o (b) aggregates contaminados. Usar con cuidado.

### Verificación F47-D1.1 antes de borrar

El comando verifica que para concepts smoke-only (sin otras occurrences):
- `weight == 0.0` ✓ (smoke no incrementó)
- `projects == []` ✓ (smoke no contaminó)

Si falla esta verificación, el comando aborta con error a menos que se use `--force`. Esto previene borrar artefactos de bug F47-D1.1 silenciosamente — si los aggregates están contaminados, hay que investigar antes de limpiar.

### Patrón de invocación recomendado: dry-run primero

```bash
# 1. Verificar previa (sin borrar)
railway run python manage.py cleanup_smoke_session \
  --session-id TEST-<...>-smoke --dry-run

# 2. Si dry-run muestra [PASS], ejecutar real
railway run python manage.py cleanup_smoke_session \
  --session-id TEST-<...>-smoke
```

### Orden de borrado dentro de `transaction.atomic`

1. `RelationDiscard.objects.filter(session_id=sid).delete()` — aristas pending del smoke.
2. `ConceptOccurrence.objects.filter(session_id=sid).delete()` — ocurrencias en concepts.
3. Para cada concept tocado: si no hay otras ocurrencias → `concept.delete()` (huérfano), si hay → conservar.
4. `SessionLog.objects.filter(session_id=sid).delete()` — registro de la sesión.

### Cleanup filesystem del YAML

Post BD-cleanup, eliminar el archivo YAML smoke:
```bash
rm /c/Users/ajmon/proyectos/concept-sediment/sessions/TEST-<...>-smoke.yaml
```

Por convención del diseño smoke (línea 39 del propio YAML smoke).

### `repair_discards apply --resolution=reject` ≠ hard delete

`repair_discards` (lado CodeCS) hace soft-mark de RelationDiscard cambiando `resolution_status`. NO borra registros. Para smokes, el ciclo de vida correcto es hard delete (no acumular soft-marks de tests en BD productiva).

---

## §3. Patrón verify-then-clean para intervenciones BD

Aplicable a cualquier modificación destructiva de BD (no solo smokes).

### 3.1 Siempre dry-run primero

Cualquier comando destructivo debe ejecutarse PRIMERO en modo `--dry-run` (o equivalente: imprimir sin ejecutar). Output mostrar exactamente qué cambiaría. Solo si el preview coincide con expectativa, correr real.

### 3.2 `transaction.atomic` en escritura

Cualquier operación que toque múltiples tablas relacionadas: envolver en `with transaction.atomic():`. Si una falla, rollback completo. Evita estados inconsistentes (e.g., RelationDiscard borrado pero ConceptOccurrence quedó).

### 3.3 Soft-delete vs hard-delete

| Caso | Estrategia |
|---|---|
| Datos productivos con valor histórico | **Soft-delete** — `archived` status o flag `deleted_at` |
| Smokes / fixtures de tests | **Hard delete** — no acumular ruido |
| Errores de pipeline (e.g., concept duplicado por bug) | Soft-delete + audit log de rectificación |
| RelationDiscard `pending` antiguo sin reconciliación | Soft-mark via `repair_discards apply --resolution=rejected` |

### 3.4 Audit log review post-intervención

Tras cualquier write tool invocación, revisar `cs_get_audit_log` filtrando por `agent` y `since` para confirmar que las entradas registradas coinciden con la operación. Útil para diagnosticar fallos parciales.

### 3.5 Verificación Mirador como cierre (§0)

Toda intervención BD se considera cerrada SOLO cuando refrescar Mirador muestra el estado esperado. Sin Mirador, el cierre es presuntivo.

---

## §4. Validación post-deploy MCP

Tras `git push` a `concept-sediment-mcp` (o a `concept-sediment` si afecta migration consumida por MCP), Railway redeploya. Ventana ~1-2 min con `cs_*` tools mortalmente inestables. Post-redeploy:

### Gates heredados del plan F47 C2f

| Gate | Verificación |
|---|---|
| 1 | Migration aplicada (`showmigrations graph` muestra `[X]`) |
| 2 | Extractor captura discordancias (smoke E2E §1) |
| 3 | Schema MCP compatible (`cs_get_alerts` no crashea con `UndefinedTable`) |
| 4 | Tool nueva responde (`cs_get_discards` retorna estructura esperada) |
| 5 | Integración E2E (smoke discard visible via tool) |
| 6 | Protocolo TCP 7 pasos (reset MCP simétrico CodeCS↔CodeMCP) |

### Quick smoke checks post-deploy

```python
# Quick check 1: alerts responde
cs_get_alerts(project="concept-sediment-mcp")
# Esperado: "estable" o estructura de alertas (NO crash)

# Quick check 2: discards estructura nueva (post F47-D1.1)
cs_get_discards()
# Esperado: response incluye campo "is_test" por entry y "total_real" en summary
```

Si Quick check 2 NO incluye `is_test`/`total_real` → deploy MCP no aplicó cambios F47-D1.1. Investigar.

### `UndefinedTable` como señal crítica

`cs_get_alerts` o `cs_get_discards` retornando error `UndefinedTable: relation "graph_xxx" does not exist`:
- Schema mismatch: BD no tiene la tabla que el código MCP espera.
- Causa típica: deploy MCP corrió ANTES que migration Django.
- Solución: aplicar migration primero (`railway run python manage.py migrate graph` desde repo Django), luego reintentar.

### ToolSearch refresh para tools nuevas

Si el deploy agrega tool nueva (e.g., `cs_get_discards` en F47 C2e), el cliente Claude Code puede tener cache stale. Sedimento `[concepto: Refresh de tools MCP deferred via ToolSearch como excepcion al cache pasivo cliente Claude Code]` (active 2026-05-08): ejecutar `ToolSearch select:mcp__claude_ai_Concept_Sediment__cs_<tool>` para cargar schema lazy del server.

**Caveat acotado** (verificado 2026-05-09 con F47-D1.1): para tools modificadas (output expandido sin breaking change de input), ToolSearch NO es estrictamente necesario. NO generaliza a tools removidas/renombradas.

### Cierre Mirador (§0)

Refrescar el conectoma del Mirador post-deploy. Confirmar que las observaciones que motivaron el deploy YA NO aparecen, o aparecen transformadas según expectativa.

---

## §5. Caso histórico — sesión 2026-05-09 F47-D1.1 + Gate 2

Cronología compactada del ciclo completo aplicando los §0-§4 arriba. Referencias al grafo entre corchetes.

### Apertura (Mirador)

Guardian observa en el Mirador discordancias estructurales del grafo: aristas que el extractor de YAMLs descartaba silenciosamente cuando el `relation_type` no estaba en el enum canónico. Esa observación motivó el plan F47 inicial (sedimentos `[concepto: FASE C0 PLAN_F47 ejecutada]` y `[concepto: PLAN_MULTISESION_F47 v2 escrito 2026-05-05]`). C2d+C2e implementados por CodeMCP el 2026-05-07 (`[concepto: Tool cs_get_discards para consulta estructurada de discordancias F47 C2e]`).

### Trayecto

| Hito | Evento |
|---|---|
| 2026-05-09 inicio | Intento de smoke test (Gate 2) con `process_session.sh` falla — pre-flight rechaza `status: smoke_test` |
| Deliberación arquitectónica | Sub-rutas 2A (extender enum status mezclando lifecycle/categoría) vs 2B (campo nuevo `is_test` ortogonal) — Guardian autoriza 2B → F47-D1 |
| Implementación F47-D1 (CodeCS) | commit `021d636` con `SessionStatus.SMOKE_TEST` + `SessionLog.is_test` + 8 tests |
| **Brecha detectada** (CodeMCP) | Lectura de `add_occurrence` revela que weight/last_seen/projects siguen contaminándose por smokes — `_productive_occurrences` solo cubre promoción/decay |
| F47-D1.1 specced (CodeMCP) | Spec Ruta B propuesto al Guardian con dos sub-cuestiones (dónde fixear: A=queries SQL del MCP, B=modelo); Guardian autoriza B |
| Implementación F47-D1.1 (CodeCS) | Branch `is_test` en `add_occurrence` + tests adicionales (53/53 verde) |
| Implementación F47-D1.1 (CodeMCP) | commit `ed22dc0` con LEFT JOIN `graph_sessionlog` en `discard_queries.py`, narrative con `total_pending_real` en `server.py`, `test_smoke_exclusion_mcp.py` (sediment `[concepto: Filtrado is_test en queries productivas del MCP]`) |
| Smoke E2E | Ejecutado via bypass `extract_concepts` (process_session.sh sigue rechazando smoke_test — F47-D1.2 en backlog) |
| Cleanup | `cleanup_smoke_session` management command creado, dry-run + run real, BD limpia |

### 5 bugs detectados en spec original CodeMCP por CodeCS pre-implementación

Sedimento `[concepto: Spec arquitectonico con bugs detectados por revisor cruzado]`:
1. Numeración migration `0008` colisionaba con `0008_sessionlog_is_test` ya merged.
2. `dependencies` apuntaba a `0007` pero requería `0008`.
3. `last_seen_at` DateTimeField vs `session_date` DateField — sin conversión.
4. `DEPTH_WEIGHTS` hardcoded ignorando `settings.CS_WEIGHT_*` configurables.
5. N+1 query en `Concept.objects.iterator()` sin `prefetch_related`.

Patrón documentado: `[concepto: Iteracion tripartita Bibliotecario-Code-Bibliotecario verifica como protocolo de revision arquitectonica]` extendido a triada Guardian-CodeMCP-CodeCS.

### Brecha pendiente: F47-D1.2

`scripts/process_session.sh` CHECK 2/6 NO fue actualizado por F47-D1. Sigue exigiendo `status: reviewed`, rechaza `smoke_test`. Spec mínimo (~5 LOC) propuesto por CodeMCP, pendiente de transmitir a CodeCS y ejecutar en sesión separada.

### Cierre

YAMLs de cierre: `2026-05-09-001-CodeMCP.yaml` (CodeMCP) y `2026-05-09-002-CodeCS.yaml` (CodeCS, sedimento `[concepto: F47-D1 y F47-D1.1 cerrados CodeCS-side]`). Materialización del borrador `2026-05-08-001-CodeMCP.yaml` autorizada el mismo día (cond 1+2 cumplidas + autorización Guardian).

### Lección operativa principal

El axioma F47-D1 inicial cubría solo 2 superficies (promoción, decay) cuando el espacio total era ≥4 (también `add_occurrence` y queries productivas del MCP). **Detectar dependencias transversales requiere que cada agente intente aplicar el axioma a su superficie** — no basta con que el axioma esté sedimentado. F47-D1.1 fue el resultado de esa aplicación recursiva. F47-D1.2 confirmará el patrón cuando se cierre la brecha shell.

---

## §6. Índice de management commands disponibles

Comandos Django de `concept-sediment` invocables via `railway run python manage.py <comando>`.

| Comando | Path | Propósito | Owner |
|---|---|---|---|
| `extract_concepts` | `graph/management/commands/extract_concepts.py` | Procesa YAMLs de sessions/ → graph_concept + graph_relationdiscard. Args: `--file`, `--dir`, `--dry-run`, `--skip-embeddings` | CodeCS |
| `cleanup_smoke_session` | `graph/management/commands/cleanup_smoke_session.py` | Hard delete de smoke session: RelationDiscard + ConceptOccurrence + Concept huérfano + SessionLog. Args: `--session-id`, `--dry-run`, `--force` | CodeCS (creado 2026-05-09 por CodeMCP) |
| `repair_discards apply` | `graph/management/commands/repair_discards.py` (lado CodeCS) | Soft-mark RelationDiscard: `--resolution=mapped_to_alias|promoted_to_enum|rejected` | CodeCS |

### Convenciones

- **Pre-flight wrapper:** `scripts/process_session.sh` envuelve `extract_concepts` con CHECK 1-6 (status reviewed, DNS, embedding provider, idempotencia). Para fixtures que no pasen pre-flight (smokes), bypass directo (§1).
- **Audit log:** comandos write registran en `mcp_audit_log` (vía MCP write tools) o vía Django logger (vía management commands directos).
- **Coordinación CodeCS↔CodeMCP:** comandos viven en repo Django; tools MCP los reflejan o consumen via BD compartida. Cambio en uno requiere coordinación con el otro si afecta contrato BD.

---

## Actualización de este documento

Cuando se agregue / modifique playbook:

1. Si nuevo playbook tipo §1-§4 → agregar sección numerada manteniendo §0 (Mirador) y §5+ (caso histórico, índice) al final.
2. Si caso histórico amerita sub-sección en §5 → agregar como §5.N con cronología compacta + referencias al grafo entre corchetes (`[concepto: nombre]`).
3. Si management command nuevo → agregar fila en tabla §6.
4. Verificar que el ciclo Mirador (§0) sigue siendo aplicable; si la nueva intervención NO toca el grafo o no es perceptible en Mirador, declararlo explícitamente.

Convención de referencias al grafo: `[concepto: nombre exacto]` para que `cs_search_concepts` lo encuentre por substring. Incluir `(active|dormant, weight X)` cuando ayude a juzgar autoridad del sedimento.

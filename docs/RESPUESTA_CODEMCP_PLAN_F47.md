# RESPUESTA_CODEMCP — Iteracion sobre PLAN_MULTISESION_F47

```
producer:    CodeMCP
fecha:       2026-05-05
project:     concept-sediment-mcp
status:      iteracion sobre draft (no instruye ejecucion)
target:      concept-sediment/docs/PLAN_MULTISESION_F47_relaciones_no_descarte.md
predecesor:  analisis preliminar Bibliotecario (5 observaciones, 2026-05-05)
metodo:      P-MTV (Marco Teorico Vivo) + revision dirigida desde
             jurisdiccion CodeMCP (deploy, BD compartida, tools MCP,
             contrato Mirador<->grafo)
```

> **Naturaleza.** Este documento responde a (a) las 5 observaciones del
> Bibliotecario sobre el plan F47 y (b) aporta mejoras CodeMCP-especificas
> que no estaban en el analisis preliminar. NO modifica el plan; aporta
> insumos para la siguiente iteracion. Las decisiones materiales siguen
> siendo del Guardian (D2).

---

## §0 — Metodo aplicado

Antes de redactar, ejecute P-MTV con 4 angulos de busqueda sobre el
grafo (sin filtro `project`, axioma cross-project del plan §2):

1. silent discard / discordancia schema YAML / relation_type
2. depth / domain / status (otros canales potenciales)
3. reconciliacion-grafia / promocion-genuina / alias / reproceso
4. Mirador / conectoma / fantasma / ortogonalidad

Hallazgos relevantes que **cambian o refuerzan** el analisis y se
referencian en linea abajo. Lista completa al final (§5).

---

## §1 — Respuesta a las 5 observaciones del Bibliotecario

### 1.1 — D6 abierto sin desarrollo (otros canales silent-discard)

**Observacion del Bibliotecario:** depth invalido, domain no registrado,
status no canonico, type invalido pueden ser canales adicionales. Si la
respuesta es "si hay otros canales", la arquitectura tres-capas deberia
declararse como **patron portable**.

**Postura CodeMCP: SI hay otros canales. El grafo lo confirma.**

Sedimentos relevantes:

- `validacion depth values como barrera procedural en protocolo YAML`
  (w=1.0, dormant) — documenta el error comun `depth: pattern` (donde
  `pattern` es TYPE no DEPTH). Hay barrera procedural, NO estructural.
- `YAML no procesado como causa de ausencia de dominio en grafo`
  (w=0.7, dormant) — caso real: dominio declarado en YAML que no
  existia en el registro formal hasta procesarse el YAML.
- `dominio graph_operations ausente del registro formal` (w=0.3,
  dormant) — caso especifico documentado del 2026-04-22.

Esto es prueba de que el patron de discordancia silent-discard NO se
agota en `relation_type`. Hay al menos un canal mas con evidencia
documentada (`depth`). `domain` y `status` requieren auditoria, pero
existen sedimentos parciales.

**Recomendacion concreta:**

1. **Declarar la arquitectura tres-capas como patron portable AHORA**
   en §9.3 del plan, con desarrollo explicito (no solo insinuacion).
   El sedimento candidato §9.3 ya dice "generalizable a otros campos
   del schema (ej. `depth` invalido, `domain` no registrado)". Hacer
   ese desarrollo ahora cierra la salida arquitectonica.

2. **Agregar subfase C0d** al plan: script 1-shot
   `scripts/audit_other_silent_discards.py` que cuente violaciones
   de `depth`, `domain`, `status`, `type` en el corpus YAML
   procesado vs no procesado. Salida JSON.

3. **Criterio de bifurcacion C0d:** si conteo ≥10 en cualquier campo,
   se abre **F47-D heredera** con la misma arquitectura tres-capas
   instanciada para ese campo. Si conteo <10, queda como deuda
   documentada en `RESPUESTA_CODEMCP_DEUDAS_F47.md` (este repo).

**Razon de no dejarlo abierto sin desarrollo:** sedimento
`extension de RelationType 6 a 11 tipos en Concept Sediment` (w=3.0)
prueba que **el patron de descubrir-tipos-faltantes-tarde ya ocurrio**.
La arquitectura tres-capas es respuesta de diseno; si no se declara
portable ahora, en 6 meses la reinventaremos para `depth`.

---

### 1.2 — Performance de cascada extendida

**Observacion del Bibliotecario:** cada arista hace 2 queries
adicionales (RelationAlias.get + RelationDiscard.create en peor caso).
Para sesiones grandes (50+ aristas) suma. Mitigacion trivial: cache
dict al inicio del run.

**Postura CodeMCP: confirmo. Mitigacion correcta y barata.**

**Recomendacion concreta:**

Agregar a §5 Capa 2 (RelationAlias) una nota de implementacion
explicita:

```python
# En el inicio del run de extract_concepts.handle()
# (antes del loop sobre conceptos)
self._alias_map = dict(
    RelationAlias.objects.values_list(
        "alias", "canonical_type", "invert_direction"
    )
)
# El extractor consulta self._alias_map.get(rel_type_str) en hot path,
# evitando query por arista.
```

**Costo:** una query al inicio del run, ~unos KB de memoria por
hash dict.
**Beneficio:** lookup O(1) en lugar de O(query) por arista. En sesion
de 50 aristas con 30% miss-rate sobre RELATION_MAP, ahorra ~15
queries. En reproceso historico (FASE C3) sobre 16 sesiones, ahorra
~40 queries (uno por arista perdida).

**No requiere cambio de schema.** Es decision de implementacion, no
de diseno. Documentar en §5 evita olvido.

**Bonus relacionado:** si se decide promover `RELATED` (D-C1-1), el
detector de sobre-uso por agente (mitigacion §4 cat D) tambien debe
cachear sus conteos por sesion en lugar de aggregate query por arista.
Mismo principio.

---

### 1.3 — Trazabilidad de aristas creadas via reproceso (C3)

**Observacion del Bibliotecario:** el plan dice "flag o notes" sin
especificar. Recomienda campo `created_via_reprocess_session_id`
nullable o prefijo grep-able `[REPROCESS:<discard_id>]` en notes.

**Postura CodeMCP: campo dedicado, pero diferente al propuesto.**

**Argumento contra prefijo en `notes`:**

- `notes` es texto libre potencialmente modificable por agentes.
- Grep-able es solo legible, no queryable en SQL eficiente.
- Si el formato del prefijo cambia, queries historicas se rompen.

**Argumento contra campo `created_via_reprocess_session_id`:**

- Modela trazabilidad como CharField libre, no como FK.
- No aprovecha que ya existe el modelo `RelationDiscard` con FK
  inversa al ConceptRelation que lo resolvio
  (`RelationDiscard.resolved_relation`, declarada en §5 del plan).

**Recomendacion concreta:**

Aprovechar la simetria que **ya esta declarada** en el plan §5:

```python
class RelationDiscard(models.Model):
    # ...
    resolved_relation = models.ForeignKey(
        "ConceptRelation", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="discard_origin",  # <-- AGREGAR ESTE related_name
        help_text="Si resolution_status crea arista real, FK a la "
                  "ConceptRelation resultante."
    )
```

Con `related_name="discard_origin"`, cualquier `ConceptRelation`
tiene acceso reverso:

```python
# Aristas creadas via reproceso (no directas):
ConceptRelation.objects.filter(discard_origin__isnull=False)

# Para una arista especifica:
relation.discard_origin  # None si fue creada directa, Discard si via reproceso
relation.discard_origin.session_id  # session original
relation.discard_origin.relation_type_raw  # tipo invalido original
```

**Beneficios:**

- Cero campos nuevos.
- Schema-explicito y queryable.
- Ya hay metadata rica en RelationDiscard (session_id, raw type,
  reason, resolved_by, resolved_at).
- Bidireccional natural.

**Para el caso de revertir aristas via reproceso si Guardian decide
que un alias mapping fue incorrecto** (riesgo §8.3 del plan), basta
con:

```python
ConceptRelation.objects.filter(
    discard_origin__resolution_status="mapped_to_alias",
    discard_origin__relation_type_raw="extends",  # tipo invalido sospechoso
).delete()
```

Sin grep, sin arqueologia.

---

### 1.4 — Ortogonalidad con PLAN_MULTISESION_MIRADOR_HORIZONTE

**Observacion del Bibliotecario:** el plan declara ortogonalidad pero
no explica el contrato. ¿El Mirador conectoma necesita leer
RelationDiscard para visualizar aristas pending? ¿O esta desacoplado?

**Postura CodeMCP: el contrato es claro a la luz de sedimentos
activos. NO esta desacoplado. El Mirador DEBE proyectar Discards.**

Sedimentos clave (active, w=1.0):

- `Asimetria grafo / Mirador como axioma operativo` — el grafo es
  emergente/sagrado (escrito solo por actos cognitivos de agentes
  via YAMLs), el Mirador es modificable/regenerable (escrito por
  actos curatoriales del Guardian).
- `Bucle fantasma->nodo cerrado por la herramienta como herradura
  epistemica entre proyeccion y grafo` — el Mirador genera evidencia
  para el Guardian sobre fantasmas, conservando D2.

**Aplicacion al caso F47:**

`RelationDiscard` NO es ni acto cognitivo de agente (no es YAML
producido), ni interpretacion curatorial Guardian. Es **captura
estructurada de discordancia**, capa intermedia. Por la asimetria, la
ubicacion correcta es:

| Capa | Naturaleza | Quien escribe | Que ve el Mirador |
|------|------------|----------------|-------------------|
| Grafo emergente (Concept, ConceptRelation) | sagrado | Agentes via YAML | si (canonico) |
| **Discard pending** | captura intermedia | Extractor automatico | **si (capa nueva, styling distinto)** |
| Discard resolved | reconciliado | Guardian via repair_discards | si (como arista canonica) |
| Mirador conectoma overlays | curatorial | Guardian | si (su capa) |

**Recomendacion concreta:**

Agregar a §7 del plan una **subseccion explicita "Mirador conectoma"**
con el siguiente contrato:

> El Mirador (PLAN_MULTISESION_MIRADOR_HORIZONTE) lee
> `RelationDiscard.objects.filter(resolution_status='pending')` y los
> proyecta como aristas con styling distinto (gris dashed) hacia
> targets si target_name_raw matchea via slug fallback, o como nodos
> rombo si reason=target_not_found. Conserva D2 (no decide; solo
> proyecta para que el Guardian tenga evidencia visual).

Esto cierra la herradura epistemica via tres rutas paralelas:

1. ALERTAS_HUMANDATO.md (texto, asincrono)
2. `cs_get_alerts` (MCP, programatico)
3. Mirador (visual, espacial)

Sin esta tercera ruta, el Mirador puede mostrar fantasmas resueltos
post-C3 sin que el Guardian sepa que su origen fue un Discard
pending — la arqueologia se romperia.

**Implicacion adicional:** §10 del plan deberia agregar **D7**:
"¿El Mirador integra Discards pending como capa visual en este plan,
o se difiere a una sesion del plan MIRADOR_HORIZONTE?". Decision
Guardian.

---

### 1.5 — `repair_discards --auto` viola D2

**Observacion del Bibliotecario:** `--auto` en C3b ("aplica resolucion
para aquellos con alias claro") sugiere intervencion automatica. Aunque
es ejecutado por humano via comando, el flag `--auto` deberia
renombrarse a `--apply-seeded-aliases` con logging muy explicito.

**Postura CodeMCP: confirmo. Sedimento del grafo refuerza la objecion.**

Sedimento clave (active, w=1.0):

- `Rectificacion manual de type a principle por decision de diseño
  codificada en codigo como axioma de gobernanza distinto a promocion
  automatica por uso` — distingue explicitamente "decision Guardian
  manual" vs "promocion automatica por uso". El nombre `--auto` cae
  retoricamente del lado equivocado.

**Recomendacion concreta:**

```
Renombre:           --auto  ->  --apply-seeded-aliases

Flag adicional:     --dry-run (obligatorio en primera ejecucion)

Audit log prefijo:  relation_discard_seeded_apply
                    (consistente con prefijos de §2 del plan)

Output mandatory:   Por cada Discard procesado, emitir linea:
  [audit] seeded_apply: discard_id=<id>
          session=<original> alias=<raw>
          canonical=<resolved> flip=<bool>
          ALIAS_RATIONALE: <RelationAlias.rationale truncated 80 chars>
```

**Por que `--dry-run` obligatorio:**

D2 exige autorizacion explicita por caso. La aprobacion del seed
inicial (FASE C1) cubre la decision sobre el mapping; `--dry-run`
fuerza al Guardian a inspeccionar la **aplicacion concreta** antes
de comprometerla. Si C3b procesa 19 aristas (cat D `related_to`)
sin que el Guardian las vea individualmente, hay riesgo de batch
silent-mistake.

**Resultado: `--dry-run` produce reporte de las N aristas que se
crearian, con rationale del alias por cada una. Solo tras revision
visual, el Guardian autoriza `--apply-seeded-aliases` (sin --dry-run).**

Esto NO es burocracia: el riesgo §8.3 del plan ("alias mapping
incorrecto retroactivo") se materializa exactamente en C3b. La
ceremonia es proporcional al blast radius.

---

## §2 — Mejoras adicionales CodeMCP-especificas

Estas no estaban en el analisis preliminar del Bibliotecario; son
aportes desde la jurisdiccion CodeMCP (deploy, BD compartida, tools
MCP, vacuna pre-deploy).

### A — Reset MCP post-deploy con orden simetrico explicito

**Problema.** §6 C2g del plan dice "Reset MCP de ambas sesiones.
Verificacion post-deploy" sin especificar el orden.

**Sedimento aplicable:** `Precaucion pre-deploy MCP` (w=2.0). Por
simetria con la vacuna ya sedimentada, el orden DEBE ser explicito:

```
ORDEN POST-DEPLOY (C2g):
  1. Verificacion: railway logs --tail (que el server arranque ok)
  2. Verificacion: prueba SQL directa contra PG nuevo schema
     (\d relation_alias, \d relation_discard)
  3. Reset MCP de sesion CodeCS (cierra antes de reabrir)
  4. Reset MCP de sesion CodeMCP
  5. cs_get_alerts(project="concept-sediment-mcp") debe funcionar
  6. cs_search_concepts contra nuevos modelos no debe romper
  7. Si algo falla, rollback: railway redeploy commit anterior
```

**Recomendacion:** documentar este orden en §6 C2g como subfase
adicional o nota.

### B — UUIDs en RelationAlias y RelationDiscard

**Problema.** Regla critica 13 del skill CodeMCP: UUIDs en Python
(`uuid.uuid4()`), no SQL. Las extensiones `gen_random_uuid()` /
`uuid_generate_v4()` pueden no estar disponibles en Postgres
compartido (dependen de pgcrypto / uuid-ossp).

**Inspeccion del modelo propuesto en §5:** los modelos `RelationAlias`
y `RelationDiscard` no especifican `id` explicito. Django default es
`AutoField` (BigInt autoincremental), que es valido y no tiene este
problema.

**Recomendacion:** verificar al implementar (FASE C2a) que los modelos
NO declaran `id = models.UUIDField(default=...)` con default SQL. Si
en algun momento se decide migrar a UUID (consistencia con resto del
schema MCP), generar via `uuid.uuid4()` en el constructor del modelo
o como `default=uuid.uuid4` en la declaracion (Python callable, no
SQL function).

**Costo:** verificacion 5 minutos en code review.

### C — `cs_get_alerts` integra Discards (cierre de herradura via MCP)

**Problema.** §5 menciona "Detector Humandato — alerta nueva" pero la
salida es `ALERTAS_HUMANDATO.md`. No hay integracion explicita con la
tool MCP `cs_get_alerts` que ya consumen los agentes.

**Recomendacion concreta:**

Extender el output de `cs_get_alerts` con seccion nueva:

```
## Aristas pending (RelationDiscard)
- Total pending: N
- Por reason:
  - unknown_type: M
  - target_not_found: K
- Top 3 tipos invalidos sin alias:
  1. <tipo> (<count> ocurrencias)
  2. ...
- Mas antiguo: <fecha> (alerta si >7 dias)
```

**Beneficio:** los agentes que ejecutan protocolo de carga al inicio
de sesion (paso `cs_get_alerts`) ven los Discards pending sin tener
que abrir Django shell. Cierra la herradura via la ruta que ya usan.

**Implementacion:** modificar `humandato_queries.py` (CodeMCP-jurisdiccion).
Agregar query a `RelationDiscard` con agregaciones simples. <30 LOC.

### D — Tool MCP nuevo `cs_get_discards`

**Problema.** §7 del plan pregunta "¿requieren tools MCP nuevas?".
Mi respuesta: SI, una.

**Diseno propuesto:**

```python
@mcp_tool
def cs_get_discards(
    reason: Optional[str] = None,         # filtro por Reason enum
    status: Optional[str] = None,         # default: "pending"
    project: Optional[str] = None,        # filtro por session_id prefix
    limit: int = 50,
) -> dict:
    """Lista RelationDiscard con filtros. Por default: pending.

    Util para Bibliotecario, Mirador, agentes que necesiten
    inspeccionar discordancias estructuradamente sin Django shell.
    """
```

**Por que tool dedicada y no extender una existente:**

- Discards son entidad distinta (no son Concept ni ConceptRelation).
- Tienen ciclo de vida propio (resolution_status).
- Audit log + repair son consumidores especificos.

**Decision alfa/beta/gamma para C2:**

| Modo | Decision |
|------|----------|
| alfa | Implementar `cs_get_discards` como parte de C2 |
| beta | Diferir a fase posterior (los agentes consultan via SQL inicialmente) |

**Recomendacion CodeMCP: alfa.** El costo es bajo (similar a
`cs_get_alerts` existente, ~50 LOC) y cierra el contrato MCP-Mirador
de forma explicita. Diferirlo crea presion de "abrir Django shell"
que viola la API estable del MCP.

### E — Seed `relation_alias_seed.yaml` append-only con `revoked_at`

**Problema.** §6 C1c menciona generar `docs/relation_alias_seed.yaml`
como tabla autoritativa post-decision Guardian. Si en el futuro el
Guardian revoca un alias o lo redirige a un canonico distinto, ¿como
se rastrea historicamente?

**Recomendacion concreta:**

El YAML seed es **append-only**:

```yaml
# docs/relation_alias_seed.yaml
aliases:
  - alias: extends
    canonical_type: refines
    invert_direction: false
    rationale: "..."
    approved_by: Guardian
    approved_at: 2026-05-XX
    revoked_at: null

  - alias: specializes
    canonical_type: refines
    invert_direction: false
    rationale: "Provisional, pendiente decision E"
    approved_by: Guardian
    approved_at: 2026-05-XX
    revoked_at: 2026-06-15  # revocado al promover SPECIALIZES al enum
    revocation_reason: "promoted to enum"

  - alias: specializes  # nueva entrada que reemplaza la revocada
    canonical_type: specializes
    invert_direction: false
    rationale: "Promovido a enum, alias mantiene retrocompatibilidad"
    approved_by: Guardian
    approved_at: 2026-06-15
    revoked_at: null
```

**Beneficios:**

- Audit trail completa de decisiones Guardian.
- Reverter una decision NO destruye historia.
- El seeder Django (`seed_relation_aliases` command) ignora entradas
  con `revoked_at != null` al poblar la tabla, pero las preserva en
  el YAML.
- Mismo patron que `RelationDiscard` (no se borra; resuelve).

---

## §3 — Riesgo nuevo no listado en §8 del plan

### Riesgo 5 (CodeMCP-especifico): asimetria de cache del detector entre instancias del MCP server tras deploy

**Descripcion.** Cuando se hace deploy via Railway con el nuevo
schema (FASE C2g):

1. La nueva imagen del server arranca con codigo nuevo (lee modelos
   nuevos `RelationAlias`, `RelationDiscard`).
2. Pero el detector Humandato (`humandato_queries.py`) puede tener
   resultados cacheados de la version anterior si hay caching
   activo, o generar baselines pre-deploy.
3. Las primeras llamadas a `cs_get_alerts` post-deploy pueden
   reportar estado mixto: alertas viejas + alertas del nuevo
   detector.

**Sedimento aplicable indirectamente:** `Bucle fantasma->nodo cerrado
por la herramienta como herradura epistemica` (active, w=1.0) — la
herramienta debe ser confiable como fuente unica para el Guardian.
Asimetria de cache la hace no-confiable temporalmente.

**Mitigacion propuesta:**

Agregar a §6 C2g un step explicito post-deploy:

> Tras railway deploy completo, antes de servir trafico:
>
> 1. Invalidar cache del detector:
>    `python manage.py invalidate_humandato_cache` (o llamada
>    equivalente al engine singleton de db.py).
> 2. Ejecutar `cs_get_alerts` directamente al endpoint y verificar
>    que la salida incluye seccion "Aristas pending" (cierre §2.C
>    de este documento).
> 3. Solo entonces autorizar reset MCP de sesiones de agentes.

**Costo:** ~5 LOC en server.py + step explicito en checklist deploy.
**Beneficio:** evita que la primera lectura del Guardian post-deploy
sea mixta y produzca diagnostico erroneo de "el detector no funciona".

---

## §4 — Resumen de propuestas concretas (tabla)

| ID | Propuesta | Donde aplica | Costo | Bloqueante |
|----|-----------|--------------|-------|------------|
| 1.1.A | Declarar tres-capas como patron portable en §9.3 con desarrollo | Plan §9.3 | edicion plan | no |
| 1.1.B | Agregar subfase C0d (audit otros canales) | Plan §6 FASE C0 | nueva subfase | no |
| 1.1.C | Criterio bifurcacion: ≥10 → F47-D, <10 → deuda | Plan §6 C0d | criterio explicito | no |
| 1.2 | Cache de RelationAlias en dict al inicio del run | Plan §5 Capa 2 | nota implementacion | no |
| 1.3 | `related_name="discard_origin"` en FK Discard.resolved_relation | Plan §5 Capa 3 | edicion modelo | no |
| 1.4.A | Subseccion Mirador en §7 con contrato proyeccion | Plan §7 | seccion nueva | no |
| 1.4.B | Agregar D7 a §10 (decision Mirador integra o difiere) | Plan §10 | nueva fila tabla | no |
| 1.5.A | Renombrar `--auto` -> `--apply-seeded-aliases` | Plan §6 C3b | edicion comando | no |
| 1.5.B | Flag `--dry-run` obligatorio antes | Plan §6 C3b | feature comando | no |
| 1.5.C | Audit log con prefijo `relation_discard_seeded_apply` | Plan §6 C3b | logging | no |
| 2.A | Orden simetrico explicito post-deploy en C2g | Plan §6 C2g | nota orden | no |
| 2.B | Verificar que modelos no usan UUID con SQL default | Implementacion C2a | code review | no |
| 2.C | Extender `cs_get_alerts` con seccion Aristas pending | Codigo CodeMCP | <30 LOC | no |
| 2.D | Implementar tool `cs_get_discards` en C2 (alfa) | Plan §6 C2 + codigo | ~50 LOC | no |
| 2.E | `relation_alias_seed.yaml` append-only con `revoked_at` | Plan §6 C1c | convencion seed | no |
| 3 | Mitigacion riesgo cache detector post-deploy | Plan §6 C2g + §8 | step deploy | no |

**Total propuestas:** 16. Ninguna requiere cambio fundamental al plan;
todas son refinamientos compatibles con el draft actual.

---

## §5 — Hallazgos del grafo MTV usados en este analisis (transparencia)

Conceptos consultados via `cs_search_concepts` (sin filtro project,
axioma cross-project del plan §2). Solo se listan los referenciados
en linea:

| Concepto | Weight | Status | Ultima vez | Aporte al analisis |
|----------|--------|--------|------------|---------------------|
| validacion depth values como barrera procedural en protocolo YAML | 1.0 | dormant | 2026-04-09 | Confirma D6: depth ya tiene barrera procedural pero no estructural (§1.1) |
| YAML no procesado como causa de ausencia de dominio en grafo | 0.7 | dormant | 2026-04-22 | Caso real de domain discordante (§1.1) |
| dominio graph_operations ausente del registro formal | 0.3 | dormant | 2026-04-22 | Caso especifico documentado (§1.1) |
| RELATION_MAP desactualizado en extract_concepts (6 vs 11 tipos) | 1.4 | dormant | 2026-04-17 | Antecedente directo del problema (§1.1) |
| extension de RelationType 6 a 11 tipos en Concept Sediment | 3.0 | dormant | 2026-04-17 | Patron historico recurrente (§1.1) |
| Distincion reconciliacion-grafia vs promocion-genuina | 1.0 | active | 2026-05-04 | Sedimento referenciado por el plan §2 |
| Asimetria grafo / Mirador como axioma operativo | 1.0 | active | 2026-04-30 | Define contrato Mirador<->grafo (§1.4) |
| Bucle fantasma->nodo cerrado por la herramienta como herradura epistemica | 1.0 | active | 2026-05-04 | Define que el Mirador genera evidencia conservando D2 (§1.4) |
| Mirador como herramienta del grafo, no de proyecto | 1.0 | active | 2026-05-02 | Confirma transversalidad del contrato (§1.4) |
| Rectificacion manual de type a principle ... distinto a promocion automatica por uso | 1.0 | active | 2026-05-05 | Refuerza objecion al `--auto` (§1.5) |
| Precaucion pre-deploy MCP | 2.0 | active | (heredado §2 plan) | Justifica orden simetrico C2g (§2.A) |

**Cs_get_alerts(project="concept-sediment-mcp"):** sistema
inmunologico estable. Sin alertas. Esto confirma que las propuestas
no entran en conflicto con axiomas activos identificados como
fracturas o vacunas faltantes.

---

## §6 — Pendientes para iteracion

Este documento NO instruye ejecucion. Pendientes:

1. **Bibliotecario** revisa que las respuestas a sus 5 observaciones
   sean satisfactorias y que las mejoras CodeMCP-especificas (§2)
   no introduzcan tensiones con sedimentos que CodeMCP no haya
   considerado.

2. **CodeCS** decide si incorpora las 16 propuestas al plan
   (parcialmente / totalmente / ninguna) y produce el draft v2.

3. **Guardian** decide sobre las decisiones D6 / D7 / aprobacion
   del seed alias / aprobacion del flag rename / orden de FASES.

4. **CodeMCP** (yo) queda disponible para:
   - Ejecutar §2.A (verificar UUIDs en code review C2a) cuando se
     abra esa fase.
   - Implementar §2.C (extender `cs_get_alerts`) cuando se abra
     C2d.
   - Implementar §2.D (`cs_get_discards`) cuando se abra C2e.
   - Coordinar deploy C2g siguiendo orden simetrico §2.A.

---

> **Estado del documento al cierre de redaccion (2026-05-05).**
> Iteracion CodeMCP sobre PLAN_MULTISESION_F47 draft del 2026-05-05.
> Aporta respuesta a 5 observaciones del Bibliotecario + 5 mejoras
> CodeMCP-especificas + 1 riesgo nuevo. Total 16 propuestas
> compatibles con el plan actual. Pendiente revision Bibliotecario,
> sintesis CodeCS, decision Guardian.

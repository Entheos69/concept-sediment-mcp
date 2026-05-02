# Relación `interpreted_under` — caso especial fuera de `RELATION_MAP`

**Sedimentado:** F45 SESIÓN 0, 2026-05-02. Ground en `concept-sediment/sessions/2026-05-02-001-CodeCS.yaml` (concepto F: decisión gamma; concepto A: Axioma D2).

Este documento describe el flujo del extractor `extract_concepts.py` (concept-sediment Django) cuando un YAML de sedimentación incluye una relación `interpreted_under` que cita un frame del Mirador. El comportamiento se desvía deliberadamente del flujo `RELATION_MAP` estándar.

---

## 1. Sintaxis YAML

```yaml
concept_sediment:
  concepts:
    - name: "<concepto que se cita bajo un frame>"
      depth: decision
      domains:
        - <dominio>
      related_to:
        - target: "frame:<alias>"
          relation: interpreted_under
          notes: "<anotación opcional sobre la interpretación>"
      notes: |
        <descripción del concepto>
```

El campo `target` debe llevar el prefijo literal `frame:` seguido del alias del archivo `<alias>.json` que vive en `settings.FRAMES_DIR` (ver §5).

---

## 2. Caso especial fuera de `RELATION_MAP`

`interpreted_under` es el **único** caso especial fuera del mapa estándar de relaciones. Razón: la cita NO se persiste en `graph_conceptrelation` sino en una tabla separada `graph_frame_reference` (concept-sediment Django, modelo `FrameReference`).

Esta separación se decidió en F45 SESIÓN 0 (decisión gamma) tras evaluar tres opciones:

- **alfa** (no persistir): pierde información. Descartada.
- **beta** (pseudo-conceptos `frame:` en `graph_concept`): contamina la tabla conceptual con entidades que no son conceptos. Descartada.
- **gamma** (tabla separada `graph_frame_reference`): preserva trazabilidad sin sobrecargar relaciones, soporta multi-frame natural (un concepto puede ser citado bajo varios frames simultáneamente sin contradicción). **Elegida.**

Implicación operativa: el detector de fracturas (`humandato_queries.py` en concept-sediment-mcp) NO necesita conocer `interpreted_under`, porque la relación no vive en `graph_conceptrelation`. Por la misma razón, **`INTERPRETED_UNDER` NO se agrega al enum `RelationType`** (decisión X1 = b en `PLAN_MULTISESION_F45_v2.md`).

---

## 3. Candado bidireccional

El extractor aplica dos chequeos simétricos antes de despachar la rama especial:

| Disparador | Verificación | Acción si falla |
|---|---|---|
| `target` empieza con `frame:` | `relation` DEBE ser `interpreted_under` | **ERROR + skip** (cualquier otra `relation` con prefijo `frame:` queda registrada como error semántico y la relación no se procesa) |
| `relation` es `interpreted_under` | `target` DEBE empezar con `frame:` | **WARNING + skip** (relación queda descartada con aviso al stdout, sin elevar a error) |

La asimetría en severidad (ERROR vs WARNING) refleja que el primer caso es intent claro de citar un frame con sintaxis incorrecta (más grave); el segundo puede ser confusión del agente sobre qué constituye un frame válido (educativo).

---

## 4. Audit log explícito

Cada disparo exitoso de la rama especial emite un log estructurado obligatorio:

- Identificador estable: `interpreted_under_dispatch`
- Campos: `source_concept`, `frame_alias`, timestamp.
- Canal: `logger.info(...)` + `stdout` con marcador `[audit]`.

**Razón:** vacuna contra silent-discard. Sin audit explícito, una rama especial fuera del flujo principal puede absorber datos sin dejar traza inspeccionable. Esta vacuna se sedimenta vinculada al concepto activo **"validación semántica ausente en extract_concepts"** (concept-sediment, weight 1.0): el extractor histórico validaba existencia de target y validez de tipo, pero no semántica del par (relation, target). El audit log explícito complementa esa validación con observabilidad post-disparo.

---

## 5. Validación del frame

Antes de crear el row en `graph_frame_reference`, el extractor valida que el archivo existe físicamente:

```python
frame_path = settings.FRAMES_DIR / f"{frame_alias}.json"
if not frame_path.exists():
    raise CommandError(
        f"Frame no encontrado: {frame_path}. "
        f"Verifica que el archivo existe antes de citar el frame."
    )
```

`settings.FRAMES_DIR` se define en `concept-sediment/config/settings.py` (decisión D1 = A en F45 SESIÓN 0):

```python
FRAMES_DIR = BASE_DIR / "dashboard" / "frames"
```

Si el archivo no existe, el extractor lanza `CommandError` y aborta el procesamiento del YAML completo. Esta validación es estricta porque la ausencia del frame indica desincronización entre sedimentación y curación visual del Mirador, no una variación tolerable.

**Modelo `FrameReference` (concept-sediment Django, NO en MCP server):**

| Campo | Tipo | Notas |
|---|---|---|
| `source_concept` | FK a `Concept` | `on_delete=CASCADE` |
| `frame_alias` | `TEXT(255)` | matchea `<alias>.json` en `FRAMES_DIR` |
| `notes` | `TEXT` | opcional, anotación de la interpretación |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Sin** unique constraint sobre `(source_concept, frame_alias)`: multi-frame natural (un concepto puede aparecer en varios frames; el mismo concepto puede ser re-interpretado bajo el mismo frame en distintas sesiones).

---

## 6. Ground arquitectónico — dos axiomas complementarios

La decisión gamma se justifica conjuntamente por dos axiomas sedimentados; ninguno por sí solo basta.

### Axioma A — Asimetría grafo / Mirador como axioma operativo

> "El grafo concept-sediment es emergente y sagrado: solo se escribe vía actos cognitivos de agentes (YAMLs sedimentados). El Mirador conectoma es modificable, regenerable y reiniciable: solo se escribe vía actos perceptuales/curatoriales del Guardian."

(`Asimetría grafo / Mirador como axioma operativo`, project=inducop, weight 1.0, sedimentado 2026-04-29)

**Eje:** arquitectónico. Define el Mirador como capa observacional aditiva al grafo (microscopio vs célula). Los frames son entidades del Mirador, **externas** al grafo conceptual. Por tanto `interpreted_under` NO puede vivir en `graph_conceptrelation` (que es relación interna al grafo) — habría una violación categorial.

### Axioma B — Axioma D2 (gobernanza)

> "La posición axiomática fuerte es para la IA. La IA no puede intervenir el grafo por iniciativa propia. Si lo hace en algún momento, es bajo todo un conjunto de precauciones."

(`Axioma D2: la IA no puede intervenir el grafo por iniciativa propia`, project=concept-sediment, weight 1.0, sedimentado 2026-05-02 en F45 SESIÓN 0)

**Eje:** gobernanza. Define qué agentes pueden escribir al grafo y bajo qué condiciones. La tabla separada `graph_frame_reference` aísla la escritura de cita-de-frame de la escritura de relaciones del grafo: cualquier modificación a `graph_frame_reference` es operación delimitada con precauciones explícitas (validación del frame en §5, audit log en §4) y no contamina `graph_concept` ni `graph_conceptrelation`.

### Por qué los dos juntos

La asimetría (Axioma A) sin D2 dejaría abierta la tentación de implementar `interpreted_under` como relación interna "porque es conveniente"; D2 (Axioma B) sin la asimetría no daría justificación arquitectónica para la separación de tablas. Juntos cierran el caso: frames son externos **y** la IA escribe a `graph_frame_reference` solo bajo precondiciones (validación archivo + audit log obligatorio).

---

## 7. Referencias

- **Sedimento ground:** [`concept-sediment/sessions/2026-05-02-001-CodeCS.yaml`](../concept-sediment/sessions/2026-05-02-001-CodeCS.yaml) — concepto **A** (Axioma D2), concepto **F** (decisión gamma con `derived_from` a A y a "Asimetría grafo/Mirador").
- **Plan operacional:** [`docs_inducop/organizacion/Cuadernos/2026-04-29-1518/PLAN_MULTISESION_F45_v2.md`](../docs_inducop/organizacion/Cuadernos/2026-04-29-1518/PLAN_MULTISESION_F45_v2.md) §4 (detalle por sesión: 1a modelo `FrameReference`, 1b este documento, 2 implementación extractor, 3 tests).
- **Conceptos del grafo invocados** (consultar via MTV cross-project — sedimento E, omitir filtro `project=`):
  - `Asimetría grafo / Mirador como axioma operativo` (project=inducop).
  - `Axioma D2: la IA no puede intervenir el grafo por iniciativa propia` (project=concept-sediment).
  - `validación semántica ausente en extract_concepts` (project=concept-sediment) — vincula el audit log de §4.
  - `Frame como marco teorico no axiomatico` (project=inducop) — fuente de la sintaxis canónica `frame:<alias>`.

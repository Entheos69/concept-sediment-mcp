# Sistema de Weight, Decay y Sedimentación

Semántica cuantitativa del grafo de Concept-Sediment. Define cómo se calcula la fuerza de un concepto, cómo decae con el tiempo, y cuándo se archiva.

---

## Sistema de Weight (peso)

El **weight** refleja la relevancia acumulada de un concepto a lo largo de las sesiones que lo mencionan.

### Incrementos por uso

| Acción | Incremento |
|--------|------------|
| `mention` (mención en discusión) | +0.3 |
| `usage` (aplicación en código) | +0.7 |
| `decision` (informó decisión arquitectónica) | +1.0 |

Esto coincide con los valores válidos del campo `depth` en los YAMLs de cierre (`mention | usage | decision`).

### Interpretación cuantitativa

| Weight | Interpretación |
|--------|----------------|
| `≥ 2.0` | **Altamente consolidado.** Principio validado en múltiples sesiones. Restricción dura — no contradecir sin consultar al Guardian. |
| `1.5 – 2.0` | **Probado.** Patrón usado varias veces. Candidato a estandarización formal. |
| `1.0 – 1.5` | **Emergente.** Concepto en proceso de consolidación. |
| `0.7 – 1.0` | **Aplicado pero único.** Una decisión o uso aislado. |
| `< 0.7` | **Tentativo.** Mención puntual o evento de baja consolidación. |

### Ejemplos

- Principio con `weight 2.0` → usado activamente en múltiples sesiones (consolidado, intocable sin consultar)
- Patrón con `weight 1.4` → usado 2 veces (probado, considerar documentar formalmente)
- Evento con `weight 0.3` → mencionado una sola vez (tentativo, observar)

---

## Sistema de Decay (decaimiento)

**Versión 2026-04-23: migrado de "sesiones del dominio" a días naturales + densidad relativa + amortiguador por weight.** La métrica anterior (sesiones del dominio sin mención) degradaba injustamente conceptos vigentes en dominios de alta frecuencia diaria — ver CS004 por diagnóstico.

Los conceptos pierden relevancia con el tiempo natural desde su última mención en una sesión del dominio. El ritmo depende del **type** (event/pattern/principle) y se modula por densidad de aparición reciente y weight acumulado.

### Reglas base por type (días naturales sin mención)

| Type | dormant | archived | Decay |
|------|---------|----------|-------|
| `event` | 7 días | 30 días | **Rápido** — vida útil corta |
| `pattern` | 30 días | 90 días | **Medio** — recurre en múltiples sesiones |
| `principle` | — | — | **Nunca decae** |

### Moduladores (extienden umbrales)

- **Densidad relativa:** si el concepto aparece en `≥ 5%` de las sesiones de su dominio en los últimos 30 días, los umbrales se **duplican** (protege presencia sostenida contra ruido de sesiones sin mención).
- **Weight amortiguador:**
  - `weight ≥ 2.0` → umbrales `× 1.5` (consolidado resiste más)
  - `weight ≥ 3.0` → **nunca llega a archived** (tope: dormant)

### Recuperación de archived

A diferencia de la versión anterior, los conceptos `archived` **sí entran** al recálculo de decay: si reciben una mención reciente (o su densidad sube), pueden volver a `active` o `dormant` automáticamente. Ya no hay trampa permanente.

### Settings (environment variables)

```
CS_DECAY_EVENT_DORMANT_DAYS       = 7
CS_DECAY_EVENT_ARCHIVED_DAYS      = 30
CS_DECAY_PATTERN_DORMANT_DAYS     = 30
CS_DECAY_PATTERN_ARCHIVED_DAYS    = 90
CS_DECAY_DENSITY_WINDOW_DAYS      = 30
CS_DECAY_DENSITY_PROTECT          = 0.05
CS_DECAY_WEIGHT_PROTECT           = 2.0
CS_DECAY_WEIGHT_NEVER_ARCHIVE     = 3.0
```

### Implicación operativa

- Un evento dormant es información histórica; rara vez aparece en queries default
- Un patrón dormant puede ser pista de algo que se dejó de hacer (¿por qué?)
- Un principio nunca se archiva — siempre debe respetarse activamente
- Un concepto archived con weight ≥ 2.0 es candidato a auditoría: probablemente sobrevivió a la métrica vieja de sesiones, debería reactivarse al próximo `recalculate_decay`

---

## Sistema de Conceptos Dormant

Los conceptos con `status: dormant` **NO aparecen en búsquedas por default**. Esto evita ruido cuando consultas el grafo activo.

### Cómo recuperar conocimiento dormant

Usa `cs_search_concepts` con texto amplio — los conceptos archivados pueden aparecer si son **semánticamente relevantes** al query (los embeddings cubren el grafo completo, no solo los activos).

### Reactivación automática

Un concepto dormant vuelve a `status: active` si se menciona en una nueva sesión. Esto sucede solo:
1. Generar YAML que incluya el nombre del concepto en `concepts[].name` o en `related_to[].target`
2. Procesar el YAML con `process_session.sh`
3. El concepto se reactiva con su weight previo + el incremento de la nueva mención

### Cuándo buscar dormant deliberadamente

- Investigando un problema que "se siente familiar"
- Antes de proponer una solución que pudo haberse intentado y descartado
- Auditando por qué algo dejó de hacerse

---

## Las 7 Reglas de Oro

1. **Consultar antes de decidir.** Si una decisión puede repetir un error pasado, buscar primero con `cs_search_concepts`.
2. **Weight indica consolidación.** Conceptos con `weight ≥ 2.0` son principios validados; respetarlos estrictamente.
3. **Relaciones revelan cadenas causales.** Usar `cs_get_concept_graph` para entender el contexto completo de un concepto.
4. **Hipótesis descartadas son valiosas.** Documentarlas previene re-trabajo futuro.
5. **Depth refleja nivel de uso.** Usar `decision`/`usage`/`mention` apropiadamente al cerrar sesión.
6. **Principios nunca decaen.** Son restricciones duras del sistema. Deben respetarse estrictamente; si parecen estorbar, hay que cuestionar la tarea, no el principio.
7. **Patrones con alto weight son candidatos a estandarización.** Si `weight ≥ 1.5` y múltiples relaciones, considerar documentación formal.

---

## Notas para CodeCS (mantenedor)

Como mantenedor del MCP, presta atención particular a:

- **Principios con weight bajo:** indican definición frágil. Si un principio aparece con `weight 1.0` después de muchas sesiones, algo está mal en el cálculo o en cómo se está clasificando.
- **Patrones que oscilan entre active y dormant:** señal de inestabilidad conceptual o de que el threshold de 6 sesiones es inadecuado para ese dominio.
- **Eventos que escalan a patterns:** seguimiento natural si el sistema funciona — cuando un evento se repite varias veces, debería promoverse. Si no lo hace, revisar la lógica de inferencia de type.
- **Dormants que nunca reactivan:** posibles candidatos a purga o consolidación con conceptos vivos similares.

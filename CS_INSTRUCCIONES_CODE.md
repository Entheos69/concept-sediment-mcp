# Concept Sediment — Instrucciones para Code

## Carga de Contexto (posición #0 en el protocolo)

Al inicio de cada sesión, leer **CONCEPTOS_RESUMEN.md**. Este archivo es
compacto (~2-3k tokens) y contiene todos los conceptos activos con su
weight, dominios y referencia a líneas de detalle.

NO leer CONCEPTOS_FULL.md completo al arrancar. Solo leerlo por rangos
cuando se necesite el detalle de un concepto específico.

## Lectura por rangos

CONCEPTOS_RESUMEN.md incluye tags de línea entre corchetes para cada concepto:

```
- **full_clean en save parcial** | w:2.0 | django_patterns [L10-L26]
```

Esto significa que el detalle completo está en CONCEPTOS_FULL.md líneas 10-26.
Para leerlo:

```
view CONCEPTOS_FULL.md [10, 26]
```

Esto retorna la descripción completa, relaciones, proyectos y metadata del
concepto sin cargar el archivo entero.

## Cuándo consultar detalle

- Antes de tomar una decisión que pueda contradecir un principio existente
- Cuando un concepto del resumen es relevante para la tarea actual
- Cuando el Guardian menciona un concepto por nombre
- Cuando se trabaja en un dominio y se quiere verificar patrones conocidos

## Cuándo NO consultar detalle

- Para tareas que no tienen relación con conceptos existentes
- Si el resumen ya da suficiente contexto (nombre + weight + dominio)
- Para operaciones rutinarias donde el concepto ya se aplicó antes

## Búsqueda por dominio

Si la sesión se enfoca en un dominio específico, filtrar mentalmente
CONCEPTOS_RESUMEN.md por los dominios relevantes. Los dominios activos son:

- `django_patterns` — ORM, vistas, modelos, signals, middleware
- `frontend` — CSS, JS, Bootstrap, responsive
- `api_design` — REST, FastAPI, DRF, endpoints
- `ai_integration` — LLM, Whisper, RAG, embeddings
- `devops` — Railway, Docker, Cloudinary, CI/CD
- `architecture_decisions` — Diseño, tradeoffs, documentación técnica
- `validation_patterns` — Patrón A+C, validación preventiva, integridad
- `workflow_protocols` — Carga de contexto, hooks, sesiones, automatización
- `ux_patterns` — UX, transparencia, gamificación
- `documentation` — Destilados, manuales, verificación cruzada

## Cierre de sesión

Al cerrar, generar el bloque YAML de concept_sediment con los conceptos
trabajados en la sesión. Formato:

```yaml
concept_sediment:
  session_id: "YYYY-MM-DD-NNN-Code"
  project: <proyecto>
  domains_active:
    - <dominios tocados>
  concepts:
    - name: "nombre descriptivo"
      depth: decision|usage|mention
      domains:
        - <dominios del concepto>
      related_to:
        - target: "concepto relacionado"
          relation: depends_on|derived_from|contradicts|refines|resolves|instance_of
      notes: "Contexto y descripción"
  status: draft
```

Reglas:
- `depth` refleja cómo se usó el concepto: mention (referenciado), usage (aplicado), decision (informó una decisión)
- El `type` (event/pattern/principle) NO se incluye — lo infiere el sistema
- `status: draft` — el Guardian cambia a `reviewed` antes de procesar
- Las hipótesis descartadas son tan valiosas como la solución

# Protocolo de Apertura y Cierre de Sesión (CodeCS)

Aplica el protocolo estándar de Concept-Sediment con particularidades de CodeCS: `session_id` con sufijo `-CodeCS` y `project: "concept-sediment"`.

---

## Apertura de Sesión

### Paso 0: Verificar WAL huérfano

```bash
ls ../concept-sediment/sessions/_WM_Code_*.jsonl 2>&1
```

**Interpretación:**

- **No hay WAL:** proceder al paso 1 (normal).
- **WAL de fecha anterior:** cierre abrupto detectado → recuperar conceptos.
  ```bash
  cat ../concept-sediment/sessions/_WM_Code_YYYY-MM-DD_NNN.jsonl
  grep '"consumed":false' ../concept-sediment/sessions/_WM_Code_*.jsonl
  ```
  **Acción:**
  1. Extraer temas + conceptos con `consumed: false`
  2. Generar YAML(s) pendientes con `status: draft`
  3. Borrar WAL: `rm ../concept-sediment/sessions/_WM_Code_*.jsonl`
  4. Informar al Guardian: "Recuperados N conceptos de sesión {fecha}"

- **WAL de hoy:** posible continuación de sesión.
  1. Preguntar al Guardian: "¿Continuar sesión actual o iniciar nueva?"
  2. Si nueva → generar YAMLs del WAL anterior (si hay pendientes), borrar, crear nuevo
  3. Si continuación → APPEND al WAL existente durante la sesión

### Paso 1: Contexto semántico

```
cs_get_session_context(
    project="concept-sediment",
    domains=["mcp_architecture", "yaml_schemas", "graph_operations",
             "sediment_protocols", "architecture_decisions", "workflow_protocols"],
    format="markdown",
    limit=20
)
```

Ajustar `domains` al foco de la sesión (no pedir todos si no aplica).

### Paso 2: Alertas inmunológicas

```
cs_get_alerts(project="concept-sediment")
```

Interpretar según [stack-cs.md](stack-cs.md) → sección "Alertas inmunológicas".

### Si el MCP no responde (fallback)

**NO asumir que los conceptos no existen.** Aplicar Fallback del MCP (ver SKILL.md principal):
```bash
grep -r "nombre-concepto" ../concept-sediment/knowledge/
```

Informar al Guardian: "MCP no disponible, usando fuente alternativa `knowledge/`".

### Confirmación al Guardian

Reportar:
- ✅ Herramientas MCP usadas (o fallback aplicado)
- ✅ Estado del grafo (sin alertas / fracturas / vacunas)
- ✅ Dominios cargados
- ⚠️ Si MCP cayó, mencionarlo

---

## Cierre de Sesión: 8 Pasos Anti-Sobrescritura

### ⚠️ CRÍTICO: Formato con Clave Raíz Obligatoria

La línea 2 del archivo (después de `---`) **DEBE SER** `concept_sediment:`. Sin esa clave raíz, el parser falla.

```yaml
---
concept_sediment:                        # ← OBLIGATORIO en línea 2
  session_id: "YYYY-MM-DD-NNN-CodeCS"     # ← CodeCS, no Code genérico
  project: "concept-sediment"            # ← NO "inducop"
  domains_active:
    - sediment_protocols
    - mcp_architecture
  concepts:
    - name: "nombre descriptivo del concepto"
      depth: decision                     # decision|usage|mention
      domains:
        - sediment_protocols
      related_to:
        - target: "concepto relacionado"
          relation: depends_on
      notes: "Contexto y descripción."

  status: draft                           # SIEMPRE draft
```

### 🚨 Anti-patterns

**Anti-pattern 1: falta clave raíz**
```yaml
---
session_id: "2026-04-13-NNN-CodeCS"  # ❌ FALTA concept_sediment:
project: "concept-sediment"
```
→ Error: `Missing 'concept_sediment' root key`.

**Anti-pattern 2: depth vs type**
```yaml
- name: "placeholders para extensibilidad"
  depth: pattern  # ❌ "pattern" es un TYPE, no un DEPTH
```

✅ Correcto:
```yaml
- name: "placeholders para extensibilidad"
  depth: decision  # ✅ CÓMO se usó
  notes: "Patrón de diseño: ..."
  # El sistema inferirá type=pattern por el contexto
```

### Reglas de campos

1. **`depth`** refleja cómo se usó el concepto:
   - `decision` — INFORMÓ una decisión arquitectónica
   - `usage` — se APLICÓ directamente en código
   - `mention` — se REFERENCIÓ en discusión
   - ⚠️ Si las notas dicen "patrón de diseño", NO escribas `depth: pattern`. Pregunta: ¿informó, aplicó, o mencionó?

2. **`type`** (event/pattern/principle) NO se incluye — el sistema lo infiere.

3. **`status: draft`** — Guardian lo revisa y cambia a `reviewed` antes de procesarlo.

4. **Hipótesis descartadas** son tan valiosas como la solución — documentarlas previene re-trabajo.

5. **`related_to`** puede estar vacío si el concepto es nuevo y aún no tiene relaciones.

6. **11 tipos de relaciones** — ver [stack-cs.md](stack-cs.md) sección "Weights y relaciones".

7. **`layers`** (opcional) — solo cuando una fractura revela que un concepto no es atómico. NO preventivamente. Ver [stack-cs.md](stack-cs.md).

### Paso 0: Verificar WAL para consumir

```bash
cd ../concept-sediment
bash check_wal_status.sh
```

Interpretación:

- **"All checkpoints consumed":** todos los conceptos ya capturados en YAMLs.
  **Acción:** borrar WAL y TERMINAR (NO generar YAMLs duplicados).
  ```bash
  rm ../concept-sediment/sessions/_WM_Code_*.jsonl
  ```

- **"X pending checkpoint(s)":** hay checkpoints sin convertir.
  **Acción:** proceder al Paso 1 para generar YAMLs SOLO de checkpoints pendientes.

- **"No WAL found":** sesión sin WAL (método tradicional). Proceder al Paso 1.

### Paso 1: Verificar archivo YAML existente (OBLIGATORIO)

```bash
ls -la ../concept-sediment/sessions/{YYYY-MM-DD}-{NNN}*.yaml 2>&1
```

- Si NO existe → usar nombre estándar: `{YYYY-MM-DD}-{NNN}-CodeCS.yaml`
- Si existe `063` → usar sufijo: `{YYYY-MM-DD}-{NNN}a-CodeCS.yaml`
- Si existe `063a` → usar sufijo: `{YYYY-MM-DD}-{NNN}b-CodeCS.yaml`
- **MOSTRAR output de `ls` al Guardian** como evidencia pre-write

### Paso 2: Generar contenido YAML

🚨 **VALIDACIÓN PRE-WRITE:**
- **PRIMERA LÍNEA** después de `---` DEBE ser `concept_sediment:`
- NO escribir `session_id:` directamente después de `---`
- Indentación: 2 espacios para campos internos

Si es fase múltiple (sufijo -a, -b), agregar `session_note` después de `project`:
```yaml
session_note: "Fase N de sesión extendida. Temas: [breve descripción]"
```

### Paso 2.5: Validar depth values (OBLIGATORIO)

```bash
echo "$yaml_content" | grep -E "^\s+depth:" | grep -vE "(mention|usage|decision)"
```

**Interpretación:**
- ✅ Sin output → todos los depth válidos, proceder a Paso 3
- ❌ Con output → depth inválido detectado
  - Revisar líneas mostradas
  - Cambiar a `decision | usage | mention`
  - Pregunta: ¿INFORMÓ decisión, se APLICÓ en código, o solo se MENCIONÓ?
  - Re-ejecutar validación hasta que no haya output

**Razón:** `depth` describe CÓMO se usó, no QUÉ es. Este error causó fallo en procesamiento de 066a (2026-04-02).

### Paso 3: Escribir archivo físico

```python
Write(
    file_path="../concept-sediment/sessions/{nombre_determinado_paso1}",
    content=yaml_content
)
```

### Paso 4: Verificar creación + validar formato (OBLIGATORIO)

```bash
# Verificar creación
ls -la ../concept-sediment/sessions/{nombre_determinado_paso1}

# VALIDAR FORMATO (línea 2 DEBE ser concept_sediment:)
head -3 ../concept-sediment/sessions/{nombre_determinado_paso1}
```

**Checklist de validación:**
- ✅ Timestamp < 10 segundos
- ✅ Tamaño > 500 bytes (conceptos no vacíos)
- ✅ **Línea 2 es `concept_sediment:`** (CRÍTICO)
- ✅ Línea 3 es `  session_id: "..."` (con 2 espacios)

**Si línea 2 NO es `concept_sediment:`:**
```
❌ ERROR DE FORMATO: YAML malformado
Regenerar archivo con clave raíz concept_sediment:
```

**Confirmar al Guardian:**
```
✅ Archivo YAML generado: [ruta] ([tamaño])
✅ Formato validado: concept_sediment: presente en línea 2
```

### Paso 5: Actualizar WAL (si existe)

```bash
# Marcar checkpoints como consumed y agregar referencia YAML
# Editar WAL agregando: "consumed": true, "yaml": "NNN"
```

Verificar estado final:
```bash
bash check_wal_status.sh
# Si "All checkpoints consumed" → borrar WAL
rm ../concept-sediment/sessions/_WM_Code_*.jsonl
```

### Paso 6: Incluir en reporte

- Incluir mismo contenido YAML en sección 13 del reporte
- Mencionar nombre de archivo físico generado

### Paso 7-8: Guardian procesa

- Guardian revisa el archivo `.yaml` y cambia status a `reviewed`
- Guardian ejecuta el MCP para procesar el YAML y actualizar `knowledge/*.yaml`
- MCP actualiza weights, relaciones y genera nuevos archivos si es necesario

---

## Reglas críticas de prevención

- ❌ NUNCA escribir YAML sin ejecutar Paso 1 (verificación pre-write)
- ❌ NUNCA escribir YAML sin ejecutar Paso 4 (verificación post-write + validación formato)
- ✅ SIEMPRE usar sufijo (-a, -b, -c) si archivo existe
- ✅ SIEMPRE mostrar evidencia física (ls output) al Guardian
- ✅ SIEMPRE validar que línea 2 del archivo es `concept_sediment:`
- ✅ SIEMPRE usar `session_id` con sufijo `-CodeCS` y `project: "concept-sediment"`

**Failure modes documentados:** ver [failure-modes.md](failure-modes.md).

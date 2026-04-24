# Protocolo de Vacunas VCM (Vector de Conocimiento Mínimo)

**Última actualización:** 2026-04-24 (Arquitectura project-agnostic)

---

## Concepto

Las **vacunas VCM** son directivas críticas hardcoded en `humandato_queries.py` que el sistema inmunológico del grafo verifica en cada consulta de alertas (`cs_get_alerts`).

**Función:** Detectar proactivamente cuando conocimiento crítico NO está representado en el grafo, antes de que cause incidentes.

---

## Estructura de una Vacuna

```python
{
    "name": "emoji",                    # String de búsqueda (ILIKE %name%)
    "scope": "global",                   # "global" | "project_specific"
    "applicable_projects": ["inducop"],  # Solo si scope="project_specific"
    "category": "encoding",              # Categoría de la directiva
    "severity": "critical",              # "critical" | "high" | "medium"
    "directive": "NUNCA usar emojis...", # La regla en lenguaje natural
    "min_weight": 1.0,                   # Peso mínimo esperado
    "failure_history": "S064, S078",     # Evidencia de violaciones pasadas
}
```

---

## Scope: Global vs Project-Specific

### Global (`"scope": "global"`)

**Semántica:** Si la vacuna existe en CUALQUIER proyecto del grafo con weight suficiente, NO se reporta como faltante para NINGÚN proyecto.

**Cuándo usar:**
- Directivas universales que aplican a todos los proyectos
- Conocimiento que, una vez sedimentado, protege a todo el sistema
- Ejemplos: encoding Windows, workflow general, reglas de git

**Verificación:**
```sql
-- Busca en TODO el grafo (sin filtro de proyecto)
SELECT name, weight FROM graph_concept 
WHERE name ILIKE '%emoji%' AND status = 'active'
ORDER BY weight DESC LIMIT 1
```

**Ejemplos actuales:**
- `emoji` - encoding Windows
- `stdout.flush` - encoding Windows
- `git push` - workflow
- `3 intentos` - workflow
- `delete()` - Django DB

### Project-Specific (`"scope": "project_specific"`)

**Semántica:** Solo se verifica cuando se consulta un proyecto que está en `applicable_projects`. Debe existir en ESE proyecto específico.

**Cuándo usar:**
- Directivas que solo tienen sentido en contextos específicos
- Workflow que solo aplica a un proyecto
- Tecnologías que no están en todos los proyectos

**Verificación:**
```sql
-- Filtra por proyecto consultado
SELECT name, weight FROM graph_concept 
WHERE name ILIKE '%YAML%' 
  AND 'concept-sediment' = ANY(projects)
  AND status = 'active'
ORDER BY weight DESC LIMIT 1
```

**Ejemplos actuales:**
- `YAML` - solo concept-sediment (cierre de sesión)
- `catalogo` - solo inducop (CSS frontend)

---

## Protocolo para Agregar Nueva Vacuna

### 1. Identificar necesidad

**Triggers:**
- Directiva violada recurrentemente
- Conocimiento crítico que los agentes olvidan
- Failure mode con evidencia (sesión ID + fecha)

### 2. Determinar scope

**Preguntas clave:**
- ¿Esta directiva aplica a TODOS los proyectos que usarán el grafo?
  - **SÍ** → `scope: "global"`
  - **NO** → `scope: "project_specific"`

- Si project-specific: ¿A cuáles proyectos aplica?
  - Listar en `applicable_projects: ["proyecto1", "proyecto2"]`

### 3. Determinar severity

- **critical:** Violación causa pérdida de datos, downtime, o bloqueo de trabajo
- **high:** Violación causa errores graves pero recuperables
- **medium:** Violación causa degradación de calidad o deuda técnica

### 4. Determinar min_weight

**Guía:**
- `1.0` - Al menos 1 decision o 3 usages (principio consolidado)
- `0.7` - Al menos 2 usages (patrón reconocido)
- `0.3` - Al menos 1 usage (mencionado en sesión)

### 5. Agregar a VCM_DIRECTIVES

**Ubicación:** `humandato_queries.py` líneas 21-105

**Ordenar:**
- Primero todas las globales (agrupadas por categoría)
- Luego todas las project-specific (agrupadas por proyecto)

### 6. Sedimentar el concepto

**IMPORTANTE:** Agregar la vacuna al código NO es suficiente. El concepto debe existir en el grafo.

**Cómo sedimentar:**

1. Crear YAML en `concept-sediment/sessions/`:
   ```yaml
   concept_sediment:
     session_id: "YYYY-MM-DD-NNN-CodeCS"
     project: "inducop"  # o el proyecto aplicable
     domains_active:
       - workflow_protocols
     concepts:
       - name: "nombre descriptivo VCM nombre embebido"
         depth: principle  # Vacunas suelen ser principles
         domains:
           - workflow_protocols
         notes: >
           Directiva VCM (categoria: X, severity: Y, min_weight Z).
           
           [Describir la directiva completa]
     status: draft
   ```

2. Guardian revisa → cambia `status: reviewed`

3. Procesar con `bash scripts/process_session.sh sessions/archivo.yaml`

4. Verificar: `cs_search_concepts(query="nombre")` debe retornar el concepto con weight >= min_weight

### 7. Verificar efectividad

```python
# Consultar alertas
cs_get_alerts(project="proyecto-aplicable")

# La nueva vacuna NO debe aparecer en "missing_vaccines"
```

---

## Protocolo para Modificar Vacuna Existente

### Cambiar scope (global ↔ project-specific)

**Requiere análisis:** ¿Cambiar el scope invalida vacunas sedimentadas en otros proyectos?

**Ejemplo:** Si "delete()" cambia de global a project-specific["inducop"], entonces concept-sediment perdería protección.

**Protocolo:**
1. Verificar sedimentación actual: `cs_search_concepts(query="nombre-vacuna")`
2. Si está sedimentada en proyecto A pero se cambia a project-specific[B], sedimentar en B antes del cambio
3. Modificar VCM_DIRECTIVES
4. Deploy
5. Verificar: `cs_get_alerts(project="A")` y `cs_get_alerts(project="B")`

### Cambiar min_weight

**Safe:** Aumentar min_weight (más restrictivo)
**Riesgoso:** Disminuir min_weight (puede ocultar vacunas realmente faltantes)

**Protocolo:**
1. Verificar weight actual del concepto en grafo
2. Si weight actual < nuevo min_weight → sedimentar más ocurrencias primero
3. Modificar VCM_DIRECTIVES
4. Deploy

---

## Troubleshooting

### Vacuna reportada como faltante pero el concepto existe

**Diagnóstico:**
```python
cs_search_concepts(query="nombre-substring-de-vacuna")
```

**Causas comunes:**
1. **Weight insuficiente:** Concepto existe pero weight < min_weight
   - Solución: Sedimentar más ocurrencias (depth: usage o decision)

2. **Proyecto incorrecto (project-specific):** Concepto sedimentado en proyecto A, vacuna aplica a proyecto B
   - Solución: Sedimentar en proyecto B

3. **Status incorrecto:** Concepto está dormant o archived
   - Solución: Reactivar con nueva ocurrencia

4. **String match falla:** Nombre en grafo no contiene substring de vacuna
   - Ejemplo: Vacuna busca "YAML" pero concepto se llama "protocolo de cierre"
   - Solución: Cambiar nombre del concepto o cambiar "name" en VCM_DIRECTIVES

### Vacuna global no protege a todos los proyectos

**Verificar:**
```python
# ¿El código tiene scope correcto?
# humandato_queries.py línea correspondiente
"scope": "global"  # ← Debe ser "global", no "project_specific"
```

**Si scope es correcto:**
- Verificar deploy: `git log -n 1 --oneline` en concept-sediment-mcp
- Verificar Railway está corriendo versión nueva
- Reiniciar sesión MCP para reconectar

---

## Historial de Cambios

### 2026-04-24: Arquitectura project-agnostic
- Agregar campo `scope` (global | project_specific)
- Agregar campo `applicable_projects` para project-specific
- Migrar 5 vacunas a global, 2 a project-specific
- Modificar get_missing_vaccines() para lógica scope-aware
- Commit: 9060736 (concept-sediment-mcp)

### Pre-2026-04-24: Arquitectura original
- Todas las vacunas se verificaban por proyecto
- No había concepto de vacunas globales
- Duplicación necesaria: misma vacuna en cada proyecto

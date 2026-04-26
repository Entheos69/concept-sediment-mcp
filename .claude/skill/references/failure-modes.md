# Failure Modes Históricos del Sistema de Sedimentación

Incidentes documentados con síntoma, causa, ejemplo y mitigación. Agregar nuevos cuando se detecten.

---

## FM-1: Sobrescritura de archivos en sesiones largas

**Síntoma:** sesión larga (6+ horas) con múltiples fases conceptuales; conceptos de fase 1 desaparecen al cerrar fase 2.

**Causa:** `Write()` ejecutado 2+ veces con mismo `file_path` sobrescribe sin advertencia.

**Ejemplo:** S063 (24-mar-2026) — Fase 1 (8 conceptos) sobrescrita por Fase 2 (7 conceptos). Pérdida neta: 8 conceptos.

**Mitigación:** Protocolo Paso 1 detecta archivo existente con `ls` y usa sufijo automático (-a, -b, -c).

**Prevención:** nunca saltar el Paso 1 del protocolo de cierre.

---

## FM-2: YAML sin clave raíz `concept_sediment:` (COMÚN)

**Síntoma:** al procesar el YAML, error `Missing 'concept_sediment' root key`.

**Causa:** `Write()` genera estructura interna (session_id, project, concepts) pero omite el wrapper raíz.

**Ejemplos:** 5 YAMLs defectuosos marzo-abril 2026:
- 065 (2 versiones)
- 066
- 066a
- 072a

**Patrón detectado:**
```yaml
---
session_id: "..."  # ❌ FALTA concept_sediment: en línea 2
project: "..."
concepts:
  - ...
```

**Mitigación:**
- Paso 2 muestra ejemplo explícito con ANTI-PATTERN visible
- Paso 4 valida con `head -3` que línea 2 es `concept_sediment:`

**Prevención:** checklist de validación post-write incluye lectura de línea 2.

---

## FM-3: `depth` inválido (confusión depth vs type)

**Síntoma:** al procesar el YAML, error de validación en campo `depth`.

**Causa:** autor del YAML escribe un TYPE (`pattern`, `principle`, `event`) en el campo DEPTH.

**Ejemplo:** 066a (2 de abril 2026) — concepto con `depth: pattern` causó fallo de procesamiento.

**Patrón del error:**
```yaml
- name: "placeholders para extensibilidad"
  depth: pattern  # ❌ Esto es un type, no un depth
```

**Mitigación:** Paso 2.5 del protocolo valida con grep que todos los `depth` están en `{decision, usage, mention}`.

**Clarificación conceptual:**
- `depth` = CÓMO se usó (mention < usage < decision)
- `type` = QUÉ es (event/pattern/principle) — **inferido por el sistema**

Pregunta mnemotécnica al clasificar: *"¿Esto INFORMÓ una decisión, se APLICÓ en código, o solo se MENCIONÓ?"*

---

## FM-4: Pérdida de BD por tests Cloudinary

**Síntoma:** pérdida total de base de datos de producción.

**Causa raíz:** ejecución de tests que mockean Cloudinary pero tocan configuración de Django settings globales, causando que una operación "limpiadora" corra contra la BD de producción en vez de la de test.

**Ejemplo:** S76-S76a (fechas en MEMORY.md).

**Mitigación:**
- P3 Checkpoint: lista de tareas prohibidas sin autorización triple incluye:
  - ❌ Mockear Cloudinary en tests S7 (`test_rhito_integration.py`)
  - ❌ Validar 9 tests S7 RHito integration
- El solo hecho de que el Guardian mencione "Cloudinary" + "tests" dispara checkpoint obligatorio.

**Prevención:** nunca asumir que una autorización general cubre tareas de esta lista.

---

## FM-5: Ciclo de ejecución persistente ignorando interrupción

**Síntoma:** Code continúa ejecutando plan interno después de que el Guardian presionó ESC y dio nueva instrucción no relacionada.

**Causa:** Code mantiene estado interno del plan aunque el Guardian lo haya rechazado; en la siguiente respuesta, vuelve a mencionarlo o lo reanuda.

**Ejemplo:** S078 (2026-04-05) — ciclo casi replica pérdida de BD (S76). Detenido a tiempo por intervención manual.

**Mitigación:** P2 Zero-Tool-Calls Después de ESC + señales de ciclo persistente (auto-diagnóstico en [protocolos.md](protocolos.md)).

**Test de auto-diagnóstico (si TÚ detectas estos 4 patrones en tu propio comportamiento → PARAR):**
1. Creaste tareas/plan estructurado
2. Usuario usó ESC
3. Usuario da instrucción que NO menciona tu plan
4. TÚ mencionas el plan original en tu siguiente respuesta

---

## Cómo agregar nuevos failure modes

Estructura por FM:

```markdown
## FM-N: Título corto y descriptivo

**Síntoma:** qué observa el Guardian o el sistema cuando ocurre.

**Causa:** mecanismo que lo produce (no solo "qué pasó" sino "por qué").

**Ejemplo:** session ID + fecha + detalle cuantitativo si aplica.

**Mitigación:** qué cambió en el protocolo/skill/código para prevenirlo.

**Prevención:** qué debe hacer CodeCS (o el Guardian) para no repetirlo.
```

**Cuándo agregar:** cuando un incidente cumpla al menos uno de:
- Causó pérdida de datos o trabajo
- Repitió un patrón previo (indica mitigación insuficiente)
- Reveló un gap epistemológico (Code no sabía que no sabía)
- Fue detectado a tiempo pero solo por intervención manual

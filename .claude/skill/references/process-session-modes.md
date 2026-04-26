# process_session.sh — Modos de Ejecución

El script `process_session.sh` procesa YAMLs de sesión y regenera índices del grafo. Para evitar redundancia en procesamiento múltiple (fix de YAMLs, MCP reintentos, batch manual), soporta **modos de ejecución** con diferentes combinaciones de pasos.

---

## Pipeline conceptual completo

Cuando se procesa un YAML "de la manera completa", el script ejecuta cuatro fases:

1. **Extract** — parsea el YAML, agrega/actualiza conceptos en el grafo
2. **Decay** — aplica decay temporal a conceptos según type (event/pattern/principle)
3. **Fracturas** — recalcula alertas inmunológicas (conceptos debilitados con dependientes)
4. **CONCEPTOS** — regenera índices y archivos consolidados de `knowledge/`

Los modos del script controlan cuáles de estas fases se ejecutan.

---

## Tabla de modos

| Modo | Comando | Ejecuta | Caso de uso |
|------|---------|---------|-------------|
| **Default** | `./process_session.sh <yaml>` | Extract + Decay + Fracturas + CONCEPTOS | Primera sesión del día |
| **Fast** | `./process_session.sh --fast <yaml>` | Solo Extract | Procesamiento múltiple consecutivo |
| **Maintenance** | `./process_session.sh --maintenance` | Decay + Fracturas + CONCEPTOS | Después de batch con --fast |
| **Skip-decay** | `./process_session.sh --skip-decay <yaml>` | Extract + Fracturas + CONCEPTOS | Múltiples sesiones mismo día |
| **Batch** | `./process_session.sh --batch --all` | Default + sugerencias | Backlog de YAMLs reviewed |

---

## Workflow típico: múltiples YAMLs consecutivos

Cuando procesas varios YAMLs en pocos minutos (caso común tras una sesión larga con varias fases, o tras corregir YAMLs malformados en lote), las fases de Decay/Fracturas/CONCEPTOS son redundantes — su resultado solo importa al final.

```bash
# Primera sesión: pipeline completo
./process_session.sh sessions/2026-04-01-073-Code.yaml
# => Mantenimiento completo

# Segunda sesión (2 min después, usa --fast)
./process_session.sh --fast sessions/2026-04-01-074-Code.yaml
# => Solo extract (skip mantenimiento redundante)

# Tercera sesión (1 min después, usa --fast)
./process_session.sh --fast sessions/2026-04-01-075-Code.yaml
# => Solo extract

# Al terminar batch, ejecutar mantenimiento UNA VEZ
./process_session.sh --maintenance
# => Decay + Fracturas + CONCEPTOS con todos los conceptos procesados
```

**Ahorro:** 3 ejecuciones de decay/fracturas/CONCEPTOS → 1 ejecución final.

**Regla práctica:** si vas a procesar más de un YAML en menos de 10 minutos, usa `--fast` para todos menos el último, o usa `--fast` para todos y cierra con `--maintenance`.

---

## Sistema de checkpoint automático

El script guarda el timestamp de la última ejecución completa de mantenimiento en `.last_maintenance` y sugiere el modo apropiado automáticamente.

### Heurísticas activas

- Si última maintenance fue hace **< 5 minutos** + estás procesando 1 YAML → sugiere `--fast`
- Si hay **3+ YAMLs reviewed pendientes** sin procesar → sugiere `--batch --all`

### Ejemplo de sugerencia

```bash
$ ./process_session.sh sessions/2026-04-01-074-Code.yaml

💡 TIP: Última maintenance hace 127s. Considera usar --fast para skip redundante.
   Ejemplo: bash process_session.sh --fast sessions/2026-04-01-074-Code.yaml
```

El script no fuerza el modo sugerido — solo lo informa. Tú (o el Guardian) decides si seguir la sugerencia o ejecutar pipeline completo de todos modos.

---

## Cuándo usar cada modo (guía rápida)

**Default** — procesamiento normal. La primera vez del día, o tras varias horas sin actividad.

**Fast** — cuando vas a procesar otro YAML inmediatamente después y los efectos de decay/fracturas pueden esperar al final del lote.

**Maintenance** — al cerrar un batch que se procesó con `--fast`. Sin él, decay y fracturas quedarán desactualizados hasta el próximo procesamiento default.

**Skip-decay** — caso intermedio: quieres recalcular fracturas y CONCEPTOS pero ya aplicaste decay hoy y aplicarlo otra vez sería duplicar el efecto temporal. Útil cuando procesas múltiples sesiones del mismo día.

**Batch + all** — backlog grande. Procesa todos los YAMLs en `sessions/` con status `reviewed` que aún no se han ingerido. Útil tras varios días sin procesar o tras corregir múltiples YAMLs malformados en lote.

---

## Notas para CodeCS (mantenedor del script)

Si modificas `process_session.sh`:

- **El checkpoint `.last_maintenance` debe actualizarse solo en modos que ejecutan Decay** (Default, Maintenance, Skip-decay, Batch). El modo Fast NO debe tocarlo, sino su utilidad se pierde.
- **Las heurísticas de sugerencia (5 min, 3 YAMLs)** son arbitrarias y pueden necesitar ajuste según tu workflow real. No son principios duros.
- **Idempotencia es importante:** procesar el mismo YAML dos veces no debería duplicar conceptos. Verificar la lógica de Extract.
- **Orden de fases importa:** Decay debe ir antes de Fracturas (las fracturas se calculan sobre weights ya decaídos), y CONCEPTOS al final (consolida resultados).

**Referencia completa del script:** `concept-sediment/docs/PROCESS_SESSION_MODES.md` (en el repo).

# Concept-sediments — Directivas de Sesión

## Gates obligatorios (verificar ANTES de actuar)

### G1: Confirmar archivo antes de editar
ANTES de abrir cualquier archivo para edición:
1. Nombrar el archivo que vas a editar y POR QUÉ
2. Si el Guardian está presente, esperar confirmación
3. Si estás en modo autónomo, verificar que el archivo pertenece al módulo que se está trabajando

Razón: Patrón documentado — archivo equivocado en 34/56 sesiones.

### G2: No push sin test del módulo
ANTES de `git push` o `git add .`:
1. Ejecutar `pytest --nomigrations -x --timeout=30` en el módulo afectado
2. Si hay tests fallidos, NO pushear — reportar al Guardian
3. Si no existen tests para el cambio, declararlo explícitamente

Razón: Push sin validación ha causado rollbacks en producción.

### G3: Análisis previo a migración
ANTES de `makemigrations` o `migrate`:
1. Listar modelos afectados y campos que cambian
2. Verificar si hay datos existentes que se perderían
3. Presentar al Guardian antes de ejecutar

Razón: Migraciones destructivas son irreversibles en producción (PostgreSQL Railway).

## Protocolo de arranque

1. Leer este archivo (ya lo hiciste)
2. Leer `.claude/skill/SKILL.md` para stack y reglas técnicas
3. Si hay concept-sediment disponible, leer `CS_INSTRUCCIONES_CODE.md`
4. Declarar: qué módulo se va a trabajar, qué archivos se esperan tocar

## Restricciones ambientales

- Entorno virtual: `source C:/Users/ajmon/env/Scripts/activate`
- `staticfiles/` NO se commitea
- NO usar emojis en print()/logger (encoding Windows)
- Extensiones siempre minúsculas (.html, .css, .js)

## Señal del Guardian

Si el Guardian dice **"Sube un nivel"**: detente, identifica en qué capa estás operando (implementación → diseño → arquitectura → epistemología), y responde desde una capa arriba.

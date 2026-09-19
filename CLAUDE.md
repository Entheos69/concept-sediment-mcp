# Concept-sediments — Directivas de Sesión

## Encabezado de identidad (episteme-minimo, dir. 15)

Todo mensaje al Guardian empieza con una linea:

    Guardian > CodeMCP @<carpeta> HH:MM-06:00

- `<carpeta>`: nombre base de `pwd`, medido en ese turno.
- Hora, medida en ese turno con la forma portable (en Git Bash de Windows `TZ=America/Mexico_City` falla sin avisar y da UTC):
  `t=$(TZ=America/Mexico_City date +%H:%M%:z); [ "${t#*-}" = "06:00" ] || t=$(date +%H:%M%:z); echo "$t"`
  Nunca copiar la del mensaje anterior.
- Solo en chat. Nunca en archivos, commits, PR, YAML, SOL/HANDOFF ni codigo.
- Canon: `docs_inducop/organizacion/SKILL_minimo.md`, directiva 15.

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

- Entorno virtual: ver "Entorno virtual (regla F77)" abajo (fuente única).
- `staticfiles/` NO se commitea
- NO usar emojis en print()/logger (encoding Windows)
- Extensiones siempre minúsculas (.html, .css, .js)

## Entorno virtual (regla F77)

- Mi entorno: `source C:/Users/ajmon/proyectos/concept-sediment-mcp/venv/Scripts/activate`
- NO crear, mover ni borrar entornos virtuales sin autorización del Guardian (dir. 5).
  Un venv no es reubicable: moverlo lo rompe; se recrea, no se mueve.
- Python real en Windows: `C:/Python314/python`. `python3` es el alias de la Microsoft Store: no usarlo.
- Si tras activar, `which python` no apunta a mi entorno: parar y avisar al Guardian.
- Deps de dev (para correr la suite) en `requirements-dev.txt`, NO en `requirements.txt` (runtime):
  `venv/Scripts/python -m pip install -r requirements-dev.txt` (trae pytest + pytest-timeout para `--timeout=30`).

## Entorno Python
- Intérprete del proyecto: `$CLAUDE_PROJECT_PY` (exportado por el launcher de Git Bash).
  Si la variable está vacía, usar la ruta literal: `venv/Scripts/python.exe`.
- Nunca `python` ni `pip` a secas: el shell de la herramienta resuelve al Python global.
- Instalar: `"$CLAUDE_PROJECT_PY" -m pip install <paquete>`.
  Con uv: `uv pip install --python "$CLAUDE_PROJECT_PY" <paquete>`.
- Primera acción de cada sesión: `echo "$CLAUDE_PROJECT_PY"` y `command -v python`;
  si difieren, usar siempre la primera.

## Señal del Guardian

Si el Guardian dice **"Sube un nivel"**: detente, identifica en qué capa estás operando (implementación → diseño → arquitectura → epistemología), y responde desde una capa arriba.

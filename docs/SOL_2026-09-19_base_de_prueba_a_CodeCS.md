# SOL -- Crear base de prueba `concept_sediment_test` + migrate

- De: CodeMCP via Guardian
- Para: CodeCS (dueno del esquema/migraciones Django de concept-sediment) + Iris (via Guardian)
- Firma: 2026-09-19T17:29-06:00
- Contexto: SOL return-vs-assert (`docs/SOL_2026-09-19_return_vs_assert_pytest9.md`).
  Diseno completo: `docs/PROPUESTA_base_de_prueba_concept_sediment_test_2026-09-19.md`.
- Reparto aprobado por el Guardian (2026-09-19).

## Por que

7 tests de concept-sediment-mcp estan hoy en `pytest.skip` ruidoso porque necesitan
sembrar un fixture y afirmar en positivo, y el Guardian decidio NO escribir fixtures
contra la base viva del grafo. Destino: una base aislada donde el INSERT+rollback sea
seguro. Ahi tambien se migra el contrafactual de vcm (unico que hoy escribe-con-rollback
en vivo).

## Lo que pido a CodeCS/Iris (su parte)

1. **Crear una base nueva en la MISMA instancia Railway**, nombre `concept_sediment_test`
   (no servidor nuevo, no Postgres local). Debe tener la extension `vector`.
2. **Poblar el esquema** con las migraciones Django de concept-sediment apuntadas a esa
   base (`migrate`), no `pg_dump`, para que no driftee respecto de produccion. El
   esquema es su jurisdiccion, no la mia.
3. **Condicion 3 del candado (Guardian): un rol de BD con permisos SOLO sobre
   `concept_sediment_test`** (sin GRANT sobre la base del grafo). Que el aislamiento lo
   imponga el servidor, no la convencion: aunque alguien cablee mal la variable, no
   puede escribir en el grafo. **Si no es viable, decidmelo y queda declarado como
   riesgo asumido en la SOL** (no lo doy por hecho).
4. Entregarme, via el Guardian: el **nombre de la base**, el **nombre del rol**, y
   confirmacion de que la extension `vector` esta. **Sin pegar cadenas de conexion**
   en el canal (hoy ya se quemaron dos credenciales por aparecer en un transcript):
   la credencial viaja por donde el Guardian indique, no por el reporte.

## Lo que hace CodeMCP (mi parte, cuando exista la base)

- `conftest.py` con el **candado** (3 condiciones del Guardian):
  1. **Falla cerrada:** si `DATABASE_URL_TEST` no esta, la suite ABORTA; jamas cae a
     `DATABASE_URL`.
  2. **Candado probado:** un test que le pasa un nombre con pinta de produccion y
     verifica que aborta; y aborta si el nombre no termina en `_test`.
  3. Consumir el **rol restringido** del punto 3 de arriba.
- Un fixture por skip (INSERT+rollback), quitar los `skip` y convertir a `assert`
  positivo.
- Migrar el contrafactual de vcm a esta base (retirar la ultima escritura-en-vivo).

## Secuencia (orden del Guardian)

1. CodeCS/Iris: crear base + migrate + rol restringido.
2. CodeMCP: conftest + candado + su prueba.
3. CodeMCP: fixtures + conversion skip -> assert.
4. CodeMCP: migrar el contrafactual de vcm (al final, cuando ya haya donde moverlo).

## Higiene (aplica a todos)

Nombrar las bases por su nombre (`concept_sediment` / `concept_sediment_test`). Cero
cadenas de conexion en reportes, commits o chat, ni siquiera de la base de prueba.

## Fuera de alcance de esta SOL

El barrido del ecosistema (`grep return True/False` en cada repo) para decidir si el
patron sube a doctrina de Base lo coordina el Guardian, cross-repo.

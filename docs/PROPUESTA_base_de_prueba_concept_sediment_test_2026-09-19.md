# Propuesta -- base de prueba `concept_sediment_test` (misma instancia Railway)

- De: CodeMCP via Guardian
- Para: Guardian; CC CodeCS (dueno del esquema/migraciones), Iris (via Guardian)
- Firma: 2026-09-19T17:21-06:00
- Origen: decision del Guardian sobre la SOL return-vs-assert (metodo (b) fixture con
  rollback, pero NO contra la base viva). Destino de los 7 skips ruidosos actuales.

## 1. Objetivo

Una base aislada donde los tests que hoy hacen `pytest.skip` puedan **sembrar su
fixture con INSERT+rollback y afirmar en POSITIVO**, sin tocar el Postgres que sirve
el grafo. Cuando exista, se migra ahi tambien el contrafactual de vcm (hoy el unico
que escribe-con-rollback en vivo): no dejar el precedente de escritura en vivo.

## 2. Que necesita el esquema

- **Una base nueva en la MISMA instancia Railway** (no un servidor nuevo, no Postgres
  local): `CREATE DATABASE concept_sediment_test;`. Mismo motor, misma version,
  `pgvector` ya disponible.
- **El esquema identico al de produccion.** Tablas que tocan los tests:
  `graph_concept`, `graph_conceptrelation`, `graph_concept_domains`, `graph_domain`,
  `graph_vcmdirective`, `graph_measurement`, `graph_sessionlog`, `mcp_audit_log`, y la
  extension `vector`. Dos vias:
  - (a) `pg_dump --schema-only` de `concept_sediment` -> `psql` a `concept_sediment_test`
    (rapido; foto puntual del esquema).
  - (b) apuntar las migraciones Django del repo `concept-sediment` (dueno: CodeCS) a
    la base test y correr `migrate` (canonico; se mantiene en sync por el mismo
    mecanismo que produccion). **Recomendada (b)** para no driftear.
- **Verificar que no haya triggers con efecto externo** al clonar (aunque, por estar
  aislada, un trigger actuaria sobre la base test, no sobre prod).

## 3. Como se siembra

- **conftest.py** en la raiz del repo con fixtures pytest que INSERTAN el fixture y
  hacen `rollback` al final de cada test (ya seguro: base aislada). Fixtures minimos,
  uno por skip actual:
  | Test hoy en skip | Fixture a sembrar |
  |---|---|
  | nodo t1/t3 (nodo A del handoff) | nodo A `active` + nodo B `active` con arista `contradicts` B->A |
  | nodo t4 (canal ancho) | un concepto `active` en project `concept-sediment` con `contradicts` entrante |
  | frontera H2 (depth) | un concepto con relaciones a >=2 saltos |
  | frontera H3 (lexico) | un concepto cuyo nombre/desc matchee un token de control |
  | frontera H6 (recorte) | >=6 conceptos `active` en project `concept-sediment-mcp` |
  | vacunas t3 (decaido) | un concepto `status=dormant` de control |
  | smoke t5 (E2E) | una fila `graph_sessionlog` con `is_test=True` + su discard |
- Los fixtures viven en el conftest, no en los tests: una sola fuente (dir. 7).
- Semilla determinista: nombres `zzz-fixture-*` reservados, para no colisionar con
  datos reales aunque la base test se poblara alguna vez.

## 4. Como se cablea -- el CANDADO (pieza no-negociable, 3 condiciones del Guardian)

- Nueva env var **`DATABASE_URL_TEST`** (solo local/CI, apuntando a la base
  `concept_sediment_test`), NUNCA en el servicio `mcp-server` de Railway.
- **conftest.py** al iniciar la sesion de pytest apunta `db` a `DATABASE_URL_TEST`
  (exporta `DATABASE_URL=$DATABASE_URL_TEST` antes de construir el engine, o resetea
  `db._engine`). El candado tiene tres condiciones:

  1. **Falla cerrada.** Si `DATABASE_URL_TEST` NO esta definida, la suite **aborta**
     (`pytest.exit`/error de coleccion). JAMAS cae a `DATABASE_URL`. Un fallback
     silencioso a produccion es justo el modo de falla que esto previene. (Esto
     REVIERTE la version anterior de este doc, que degradaba a skip: descartada.)
  2. **El candado se prueba.** Un test dedicado le pasa un nombre de base con pinta de
     produccion (p.ej. `.../concept_sediment`) y verifica que el guard **aborta**.
     Ademas: abortar si el nombre de base NO termina en `_test`. Un guard sin prueba es
     otro verde que no mide.
  3. **Aislamiento impuesto por el servidor, no por convencion.** Pedir a CodeCS/Iris
     un **rol de BD con permisos solo sobre `concept_sediment_test`** (sin GRANT sobre
     `concept_sediment`). Asi, aunque alguien cablee mal la variable, el servidor
     rechaza cualquier escritura al grafo. Si no es viable, queda declarado como
     **riesgo asumido** en la SOL.

## 5. Costo

- **Infra:** cero servicios nuevos; una base logica extra en la instancia existente.
  Storage de fixtures: trivial (KB). pgvector ya pagado.
- **Trabajo:** clonar esquema (via migrate), escribir conftest + 7 fixtures, quitar
  los `skip` y convertir a `assert` positivo, migrar el contrafactual de vcm.
  Estimado: una sesion enfocada.
- **Mantenimiento:** mantener el esquema test en sync con las migraciones de prod
  (resuelto si se usa la via (b)/migrate).
- **Riesgo a prod:** nulo si el candado anti-prod (nombre `*_test`) esta en el
  conftest. Ese candado es la pieza no-negociable.

## 6. Cruce de perimetros (a coordinar por el Guardian)

- **Crear la base y correr migrate** es operacion de infra/esquema: la base la crea
  Iris (mediada) o CodeCS; el esquema lo gobiernan las migraciones Django del repo
  `concept-sediment` (dueno CodeCS). CodeMCP no crea bases ni corre migraciones de
  otro repo por su cuenta (Flujo Tripartito).
- **CodeMCP hace** el conftest, los fixtures, el candado anti-prod y la conversion de
  los tests en su repo, una vez que `concept_sediment_test` exista y
  `DATABASE_URL_TEST` este disponible.
- Propuesta de reparto para tu visto bueno: SOL de CodeMCP -> CodeCS/Iris para
  (crear base + migrate); CodeMCP ejecuta el resto.

## 7. Estado interino (hoy, ya en main)

Los 7 casos data-dependientes estan en `pytest.skip` RUIDOSO con motivo que nombra el
fixture ausente; listados en la SOL. La suite reporta `20 passed, 7 skipped` -- no
falso verde, no falso rojo. El blindaje `filterwarnings=error::PytestReturnNotNoneWarning`
ya impide que el patron reingrese.

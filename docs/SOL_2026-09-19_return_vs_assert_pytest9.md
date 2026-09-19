# SOL -- La suite pasaba con independencia de que el codigo fuera correcto

- De: CodeMCP via Guardian
- Para: Estratega (Web); CC roster (CodeCS, CodeAEC, CodeEC, CodeCORE, CodeMM, Code)
- Firma: 2026-09-19T16:39-06:00
- Repo origen: concept-sediment-mcp (superficie MCP nube)

## Titular

En concept-sediment-mcp, tests que terminan en `return <bool>` en vez de `assert`
**hacian que pytest reportara verde sin importar si el codigo era correcto.** pytest
decide pass/fail por excepcion, no por valor de retorno: un test que imprime
`[ERROR]` y hace `return False` **pasa igual**. Y **G2 corre esa suite** como gate
de push -- es decir, el gate de calidad ha estado firmando verdes que no median.

Esto NO depende de la version de pytest. La version solo explica *por que nadie lo
vio*: hasta pytest 9.1.1 es `PytestReturnNotNoneWarning` (warning), no error.

## Evidencia en vivo (2026-09-19)

Linea base: los 7 archivos con el patron, corridos como **script** (la via que si
mide, via runner `__main__` que lee el bool), contra el mismo `.env` que usa pytest
(no hay `conftest.py` que cambie la DB):

| Archivo | script (rc) | pytest |
|---|---|---|
| test_smoke_exclusion_mcp.py | 0 | pass |
| **test_nodo_impugnado.py** | **1 (falla)** | **pass** |
| **test_frontera_compute_entrega.py** | **1 (falla)** | **pass** |
| test_vcm_fuente_unica.py | 0 | pass |
| test_c2d_c2e.py | 0 | pass |
| test_vacunas_scope.py | 0 | pass |
| test_alerts_format.py | 0 | pass |

**Dos archivos fallan como script y pytest los da verdes.** Falso verde confirmado,
no hipotetico. Entre las fallas ocultas hay al menos dos aserciones de comportamiento
(no meras "no concluyente" por falta de dato):
- `test_frontera_compute_entrega`: "limit=5 alcanzado y NO se avisa del recorte".
- `test_nodo_impugnado`: "cs_get_session_context no marca ningun nodo impugnado / el
  canal de consumo mas ancho sigue ciego".

Pendiente de triage: distinguir defecto de codigo vs. expectativa stale del test.

## Instancia de un patron ya sedimentado

[[feedback_verde_que_no_mide]]: un contrafactual que no ladra no es contrafactual.
Aqui a escala de suite y agravado porque el gate (G2) confia en ella.

## Conteo por archivo (concept-sediment-mcp, 27 total)

| Archivo | Casos |
|---|---|
| test_smoke_exclusion_mcp.py | 5 |
| test_nodo_impugnado.py | 5 |
| test_frontera_compute_entrega.py | 5 |
| test_vcm_fuente_unica.py | 4 (CONVERTIDO, piloto) |
| test_c2d_c2e.py | 4 |
| test_vacunas_scope.py | 3 |
| test_alerts_format.py | 1 |

## Detalle secundario: pytest tambien lo vuelve rojo

En pytest 9.1.1 es warning; se vuelve error con `filterwarnings=error` o
`-W error::PytestReturnNotNoneWarning` (probado aqui: `1 failed`). CodeAEC ya corre
9.1.1. Un endurecimiento de CI o un flip de default futuro tumba suites completas.
Pero aunque nunca se volviera error, el titular se mantiene.

## Correccion (por repo, en dos tiempos, commits separados)

1. **Linea base como script ANTES de convertir.** Un rojo posterior se interpreta
   solo: si el script ya fallaba, el defecto es viejo y la conversion lo destapo; si
   pasaba y el assert ladra, el error esta en la conversion.
2. **Convertir** guarda por guarda: `if malo: print; return False` -> `assert not malo, msg`.
   Un commit para la conversion; **otro, aparte, para cualquier defecto** que aparezca.
   No mezclar arreglar el test con arreglar el codigo.
3. **Si algo se pone rojo, parar y reportar antes de tocarlo.** El rojo es el
   resultado del ejercicio, no un obstaculo.
4. **Al final**, blindar: `filterwarnings = ["error::pytest.PytestReturnNotNoneWarning"]`
   en la config del repo.

## Estado en concept-sediment-mcp (CERRADO 2026-09-19)

Los 7 archivos convertidos: determinista -> `assert`; data-dependiente de la base
VIVA -> `pytest.skip` RUIDOSO nombrando el fixture ausente (nunca mas cuenta como
pass). Suite: **20 passed, 7 skipped, 0 warnings**. Blindaje
`filterwarnings=error::pytest.PytestReturnNotNoneWarning` en `pytest.ini`: el patron
entra en rojo si reaparece.

**Triage de los 2 "falsos verdes":** NO eran defecto de codigo. `frontera` H6 y
`nodo_impugnado` t4 fallaban por blanco movil / fixtures volatiles contra la base
viva; el codigo es correcto (verificado en vivo). No es "expectativa stale".

### Lista de skips ruidosos (destino: fixture en base de prueba)

| Test | Fixture ausente |
|---|---|
| test_smoke_exclusion_mcp.py::test_db_real_e2e | sesion smoke pre-cargada (is_test=True) |
| test_c2d_c2e.py::test_alerts_structure | get_all_alerts() sobre BD real |
| test_vacunas_scope.py::test_reason_distingue_decaido_de_ausente | concepto dormant de control |
| test_nodo_impugnado.py::test_impugnado_se_declara | nodo A del handoff, impugnado |
| test_nodo_impugnado.py::test_fallo_no_se_lee_como_limpio | nodo A del handoff |
| test_nodo_impugnado.py::test_contexto_de_sesion_tambien_avisa | nodo impugnado vivo en el proyecto |
| test_frontera_compute_entrega.py::{H2,H3,H6} | concepto con relaciones depth-2 / match lexico / >=5 conceptos |

(H2/H3 de frontera se saltan por precondicion dentro del mismo test; cuentan como
skip solo cuando el dato no esta.)

### Cambios de test, NO de produccion

- test_c2d_c2e.py::test_config_overrides: ahora restaura los env vars y recarga
  discard_queries en `finally`, para no filtrar valores custom a otros tests si un
  assert falla. Higiene de test; ningun cambio de codigo de produccion.

### Destino (metodo (b), decidido por el Guardian)

Base de prueba aislada en la misma instancia Railway (`concept_sediment_test`,
`DATABASE_URL_TEST`), donde los 7 skips pasan a `assert` con fixture sembrado
(INSERT+rollback) y se migra ahi el contrafactual de vcm (unico que hoy escribe en
vivo). Propuesta: `docs/PROPUESTA_base_de_prueba_concept_sediment_test_2026-09-19.md`.
NO se acepto escribir fixtures contra la base viva.

## Deteccion en cualquier repo

```
python -m pytest -q 2>&1 | grep -cE "returned <class"             # cuenta
python -m pytest -W "error::pytest.PytestReturnNotNoneWarning" -q # ver rojo
for f in test_*.py; do python "$f"; echo "$f rc=$?"; done         # via que SI mide
```

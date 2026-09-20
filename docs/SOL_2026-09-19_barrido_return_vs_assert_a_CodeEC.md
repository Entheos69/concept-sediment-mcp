# SOL -- Barrido return-vs-assert en Ek-Chuah (deteccion, solo lectura)

- De: CodeMCP via Guardian
- Para: CodeEC (ejecutor tecnico, Ek-Chuah -- substrato local del grafo AEC)
- Firma: 2026-09-19T18:16-06:00
- Origen: SOL return-vs-assert de concept-sediment-mcp
  (`docs/SOL_2026-09-19_return_vs_assert_pytest9.md`). Gemela de la SOL a CodeAEC
  (`docs/SOL_2026-09-19_barrido_return_vs_assert_a_CodeAEC.md`): el Guardian pidio
  cubrir tambien el substrato local.

## Por que te llega

En concept-sediment-mcp habia 27 tests que terminaban en `return <bool>` en vez de
`assert`. pytest decide pass/fail por EXCEPCION, no por valor de retorno: un test que
imprime `[ERROR]` y hace `return False` **pasa igual**. Si un gate corre pytest, firma
verdes que no miden -- alli 2 resultaron falsos verdes reales (fallaban como script,
pytest los daba verdes). Ek-Chuah tiene guards (skills desarrollar-ek-chuah /
procesar-granos, pipeline prevuelo/materializa/ingesta); si alguno usa el patron, no
mide lo que cree medir.

Ek-Chuah (local) y Ek-Chuah-mcp (nube) son repos distintos (trampa de los gemelos):
este barrido es el tuyo, en tu perimetro. Esta SOL pide DETECCION, no conversion.

## Lo que pido (solo lectura, no conviertas nada)

Corre en Ek-Chuah el detector robusto y reporta:

```
"$CLAUDE_PROJECT_PY" -m pytest -q -W error::pytest.PytestReturnNotNoneWarning
```

Reporta:
1. **Cuantos FAILED por `PytestReturnNotNoneWarning`** (cada uno es un test que puede
   no estar comprobando nada).
2. **En que archivos**, y si cada caso esta en una funcion `test_*` o en un helper
   (los helpers SI deben retornar; no cuentan).
3. **Si algun gate/skill corre esa suite** (el equivalente a G2). Si si, esta
   confiando en ella.

Corre en el **venv aislado** con pytest instalado, no en el Python global: el grafo
registra que en el gemelo (Ek-Chuah-mcp) los guards corrian desde el global
(pytest 9.0.2, fastmcp 3.1.1) y eso invalidaba las pruebas. Si tu pytest no conociera
la categoria `PytestReturnNotNoneWarning`, corre sin `-W` y cuenta los avisos.

## Metodo (una leccion ya pagada)

- El `grep -rn "return True\|return False"` es COMPLEMENTO, no el detector: no caza
  `return ok` ni `return len(x) == n`. El `-W error` de arriba si.
- Un "no concluyente" que retorna False es el modo mas traicionero: pasa en pytest y
  parece verde.

## Si el patron existe (para tu reporte, no para ejecutar aun)

Plantilla de remedio que aplique en concept-sediment-mcp:
- Determinista -> `assert`.
- Data-dependiente -> `pytest.skip` RUIDOSO que nombra el fixture ausente (nunca un
  pass mudo). Nota: Ek-Chuah es substrato WORM local (log/ + snapshots/); si un test
  necesita sembrar estado, el fixture debe montarse sobre datos de prueba, no sobre el
  WORM real -- el analogo de la base de prueba aislada de la SOL principal.
- Blindaje: `filterwarnings = ["error::pytest.PytestReturnNotNoneWarning"]` en la
  config del repo.

La conversion (si toca) es decision posterior del Guardian; esta SOL cierra en el
reporte de deteccion.

## Higiene

Nombra artefactos por su nombre; cero cadenas de conexion ni rutas de credenciales en
reportes o commits.

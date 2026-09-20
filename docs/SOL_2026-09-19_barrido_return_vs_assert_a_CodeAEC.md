# SOL -- Barrido return-vs-assert en Ek-Chuah-mcp (deteccion, solo lectura)

- De: CodeMCP via Guardian
- Para: CodeAEC (lector/custodio nube, Ek-Chuah-mcp)
- Firma: 2026-09-19T18:14-06:00
- Origen: SOL return-vs-assert de concept-sediment-mcp
  (`docs/SOL_2026-09-19_return_vs_assert_pytest9.md`). El Guardian pidio replicar el
  barrido en el gemelo nube (simetria CodeMCP<->CodeAEC).

## Por que te llega

En concept-sediment-mcp habia 27 tests que terminaban en `return <bool>` en vez de
`assert`. pytest decide pass/fail por EXCEPCION, no por valor de retorno: un test que
imprime `[ERROR]` y hace `return False` **pasa igual**. El gate G2 corre pytest, o sea
que el gate firmaba verdes que no median -- y 2 resultaron falsos verdes reales
(fallaban como script, pytest los daba verdes). Tu venv ya corre **pytest 9.1.1**
(medido esta tanda), asi que la categoria del detector existe en tu repo.

Ek-Chuah-mcp es otro servicio/repo (trampa de los gemelos): el barrido es tuyo, en tu
perimetro. Esta SOL pide DETECCION, no conversion.

## Lo que pido (solo lectura, no conviertas nada)

Corre en Ek-Chuah-mcp el detector robusto y reporta:

```
"$CLAUDE_PROJECT_PY" -m pytest -q -W error::pytest.PytestReturnNotNoneWarning
```

Reporta:
1. **Cuantos FAILED por `PytestReturnNotNoneWarning`** (cada uno es un test que puede
   no estar comprobando nada).
2. **En que archivos**, y si cada caso esta en una funcion `test_*` o en un helper
   (los helpers SI deben retornar; no cuentan).
3. **Si tu gate corre esa suite** (equivalente a G2). Si si, el gate esta confiando en
   ella.

Si tu pytest no conociera la categoria, corre sin `-W` y cuenta los avisos
`PytestReturnNotNoneWarning`.

## Metodo (una leccion ya pagada)

- El `grep -rn "return True\|return False"` es COMPLEMENTO, no el detector: no caza
  `return ok` ni `return len(x) == n`. El `-W error` de arriba si.
- Un "no concluyente" que retorna False es el modo mas traicionero: pasa en pytest y
  parece verde.

## Si el patron existe (para tu reporte, no para ejecutar aun)

El remedio que aplique en concept-sediment-mcp, por si sirve de plantilla:
- Determinista -> `assert`.
- Data-dependiente de la base viva -> `pytest.skip` RUIDOSO que nombra el fixture
  ausente (nunca un pass mudo), con destino a una base de prueba aislada
  (INSERT+rollback) y candado FALLA-CERRADA. Ver
  `docs/PROPUESTA_base_de_prueba_concept_sediment_test_2026-09-19.md`.
- Blindaje: `filterwarnings = ["error::pytest.PytestReturnNotNoneWarning"]` en la
  config del repo, para que el patron entre en rojo apenas reaparezca.

La conversion (si toca) es decision posterior del Guardian; esta SOL cierra en el
reporte de deteccion.

## Contexto que quiza ya conozcas

El grafo tiene eventos de tu repo de esta tanda: "pytest es dev-only y no vive en el
pineo runtime de Ek-Chuah-mcp..." y "el interprete global de Python driftea del deploy
pineado: los guards de Ek-Chuah-mcp corrian sobre fastmcp 3.1.1...". Corre el detector
en el venv aislado (con pytest instalado), no en el global.

## Higiene

Nombra bases y servicios por su nombre; cero cadenas de conexion en reportes o commits.

## Adyacente (para el Guardian, no en esta SOL)

CodeEC / Ek-Chuah (substrato local, gemelo de CodeAEC) es el siguiente candidato
natural del barrido. Queda a criterio del Guardian levantar esa SOL por separado.

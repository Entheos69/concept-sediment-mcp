# SOL -- Tests que retornan en vez de afirmar: verdes posiblemente falsos

- De: CodeMCP via Guardian
- Para: Estratega (Web); CC roster (CodeCS, CodeAEC, CodeEC, CodeCORE, CodeMM, Code)
- Firma: 2026-09-19T16:20-06:00
- Repo origen: concept-sediment-mcp (superficie MCP nube)

## Que pido (el argumento real, primero)

Barrer en todo el roster el patron **`def test_*` que termina en `return <valor>` en
lugar de `assert`.** Un test que retorna en vez de afirmar **puede no estar
comprobando nada**: si la logica falla, el test igual "pasa" mientras el `return` no
sea None. En concept-sediment-mcp hay **27 casos hoy en verde, y no sabemos cuantos
de esos verdes son falsos** hasta revisarlos uno por uno.

Esto **no depende de la version de pytest.** Es correccion de calidad de test:
verificar que cada caso realmente afirme, no que retorne. Instancia directa de
[[feedback_verde_que_no_mide]] -- un verde que no mide no es evidencia.

## Lo secundario: pytest tambien lo va a volver rojo

Ademas del riesgo silencioso de arriba, el patron es fragil ante la herramienta:

- **En pytest 9.1.1 es warning** (`PytestReturnNotNoneWarning`); la suite pasa.
  **Se vuelve error con `filterwarnings=error` o `-W error::PytestReturnNotNoneWarning`.**
  Probado en este repo: `pytest -W error::pytest.PytestReturnNotNoneWarning
  test_alerts_format.py` -> `1 failed`.
- CodeAEC ya corre 9.1.1. Si el patron vive en mas repos, un endurecimiento de CI
  (warnings-as-errors) o un flip de default futuro tumba suites completas de golpe.

Pero aunque pytest nunca lo volviera error, el punto de arriba se mantiene: hay que
saber cuantos de los 27 comprobaban algo.

## Conteo por archivo (concept-sediment-mcp, 27 total)

| Archivo | Casos |
|---|---|
| test_smoke_exclusion_mcp.py | 5 |
| test_nodo_impugnado.py | 5 |
| test_frontera_compute_entrega.py | 5 |
| test_vcm_fuente_unica.py | 4 |
| test_c2d_c2e.py | 4 |
| test_vacunas_scope.py | 3 |
| test_alerts_format.py | 1 |

## Correccion propuesta (por repo, en dos tiempos)

1. **Revisar antes de convertir.** Por cada caso, distinguir:
   - `return <cond>` donde `<cond>` era una comprobacion real que solo faltaba
     afirmar -> conversion mecanica a `assert <cond>`.
   - `return` que no comprobaba nada (prints sin assert, o valor irrelevante) ->
     **hallazgo, no mecanica**: ese verde nunca probo nada; escribir la afirmacion
     que faltaba y validar que ahora puede ladrar.
2. Re-correr la suite; verde real.
3. **Blindar la regresion:** `filterwarnings = ["error::pytest.PytestReturnNotNoneWarning"]`
   en la config del repo, para que el patron entre en rojo desde ya.

## Alcance / jurisdiccion

- concept-sediment-mcp: CodeMCP ejecuta la correccion en su repo bajo G1/G2.
- Otros repos: cada custodio en el suyo. Esta SOL levanta el patron, el argumento y el
  metodo de deteccion; la ejecucion es local.

## Como detectarlo en cualquier repo

```
python -m pytest -q 2>&1 | grep -cE "returned <class"             # cuenta
python -m pytest -W "error::pytest.PytestReturnNotNoneWarning" -q # ver rojo
```

"""
Tests del nodo impugnado invisible al canal de lectura.
HANDOFF CodeCS -> CodeMCP, 2026-07-16.

Forma: la `description` de un nodo sale SOLO del YAML que lo DECLARA; la
enmienda de quien lo corrige vive en la ARISTA. El camino de busqueda nunca
tocaba graph_conceptrelation, asi que un nodo con `contradicts` entrante se
servia como incolume — con la description falsa intacta y la correccion muda.

NO es la forma de test_frontera_compute_entrega.py ("calcula el dato correcto y
lo pierde"): alli el dato existia y se tiraba en la entrega. Aqui NUNCA se
calculaba. Bug opuesto, remedio opuesto — por eso vive en su propio archivo.

Contrato que se verifica (tres valores, nunca null):
    False         -> se pregunto, esta limpio
    {by_active..} -> se pregunto, hay disputa
    {error: ...}  -> NO se pudo preguntar

Requiere BD (lectura pura). NO escribe.

Estado (SOL return-vs-assert, 2026-09-19): las pruebas que dependen de un fixture
volatil en la base VIVA (nodo A del handoff; presencia de un nodo impugnado) hacen
`pytest.skip` RUIDOSO nombrando el fixture ausente, en vez de retornar bool (que
pytest ignoraba -> falso verde). Migraran a `assert` con fixture sembrado cuando
exista la base de prueba (concept_sediment_test). Las que fuerzan su propio estado
(contrafactual del canal ciego, oraculo de nodo limpio) SI afirman.
"""
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402
import queries  # noqa: E402
from sqlalchemy import text as _sql  # noqa: E402

# El caso real que origino el handoff: nodo A (active) impugnado por nodo B
# (active) con `contradicts`. Su description afirma un exit 0 que nunca ocurre.
FRAGMENTO_NODO_A = "exit 0 vuelve el fallo indistinguible"


def _oraculo_limpio():
    """Un concepto activo SIN impugnacion entrante, hallado por SQL propio.

    Deliberadamente NO usa _fetch_contested: si el test tomara su control de la
    misma funcion que audita, se validaria a si misma. El oraculo es
    independiente.
    """
    session = db.get_session()
    try:
        row = session.execute(_sql("""
            SELECT c.name FROM graph_concept c
            WHERE c.status = 'active'
              AND NOT EXISTS (
                  SELECT 1 FROM graph_conceptrelation r
                  WHERE r.target_id = c.id
                    AND r.relation_type IN ('contradicts', 'supersedes')
              )
            ORDER BY c.weight DESC LIMIT 1
        """)).fetchone()
        return row.name if row else None
    finally:
        session.close()


def test_impugnado_se_declara():
    """El nodo con retador VIVO debe llegar marcado por el canal de busqueda.

    DATA-DEPENDIENTE: exige el nodo A del handoff vivo e impugnado. SKIP hasta
    fixture en base de prueba (ver SOL return-vs-assert).
    """
    res = queries.search_concepts_by_text(FRAGMENTO_NODO_A, limit=3)
    if not res:
        pytest.skip(
            f"fixture ausente: nodo A del handoff ('{FRAGMENTO_NODO_A}') no esta "
            "en el grafo vivo. Requiere sembrar nodo A impugnado por B en base de "
            "prueba. Ver SOL return-vs-assert."
        )

    nodo = res[0]
    flag = nodo.get("contested", "AUSENTE")

    assert flag != "AUSENTE", "el resultado no trae el campo `contested`"
    assert flag is not False, (
        "nodo con contradicts entrante servido como LIMPIO (el bug del handoff, intacto)"
    )
    assert isinstance(flag, dict) and flag.get("by_active"), (
        f"impugnacion viva no declarada en by_active: {flag!r}"
    )

    print(f"  [OK] '{nodo['name'][:60]}...'")
    print(f"  [OK] contested.by_active = {flag['by_active']}")
    print("  [OK] quien BUSCA ya recibe la senal que antes solo veia quien NAVEGA")


def test_limpio_no_se_marca():
    """CONTRAFACTUAL: un nodo sin impugnacion debe dar False.

    Sin esta mitad, una bandera encendida SIEMPRE pasaria el test de arriba y
    el verde no mediria nada. Un contrafactual que no ladra no es contrafactual.
    """
    nombre = _oraculo_limpio()
    if not nombre:
        pytest.skip(
            "fixture ausente: el oraculo no hallo ningun concepto activo limpio "
            "en el grafo. Ver SOL return-vs-assert."
        )

    res = queries.search_concepts_by_text(nombre, limit=1)
    if not res:
        pytest.skip(
            f"fixture ausente: no se recupero el control limpio '{nombre[:40]}' "
            "por el canal de busqueda. Ver SOL return-vs-assert."
        )

    flag = res[0].get("contested", "AUSENTE")
    assert flag is False, (
        f"concepto limpio marcado como impugnado: {flag!r}. "
        "La bandera estaria siempre encendida: el otro test no mediria nada."
    )

    print(f"  [OK] control limpio '{nombre[:55]}' -> contested=False")
    print("  [OK] la bandera discrimina: no esta encendida por default")


def test_fallo_no_se_lee_como_limpio():
    """EL QUE IMPORTA: si la verificacion cae, NO puede devolver False.

    Es el bug H1 en miniatura (auditoria 2026-07-14): un fallo de
    infraestructura entregado como vacio se lee como "no existe". Un LLM lee
    `false`/`null` como "no hay disputa". El caso de fallo tiene que ser ruidoso.

    DATA-DEPENDIENTE: ejercita el camino sobre el nodo A. SKIP hasta fixture.
    """
    original = queries._fetch_contested
    queries._fetch_contested = lambda session, ids: None  # "no pude preguntar"
    try:
        res = queries.search_concepts_by_text(FRAGMENTO_NODO_A, limit=2)
    finally:
        queries._fetch_contested = original

    if not res:
        pytest.skip(
            f"fixture ausente: nodo A ('{FRAGMENTO_NODO_A}') no esta en el grafo "
            "vivo para ejercitar el camino de fallo. Ver SOL return-vs-assert."
        )

    flag = res[0].get("contested", "AUSENTE")
    assert flag not in (False, None, "AUSENTE"), (
        f"verificacion caida entregada como {flag!r}: el consumidor no puede "
        "distinguir 'limpio' de 'no pude preguntar'"
    )
    assert isinstance(flag, dict) and "error" in flag, (
        f"fallo sin campo `error` explicito: {flag!r}"
    )

    print(f"  [OK] verificacion caida -> contested.error = '{flag['error']}'")
    print("  [OK] falla ruidoso, no falsy: no se lee como 'limpio'")


def test_contexto_de_sesion_tambien_avisa():
    """El tool que TODO agente lee al abrir sesion no puede ser el punto ciego.

    DATA-DEPENDIENTE: exige que exista un nodo impugnado vivo en el proyecto.
    SKIP hasta fixture en base de prueba (ver SOL return-vs-assert).
    """
    md = queries.get_session_context_data(
        project="concept-sediment", domains=None, limit=50, output_format="markdown"
    )
    if "[IMPUGNADO]" not in md:
        pytest.skip(
            "fixture ausente: no hay ningun nodo impugnado vivo en project "
            "'concept-sediment' (top 50) para marcar. Requiere sembrar un nodo con "
            "contradicts entrante en base de prueba. Ver SOL return-vs-assert."
        )

    marcados = [ln.strip() for ln in md.splitlines() if "[IMPUGNADO] por:" in ln]
    assert marcados, "hay '[IMPUGNADO]' en el md pero ninguna linea '[IMPUGNADO] por:'"
    print(f"  [OK] contexto de sesion marca {len(marcados)} nodo(s) impugnado(s)")
    for m in marcados[:2]:
        print(f"       {m[:100]}")


def test_contexto_declara_su_propia_ceguera():
    """CONTRAFACTUAL del anterior: si la verificacion cae, el markdown lo dice.

    Si no, un contexto sin marcas se lee como "nada impugnado" cuando en verdad
    es "no se pudo mirar". Determinista: fuerza el fallo con monkeypatch.
    """
    original = queries._fetch_contested
    queries._fetch_contested = lambda session, ids: None
    try:
        md = queries.get_session_context_data(
            project="concept-sediment", limit=50, output_format="markdown"
        )
    finally:
        queries._fetch_contested = original

    assert "[IMPUGNADO]" not in md, (
        "la verificacion cayo y aun asi hay marcas (imposible)"
    )
    assert "No se pudo verificar impugnaciones" in md, (
        "verificacion caida y el markdown NO lo declara: se lee como 'ningun nodo impugnado'"
    )

    print("  [OK] verificacion caida -> '[AVISO] No se pudo verificar impugnaciones...'")
    print("  [OK] el silencio viene declarado como silencio, no como limpieza")


if __name__ == "__main__":
    _tests = [
        ("[1] El nodo con retador vivo se declara impugnado",
         test_impugnado_se_declara),
        ("[2] CONTRAFACTUAL: el nodo limpio NO se marca",
         test_limpio_no_se_marca),
        ("[3] La verificacion caida no se lee como 'limpio'",
         test_fallo_no_se_lee_como_limpio),
        ("[4] cs_get_session_context tambien avisa",
         test_contexto_de_sesion_tambien_avisa),
        ("[5] CONTRAFACTUAL: el contexto declara su propia ceguera",
         test_contexto_declara_su_propia_ceguera),
    ]
    passed = skipped = failed = 0
    for _titulo, _fn in _tests:
        print(_titulo)
        try:
            _fn()
            passed += 1
        except pytest.skip.Exception as _e:
            skipped += 1
            print(f"  [SKIP] {_e}")
        except AssertionError as _e:
            failed += 1
            print(f"  [ERROR] {_e}")

    print()
    print(f"RESULTADO: {passed} pass / {skipped} skip / {failed} fail")
    sys.exit(0 if failed == 0 else 1)

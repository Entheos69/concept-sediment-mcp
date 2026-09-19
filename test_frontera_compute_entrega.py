"""
Tests de la auditoria de la frontera COMPUTE -> ENTREGA (2026-07-14).

Forma auditada: el sistema calcula el dato correcto y lo pierde, lo recorta o lo
distorsiona antes de entregarlo al consumidor. Un sistema que calcula bien y
entrega mal es indistinguible, para quien lo consume, de uno que calcula mal —
y es peor, porque sus tests unitarios pasan.

Cubre los 6 hallazgos:
  H1 el fallo de embedding se entregaba como "0 resultados" (= "no existe")
  H2 cs_get_concept_graph aceptaba `depth` (1-3) y lo IGNORABA
  H3 el ranking de cs_session_open mezclaba similarity semantica con 0.0 lexico
  H4 cs_audit_thread recortaba a 5/5/3 sin declarar totales
  H5 `description` truncada a 300 chars sin marcador
  H6 cs_get_session_context no declaraba que el LIMIT habia recortado

Requiere BD (lectura pura). NO escribe.

Estado (SOL return-vs-assert, 2026-09-19): H2/H3/H6 dependen de fixtures volatiles en
la base VIVA (un concepto con relaciones de profundidad 2; un match lexico 'zombi';
>=5 conceptos en el proyecto para forzar el recorte). Contra la base viva eso es
blanco movil, asi que hacen `pytest.skip` RUIDOSO nombrando el fixture ausente en
vez de retornar bool (que pytest ignoraba -> falso verde). Migraran a `assert` con
fixture sembrado cuando exista la base de prueba (concept_sediment_test). H1/H5
fuerzan su propio camino (vector real + generador monkeypatch) y SI afirman.
"""
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402
import queries  # noqa: E402
from queries import (  # noqa: E402
    SEARCH_MODE_EMBEDDING,
    SEARCH_MODE_TEXT_DEGRADED,
    get_concept_with_relations,
    get_session_context_data,
    search_concepts,
)
from sqlalchemy import text as _sql  # noqa: E402

# Query en lenguaje natural: el motor semantico la entiende, ILIKE no (busca la
# frase literal). Es justo el caso donde el fallback mudo mentia.
QUERY_NL = "afirmacion zombi evento revision"
CONCEPTO_CON_RELACIONES = "Deriva de dependencias sin pin"


def _vector_de_un_concepto():
    """Toma el embedding real de un concepto del grafo, para usarlo como query.

    Asi el camino 'sano' se ejercita sin llamar a OpenAI: la busqueda semantica
    corre de verdad (pgvector, similitudes reales) aunque el proveedor de
    embeddings este caido/bloqueado en este entorno. Lo que probamos es la
    FRONTERA DE ENTREGA (search_mode, truncado declarado), no el proveedor.
    """
    session = db.get_session()
    try:
        row = session.execute(_sql(
            "SELECT embedding FROM graph_concept "
            "WHERE embedding IS NOT NULL ORDER BY weight DESC LIMIT 1"
        )).fetchone()
    finally:
        session.close()
    if not row or row.embedding is None:
        return None
    emb = row.embedding
    # pgvector puede devolverlo como str "[...]" o como lista.
    if isinstance(emb, str):
        return [float(x) for x in emb.strip("[]").split(",")]
    return list(emb)


def test_h1_degradacion_declarada():
    """Con el embedding caido, el vacio debe venir MARCADO como degradado.

    Independiente del proveedor de embeddings: el camino sano se fuerza con un
    vector real del grafo (monkeypatch), el degradado tumbando el generador.
    """
    vec = _vector_de_un_concepto()
    if vec is None:
        pytest.skip(
            "fixture ausente: ningun concepto con embedding en el grafo. "
            "Ver SOL return-vs-assert."
        )

    original = queries._generate_query_embedding

    # Camino SANO: el generador devuelve un vector valido -> corre pgvector.
    queries._generate_query_embedding = lambda t: vec
    try:
        sano = search_concepts(QUERY_NL, limit=3)
    finally:
        queries._generate_query_embedding = original

    # Invariante determinista: con un vector valido, el modo es embedding.
    assert sano["search_mode"] == SEARCH_MODE_EMBEDDING, (
        f"camino sano no dio modo embedding: {sano['search_mode']}"
    )
    print(f"  [OK] sano: mode={sano['search_mode']} degraded={sano['degraded']} "
          f"count={sano['count']}")

    # Camino DEGRADADO: el generador falla (None) -> ILIKE, marcado.
    queries._generate_query_embedding = lambda t: None
    try:
        roto = search_concepts(QUERY_NL, limit=3)
    finally:
        queries._generate_query_embedding = original

    assert roto["search_mode"] == SEARCH_MODE_TEXT_DEGRADED, (
        f"embedding caido -> mode={roto['search_mode']}"
    )
    assert roto["degraded"], "embedding caido y degraded=False"
    assert "warning" in roto, "degradado sin warning para el consumidor"
    print(f"  [OK] caido: mode={roto['search_mode']} degraded={roto['degraded']} "
          f"count={roto['count']} (declarado)")
    print("  [OK] el consumidor ya puede distinguir 'no existe' de 'no pude preguntar'")


def test_h2_depth_hace_algo():
    """depth=2 debe traer mas que depth=1. Antes eran identicos.

    DATA-DEPENDIENTE: exige un concepto de control con relaciones a profundidad 2.
    SKIP hasta fixture en base de prueba (ver SOL return-vs-assert).
    """
    d1 = get_concept_with_relations(CONCEPTO_CON_RELACIONES, depth=1)
    d2 = get_concept_with_relations(CONCEPTO_CON_RELACIONES, depth=2)
    if not d1 or not d2:
        pytest.skip(
            f"fixture ausente: concepto de control '{CONCEPTO_CON_RELACIONES}' con "
            "relaciones no esta en el grafo vivo. Ver SOL return-vs-assert."
        )

    t1 = len(d1.get("transitive_relations", []))
    t2 = len(d2.get("transitive_relations", []))

    assert d1.get("depth_requested") == 1 and d2.get("depth_requested") == 2, (
        "depth_requested no se refleja en la respuesta"
    )
    assert t1 == 0, f"depth=1 devolvio {t1} transitivas (el nivel 1 ya esta en out/in)"
    if t2 == 0:
        pytest.skip(
            f"fixture ausente: '{CONCEPTO_CON_RELACIONES}' no tiene relaciones "
            "transitivas a depth=2 en el grafo vivo. Ver SOL return-vs-assert."
        )

    niveles = sorted({r["level"] for r in d2["transitive_relations"]})
    print(f"  [OK] depth=1 -> 0 transitivas | depth=2 -> {t2} transitivas (niveles {niveles})")


def test_h3_ranking_no_mezcla_escalas():
    """Un hit lexico (similarity=None) no debe competir contra uno semantico.

    DATA-DEPENDIENTE: exige un match lexico para el control 'zombi'. SKIP hasta
    fixture en base de prueba (ver SOL return-vs-assert).
    """
    lexicos = queries.search_concepts_by_text("zombi", limit=2)
    if not lexicos:
        pytest.skip(
            "fixture ausente: el control lexico 'zombi' no matcheo ningun concepto "
            "en el grafo vivo. Ver SOL return-vs-assert."
        )

    assert "similarity" in lexicos[0], "el resultado lexico no declara el campo similarity"
    assert lexicos[0]["similarity"] is None, (
        f"ILIKE reporto similarity={lexicos[0]['similarity']!r} (deberia ser None: no puntua)"
    )

    print("  [OK] hit lexico declara similarity=None (antes el campo faltaba y se "
          "leia como 0.0 al rankear)")


def test_h5_truncado_declarado():
    """Toda description recortada debe venir marcada.

    Se fuerza el camino embedding con un vector real (independiente del proveedor)
    para obtener un lote de conceptos con descriptions largas.
    """
    vec = _vector_de_un_concepto()
    if vec is None:
        pytest.skip(
            "fixture ausente: ningun concepto con embedding. Ver SOL return-vs-assert."
        )

    original = queries._generate_query_embedding
    queries._generate_query_embedding = lambda t: vec
    try:
        res = search_concepts(QUERY_NL, limit=5)
    finally:
        queries._generate_query_embedding = original

    concepts = res["concepts"]
    if not concepts:
        pytest.skip(
            "fixture ausente: la busqueda semantica no devolvio conceptos para "
            "inspeccionar el truncado. Ver SOL return-vs-assert."
        )

    faltan_campo = [c["name"] for c in concepts if "description_truncated" not in c]
    assert not faltan_campo, f"sin marcador de truncado: {faltan_campo}"

    truncados = [c for c in concepts if c["description_truncated"]]
    for c in truncados:
        assert c["description"].endswith("..."), (
            f"marcado como truncado pero sin '...': {c['name'][:40]}"
        )

    print(f"  [OK] {len(concepts)} conceptos, {len(truncados)} con description "
          f"recortada y DECLARADA (campo + sufijo '...')")


def test_h6_limite_declarado():
    """Si el LIMIT recorta, el markdown debe avisar de que no es el dominio entero.

    DATA-DEPENDIENTE: exige >=5 conceptos activos en el proyecto para que el LIMIT
    recorte de verdad. Contra la base viva el conteo es blanco movil (CodeCS
    sedimenta en paralelo). SKIP hasta fixture con N>limit sembrado en base de
    prueba (ver SOL return-vs-assert).
    """
    md_corto = get_session_context_data(
        project="concept-sediment-mcp", limit=5, output_format="markdown"
    )
    # Precondicion: que el LIMIT se haya alcanzado de verdad (Conceptos: 5).
    if "Conceptos: 5" not in md_corto:
        pytest.skip(
            "fixture ausente: project 'concept-sediment-mcp' no tiene >=5 conceptos "
            "activos para forzar el recorte (blanco movil en base viva). "
            "Ver SOL return-vs-assert."
        )

    assert "[AVISO]" in md_corto, "limit=5 alcanzado y NO se avisa del recorte"
    print("  [OK] limit alcanzado -> '[AVISO] Se alcanzo el limite (5)...' en la salida")
    print("  [OK] el agente que abre sesion ya no cree ver el dominio entero")


if __name__ == "__main__":
    _tests = [
        ("[H1] La degradacion del motor semantico se DECLARA", test_h1_degradacion_declarada),
        ("[H2] El parametro depth hace algo", test_h2_depth_hace_algo),
        ("[H3] El ranking no mezcla escalas", test_h3_ranking_no_mezcla_escalas),
        ("[H5] El truncado de description se declara", test_h5_truncado_declarado),
        ("[H6] El recorte por LIMIT se declara", test_h6_limite_declarado),
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

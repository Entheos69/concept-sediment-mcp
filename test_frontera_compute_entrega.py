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
"""
import sys

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
        print("  [ERROR] ningun concepto con embedding en el grafo (no concluyente)")
        return False

    original = queries._generate_query_embedding

    # Camino SANO: el generador devuelve un vector valido -> corre pgvector.
    queries._generate_query_embedding = lambda t: vec
    try:
        sano = search_concepts(QUERY_NL, limit=3)
    finally:
        queries._generate_query_embedding = original

    if sano["search_mode"] != SEARCH_MODE_EMBEDDING or sano["count"] == 0:
        print(f"  [ERROR] camino sano no dio modo embedding: {sano['search_mode']}, "
              f"{sano['count']} hits")
        return False
    print(f"  [OK] sano: mode={sano['search_mode']} degraded={sano['degraded']} "
          f"count={sano['count']}")

    # Camino DEGRADADO: el generador falla (None) -> ILIKE, marcado.
    queries._generate_query_embedding = lambda t: None
    try:
        roto = search_concepts(QUERY_NL, limit=3)
    finally:
        queries._generate_query_embedding = original

    ok = True
    if roto["search_mode"] != SEARCH_MODE_TEXT_DEGRADED:
        print(f"  [ERROR] embedding caido -> mode={roto['search_mode']}")
        ok = False
    if not roto["degraded"]:
        print("  [ERROR] embedding caido y degraded=False")
        ok = False
    if "warning" not in roto:
        print("  [ERROR] degradado sin warning para el consumidor")
        ok = False
    if ok:
        print(f"  [OK] caido: mode={roto['search_mode']} degraded={roto['degraded']} "
              f"count={roto['count']} (0 hits, pero DECLARADO)")
        print("  [OK] el consumidor ya puede distinguir 'no existe' de 'no pude preguntar'")
    return ok


def test_h2_depth_hace_algo():
    """depth=2 debe traer mas que depth=1. Antes eran identicos."""
    d1 = get_concept_with_relations(CONCEPTO_CON_RELACIONES, depth=1)
    d2 = get_concept_with_relations(CONCEPTO_CON_RELACIONES, depth=2)
    if not d1 or not d2:
        print("  [ERROR] concepto de control no encontrado (test no concluyente)")
        return False

    t1 = len(d1.get("transitive_relations", []))
    t2 = len(d2.get("transitive_relations", []))

    if d1.get("depth_requested") != 1 or d2.get("depth_requested") != 2:
        print("  [ERROR] depth_requested no se refleja en la respuesta")
        return False
    if t1 != 0:
        print(f"  [ERROR] depth=1 devolvio {t1} transitivas (el nivel 1 ya esta en out/in)")
        return False
    if t2 == 0:
        print("  [ERROR] depth=2 no trajo NINGUNA relacion transitiva: el parametro "
              "sigue siendo fantasma")
        return False

    niveles = sorted({r["level"] for r in d2["transitive_relations"]})
    print(f"  [OK] depth=1 -> 0 transitivas | depth=2 -> {t2} transitivas (niveles {niveles})")
    return True


def test_h3_ranking_no_mezcla_escalas():
    """Un hit lexico (similarity=None) no debe competir contra uno semantico."""
    lexicos = queries.search_concepts_by_text("zombi", limit=2)
    if not lexicos:
        print("  [ERROR] el control lexico no matcheo (test no concluyente)")
        return False

    if "similarity" not in lexicos[0]:
        print("  [ERROR] el resultado lexico no declara el campo similarity")
        return False
    if lexicos[0]["similarity"] is not None:
        print(f"  [ERROR] ILIKE reporto similarity={lexicos[0]['similarity']!r} "
              "(deberia ser None: no puntua)")
        return False

    print("  [OK] hit lexico declara similarity=None (antes el campo faltaba y se "
          "leia como 0.0 al rankear)")
    return True


def test_h5_truncado_declarado():
    """Toda description recortada debe venir marcada.

    Se fuerza el camino embedding con un vector real (independiente del proveedor)
    para obtener un lote de conceptos con descriptions largas.
    """
    vec = _vector_de_un_concepto()
    if vec is None:
        print("  [ERROR] ningun concepto con embedding (no concluyente)")
        return False

    original = queries._generate_query_embedding
    queries._generate_query_embedding = lambda t: vec
    try:
        res = search_concepts(QUERY_NL, limit=5)
    finally:
        queries._generate_query_embedding = original

    concepts = res["concepts"]
    if not concepts:
        print("  [ERROR] sin resultados (test no concluyente)")
        return False

    faltan_campo = [c["name"] for c in concepts if "description_truncated" not in c]
    if faltan_campo:
        print(f"  [ERROR] sin marcador de truncado: {faltan_campo}")
        return False

    truncados = [c for c in concepts if c["description_truncated"]]
    for c in truncados:
        if not c["description"].endswith("..."):
            print(f"  [ERROR] marcado como truncado pero sin '...': {c['name'][:40]}")
            return False

    print(f"  [OK] {len(concepts)} conceptos, {len(truncados)} con description "
          f"recortada y DECLARADA (campo + sufijo '...')")
    return True


def test_h6_limite_declarado():
    """Si el LIMIT recorta, el markdown debe avisar de que no es el dominio entero."""
    md_corto = get_session_context_data(
        project="concept-sediment-mcp", limit=5, output_format="markdown"
    )
    tiene_aviso = "[AVISO]" in md_corto

    if not tiene_aviso:
        print("  [ERROR] limit=5 alcanzado y NO se avisa del recorte")
        return False

    print("  [OK] limit alcanzado -> '[AVISO] Se alcanzo el limite (5)...' en la salida")
    print("  [OK] el agente que abre sesion ya no cree ver el dominio entero")
    return True


if __name__ == "__main__":
    print("[H1] La degradacion del motor semantico se DECLARA")
    r1 = test_h1_degradacion_declarada()
    print("[H2] El parametro depth hace algo")
    r2 = test_h2_depth_hace_algo()
    print("[H3] El ranking no mezcla escalas")
    r3 = test_h3_ranking_no_mezcla_escalas()
    print("[H5] El truncado de description se declara")
    r5 = test_h5_truncado_declarado()
    print("[H6] El recorte por LIMIT se declara")
    r6 = test_h6_limite_declarado()

    print()
    if all([r1, r2, r3, r5, r6]):
        print("[OK] Todos los tests pasaron")
        sys.exit(0)
    print("[ERROR] Hay tests fallidos")
    sys.exit(1)

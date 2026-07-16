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
"""
import sys

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
    """El nodo con retador VIVO debe llegar marcado por el canal de busqueda."""
    res = queries.search_concepts_by_text(FRAGMENTO_NODO_A, limit=3)
    if not res:
        print("  [ERROR] el nodo A del handoff no esta en el grafo (no concluyente)")
        return False

    nodo = res[0]
    flag = nodo.get("contested", "AUSENTE")

    if flag == "AUSENTE":
        print("  [ERROR] el resultado no trae el campo `contested`")
        return False
    if flag is False:
        print("  [ERROR] nodo con contradicts entrante servido como LIMPIO "
              "(el bug del handoff, intacto)")
        return False
    if not isinstance(flag, dict) or not flag.get("by_active"):
        print(f"  [ERROR] impugnacion viva no declarada en by_active: {flag!r}")
        return False

    print(f"  [OK] '{nodo['name'][:60]}...'")
    print(f"  [OK] contested.by_active = {flag['by_active']}")
    print("  [OK] quien BUSCA ya recibe la senal que antes solo veia quien NAVEGA")
    return True


def test_limpio_no_se_marca():
    """CONTRAFACTUAL: un nodo sin impugnacion debe dar False.

    Sin esta mitad, una bandera encendida SIEMPRE pasaria el test de arriba y
    el verde no mediria nada. Un contrafactual que no ladra no es contrafactual.
    """
    nombre = _oraculo_limpio()
    if not nombre:
        print("  [ERROR] el oraculo no hallo ningun concepto limpio (no concluyente)")
        return False

    res = queries.search_concepts_by_text(nombre, limit=1)
    if not res:
        print(f"  [ERROR] no se recupero el control '{nombre[:40]}' (no concluyente)")
        return False

    flag = res[0].get("contested", "AUSENTE")
    if flag is not False:
        print(f"  [ERROR] concepto limpio marcado como impugnado: {flag!r}")
        print("  [ERROR] la bandera esta siempre encendida: el otro test no mide nada")
        return False

    print(f"  [OK] control limpio '{nombre[:55]}' -> contested=False")
    print("  [OK] la bandera discrimina: no esta encendida por default")
    return True


def test_fallo_no_se_lee_como_limpio():
    """EL QUE IMPORTA: si la verificacion cae, NO puede devolver False.

    Es el bug H1 en miniatura (auditoria 2026-07-14): un fallo de
    infraestructura entregado como vacio se lee como "no existe". Un LLM lee
    `false`/`null` como "no hay disputa". El caso de fallo tiene que ser ruidoso.
    """
    original = queries._fetch_contested
    queries._fetch_contested = lambda session, ids: None  # "no pude preguntar"
    try:
        res = queries.search_concepts_by_text(FRAGMENTO_NODO_A, limit=2)
    finally:
        queries._fetch_contested = original

    if not res:
        print("  [ERROR] sin resultados (no concluyente)")
        return False

    flag = res[0].get("contested", "AUSENTE")
    if flag is False or flag is None or flag == "AUSENTE":
        print(f"  [ERROR] verificacion caida entregada como {flag!r}: el consumidor "
              "no puede distinguir 'limpio' de 'no pude preguntar'")
        return False
    if not isinstance(flag, dict) or "error" not in flag:
        print(f"  [ERROR] fallo sin campo `error` explicito: {flag!r}")
        return False

    print(f"  [OK] verificacion caida -> contested.error = '{flag['error']}'")
    print("  [OK] falla ruidoso, no falsy: no se lee como 'limpio'")
    return True


def test_contexto_de_sesion_tambien_avisa():
    """El tool que TODO agente lee al abrir sesion no puede ser el punto ciego."""
    md = queries.get_session_context_data(
        project="concept-sediment", domains=None, limit=50, output_format="markdown"
    )
    if "[IMPUGNADO]" not in md:
        print("  [ERROR] cs_get_session_context no marca ningun nodo impugnado")
        print("  [ERROR] el canal de consumo mas ancho sigue ciego")
        return False

    marcados = [ln.strip() for ln in md.splitlines() if "[IMPUGNADO] por:" in ln]
    print(f"  [OK] contexto de sesion marca {len(marcados)} nodo(s) impugnado(s)")
    for m in marcados[:2]:
        print(f"       {m[:100]}")
    return True


def test_contexto_declara_su_propia_ceguera():
    """CONTRAFACTUAL del anterior: si la verificacion cae, el markdown lo dice.

    Si no, un contexto sin marcas se lee como "nada impugnado" cuando en verdad
    es "no se pudo mirar".
    """
    original = queries._fetch_contested
    queries._fetch_contested = lambda session, ids: None
    try:
        md = queries.get_session_context_data(
            project="concept-sediment", limit=50, output_format="markdown"
        )
    finally:
        queries._fetch_contested = original

    if "[IMPUGNADO]" in md:
        print("  [ERROR] la verificacion cayo y aun asi hay marcas (imposible)")
        return False
    if "No se pudo verificar impugnaciones" not in md:
        print("  [ERROR] verificacion caida y el markdown NO lo declara: se lee "
              "como 'ningun nodo impugnado'")
        return False

    print("  [OK] verificacion caida -> '[AVISO] No se pudo verificar impugnaciones...'")
    print("  [OK] el silencio viene declarado como silencio, no como limpieza")
    return True


if __name__ == "__main__":
    print("[1] El nodo con retador vivo se declara impugnado")
    r1 = test_impugnado_se_declara()
    print("[2] CONTRAFACTUAL: el nodo limpio NO se marca")
    r2 = test_limpio_no_se_marca()
    print("[3] La verificacion caida no se lee como 'limpio'")
    r3 = test_fallo_no_se_lee_como_limpio()
    print("[4] cs_get_session_context tambien avisa")
    r4 = test_contexto_de_sesion_tambien_avisa()
    print("[5] CONTRAFACTUAL: el contexto declara su propia ceguera")
    r5 = test_contexto_declara_su_propia_ceguera()

    print()
    if all([r1, r2, r3, r4, r5]):
        print("[OK] Todos los tests pasaron")
        sys.exit(0)
    print("[ERROR] Hay tests fallidos")
    sys.exit(1)

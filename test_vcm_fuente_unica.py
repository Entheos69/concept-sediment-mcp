"""
Test del cableado a la fuente unica de vacunas (tabla graph_vcmdirective).

Cierra el paso 2 del contrato con CodeCS (gemelo VCM, 2026-07-14): las directivas
dejan de vivir como constante duplicada en dos repos y pasan a ser un DATO en el
Postgres que ambos ya compartian.

Cubre:
  1. FUENTE: load_vcm_directives() lee de 'db', no del fallback.
  2. PARIDAD: lo leido coincide con la tabla (conteo + nombres).
  3. FALLBACK DECLARADO: si la tabla no esta, cae a la constante local y lo DICE
     (un fallback silencioso seria el gemelo otra vez, ahora invisible).
  4. CONTRAFACTUAL: insertar una vacuna imposible -> ladra; rollback -> calla.
     Un cero sin contrafactual es indistinguible de un matcher roto (metodo de
     CodeCS, 2026-07-14). La insercion va en transaccion con ROLLBACK: no deja
     rastro en la tabla.

Requiere BD. NO deja escrituras.
"""
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text  # noqa: E402

import db  # noqa: E402
import humandato_queries as hq  # noqa: E402


def test_fuente_es_db():
    directivas, fuente = hq.load_vcm_directives()
    if fuente != "db":
        print(f"  [ERROR] fuente='{fuente}', esperado 'db' (la tabla no se esta leyendo)")
        return False
    print(f"  [OK] fuente='db': {len(directivas)} directivas leidas de graph_vcmdirective")
    return True


def test_paridad_con_tabla():
    directivas, _ = hq.load_vcm_directives()
    session = db.get_session()
    try:
        rows = session.execute(
            text("SELECT name FROM graph_vcmdirective WHERE revoked_at IS NULL")
        ).fetchall()
    finally:
        session.close()

    en_tabla = {r.name for r in rows}
    en_memoria = {d["name"] for d in directivas}

    if en_tabla != en_memoria:
        print(f"  [ERROR] divergencia: tabla-memoria={en_tabla - en_memoria}, "
              f"memoria-tabla={en_memoria - en_tabla}")
        return False
    print(f"  [OK] paridad {len(en_tabla)}/{len(en_memoria)} vigentes (revoked_at IS NULL)")
    return True


def test_fallback_declarado():
    """Simula tabla ausente: debe caer a la constante Y declararlo."""
    original = hq.VCM_LOAD_SQL
    hq.VCM_LOAD_SQL = "SELECT * FROM tabla_que_no_existe_vcm"
    try:
        directivas, fuente = hq.load_vcm_directives()
    finally:
        hq.VCM_LOAD_SQL = original

    if fuente != "fallback":
        print(f"  [ERROR] con la tabla ausente, fuente='{fuente}' (esperado 'fallback')")
        return False
    if directivas is not hq.VCM_DIRECTIVES_FALLBACK:
        print("  [ERROR] el fallback no devolvio la constante local")
        return False
    print(f"  [OK] tabla ausente -> fallback declarado ({len(directivas)} directivas)")
    return True


def test_contrafactual_rollback():
    """Inserta una vacuna imposible de satisfacer: debe ladrar. Rollback: calla.

    Sin esto, 'cero vacunas faltantes' no distingue un grafo sano de un matcher
    roto que nunca ladra.
    """
    nombre = "zzz-contrafactual-nunca-sedimentado"
    directiva = "CONTRAFACTUAL: no debe existir en el grafo"

    antes = hq.get_missing_vaccines(None)
    ok = True

    session = db.get_session()
    try:
        session.execute(
            text("""
                INSERT INTO graph_vcmdirective
                    (id, name, scope, applicable_projects, category, severity,
                     directive, min_weight, failure_history, revocation_reason,
                     created_at, updated_at)
                VALUES
                    (:id, :name, 'global', '{}', 'ctl', 'critical',
                     :directive, 1.0, 'control de test', '', NOW(), NOW())
            """),
            {
                "id": str(uuid.uuid4()),  # UUID en Python, no gen_random_uuid()
                "name": nombre,
                "directive": directiva,
            },
        )
        session.flush()  # visible en ESTA transaccion, no commiteada

        # La sesion se inyecta: recorre la cadena completa tabla -> ladrido.
        durante = hq.get_missing_vaccines(None, session=session)
        ladro = directiva in {v["directive"] for v in durante}

        if ladro:
            print(f"  [OK] vacuna imposible insertada -> LADRA "
                  f"({len(antes)} -> {len(durante)} faltantes)")
        else:
            ok = False
            print("  [ERROR] vacuna imposible insertada y NO ladro: "
                  "el matcher esta roto (un cero suyo no seria evidencia)")
    finally:
        session.rollback()  # nada se commitea
        session.close()

    # Post-rollback: ni rastro en la tabla, y las alertas vuelven a su estado
    despues = hq.get_missing_vaccines(None)
    session = db.get_session()
    try:
        quedan = session.execute(
            text("SELECT COUNT(*) AS n FROM graph_vcmdirective WHERE name = :n"),
            {"n": nombre},
        ).fetchone().n
    finally:
        session.close()

    if quedan != 0:
        print(f"  [ERROR] el rollback dejo rastro: {quedan} fila(s) de '{nombre}'")
        return False

    if {v["directive"] for v in antes} != {v["directive"] for v in despues}:
        print("  [ERROR] el estado de alertas no volvio a su punto de partida")
        return False

    print(f"  [OK] rollback limpio: 0 filas de control en la tabla, "
          f"alertas de vuelta a {len(despues)} faltante(s)")
    return ok


if __name__ == "__main__":
    print("[TEST 1] La fuente de las vacunas es la tabla, no la constante")
    r1 = test_fuente_es_db()
    print("[TEST 2] Paridad memoria <-> tabla")
    r2 = test_paridad_con_tabla()
    print("[TEST 3] Fallback declarado si la tabla no esta")
    r3 = test_fallback_declarado()
    print("[TEST 4] Contrafactual con rollback (un cero sin contrafactual no es evidencia)")
    r4 = test_contrafactual_rollback()

    print()
    if all([r1, r2, r3, r4]):
        print("[OK] Todos los tests pasaron")
        sys.exit(0)
    print("[ERROR] Hay tests fallidos")
    sys.exit(1)

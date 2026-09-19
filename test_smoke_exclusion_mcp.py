"""
Test de validacion para F47-D1.1 lado MCP.

Verifica que:
1. Los modulos modificados sigan importando sin errores tras los cambios.
2. DISCARDS_DETAIL_SQL incluya el JOIN con graph_sessionlog y la columna is_test.
3. DISCARDS_SUMMARY_SQL incluya total_pending_real y filtro is_test=FALSE en type_stats.
4. server.py incluya la rama narrativa para smokes.
5. (BD real, SKIP ruidoso) end-to-end: smokes no rompen 'estable', narrative muestra
   'Productivas (excluyendo smokes)' cuando total_pending != total_pending_real.

Tests 1-4 NO requieren BD: validan estructura del codigo con `assert` (fallan/ladran
tanto bajo pytest como al correr el archivo como script). Antes retornaban bool, que
pytest ignora -> el test pasaba aunque el invariante fallara (verde que no mide).
El test 5 es un SKIP declarado (pytest.skip con motivo), no un pass silencioso.
"""
import sys

import pytest


def test_imports():
    """Verifica que los modulos se importen sin errores tras los cambios F47-D1.1."""
    print("[TEST 1] Verificando imports tras cambios F47-D1.1...")

    try:
        from discard_queries import (  # noqa: F401
            get_discards_summary,
            get_discards_detail,
            DISCARDS_SUMMARY_SQL,
            DISCARDS_DETAIL_SQL,
        )
        print("  [OK] discard_queries imports completos")
    except ImportError as e:
        raise AssertionError(f"Import de discard_queries fallo: {e}")

    try:
        from humandato_queries import get_all_alerts  # noqa: F401
        print("  [OK] humandato_queries.get_all_alerts disponible")
    except ImportError as e:
        raise AssertionError(f"Import de humandato_queries fallo: {e}")

    try:
        import server  # noqa: F401
        print("  [OK] server.py importado correctamente")
    except ImportError as e:
        raise AssertionError(f"Import de server fallo: {e}")

    print("[TEST 1] PASS\n")


def test_detail_sql_has_is_test():
    """Verifica que DISCARDS_DETAIL_SQL incluya JOIN con graph_sessionlog y columna is_test."""
    print("[TEST 2] Verificando DISCARDS_DETAIL_SQL incluye is_test...")

    from discard_queries import DISCARDS_DETAIL_SQL

    assert "LEFT JOIN graph_sessionlog sl" in DISCARDS_DETAIL_SQL, (
        "LEFT JOIN graph_sessionlog NO encontrado"
    )
    print("  [OK] LEFT JOIN graph_sessionlog presente")

    assert "COALESCE(sl.is_test, FALSE) as is_test" in DISCARDS_DETAIL_SQL, (
        "COALESCE(sl.is_test, FALSE) NO encontrado"
    )
    print("  [OK] columna is_test seleccionada via COALESCE")

    assert "sl.session_id = rd.session_id" in DISCARDS_DETAIL_SQL, (
        "JOIN ON clause incorrecta"
    )
    print("  [OK] JOIN ON sl.session_id = rd.session_id")

    print("[TEST 2] PASS\n")


def test_summary_sql_has_total_real():
    """Verifica que DISCARDS_SUMMARY_SQL incluya total_pending_real y filtro smokes en type_stats."""
    print("[TEST 3] Verificando DISCARDS_SUMMARY_SQL incluye total_pending_real...")

    from discard_queries import DISCARDS_SUMMARY_SQL

    assert "FILTER (WHERE COALESCE(sl.is_test, FALSE) = FALSE) as total_real" in DISCARDS_SUMMARY_SQL, (
        "FILTER de total_real NO encontrado"
    )
    print("  [OK] CTE discard_counts calcula total_real con FILTER")

    assert "total_pending_real" in DISCARDS_SUMMARY_SQL, (
        "total_pending_real NO en SELECT"
    )
    print("  [OK] total_pending_real expuesto en SELECT principal")

    assert "AND COALESCE(sl.is_test, FALSE) = FALSE" in DISCARDS_SUMMARY_SQL, (
        "type_stats NO excluye smokes"
    )
    print("  [OK] type_stats excluye smokes para regla B1.2")

    join_count = DISCARDS_SUMMARY_SQL.count("LEFT JOIN graph_sessionlog sl")
    assert join_count >= 2, (
        f"JOIN sessionlog solo en {join_count} lugares (esperado >=2)"
    )
    print(f"  [OK] LEFT JOIN graph_sessionlog presente en {join_count} lugares")

    print("[TEST 3] PASS\n")


def test_server_narrative_smoke_branch():
    """Verifica que server.py incluya la rama narrativa para smokes."""
    print("[TEST 4] Verificando server.py incluye rama narrativa F47-D1.1...")

    import inspect

    # La narrativa de cs_get_alerts se extrajo de server.py a alerts_format.py
    # (2026-07-14, fix del formateador que silenciaba lo no-critico). El
    # stable-check tambien: get_all_alerts calcula el status y format_alerts
    # decide el silencio. Se inspeccionan ambos modulos.
    import alerts_format
    import humandato_queries
    src = (
        inspect.getsource(alerts_format)
        + inspect.getsource(humandato_queries)
    )

    # Stable check ya no silencia por status: ahora solo calla si NO hay alerta
    # de ningun tipo, e incluye discards_real en ese conteo.
    assert "discards_real" in src and "total_alertas" in src, (
        "stable-check no actualizado para F47-D1.1"
    )
    print("  [OK] silencio condicionado a total_alertas (incluye discards_real)")

    assert "Productivas (excluyendo smokes)" in src, (
        "narrativa no muestra total productivo"
    )
    print("  [OK] narrativa muestra total productivo cuando difiere")

    assert "Todos los pending provienen de sesiones smoke" in src, (
        "mensaje INFO de 100% smoke ausente"
    )
    print("  [OK] mensaje INFO para caso 100% smoke presente")

    print("[TEST 4] PASS\n")


def test_db_real_e2e():
    """E2E con BD real. SKIP declarado: requiere un fixture no auto-construible."""
    pytest.skip(
        "E2E requiere BD con una sesion smoke pre-cargada "
        "(session_id 'TEST-...-smoke', is_test=True via extract_concepts); "
        "fixture no auto-construible en la suite. Listado en SOL return-vs-assert."
    )


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDACION F47-D1.1 lado MCP (smokes no contaminan)")
    print("=" * 60)
    print()

    tests = [
        test_imports,
        test_detail_sql_has_is_test,
        test_summary_sql_has_total_real,
        test_server_narrative_smoke_branch,
        test_db_real_e2e,
    ]

    passed = skipped = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except pytest.skip.Exception as e:
            skipped += 1
            print(f"[SKIP] {test.__name__}: {e}\n")
        except AssertionError as e:
            failed += 1
            print(f"  [ERROR] {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[EXCEPCION] {test.__name__}: {e}")

    print("=" * 60)
    print(f"RESULTADO: {passed} pass / {skipped} skip / {failed} fail")

    if failed == 0:
        print("STATUS: PASS - Implementacion F47-D1.1 lado MCP validada")
        sys.exit(0)
    print("STATUS: FAIL - Revisar errores arriba")
    sys.exit(1)

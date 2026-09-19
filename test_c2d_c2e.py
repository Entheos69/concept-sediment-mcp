"""
Test de validación para C2d + C2e (F47).

Verifica que:
1. Los imports funcionen correctamente
2. Las funciones estén definidas
3. Los parámetros de configuración sean accesibles
4. La estructura de datos retornada sea correcta

NO requiere BD activa — solo valida estructura del código con `assert`.
El test de estructura sobre BD real es un SKIP declarado (pytest.skip), no un pass.
"""
import os
import sys

import pytest


def test_imports():
    """Verifica que los módulos se importen sin errores."""
    print("[TEST 1] Verificando imports...")

    try:
        from discard_queries import (  # noqa: F401
            get_discards_summary,
            get_discards_detail,
            CS_DISCARD_STALE_DAYS,
            CS_DISCARD_PROMO_OCCURRENCES,
            CS_DISCARD_PROMO_AGENTS,
        )
        print("  [OK] discard_queries importado correctamente")
        print(f"  [OK] CS_DISCARD_STALE_DAYS = {CS_DISCARD_STALE_DAYS}")
        print(f"  [OK] CS_DISCARD_PROMO_OCCURRENCES = {CS_DISCARD_PROMO_OCCURRENCES}")
        print(f"  [OK] CS_DISCARD_PROMO_AGENTS = {CS_DISCARD_PROMO_AGENTS}")
    except ImportError as e:
        raise AssertionError(f"Import de discard_queries fallo: {e}")

    try:
        from humandato_queries import get_all_alerts  # noqa: F401
        print("  [OK] humandato_queries.get_all_alerts disponible")
    except ImportError as e:
        raise AssertionError(f"Import de humandato_queries fallo: {e}")

    import server
    assert hasattr(server, "cs_get_discards"), (
        "Tool cs_get_discards NO encontrado en server.py"
    )
    print("  [OK] server.py importado correctamente")
    print("  [OK] Tool cs_get_discards definido en server.py")

    print("[TEST 1] PASS\n")


def test_function_signatures():
    """Verifica que las funciones tengan las firmas correctas."""
    print("[TEST 2] Verificando firmas de funciones...")

    from discard_queries import get_discards_summary, get_discards_detail
    import inspect

    sig = inspect.signature(get_discards_summary)
    params = list(sig.parameters.keys())
    assert params == ["project"], (
        f"get_discards_summary params: esperado ['project'], obtuvo {params}"
    )
    print(f"  [OK] get_discards_summary{sig}")

    sig = inspect.signature(get_discards_detail)
    params = list(sig.parameters.keys())
    assert params == ["reason", "status", "project", "limit"], (
        f"get_discards_detail params: esperado ['reason', 'status', 'project', 'limit'], "
        f"obtuvo {params}"
    )
    print(f"  [OK] get_discards_detail{sig}")

    print("[TEST 2] PASS\n")


def test_alerts_structure():
    """Estructura de get_all_alerts con BD real. SKIP declarado."""
    pytest.skip(
        "Requiere conexion a BD real para get_all_alerts(); no es fixture "
        "auto-construible en la suite. Listado en SOL return-vs-assert."
    )


def test_config_overrides():
    """Verifica que los env vars sobreescriban defaults."""
    print("[TEST 4] Verificando configuración parametrizada...")

    # Guardar valores originales
    original_stale = os.getenv("CS_DISCARD_STALE_DAYS")
    original_promo_occ = os.getenv("CS_DISCARD_PROMO_OCCURRENCES")
    original_promo_ag = os.getenv("CS_DISCARD_PROMO_AGENTS")

    # Setear valores custom
    os.environ["CS_DISCARD_STALE_DAYS"] = "14"
    os.environ["CS_DISCARD_PROMO_OCCURRENCES"] = "5"
    os.environ["CS_DISCARD_PROMO_AGENTS"] = "3"

    # Reimportar módulo para cargar nuevos valores
    import importlib
    import discard_queries
    importlib.reload(discard_queries)

    try:
        assert discard_queries.CS_DISCARD_STALE_DAYS == 14, (
            f"CS_DISCARD_STALE_DAYS: esperado 14, obtuvo {discard_queries.CS_DISCARD_STALE_DAYS}"
        )
        print("  [OK] CS_DISCARD_STALE_DAYS configurable via env")

        assert discard_queries.CS_DISCARD_PROMO_OCCURRENCES == 5, (
            f"CS_DISCARD_PROMO_OCCURRENCES: esperado 5, obtuvo {discard_queries.CS_DISCARD_PROMO_OCCURRENCES}"
        )
        print("  [OK] CS_DISCARD_PROMO_OCCURRENCES configurable via env")

        assert discard_queries.CS_DISCARD_PROMO_AGENTS == 3, (
            f"CS_DISCARD_PROMO_AGENTS: esperado 3, obtuvo {discard_queries.CS_DISCARD_PROMO_AGENTS}"
        )
        print("  [OK] CS_DISCARD_PROMO_AGENTS configurable via env")
    finally:
        # Restaurar valores originales SIEMPRE (aunque un assert falle)
        for var, original in (
            ("CS_DISCARD_STALE_DAYS", original_stale),
            ("CS_DISCARD_PROMO_OCCURRENCES", original_promo_occ),
            ("CS_DISCARD_PROMO_AGENTS", original_promo_ag),
        ):
            if original is not None:
                os.environ[var] = original
            else:
                os.environ.pop(var, None)
        importlib.reload(discard_queries)

    print("[TEST 4] PASS\n")


def main():
    """Ejecuta todos los tests de validación."""
    print("=" * 60)
    print("VALIDACIÓN C2d + C2e (F47)")
    print("=" * 60)
    print()

    tests = [
        test_imports,
        test_function_signatures,
        test_alerts_structure,
        test_config_overrides,
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
            print(f"[EXCEPCIÓN] {test.__name__}: {e}")

    print("=" * 60)
    print(f"RESULTADO: {passed} pass / {skipped} skip / {failed} fail")

    if failed == 0:
        print("STATUS: PASS — Implementación C2d + C2e validada")
        return 0
    print("STATUS: FAIL — Revisar errores arriba")
    return 1


if __name__ == "__main__":
    sys.exit(main())

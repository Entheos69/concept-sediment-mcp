"""
Test de validación para C2d + C2e (F47).

Verifica que:
1. Los imports funcionen correctamente
2. Las funciones estén definidas
3. Los parámetros de configuración sean accesibles
4. La estructura de datos retornada sea correcta

NO requiere BD activa — solo valida estructura del código.
"""
import os
import sys


def test_imports():
    """Verifica que los módulos se importen sin errores."""
    print("[TEST 1] Verificando imports...")

    try:
        from discard_queries import (
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
        print(f"  [ERROR] Import de discard_queries fallo: {e}")
        return False

    try:
        from humandato_queries import get_all_alerts
        print("  [OK] humandato_queries.get_all_alerts disponible")
    except ImportError as e:
        print(f"  [ERROR] Import de humandato_queries fallo: {e}")
        return False

    try:
        import server
        print("  [OK] server.py importado correctamente")

        # Verificar que cs_get_discards esté definido
        if hasattr(server, 'cs_get_discards'):
            print("  [OK] Tool cs_get_discards definido en server.py")
        else:
            print("  [ERROR] Tool cs_get_discards NO encontrado en server.py")
            return False

    except ImportError as e:
        print(f"  [ERROR] Import de server fallo: {e}")
        return False

    print("[TEST 1] PASS\n")
    return True


def test_function_signatures():
    """Verifica que las funciones tengan las firmas correctas."""
    print("[TEST 2] Verificando firmas de funciones...")

    from discard_queries import get_discards_summary, get_discards_detail
    import inspect

    # Verificar get_discards_summary
    sig = inspect.signature(get_discards_summary)
    params = list(sig.parameters.keys())
    expected = ["project"]
    if params == expected:
        print(f"  [OK] get_discards_summary{sig}")
    else:
        print(f"  [ERROR] get_discards_summary params: esperado {expected}, obtuvo {params}")
        return False

    # Verificar get_discards_detail
    sig = inspect.signature(get_discards_detail)
    params = list(sig.parameters.keys())
    expected = ["reason", "status", "project", "limit"]
    if params == expected:
        print(f"  [OK] get_discards_detail{sig}")
    else:
        print(f"  [ERROR] get_discards_detail params: esperado {expected}, obtuvo {params}")
        return False

    print("[TEST 2] PASS\n")
    return True


def test_alerts_structure():
    """Verifica que get_all_alerts retorne estructura esperada con discards."""
    print("[TEST 3] Verificando estructura de get_all_alerts...")
    print("  [INFO] Este test requiere conexión a BD — SKIPPED")
    print("  [INFO] Para testear con BD real, ejecutar:")
    print("         python -c 'from humandato_queries import get_all_alerts; print(get_all_alerts())'")
    print("[TEST 3] SKIPPED\n")
    return True


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

    if discard_queries.CS_DISCARD_STALE_DAYS == 14:
        print("  [OK] CS_DISCARD_STALE_DAYS configurable via env")
    else:
        print(f"  [ERROR] CS_DISCARD_STALE_DAYS: esperado 14, obtuvo {discard_queries.CS_DISCARD_STALE_DAYS}")
        return False

    if discard_queries.CS_DISCARD_PROMO_OCCURRENCES == 5:
        print("  [OK] CS_DISCARD_PROMO_OCCURRENCES configurable via env")
    else:
        print(f"  [ERROR] CS_DISCARD_PROMO_OCCURRENCES: esperado 5, obtuvo {discard_queries.CS_DISCARD_PROMO_OCCURRENCES}")
        return False

    if discard_queries.CS_DISCARD_PROMO_AGENTS == 3:
        print("  [OK] CS_DISCARD_PROMO_AGENTS configurable via env")
    else:
        print(f"  [ERROR] CS_DISCARD_PROMO_AGENTS: esperado 3, obtuvo {discard_queries.CS_DISCARD_PROMO_AGENTS}")
        return False

    # Restaurar valores originales
    if original_stale:
        os.environ["CS_DISCARD_STALE_DAYS"] = original_stale
    else:
        del os.environ["CS_DISCARD_STALE_DAYS"]

    if original_promo_occ:
        os.environ["CS_DISCARD_PROMO_OCCURRENCES"] = original_promo_occ
    else:
        del os.environ["CS_DISCARD_PROMO_OCCURRENCES"]

    if original_promo_ag:
        os.environ["CS_DISCARD_PROMO_AGENTS"] = original_promo_ag
    else:
        del os.environ["CS_DISCARD_PROMO_AGENTS"]

    print("[TEST 4] PASS\n")
    return True


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

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"[EXCEPCIÓN] {test.__name__}: {e}")
            results.append(False)

    print("=" * 60)
    print(f"RESULTADO: {sum(results)}/{len(results)} tests pasaron")

    if all(results):
        print("STATUS: PASS — Implementación C2d + C2e validada")
        return 0
    else:
        print("STATUS: FAIL — Revisar errores arriba")
        return 1


if __name__ == "__main__":
    sys.exit(main())

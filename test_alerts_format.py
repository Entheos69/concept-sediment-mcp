"""
Test de regresion del formateador de alertas (alerts_format.format_alerts).

BUG que cubre (detectado 2026-07-14 leyendo el grafo tras el fix de vacunas):
    El early-return de "sistema inmunologico estable. Sin alertas." se disparaba
    con summary["status"] == "stable", y status SOLO mira criticas
    (critical_alerts = fracturas criticas + vacunas severity=critical).
    Efecto: una vacuna HIGH faltante o una fractura MODERADA se calculaban, se
    metian en el payload... y se tiraban sin imprimir. El consumidor leia
    "Sin alertas" con alertas vivas.

    Caso real: cs_get_alerts(project="concept-sediment") decia "estable" con la
    vacuna `name es identificador` (HIGH) faltante. Y en el arranque de esa misma
    sesion, project="concept-sediment-mcp" dijo "estable" ocultando 3 fracturas
    moderadas que cs_session_open (JSON crudo, sin este formateador) si mostraba.

NO requiere BD ni fastmcp: format_alerts es una funcion pura dict -> str.
"""
import sys

from alerts_format import format_alerts


def _alerts(criticas=0, moderadas=0, vacunas=None, discards_real=0):
    """Construye un payload de get_all_alerts() sintetico."""
    vacunas = vacunas or []

    def _fractura(nombre):
        return {
            "concept": nombre,
            "status": "dormant",
            "active_dependents": [{"name": f"dep de {nombre}"}],
        }

    lista_criticas = [_fractura(f"critica-{i}") for i in range(criticas)]
    lista_moderadas = [_fractura(f"moderada-{i}") for i in range(moderadas)]
    total_fracturas = criticas + moderadas

    critical_alerts = criticas + len(
        [v for v in vacunas if v["severity"] == "critical"]
    )
    # Replica la logica de get_all_alerts(): stable si no hay NADA critico.
    status = "stable" if critical_alerts == 0 else "vulnerable"

    return {
        "fractures": {
            "criticas": lista_criticas,
            "moderadas": lista_moderadas,
            "bajas": [],
            "total": total_fracturas,
        },
        "missing_vaccines": vacunas,
        "relation_discards": {
            "total_pending": discards_real,
            "total_pending_real": discards_real,
            "by_reason": {"unknown_type": 0, "target_not_found": discards_real},
            "top_invalid_types": [],
            "oldest_pending_days": None,
            "types_meeting_promo_rule": 0,
        },
        "summary": {
            "fractures_count": total_fracturas,
            "fractures_criticas": criticas,
            "fractures_moderadas": moderadas,
            "fractures_bajas": 0,
            "missing_vaccines_count": len(vacunas),
            "critical_alerts": critical_alerts,
            "status": status,
        },
    }


VACUNA_HIGH = {
    "severity": "high",
    "category": "concept_sediment",
    "directive": "name es IDENTIFICADOR corto (<=200 chars)",
    "failure_history": "StringDataRightTruncation, 3 YAMLs 2026-06-05/06",
    "found_concept": None,
    "found_weight": 0.0,
    "reason": "Sin representacion en el grafo",
}
VACUNA_CRITICAL = {
    "severity": "critical",
    "category": "workflow",
    "directive": "Git push NUNCA automatico",
    "failure_history": "Violada frecuentemente",
    "found_concept": None,
    "found_weight": 0.0,
    "reason": "Sin representacion en el grafo",
}

SILENCIO = "Sin alertas"

CASOS = [
    # (titulo, alerts, debe_estar_en_salida, NO_debe_estar)
    (
        "grafo limpio: silencio legitimo",
        _alerts(),
        [SILENCIO],
        [],
    ),
    (
        "solo vacuna HIGH (status=stable): DEBE ladrar",  # el bug
        _alerts(vacunas=[VACUNA_HIGH]),
        ["VACUNAS FALTANTES", "[HIGH]", "IDENTIFICADOR"],
        [SILENCIO],
    ),
    (
        "solo fracturas MODERADAS (status=stable): DEBEN salir",  # el bug
        _alerts(moderadas=3),
        ["FRACTURAS", "[MODERADA]", "moderada-0"],
        [SILENCIO],
    ),
    (
        "solo discards: DEBEN salir",
        _alerts(discards_real=62),
        ["ARISTAS PENDING", "62"],
        [SILENCIO],
    ),
    (
        "criticas + no criticas: encabezado cuenta ambas",
        _alerts(criticas=2, moderadas=1, vacunas=[VACUNA_CRITICAL, VACUNA_HIGH]),
        ["3 alerta(s) critica(s)", "2 no critica(s)", "[CRITICA]", "[HIGH]"],
        [SILENCIO],
    ),
]


def test_formateador():
    ok = True
    for titulo, alerts, esperados, prohibidos in CASOS:
        salida = format_alerts(alerts)
        faltan = [e for e in esperados if e not in salida]
        sobran = [p for p in prohibidos if p in salida]

        if not faltan and not sobran:
            print(f"  [OK] {titulo}")
        else:
            ok = False
            print(f"  [ERROR] {titulo}")
            if faltan:
                print(f"      falta en la salida: {faltan}")
            if sobran:
                print(f"      NO deberia aparecer: {sobran}")
            print(f"      salida: {salida!r:.180}")
    return ok


if __name__ == "__main__":
    print("[TEST] Formateador de alertas: nada no-critico puede quedar mudo")
    if test_formateador():
        print("\n[OK] Todos los tests pasaron")
        sys.exit(0)
    print("\n[ERROR] Hay tests fallidos")
    sys.exit(1)

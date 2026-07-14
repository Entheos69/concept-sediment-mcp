"""
Formateo narrativo de las alertas del Humandato (para el LLM).

Extraido de server.py (2026-07-14) para que sea TESTEABLE sin fastmcp ni BD:
format_alerts() es una funcion pura dict -> str. Vivia dentro del cuerpo de la
tool @mcp.tool cs_get_alerts, donde ningun test podia alcanzarla — y ahi
sobrevivio el bug del early-return (ver abajo).
"""
from discard_queries import (
    CS_DISCARD_PROMO_AGENTS,
    CS_DISCARD_PROMO_OCCURRENCES,
    CS_DISCARD_STALE_DAYS,
)


def format_alerts(alerts: dict) -> str:
    """Renderiza el dict de get_all_alerts() como texto narrativo.

    Args:
        alerts: salida de humandato_queries.get_all_alerts()

    Returns:
        str: alertas en formato legible para el LLM
    """
    lines = []
    summary = alerts["summary"]

    discards = alerts["relation_discards"]
    discards_real = discards.get("total_pending", 0)
    discards_real = discards.get("total_pending_real", discards_real)

    # El silencio solo es legitimo si NO hay alerta de NINGUN tipo.
    # BUG (2026-07-14): el early-return se disparaba con status == "stable", y
    # status solo mira criticas (critical_alerts = fracturas criticas + vacunas
    # severity=critical). Efecto: fracturas moderadas/bajas y vacunas high/medium
    # se calculaban y se tiraban sin imprimir -> "Sin alertas" con alertas vivas.
    # Mismo linaje que el gemelo VCM: el instrumento mide bien y se calla.
    total_alertas = (
        alerts["fractures"]["total"]
        + len(alerts["missing_vaccines"])
        + discards_real
    )
    if total_alertas == 0:
        return "Humandato: sistema inmunologico estable. Sin alertas."

    criticas = summary["critical_alerts"]
    no_criticas = total_alertas - criticas
    lines.append(
        f"Humandato: {criticas} alerta(s) critica(s), "
        f"{no_criticas} no critica(s)"
    )
    lines.append("")

    if alerts["fractures"]["total"] > 0:
        lines.append("FRACTURAS (conceptos debilitados con dependientes activos):")
        for etiqueta, clave in (
            ("CRITICA", "criticas"),
            ("MODERADA", "moderadas"),
            ("BAJA", "bajas"),
        ):
            for f in alerts["fractures"][clave]:
                deps = ", ".join(d["name"] for d in f["active_dependents"])
                lines.append(
                    f"  [{etiqueta}] {f['concept']} [{f['status']}]: "
                    f"dependientes activos: {deps}"
                )
        lines.append("")

    if alerts["missing_vaccines"]:
        lines.append("VACUNAS FALTANTES (directivas sin representacion):")
        for v in alerts["missing_vaccines"]:
            sev = v["severity"].upper()
            lines.append(f"  [{sev}] {v['category']}: {v['directive']}")
            if v.get("failure_history"):
                lines.append(f"    Historial: {v['failure_history']}")
        lines.append("")

    # C2d F47: Aristas pending (RelationDiscard)
    if discards["total_pending"] > 0:
        lines.append("ARISTAS PENDING (RelationDiscard - F47 C2d):")
        lines.append(f"  Total pending: {discards['total_pending']}")
        # F47-D1.1: distinguir productivas de smokes
        total_real = discards.get("total_pending_real", discards["total_pending"])
        if total_real != discards["total_pending"]:
            lines.append(f"  Productivas (excluyendo smokes): {total_real}")
            if total_real == 0:
                lines.append(
                    "  [INFO] Todos los pending provienen de sesiones smoke. "
                    "Sin alerta productiva."
                )
        lines.append("  Por reason:")
        lines.append(f"    - unknown_type: {discards['by_reason']['unknown_type']}")
        lines.append(
            f"    - target_not_found: {discards['by_reason']['target_not_found']}"
        )

        if discards["top_invalid_types"]:
            lines.append("  Top 3 tipos invalidos sin alias:")
            for i, t in enumerate(discards["top_invalid_types"], 1):
                lines.append(
                    f"    {i}. {t['type']} "
                    f"({t['occurrences']} ocurrencias x {t['agents']} agentes)"
                )

        if discards["oldest_pending_days"] is not None:
            lines.append(f"  Mas antiguo: {discards['oldest_pending_days']} dias")
            if discards["oldest_pending_days"] > CS_DISCARD_STALE_DAYS:
                lines.append(
                    f"    [ALERTA] Supera umbral de {CS_DISCARD_STALE_DAYS} dias"
                )

        if discards["types_meeting_promo_rule"] > 0:
            lines.append(
                f"  Cumple regla B1.2 (>={CS_DISCARD_PROMO_OCCURRENCES} x "
                f">={CS_DISCARD_PROMO_AGENTS}): "
                f"{discards['types_meeting_promo_rule']} tipo(s)"
            )

        lines.append("")

    return "\n".join(lines)

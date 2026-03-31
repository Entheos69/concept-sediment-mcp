"""
Humandato Queries — funciones de consulta para alertas inmunologicas.

Versión SQL pura para MCP Server (sin Django ORM).

Dos tipos de alerta:
  1. Fracturas: concepto dormant/archived con dependientes activos
  2. Vacunas faltantes: directivas VCM sin representacion en el grafo
"""
from typing import Optional

from sqlalchemy import text

from db import get_session


# ════════════════════════════════════════════════════════════════
# VCM: Vector de Conocimiento Minimo
# ════════════════════════════════════════════════════════════════

VCM_DIRECTIVES = [
    {
        "name": "emoji",
        "category": "encoding",
        "severity": "critical",
        "directive": (
            "NUNCA usar emojis en codigo, management commands, ni outputs "
            "de consola. Windows no soporta UTF-8 extendido. "
            "Causa AttributeError/UnicodeEncodeError. "
            "Usar marcadores ASCII: [OK], [ERROR], [WARN], +, -, ~"
        ),
        "min_weight": 1.0,
        "failure_history": "Recurrente. Violada en S064.",
    },
    {
        "name": "stdout.flush",
        "category": "encoding",
        "severity": "critical",
        "directive": (
            "En management commands con output progresivo, usar "
            "self.stdout.write() + self.stdout.flush(). "
            "print() sin flush buferea en Windows."
        ),
        "min_weight": 0.7,
        "failure_history": "Documentada en sistema de diseno.",
    },
    {
        "name": "git push",
        "category": "workflow",
        "severity": "critical",
        "directive": (
            "Git push NUNCA automatico. Requiere autorizacion explicita. "
            "Igualmente prohibido: resumenes automaticos, "
            "modificar start.sh sin consultar."
        ),
        "min_weight": 1.0,
        "failure_history": "Violada frecuentemente.",
    },
    {
        "name": "3 intentos",
        "category": "workflow",
        "severity": "critical",
        "directive": (
            "Si algo falla 3 veces, PARAR y preguntar. "
            "NO iterar con variaciones infinitas. "
            "Contar intentos activamente."
        ),
        "min_weight": 1.0,
        "failure_history": "Violada 3 veces (S17, S18, S20).",
    },
    {
        "name": "YAML",
        "category": "concept_sediment",
        "severity": "critical",
        "directive": (
            "Cierre sesion: (1) generar YAML, (2) Write tool, "
            "(3) verificar ls -la, (4) confirmar a Guardian. "
            "Evidencia fisica obligatoria."
        ),
        "min_weight": 0.7,
        "failure_history": "S060: 0 YAML. S061: sin archivo. S063: confabulacion.",
    },
    {
        "name": "delete()",
        "category": "django_db",
        "severity": "high",
        "directive": (
            "NUNCA usar .delete() en produccion sin autorizacion. "
            "Preferir soft-delete o archivado."
        ),
        "min_weight": 0.3,
        "failure_history": "Documentada en sistema de diseno.",
    },
    {
        "name": "catalogo",
        "category": "css_design",
        "severity": "medium",
        "directive": (
            "Usar SIEMPRE catalogo de componentes con "
            "prefijos at-/mo-/or-. NUNCA duplicar."
        ),
        "min_weight": 0.3,
        "failure_history": "Documentada en sistema de diseno.",
    },
]


# ════════════════════════════════════════════════════════════════
# FRACTURAS: conceptos debilitados con dependientes activos
# ════════════════════════════════════════════════════════════════

FRACTURES_SQL = """
SELECT
    c.id AS concept_id,
    c.name AS concept_name,
    c.status AS concept_status,
    c.weight AS concept_weight,
    c.type AS concept_type,
    c.last_seen_at,
    dep.id AS dependent_id,
    dep.name AS dependent_name,
    dep.weight AS dependent_weight,
    cr.relation_type,
    ARRAY_AGG(DISTINCT d.slug) FILTER (WHERE d.slug IS NOT NULL) AS concept_domains,
    ARRAY_AGG(DISTINCT dd.slug) FILTER (WHERE dd.slug IS NOT NULL) AS dependent_domains
FROM graph_concept c
JOIN graph_conceptrelation cr ON cr.target_id = c.id
JOIN graph_concept dep ON dep.id = cr.source_id
LEFT JOIN graph_concept_domains cd ON cd.concept_id = c.id
LEFT JOIN graph_domain d ON d.id = cd.domain_id
LEFT JOIN graph_concept_domains cdd ON cdd.concept_id = dep.id
LEFT JOIN graph_domain dd ON dd.id = cdd.domain_id
WHERE c.status IN ('dormant', 'archived')
  AND cr.relation_type = 'depends_on'
  AND dep.status = 'active'
GROUP BY c.id, dep.id, cr.relation_type
ORDER BY c.weight DESC, dep.weight DESC
"""


def get_fractures(project: Optional[str] = None) -> list[dict]:
    """Detecta fracturas: conceptos debilitados con dependientes activos."""
    session = get_session()
    try:
        sql = FRACTURES_SQL
        params = {}

        if project:
            sql = sql.replace(
                "WHERE c.status",
                "WHERE :project = ANY(c.projects) AND c.status"
            )
            params["project"] = project

        rows = session.execute(text(sql), params).fetchall()

        # Agrupar por concepto
        fracturas = {}
        for row in rows:
            cid = row.concept_id
            if cid not in fracturas:
                fracturas[cid] = {
                    "concept": row.concept_name,
                    "status": row.concept_status,
                    "weight": round(row.concept_weight, 1),
                    "type": row.concept_type,
                    "domains": row.concept_domains or [],
                    "last_seen": (
                        row.last_seen_at.strftime("%Y-%m-%d")
                        if row.last_seen_at else "unknown"
                    ),
                    "active_dependents": [],
                }

            # Calcular shared domains
            concept_domains = set(row.concept_domains or [])
            dependent_domains = set(row.dependent_domains or [])
            shared = list(concept_domains & dependent_domains)

            if shared:
                fracturas[cid]["active_dependents"].append({
                    "name": row.dependent_name,
                    "weight": round(row.dependent_weight, 1),
                    "shared_domains": shared,
                })

        # Filtrar conceptos sin dependientes con dominios compartidos
        result = [f for f in fracturas.values() if f["active_dependents"]]
        result.sort(key=lambda a: len(a["active_dependents"]), reverse=True)
        return result

    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# VACUNAS FALTANTES: directivas sin representación en el grafo
# ════════════════════════════════════════════════════════════════

VACCINES_CHECK_SQL = """
SELECT
    c.name,
    c.weight,
    c.status
FROM graph_concept c
WHERE c.name ILIKE :pattern
  AND c.status = 'active'
ORDER BY c.weight DESC
LIMIT 1
"""


def get_missing_vaccines(project: Optional[str] = None) -> list[dict]:
    """Detecta vacunas faltantes: directivas VCM sin representación suficiente."""
    session = get_session()
    try:
        missing = []

        for vcm in VCM_DIRECTIVES:
            pattern = f"%{vcm['name']}%"
            params = {"pattern": pattern}

            sql = VACCINES_CHECK_SQL
            if project:
                sql = sql.replace(
                    "WHERE c.name",
                    "WHERE :project = ANY(c.projects) AND c.name"
                )
                params["project"] = project

            row = session.execute(text(sql), params).fetchone()

            # Si existe concepto con peso suficiente, no es vacuna faltante
            if row and row.weight >= vcm["min_weight"]:
                continue

            entry = {
                "category": vcm["category"],
                "severity": vcm["severity"],
                "directive": vcm["directive"],
                "failure_history": vcm["failure_history"],
            }

            if row:
                entry["found_concept"] = row.name
                entry["found_weight"] = round(row.weight, 1)
                entry["reason"] = (
                    f"Peso insuficiente: {row.weight:.1f} < {vcm['min_weight']}"
                )
            else:
                entry["found_concept"] = None
                entry["found_weight"] = 0.0
                entry["reason"] = "Sin representacion en el grafo"

            missing.append(entry)

        severity_order = {"critical": 0, "high": 1, "medium": 2}
        missing.sort(key=lambda m: severity_order.get(m["severity"], 9))
        return missing

    finally:
        session.close()


# ════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL: get_all_alerts
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# SISTEMA INMUNOLÓGICO ACTIVO: Severidad + Auto-reparación
# Implementado: 2026-03-28 (S65)
# ════════════════════════════════════════════════════════════════

REPAIR_CHECK_SQL = """
SELECT COUNT(*) as count
FROM graph_conceptrelation cr
JOIN graph_concept source ON source.id = cr.source_id
WHERE cr.target_id = :concept_id
  AND source.status = 'active'
  AND cr.relation_type IN ('refines', 'resolves', 'instance_of')
"""


def _fractura_reparada(concept_id: int) -> bool:
    """
    Una fractura se considera reparada si existe un concepto activo
    que tiene relación refines/resolves/instance_of hacia el concepto
    debilitado. Eso significa que el eslabón genealógico existe.

    Args:
        concept_id: ID del concepto debilitado

    Returns:
        bool: True si existe eslabón genealógico reparador
    """
    session = get_session()
    try:
        result = session.execute(
            text(REPAIR_CHECK_SQL),
            {"concept_id": concept_id}
        ).fetchone()
        if not result:
            return False
        return result.count > 0
    finally:
        session.close()


def _calcular_severidad(fractura_dict: dict) -> str:
    """
    Clasifica severidad de una fractura.

    Criterios:
    - CRITICA: Concepto debilitado con weight > 1.0, O dependientes
      activos con weight > 1.0 (alta consolidación antes de decaer)
    - MODERADA: Concepto debilitado con dependientes activos
      de weight <= 1.0. Señala evolución no documentada.
    - BAJA: Dependiente con weight bajo (puede ser falso positivo
      o feature reciente)

    Args:
        fractura_dict: Dict con información de fractura

    Returns:
        str: 'critica', 'moderada', o 'baja'
    """
    dependientes = fractura_dict["active_dependents"]
    concept_weight = fractura_dict["weight"]

    # Peso máximo entre dependientes activos
    max_dep_weight = max(
        (d["weight"] for d in dependientes),
        default=0
    )

    # Concepto altamente consolidado que decayó
    if concept_weight > 1.0 or max_dep_weight > 1.0:
        return 'critica'

    # Dependiente con pocas ocurrencias = posible falso positivo
    if max_dep_weight <= 0.5:
        return 'baja'

    return 'moderada'


def get_all_alerts(project: Optional[str] = None) -> dict:
    """Retorna todas las alertas del sistema inmunológico con
    clasificación por severidad y auto-filtrado de fracturas reparadas.

    Args:
        project: filtrar por proyecto (ej: "inducop")

    Returns:
        dict con fractures (clasificadas por severidad),
        missing_vaccines, summary
    """
    fractures_raw = get_fractures(project)
    vaccines = get_missing_vaccines(project)

    # Clasificar fracturas por severidad y filtrar reparadas
    criticas = []
    moderadas = []
    bajas = []

    session = get_session()
    try:
        for fractura in fractures_raw:
            # Obtener concept_id para verificar reparación
            # (ya tenemos concept_name, necesitamos buscar el ID)
            result = session.execute(
                text("SELECT id FROM graph_concept WHERE name = :name LIMIT 1"),
                {"name": fractura["concept"]}
            ).fetchone()

            if not result:
                continue

            concept_id = result.id

            # Si fractura está reparada, no reportarla
            if _fractura_reparada(concept_id):
                continue

            # Clasificar por severidad
            severidad = _calcular_severidad(fractura)

            if severidad == 'critica':
                criticas.append(fractura)
            elif severidad == 'moderada':
                moderadas.append(fractura)
            else:
                bajas.append(fractura)

    finally:
        session.close()

    # Calcular conteos
    total_fractures = len(criticas) + len(moderadas) + len(bajas)
    critical_alerts = (
        len(criticas)
        + len([v for v in vaccines if v["severity"] == "critical"])
    )

    # Determinar status
    if len(criticas) >= 5:
        status = "critical"
    elif len(criticas) >= 3:
        status = "warning"
    elif critical_alerts == 0:
        status = "stable"
    else:
        status = "vulnerable"

    return {
        "fractures": {
            "criticas": criticas,
            "moderadas": moderadas,
            "bajas": bajas,
            "total": total_fractures,
        },
        "missing_vaccines": vaccines,
        "summary": {
            "fractures_count": total_fractures,
            "fractures_criticas": len(criticas),
            "fractures_moderadas": len(moderadas),
            "fractures_bajas": len(bajas),
            "missing_vaccines_count": len(vaccines),
            "critical_alerts": critical_alerts,
            "status": status,
        },
    }

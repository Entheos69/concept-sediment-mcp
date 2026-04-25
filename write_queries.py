"""
Concept Sediment MCP — Write Queries

Tools de escritura. Cada write registra entrada en mcp_audit_log
(append-only) en la misma transacción.

Disciplinas compensatorias del Estratega (RESPUESTA §2):
  §2.1 Módulo separado de queries.py / humandato_queries.py.
  §2.2 README declara catálogo write explícito (cs_record_*, cs_promote_*).
  §2.3 Audit log append-only obligatorio en cada write.

Prefijos: cs_record_*, cs_promote_*.

Per protocolo Estratega §4 y schema D2 agnóstico al operador
(concepto active w:1.0): measurements NO se sedimentan en grafo
conceptual. Viven en tabla aparte (graph_measurement) fuera del
espacio de búsqueda semántica.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy import text

from db import get_session
from audit_queries import write_audit_entry

logger = logging.getLogger(__name__)


# ENUM válido — espejo del modelo Django Measurement
# (concept-sediment/graph/migrations/0005_add_measurements.py)
VALID_OUTCOMES = {
    "resolvio",
    "resolvio_parcial",
    "no_resolvio",
    "aun_no_observable",
}


def record_measurement(
    contexto: str,
    outcome: str,
    contribucion_ia: str = "",
    contribucion_humana: str = "",
    project: str = "",
    domains: Optional[list[str]] = None,
    agent: str = "unknown",
) -> dict:
    """Registra una medición compuesta IA-humano.

    Per protocolo Estratega §4 y schema D2 agnóstico al operador.
    NO sedimenta en grafo conceptual — measurements viven en tabla
    aparte (graph_measurement), fuera del espacio de búsqueda semántica.

    Validaciones:
        - outcome ∈ VALID_OUTCOMES
        - contexto no vacío
        - todos los domain slugs (si provistos) existen en graph_domain

    Transacción atómica: INSERT measurement + INSERT m2m domains +
    INSERT audit log se commitean juntos. Si algo falla, todo se
    rollbackea y se registra audit log de error en sesión separada.

    Args:
        contexto: descripción del problema/sesión donde ocurrió la medición
        outcome: uno de VALID_OUTCOMES
        contribucion_ia: aporte de la IA (puede ser "")
        contribucion_humana: aporte del humano (puede ser "")
        project: tag de proyecto (ej: "inducop", "concept-sediment-mcp")
        domains: lista de slugs de graph_domain. Cada slug debe existir.
        agent: caller declara su identidad

    Returns:
        {"id": "<uuid>", "created_at": "<iso>", "audit_id": "<uuid>"}

    Raises:
        ValueError: outcome inválido, contexto vacío, o domain inexistente
    """
    payload = {
        "contexto": contexto,
        "contribucion_ia": contribucion_ia,
        "contribucion_humana": contribucion_humana,
        "outcome": outcome,
        "project": project,
        "domains": domains or [],
        "agent": agent,
    }

    if outcome not in VALID_OUTCOMES:
        error_msg = (
            f"Invalid outcome: {outcome!r}. "
            f"Must be one of {sorted(VALID_OUTCOMES)}"
        )
        write_audit_entry(
            agent=agent,
            tool_name="cs_record_measurement",
            payload=payload,
            success=False,
            error_message=error_msg,
        )
        raise ValueError(error_msg)

    if not contexto or not contexto.strip():
        error_msg = "contexto must be non-empty"
        write_audit_entry(
            agent=agent,
            tool_name="cs_record_measurement",
            payload=payload,
            success=False,
            error_message=error_msg,
        )
        raise ValueError(error_msg)

    measurement_id = uuid.uuid4()

    session = get_session()
    try:
        domain_ids = []
        if domains:
            for slug in domains:
                result = session.execute(
                    text("SELECT id FROM graph_domain WHERE slug = :slug"),
                    {"slug": slug},
                )
                row = result.first()
                if row is None:
                    raise ValueError(f"Domain slug not found: {slug!r}")
                domain_ids.append(row[0])

        result = session.execute(
            text("""
                INSERT INTO graph_measurement
                (id, contexto, contribucion_ia, contribucion_humana,
                 outcome, project, created_at)
                VALUES
                (:id, :contexto, :contribucion_ia, :contribucion_humana,
                 :outcome, :project, NOW())
                RETURNING created_at
            """),
            {
                "id": measurement_id,
                "contexto": contexto,
                "contribucion_ia": contribucion_ia,
                "contribucion_humana": contribucion_humana,
                "outcome": outcome,
                "project": project,
            },
        )
        created_at = result.scalar()

        for domain_id in domain_ids:
            session.execute(
                text("""
                    INSERT INTO graph_measurement_domains
                    (measurement_id, domain_id)
                    VALUES (:measurement_id, :domain_id)
                """),
                {"measurement_id": measurement_id, "domain_id": domain_id},
            )

        audit_id = write_audit_entry(
            agent=agent,
            tool_name="cs_record_measurement",
            payload=payload,
            target_id=measurement_id,
            target_table="graph_measurement",
            success=True,
            session=session,
        )

        session.commit()
        logger.info("Measurement %s recorded by %s", measurement_id, agent)

        return {
            "id": str(measurement_id),
            "created_at": created_at.isoformat() if created_at else None,
            "audit_id": str(audit_id),
        }

    except Exception as e:
        session.rollback()
        write_audit_entry(
            agent=agent,
            tool_name="cs_record_measurement",
            payload=payload,
            success=False,
            error_message=str(e),
        )
        logger.error("Failed to record measurement: %s", e)
        raise
    finally:
        session.close()

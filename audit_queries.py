"""
Concept Sediment MCP — Audit Log Queries

Init de tabla mcp_audit_log + read tools sobre audit log.
APPEND-ONLY por convención de código: solo INSERTs, nunca UPDATE/DELETE.

Disciplina §2.3 del Estratega (RESPUESTA_ESTRATEGA_read_only_mcp_2026-04-25.md):
cada invocación de cs_record_*/cs_promote_* registra timestamp, agente,
payload, target_id. Consultable vía cs_get_audit_log.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import text

from db import get_session

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def init_audit_log_table() -> None:
    """Crea la tabla mcp_audit_log si no existe (idempotente).

    Ejecutar al startup del MCP server antes de aceptar requests.
    Lee el SQL de migrations/001_audit_log.sql y ejecuta cada statement.
    """
    sql_file = MIGRATIONS_DIR / "001_audit_log.sql"
    if not sql_file.exists():
        raise FileNotFoundError(f"Migration file not found: {sql_file}")

    sql_content = sql_file.read_text(encoding="utf-8")

    session = get_session()
    try:
        for stmt in sql_content.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                session.execute(text(stmt))
        session.commit()
        logger.info("mcp_audit_log table initialized (idempotent)")
    except Exception as e:
        session.rollback()
        logger.error("Failed to init audit log: %s", e)
        raise
    finally:
        session.close()


def write_audit_entry(
    agent: str,
    tool_name: str,
    payload: dict,
    target_id: Optional[uuid.UUID] = None,
    target_table: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    session=None,
) -> uuid.UUID:
    """Inserta entrada al audit log. APPEND-ONLY.

    Si se pasa session existente, ejecuta dentro de esa transacción —
    caller decide commit/rollback. Si session=None, abre y commitea
    su propia sesión (uso típico: error path fuera del flujo principal).
    """
    audit_id = uuid.uuid4()
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)

    own_session = session is None
    if own_session:
        session = get_session()

    try:
        session.execute(
            text("""
                INSERT INTO mcp_audit_log
                (id, agent, tool_name, payload_json, target_id, target_table,
                 success, error_message)
                VALUES
                (:id, :agent, :tool_name, CAST(:payload_json AS JSONB),
                 :target_id, :target_table, :success, :error_message)
            """),
            {
                "id": audit_id,
                "agent": agent,
                "tool_name": tool_name,
                "payload_json": payload_json,
                "target_id": target_id,
                "target_table": target_table,
                "success": success,
                "error_message": error_message,
            },
        )
        if own_session:
            session.commit()
    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()

    return audit_id


def get_audit_log(
    agent: Optional[str] = None,
    tool_name: Optional[str] = None,
    target_id: Optional[str] = None,
    success: Optional[bool] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> list:
    """Read-only query sobre mcp_audit_log con filtros.

    Args:
        agent: filtrar por agent (CodeMCP, CodeCS, ...)
        tool_name: filtrar por nombre exacto del tool
        target_id: filtrar por UUID del target (string)
        success: filtrar por éxito/fracaso
        since: ISO datetime — solo entradas posteriores
        limit: max 200, default 50
    """
    where_clauses = []
    params_dict = {}

    if agent is not None:
        where_clauses.append("agent = :agent")
        params_dict["agent"] = agent
    if tool_name is not None:
        where_clauses.append("tool_name = :tool_name")
        params_dict["tool_name"] = tool_name
    if target_id is not None:
        where_clauses.append("target_id = CAST(:target_id AS UUID)")
        params_dict["target_id"] = target_id
    if success is not None:
        where_clauses.append("success = :success")
        params_dict["success"] = success
    if since is not None:
        where_clauses.append("timestamp >= CAST(:since AS TIMESTAMP)")
        params_dict["since"] = since

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
        SELECT id, timestamp, agent, tool_name, payload_json, target_id,
               target_table, success, error_message
        FROM mcp_audit_log
        {where_sql}
        ORDER BY timestamp DESC
        LIMIT :limit
    """
    params_dict["limit"] = max(1, min(limit, 200))

    session = get_session()
    try:
        result = session.execute(text(sql), params_dict)
        rows = []
        for row in result.mappings():
            rows.append({
                "id": str(row["id"]),
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                "agent": row["agent"],
                "tool_name": row["tool_name"],
                "payload": row["payload_json"],
                "target_id": str(row["target_id"]) if row["target_id"] else None,
                "target_table": row["target_table"],
                "success": row["success"],
                "error_message": row["error_message"],
            })
        return rows
    finally:
        session.close()

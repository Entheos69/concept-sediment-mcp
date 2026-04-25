-- Concept Sediment MCP — Audit Log
--
-- Tabla append-only para auditoría de write tools del MCP server.
-- Aplicada al startup vía init_audit_log_table() (idempotente).
--
-- Convención de naming: prefijo mcp_* para distinguir del dominio del
-- grafo conceptual (graph_*, mantenido por Django).
--
-- UUIDs generados en Python (uuid.uuid4()), no en SQL — evita dependencia
-- de extensiones pgcrypto/uuid-ossp.

CREATE TABLE IF NOT EXISTS mcp_audit_log (
    id            UUID         PRIMARY KEY,
    timestamp     TIMESTAMP    NOT NULL DEFAULT NOW(),
    agent         VARCHAR(50)  NOT NULL,
    tool_name     VARCHAR(100) NOT NULL,
    payload_json  JSONB        NOT NULL,
    target_id     UUID,
    target_table  VARCHAR(50),
    success       BOOLEAN      NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON mcp_audit_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_agent     ON mcp_audit_log (agent);
CREATE INDEX IF NOT EXISTS idx_audit_log_tool_name ON mcp_audit_log (tool_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_target_id ON mcp_audit_log (target_id) WHERE target_id IS NOT NULL;

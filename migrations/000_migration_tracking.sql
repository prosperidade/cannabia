-- Migration tracking table
-- Registra quais migrations foram aplicadas, quando, e seu checksum.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(50)  PRIMARY KEY,
    filename    VARCHAR(255) NOT NULL,
    applied_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checksum    VARCHAR(64)  NOT NULL
);

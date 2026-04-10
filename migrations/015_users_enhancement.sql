-- Migration 015: Enhance users table for admin management
-- Adds profile fields needed by /admin/users endpoint

ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

INSERT INTO schema_migrations (version, filename, applied_at, checksum)
VALUES ('015', '015_users_enhancement.sql', NOW(), '')
ON CONFLICT DO NOTHING;

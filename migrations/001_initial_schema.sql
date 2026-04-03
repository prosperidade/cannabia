CREATE TABLE IF NOT EXISTS clinics (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(64) NOT NULL UNIQUE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patients (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) DEFAULT NULL,
  phone VARCHAR(20) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  -- We'll skip foreign keys initially to avoid circular dependency pain, or add it:
  -- CONSTRAINT fk_patients_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(id)
);

CREATE TABLE IF NOT EXISTS ai_prompt_versions (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  version VARCHAR(50) NOT NULL,
  prompt_text TEXT NOT NULL,
  hash VARCHAR(64) NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'Medico',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_clinics (
  user_id INT NOT NULL,
  clinic_id INT NOT NULL,
  role VARCHAR(50) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, clinic_id)
);

CREATE TABLE IF NOT EXISTS appointments (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  patient_id INT NOT NULL,
  appointment_date TIMESTAMP NOT NULL,
  status VARCHAR(50) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incoming_messages (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  sender VARCHAR(50) DEFAULT NULL,
  contact_name VARCHAR(100) DEFAULT NULL,
  message_text TEXT,
  timestamp VARCHAR(50) DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS message_status_updates (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  message_id VARCHAR(100) NOT NULL,
  status VARCHAR(50) NOT NULL,
  timestamp VARCHAR(50) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_audit_logs (
  id SERIAL PRIMARY KEY,
  patient_id INT NOT NULL,
  clinic_id INT NOT NULL DEFAULT 1,
  request_id VARCHAR(36) NOT NULL,
  user_id VARCHAR(50) DEFAULT NULL,
  endpoint VARCHAR(100) NOT NULL,
  input_payload JSONB NOT NULL,
  output_payload JSONB DEFAULT NULL,
  status VARCHAR(20) NOT NULL,
  error_message TEXT,
  model VARCHAR(50) NOT NULL,
  prompt_version VARCHAR(50) NOT NULL,
  prompt_hash VARCHAR(64) NOT NULL,
  input_tokens INT DEFAULT NULL,
  output_tokens INT DEFAULT NULL,
  total_tokens INT DEFAULT NULL,
  clinical_time_ms INT DEFAULT NULL,
  treatment_time_ms INT DEFAULT NULL,
  report_time_ms INT DEFAULT NULL,
  total_time_ms INT DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estimated_cost_usd DECIMAL(10,6) DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  patient_id INT DEFAULT NULL,
  message TEXT,
  alert_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS medical_history (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  patient_id INT NOT NULL,
  history TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monitoring (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  patient_id INT NOT NULL,
  status VARCHAR(50) DEFAULT NULL,
  notes TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scientific_references (
  id SERIAL PRIMARY KEY,
  reference_title VARCHAR(255) DEFAULT NULL,
  reference_url VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS treatment_plans (
  id SERIAL PRIMARY KEY,
  clinic_id INT NOT NULL DEFAULT 1,
  patient_id INT NOT NULL,
  plan_description TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Inserir a clínica padrão
INSERT INTO clinics (name, slug, is_active) 
VALUES ('Clínica Cannabia', 'cannabia', TRUE) 
ON CONFLICT (slug) DO NOTHING;

-- Inserir o usuário administrador (Usuário: admin | Senha: admin123)
-- Nota: O hash abaixo é para a senha 'admin123' usando o padrão do sistema
INSERT INTO users (username, password_hash, role, is_active) 
VALUES ('admin', '$2b$12$gp4/sX68FDK9IFOoU/wPSeMp/TqRpH5JXfHal4Cmccm6RIuvz49Qe', 'Medico', TRUE)
ON CONFLICT (username) DO NOTHING;

-- Vincular o admin à clínica (ID 1)
INSERT INTO user_clinics (user_id, clinic_id, role, is_default)
VALUES (1, 1, 'clinic_admin', TRUE)
ON CONFLICT DO NOTHING;

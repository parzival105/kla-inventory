-- KLA Business Suite — Supabase Setup
-- Jalankan di: dashboard.supabase.com → SQL Editor → New Query → Run

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, full_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('super_admin','area_manager','store_leader','sales')),
  branch TEXT, area TEXT, is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(), last_login TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY, user_id BIGINT, username TEXT,
  action TEXT NOT NULL, detail TEXT, created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS analysis_store (
  id BIGINT PRIMARY KEY DEFAULT 1, filename TEXT, uploaded_by TEXT,
  sku_count INTEGER DEFAULT 0, uploaded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS build_history (
  id BIGSERIAL PRIMARY KEY, user_id BIGINT, branch TEXT,
  build_name TEXT, build_type TEXT, budget NUMERIC, total_price NUMERIC,
  ai_notes TEXT, created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO users (username,password_hash,full_name,role,is_active)
VALUES ('admin','87713280795750557dae5dce27b090dc28bb9b2324314ebb68fd0d4545ca9f73','Super Administrator','super_admin',true)
ON CONFLICT (username) DO NOTHING;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE build_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sa" ON users; CREATE POLICY "sa" ON users FOR ALL USING (true);
DROP POLICY IF EXISTS "sa" ON sessions; CREATE POLICY "sa" ON sessions FOR ALL USING (true);
DROP POLICY IF EXISTS "sa" ON audit_log; CREATE POLICY "sa" ON audit_log FOR ALL USING (true);
DROP POLICY IF EXISTS "sa" ON analysis_store; CREATE POLICY "sa" ON analysis_store FOR ALL USING (true);
DROP POLICY IF EXISTS "sa" ON build_history; CREATE POLICY "sa" ON build_history FOR ALL USING (true);

SELECT (SELECT COUNT(*) FROM users) AS total_users, 'Setup complete!' AS status;

-- Branch Management Table (tambahkan ini di SQL Editor Supabase)
CREATE TABLE IF NOT EXISTS branches (
  id        BIGSERIAL PRIMARY KEY,
  code      TEXT UNIQUE NOT NULL,
  name      TEXT NOT NULL,
  area      TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "sa" ON branches;
CREATE POLICY "sa" ON branches FOR ALL USING (true);

-- Insert default 13 cabang KLA
INSERT INTO branches (code, name, area, is_active) VALUES
  ('SMG','Semarang','Area 2 — Jawa Tengah Timur',true),
  ('YK','Yogyakarta','Area 2 — Jawa Tengah Timur',true),
  ('SLA','Slawi','Area 1 — Jawa Tengah Barat',true),
  ('TGL','Tegal','Area 1 — Jawa Tengah Barat',true),
  ('PKL','Pekalongan','Area 1 — Jawa Tengah Barat',true),
  ('CRB','Cirebon','Area 1 — Jawa Tengah Barat',true),
  ('KDR','Kediri','Area 3 — Jawa Timur',true),
  ('NGL','Ngaliyan','Area 2 — Jawa Tengah Timur',true),
  ('SKH','Sukoharjo','Area 2 — Jawa Tengah Timur',true),
  ('MSBY','Surabaya Merr','Area 3 — Jawa Timur',true),
  ('MJK','Mojokerto','Area 3 — Jawa Timur',true),
  ('BSBY','Surabaya Babatan','Area 3 — Jawa Timur',true),
  ('PWT','Purwokerto','Area 1 — Jawa Tengah Barat',true)
ON CONFLICT (code) DO NOTHING;

SELECT COUNT(*) AS total_branches FROM branches;

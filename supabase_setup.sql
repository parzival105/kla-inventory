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

-- Online Presence Table
CREATE TABLE IF NOT EXISTS online_presence (
  user_id    BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  username   TEXT NOT NULL,
  full_name  TEXT NOT NULL,
  role       TEXT NOT NULL,
  branch     TEXT,
  last_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE online_presence ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "sa" ON online_presence;
CREATE POLICY "sa" ON online_presence FOR ALL USING (true);

-- Tambah kolom components ke build_history jika belum ada
ALTER TABLE build_history ADD COLUMN IF NOT EXISTS components TEXT DEFAULT '';

-- Status Deal / No Deal / Pending untuk tiap build PC
ALTER TABLE build_history ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
ALTER TABLE build_history ADD COLUMN IF NOT EXISTS status_note TEXT;
ALTER TABLE build_history ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMPTZ;

-- Stock Request Table
CREATE TABLE IF NOT EXISTS stock_requests (
  id           BIGSERIAL PRIMARY KEY,
  user_id      BIGINT REFERENCES users(id),
  username     TEXT NOT NULL,
  full_name    TEXT NOT NULL,
  branch       TEXT NOT NULL,
  branch_name  TEXT NOT NULL,
  product_name TEXT NOT NULL,
  qty          INTEGER NOT NULL DEFAULT 1,
  reason       TEXT,
  priority     TEXT DEFAULT 'Normal',
  status       TEXT DEFAULT 'pending',
  admin_note   TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ
);
ALTER TABLE stock_requests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "sa" ON stock_requests;
CREATE POLICY "sa" ON stock_requests FOR ALL USING (true);

-- ══════════════════════════════════════════════════════════════════════════════
-- PROJECT REQUEST MANAGEMENT
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS project_requests (
  id              BIGSERIAL PRIMARY KEY,
  project_number  TEXT UNIQUE NOT NULL,
  -- Customer
  customer_name   TEXT NOT NULL,
  customer_company TEXT,
  customer_pic    TEXT,
  customer_phone  TEXT,
  customer_email  TEXT,
  -- Sales
  branch          TEXT NOT NULL,
  branch_name     TEXT,
  sales_id        BIGINT REFERENCES users(id),
  sales_name      TEXT,
  -- Status & Priority
  status          TEXT NOT NULL DEFAULT 'new_request',
  priority        TEXT DEFAULT 'Medium',
  -- Value
  estimated_value NUMERIC DEFAULT 0,
  deal_value      NUMERIC DEFAULT 0,
  -- Dates
  deadline        DATE,
  deal_date       DATE,
  lost_date       DATE,
  lost_reason     TEXT,
  lost_note       TEXT,
  -- Meta
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_products (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT NOT NULL REFERENCES project_requests(id) ON DELETE CASCADE,
  brand           TEXT,
  part_number     TEXT,
  category        TEXT,
  product_name    TEXT NOT NULL,
  qty             INTEGER DEFAULT 1,
  budget_customer NUMERIC DEFAULT 0,
  customer_notes  TEXT,
  -- PM Review
  pm_available    TEXT,   -- 'yes','no','eol'
  pm_eol_reason   TEXT,
  pm_eol_status   TEXT,   -- 'end_of_life','end_of_sale','discontinue'
  pm_notes        TEXT,
  pm_reviewed_at  TIMESTAMPTZ,
  pm_reviewed_by  TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_replacement (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT NOT NULL REFERENCES project_requests(id) ON DELETE CASCADE,
  product_id      BIGINT REFERENCES project_products(id),
  original_brand  TEXT,
  original_model  TEXT,
  new_brand       TEXT,
  new_model       TEXT,
  new_category    TEXT,
  performance     TEXT,  -- 'equal','higher','lower'
  price_change    TEXT,
  pm_notes        TEXT,
  approved        BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_supplier (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT NOT NULL REFERENCES project_requests(id) ON DELETE CASCADE,
  supplier_name   TEXT NOT NULL,
  price_modal     NUMERIC DEFAULT 0,
  stock           INTEGER DEFAULT 0,
  lead_time       TEXT,
  moq             INTEGER DEFAULT 1,
  warranty        TEXT,
  notes           TEXT,
  is_selected     BOOLEAN DEFAULT false,
  added_by        TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_quotation (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT NOT NULL REFERENCES project_requests(id) ON DELETE CASCADE,
  quotation_number TEXT UNIQUE,
  product_name    TEXT,
  qty             INTEGER DEFAULT 1,
  price_modal     NUMERIC DEFAULT 0,
  price_sell      NUMERIC DEFAULT 0,
  margin_pct      NUMERIC DEFAULT 0,
  discount        NUMERIC DEFAULT 0,
  total_value     NUMERIC DEFAULT 0,
  status          TEXT DEFAULT 'draft',  -- draft,sent,revised,approved
  notes           TEXT,
  created_by      TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  sent_at         TIMESTAMPTZ,
  approved_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS project_followup (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT NOT NULL REFERENCES project_requests(id) ON DELETE CASCADE,
  followup_date   DATE NOT NULL,
  followup_time   TEXT,
  media           TEXT,   -- wa,phone,email,meeting
  result          TEXT,
  notes           TEXT,
  next_followup   DATE,
  created_by      TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_timeline (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT NOT NULL REFERENCES project_requests(id) ON DELETE CASCADE,
  actor           TEXT,
  action          TEXT NOT NULL,
  detail          TEXT,
  old_status      TEXT,
  new_status      TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_knowledge_base (
  id              BIGSERIAL PRIMARY KEY,
  original_brand  TEXT,
  original_model  TEXT NOT NULL,
  replacement_brand TEXT,
  replacement_model TEXT,
  reason          TEXT,
  supplier_name   TEXT,
  usage_count     INTEGER DEFAULT 1,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE project_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_replacement ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_supplier ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_quotation ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_followup ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_timeline ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_knowledge_base ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sa" ON project_requests;
DROP POLICY IF EXISTS "sa" ON project_products;
DROP POLICY IF EXISTS "sa" ON project_replacement;
DROP POLICY IF EXISTS "sa" ON project_supplier;
DROP POLICY IF EXISTS "sa" ON project_quotation;
DROP POLICY IF EXISTS "sa" ON project_followup;
DROP POLICY IF EXISTS "sa" ON project_timeline;
DROP POLICY IF EXISTS "sa" ON project_knowledge_base;

CREATE POLICY "sa" ON project_requests FOR ALL USING (true);
CREATE POLICY "sa" ON project_products FOR ALL USING (true);
CREATE POLICY "sa" ON project_replacement FOR ALL USING (true);
CREATE POLICY "sa" ON project_supplier FOR ALL USING (true);
CREATE POLICY "sa" ON project_quotation FOR ALL USING (true);
CREATE POLICY "sa" ON project_followup FOR ALL USING (true);
CREATE POLICY "sa" ON project_timeline FOR ALL USING (true);
CREATE POLICY "sa" ON project_knowledge_base FOR ALL USING (true);

SELECT 'Project Request Management tables created!' AS status;

-- ══════════════════════════════════════════════════════════════════════════════
-- PROJECT REQUEST MANAGEMENT — ADD-ON: Documents, Notifications, Logs
-- (Jalankan blok ini terpisah jika tabel di atas sudah pernah dibuat sebelumnya)
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS project_documents (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT NOT NULL REFERENCES project_requests(id) ON DELETE CASCADE,
  file_name       TEXT NOT NULL,
  storage_path    TEXT NOT NULL,
  file_size       BIGINT DEFAULT 0,
  content_type    TEXT,
  category        TEXT DEFAULT 'Lainnya',  -- 'Quotation','PO','Foto Produk','Lainnya'
  uploaded_by     TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_notifications (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT REFERENCES project_requests(id) ON DELETE CASCADE,
  notif_type      TEXT NOT NULL,   -- 'new_request','pm_late','supplier_late','quotation_late','followup_late','deadline_near','po_received','delivered','closed'
  message         TEXT NOT NULL,
  branch          TEXT,
  target_role     TEXT,            -- role that should see this notification, or '' for everyone relevant
  is_read         BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_logs (
  id              BIGSERIAL PRIMARY KEY,
  project_id      BIGINT REFERENCES project_requests(id) ON DELETE CASCADE,
  actor           TEXT,
  event           TEXT NOT NULL,   -- e.g. 'document_upload','document_delete','notification_run'
  detail          TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE project_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sa" ON project_documents;
DROP POLICY IF EXISTS "sa" ON project_notifications;
DROP POLICY IF EXISTS "sa" ON project_logs;

CREATE POLICY "sa" ON project_documents FOR ALL USING (true);
CREATE POLICY "sa" ON project_notifications FOR ALL USING (true);
CREATE POLICY "sa" ON project_logs FOR ALL USING (true);

-- Jangan lupa buat Storage Bucket "kla-inventory" (Public) jika belum ada,
-- dokumen project akan disimpan di path crm_docs/{project_id}/{filename}

SELECT 'Project Request Management add-on (documents, notifications, logs) created!' AS status;

-- ══════════════════════════════════════════════════════════════════════════════
-- PRMS — Product Request Management System (modul baru, menggantikan alur lama)
-- ══════════════════════════════════════════════════════════════════════════════

-- Izinkan role baru: product_manager, admin_purchasing, management
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN
  ('super_admin','area_manager','store_leader','sales','product_manager','admin_purchasing','management'));

CREATE TABLE IF NOT EXISTS prms_requests (
  id                  BIGSERIAL PRIMARY KEY,
  request_number      TEXT UNIQUE NOT NULL,
  customer_name       TEXT NOT NULL,
  branch              TEXT NOT NULL,
  branch_name         TEXT,
  sales_id            BIGINT REFERENCES users(id),
  sales_name          TEXT,
  request_date        DATE DEFAULT CURRENT_DATE,
  product_name        TEXT NOT NULL,
  brand               TEXT,
  part_number         TEXT,
  category            TEXT,
  qty                 INT DEFAULT 1,
  budget_customer      NUMERIC DEFAULT 0,
  ref_link            TEXT,
  customer_note       TEXT,
  urgency             TEXT DEFAULT 'Medium',
  status              TEXT NOT NULL DEFAULT 'draft',
  -- Store Leader review
  reject_reason       TEXT,
  -- PM review — produk ready
  pm_supplier         TEXT, pm_cost_price NUMERIC, pm_sell_price NUMERIC,
  pm_eta              TEXT, pm_supplier_stock TEXT,
  -- PM review — EOL / replacement
  repl_product_name   TEXT, repl_brand TEXT, repl_part_number TEXT, repl_spec TEXT,
  repl_reason         TEXT, repl_price NUMERIC, repl_price_diff NUMERIC,
  -- PM review — tidak ditemukan
  unable_reason       TEXT,
  -- Admin Purchasing
  pur_supplier        TEXT, pur_stock TEXT, pur_eta TEXT, pur_price NUMERIC, pur_po_number TEXT,
  -- Sales offer
  deal_qty            INT, deal_price NUMERIC, deal_est_closing DATE,
  nodeal_reason       TEXT, nodeal_note TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prms_history (
  id            BIGSERIAL PRIMARY KEY,
  request_id    BIGINT NOT NULL REFERENCES prms_requests(id) ON DELETE CASCADE,
  actor         TEXT,
  action        TEXT NOT NULL,
  note          TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prms_notifications (
  id            BIGSERIAL PRIMARY KEY,
  request_id    BIGINT REFERENCES prms_requests(id) ON DELETE CASCADE,
  target_role   TEXT,
  branch        TEXT,
  notif_type    TEXT NOT NULL,
  message       TEXT NOT NULL,
  is_read       BOOLEAN DEFAULT false,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prms_master_brand (
  id BIGSERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, is_active BOOLEAN DEFAULT true
);
CREATE TABLE IF NOT EXISTS prms_master_category (
  id BIGSERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, is_active BOOLEAN DEFAULT true
);
CREATE TABLE IF NOT EXISTS prms_master_supplier (
  id BIGSERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, contact TEXT, note TEXT, is_active BOOLEAN DEFAULT true
);
CREATE TABLE IF NOT EXISTS prms_master_reject_reason (
  id BIGSERIAL PRIMARY KEY, reason TEXT UNIQUE NOT NULL, is_active BOOLEAN DEFAULT true
);
CREATE TABLE IF NOT EXISTS prms_master_nodeal_reason (
  id BIGSERIAL PRIMARY KEY, reason TEXT UNIQUE NOT NULL, is_active BOOLEAN DEFAULT true
);

INSERT INTO prms_master_nodeal_reason (reason) VALUES
  ('Harga terlalu mahal'),('Customer batal beli'),('Customer membeli di tempat lain'),
  ('Barang terlalu lama datang'),('Produk tidak sesuai'),('Customer tidak jadi rakit'),
  ('Budget kurang'),('Spesifikasi berubah'),('Lainnya')
ON CONFLICT (reason) DO NOTHING;

ALTER TABLE prms_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE prms_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE prms_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE prms_master_brand ENABLE ROW LEVEL SECURITY;
ALTER TABLE prms_master_category ENABLE ROW LEVEL SECURITY;
ALTER TABLE prms_master_supplier ENABLE ROW LEVEL SECURITY;
ALTER TABLE prms_master_reject_reason ENABLE ROW LEVEL SECURITY;
ALTER TABLE prms_master_nodeal_reason ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sa" ON prms_requests;
DROP POLICY IF EXISTS "sa" ON prms_history;
DROP POLICY IF EXISTS "sa" ON prms_notifications;
DROP POLICY IF EXISTS "sa" ON prms_master_brand;
DROP POLICY IF EXISTS "sa" ON prms_master_category;
DROP POLICY IF EXISTS "sa" ON prms_master_supplier;
DROP POLICY IF EXISTS "sa" ON prms_master_reject_reason;
DROP POLICY IF EXISTS "sa" ON prms_master_nodeal_reason;

CREATE POLICY "sa" ON prms_requests FOR ALL USING (true);
CREATE POLICY "sa" ON prms_history FOR ALL USING (true);
CREATE POLICY "sa" ON prms_notifications FOR ALL USING (true);
CREATE POLICY "sa" ON prms_master_brand FOR ALL USING (true);
CREATE POLICY "sa" ON prms_master_category FOR ALL USING (true);
CREATE POLICY "sa" ON prms_master_supplier FOR ALL USING (true);
CREATE POLICY "sa" ON prms_master_reject_reason FOR ALL USING (true);
CREATE POLICY "sa" ON prms_master_nodeal_reason FOR ALL USING (true);

SELECT 'PRMS (Product Request Management System) tables created!' AS status;

-- ══════════════════════════════════════════════════════════════════════════════
-- PROJECT REQUEST — multi-produk per request (keranjang produk)
-- ══════════════════════════════════════════════════════════════════════════════

-- prms_requests sekarang jadi "parent" (data customer), produk dipindah ke item
ALTER TABLE prms_requests ALTER COLUMN product_name DROP NOT NULL;

CREATE TABLE IF NOT EXISTS prms_request_items (
  id                  BIGSERIAL PRIMARY KEY,
  request_id          BIGINT NOT NULL REFERENCES prms_requests(id) ON DELETE CASCADE,
  product_name        TEXT NOT NULL,
  brand               TEXT, part_number TEXT, category TEXT,
  qty                 INT DEFAULT 1,
  budget_customer     NUMERIC DEFAULT 0,
  ref_link            TEXT,
  urgency             TEXT DEFAULT 'Medium',
  status              TEXT NOT NULL DEFAULT 'waiting_product_review',
  -- PM review — produk ready
  pm_supplier TEXT, pm_cost_price NUMERIC, pm_sell_price NUMERIC, pm_eta TEXT, pm_supplier_stock TEXT,
  -- PM review — EOL / replacement
  repl_product_name TEXT, repl_brand TEXT, repl_part_number TEXT, repl_spec TEXT,
  repl_reason TEXT, repl_price NUMERIC, repl_price_diff NUMERIC,
  -- PM review — tidak ditemukan
  unable_reason TEXT,
  -- Admin Purchasing
  pur_supplier TEXT, pur_stock TEXT, pur_eta TEXT, pur_price NUMERIC, pur_po_number TEXT,
  -- Sales offer
  deal_qty INT, deal_price NUMERIC, deal_est_closing DATE,
  nodeal_reason TEXT, nodeal_note TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Kaitkan history & notifikasi ke item spesifik (nullable — tetap kompatibel dengan yang lama)
ALTER TABLE prms_history ADD COLUMN IF NOT EXISTS item_id BIGINT;
ALTER TABLE prms_notifications ADD COLUMN IF NOT EXISTS item_id BIGINT;

ALTER TABLE prms_request_items ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "sa" ON prms_request_items;
CREATE POLICY "sa" ON prms_request_items FOR ALL USING (true);

SELECT 'Project Request multi-produk (prms_request_items) created!' AS status;

-- ══════════════════════════════════════════════════════════════════════════════
-- Store Leader bisa cek unit dari Purchasing & set harga jual sendiri
-- ══════════════════════════════════════════════════════════════════════════════
ALTER TABLE prms_request_items ADD COLUMN IF NOT EXISTS sl_price NUMERIC;
ALTER TABLE prms_request_items ADD COLUMN IF NOT EXISTS sl_note TEXT;

SELECT 'Store Leader price override (sl_price, sl_note) added!' AS status;

# Cara Deploy KLA Business Suite
# Platform: Streamlit Cloud (GRATIS, tidak perlu kartu kredit)

---

## STEP 1 — Setup Supabase (5 menit)

1. Buka https://supabase.com → Sign Up (gratis, tidak perlu kartu kredit)
2. New Project → isi nama, password, region: Singapore
3. Tunggu ~2 menit
4. SQL Editor → New Query → paste isi file `supabase_setup.sql` → Run
5. Pastikan muncul: `status: Setup complete!`
6. Storage → New Bucket → nama: `kla-inventory` → Public: ON → Save
7. Settings → API → catat:
   - Project URL      → untuk SUPABASE_URL
   - service_role key → untuk SUPABASE_SERVICE_KEY

---

## STEP 2 — Push ke GitHub (3 menit)

1. Buka github.com → New repository → nama: `kla-app` → Public → Create
2. Di komputer, ekstrak ZIP ini:
   ```
   cd kla-streamlit
   git init
   git add .
   git commit -m "KLA Business Suite"
   git branch -M main
   git remote add origin https://github.com/USERNAME/kla-app.git
   git push -u origin main
   ```

---

## STEP 3 — Deploy di Streamlit Cloud (3 menit)

1. Buka https://share.streamlit.io → Sign in with GitHub
2. New app → pilih repo `kla-app` → Branch: main → File: app.py
3. Advanced settings → Secrets → paste ini (ganti dengan nilai dari Supabase):
   ```toml
   SUPABASE_URL = "https://xxxxx.supabase.co"
   SUPABASE_SERVICE_KEY = "eyJ..."
   ANTHROPIC_API_KEY = ""
   ```
4. Deploy! → tunggu 3-5 menit

---

## STEP 4 — Login & Upload Stok

1. Buka URL Streamlit yang diberikan
2. Login: username `admin`, password `admin123`
3. Di Dashboard → klik Upload File Stok Excel
4. Drag & drop file .xlsx → tunggu ~15-30 detik
5. Selesai — semua user bisa akses data

---

## TROUBLESHOOTING

### Login gagal
Jalankan SQL ini di Supabase:
```sql
UPDATE users
SET password_hash = '87713280795750557dae5dce27b090dc28bb9b2324314ebb68fd0d4545ca9f73'
WHERE username = 'admin';
```

### Error "Supabase 401"
- Pastikan SUPABASE_SERVICE_KEY di Secrets adalah **service_role** key, bukan anon key

### Error saat upload Excel
- Pastikan file format .xlsx (bukan .xls lama)
- Cek kolom HPP dan Total Stok ada di file

---

## FITUR LENGKAP

| Fitur | Role |
|-------|------|
| Upload & analisa stok | Super Admin |
| Executive Dashboard | Admin, Area Mgr, Store Leader |
| Inventory Analysis | Admin, Area Mgr, Store Leader |
| Branch Intelligence | Admin, Area Mgr, Store Leader |
| Transfer Engine | Admin, Area Mgr, Store Leader |
| Restock Engine | Admin, Area Mgr, Store Leader |
| Dead Stock Center | Admin, Area Mgr, Store Leader |
| Pricing Analysis | Admin, Area Mgr, Store Leader |
| AI Recommendation | Admin, Area Mgr, Store Leader |
| Sales Assistant | Semua role |
| PC Builder | Semua role |
| Export Excel | Super Admin |
| User Management | Super Admin |

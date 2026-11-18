"""
Migrasi skema database yang idempotent (aman dijalankan berulang).

Dipanggil oleh koordinator (app.py) DAN validator (validator.py) saat start,
sehingga database lama dari versi sebelumnya otomatis mendapat kolom/tabel baru
tanpa perlu './hpc.sh head-reset'.
"""

STATEMENTS = [
    # ---- Autentikasi CLI worker ------------------------------------------------
    """CREATE TABLE IF NOT EXISTS worker_auth_sessions (
        session_id      TEXT PRIMARY KEY,
        worker_name     TEXT NOT NULL,
        github_username TEXT NOT NULL,
        email           TEXT NOT NULL,
        otp             TEXT NOT NULL,
        otp_expires_at  TIMESTAMPTZ NOT NULL,
        verified        BOOLEAN NOT NULL DEFAULT FALSE,
        attempts        INT NOT NULL DEFAULT 0,
        github_metrics  JSONB,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now())""",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS github_username TEXT",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS email TEXT",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS auth_token TEXT UNIQUE",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "CREATE INDEX IF NOT EXISTS idx_workers_auth_token ON workers (auth_token)",
    # Kapasitas sandbox yang dilaporkan worker (dipakai mencocokkan spesifikasi resource job)
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS cpus REAL",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS memory_mb INT",
    # Izin tampil di papan apresiasi kontributor (consent relawan)
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS show_in_appreciation BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS appreciation_consent_at TIMESTAMPTZ",

    # ---- Job: multi-tahap, kode dari repo job (SHA), resource, hasil ke branch ---
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'running'",  # running|done|failed
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS spec JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS n_stages INT NOT NULL DEFAULT 1",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS current_stage INT NOT NULL DEFAULT 0",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS code JSONB",            # {repo_url, sha, entry} atau NULL
    """ALTER TABLE jobs ADD COLUMN IF NOT EXISTS resources JSONB NOT NULL
         DEFAULT '{"cpus": 1, "memory_mb": 256, "timeout_s": 120}'::jsonb""",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result JSONB",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result_branch TEXT",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result_commit TEXT",
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS publish_status TEXT",   # skipped|published|failed: ...

    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage INT NOT NULL DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS block INT",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS credit INT NOT NULL DEFAULT 1",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS result_hash TEXT",
    "CREATE INDEX IF NOT EXISTS idx_tasks_job_stage ON tasks (job_id, stage)",

    # Hash SHA-256 hasil dihitung KOORDINATOR saat submit (tidak percaya hash dari worker)
    "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS result_hash TEXT",
    "CREATE INDEX IF NOT EXISTS idx_assignments_worker ON assignments (worker_id)",

    # ---- Insentif relawan: sertifikat kontributor ---------------------------------
    """CREATE TABLE IF NOT EXISTS certificates (
        code            TEXT PRIMARY KEY,
        worker_id       TEXT NOT NULL UNIQUE REFERENCES workers(id),
        worker_name     TEXT NOT NULL,
        github_username TEXT,
        credits         INT NOT NULL,
        tasks_validated INT NOT NULL,
        issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now())""",

    # Sertifikat juga mencatat jobdesk yang diselesaikan (relawan developer)
    "ALTER TABLE certificates ADD COLUMN IF NOT EXISTS jobdesks_done INT NOT NULL DEFAULT 0",

    # Log keluaran tugas (tidak ikut di-hash; mis. output build/test yang berisi waktu)
    "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS log TEXT",

    # ---- Proyek perangkat lunak (repo B): jobdesk relawan + CI per commit ----------
    """CREATE TABLE IF NOT EXISTS jobdesks (
        id            SERIAL PRIMARY KEY,
        title         TEXT NOT NULL,
        description   TEXT NOT NULL DEFAULT '',
        kind          TEXT NOT NULL DEFAULT 'fitur',      -- fitur | bug | lainnya
        credit        INT NOT NULL DEFAULT 10,
        status        TEXT NOT NULL DEFAULT 'open',       -- open | in_progress | review | done | cancelled
        worker_id     TEXT REFERENCES workers(id),
        branch        TEXT,
        note          TEXT,
        last_sha      TEXT,
        last_ci_job   INT,
        last_ci_status TEXT,                               -- running | passed | failed | error | cancelled
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        assigned_at   TIMESTAMPTZ,
        submitted_at  TIMESTAMPTZ,
        done_at       TIMESTAMPTZ,
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT now())""",
    "ALTER TABLE jobdesks ADD COLUMN IF NOT EXISTS pr_number INT",
    "ALTER TABLE jobdesks ADD COLUMN IF NOT EXISTS pr_url TEXT",
    "ALTER TABLE jobdesks ADD COLUMN IF NOT EXISTS merged_sha TEXT",
    "CREATE INDEX IF NOT EXISTS idx_jobdesks_status ON jobdesks (status, id)",
    "CREATE INDEX IF NOT EXISTS idx_jobdesks_worker ON jobdesks (worker_id)",
    """CREATE TABLE IF NOT EXISTS jobdesk_events (
        id         SERIAL PRIMARY KEY,
        jobdesk_id INT NOT NULL REFERENCES jobdesks(id),
        at         TIMESTAMPTZ NOT NULL DEFAULT now(),
        actor      TEXT NOT NULL,
        event      TEXT NOT NULL,
        detail     TEXT)""",
    """CREATE TABLE IF NOT EXISTS repo_pushes (
        branch  TEXT NOT NULL,
        sha     TEXT NOT NULL,
        source  TEXT NOT NULL,
        seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        job_id  INT,
        PRIMARY KEY (branch, sha))""",
    "CREATE INDEX IF NOT EXISTS idx_jobs_ci_branch ON jobs ((spec->>'branch')) WHERE kind = 'ci'",

    # ---- Watch + peringatan admin, backup otomatis ----------------------------------
    """CREATE TABLE IF NOT EXISTS alerts (
        id         SERIAL PRIMARY KEY,
        key        TEXT NOT NULL UNIQUE,           -- pencegah dobel, mis. author:task/3-x:<sha>
        level      TEXT NOT NULL,                  -- info | warning | critical
        category   TEXT NOT NULL,                  -- error | suspicious | branch | backup | node
        title      TEXT NOT NULL,
        detail     TEXT,
        ref        JSONB NOT NULL DEFAULT '{}'::jsonb,
        count      INT NOT NULL DEFAULT 1,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        acked_at   TIMESTAMPTZ,
        acked_by   TEXT,
        emailed_at TIMESTAMPTZ)""",
    "CREATE INDEX IF NOT EXISTS idx_alerts_open ON alerts (acked_at, level)",
    """CREATE TABLE IF NOT EXISTS backups (
        id SERIAL PRIMARY KEY, at TIMESTAMPTZ NOT NULL DEFAULT now(), ok BOOLEAN NOT NULL,
        file TEXT, bytes BIGINT, sha256 TEXT, copied BOOLEAN NOT NULL DEFAULT FALSE, error TEXT)""",
    # Cek per branch: siapa yang push (webhook), force push, dan apakah sudah dicek watch.
    # Push lama (sebelum fitur ini) dianggap sudah dicek; push baru bawaannya belum.
    "ALTER TABLE repo_pushes ADD COLUMN IF NOT EXISTS pusher TEXT",
    "ALTER TABLE repo_pushes ADD COLUMN IF NOT EXISTS forced BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE repo_pushes ADD COLUMN IF NOT EXISTS author TEXT",
    "ALTER TABLE repo_pushes ADD COLUMN IF NOT EXISTS check_note TEXT",
    "ALTER TABLE repo_pushes ADD COLUMN IF NOT EXISTS checked BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE repo_pushes ALTER COLUMN checked SET DEFAULT FALSE",

    # ---- Login web relawan: email + password (sesi web), token tetap untuk CLI/worker ----
    # Hash password (PBKDF2, format sama dengan admin). Dibuat saat Register (web) atau di dashboard.
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS password_hash TEXT",
    "ALTER TABLE worker_auth_sessions ADD COLUMN IF NOT EXISTS password_hash TEXT",
    "CREATE INDEX IF NOT EXISTS idx_workers_email ON workers (lower(email))",
    # Nama tampilan pilihan relawan (PREFERRED USERNAME di Register), tampil di navbar saat login
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS username TEXT",
    "ALTER TABLE worker_auth_sessions ADD COLUMN IF NOT EXISTS username TEXT",
    # Nama depan & nama belakang relawan
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS first_name TEXT",
    "ALTER TABLE workers ADD COLUMN IF NOT EXISTS last_name TEXT",
    "ALTER TABLE worker_auth_sessions ADD COLUMN IF NOT EXISTS first_name TEXT",
    "ALTER TABLE worker_auth_sessions ADD COLUMN IF NOT EXISTS last_name TEXT",
    # Batas kirim ulang OTP pendaftaran (lihat app.py: RESEND_MAX, RESEND_COOLDOWN_S)
    "ALTER TABLE worker_auth_sessions ADD COLUMN IF NOT EXISTS resends INT NOT NULL DEFAULT 0",
    "ALTER TABLE worker_auth_sessions ADD COLUMN IF NOT EXISTS last_sent_at TIMESTAMPTZ",
    # Sesi web relawan: hanya HASH token sesi yang disimpan; token worker (CLI) tidak pernah ke browser.
    """CREATE TABLE IF NOT EXISTS worker_sessions (
        token_hash   TEXT PRIMARY KEY,
        worker_id    TEXT NOT NULL REFERENCES workers(id),
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at   TIMESTAMPTZ NOT NULL,
        last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        ip           TEXT,
        user_agent   TEXT)""",
    "CREATE INDEX IF NOT EXISTS idx_worker_sessions_worker ON worker_sessions (worker_id)",
    # Atur ulang / buat password website lewat OTP email (akun lama tanpa password). Hanya hash kode.
    """CREATE TABLE IF NOT EXISTS worker_password_resets (
        email      TEXT PRIMARY KEY,
        worker_id  TEXT NOT NULL REFERENCES workers(id),
        otp_hash   TEXT NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        attempts   INT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    # Pengaturan yang berubah saat berjalan, mis. alamat HTTPS koordinator dari './hpc.sh head-online'
    """CREATE TABLE IF NOT EXISTS settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    # ---- Akses relawan ke compute node per jobdesk (ssh + gerbang git, lihat node_access.py) ----
    # Compute node disediakan platform (kontainer 'node' di head); agennya sync tiap beberapa detik.
    """CREATE TABLE IF NOT EXISTS nodes (
        name       TEXT PRIMARY KEY,
        ip         TEXT,
        last_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
        max_users  INT NOT NULL DEFAULT 20,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    # Satu baris = satu izin login (user jd<id>) untuk satu jobdesk. Dicabut saat jobdesk disetujui /
    # dibatalkan: token git mati, agen memutus sesi SSH dan menghapus user-nya.
    """CREATE TABLE IF NOT EXISTS node_access (
        id             SERIAL PRIMARY KEY,
        jobdesk_id     INT NOT NULL REFERENCES jobdesks(id),
        worker_id      TEXT NOT NULL REFERENCES workers(id),
        username       TEXT NOT NULL,
        uid            INT NOT NULL,
        password       TEXT NOT NULL,                 -- token node (password ssh), sama dengan git_token
        git_token      TEXT NOT NULL UNIQUE,          -- hpc_ng_..., hanya berlaku dari IP compute node-nya
        status         TEXT NOT NULL DEFAULT 'active',  -- active | revoked
        node           TEXT,                          -- compute node yang menjalankan user ini
        sessions       INT NOT NULL DEFAULT 0,        -- sesi SSH yang sedang login (laporan agen)
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        provisioned_at TIMESTAMPTZ,
        last_login_at  TIMESTAMPTZ,
        revoked_at     TIMESTAMPTZ,
        revoked_reason TEXT)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_node_access_one_active ON node_access (jobdesk_id) WHERE status = 'active'",
    "CREATE INDEX IF NOT EXISTS idx_node_access_node ON node_access (node, status)",
    # Batas umur token node per jobdesk (NODE_TOKEN_TTL_DAYS); NULL = tanpa batas
    "ALTER TABLE node_access ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
    # Banyak compute node: port SSH tiap node + giliran penempatan (node paling lama tidak diberi akses)
    "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS ssh_port INT",
    "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS last_assigned_at TIMESTAMPTZ",
    # Lepas node saat relawan tidak aktif (NODE_IDLE_MINUTES): akses tetap aktif tanpa node ("parkir"),
    # relawan menekan MASUK LAGI KE NODE di website; node terakhir diutamakan bila kosong
    "ALTER TABLE node_access ADD COLUMN IF NOT EXISTS parked_at TIMESTAMPTZ",
    "ALTER TABLE node_access ADD COLUMN IF NOT EXISTS last_node TEXT",
]


def migrate(c) -> None:
    # Koordinator dan validator start bersamaan: kunci agar CREATE TABLE tidak balapan
    c.execute("SELECT pg_advisory_lock(727001)")
    try:
        for sql in STATEMENTS:
            c.execute(sql)
        # Tabel sesi admin didefinisikan di admin.py
        from admin import init_admin_schema
        init_admin_schema(c)
    finally:
        c.execute("SELECT pg_advisory_unlock(727001)")

CREATE TABLE workers (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  github_username TEXT,
  email           TEXT,
  auth_token      TEXT UNIQUE,
  status          TEXT NOT NULL DEFAULT 'active', -- active | pending | suspended
  last_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
  credits         INT NOT NULL DEFAULT 0,
  cpus            REAL,                            -- kapasitas sandbox yang dilaporkan worker
  memory_mb       INT,
  show_in_appreciation BOOLEAN NOT NULL DEFAULT FALSE, -- izin tampil di papan apresiasi publik
  appreciation_consent_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE worker_auth_sessions (
  session_id      TEXT PRIMARY KEY,
  worker_name     TEXT NOT NULL,
  github_username TEXT NOT NULL,
  email           TEXT NOT NULL,
  otp             TEXT NOT NULL,
  otp_expires_at  TIMESTAMPTZ NOT NULL,
  verified        BOOLEAN NOT NULL DEFAULT FALSE,
  attempts        INT NOT NULL DEFAULT 0,
  github_metrics  JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
  id             SERIAL PRIMARY KEY,
  kind           TEXT NOT NULL,                    -- montecarlo_pi | mandelbrot | heat2d | repo | ci
  status         TEXT NOT NULL DEFAULT 'running',  -- running | done | failed | cancelled
  spec           JSONB NOT NULL DEFAULT '{}'::jsonb,
  n_stages       INT NOT NULL DEFAULT 1,           -- job multi-tahap (heat2d): jumlah tahap
  current_stage  INT NOT NULL DEFAULT 0,
  code           JSONB,                            -- {repo_url, sha, entry}: kode dari repo job
  resources      JSONB NOT NULL DEFAULT '{"cpus": 1, "memory_mb": 256, "timeout_s": 120}'::jsonb,
  result         JSONB,
  result_branch  TEXT,                             -- branch hasil di GitHub (results/job-<id>)
  result_commit  TEXT,
  publish_status TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at    TIMESTAMPTZ
);

CREATE TABLE tasks (
  id        SERIAL PRIMARY KEY,
  job_id    INT NOT NULL REFERENCES jobs(id),
  kind      TEXT NOT NULL,
  payload   JSONB NOT NULL,
  replicas  INT NOT NULL DEFAULT 2,
  stage     INT NOT NULL DEFAULT 0,           -- tahap ke berapa (job multi-tahap)
  block     INT,                              -- nomor blok / indeks tugas
  credit    INT NOT NULL DEFAULT 1,           -- kredit untuk tiap worker yang hasilnya sepakat
  status    TEXT NOT NULL DEFAULT 'pending',  -- pending | done | invalid | cancelled
  result    JSONB,
  result_hash TEXT
);

CREATE TABLE assignments (
  id          SERIAL PRIMARY KEY,
  task_id     INT NOT NULL REFERENCES tasks(id),
  worker_id   TEXT NOT NULL REFERENCES workers(id),
  status      TEXT NOT NULL DEFAULT 'running', -- running | submitted | expired
  lease_until TIMESTAMPTZ NOT NULL,
  result      JSONB,
  result_hash TEXT,                            -- SHA-256 hasil, dihitung koordinator
  log         TEXT,                            -- potongan output build/test (tidak di-hash)
  started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE TABLE admin_sessions (
  token_hash   TEXT PRIMARY KEY,           -- SHA-256 dari token sesi (token asli tidak disimpan)
  email        TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at   TIMESTAMPTZ NOT NULL,
  last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ip           TEXT,
  user_agent   TEXT
);

CREATE TABLE certificates (
  code            TEXT PRIMARY KEY,              -- HPC-XXXXXXXXXX, bisa diverifikasi publik
  worker_id       TEXT NOT NULL UNIQUE REFERENCES workers(id),
  worker_name     TEXT NOT NULL,
  github_username TEXT,
  credits         INT NOT NULL,
  tasks_validated INT NOT NULL,
  issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Proyek perangkat lunak (repo B): jobdesk relawan (seperti papan tugas Jira)
CREATE TABLE jobdesks (
  id             SERIAL PRIMARY KEY,
  title          TEXT NOT NULL,
  description    TEXT NOT NULL DEFAULT '',
  kind           TEXT NOT NULL DEFAULT 'fitur',  -- fitur | bug | lainnya
  credit         INT NOT NULL DEFAULT 10,        -- kredit bila disetujui admin
  status         TEXT NOT NULL DEFAULT 'open',   -- open | in_progress | review | done | cancelled
  worker_id      TEXT REFERENCES workers(id),    -- relawan yang mengerjakan (di-assign sistem, FIFO)
  branch         TEXT,                           -- task/<id>-<judul> di repo B
  note           TEXT,                           -- catatan admin (mis. permintaan revisi)
  last_sha       TEXT,                           -- commit terakhir di branch
  last_ci_job    INT,
  last_ci_status TEXT,                           -- running | passed | failed | error | cancelled
  pr_number      INT,                            -- Pull Request yang dibuka sistem saat ajukan review
  pr_url         TEXT,
  merged_sha     TEXT,                           -- commit hasil merge saat admin menyetujui
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  assigned_at    TIMESTAMPTZ,
  submitted_at   TIMESTAMPTZ,
  done_at        TIMESTAMPTZ,
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE jobdesk_events (
  id         SERIAL PRIMARY KEY,
  jobdesk_id INT NOT NULL REFERENCES jobdesks(id),
  at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor      TEXT NOT NULL,
  event      TEXT NOT NULL,
  detail     TEXT
);

-- Push ke repo B yang sudah dilihat (webhook / polling); satu job CI per (branch, sha)
CREATE TABLE repo_pushes (
  branch  TEXT NOT NULL,
  sha     TEXT NOT NULL,
  source  TEXT NOT NULL,
  seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  job_id  INT,
  pusher  TEXT,                                  -- akun GitHub yang push (dari webhook)
  forced  BOOLEAN NOT NULL DEFAULT FALSE,        -- force push
  author  TEXT,                                  -- login GitHub author commit (hasil cek watch)
  check_note TEXT,
  checked BOOLEAN NOT NULL DEFAULT FALSE,        -- sudah dicek watch (cek per branch)
  PRIMARY KEY (branch, sha)
);

-- Watch: peringatan untuk admin (tab PERINGATAN + email)
CREATE TABLE alerts (
  id         SERIAL PRIMARY KEY,
  key        TEXT NOT NULL UNIQUE,
  level      TEXT NOT NULL,                      -- info | warning | critical
  category   TEXT NOT NULL,                      -- error | suspicious | branch | backup | node
  title      TEXT NOT NULL,
  detail     TEXT,
  ref        JSONB NOT NULL DEFAULT '{}'::jsonb,
  count      INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  acked_at   TIMESTAMPTZ,
  acked_by   TEXT,
  emailed_at TIMESTAMPTZ
);
CREATE INDEX idx_alerts_open ON alerts (acked_at, level);

-- Catatan backup otomatis tiap jam (diisi layanan backup)
CREATE TABLE backups (
  id      SERIAL PRIMARY KEY,
  at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  ok      BOOLEAN NOT NULL,
  file    TEXT,
  bytes   BIGINT,
  sha256  TEXT,
  copied  BOOLEAN NOT NULL DEFAULT FALSE,
  error   TEXT
);

CREATE INDEX ON jobdesks (status, id);
CREATE INDEX ON jobdesks (worker_id);
CREATE INDEX ON jobs ((spec->>'branch')) WHERE kind = 'ci';
CREATE INDEX ON workers (auth_token);
CREATE INDEX ON tasks (job_id, stage);
CREATE INDEX ON assignments (worker_id);
CREATE INDEX ON admin_sessions (expires_at);
CREATE INDEX ON worker_auth_sessions (email);
CREATE INDEX ON worker_auth_sessions (github_username);
CREATE INDEX ON tasks (status);
CREATE INDEX ON assignments (task_id);
CREATE INDEX ON assignments (status, lease_until);

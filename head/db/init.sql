CREATE TABLE workers (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  github_username TEXT,
  email           TEXT,
  auth_token      TEXT UNIQUE,
  status          TEXT NOT NULL DEFAULT 'active', -- active | pending | suspended
  last_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
  credits         INT NOT NULL DEFAULT 0,
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
  id         SERIAL PRIMARY KEY,
  kind       TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
  id        SERIAL PRIMARY KEY,
  job_id    INT NOT NULL REFERENCES jobs(id),
  kind      TEXT NOT NULL,
  payload   JSONB NOT NULL,
  replicas  INT NOT NULL DEFAULT 2,
  status    TEXT NOT NULL DEFAULT 'pending',  -- pending | done | invalid
  result    JSONB
);

CREATE TABLE assignments (
  id          SERIAL PRIMARY KEY,
  task_id     INT NOT NULL REFERENCES tasks(id),
  worker_id   TEXT NOT NULL REFERENCES workers(id),
  status      TEXT NOT NULL DEFAULT 'running', -- running | submitted | expired
  lease_until TIMESTAMPTZ NOT NULL,
  result      JSONB,
  started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX ON workers (auth_token);
CREATE INDEX ON worker_auth_sessions (email);
CREATE INDEX ON worker_auth_sessions (github_username);
CREATE INDEX ON tasks (status);
CREATE INDEX ON assignments (task_id);
CREATE INDEX ON assignments (status, lease_until);

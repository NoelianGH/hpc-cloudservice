CREATE TABLE workers (
  id        TEXT PRIMARY KEY,
  name      TEXT NOT NULL,
  last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
  credits   INT NOT NULL DEFAULT 0
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

CREATE INDEX ON tasks (status);
CREATE INDEX ON assignments (task_id);
CREATE INDEX ON assignments (status, lease_until);
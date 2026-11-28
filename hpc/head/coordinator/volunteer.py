"""
Insentif relawan (masukan dosen #1): kredit tervalidasi, leaderboard, lencana, dan
sertifikat kontributor yang bisa diverifikasi publik.

Aturan (bisa diubah lewat .env):
  - Kredit hanya bertambah bila hasil worker SAMA dengan quorum (lihat validator.py).
  - Lencana menurut total kredit: Perintis >= 1, Perunggu >= 25, Perak >= 100, Emas >= 250.
  - Sertifikat bisa diambil bila kredit >= CERT_MIN_CREDITS (bawaan 50) dan
    hasil diterima >= CERT_MIN_ACCEPT_PCT persen (bawaan 90). Hasil diterima =
    review jobdesk yang langsung disetujui admin dibanding yang diminta revisi;
    belum ada review = belum ada yang ditolak, jadi tidak menghalangi.
  - PDF sertifikat: sertifikat/template.png diisi nama lengkap registrasi (First Name + Last Name)
    oleh certificate_pdf.py. Membuka PDF saat sudah memenuhi syarat otomatis menerbitkan sertifikat.
  - Sertifikat punya kode unik; siapa pun bisa memeriksa keasliannya di
    /api/certificates/<kode> (web: /certificate/<kode>).

Endpoint:
  GET  /api/leaderboard              publik
  GET  /api/me                       token worker individual (hpc_w_...)
  POST /api/me/certificate           token worker individual
  GET  /api/me/certificate.pdf       sesi web relawan: PDF sertifikat (template PNG + nama lengkap)
  GET  /api/certificates/{code}      publik
Endpoint relawan menerima sesi web (login email + password) maupun token worker pribadi.
"""
import os
import re
import secrets

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel

from certificate_pdf import render_certificate
from common import db
from volunteer_auth import check_volunteer_auth

CERT_MIN_CREDITS = int(os.environ.get("CERT_MIN_CREDITS", "50") or 50)
CERT_MIN_ACCEPT_PCT = float(os.environ.get("CERT_MIN_ACCEPT_PCT", "90") or 90)
PROJECT_NAME = os.environ.get("PROJECT_NAME", "Cloud Service HPC - Volunteer Computing")

BADGES = [(250, "Emas"), (100, "Perak"), (25, "Perunggu"), (1, "Perintis")]

router = APIRouter(tags=["relawan"])

# Statistik per worker: tugas tervalidasi (hash sama dengan hasil final) dan ditolak (beda)
_STATS_SQL = """
    SELECT w.id, w.name, w.github_username, w.status, w.credits, w.created_at, w.last_seen,
           (now() - w.last_seen) < interval '60 seconds' AS online,
           count(a.id) FILTER (WHERE a.status = 'submitted' AND t.status = 'done'
                               AND a.result_hash = t.result_hash) AS tasks_validated,
           count(a.id) FILTER (WHERE a.status = 'submitted' AND t.status IN ('done', 'invalid')
                               AND a.result_hash IS DISTINCT FROM t.result_hash) AS tasks_rejected,
           count(a.id) FILTER (WHERE a.status = 'expired') AS tasks_expired,
           count(DISTINCT t.job_id) FILTER (WHERE a.status = 'submitted') AS jobs_joined,
           coalesce(sum(EXTRACT(EPOCH FROM (a.finished_at - a.started_at)))
                    FILTER (WHERE a.status = 'submitted'), 0) AS compute_seconds
    FROM workers w
    LEFT JOIN assignments a ON a.worker_id = w.id
    LEFT JOIN tasks t ON t.id = a.task_id
"""


def badge(credits: int) -> str | None:
    for limit, name in BADGES:
        if credits >= limit:
            return name
    return None


def next_badge(credits: int) -> dict | None:
    for limit, name in reversed(BADGES):
        if credits < limit:
            return {"name": name, "credits": limit}
    return None


def _reject_pct(s: dict) -> float:
    total = s["tasks_validated"] + s["tasks_rejected"]
    return round(100.0 * s["tasks_rejected"] / total, 1) if total else 0.0


def _reviews(c, worker_id: str) -> dict:
    """Jobdesk relawan: jumlah selesai/aktif dan hasil review admin (disetujui vs diminta revisi)."""
    jd = c.execute("""
        SELECT count(*) FILTER (WHERE status = 'done') AS done,
               count(*) FILTER (WHERE status IN ('in_progress', 'review')) AS active
          FROM jobdesks WHERE worker_id = %s""", (worker_id,)).fetchone()
    rv = c.execute("""
        SELECT count(*) FILTER (WHERE e.event = 'approve') AS approved,
               count(*) FILTER (WHERE e.event = 'revise') AS revised
          FROM jobdesk_events e JOIN jobdesks d ON d.id = e.jobdesk_id
         WHERE d.worker_id = %s""", (worker_id,)).fetchone()
    reviewed = rv["approved"] + rv["revised"]
    return {"jobdesks_done": jd["done"], "jobdesks_active": jd["active"],
            "reviews_approved": rv["approved"], "reviews_revised": rv["revised"],
            "accept_pct": round(100 * rv["approved"] / reviewed) if reviewed else None}


def _eligibility(s: dict, rv: dict) -> dict:
    reasons = []
    if s["credits"] < CERT_MIN_CREDITS:
        reasons.append(f"Kredit {s['credits']}/{CERT_MIN_CREDITS}")
    if rv["accept_pct"] is not None and rv["accept_pct"] < CERT_MIN_ACCEPT_PCT:
        reasons.append(f"Hasil diterima {rv['accept_pct']}% (min {CERT_MIN_ACCEPT_PCT:g}%)")
    if not s.get("github_username"):
        reasons.append("Worker belum terverifikasi GitHub + OTP")
    return {"eligible": not reasons, "missing": reasons, "min_credits": CERT_MIN_CREDITS,
            "min_accept_pct": CERT_MIN_ACCEPT_PCT,
            "progress_pct": min(100, round(100 * s["credits"] / CERT_MIN_CREDITS)) if CERT_MIN_CREDITS else 100}


def _ranked(c) -> list[dict]:
    rows = c.execute(_STATS_SQL + """
        WHERE w.status = 'active'
        GROUP BY w.id
        ORDER BY w.credits DESC, tasks_validated DESC, w.created_at ASC""").fetchall()
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


@router.get("/api/leaderboard")
def leaderboard(limit: int = 50):
    """Peringkat publik. Tidak memuat email maupun worker_id."""
    limit = max(1, min(limit, 200))
    with db() as c:
        rows = _ranked(c)
        totals = c.execute("""SELECT count(*) AS volunteers,
                                     count(*) FILTER (WHERE github_username IS NOT NULL) AS verified,
                                     coalesce(sum(credits), 0) AS credits FROM workers
                              WHERE status = 'active'""").fetchone()
        certs = c.execute("SELECT count(*) AS n FROM certificates").fetchone()
    out = [{
        "rank": r["rank"], "name": r["name"], "github_username": r["github_username"],
        "credits": r["credits"], "badge": badge(r["credits"]), "tasks_validated": r["tasks_validated"],
        "reject_pct": _reject_pct(r), "compute_seconds": round(float(r["compute_seconds"] or 0)),
        "jobs_joined": r["jobs_joined"], "online": r["online"], "verified": bool(r["github_username"]),
    } for r in rows[:limit]]
    return {"leaderboard": out, "totals": {**totals, "certificates": certs["n"]},
            "rules": {"badges": [{"name": n, "credits": l} for l, n in reversed(BADGES)],
                      "certificate_min_credits": CERT_MIN_CREDITS,
                      "certificate_min_accept_pct": CERT_MIN_ACCEPT_PCT}}


def _individual(authorization: str | None) -> dict:
    info = check_volunteer_auth(authorization)
    if info["type"] != "individual":
        raise HTTPException(403, "Token bersama (WORKER_TOKEN global) tidak punya profil relawan. "
                                 "Daftar dulu lewat halaman Register atau './hpc.sh worker-login'.")
    return info["worker"]


@router.get("/api/me")
def me(authorization: str = Header(None)):
    """Profil relawan + kredit, peringkat, lencana, progres sertifikat, dan riwayat tugas."""
    w = _individual(authorization)
    with db() as c:
        ranked = _ranked(c)
        s = next((r for r in ranked if r["id"] == w["id"]), None)
        if s is None:  # mis. belum pernah aktif
            s = c.execute(_STATS_SQL + " WHERE w.id = %s GROUP BY w.id", (w["id"],)).fetchone()
            s["rank"] = None
        recent = c.execute("""
            SELECT a.id, a.task_id, t.job_id, t.kind, t.stage, j.n_stages, a.status,
                   t.status AS task_status, t.credit, a.started_at, a.finished_at,
                   EXTRACT(EPOCH FROM (a.finished_at - a.started_at)) AS seconds,
                   CASE WHEN a.status <> 'submitted' THEN a.status
                        WHEN t.status = 'pending' THEN 'menunggu validasi'
                        WHEN a.result_hash = t.result_hash THEN 'tervalidasi'
                        ELSE 'ditolak' END AS outcome
            FROM assignments a JOIN tasks t ON t.id = a.task_id JOIN jobs j ON j.id = t.job_id
            WHERE a.worker_id = %s ORDER BY a.id DESC LIMIT 25""", (w["id"],)).fetchall()
        cert = c.execute("SELECT code, issued_at, updated_at, credits FROM certificates WHERE worker_id = %s",
                         (w["id"],)).fetchone()
        rv = _reviews(c, w["id"])
        acc = c.execute("""
            SELECT password_hash IS NOT NULL AS has_password,
                   appreciation_consent_at IS NOT NULL AS has_consented,
                   coalesce(show_in_appreciation, false) AS show_in_appreciation,
                   first_name,
                   last_name,
                   username,
                   name AS worker_node_name
              FROM workers WHERE id = %s""", (w["id"],)).fetchone()
        fn = (acc.get("first_name") or "").strip() if acc else ""
        ln = (acc.get("last_name") or "").strip() if acc else ""
        un = (acc.get("username") or "").strip() if acc else (w.get("username") or "").strip()
        wn = (acc.get("worker_node_name") or w.get("name") or "").strip() if acc else (w.get("name") or "").strip()
    return {
        "worker": {"id": w["id"], "name": wn, "worker_name": wn, "worker_node_name": wn,
                   "github_username": w["github_username"],
                   "email": w["email"], "status": w["status"], "created_at": s["created_at"],
                   "online": s["online"], "last_seen": s["last_seen"],
                   "first_name": fn,
                   "last_name": ln,
                   "username": un,
                   "show_in_appreciation": bool(acc["show_in_appreciation"]),
                   "has_consented": bool(acc["has_consented"]),
                   "has_password": acc["has_password"]},
        "stats": {"credits": s["credits"], "rank": s["rank"], "of": len(ranked),
                  "badge": badge(s["credits"]), "next_badge": next_badge(s["credits"]),
                  "tasks_validated": s["tasks_validated"], "tasks_rejected": s["tasks_rejected"],
                  "tasks_expired": s["tasks_expired"], "reject_pct": _reject_pct(s),
                  "jobs_joined": s["jobs_joined"], "compute_seconds": round(float(s["compute_seconds"] or 0)),
                  **rv},
        "certificate": {**_eligibility(s, rv), "issued": cert},
        "recent": recent,
    }


def _registration_name(c, worker_id: str, fallback: str = "") -> str:
    """Nama lengkap saat registrasi (First Name + Last Name); akun lama tanpa nama jatuh ke
    username / nama worker."""
    r = c.execute("SELECT name, username, first_name, last_name FROM workers WHERE id = %s",
                  (worker_id,)).fetchone() or {}
    full = " ".join(p.strip() for p in (r.get("first_name"), r.get("last_name")) if p and p.strip())
    return full or (r.get("username") or "").strip() or (r.get("name") or "").strip() or fallback


def _upsert_certificate(c, w: dict, s: dict, rv: dict) -> dict:
    """Terbitkan sertifikat, atau perbarui nama & angka pada sertifikat yang sudah ada (kode tetap)."""
    code = "HPC-" + secrets.token_hex(5).upper()
    return c.execute("""
        INSERT INTO certificates (code, worker_id, worker_name, github_username, credits, tasks_validated,
                                  jobdesks_done)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (worker_id) DO UPDATE
           SET worker_name = EXCLUDED.worker_name, github_username = EXCLUDED.github_username,
               credits = EXCLUDED.credits, tasks_validated = EXCLUDED.tasks_validated,
               jobdesks_done = EXCLUDED.jobdesks_done, updated_at = now()
        RETURNING code, worker_name, issued_at, updated_at, credits, tasks_validated, jobdesks_done""",
        (code, w["id"], _registration_name(c, w["id"], w.get("name") or ""), w["github_username"],
         s["credits"], s["tasks_validated"], rv["jobdesks_done"])).fetchone()


@router.post("/api/me/certificate")
def issue_certificate(authorization: str = Header(None)):
    """Terbitkan (atau perbarui angka pada) sertifikat kontributor bila syarat terpenuhi."""
    w = _individual(authorization)
    with db() as c:
        s = c.execute(_STATS_SQL + " WHERE w.id = %s GROUP BY w.id", (w["id"],)).fetchone()
        rv = _reviews(c, w["id"])
        el = _eligibility(s, rv)
        if not el["eligible"]:
            raise HTTPException(400, {"message": "Belum memenuhi syarat sertifikat.", "missing": el["missing"]})
        cert = _upsert_certificate(c, w, s, rv)
    print(f"[SERTIFIKAT] {cert['code']} untuk {cert['worker_name']} @{w['github_username']} ({cert['credits']} kredit)", flush=True)
    return {"ok": True, **cert}


_BASE_RE = re.compile(r"^https?://[A-Za-z0-9.\-]+(:\d{1,5})?$")


@router.get("/api/me/certificate.pdf")
def certificate_pdf(download: bool = False, base: str | None = None, authorization: str = Header(None)):
    """
    Sertifikat kontributor dalam bentuk PDF: template PNG (sertifikat/template.png) diisi nama
    lengkap registrasi relawan, lalu dijadikan PDF A4 lanskap.
    - Memenuhi syarat (poin >= CERT_MIN_CREDITS, bawaan 50): sertifikat otomatis diterbitkan bila
      belum ada, atau nama & angkanya diperbarui, lalu PDF dikirim.
    - Belum memenuhi syarat dan belum pernah terbit: 403 berisi syarat yang kurang.
    - Sudah pernah terbit tetapi kini tidak memenuhi syarat (mis. persentase diterima turun):
      PDF sertifikat yang sudah terbit tetap bisa diunduh.
    Query: download=1 -> unduh sebagai lampiran; base=https://situs-web -> alamat verifikasi di kaki sertifikat.
    """
    w = _individual(authorization)
    with db() as c:
        s = c.execute(_STATS_SQL + " WHERE w.id = %s GROUP BY w.id", (w["id"],)).fetchone()
        rv = _reviews(c, w["id"])
        el = _eligibility(s, rv)
        if el["eligible"]:
            cert = _upsert_certificate(c, w, s, rv)
        else:
            cert = c.execute("SELECT code, worker_name, issued_at FROM certificates WHERE worker_id = %s",
                             (w["id"],)).fetchone()
            if not cert:
                raise HTTPException(403, {"message": f"Sertifikat terbuka setelah mengumpulkan {CERT_MIN_CREDITS} poin.",
                                          "missing": el["missing"], "credits": s["credits"],
                                          "min_credits": CERT_MIN_CREDITS})
    base = (base or "").strip().rstrip("/")
    verify = f"{base}/certificate/{cert['code']}" if base and len(base) <= 100 and _BASE_RE.match(base) else None
    pdf = render_certificate(cert["worker_name"], cert["code"], cert["issued_at"], verify)
    fname = f"Sertifikat-{cert['code']}.pdf"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{fname}"',
        "Cache-Control": "private, no-store",
        "X-Certificate-Code": cert["code"],
    })


@router.get("/api/certificates/{code}")
def verify_certificate(code: str):
    """Verifikasi publik keaslian sertifikat."""
    code = code.strip().upper()
    if not code.startswith("HPC-") or len(code) > 20:
        raise HTTPException(404, "Sertifikat tidak ditemukan")
    with db() as c:
        cert = c.execute("""
            SELECT ce.code, ce.worker_name, ce.github_username, ce.credits, ce.tasks_validated, ce.jobdesks_done,
                   ce.issued_at, ce.updated_at, w.status AS worker_status
            FROM certificates ce JOIN workers w ON w.id = ce.worker_id WHERE ce.code = %s""", (code,)).fetchone()
    if not cert:
        raise HTTPException(404, "Sertifikat tidak ditemukan")
    return {"valid": cert["worker_status"] == "active", "project": PROJECT_NAME,
            "badge": badge(cert["credits"]), **cert}


# =============================================================================
# PAPAN APRESIASI KONTRIBUTOR & KONSENSUS PRIVASI
# =============================================================================

class AppreciationConsentBody(BaseModel):
    consent: bool

@router.post("/api/volunteer/appreciation-consent")
@router.post("/api/me/appreciation-consent")
def set_appreciation_consent(body: AppreciationConsentBody, authorization: str = Header(None)):
    """Mengatur izin relawan (consent) untuk ditampilkan di papan apresiasi publik."""
    w = _individual(authorization)
    with db() as c:
        c.execute("""
            UPDATE workers
               SET show_in_appreciation = %s,
                   appreciation_consent_at = now()
             WHERE id = %s
        """, (body.consent, w["id"]))
    print(f"[APPRECIATION CONSENT] Worker @{w.get('github_username', w['id'])} set consent={body.consent}", flush=True)
    return {"ok": True, "show_in_appreciation": body.consent}


@router.get("/api/appreciation")
def appreciation_list():
    """
    Papan Apresiasi Publik.
    HANYA menampilkan relawan yang telah secara eksplisit memberikan persetujuan (consent)
    saat logout atau di profil mereka.
    """
    with db() as c:
        rows = c.execute("""
            SELECT id, name, github_username, credits, created_at, last_seen, status,
                   show_in_appreciation, appreciation_consent_at
              FROM workers
             WHERE show_in_appreciation = TRUE
               AND github_username IS NOT NULL
             ORDER BY credits DESC, created_at ASC
        """).fetchall()

    contributors = [{
        "name": r["name"],
        "github_username": r["github_username"],
        "avatar_url": f"https://github.com/{r['github_username']}.png",
        "github_url": f"https://github.com/{r['github_username']}",
        "credits": r["credits"],
        "badge": badge(r["credits"]),
        "joined_at": r["created_at"].isoformat() if r["created_at"] else None,
        "consent_at": r["appreciation_consent_at"].isoformat() if r["appreciation_consent_at"] else None,
    } for r in rows]

    return {
        "contributors": contributors,
        "total": len(contributors)
    }

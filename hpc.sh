#!/usr/bin/env bash
# Pintasan perintah proyek Cloud Service HPC. Jalankan dari folder proyek: ./hpc.sh <perintah>
set -e
cd "$(dirname "$0")"
[ -f .env ] || { cp .env.example .env; echo "File .env dibuat dari .env.example. Ubah isinya bila perlu."; }
set -a; . ./.env; set +a

HEAD="docker compose --env-file .env -p hpc-head -f hpc/head/docker-compose.yml"
WORK="docker compose --env-file .env -p hpc-worker -f hpc/compute/docker-compose.yml"

# Rahasia acak: dibuat / diganti di .env bila kosong, masih nilai contoh, atau terlalu pendek.
# (Koordinator menolak nilai contoh seperti 'token-admin-sementara'.)
rand_hex() { head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }
set_env_secret() {   # set_env_secret NAMA NILAI_BARU
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else printf '\n%s=%s\n' "$1" "$2" >> .env; fi
  export "$1=$2"
}
weak_secret() {      # weak_secret NILAI -> sukses bila kosong / contoh / < 16 karakter
  case "$1" in ""|token-admin-sementara|token-relawan-sementara|ganti-password-db|changeme|secret|password) return 0 ;; esac
  [ "${#1}" -lt 16 ]
}
ensure_secrets() {
  weak_secret "${NODE_TOKEN:-}" && { set_env_secret NODE_TOKEN "hpc_node_$(rand_hex 24)"; echo "NODE_TOKEN dibuat di .env"; }
  weak_secret "${ADMIN_TOKEN:-}" && { set_env_secret ADMIN_TOKEN "hpc_admin_$(rand_hex 24)"; echo "ADMIN_TOKEN acak dibuat di .env (dipakai perintah ./hpc.sh)"; }
  weak_secret "${WEB_PROXY_SECRET:-}" && { set_env_secret WEB_PROXY_SECRET "$(rand_hex 24)"; echo "WEB_PROXY_SECRET dibuat di .env"; }
  # Token worker global hanya untuk worker uji di laptop ini (compute/ memakai .env yang sama)
  if [ -n "${WORKER_TOKEN:-}" ] && weak_secret "$WORKER_TOKEN"; then
    set_env_secret WORKER_TOKEN "hpc_shared_$(rand_hex 24)"; echo "WORKER_TOKEN contoh diganti nilai acak di .env"
  fi
  case "${POSTGRES_PASSWORD:-}" in ""|ganti-password-db)
    echo "PERINGATAN: POSTGRES_PASSWORD masih contoh. Database tidak dibuka ke luar, tetapi ganti sebelum publik"
    echo "            (ganti di .env SEBELUM head-up pertama, atau ALTER USER hpc PASSWORD di database lama)." ;;
  esac
  [ -n "${ADMIN_EMAIL:-}" ] && [ -n "${ADMIN_PASSWORD_HASH:-}" ] || echo "PERINGATAN: login admin belum diatur. Jalankan ./hpc.sh admin-setup"
  return 0
}
ensure_node_token() { ensure_secrets; }

stop_watch() {
  for f in hpc/watch/.head.pid hpc/watch/.worker.pid; do
    [ -f "$f" ] && { kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"; }
  done
  return 0
}

case "$1" in
  # ---- Head node ----
  head-up)      ensure_node_token
                $HEAD up -d --build; $HEAD ps; echo "Dashboard: http://localhost:8000"
                echo "Compute node relawan: ssh -p ${NODE_SSH_PORT:-2222} (node1) / -p ${NODE2_SSH_PORT:-2223} (node2) jd<id>@${NODE_SSH_HOST:-localhost}" ;;
  head-online)  $HEAD --profile online up -d; sleep 8
                URL=$($HEAD logs tunnel 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
                SSHURL=$($HEAD logs tunnel-ssh 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
                SSHURL2=$($HEAD logs tunnel-ssh2 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
                echo "Alamat HTTPS untuk relawan (COORDINATOR_URL di repo worker): ${URL:-(belum muncul, ulangi perintah ini)}"
                echo "SSH node1 lewat internet: ${SSHURL:-(belum muncul, ulangi perintah ini)}"
                echo "SSH node2 lewat internet: ${SSHURL2:-(belum muncul, ulangi perintah ini)}"
                # Simpan ke koordinator agar dashboard relawan menampilkan perintah setup / ssh yang tepat
                [ -n "$URL" ] && curl -s -o /dev/null -X POST http://localhost:8000/api/admin/public-url \
                  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
                  -d "{\"url\":\"$URL\",\"ssh_urls\":{\"node1\":\"$SSHURL\",\"node2\":\"$SSHURL2\"}}" && echo "(tersimpan; tampil di dashboard relawan)" || true ;;
  nodes)        curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/api/admin/nodes | python3 -c '
import json, sys
d = json.load(sys.stdin)
for n in d.get("nodes", []):
    st = "ONLINE " if n["online"] else "OFFLINE"
    print("%-10s %s %s/%s relawan  ip %s" % (n["name"], st, n["users"], n["max_users"], n["ip"]))
print()
for a in d.get("access", [])[:30]:
    st = "AKTIF" if a["status"] == "active" else "dicabut"
    print("#%-4s %-8s %-8s node %-6s sesi %s  %s  %s  %s" % (a["jobdesk_id"], a["username"], st, a["node"] or "-",
          a["sessions"], a["worker_name"], a["branch"] or "", a["revoked_reason"] or ""))
' ;;
  node-revoke)  [ -n "${2:-}" ] || { echo "Pemakaian: ./hpc.sh node-revoke <id_jobdesk> [alasan]"; exit 1; }
                curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
                  "http://localhost:8000/api/admin/jobdesks/$2/revoke-node" -d "{\"reason\":\"${3:-}\"}"; echo ;;
  head-down)    $HEAD --profile online down ;;
  head-reset)   $HEAD --profile online down -v; echo "Database dihapus." ;;
  head-logs)    $HEAD logs -f --tail 50 ${2:-} ;;
  job)          # ./hpc.sh job [montecarlo_pi|mandelbrot] [n]   atau   ./hpc.sh job heat2d [blok] [tahap] [langkah] [N]
                if [ "${2:-}" = "heat2d" ]; then
                  BODY="{\"kind\":\"heat2d\",\"n_tasks\":${3:-8},\"params\":{\"stages\":${4:-10},\"steps\":${5:-20},\"n\":${6:-160},\"verify_serial\":true}}"
                else
                  BODY="{\"kind\":\"${2:-montecarlo_pi}\",\"n_tasks\":${3:-20}}"
                fi
                curl -s -X POST http://localhost:8000/api/jobs \
                  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d "$BODY"; echo ;;
  job-repo)     # ./hpc.sh job-repo <commit-sha> <task_kind> [n] [repo_url]  (repo bawaan: JOB_REPO_URL di .env)
                [ -n "${2:-}" ] && [ -n "${3:-}" ] || { echo "Pemakaian: ./hpc.sh job-repo <commit-sha> <task_kind> [n] [repo_url]"; exit 1; }
                REPO_JSON=""; [ -n "${5:-}" ] && REPO_JSON="\"repo_url\":\"$5\","
                curl -s -X POST http://localhost:8000/api/jobs \
                  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
                  -d "{\"kind\":\"repo\",\"task_kind\":\"$3\",\"n_tasks\":${4:-10},\"code\":{${REPO_JSON}\"sha\":\"$2\"}}"; echo ;;
  jobdesk-add)  # ./hpc.sh jobdesk-add "<judul>" [kredit] [fitur|bug|lainnya]   -> masuk antrean FIFO
                [ -n "${2:-}" ] || { echo 'Pemakaian: ./hpc.sh jobdesk-add "<judul>" [kredit] [fitur|bug|lainnya]'; exit 1; }
                BODY=$(python3 -c 'import json,sys; print(json.dumps({"title": sys.argv[1], "credit": int(sys.argv[2]), "kind": sys.argv[3]}))' \
                  "$2" "${3:-10}" "${4:-fitur}")
                curl -s -X POST http://localhost:8000/api/admin/jobdesks \
                  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d "$BODY"; echo ;;
  jobdesks)     curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/api/admin/jobdesks | python3 -c '
import json, sys
d = json.load(sys.stdin)
if "jobdesks" not in d: sys.exit(print(d))
print("%4s  %-11s %-34s %-14s %-8s %s" % ("id", "status", "judul", "relawan", "CI", "branch"))
for j in d["jobdesks"]:
    print("%4d  %-11s %-34s %-14s %-8s %s" % (j["id"], j["status"], j["title"][:34], (j["worker_name"] or "-")[:14],
          j["last_ci_status"] or "-", j["branch"] or "-"))
' ;;
  ci)           # ./hpc.sh ci [branch]   jalankan CI terdistribusi untuk ujung branch repo B (bawaan main)
                curl -s -X POST http://localhost:8000/api/admin/ci \
                  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
                  -d "{\"branch\":\"${2:-main}\"}"; echo ;;
  ci-status)    curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://localhost:8000/api/admin/ci?limit=${2:-10}" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if "runs" not in d: sys.exit(print(d))
print("%5s  %-32s %-8s %-9s %-7s %5s %8s %7s" % ("job", "branch@sha", "status", "tahap", "file", "node", "waktu", "speedup"))
for r in d["runs"]:
    print("%5d  %-32s %-8s %-9s %-7s %5s %8s %7s" % (r["job_id"], (r["branch"] + "@" + r["sha"][:7])[-32:], r["status"],
          r["step"], "%s/%s" % (r["shards_done"], r["shards"]), r["nodes"], r["wall_s"] or "-", r["speedup_est"] or "-"))
' ;;
  job-result)   [ -n "${2:-}" ] || { echo "Pemakaian: ./hpc.sh job-result <job_id>"; exit 1; }
                curl -s "http://localhost:8000/api/jobs/$2/result" | python3 -m json.tool ;;
  leaderboard)  curl -s "http://localhost:8000/api/leaderboard?limit=${2:-20}" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("%3s  %-26s %-9s %6s %6s %8s" % ("#", "relawan", "lencana", "kredit", "valid", "ditolak"))
for r in d["leaderboard"]:
    gh = "@" + r["github_username"] if r["github_username"] else "anonim"
    print("%3d  %-26s %-9s %6d %6d %7.1f%%" % (r["rank"], (r["name"] + " " + gh)[:26], r["badge"] or "-",
          r["credits"], r["tasks_validated"], r["reject_pct"]))
' ;;
  admin-setup)  # Atur email + password admin untuk dashboard admin web (/admin)
                python3 hpc/head/coordinator/admin_auth.py set .env ;;
  stats)        curl -s http://localhost:8000/api/stats | python3 -m json.tool 2>/dev/null \
                  || curl -s http://localhost:8000/api/stats; echo ;;

  # ---- Autentikasi Worker ----
  worker-login|login)
                # Autentikasi interaktif: verifikasi GitHub + kirim OTP ke email
                # Setelah selesai, WORKER_TOKEN & WORKER_ID tersimpan ke .env secara otomatis
                if command -v python3 >/dev/null 2>&1; then
                    python3 hpc/worker_auth_cli.py "${@:2}"
                else
                    echo "[ERROR] python3 tidak ditemukan. Install Python 3.8+ lalu coba lagi."
                    exit 1
                fi ;;

  # ---- Compute node ----
  worker-up)    $WORK up -d --build --scale worker=${2:-1}; $WORK ps ;;
  worker-cheat) CHEAT=1 WORKER_NAME=curang $WORK -p hpc-cheat up -d --build ;;
  worker-down)  $WORK down; $WORK -p hpc-cheat down 2>/dev/null || true ;;
  worker-logs)  $WORK logs -f --tail 50 ;;
  worker-status)
                # Cek identitas worker ke koordinator via /api/auth/me
                echo "=== Status Worker di .env ==="
                echo "WORKER_NAME  : ${WORKER_NAME:-(belum diisi)}"
                echo "WORKER_ID    : ${WORKER_ID:-(belum diisi)}"
                if [ -n "$WORKER_TOKEN" ]; then
                    echo "WORKER_TOKEN : ${WORKER_TOKEN:0:12}...(tersimpan)"
                    echo ""
                    echo "=== Verifikasi Token ke Koordinator ==="
                    curl -s "${COORDINATOR_URL:-http://localhost:8000}/api/auth/me" \
                         -H "Authorization: Bearer $WORKER_TOKEN" | python3 -m json.tool 2>/dev/null \
                      || echo "(koordinator tidak dapat dihubungi)"
                else
                    echo "WORKER_TOKEN : (belum diisi - jalankan: ./hpc.sh worker-login)"
                fi ;;

  # ---- Watch folder: log aktivitas ----
  watch-start)  mkdir -p hpc/watch
                stop_watch
                # Log lama > 50 MB diputar agar folder watch/ tidak terus membesar
                for f in hpc/watch/head-activity.log hpc/watch/worker-activity.log; do
                  [ -f "$f" ] && [ "$(wc -c < "$f")" -gt 52428800 ] && mv "$f" "$f.1"
                done
                nohup setsid $HEAD logs -f --timestamps --no-color --tail 0 >> hpc/watch/head-activity.log 2>&1 < /dev/null &
                echo $! > hpc/watch/.head.pid
                nohup setsid $WORK logs -f --timestamps --no-color --tail 0 >> hpc/watch/worker-activity.log 2>&1 < /dev/null &
                echo $! > hpc/watch/.worker.pid
                echo "Log aktivitas dicatat ke hpc/watch/head-activity.log dan hpc/watch/worker-activity.log" ;;
  watch-stop)   stop_watch; echo "Pencatatan log aktivitas dihentikan." ;;
  watch)        for f in hpc/watch/.head.pid hpc/watch/.worker.pid; do
                  if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then echo "$f: aktif"; else echo "$f: mati"; fi
                done
                tail -n ${2:-20} hpc/watch/head-activity.log hpc/watch/worker-activity.log 2>/dev/null
                echo; "$0" alerts ;;

  # ---- Backup folder: backup database (otomatis tiap jam oleh layanan "backup") ----
  backup)       # backup sekarang juga, lewat layanan backup (hasil + catatan sama dengan yang otomatis)
                $HEAD exec -T backup /bin/sh /backup.sh once ;;
  backups)      # daftar backup terakhir dari koordinator + isi folder backup/
                curl -s "http://localhost:8000/api/admin/backups?limit=${2:-10}" -H "Authorization: Bearer $ADMIN_TOKEN" \
                  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(('OK   ' if b['ok'] else 'GAGAL'), b['at'][:19], b['file'] or '-', b['bytes'] or '', 'salinan-luar' if b['copied'] else '', b['error'] or '') for b in d.get('backups', [])]" \
                  || echo "(koordinator tidak dapat dihubungi)"
                echo; ls -lh hpc/backup/hourly hpc/backup/daily 2>/dev/null | grep -v '^total' ;;
  backup-env)   # .env berisi password/token: disimpan TERENKRIPSI (AES-256, passphrase Anda)
                mkdir -p hpc/backup/env
                OUT="hpc/backup/env/env-$(date +%Y%m%d-%H%M%S).enc"
                openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in .env -out "$OUT" \
                  && echo "Tersimpan terenkripsi: $OUT (buka: ./hpc.sh restore-env $OUT)" ;;
  restore-env)  [ -f "${2:-}" ] || { echo "Pemakaian: ./hpc.sh restore-env hpc/backup/env/env-....enc"; exit 1; }
                openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$2" -out .env.pulih \
                  && echo "Didekripsi ke .env.pulih. Periksa, lalu: mv .env.pulih .env" ;;
  restore)      [ -f "${2:-}" ] || { echo "Pemakaian: ./hpc.sh restore hpc/backup/hourly/hpc-db-....sql.gz  (lihat: ./hpc.sh backups)"; exit 1; }
                gunzip -t "$2" || { echo "File backup rusak: $2"; exit 1; }
                read -r -p "Database sekarang akan DITIMPA dengan $2. Lanjut? [y/N] " OK
                [ "$OK" = "y" ] || [ "$OK" = "Y" ] || { echo "Dibatalkan."; exit 1; }
                $HEAD exec -T backup /bin/sh /backup.sh once >/dev/null 2>&1 && echo "(backup kondisi sebelum restore dibuat)"
                gunzip -c "$2" | $HEAD exec -T db psql -q -U hpc -d hpc
                echo "Database dipulihkan dari $2" ;;

  # ---- Peringatan admin (hasil watch) ----
  alerts)       # ./hpc.sh alerts [all]   peringatan terbuka (atau semua)
                curl -s "http://localhost:8000/api/admin/alerts?state=${2:-open}&limit=50" -H "Authorization: Bearer $ADMIN_TOKEN" \
                  | python3 -c "
import json,sys
d=json.load(sys.stdin); s=d.get('summary') or {}
print(f\"Terbuka: {s.get('open',0)} (critical {s.get('critical',0)}, warning {s.get('warning',0)}, info {s.get('info',0)})\")
for a in d.get('alerts', []):
    st = 'ditangani' if a['acked_at'] else 'TERBUKA'
    print(f\"#{a['id']:<5} {a['level'].upper():8} {a['category']:10} {a['last_at'][:16]} {st:9} {a['title']}\" + (f\" (x{a['count']})\" if a['count'] > 1 else ''))
" || echo "(koordinator tidak dapat dihubungi)" ;;
  alert-ack)    [ -n "${2:-}" ] || { echo "Pemakaian: ./hpc.sh alert-ack <id|all>"; exit 1; }
                if [ "$2" = "all" ]; then P="ack-all"; else P="$2/ack"; fi
                curl -s -X POST "http://localhost:8000/api/admin/alerts/$P" -H "Authorization: Bearer $ADMIN_TOKEN"; echo ;;

  # ---- Web Portal (Next.js) ----
  web-dev)
                echo "Menjalankan Web Portal Next.js (mode pengembangan) di http://localhost:3000 ..."
                # package-lock.json lebih baru dari node_modules (mis. habis upgrade Next 15) -> npm install dulu
                cd web && { [ node_modules/.package-lock.json -nt package-lock.json ] || npm install; } && npm run dev ;;
  web-prod)     # Untuk PUBLIK: build produksi + next start (bukan next dev)
                ensure_secrets
                cd web && npm ci && npm run build && echo "Web produksi di http://localhost:3000" && NODE_ENV=production npx next start ;;

  *) cat << 'USAGE'
Pemakaian: ./hpc.sh <perintah>

Head node:
  head-up              build & jalankan db, coordinator, validator (dashboard :8000)
  head-online          buka tunnel HTTPS Cloudflare, tampilkan alamat untuk relawan
  head-logs [layanan]  lihat log (coordinator / validator / node / db / tunnel)
  nodes                compute node relawan: online/offline, akses per jobdesk (user, sesi login)
  node-revoke <id> [alasan]
                       cabut akses compute node jobdesk itu sekarang (sesi SSH diputus)
  head-down            matikan semua (data tetap)
  head-reset           matikan dan HAPUS database
  job [jenis] [n]      buat job bag-of-tasks: montecarlo_pi (bawaan) atau mandelbrot, n tugas (bawaan 20)
  job heat2d [blok] [tahap] [langkah] [N]
                       job MULTI-TAHAP simulasi panas 2D (bawaan 8 blok, 10 tahap, 20 langkah, grid 160)
  job-repo <sha> <task_kind> [n] [repo_url]
                       job dari repo job pada commit SHA (repo bawaan: JOB_REPO_URL)
  job-result <id>      hasil akhir job (JSON), termasuk branch hasil di GitHub bila dipublikasikan
  leaderboard [n]      papan peringkat relawan

Proyek perangkat lunak (repo B, PROJECT_REPO_URL di .env):
  jobdesk-add "<judul>" [kredit] [fitur|bug|lainnya]   tambah jobdesk ke antrean FIFO
  jobdesks             papan jobdesk: status, relawan, hasil CI, branch
  ci [branch]          jalankan CI terdistribusi untuk ujung branch (bawaan main)
  ci-status [n]        n CI terakhir: status, tahap, jumlah node, waktu, percepatan
  stats                ringkasan status dalam JSON
  admin-setup          atur email + password login dashboard admin (disimpan sebagai hash di .env)

Compute node (alur pertama kali):
  worker-login         autentikasi interaktif: verifikasi GitHub + OTP ke email
                       -> simpan WORKER_TOKEN & WORKER_ID ke .env secara otomatis
  worker-status        tampilkan identitas worker yang tersimpan di .env
  worker-up [n]        jalankan n worker sandbox (bawaan 1)
  worker-cheat         jalankan 1 worker curang (uji validator)
  worker-logs          lihat log worker
  worker-down          matikan semua worker

Watch, peringatan & backup:
  alerts [all]         peringatan untuk admin (error, aktivitas mencurigakan, cek per branch, backup)
  alert-ack <id|all>   tandai peringatan sudah ditangani
  watch-start          catat log aktivitas head & worker ke folder watch/ (jalan di latar)
  watch [n]            status pencatat + n baris log terakhir (bawaan 20) + peringatan terbuka
  watch-stop           hentikan pencatatan log aktivitas
  backup               backup database sekarang (otomatis sudah tiap jam: backup/hourly + backup/daily)
  backups [n]          daftar backup terakhir (berhasil/gagal, salinan luar)
  restore <file>       pulihkan database dari backup/hourly|daily/hpc-db-*.sql.gz (minta konfirmasi)
  backup-env           simpan .env TERENKRIPSI ke backup/env/ (passphrase; .env berisi password)
  restore-env <file>   dekripsi backup .env ke .env.pulih

Web Portal:
  web-dev              jalankan portal web Next.js mode pengembangan (port :3000)
  web-prod             build + jalankan portal web mode produksi (untuk publik, port :3000)
USAGE
  ;;
esac

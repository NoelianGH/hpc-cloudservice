#!/usr/bin/env bash
# Pintasan perintah proyek Cloud Service HPC. Jalankan dari folder proyek: ./hpc.sh <perintah>
set -e
cd "$(dirname "$0")"
[ -f .env ] || { cp .env.example .env; echo "File .env dibuat dari .env.example. Ubah isinya bila perlu."; }
set -a; . ./.env; set +a

HEAD="docker compose --env-file .env -p hpc-head -f head/docker-compose.yml"
WORK="docker compose --env-file .env -p hpc-worker -f compute/docker-compose.yml"

case "$1" in
  # ---- Head node ----
  head-up)      $HEAD up -d --build; $HEAD ps; echo "Dashboard: http://localhost:8000" ;;
  head-online)  $HEAD --profile online up -d; sleep 8
                echo "Alamat HTTPS untuk relawan (isi ke COORDINATOR_URL):"
                $HEAD logs tunnel 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1 ;;
  head-down)    $HEAD --profile online down ;;
  head-reset)   $HEAD --profile online down -v; echo "Database dihapus." ;;
  head-logs)    $HEAD logs -f --tail 50 ${2:-} ;;
  job)          curl -s -X POST http://localhost:8000/api/jobs \
                  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
                  -d "{\"kind\":\"${2:-montecarlo_pi}\",\"n_tasks\":${3:-20}}"; echo ;;
  stats)        curl -s http://localhost:8000/api/stats | python3 -m json.tool 2>/dev/null \
                  || curl -s http://localhost:8000/api/stats; echo ;;

  # ---- Autentikasi Worker ----
  worker-login|login)
                # Autentikasi interaktif: verifikasi GitHub + kirim OTP ke email
                # Setelah selesai, WORKER_TOKEN & WORKER_ID tersimpan ke .env secara otomatis
                if command -v python3 >/dev/null 2>&1; then
                    python3 worker_auth_cli.py "${@:2}"
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

  # ---- Web Portal (Next.js) ----
  web-dev)
                echo "Menjalankan Web Portal Next.js di http://localhost:3000 ..."
                cd web && npm run dev ;;

  *) cat << 'USAGE'
Pemakaian: ./hpc.sh <perintah>

Head node:
  head-up              build & jalankan db, coordinator, validator (dashboard :8000)
  head-online          buka tunnel HTTPS Cloudflare, tampilkan alamat untuk relawan
  head-logs [layanan]  lihat log (coordinator / validator / db / tunnel)
  head-down            matikan semua (data tetap)
  head-reset           matikan dan HAPUS database
  job [jenis] [n]      buat job: montecarlo_pi (bawaan) atau mandelbrot, n tugas (bawaan 20)
  stats                ringkasan status dalam JSON

Compute node (alur pertama kali):
  worker-login         autentikasi interaktif: verifikasi GitHub + OTP ke email
                       -> simpan WORKER_TOKEN & WORKER_ID ke .env secara otomatis
  worker-status        tampilkan identitas worker yang tersimpan di .env
  worker-up [n]        jalankan n worker sandbox (bawaan 1)
  worker-cheat         jalankan 1 worker curang (uji validator)
  worker-logs          lihat log worker
  worker-down          matikan semua worker

Web Portal:
  web-dev              jalankan portal web Next.js (port :3000)
USAGE
  ;;
esac

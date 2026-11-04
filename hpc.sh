#!/usr/bin/env bash
# Pintasan perintah proyek Cloud Service HPC. Jalankan dari folder proyek: ./hpc.sh <perintah>
set -e
cd "$(dirname "$0")"
[ -f .env ] || { cp .env.example .env; echo "File .env dibuat dari .env.example. Ubah isinya bila perlu."; }
set -a; . ./.env; set +a

HEAD="docker compose --env-file .env -p hpc-head -f head/docker-compose.yml"
WORK="docker compose --env-file .env -p hpc-worker -f compute/docker-compose.yml"

case "$1" in
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
  stats)        curl -s http://localhost:8000/api/stats; echo ;;
  worker-up)    $WORK up -d --build --scale worker=${2:-1}; $WORK ps ;;
  worker-cheat) CHEAT=1 WORKER_NAME=curang $WORK -p hpc-cheat up -d --build ;;
  worker-down)  $WORK down; $WORK -p hpc-cheat down 2>/dev/null || true ;;
  worker-logs)  $WORK logs -f --tail 50 ;;
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

Compute node:
  worker-up [n]        jalankan n worker sandbox (bawaan 1)
  worker-cheat         jalankan 1 worker curang (uji validator)
  worker-logs          lihat log worker
  worker-down          matikan semua worker
USAGE
  ;;
esac
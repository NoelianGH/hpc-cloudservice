#!/bin/sh
# Backup database head node, dijalankan oleh layanan "backup" (docker compose).
#   backup.sh          loop: backup saat start (bila backup terakhir > 50 menit), lalu tiap awal jam
#   backup.sh once     satu kali sekarang (dipakai "./hpc.sh backup")
#
# Hasil (folder backup/ di root repo, di-mount ke /backup):
#   backup/hourly/hpc-db-YYYYmmdd-HHMMSS.sql.gz   simpan BACKUP_KEEP_HOURLY terbaru (bawaan 24)
#   backup/daily/hpc-db-YYYYmmdd.sql.gz           1 per hari, simpan BACKUP_KEEP_DAILY (bawaan 7)
#   + salinan ke BACKUP_COPY_DIR (mis. folder Google Drive/OneDrive) bila diisi
# Setiap backup dicek (gzip -t, berisi tabel workers) lalu dicatat di tabel "backups";
# koordinator memberi PERINGATAN ke admin bila backup gagal atau terlambat.
# File .env TIDAK ikut (berisi password). Gunakan "./hpc.sh backup-env" (terenkripsi).
set -u
KEEP_H=${BACKUP_KEEP_HOURLY:-24}
KEEP_D=${BACKUP_KEEP_DAILY:-7}
COPY=0; [ -n "${BACKUP_COPY_DIR:-}" ] && COPY=1   # path di host; di kontainer di-mount ke /backup-copy
export PGHOST=${PGHOST:-db} PGUSER=${PGUSER:-hpc} PGDATABASE=${PGDATABASE:-hpc}

say() { echo "[backup] $(date '+%Y-%m-%d %H:%M:%S %Z') $*"; }
sq() { printf "%s" "$1" | sed "s/'/''/g"; }

record() { # ok file bytes sha256 copied error
  psql -q -v ON_ERROR_STOP=1 -c "CREATE TABLE IF NOT EXISTS backups (
      id SERIAL PRIMARY KEY, at TIMESTAMPTZ NOT NULL DEFAULT now(), ok BOOLEAN NOT NULL,
      file TEXT, bytes BIGINT, sha256 TEXT, copied BOOLEAN NOT NULL DEFAULT FALSE, error TEXT)" \
    -c "INSERT INTO backups (ok, file, bytes, sha256, copied, error) VALUES
        ($1, NULLIF('$(sq "$2")',''), NULLIF('$3','')::bigint, NULLIF('$4',''), $5, NULLIF('$(sq "$6")',''))" \
    >/dev/null 2>&1 || say "PERINGATAN: gagal mencatat ke tabel backups"
}

rotate() { # folder pola jumlah
  ls -1t "$1"/$2 2>/dev/null | tail -n +$(( $3 + 1 )) | while read -r f; do rm -f "$f"; done
}

run_backup() {
  mkdir -p /backup/hourly /backup/daily
  ts=$(date +%Y%m%d-%H%M%S); day=$(date +%Y%m%d)
  out=/backup/hourly/hpc-db-$ts.sql.gz
  err=$(pg_dump --clean --if-exists 2>&1 >/tmp/dump.sql) || { rm -f /tmp/dump.sql; say "GAGAL pg_dump: $err"; record false "" "" "" false "pg_dump: $err"; return 1; }
  if ! grep -q "CREATE TABLE public.workers" /tmp/dump.sql; then
    rm -f /tmp/dump.sql; say "GAGAL: hasil dump tidak berisi tabel workers"; record false "" "" "" false "dump tidak lengkap"; return 1
  fi
  gzip -c /tmp/dump.sql > "$out.tmp" && rm -f /tmp/dump.sql && gzip -t "$out.tmp" && mv "$out.tmp" "$out" \
    || { rm -f "$out.tmp" /tmp/dump.sql; say "GAGAL menulis $out (disk penuh?)"; record false "" "" "" false "gagal menulis file backup"; return 1; }
  bytes=$(wc -c < "$out" | tr -d ' '); sum=$(sha256sum "$out" | cut -c1-64)
  [ -f "/backup/daily/hpc-db-$day.sql.gz" ] || cp "$out" "/backup/daily/hpc-db-$day.sql.gz"
  rotate /backup/hourly 'hpc-db-*.sql.gz' "$KEEP_H"
  rotate /backup/daily 'hpc-db-*.sql.gz' "$KEEP_D"
  copied=false; cerr=""
  if [ "$COPY" = "1" ]; then
    if mkdir -p /backup-copy/hourly /backup-copy/daily && cp "$out" /backup-copy/hourly/ \
       && cp "/backup/daily/hpc-db-$day.sql.gz" /backup-copy/daily/; then
      rotate /backup-copy/hourly 'hpc-db-*.sql.gz' "$KEEP_H"; rotate /backup-copy/daily 'hpc-db-*.sql.gz' "$KEEP_D"
      copied=true
    else
      cerr="salinan ke BACKUP_COPY_DIR gagal"
    fi
  fi
  record true "hourly/$(basename "$out")" "$bytes" "$sum" "$copied" "$cerr"
  say "OK $out ($bytes byte, sha256 $(echo "$sum" | cut -c1-12)...)${cerr:+, $cerr}"
}

until pg_isready -q; do sleep 2; done
if [ "${1:-}" = "once" ]; then run_backup; exit $?; fi

say "jalan: tiap jam, simpan $KEEP_H per jam + $KEEP_D harian, salinan luar=$COPY"
recent=$(psql -tAc "SELECT count(*) FROM backups WHERE ok AND at > now() - interval '50 minutes'" 2>/dev/null || echo 0)
[ "${recent:-0}" -gt 0 ] 2>/dev/null || run_backup
while true; do
  sleep $(( 3600 - $(date +%s) % 3600 + 5 ))
  run_backup || true
done

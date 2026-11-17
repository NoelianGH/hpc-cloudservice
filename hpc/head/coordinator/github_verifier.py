import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Konfigurasi ambang batas (threshold) dari environment variable atau nilai default
MIN_ACCOUNT_AGE_DAYS = int(os.environ.get("GITHUB_MIN_ACCOUNT_AGE_DAYS", "30"))
MIN_PUBLIC_REPOS = int(os.environ.get("GITHUB_MIN_PUBLIC_REPOS", "2"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


def check_github_worker(username: str) -> dict:
    """
    Melakukan verifikasi akun GitHub untuk mendeteksi apakah worker merupakan
    akun asli atau fake/bot worker (misal: sybil attack, throwaway account).

    Faktor-faktor yang diuji:
    1. Keberadaan akun di GitHub API
    2. [FAKTOR UTAMA] Usia akun (Account Age)
    3. [FAKTOR UTAMA] Jumlah repositori publik (Public Repos)
    4. [FAKTOR TAMBAHAN] Jumlah pengikut (Followers Count)
    5. [FAKTOR TAMBAHAN] Kelengkapan profil (Bio, Nama Lengkap, dsb)
    6. [FAKTOR TAMBAHAN] Pembaruan akun terakhir (Account Activity / Recency)
    7. [FAKTOR TAMBAHAN] Rasio following vs followers (Spam Indicators)
    8. [FAKTOR TAMBAHAN] Tipe entitas akun (User vs Bot/Org)
    """
    clean_username = username.strip()
    if not clean_username:
        return {
            "passed": False,
            "username": username,
            "reasons": ["Username GitHub tidak boleh kosong."],
            "factors": {},
            "score": 0,
        }

    # =========================================================================
    # 1. PENGAMBILAN DATA DARI GITHUB API
    # =========================================================================
    url = f"https://api.github.com/users/{clean_username}"
    headers = {
        "User-Agent": "HPC-CloudService-Coordinator/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    # Jika admin menyediakan GITHUB_TOKEN di .env, gunakan untuk menaikkan rate limit
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {
                "passed": False,
                "username": clean_username,
                "reasons": [f"Akun GitHub '{clean_username}' tidak ditemukan (404)."],
                "factors": {},
                "score": 0,
            }
        elif e.code in (403, 429):
            # Jika terkena rate-limit dari GitHub API
            return {
                "passed": False,
                "username": clean_username,
                "reasons": [
                    "Batas permintaan GitHub API (rate limit) tercapai. Silakan coba lagi nanti atau pasang GITHUB_TOKEN."
                ],
                "factors": {},
                "score": 0,
            }
        else:
            return {
                "passed": False,
                "username": clean_username,
                "reasons": [f"Gagal menghubungi GitHub API (Status: {e.code})."],
                "factors": {},
                "score": 0,
            }
    except Exception as e:
        return {
            "passed": False,
            "username": clean_username,
            "reasons": [f"Kesalahan jaringan saat verifikasi GitHub: {str(e)}"],
            "factors": {},
            "score": 0,
        }

    now_utc = datetime.now(timezone.utc)
    reasons = []
    score = 100

    # =========================================================================
    # FAKTOR UTAMA 1: Usia Akun (Account Age)
    # =========================================================================
    # Penjelasan:
    # Akun bot/fake worker umumnya dibuat secara massal sesaat sebelum mendaftar
    # (throwaway account). Dengan memeriksa tanggal pembuatan akun (created_at),
    # kita dapat memastikan akun sudah berumur dan memiliki riwayat wajar.
    # Ambang batas default: minimal 30 hari.
    # =========================================================================
    created_at_raw = data.get("created_at")
    account_age_days = 0
    if created_at_raw:
        try:
            created_at_dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            account_age_days = (now_utc - created_at_dt).days
        except Exception:
            pass

    passed_age = account_age_days >= MIN_ACCOUNT_AGE_DAYS
    if not passed_age:
        reasons.append(
            f"Usia akun terlalu baru ({account_age_days} hari). Minimal {MIN_ACCOUNT_AGE_DAYS} hari untuk mencegah throwaway/bot account."
        )
        score -= 40

    # =========================================================================
    # FAKTOR UTAMA 2: Jumlah Proyek / Repositori Publik (Public Repos)
    # =========================================================================
    # Penjelasan:
    # Developer/relawan komputasi riil umumnya memiliki jejak portofolio berupa
    # repositori publik di akun GitHub mereka. Akun bot/palsu biasanya tidak
    # memiliki proyek sama sekali (0 repositori).
    # Ambang batas default: minimal 2 repositori publik.
    # =========================================================================
    public_repos = int(data.get("public_repos", 0))
    passed_repos = public_repos >= MIN_PUBLIC_REPOS
    if not passed_repos:
        reasons.append(
            f"Jumlah repositori publik ({public_repos}) kurang dari syarat minimal ({MIN_PUBLIC_REPOS} repo)."
        )
        score -= 35

    # =========================================================================
    # FAKTOR TAMBAHAN 3: Jumlah Pengikut (Followers Count)
    # =========================================================================
    # Penjelasan:
    # Akun manusia alami umumnya terhubung dengan komunitas dan memiliki pengikut.
    # Bot otomatis hampir selalu memiliki 0 follower. Jika follower == 0,
    # diberi penalti kecil, tetapi jika ada followers akan menambah kepercayaan.
    # =========================================================================
    followers = int(data.get("followers", 0))
    if followers == 0:
        score -= 10
        # Tidak langsung menggagalkan, tetapi dicatat dalam skor reputasi

    # =========================================================================
    # FAKTOR TAMBAHAN 4: Kelengkapan Profil (Profile Completeness)
    # =========================================================================
    # Penjelasan:
    # Akun asli biasanya mengisi identitas seperti nama lengkap, bio singkat,
    # lokasi, atau tautan blog/portofolio.
    # Akun bot seringkali membiarkan nama kosong (hanya username) dan bio kosong.
    # =========================================================================
    has_name = bool(data.get("name") and data.get("name").strip())
    has_bio = bool(data.get("bio") and data.get("bio").strip())
    has_location = bool(data.get("location") and data.get("location").strip())
    profile_complete = has_name or has_bio or has_location
    if not profile_complete:
        score -= 10
        # Penalti jika profil sama sekali kosong tanpa nama/bio/lokasi

    # =========================================================================
    # FAKTOR TAMBAHAN 5: Aktivitas & Pembaruan Terakhir (Recency of Activity)
    # =========================================================================
    # Penjelasan:
    # Memeriksa atribut `updated_at`. Jika akun tidak pernah diperbarui sama sekali
    # dalam kurun waktu sangat lama (misal akun dormant/ditinggalkan bertahun-tahun
    # yang tiba-tiba dipakai kembali oleh pihak ketiga), ini dicatat sebagai indikator.
    # =========================================================================
    updated_at_raw = data.get("updated_at")
    days_since_update = 0
    if updated_at_raw:
        try:
            updated_at_dt = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
            days_since_update = (now_utc - updated_at_dt).days
        except Exception:
            pass

    # =========================================================================
    # FAKTOR TAMBAHAN 6: Rasio Following vs Followers (Indikasi Spam Bot)
    # =========================================================================
    # Penjelasan:
    # Akun spam seringkali mem-follow puluhan/ratusan pengguna lain secara acak
    # namun tidak memiliki satu pun followers (following > 50 dan followers == 0).
    # =========================================================================
    following = int(data.get("following", 0))
    is_spam_following = following > 50 and followers == 0
    if is_spam_following:
        reasons.append("Pola akun mencurigakan (mengikuti banyak orang tetapi tanpa pengikut/followers).")
        score -= 25

    # =========================================================================
    # FAKTOR TAMBAHAN 7: Tipe Akun (User vs Bot/Org)
    # =========================================================================
    # Penjelasan:
    # Memastikan bahwa tipe entitas akun GitHub adalah 'User' (pengguna pribadi),
    # bukan organisasi atau bot terdaftar.
    # =========================================================================
    account_type = data.get("type", "User")
    if account_type != "User":
        reasons.append(f"Tipe akun bukan akun personal User (terdeteksi: {account_type}).")
        score -= 50

    # =========================================================================
    # EVALUASI AKHIR
    # =========================================================================
    # Akun dinyatakan lolos (bukan fake worker) HANYA JIKA:
    # 1. Faktor utama 1 (Usia akun) terpenuhi
    # 2. Faktor utama 2 (Repositori publik) terpenuhi
    # 3. Tidak terindikasi spam following
    # 4. Total skor reputasi >= 50
    # =========================================================================
    passed = passed_age and passed_repos and not is_spam_following and (score >= 50)

    factors_detail = {
        "account_age_days": account_age_days,
        "min_account_age_days": MIN_ACCOUNT_AGE_DAYS,
        "passed_age": passed_age,
        "public_repos": public_repos,
        "min_public_repos": MIN_PUBLIC_REPOS,
        "passed_repos": passed_repos,
        "followers": followers,
        "following": following,
        "profile_complete": profile_complete,
        "has_name": has_name,
        "has_bio": has_bio,
        "days_since_update": days_since_update,
        "account_type": account_type,
    }

    return {
        "passed": passed,
        "username": clean_username,
        "score": max(0, score),
        "reasons": reasons if not passed else ["Akun memenuhi kriteria verifikasi reputasi GitHub."],
        "factors": factors_detail,
        "github_profile": {
            "name": data.get("name"),
            "avatar_url": data.get("avatar_url"),
            "html_url": data.get("html_url"),
        },
    }


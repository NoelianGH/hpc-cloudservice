/**
 * Sesi relawan (worker) di web portal.
 * Token worker (hpc_w_...) disimpan di cookie httpOnly, bukan localStorage, dan
 * diteruskan ke koordinator sebagai Authorization: Bearer pada setiap request.
 * Koordinator yang memutuskan token sah atau tidak (lihat /api/auth/me dan /api/me).
 */
export const WORKER_COOKIE = "hpc_worker_session";
export const WORKER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 hari

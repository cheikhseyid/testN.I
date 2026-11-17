// Minimal API client: get/post with an 8 s timeout and readable error messages.
(function () {
  const cfg = window.MAWJOUD_CONFIG || {};
  const BASE = (cfg.API_BASE || "").replace(/\/$/, "");
  const TIMEOUT = cfg.TIMEOUT_MS || 8000;

  // Translated message if i18n is loaded, French fallback otherwise.
  function msg(key, fallback) {
    const t = window.i18n && window.i18n.t(key);
    return t && t !== key ? t : fallback;
  }

  class ApiError extends Error {
    // kind: "timeout" (no answer in time), "network" (unreachable) or "http" (answered with an error)
    constructor(message, status, kind) {
      super(message);
      this.name = "ApiError";
      this.status = status || 0;
      this.kind = kind || "http";
    }
    // Typical of a sleeping server (free Render instance waking up): worth retrying.
    get retryable() {
      return this.kind !== "http" || [502, 503, 504].includes(this.status);
    }
  }

  async function request(method, path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT);
    const opts = { method, signal: controller.signal, headers: { Accept: "application/json" } };

    if (body instanceof FormData) {
      opts.body = body; // browser sets multipart boundary
    } else if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(BASE + path, opts);
    } catch (e) {
      if (e.name === "AbortError") {
        throw new ApiError(msg("err.timeout", "Le serveur ne répond pas (délai de 8 secondes dépassé). Réessayez plus tard."), 0, "timeout");
      }
      throw new ApiError(msg("err.network", "Impossible de joindre le serveur. Vérifiez votre connexion internet."), 0, "network");
    } finally {
      clearTimeout(timer);
    }

    const isJson = (res.headers.get("content-type") || "").includes("application/json");
    const data = isJson ? await res.json().catch(() => null) : await res.text().catch(() => "");

    if (!res.ok) {
      let detail = data && data.detail;
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join(" · ");
      const base =
        res.status === 429 ? msg("err.too_many", "Trop de requêtes. Patientez un instant.")
        : res.status >= 500 ? msg("err.server", "Erreur du serveur. Réessayez plus tard.")
        : msg("err.request", "La requête a échoué.");
      throw new ApiError(detail ? `${base} (${detail})` : `${base} [${res.status}]`, res.status);
    }
    return data;
  }

  window.api = {
    get: (path) => request("GET", path),
    post: (path, body) => request("POST", path, body),
    ApiError,
  };
})();

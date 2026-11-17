// Global front-end configuration.
// Local (localhost, 127.0.0.1, file://, LAN IP) → API on port 8000 of the same machine.
// Anywhere else (Vercel) → API on Render.
// index.html repeats this rule inline for its GET /points preload: keep both in sync.
(function () {
  const PROD_API = "https://mawjoud-api.onrender.com"; // URL du service Render (Dashboard → mawjoud-api)

  const host = location.hostname;
  const isLocal =
    location.protocol === "file:" ||
    host === "" ||
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "[::1]" ||
    host.endsWith(".localhost") ||
    /^(10|192\.168|172\.(1[6-9]|2\d|3[01]))\./.test(host); // phone testing on the LAN

  window.MAWJOUD_CONFIG = {
    API_BASE: isLocal ? `http://${host || "localhost"}:8000` : PROD_API,
    TIMEOUT_MS: 8000,
    DEFAULT_LANG: "fr",
    LANGS: ["fr", "ar"],
  };
})();

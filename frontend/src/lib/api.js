import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true, headers: { "X-Requested-With": "XMLHttpRequest" } });

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const cfg = error.config;
    if (error.response?.status === 401 && !cfg._retry && !cfg.url.includes("/auth/")) {
      cfg._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(cfg);
      } catch (e) {
        refreshing = null;
        window.dispatchEvent(new Event("auth:logout"));
      }
    }
    return Promise.reject(error);
  }
);

export function formatApiError(e) {
  const detail = e?.response?.data?.detail;
  if (detail == null) return e?.message || "Si è verificato un errore. Riprova.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg || JSON.stringify(d)).join(" ");
  return detail.msg || String(detail);
}

export const fmtEUR = (n, cur = "EUR") =>
  new Intl.NumberFormat("it-IT", { style: "currency", currency: cur || "EUR" }).format(n || 0);

export const fmtDate = (s) => (s ? s.split("-").reverse().join("/") : "");

export async function downloadFile(url, params, fallbackName) {
  const res = await api.get(url, { params, responseType: "blob" });
  const cd = res.headers["content-disposition"] || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(res.data);
  link.download = m ? m[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";

export const PlafondAlert = () => {
  const [s, setS] = useState(null);
  useEffect(() => {
    api.get("/dichiarazioni/riepilogo").then((r) => setS(r.data)).catch(() => setS(null));
  }, []);
  if (!s || !(s.attenzione || s.superate || s.anomalie)) return null;
  const parts = [
    s.superate && `${s.superate} plafond superati`,
    s.attenzione && `${s.attenzione} dichiarazioni oltre l'80%`,
    s.anomalie && `${s.anomalie} fatture irregolari`,
  ].filter(Boolean);
  return (
    <Link to="/dichiarazioni" data-testid="plafond-alert"
      className="fade-up mb-6 flex items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 transition-colors hover:bg-amber-100">
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <span><span className="font-semibold">Dichiarazioni d'intento:</span> {parts.join(" · ")}</span>
    </Link>
  );
};

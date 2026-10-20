import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const CompanyContext = createContext(null);
const KEY = "activeCompanyVat";

const applyHeader = (vat) => {
  if (vat) api.defaults.headers.common["X-Company-Vat"] = vat;
  else delete api.defaults.headers.common["X-Company-Vat"];
};

export const CompanyProvider = ({ children }) => {
  const { user } = useAuth();
  const [companies, setCompanies] = useState(null);
  const [active, setActiveState] = useState("");

  const storageKey = `${KEY}:${user?.id}`;
  const setActive = (vat) => {
    applyHeader(vat);
    localStorage.setItem(storageKey, vat);
    setActiveState(vat);
  };

  const reload = useCallback(async () => {
    applyHeader("");
    const { data } = await api.get("/companies");
    const saved = localStorage.getItem(`${KEY}:${user?.id}`);
    const pick = data.find((c) => c.company_vat === saved)
      || data.find((c) => (user?.company_vats || []).includes(c.company_vat)) || data[0];
    const vat = pick?.company_vat || "";
    applyHeader(vat);
    setActiveState(vat);
    setCompanies(data);
  }, [user]);

  useEffect(() => {
    reload().catch(() => setCompanies([]));
  }, [reload]);

  const current = (companies || []).find((c) => c.company_vat === active);
  return (
    <CompanyContext.Provider value={{ companies, active, current, setActive, reload }}>
      {children}
    </CompanyContext.Provider>
  );
};

export const useCompany = () => useContext(CompanyContext);

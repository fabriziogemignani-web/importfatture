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

  const setActive = (vat) => {
    applyHeader(vat);
    localStorage.setItem(KEY, vat);
    setActiveState(vat);
  };

  const reload = useCallback(async () => {
    const { data } = await api.get("/companies");
    const isAdmin = user?.role === "admin";
    const saved = localStorage.getItem(KEY);
    const pick = isAdmin
      ? (data.find((c) => c.company_vat === saved) || data.find((c) => c.company_vat === user.company_vat) || data[0])
      : data[0];
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

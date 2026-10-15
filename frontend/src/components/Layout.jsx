import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LayoutGrid, ArrowUpRight, ArrowDownLeft, Users, UploadCloud, Settings, LogOut, Menu, X, FileText } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutGrid, id: "dashboard" },
  { to: "/attive", label: "Fatture Attive", icon: ArrowUpRight, id: "attive" },
  { to: "/passive", label: "Fatture Passive", icon: ArrowDownLeft, id: "passive" },
  { to: "/anagrafiche", label: "Anagrafiche", icon: Users, id: "anagrafiche" },
  { to: "/carica", label: "Caricamento", icon: UploadCloud, id: "carica" },
  { to: "/impostazioni", label: "Impostazioni", icon: Settings, id: "impostazioni" },
];

const Sidebar = ({ onNavigate, vat }) => {
  const { user, logout } = useAuth();
  return (
    <div className="flex h-full flex-col p-4">
      <div className="flex items-center gap-2 px-2 py-3">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-slate-900 text-white"><FileText size={18} /></div>
        <div>
          <div className="text-sm font-extrabold tracking-tight">Archivio Fatture</div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500" data-testid="sidebar-company-vat">
            {vat ? `P.IVA ${vat}` : "P.IVA non impostata"}
          </div>
        </div>
      </div>
      <nav className="mt-6 flex flex-1 flex-col gap-1">
        {NAV.map(({ to, label, icon: Icon, id }) => (
          <NavLink key={to} to={to} end={to === "/"} onClick={onNavigate} data-testid={`nav-${id}`}
            className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${isActive ? "bg-slate-900 text-white font-medium shadow-sm" : "text-slate-600 hover:bg-slate-100"}`}>
            <Icon size={17} /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-200 pt-4">
        <div className="truncate px-2 text-xs text-slate-500" data-testid="sidebar-user-email">{user?.email}</div>
        <button onClick={logout} data-testid="logout-button"
          className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 transition-colors hover:bg-red-50 hover:text-red-700">
          <LogOut size={16} /> Esci
        </button>
      </div>
    </div>
  );
};

export const Layout = () => {
  const [open, setOpen] = useState(false);
  const [vat, setVat] = useState("");
  const loc = useLocation();
  useEffect(() => {
    api.get("/settings").then((r) => setVat(r.data.company_vat)).catch(() => {});
  }, [loc.pathname]);
  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white lg:block"><Sidebar vat={vat} /></aside>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur-md lg:hidden">
        <span className="text-sm font-extrabold">Archivio Fatture</span>
        <button onClick={() => setOpen(true)} data-testid="mobile-menu-button"><Menu size={22} /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64 bg-white">
            <button className="absolute right-3 top-4" onClick={() => setOpen(false)} data-testid="mobile-menu-close"><X size={20} /></button>
            <Sidebar vat={vat} onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
      <main className="lg:pl-64">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8"><Outlet /></div>
      </main>
    </div>
  );
};

import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Layout } from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Invoices from "@/pages/Invoices";
import InvoiceDetail from "@/pages/InvoiceDetail";
import Anagrafiche from "@/pages/Anagrafiche";
import AnagraficaDetail from "@/pages/AnagraficaDetail";
import Upload from "@/pages/Upload";
import ExportCommercialista from "@/pages/ExportCommercialista";
import Settings from "@/pages/Settings";
import Users from "@/pages/Users";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";

const Protected = ({ children }) => {
  const { user } = useAuth();
  if (user === null) {
    return <div className="min-h-screen grid place-items-center text-slate-500" data-testid="auth-loading">Caricamento…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

const AdminOnly = ({ children }) => {
  const { user } = useAuth();
  return user?.role === "admin" ? children : <Navigate to="/" replace />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/password-dimenticata" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/attive" element={<Invoices tipo="attiva" />} />
            <Route path="/passive" element={<Invoices tipo="passiva" />} />
            <Route path="/fatture/:id" element={<InvoiceDetail />} />
            <Route path="/anagrafiche" element={<Anagrafiche />} />
            <Route path="/anagrafiche/:id" element={<AnagraficaDetail />} />
            <Route path="/carica" element={<Upload />} />
            <Route path="/esporta" element={<ExportCommercialista />} />
            <Route path="/impostazioni" element={<Settings />} />
            <Route path="/utenti" element={<AdminOnly><Users /></AdminOnly>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="bottom-right" />
    </AuthProvider>
  );
}

export default App;

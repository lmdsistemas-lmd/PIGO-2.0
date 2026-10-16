import { Link, Navigate, useLocation } from "react-router-dom";
import { allowedPage, firstAllowedPath } from '../utils/access';
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loadingAuth, user } = useAuth();
  const {pathname}=useLocation();

  if (loadingAuth) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "18px",
          color: "#334155",
          background: "#f8fafc",
        }}
      >
        Validando acesso...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if(!allowedPage(user,pathname))return <main style={{padding:'40px'}}><h1>Acesso não permitido</h1><p>Seu perfil não permite abrir esta tela.</p><Link to={firstAllowedPath(user)}>Abrir uma tela permitida</Link></main>;
  return children;
}

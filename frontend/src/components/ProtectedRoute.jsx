import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext.jsx";
import { roleRoutes } from "../routes/roleRoutes.js";

export function ProtectedRoute({ role, children }) {
  const { session } = useAuth();
  if (!session?.token) {
    return <Navigate to="/login" replace />;
  }
  if (role && session.role !== role && !(role === "ADMIN" && session.role === "SUB_ADMIN")) {
    return <Navigate to={roleRoutes[session.role] ?? "/"} replace />;
  }
  return children;
}

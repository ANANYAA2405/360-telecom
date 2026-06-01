import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext.jsx";
import { roleRoutes } from "../routes/roleRoutes.js";

export function RoleHomePage() {
  const { session } = useAuth();
  if (!session?.token) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={roleRoutes[session.role] ?? "/"} replace />;
}

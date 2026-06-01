import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "../components/AppShell.jsx";
import { ProtectedRoute } from "../components/ProtectedRoute.jsx";
import { AdminDashboard } from "../pages/AdminDashboard.jsx";
import { CompanyDashboard } from "../pages/CompanyDashboard.jsx";
import { CustomerDashboard } from "../pages/CustomerDashboard.jsx";
import { LandingPage } from "../pages/LandingPage.jsx";
import { LoginPage } from "../pages/LoginPage.jsx";
import { RegisterPage } from "../pages/RegisterPage.jsx";
import { RoleHomePage } from "../pages/RoleHomePage.jsx";
import { SellerDashboard } from "../pages/SellerDashboard.jsx";

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/home", element: <RoleHomePage /> },
      { path: "/customer", element: <ProtectedRoute role="CUSTOMER"><CustomerDashboard /></ProtectedRoute> },
      { path: "/seller", element: <ProtectedRoute role="SELLER"><SellerDashboard /></ProtectedRoute> },
      { path: "/company", element: <ProtectedRoute role="COMPANY"><CompanyDashboard /></ProtectedRoute> },
      { path: "/admin", element: <ProtectedRoute role="ADMIN"><AdminDashboard /></ProtectedRoute> },
      { path: "*", element: <Navigate to="/" replace /> }
    ]
  }
]);

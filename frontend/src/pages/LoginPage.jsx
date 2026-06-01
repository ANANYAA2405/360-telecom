import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { roleRoutes } from "../routes/roleRoutes.js";

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setSession } = useAuth();
  const selectedRole = (searchParams.get("role") ?? "CUSTOMER").toUpperCase();
  const [form, setForm] = useState({ email: "", password: "" });
  const [otp, setOtp] = useState("");
  const [otpRequested, setOtpRequested] = useState(false);
  const [devOtp, setDevOtp] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setSession(null);
  }, [selectedRole]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      if (!otpRequested) {
        const result = await apiRequest("/auth/login/request-otp", {
          method: "POST",
          body: JSON.stringify(form)
        });
        if (result.role !== selectedRole && !(selectedRole === "ADMIN" && result.role === "SUB_ADMIN")) {
          setError(`This is the ${selectedRole} portal. Use the ${result.role} portal for this account.`);
          return;
        }
        setOtpRequested(true);
        setDevOtp(result.dev_otp);
        return;
      }
      const result = await apiRequest("/auth/login/verify-otp", {
        method: "POST",
        body: JSON.stringify({ ...form, otp_code: otp })
      });
      if (result.role !== selectedRole && !(selectedRole === "ADMIN" && result.role === "SUB_ADMIN")) {
        setError(`This is the ${selectedRole} portal. Use the ${result.role} portal for this account.`);
        return;
      }
      setSession({ token: result.access_token, role: result.role });
      navigate(roleRoutes[result.role] ?? "/");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="max-w-md">
      <h1 className="text-2xl font-semibold">{selectedRole} Login</h1>
      <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
        <label className="grid gap-2 text-sm">
          Email
          <input
            className="rounded border border-slate-300 px-3 py-2"
            type="email"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            required
          />
        </label>
        <label className="grid gap-2 text-sm">
        Password
          <input
            className="rounded border border-slate-300 px-3 py-2"
            type="password"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            required
          />
        </label>
        {otpRequested ? (
          <label className="grid gap-2 text-sm">
            OTP
            <input
              className="rounded border border-slate-300 px-3 py-2"
              value={otp}
              onChange={(event) => setOtp(event.target.value)}
              required
            />
            <span className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">Dev OTP: {devOtp}</span>
          </label>
        ) : null}
        {error ? <p className="text-sm text-alert">{error}</p> : null}
        <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">
          {otpRequested ? "Verify OTP and sign in" : "Send OTP"}
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        Need an account? <Link className="text-signal" to={`/register?role=${selectedRole}`}>Register for this portal</Link>
      </p>
    </section>
  );
}

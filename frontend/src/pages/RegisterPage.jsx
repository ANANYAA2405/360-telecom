import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { roleRoutes } from "../routes/roleRoutes.js";

export function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setSession } = useAuth();
  const selectedRole = (searchParams.get("role") ?? "CUSTOMER").toUpperCase();
  const [companies, setCompanies] = useState([]);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: selectedRole, company_id: "" });
  const [error, setError] = useState("");

  useEffect(() => {
    setSession(null);
    setForm((current) => ({ ...current, role: selectedRole, company_id: "" }));
    if (selectedRole !== "CUSTOMER") {
      apiRequest("/companies").then(setCompanies).catch(() => setCompanies([]));
    }
  }, [selectedRole]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      const result = await apiRequest("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          company_id: form.company_id ? Number(form.company_id) : null
        })
      });
      setSession({ token: result.access_token, role: result.role });
      navigate(roleRoutes[result.role] ?? "/home");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="max-w-md">
      <h1 className="text-2xl font-semibold">{selectedRole} Register</h1>
      <p className="mt-2 text-sm text-slate-600">Create an account for the selected Telecom360 portal.</p>
      <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
        {selectedRole !== "CUSTOMER" ? (
          <label className="grid gap-2 text-sm">
            Company
            <select
              className="rounded border border-slate-300 px-3 py-2"
              value={form.company_id}
              onChange={(event) => setForm({ ...form, company_id: event.target.value })}
              required
            >
              <option value="">Choose company</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>{company.name}</option>
              ))}
            </select>
          </label>
        ) : null}
        <label className="grid gap-2 text-sm">
          Full name
          <input
            className="rounded border border-slate-300 px-3 py-2"
            value={form.full_name}
            onChange={(event) => setForm({ ...form, full_name: event.target.value })}
            required
          />
        </label>
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
        {error ? <p className="text-sm text-alert">{error}</p> : null}
        <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">
          Create account
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        Already registered? <Link className="text-signal" to={`/login?role=${selectedRole}`}>Sign in</Link>
      </p>
    </section>
  );
}

import { useEffect, useState } from "react";

import { apiRequest } from "../api/client.js";
import { MetricTile } from "../components/MetricTile.jsx";
import { TextInput } from "../components/TextInput.jsx";

export function AdminDashboard() {
  const [summary, setSummary] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [series, setSeries] = useState([]);
  const [fullDashboard, setFullDashboard] = useState(null);
  const [companyForm, setCompanyForm] = useState({ name: "", code: "" });
  const [subAdminForm, setSubAdminForm] = useState({ full_name: "", email: "", password: "Password@12345" });
  const [sellerForm, setSellerForm] = useState({ full_name: "", email: "", password: "Password@12345", company_id: "" });
  const [inventoryForm, setInventoryForm] = useState({ company_id: "", start_msisdn: "", count: 1000 });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function loadData() {
    const [summaryData, companyData, seriesData, dashboardData] = await Promise.all([
      apiRequest("/management/summary"),
      apiRequest("/companies"),
      apiRequest("/management/series"),
      apiRequest("/dashboard/admin")
    ]);
    setSummary(summaryData);
    setCompanies(companyData);
    setSeries(seriesData);
    setFullDashboard(dashboardData);
  }

  useEffect(() => {
    loadData().catch((err) => setError(err.message));
  }, []);

  async function submitCompany(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    await apiRequest("/companies", { method: "POST", body: JSON.stringify(companyForm) });
    setCompanyForm({ name: "", code: "" });
    setNotice("Company created");
    await loadData();
  }

  async function submitSeller(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    await apiRequest("/management/sellers", {
      method: "POST",
      body: JSON.stringify({ ...sellerForm, company_id: Number(sellerForm.company_id) })
    });
    setSellerForm({ full_name: "", email: "", password: "Password@12345", company_id: sellerForm.company_id });
    setNotice("Seller created");
    await loadData();
  }

  async function submitInventory(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    const result = await apiRequest("/management/inventory/generate", {
      method: "POST",
      body: JSON.stringify({
        company_id: Number(inventoryForm.company_id),
        start_msisdn: inventoryForm.start_msisdn,
        count: Number(inventoryForm.count)
      })
    });
    setNotice(`Generated ${result.created} SIMs from ${result.start_msisdn} to ${result.end_msisdn}`);
    setInventoryForm({ ...inventoryForm, start_msisdn: "" });
    await loadData();
  }

  async function submitSubAdmin(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    await apiRequest("/admin/sub-admins", { method: "POST", body: JSON.stringify(subAdminForm) });
    setSubAdminForm({ full_name: "", email: "", password: "Password@12345" });
    setNotice("Sub-admin created");
    await loadData();
  }

  return (
    <section className="grid gap-6">
      <h1 className="text-2xl font-semibold">Admin Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-4">
        <MetricTile label="Companies" value={summary?.companies ?? 0} />
        <MetricTile label="Sellers" value={summary?.sellers ?? 0} />
        <MetricTile label="Customers" value={fullDashboard?.all_customers?.length ?? 0} />
        <MetricTile label="SIM inventory" value={fullDashboard?.all_sim_inventory?.length ?? summary?.sim_records ?? 0} />
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        <MetricTile label="Revenue" value={`Rs. ${fullDashboard?.metrics?.total_revenue ?? 0}`} />
        <MetricTile label="Top Company" value={fullDashboard?.metrics?.top_company?.company_name ?? "None"} />
        <MetricTile label="Top Seller" value={fullDashboard?.metrics?.top_seller?.seller_name ?? "None"} />
        <MetricTile label="Segments" value={Object.keys(fullDashboard?.metrics?.customer_segment_counts ?? {}).length} />
      </div>
      {notice ? <p className="rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p> : null}
      {error ? <p className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-alert">{error}</p> : null}
      <div className="grid gap-6 lg:grid-cols-3">
        <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitCompany}>
          <h2 className="font-semibold">Create Company</h2>
          <TextInput label="Company name" value={companyForm.name} onChange={(value) => setCompanyForm({ ...companyForm, name: value })} />
          <TextInput label="Code" value={companyForm.code} onChange={(value) => setCompanyForm({ ...companyForm, code: value.toUpperCase() })} />
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Create</button>
        </form>
        <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitSeller}>
          <h2 className="font-semibold">Create Seller</h2>
          <label className="grid gap-2 text-sm">
            Company
            <select className="rounded border border-slate-300 px-3 py-2" value={sellerForm.company_id} onChange={(event) => setSellerForm({ ...sellerForm, company_id: event.target.value })} required>
              <option value="">Choose company</option>
              {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
            </select>
          </label>
          <TextInput label="Seller name" value={sellerForm.full_name} onChange={(value) => setSellerForm({ ...sellerForm, full_name: value })} />
          <TextInput label="Email" type="email" value={sellerForm.email} onChange={(value) => setSellerForm({ ...sellerForm, email: value })} />
          <TextInput label="Password" type="password" value={sellerForm.password} onChange={(value) => setSellerForm({ ...sellerForm, password: value })} />
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Create</button>
        </form>
        <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitInventory}>
          <h2 className="font-semibold">Generate SIMs</h2>
          <label className="grid gap-2 text-sm">
            Company
            <select className="rounded border border-slate-300 px-3 py-2" value={inventoryForm.company_id} onChange={(event) => setInventoryForm({ ...inventoryForm, company_id: event.target.value })} required>
              <option value="">Choose company</option>
              {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
            </select>
          </label>
          <TextInput label="Start MSISDN" value={inventoryForm.start_msisdn} onChange={(value) => setInventoryForm({ ...inventoryForm, start_msisdn: value })} />
          <TextInput label="Count" type="number" min="1" max="1000" value={inventoryForm.count} onChange={(value) => setInventoryForm({ ...inventoryForm, count: value })} />
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Generate</button>
        </form>
        <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitSubAdmin}>
          <h2 className="font-semibold">Create Sub-Admin</h2>
          <TextInput label="Full name" value={subAdminForm.full_name} onChange={(value) => setSubAdminForm({ ...subAdminForm, full_name: value })} />
          <TextInput label="Email" type="email" value={subAdminForm.email} onChange={(value) => setSubAdminForm({ ...subAdminForm, email: value })} />
          <TextInput label="Password" type="password" value={subAdminForm.password} onChange={(value) => setSubAdminForm({ ...subAdminForm, password: value })} />
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Create</button>
        </form>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Company Rankings</div>
          {(fullDashboard?.metrics?.company_rankings ?? []).slice(0, 5).map((item) => <div key={item.company_id} className="flex justify-between border-b border-slate-100 px-4 py-3 text-sm"><span>{item.company_name}</span><span>{item.active_sims} active</span></div>)}
        </div>
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Customer Tiers</div>
          {Object.entries(fullDashboard?.metrics?.profile_tier_counts ?? {}).map(([tier, count]) => <div key={tier} className="flex justify-between border-b border-slate-100 px-4 py-3 text-sm"><span>{tier}</span><span>{count}</span></div>)}
        </div>
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Seller Profiles</div>
          {(fullDashboard?.metrics?.seller_profiles ?? []).slice(0, 5).map((item) => <div key={item.seller_id} className="border-b border-slate-100 px-4 py-3 text-sm">{item.seller_name}: {item.profile} ({item.score})</div>)}
        </div>
      </div>
      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="grid grid-cols-4 border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">
          <span>Company</span>
          <span>Prefix</span>
          <span>Start</span>
          <span>End</span>
        </div>
        {series.slice(0, 8).map((item) => (
          <div key={item.id} className="grid grid-cols-4 border-b border-slate-100 px-4 py-3 text-sm">
            <span>{companies.find((company) => company.id === item.company_id)?.name ?? item.company_id}</span>
            <span>{item.prefix}</span>
            <span>{item.start_number}</span>
            <span>{item.end_number}</span>
          </div>
        ))}
        {series.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No number series loaded.</div> : null}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">All Sellers</div>
          {(fullDashboard?.all_sellers ?? []).slice(0, 10).map((item) => <div key={item.id} className="border-b border-slate-100 px-4 py-3 text-sm">{item.full_name} - {item.company_name}</div>)}
        </div>
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">All Customers</div>
          {(fullDashboard?.sorted_customers ?? fullDashboard?.all_customers ?? []).slice(0, 10).map((item) => <div key={item.id} className="border-b border-slate-100 px-4 py-3 text-sm">{item.full_name} - {item.email} - {item.profile?.tier}/{item.profile?.segment}</div>)}
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Activation Logs</div>
          {(fullDashboard?.all_activation_logs ?? []).slice(0, 10).map((item) => <div key={item.id} className="border-b border-slate-100 px-4 py-3 text-sm">#{item.id} {item.msisdn}: {item.status}</div>)}
        </div>
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Audit Logs</div>
          {(fullDashboard?.audit_logs ?? []).slice(0, 10).map((item) => <div key={item.id} className="border-b border-slate-100 px-4 py-3 text-sm">{item.action} {item.entity_type} #{item.entity_id}</div>)}
        </div>
      </div>
    </section>
  );
}

import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { apiRequest } from "../api/client.js";
import { MetricTile } from "../components/MetricTile.jsx";
import { TextInput } from "../components/TextInput.jsx";

const data = [
  { day: "Mon", activations: 18 },
  { day: "Tue", activations: 32 },
  { day: "Wed", activations: 27 },
  { day: "Thu", activations: 44 },
  { day: "Fri", activations: 39 }
];

const accessMatrix = [
  ["COMPANY_ADMIN", "Full company access: plans, sellers, inventory, analytics, targets, support inbox"],
  ["PLAN_MANAGER", "Create, edit, and retire plans. View plans and analytics."],
  ["INVENTORY_MANAGER", "Generate SIM inventory and view number series/SIM stock."],
  ["SELLER_MANAGER", "Create company staff and sellers. Set seller targets."],
  ["ANALYST", "View company intelligence, profiles, rankings, failures, and reports."],
  ["SUPPORT_MANAGER", "Handle failed activations, complaints, and replacement workflows."]
];

const companyRoles = ["COMPANY_ADMIN", "PLAN_MANAGER", "INVENTORY_MANAGER", "SELLER_MANAGER", "ANALYST", "SUPPORT_MANAGER"];

export function CompanyDashboard() {
  const [summary, setSummary] = useState(null);
  const [series, setSeries] = useState([]);
  const [plans, setPlans] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [companyUsers, setCompanyUsers] = useState([]);
  const [targets, setTargets] = useState([]);
  const [activationInbox, setActivationInbox] = useState([]);
  const [fullDashboard, setFullDashboard] = useState(null);
  const [sellerForm, setSellerForm] = useState({ full_name: "", email: "", password: "Password@12345" });
  const [companyUserForm, setCompanyUserForm] = useState({ full_name: "", email: "", password: "Password@12345", company_role: "ANALYST" });
  const [planForm, setPlanForm] = useState({ name: "", description: "", monthly_price: "299.00", data_gb: 28, voice_minutes: 1000, sms_count: 100, validity_days: 28 });
  const [targetForm, setTargetForm] = useState({ seller_id: "", month: new Date().toISOString().slice(0, 7), activation_target: 10, recharge_target: 20, kyc_target: 10 });
  const [inventoryForm, setInventoryForm] = useState({ start_msisdn: "", count: 1000 });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function loadData() {
    const safe = async (request, fallback) => request.catch(() => fallback);
    const dashboardData = await safe(apiRequest("/dashboard/company"), null);
    const allowed = dashboardData?.permissions ?? {};
    const [summaryData, seriesData, planData, sellerData, companyUserData, targetData] = await Promise.all([
      safe(apiRequest("/management/summary"), null),
      allowed.can_manage_inventory || allowed.can_view_analytics ? safe(apiRequest("/management/series"), []) : [],
      allowed.can_manage_plans || allowed.can_view_analytics ? safe(apiRequest("/management/plans"), []) : [],
      allowed.can_manage_sellers || allowed.can_view_seller_profiles ? safe(apiRequest("/management/sellers"), []) : [],
      allowed.can_manage_sellers ? safe(apiRequest("/management/company-users"), []) : [],
      allowed.can_manage_sellers || allowed.can_view_seller_profiles ? safe(apiRequest("/usage/targets"), []) : []
    ]);
    setSummary(summaryData);
    setSeries(seriesData);
    setPlans(planData);
    setSellers(sellerData);
    setCompanyUsers(companyUserData);
    setTargets(targetData);
    setFullDashboard(dashboardData);
    if (allowed.can_handle_support || allowed.can_view_analytics) {
      apiRequest("/activation/manual-inbox").then(setActivationInbox).catch(() => setActivationInbox([]));
    } else {
      setActivationInbox([]);
    }
  }

  useEffect(() => {
    loadData().catch((err) => setError(err.message));
  }, []);

  async function submitSeller(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    await apiRequest("/management/sellers", { method: "POST", body: JSON.stringify(sellerForm) });
    setSellerForm({ full_name: "", email: "", password: "Password@12345" });
    setNotice("Seller created");
    await loadData();
  }

  async function submitCompanyUser(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    await apiRequest("/management/company-users", { method: "POST", body: JSON.stringify(companyUserForm) });
    setCompanyUserForm({ full_name: "", email: "", password: "Password@12345", company_role: "ANALYST" });
    setNotice("Company staff login created");
    await loadData();
  }

  async function submitPlan(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    await apiRequest("/management/plans", { method: "POST", body: JSON.stringify(planForm) });
    setPlanForm({ name: "", description: "", monthly_price: "299.00", data_gb: 28, voice_minutes: 1000, sms_count: 100, validity_days: 28 });
    setNotice("Plan created");
    await loadData();
  }

  async function editPlan(plan) {
    const monthly_price = window.prompt("Monthly price", plan.monthly_price);
    if (!monthly_price) return;
    await apiRequest(`/management/plans/${plan.id}`, { method: "PATCH", body: JSON.stringify({ monthly_price }) });
    setNotice("Plan updated");
    await loadData();
  }

  async function deactivatePlan(plan) {
    await apiRequest(`/management/plans/${plan.id}`, { method: "DELETE" });
    setNotice("Plan deactivated");
    await loadData();
  }

  async function submitTarget(event) {
    event.preventDefault();
    await apiRequest("/usage/targets", {
      method: "POST",
      body: JSON.stringify({
        ...targetForm,
        seller_id: Number(targetForm.seller_id),
        activation_target: Number(targetForm.activation_target),
        recharge_target: Number(targetForm.recharge_target),
        kyc_target: Number(targetForm.kyc_target)
      })
    });
    setNotice("Seller target saved");
    await loadData();
  }

  async function submitInventory(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    const result = await apiRequest("/management/inventory/generate", {
      method: "POST",
      body: JSON.stringify({
        start_msisdn: inventoryForm.start_msisdn,
        count: Number(inventoryForm.count)
      })
    });
    setNotice(`Generated ${result.created} SIMs from ${result.start_msisdn} to ${result.end_msisdn}`);
    setInventoryForm({ ...inventoryForm, start_msisdn: "" });
    await loadData();
  }

  async function resumeActivation(item) {
    setError("");
    setNotice("");
    try {
      const result = await apiRequest(`/activation/${item.id}/resume`, { method: "POST" });
      setNotice(`Activation resubmitted from ${result.resumed_from || item.failed_node}: ${result.status}`);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function updateComplaint(item, status) {
    setError("");
    setNotice("");
    try {
      await apiRequest(`/lifecycle/complaints/${item.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status })
      });
      setNotice(`Complaint ${status}`);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function verifyReplacement(item, approved = true) {
    setError("");
    setNotice("");
    try {
      const result = await apiRequest(`/lifecycle/replacements/${item.id}/verify`, {
        method: "POST",
        body: JSON.stringify({ approved })
      });
      setNotice(`Replacement ${result.status}`);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  const permissions = fullDashboard?.permissions ?? {};
  const companyRole = fullDashboard?.company_role ?? "COMPANY_ADMIN";
  const sellerProfiles = fullDashboard?.seller_profiles ?? [];
  const customerTierCounts = fullDashboard?.customer_tier_counts ?? {};
  const customerSegments = fullDashboard?.customer_segment_counts ?? {};
  const nodeFailures = fullDashboard?.node_wise_failure_analytics ?? {};
  const totalProfiledCustomers = Object.values(customerTierCounts).reduce((sum, value) => sum + Number(value || 0), 0);
  const activeSims = Number(fullDashboard?.active_sims ?? 0);
  const failedActivationCount = fullDashboard?.failed_activations?.length ?? 0;
  const operationsScore = Math.max(0, Math.min(100, 82 + Math.min(activeSims, 20) - failedActivationCount * 8 - Object.keys(nodeFailures).length * 4));
  const bestSellerProfile = fullDashboard?.best_seller;
  const dominantTier = Object.entries(customerTierCounts).sort((a, b) => Number(b[1]) - Number(a[1]))[0]?.[0] ?? "SILVER";
  const companyRisk = failedActivationCount > 3 ? "HIGH" : Object.keys(nodeFailures).length ? "MEDIUM" : "LOW";
  const showPlans = permissions.can_manage_plans || permissions.can_view_analytics;
  const showInventory = permissions.can_manage_inventory || permissions.can_view_analytics;
  const showSellerOps = permissions.can_manage_sellers || permissions.can_view_seller_profiles;
  const showSupport = permissions.can_handle_support || permissions.can_view_analytics;
  const showCustomerProfiles = permissions.can_view_customer_profiles;

  return (
    <section className="grid gap-6">
      <h1 className="text-2xl font-semibold">Company Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-4">
        <MetricTile label="Total SIMs issued" value={fullDashboard?.total_sims_issued ?? 0} />
        <MetricTile label="Available SIMs" value={fullDashboard?.available_sims ?? summary?.available_sims ?? 0} />
        <MetricTile label="Sellers" value={summary?.sellers ?? 0} />
        <MetricTile label="Failed activations" value={activationInbox.length} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricTile label="Reserved SIMs" value={fullDashboard?.reserved_sims ?? 0} />
        <MetricTile label="Active SIMs" value={fullDashboard?.active_sims ?? 0} />
        <MetricTile label="Replacements" value={fullDashboard?.replacements?.length ?? 0} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricTile label="Best Seller" value={fullDashboard?.best_seller?.seller_name ?? "None"} />
        <MetricTile label="Retail Customers" value={fullDashboard?.customer_segment_counts?.RETAIL ?? 0} />
        <MetricTile label="Enterprise Customers" value={fullDashboard?.customer_segment_counts?.ENTERPRISE ?? 0} />
      </div>
      <div className="rounded border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-900">
        Logged in as <strong>{companyRole}</strong>. Your enabled access: {Object.entries(permissions).filter(([, enabled]) => enabled).map(([key]) => key.replace("can_", "").replaceAll("_", " ")).join(", ") || "view only"}.
      </div>
      <div className="overflow-hidden rounded border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
          <h2 className="font-semibold">Company Profiling & Intelligence</h2>
          <p className="text-sm text-slate-500">Company score, customer profiling, seller profiling, and rule-based prediction signals.</p>
        </div>
        <div className="grid gap-3 p-4 md:grid-cols-4">
          <MetricTile label="Operations Score" value={`${operationsScore}/100`} />
          <MetricTile label="Risk Level" value={companyRisk} />
          <MetricTile label="Dominant Customer Tier" value={dominantTier} />
          <MetricTile label="Profiled Customers" value={totalProfiledCustomers} />
        </div>
        <div className="grid gap-4 border-t border-slate-100 p-4 lg:grid-cols-3">
          <div className="rounded border border-slate-200 p-3">
            <div className="text-sm font-semibold">Customer Profiling</div>
            {showCustomerProfiles ? (
              <div className="mt-3 grid gap-2 text-sm">
                <div className="flex justify-between"><span>Retail</span><strong>{customerSegments.RETAIL ?? 0}</strong></div>
                <div className="flex justify-between"><span>Enterprise</span><strong>{customerSegments.ENTERPRISE ?? 0}</strong></div>
                {Object.entries(customerTierCounts).map(([tier, count]) => (
                  <div key={tier} className="flex justify-between"><span>{tier}</span><strong>{count}</strong></div>
                ))}
              </div>
            ) : <p className="mt-3 text-sm text-slate-500">Restricted to Company Admin and Analyst roles.</p>}
          </div>
          <div className="rounded border border-slate-200 p-3">
            <div className="text-sm font-semibold">Seller Profiling</div>
            {showSellerOps ? (
              <div className="mt-3 grid gap-2 text-sm">
                <div>Best seller: <strong>{bestSellerProfile?.seller_name ?? "None"}</strong></div>
                <div>Profile: <strong>{bestSellerProfile?.profile ?? "Not enough data"}</strong></div>
                <div>Forecast: <strong>{bestSellerProfile?.prediction ?? "Pending activity"}</strong></div>
                <div>Total sellers profiled: <strong>{sellerProfiles.length}</strong></div>
              </div>
            ) : <p className="mt-3 text-sm text-slate-500">Restricted to Company Admin, Seller Manager, and Analyst roles.</p>}
          </div>
          <div className="rounded border border-slate-200 p-3">
            <div className="text-sm font-semibold">AI-like Prediction Signals</div>
            <div className="mt-3 grid gap-2 text-sm">
              <div>Node failure risk: <strong>{companyRisk}</strong></div>
              <div>Failure nodes watched: <strong>{Object.keys(nodeFailures).length}</strong></div>
              <div>Growth forecast: <strong>{operationsScore >= 90 ? "Strong activation momentum" : operationsScore >= 70 ? "Stable with follow-up needed" : "Needs intervention"}</strong></div>
              <div>Recommendation: <strong>{failedActivationCount ? "Review failed activation inbox" : "Push high-value plan conversion"}</strong></div>
            </div>
          </div>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Quick Profiling Snapshot</div>
          <div className="grid gap-3 p-4 text-sm md:grid-cols-2">
            <div className="rounded bg-slate-50 p-3">Best seller: <strong>{fullDashboard?.best_seller?.seller_name ?? "None"}</strong></div>
            <div className="rounded bg-slate-50 p-3">Enterprise mix: <strong>{fullDashboard?.customer_segment_counts?.ENTERPRISE ?? 0}</strong></div>
            <div className="rounded bg-slate-50 p-3">Retail base: <strong>{fullDashboard?.customer_segment_counts?.RETAIL ?? 0}</strong></div>
            <div className="rounded bg-slate-50 p-3">Failure nodes: <strong>{Object.keys(fullDashboard?.node_wise_failure_analytics ?? {}).length}</strong></div>
          </div>
        </div>
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Role Access Matrix</div>
          {accessMatrix.map(([role, access]) => (
            <div key={role} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-[0.5fr_1.5fr]">
              <span className="font-semibold">{role}</span><span>{access}</span>
            </div>
          ))}
        </div>
      </div>
      {notice ? <p className="rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p> : null}
      {error ? <p className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-alert">{error}</p> : null}
      <div className="grid gap-6 lg:grid-cols-4">
        {permissions.can_manage_sellers ? <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitCompanyUser}>
          <h2 className="font-semibold">Create Company Login</h2>
          <TextInput label="Staff name" value={companyUserForm.full_name} onChange={(value) => setCompanyUserForm({ ...companyUserForm, full_name: value })} />
          <TextInput label="Email" type="email" value={companyUserForm.email} onChange={(value) => setCompanyUserForm({ ...companyUserForm, email: value })} />
          <TextInput label="Password" type="password" value={companyUserForm.password} onChange={(value) => setCompanyUserForm({ ...companyUserForm, password: value })} />
          <label className="grid gap-2 text-sm">
            Company role
            <select className="rounded border border-slate-300 px-3 py-2" value={companyUserForm.company_role} onChange={(event) => setCompanyUserForm({ ...companyUserForm, company_role: event.target.value })}>
              {companyRoles.map((role) => <option key={role} value={role}>{role}</option>)}
            </select>
          </label>
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Create</button>
        </form> : null}
        {permissions.can_manage_sellers ? <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitSeller}>
          <h2 className="font-semibold">Create Seller</h2>
          <TextInput label="Seller name" value={sellerForm.full_name} onChange={(value) => setSellerForm({ ...sellerForm, full_name: value })} />
          <TextInput label="Email" type="email" value={sellerForm.email} onChange={(value) => setSellerForm({ ...sellerForm, email: value })} />
          <TextInput label="Password" type="password" value={sellerForm.password} onChange={(value) => setSellerForm({ ...sellerForm, password: value })} />
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Create</button>
        </form> : null}
        {permissions.can_manage_plans ? <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitPlan}>
          <h2 className="font-semibold">Create Plan</h2>
          <TextInput label="Plan name" value={planForm.name} onChange={(value) => setPlanForm({ ...planForm, name: value })} />
          <TextInput label="Description" value={planForm.description} onChange={(value) => setPlanForm({ ...planForm, description: value })} />
          <TextInput label="Monthly price" type="number" min="1" value={planForm.monthly_price} onChange={(value) => setPlanForm({ ...planForm, monthly_price: value })} />
          <TextInput label="Data GB" type="number" min="0" value={planForm.data_gb} onChange={(value) => setPlanForm({ ...planForm, data_gb: value })} />
          <TextInput label="Voice minutes" type="number" min="0" value={planForm.voice_minutes} onChange={(value) => setPlanForm({ ...planForm, voice_minutes: value })} />
          <TextInput label="SMS" type="number" min="0" value={planForm.sms_count} onChange={(value) => setPlanForm({ ...planForm, sms_count: value })} />
          <TextInput label="Validity days" type="number" min="1" value={planForm.validity_days} onChange={(value) => setPlanForm({ ...planForm, validity_days: value })} />
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Create</button>
        </form> : null}
        {permissions.can_manage_inventory ? <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitInventory}>
          <h2 className="font-semibold">Generate SIMs</h2>
          <TextInput label="Start MSISDN" value={inventoryForm.start_msisdn} onChange={(value) => setInventoryForm({ ...inventoryForm, start_msisdn: value })} />
          <TextInput label="Count" type="number" min="1" max="1000" value={inventoryForm.count} onChange={(value) => setInventoryForm({ ...inventoryForm, count: value })} />
          <button className="rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Generate</button>
        </form> : null}
      </div>
      {permissions.can_manage_sellers ? <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Company Staff Roles</div>
        {companyUsers.map((staff) => (
          <div key={staff.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-[1fr_1.2fr_0.8fr]">
            <span className="font-medium">{staff.full_name}</span>
            <span>{staff.email}</span>
            <span>{staff.company_role ?? "COMPANY_ADMIN"}</span>
          </div>
        ))}
        {companyUsers.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No company staff users yet.</div> : null}
      </div> : null}
      <div className="h-80 rounded border border-slate-200 bg-white p-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="day" />
            <YAxis />
            <Tooltip />
            <Line dataKey="activations" stroke="#0e7490" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {showPlans ? <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Published Plans</div>
        {plans.map((plan) => (
          <div key={plan.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-[1fr_2fr_0.6fr]">
            <span className="font-medium">{plan.name}</span>
            <span>{plan.description} ({plan.data_gb}GB, {plan.validity_days} days)</span>
            <span className="flex items-center gap-2">Rs. {plan.monthly_price}<button className="rounded border px-2 py-1 disabled:opacity-50" onClick={() => editPlan(plan)} disabled={!permissions.can_manage_plans}>Edit</button><button className="rounded border border-red-300 px-2 py-1 text-alert disabled:opacity-50" onClick={() => deactivatePlan(plan)} disabled={!permissions.can_manage_plans}>Delete</button></span>
          </div>
        ))}
        {plans.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No plans created yet.</div> : null}
      </div> : null}
      {permissions.can_manage_sellers ? <form className="grid gap-4 rounded border border-slate-200 bg-white p-4 md:grid-cols-5" onSubmit={submitTarget}>
        <label className="grid gap-2 text-sm">
          Seller
          <select className="rounded border border-slate-300 px-3 py-2" value={targetForm.seller_id} onChange={(event) => setTargetForm({ ...targetForm, seller_id: event.target.value })} required>
            <option value="">Choose seller</option>
            {sellers.map((seller) => <option key={seller.id} value={seller.id}>{seller.full_name}</option>)}
          </select>
        </label>
        <TextInput label="Month" type="month" value={targetForm.month} onChange={(value) => setTargetForm({ ...targetForm, month: value })} />
        <TextInput label="Activation target" type="number" min="0" value={targetForm.activation_target} onChange={(value) => setTargetForm({ ...targetForm, activation_target: value })} />
        <TextInput label="Recharge target" type="number" min="0" value={targetForm.recharge_target} onChange={(value) => setTargetForm({ ...targetForm, recharge_target: value })} />
        <button className="self-end rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Set Target</button>
      </form> : null}
      {showSellerOps ? <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Seller Targets</div>
        {targets.map((target) => (
          <div key={target.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-5">
            <span>{target.seller_name}</span><span>{target.month}</span><span>Target {target.activation_target}</span><span>Done {target.activation_achieved}</span><span>Left {target.activation_remaining}</span>
          </div>
        ))}
      </div> : null}
      {(showSellerOps || showCustomerProfiles) ? <div className="grid gap-6 lg:grid-cols-2">
        {showSellerOps ? (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Seller Profiles</div>
          {(fullDashboard?.seller_profiles ?? []).map((item) => <div key={item.seller_id} className="border-b border-slate-100 px-4 py-3 text-sm">{item.seller_name}: {item.profile} - {item.prediction}</div>)}
        </div>) : null}
        {showCustomerProfiles ? (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Customer Tier Mix</div>
          {Object.entries(fullDashboard?.customer_tier_counts ?? {}).map(([tier, count]) => <div key={tier} className="flex justify-between border-b border-slate-100 px-4 py-3 text-sm"><span>{tier}</span><span>{count}</span></div>)}
        </div>) : null}
      </div> : null}
      {showSupport ? <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_1fr_1.2fr] border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">
          <span>Customer</span>
          <span>MSISDN</span>
          <span>ICCID</span>
          <span>IMSI</span>
          <span>Failed node</span>
          <span>Failure reason</span>
          <span>Action</span>
        </div>
        {activationInbox.map((item) => (
          <div key={item.id} className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_1fr_1.2fr] items-center gap-2 border-b border-slate-100 px-4 py-3 text-sm">
            <span>{item.customer_name ?? "Unassigned"}<br /><span className="text-xs text-slate-500">{item.customer_email ?? `Attempt #${item.id}`}</span></span>
            <span>{item.msisdn}</span>
            <span className="break-all">{item.iccid}</span>
            <span className="break-all">{item.imsi}</span>
            <span>{item.failed_node}</span>
            <span>{item.failure_reason}</span>
            <span><button className="rounded bg-signal px-3 py-1 text-white" onClick={() => resumeActivation(item)}>Resubmit</button></span>
          </div>
        ))}
        {activationInbox.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No activation cases in manual review.</div> : null}
      </div> : null}
      {(showSupport || permissions.can_view_operations || permissions.can_view_analytics) ? <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Node-wise Failure Analytics</div>
          {Object.entries(fullDashboard?.node_wise_failure_analytics ?? {}).map(([node, count]) => (
            <div key={node} className="flex justify-between border-b border-slate-100 px-4 py-3 text-sm"><span>{node}</span><span>{count}</span></div>
          ))}
          {!Object.keys(fullDashboard?.node_wise_failure_analytics ?? {}).length ? <div className="px-4 py-6 text-sm text-slate-500">No node failures.</div> : null}
        </div>
        {showSellerOps ? <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Seller-wise Performance</div>
          {(fullDashboard?.seller_wise_performance ?? []).map((item) => (
            <div key={item.seller_id} className="border-b border-slate-100 px-4 py-3 text-sm">{item.seller_name}: {JSON.stringify(item.status_counts)}</div>
          ))}
          {!(fullDashboard?.seller_wise_performance ?? []).length ? <div className="px-4 py-6 text-sm text-slate-500">No seller performance data.</div> : null}
        </div> : null}
      </div> : null}
      {showSupport ? <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Complaints</div>
          {(fullDashboard?.complaints ?? []).map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 text-sm">
              <span>{item.title}: {item.status}</span>
              <span className="flex gap-2">
                <button className="rounded border border-slate-300 px-3 py-1" onClick={() => updateComplaint(item, "IN_PROGRESS")}>Progress</button>
                <button className="rounded border border-slate-300 px-3 py-1" onClick={() => updateComplaint(item, "RESOLVED")}>Resolve</button>
                <button className="rounded border border-slate-300 px-3 py-1" onClick={() => updateComplaint(item, "CLOSED")}>Close</button>
              </span>
            </div>
          ))}
          {!(fullDashboard?.complaints ?? []).length ? <div className="px-4 py-6 text-sm text-slate-500">No complaints.</div> : null}
        </div>
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Replacements</div>
          {(fullDashboard?.replacements ?? []).map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 text-sm">
              <span>{item.reason}: {item.status}</span>
              <span className="flex gap-2">
                <button className="rounded bg-signal px-3 py-1 text-white" onClick={() => verifyReplacement(item, true)}>Verify</button>
                <button className="rounded border border-red-300 px-3 py-1 text-alert" onClick={() => verifyReplacement(item, false)}>Reject</button>
              </span>
            </div>
          ))}
          {!(fullDashboard?.replacements ?? []).length ? <div className="px-4 py-6 text-sm text-slate-500">No replacements.</div> : null}
        </div>
      </div> : null}
      {showInventory ? <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="grid grid-cols-3 border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">
          <span>Prefix</span>
          <span>Start</span>
          <span>End</span>
        </div>
        {series.slice(0, 8).map((item) => (
          <div key={item.id} className="grid grid-cols-3 border-b border-slate-100 px-4 py-3 text-sm">
            <span>{item.prefix}</span>
            <span>{item.start_number}</span>
            <span>{item.end_number}</span>
          </div>
        ))}
        {series.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No number series loaded.</div> : null}
      </div> : null}
    </section>
  );
}

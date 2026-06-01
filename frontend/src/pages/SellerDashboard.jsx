import { useCallback, useEffect, useState } from "react";

import { apiRequest } from "../api/client.js";
import { MetricTile } from "../components/MetricTile.jsx";
import { useRealtimeChannel } from "../hooks/useRealtimeChannel.js";

export function SellerDashboard() {
  const [currentUser, setCurrentUser] = useState(null);
  const [items, setItems] = useState([]);
  const [activationInbox, setActivationInbox] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [plans, setPlans] = useState([]);
  const [targets, setTargets] = useState([]);
  const [preview, setPreview] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadQueue = useCallback(() => {
    apiRequest("/kyc/pending").then(setItems).catch((err) => setError(err.message));
    apiRequest("/activation/manual-inbox").then(setActivationInbox).catch(() => setActivationInbox([]));
    apiRequest("/dashboard/seller").then(setDashboard).catch(() => null);
    apiRequest("/usage/targets").then(setTargets).catch(() => setTargets([]));
  }, []);

  useEffect(() => {
    apiRequest("/auth/me").then((user) => {
      setCurrentUser(user);
      if (user.company_id) {
        apiRequest(`/companies/${user.company_id}/plans`).then(setPlans).catch(() => setPlans([]));
      }
    }).catch(() => setCurrentUser(null));
    loadQueue();
  }, [loadQueue]);

  useRealtimeChannel(
    currentUser?.company_id ? `company:${currentUser.company_id}:kyc` : null,
    useCallback(() => {
      loadQueue();
    }, [loadQueue])
  );

  useRealtimeChannel(
    currentUser?.company_id ? `company:${currentUser.company_id}:plans` : null,
    useCallback((event) => {
      if (event.type === "PLAN_CREATED") {
        setPlans((items) => [event.plan, ...items.filter((item) => item.id !== event.plan.id)]);
        setNotice(`New plan published: ${event.plan.name}`);
      }
    }, [])
  );

  async function review(item, status) {
    setError("");
    setNotice("");
    const body = { status };
    if (status === "REJECTED") body.rejection_reason = "Rejected by seller review";
    if (status === "CORRECTION_REQUESTED") body.correction_reason = "Please correct the submitted KYC details";
    try {
      await apiRequest(`/kyc/${item.id}/review`, { method: "POST", body: JSON.stringify(body) });
      setNotice(`KYC ${status}`);
      await loadQueue();
    } catch (err) {
      setError(err.message);
    }
  }

  async function resumeActivation(item) {
    setError("");
    setNotice("");
    try {
      const result = await apiRequest(`/activation/${item.id}/resume`, { method: "POST" });
      setNotice(`Activation resubmitted from ${result.resumed_from || item.failed_node}: ${result.status}`);
      await loadQueue();
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
      await loadQueue();
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
      await loadQueue();
    } catch (err) {
      setError(err.message);
    }
  }

  function openPreview(title, value) {
    if (!value || !value.startsWith("data:")) {
      setPreview({ title, value: "", message: "This KYC was submitted without a real uploaded file. Ask customer to request correction and upload again." });
      return;
    }
    setPreview({ title, value, message: "" });
  }

  return (
    <section className="grid gap-6">
      <h1 className="text-2xl font-semibold">Seller Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricTile label="KYC queue" value={items.length} />
        <MetricTile label="Failed activations" value={activationInbox.length} />
        <MetricTile label="Manual fixes" value={activationInbox.length} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricTile label="Assigned SIM stock" value={dashboard?.assigned_sim_stock?.length ?? 0} />
        <MetricTile label="Complaints assigned" value={dashboard?.complaints_assigned?.length ?? 0} />
        <MetricTile label="Replacement requests" value={dashboard?.replacement_requests?.length ?? 0} />
      </div>
      {dashboard?.profile ? (
        <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 text-sm md:grid-cols-4">
          <div><span className="text-slate-500">Seller profile</span><div className="font-semibold">{dashboard.profile.profile}</div></div>
          <div><span className="text-slate-500">Score</span><div className="font-semibold">{dashboard.profile.score}</div></div>
          <div><span className="text-slate-500">KYC reviews</span><div className="font-semibold">{dashboard.profile.kyc_reviews}</div></div>
          <div><span className="text-slate-500">Prediction</span><div className="font-semibold">{dashboard.profile.prediction}</div></div>
        </div>
      ) : null}
      {notice ? <p className="rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p> : null}
      {error ? <p className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-alert">{error}</p> : null}
      {preview ? (
        <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/40 p-4">
          <div className="max-h-[86vh] w-full max-w-3xl overflow-hidden rounded-lg bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h2 className="font-semibold">{preview.title}</h2>
              <button className="rounded border border-slate-300 px-3 py-1 text-sm" onClick={() => setPreview(null)}>Close</button>
            </div>
            <div className="max-h-[75vh] overflow-auto p-4">
              {preview.message ? <p className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{preview.message}</p> : null}
              {preview.value?.startsWith("data:image") ? <img className="mx-auto max-h-[68vh] max-w-full rounded border border-slate-200" src={preview.value} alt={preview.title} /> : null}
              {preview.value?.startsWith("data:application/pdf") ? <iframe className="h-[68vh] w-full rounded border border-slate-200" src={preview.value} title={preview.title} /> : null}
              {preview.value && !preview.value.startsWith("data:image") && !preview.value.startsWith("data:application/pdf") ? (
                <p className="text-sm text-slate-600">Unsupported preview format.</p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">My Targets</div>
        {targets.map((target) => (
          <div key={target.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-5">
            <span>{target.month}</span><span>Target {target.activation_target}</span><span>Achieved {target.activation_achieved}</span><span>Remaining {target.activation_remaining}</span><progress className="mt-1" value={target.activation_achieved} max={target.activation_target || 1} />
          </div>
        ))}
        {targets.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No target assigned yet.</div> : null}
      </div>
      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Company Plans</div>
        {plans.map((plan) => (
          <div key={plan.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-[1fr_2fr_0.6fr]">
            <span className="font-medium">{plan.name}</span>
            <span>{plan.description}</span>
            <span>Rs. {plan.monthly_price}</span>
          </div>
        ))}
        {plans.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No company plans published yet.</div> : null}
      </div>
      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Customer Usage And Risk Watchlist</div>
        {(dashboard?.customer_usage_watchlist ?? []).map((item) => (
          <div key={item.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-5">
            <span>{item.full_name}</span><span>{item.profile?.tier}</span><span>{item.profile?.segment}</span><span>{item.profile?.data_used_gb}GB used</span><span>{item.profile?.churn_risk}</span>
          </div>
        ))}
        {!(dashboard?.customer_usage_watchlist ?? []).length ? <div className="px-4 py-6 text-sm text-slate-500">No customer usage risk items.</div> : null}
      </div>
      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <div className="grid grid-cols-[1fr_1fr_1fr_1.4fr] border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">
          <span>Customer</span>
          <span>MSISDN</span>
          <span>Status</span>
          <span>Action</span>
        </div>
        {items.map((item) => (
          <div key={item.id} className="grid grid-cols-[1fr_1fr_1fr_1.4fr] items-center gap-2 border-b border-slate-100 px-4 py-3 text-sm">
            <span>{item.full_name}<br /><span className="text-xs text-slate-500">{item.customer_email}</span></span>
            <span>{item.msisdn}</span>
            <span>{item.status}</span>
            <span className="flex flex-wrap gap-2">
              <button className="rounded border border-slate-300 px-3 py-1" onClick={() => openPreview("KYC Document", item.document_upload_placeholder)} type="button">Document</button>
              <button className="rounded border border-slate-300 px-3 py-1" onClick={() => openPreview("Customer Selfie", item.selfie_placeholder)} type="button">Selfie</button>
              <button className="rounded bg-signal px-3 py-1 text-white" onClick={() => review(item, "APPROVED")}>Approve</button>
              <button className="rounded border border-slate-300 px-3 py-1" onClick={() => review(item, "CORRECTION_REQUESTED")}>Correction</button>
              <button className="rounded border border-red-300 px-3 py-1 text-alert" onClick={() => review(item, "REJECTED")}>Reject</button>
            </span>
          </div>
        ))}
        {items.length === 0 ? <div className="px-4 py-6 text-sm text-slate-500">No pending work items.</div> : null}
      </div>
      <div className="overflow-hidden rounded border border-slate-200 bg-white">
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
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Complaints Assigned</div>
          {(dashboard?.complaints_assigned ?? []).map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 text-sm">
              <span>{item.title}: {item.status}</span>
              {item.status === "CLOSED" ? (
                <span className="text-xs font-medium text-slate-500">Closed</span>
              ) : (
                <span className="flex gap-2">
                  {item.status !== "IN_PROGRESS" ? <button className="rounded border border-slate-300 px-3 py-1" onClick={() => updateComplaint(item, "IN_PROGRESS")}>Progress</button> : null}
                  {item.status !== "RESOLVED" ? <button className="rounded border border-slate-300 px-3 py-1" onClick={() => updateComplaint(item, "RESOLVED")}>Resolve</button> : null}
                  <button className="rounded border border-slate-300 px-3 py-1" onClick={() => updateComplaint(item, "CLOSED")}>Close</button>
                </span>
              )}
            </div>
          ))}
          {!(dashboard?.complaints_assigned ?? []).length ? <div className="px-4 py-6 text-sm text-slate-500">No complaints assigned.</div> : null}
        </div>
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Replacement Requests</div>
          {(dashboard?.replacement_requests ?? []).map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 text-sm">
              <span>{item.reason}: {item.status}</span>
              {["COMPLETED", "REJECTED"].includes(item.status) ? (
                <span className="text-xs font-medium text-slate-500">{item.status}</span>
              ) : (
                <span className="flex gap-2">
                  <button className="rounded bg-signal px-3 py-1 text-white" onClick={() => verifyReplacement(item, true)}>Verify</button>
                  <button className="rounded border border-red-300 px-3 py-1 text-alert" onClick={() => verifyReplacement(item, false)}>Reject</button>
                </span>
              )}
            </div>
          ))}
          {!(dashboard?.replacement_requests ?? []).length ? <div className="px-4 py-6 text-sm text-slate-500">No replacement requests.</div> : null}
        </div>
      </div>
    </section>
  );
}

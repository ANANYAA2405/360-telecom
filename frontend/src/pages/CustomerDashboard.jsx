import { useCallback, useEffect, useState } from "react";

import { apiRequest } from "../api/client.js";
import { ActivationFlow } from "../components/ActivationFlow.jsx";
import { MetricTile } from "../components/MetricTile.jsx";
import { TextInput } from "../components/TextInput.jsx";
import { useRealtimeChannel } from "../hooks/useRealtimeChannel.js";

export function CustomerDashboard() {
  const [currentUser, setCurrentUser] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [numbers, setNumbers] = useState([]);
  const [plans, setPlans] = useState([]);
  const [usage, setUsage] = useState([]);
  const [recharges, setRecharges] = useState([]);
  const [reserved, setReserved] = useState(null);
  const [kycItems, setKycItems] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [complaintForm, setComplaintForm] = useState({ title: "", description: "" });
  const [replacementReason, setReplacementReason] = useState("");
  const [kycForm, setKycForm] = useState({
    full_name: "",
    date_of_birth: "",
    address: "",
    document_type: "Aadhaar",
    document_number: "",
    document_upload_placeholder: "",
    selfie_placeholder: ""
  });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest("/auth/me").then(setCurrentUser).catch(() => setCurrentUser(null));
    apiRequest("/companies").then(setCompanies).catch(() => setCompanies([]));
    apiRequest("/kyc/mine").then(setKycItems).catch(() => setKycItems([]));
    apiRequest("/usage/mine").then(setUsage).catch(() => setUsage([]));
    apiRequest("/usage/recharges").then(setRecharges).catch(() => setRecharges([]));
    apiRequest("/dashboard/customer").then((data) => {
      setDashboard(data);
      if (data?.selected_sim && ["RESERVED", "KYC_REJECTED", "KYC_CORRECTION_REQUESTED"].includes(data.sim_status)) {
        setReserved({ ...data.selected_sim, status: data.sim_status, company_name: data.selected_operator });
      }
    }).catch(() => null);
  }, []);

  const loadNumbers = useCallback(() => {
    if (!companyId) return;
    apiRequest(`/sims/available?company_id=${companyId}`).then(setNumbers).catch(() => setNumbers([]));
    apiRequest(`/companies/${companyId}/plans`).then(setPlans).catch(() => setPlans([]));
  }, [companyId]);

  useEffect(() => {
    loadNumbers();
  }, [loadNumbers]);

  useRealtimeChannel(
    companyId ? `company:${companyId}:numbers` : null,
    useCallback((event) => {
      if (event.type === "NUMBER_RESERVED") {
        setNumbers((items) => items.filter((item) => item.id !== event.sim_record_id));
      }
      if (event.type === "NUMBER_RELEASED") {
        loadNumbers();
      }
    }, [loadNumbers])
  );

  useRealtimeChannel(
    companyId ? `company:${companyId}:plans` : null,
    useCallback((event) => {
      if (event.type === "PLAN_CREATED") {
        setPlans((items) => [event.plan, ...items.filter((item) => item.id !== event.plan.id)]);
        setNotice(`New plan published: ${event.plan.name}`);
      }
    }, [])
  );

  useRealtimeChannel(
    currentUser?.id ? `user:${currentUser.id}:kyc` : null,
    useCallback((event) => {
      if (event.type === "KYC_SUBMITTED" || event.type === "KYC_REVIEWED") {
        apiRequest("/kyc/mine").then(setKycItems).catch(() => null);
        apiRequest("/dashboard/customer").then(setDashboard).catch(() => null);
        setReserved((item) => item ? { ...item, status: event.sim_status ?? item.status } : item);
        setNotice(`KYC status updated: ${event.status}`);
      }
    }, [])
  );

  useRealtimeChannel(
    currentUser?.id ? `user:${currentUser.id}:activation` : null,
    useCallback((event) => {
      if (event.type === "ACTIVATION_UPDATED") {
        setDashboard((data) => {
          const timeline = data?.activation_timeline ?? [];
          const nextTimeline = [
            event.attempt,
            ...timeline.filter((attempt) => attempt.id !== event.attempt.id)
          ];
          return {
            ...data,
            sim_status: event.sim_status ?? data?.sim_status,
            activation_timeline: nextTimeline
          };
        });
        setReserved((item) => item ? { ...item, status: event.sim_status ?? item.status } : item);
        setNotice(`Activation updated: ${event.attempt.status}`);
      }
    }, [])
  );

  useRealtimeChannel(
    currentUser?.id ? `user:${currentUser.id}:complaints` : null,
    useCallback((event) => {
      if (event.type === "COMPLAINT_UPDATED") {
        setDashboard((data) => {
          const complaints = data?.complaints ?? [];
          return {
            ...data,
            complaints: [
              event.complaint,
              ...complaints.filter((item) => item.id !== event.complaint.id)
            ]
          };
        });
        setNotice(`Complaint updated: ${event.complaint.status}`);
      }
    }, [])
  );

  async function reserve(simRecordId) {
    setError("");
    setNotice("");
    if (!selectedPlanId) {
      setError("Select a plan before reserving a number.");
      return;
    }
    try {
      const result = await apiRequest("/sims/reserve", {
        method: "POST",
        body: JSON.stringify({ sim_record_id: simRecordId, plan_id: Number(selectedPlanId) })
      });
      setReserved(result);
      setKycForm((form) => ({ ...form, full_name: currentUser?.full_name ?? form.full_name }));
      setNotice(`${result.msisdn} reserved until ${new Date(result.reserved_until).toLocaleString()}`);
      setNumbers((items) => items.filter((item) => item.id !== simRecordId));
      apiRequest("/dashboard/customer").then(setDashboard).catch(() => null);
    } catch (err) {
      setError(err.message);
      loadNumbers();
    }
  }

  function readUpload(field, file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setKycForm((form) => ({ ...form, [field]: reader.result }));
    reader.readAsDataURL(file);
  }

  async function submitKyc(event) {
    event.preventDefault();
    const selectedSim = reserved ?? dashboard?.selected_sim;
    if (!selectedSim?.id) {
      setError("Reserve a number before submitting KYC.");
      return;
    }
    setError("");
    setNotice("");
    if (!kycForm.document_upload_placeholder || !kycForm.selfie_placeholder) {
      setError("Upload both ID document and selfie before submitting KYC.");
      return;
    }
    try {
      const result = await apiRequest("/kyc/submit", {
        method: "POST",
        body: JSON.stringify({ ...kycForm, sim_record_id: selectedSim.id })
      });
      setKycItems((items) => [result, ...items.filter((item) => item.id !== result.id)]);
      setReserved((item) => item ? { ...item, status: "KYC_PENDING" } : item);
      setNotice("KYC submitted for seller verification");
      apiRequest("/dashboard/customer").then(setDashboard).catch(() => null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function createComplaint(event) {
    event.preventDefault();
    const simId = reserved?.id ?? dashboard?.selected_sim?.id;
    if (!simId) return;
    const result = await apiRequest("/dashboard/complaints", {
      method: "POST",
      body: JSON.stringify({ sim_record_id: simId, ...complaintForm })
    });
    setDashboard((data) => ({ ...data, complaints: [result, ...(data?.complaints ?? [])] }));
    setComplaintForm({ title: "", description: "" });
    setNotice("Complaint created");
  }

  async function createReplacement(event) {
    event.preventDefault();
    const simId = reserved?.id ?? dashboard?.selected_sim?.id;
    if (!simId) return;
    const result = await apiRequest("/dashboard/replacements", {
      method: "POST",
      body: JSON.stringify({ old_sim_record_id: simId, reason: replacementReason })
    });
    setDashboard((data) => ({ ...data, replacements: [result, ...(data?.replacements ?? [])] }));
    setReplacementReason("");
    setNotice("Replacement requested");
  }

  async function rechargeSim(simRecordId, planId) {
    setError("");
    setNotice("");
    try {
      await apiRequest("/usage/recharge", {
        method: "POST",
        body: JSON.stringify({ sim_record_id: simRecordId, plan_id: Number(planId) })
      });
      setNotice("Recharge successful");
      apiRequest("/usage/mine").then(setUsage).catch(() => null);
      apiRequest("/usage/recharges").then(setRecharges).catch(() => null);
      apiRequest("/dashboard/customer").then(setDashboard).catch(() => null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function secureSimAction(simRecordId, action) {
    const purpose = action === "suspend" ? "SIM_SUSPENSION" : "SIM_DEACTIVATION";
    let otpResponse;
    try {
      otpResponse = await apiRequest("/otp/request", {
        method: "POST",
        body: JSON.stringify({ purpose, reference_id: String(simRecordId) })
      });
    } catch (err) {
      setError(err.message);
      return;
    }
    window.alert(`Dev OTP for SIM ${action}: ${otpResponse.dev_otp}`);
    const otp_code = window.prompt(`Enter OTP to ${action} this SIM`);
    if (!otp_code) return;
    const password = window.prompt(`Confirm your password to ${action} this SIM`);
    if (!password) return;
    setError("");
    try {
      await apiRequest(`/sims/${simRecordId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ password, otp_code })
      });
      setNotice(`SIM ${action} completed`);
      apiRequest("/dashboard/customer").then(setDashboard).catch(() => null);
      apiRequest("/usage/mine").then(setUsage).catch(() => null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function reactivateSim(simRecordId) {
    const password = window.prompt("Confirm your password to reactivate this SIM");
    if (!password) return;
    try {
      await apiRequest(`/sims/${simRecordId}/reactivate`, {
        method: "POST",
        body: JSON.stringify({ password })
      });
      setNotice("SIM reactivated");
      apiRequest("/dashboard/customer").then(setDashboard).catch(() => null);
      apiRequest("/usage/mine").then(setUsage).catch(() => null);
    } catch (err) {
      setError(err.message);
    }
  }

  const latestKyc = kycItems[0];
  const selectedStatus = reserved?.status ?? dashboard?.sim_status;
  const canSubmitKyc = Boolean(reserved?.id ?? dashboard?.selected_sim?.id) && ["RESERVED", "KYC_REJECTED", "KYC_CORRECTION_REQUESTED"].includes(selectedStatus);
  const activationProcessing = ["KYC_VERIFIED", "ACTIVATING", "MANUAL_REVIEW_REQUIRED"].includes(selectedStatus);
  const selectedSim = reserved ?? dashboard?.selected_sim;
  const kycDisplay = latestKyc?.status ?? dashboard?.kyc_status ?? (selectedStatus === "ACTIVE" ? "Completed" : "Pending submission");
  const latestActivationAttempt = (dashboard?.activation_timeline ?? []).find(
    (attempt) => attempt.sim_record_id === selectedSim?.id
  ) ?? null;
  const latestTelecom = dashboard?.telecom_tracking?.[0];

  return (
    <section className="grid gap-6">
      <h1 className="text-2xl font-semibold">Customer Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricTile label="Available numbers loaded" value={numbers.length} />
        <MetricTile label="Selected number" value={reserved?.msisdn ?? dashboard?.selected_number ?? "Not selected"} />
        <MetricTile label="KYC" value={kycDisplay} />
      </div>
      {dashboard?.selected_sim ? (
        <div className="grid gap-3 rounded border border-slate-200 bg-white p-4 text-sm md:grid-cols-3">
          <span>Operator: {dashboard.selected_operator}</span>
          <span>SIM status: {dashboard.sim_status}</span>
          <span>ICCID/IMSI: {dashboard.selected_sim.iccid} / {dashboard.selected_sim.imsi}</span>
          <span className="flex flex-wrap gap-2">
            <button className="w-fit rounded border border-amber-300 px-3 py-1 text-amber-700" onClick={() => secureSimAction(dashboard.selected_sim.id, "suspend")} type="button">Suspend SIM</button>
            <button className="w-fit rounded border border-red-300 px-3 py-1 text-alert" onClick={() => secureSimAction(dashboard.selected_sim.id, "deactivate")} type="button">Deactivate SIM</button>
            {["SUSPENDED", "ACTIVE_IDLE", "DORMANT"].includes(dashboard.sim_status) ? <button className="w-fit rounded bg-signal px-3 py-1 text-white" onClick={() => reactivateSim(dashboard.selected_sim.id)} type="button">Reactivate SIM</button> : null}
          </span>
        </div>
      ) : null}
      {dashboard?.profile ? (
        <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 text-sm md:grid-cols-4">
          <div><span className="text-slate-500">Profile</span><div className="font-semibold">{dashboard.profile.tier}</div></div>
          <div><span className="text-slate-500">Segment</span><div className="font-semibold">{dashboard.profile.segment}</div></div>
          <div><span className="text-slate-500">Churn risk</span><div className="font-semibold">{dashboard.profile.churn_risk}</div></div>
          <div><span className="text-slate-500">Recommendation</span><div className="font-semibold">{dashboard.profile.recommendation}</div></div>
        </div>
      ) : null}
      {companyId ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => (
            <button key={plan.id} className={`rounded border bg-white p-4 text-left ${String(plan.id) === selectedPlanId ? "border-signal ring-2 ring-cyan-100" : "border-slate-200"}`} onClick={() => setSelectedPlanId(String(plan.id))} type="button">
              <div className="font-semibold">{plan.name}</div>
              <div className="mt-1 text-2xl font-semibold text-ink">Rs. {plan.monthly_price}</div>
              <p className="mt-2 text-sm text-slate-600">{plan.description}</p>
              <div className="mt-3 text-xs text-slate-500">{plan.data_gb}GB | {plan.voice_minutes} mins | {plan.sms_count} SMS | {plan.validity_days} days</div>
            </button>
          ))}
          {plans.length === 0 ? (
            <div className="rounded border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
              No plans published for this operator yet.
            </div>
          ) : null}
        </div>
      ) : null}
      {notice ? <p className="rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p> : null}
      {error ? <p className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-alert">{error}</p> : null}
      {usage.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {usage.map((item) => (
            <div key={item.sim_record_id} className="rounded border border-slate-200 bg-white p-4 text-sm">
              <div className="font-semibold">{item.msisdn} - {item.plan?.name ?? "No plan"}</div>
              <div className="mt-3 grid gap-2">
                <div>Data: {item.data_used_gb}GB used, {item.data_left_gb}GB left</div>
                <div>Voice: {item.voice_used_minutes} mins used, {item.voice_left_minutes} mins left</div>
                <div>SMS: {item.sms_used_count} used, {item.sms_left_count} left</div>
                <div>Valid until: {item.valid_until ? new Date(item.valid_until).toLocaleDateString() : "Not active"}</div>
              </div>
              {plans.length ? (
                <button className="mt-3 rounded bg-signal px-3 py-1 text-white" onClick={() => rechargeSim(item.sim_record_id, selectedPlanId || plans[0].id)} type="button">Recharge selected plan</button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      <label className="grid max-w-sm gap-2 text-sm">
        Operator
        <select className="rounded border border-slate-300 px-3 py-2" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
          <option value="">Choose company</option>
          {companies.map((company) => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </select>
      </label>
      {reserved ? (
        <div className="rounded border border-slate-200 bg-white p-4">
          <h2 className="font-semibold">Reserved SIM</h2>
          <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
            <p>Company: {reserved.company_name ?? reserved.company_id}</p>
            <p>Status: {reserved.status}</p>
            <p>MSISDN: {reserved.msisdn}</p>
            <p>ICCID: {reserved.iccid}</p>
            <p>IMSI: {reserved.imsi}</p>
            <p>Reserved until: {reserved.reserved_until ? new Date(reserved.reserved_until).toLocaleString() : "Not set"}</p>
          </div>
        </div>
      ) : null}
      {activationProcessing ? (
        <div className="rounded border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-900">
          Activation under processing
        </div>
      ) : null}
      {selectedSim && !canSubmitKyc && !activationProcessing ? (
        <div className="rounded border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
          KYC submission is available only for a reserved number. Current SIM status: {selectedStatus}.
        </div>
      ) : null}
      {latestTelecom ? (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <h2 className="font-semibold">Activation Tracking</h2>
            <p className="text-sm text-slate-500">Telecom layer visibility from CRM to service activation.</p>
          </div>
          <div className="grid gap-3 p-4 text-sm md:grid-cols-4">
            <div><span className="text-slate-500">Correlation ID</span><div className="font-semibold">{latestTelecom.correlation_id}</div></div>
            <div><span className="text-slate-500">Order ID</span><div className="font-semibold">{latestTelecom.order_id}</div></div>
            <div><span className="text-slate-500">Current Layer</span><div className="font-semibold">{latestTelecom.current_layer ?? "Complete"}</div></div>
            <div><span className="text-slate-500">Status</span><div className="font-semibold">{latestTelecom.activation_status}</div></div>
          </div>
          <div className="grid gap-2 p-4 pt-0 text-sm md:grid-cols-3">
            {(latestTelecom.timeline ?? []).map((event) => (
              <div key={event.event_id} className="rounded border border-slate-200 p-3">
                <div className="font-medium">{event.layer ?? "SYSTEM"}: {event.status}</div>
                <div className="text-slate-500">{new Date(event.timestamp).toLocaleTimeString()} - {event.event_description}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <ActivationFlow attempt={latestActivationAttempt} />
      {dashboard?.activation_timeline?.length ? (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="grid grid-cols-4 border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">
            <span>Attempt</span><span>Status</span><span>Current</span><span>Failed</span>
          </div>
          {dashboard.activation_timeline.map((item) => (
            <div key={item.id} className="grid grid-cols-4 border-b border-slate-100 px-4 py-3 text-sm">
              <span>#{item.id}</span><span>{item.status}</span><span>{item.current_node ?? ""}</span><span>{item.failed_node ?? ""}</span>
            </div>
          ))}
        </div>
      ) : null}
      {(reserved || dashboard?.selected_sim) ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <form className="grid gap-3 rounded border border-slate-200 bg-white p-4" onSubmit={createComplaint}>
            <h2 className="font-semibold">Complaints</h2>
            <TextInput label="Title" value={complaintForm.title} onChange={(value) => setComplaintForm({ ...complaintForm, title: value })} />
            <TextInput label="Description" value={complaintForm.description} onChange={(value) => setComplaintForm({ ...complaintForm, description: value })} />
            <button className="w-fit rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Raise complaint</button>
            {(dashboard?.complaints ?? []).map((item) => <p className="text-sm" key={item.id}>{item.title}: {item.status}</p>)}
          </form>
          <form className="grid gap-3 rounded border border-slate-200 bg-white p-4" onSubmit={createReplacement}>
            <h2 className="font-semibold">Replacement Request</h2>
            <TextInput label="Reason" value={replacementReason} onChange={setReplacementReason} />
            <button className="w-fit rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Request replacement</button>
            {(dashboard?.replacements ?? []).map((item) => <p className="text-sm" key={item.id}>{item.reason}: {item.status}</p>)}
          </form>
        </div>
      ) : null}
      {canSubmitKyc ? (
        <form className="grid gap-4 rounded border border-slate-200 bg-white p-4" onSubmit={submitKyc}>
          <h2 className="font-semibold">Submit KYC</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <TextInput label="Name" required value={kycForm.full_name} onChange={(value) => setKycForm({ ...kycForm, full_name: value })} />
            <TextInput label="DOB" required type="date" value={kycForm.date_of_birth} onChange={(value) => setKycForm({ ...kycForm, date_of_birth: value })} />
            <TextInput label="Address" required value={kycForm.address} onChange={(value) => setKycForm({ ...kycForm, address: value })} />
            <TextInput label="ID type" required value={kycForm.document_type} onChange={(value) => setKycForm({ ...kycForm, document_type: value })} />
            <TextInput label="ID number" required value={kycForm.document_number} onChange={(value) => setKycForm({ ...kycForm, document_number: value })} />
            <label className="grid gap-2 text-sm">
              ID document
              <input className="rounded border border-slate-300 px-3 py-2" type="file" accept="image/*,.pdf" onChange={(event) => readUpload("document_upload_placeholder", event.target.files?.[0])} required />
            </label>
            <label className="grid gap-2 text-sm">
              Selfie
              <input className="rounded border border-slate-300 px-3 py-2" type="file" accept="image/*" onChange={(event) => readUpload("selfie_placeholder", event.target.files?.[0])} required />
            </label>
          </div>
          <button className="w-fit rounded bg-signal px-4 py-2 font-medium text-white" type="submit">Submit KYC</button>
        </form>
      ) : null}
      {recharges.length ? (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">Recharge History</div>
          {recharges.map((item) => (
            <div key={item.id} className="grid gap-2 border-b border-slate-100 px-4 py-3 text-sm md:grid-cols-4">
              <span>{item.msisdn}</span><span>{item.plan_name}</span><span>Rs. {item.amount}</span><span>{item.status}</span>
            </div>
          ))}
        </div>
      ) : null}
      {kycItems.length ? (
        <div className="overflow-hidden rounded border border-slate-200 bg-white">
          <div className="grid grid-cols-4 border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-500">
            <span>MSISDN</span>
            <span>Status</span>
            <span>Company</span>
            <span>Note</span>
          </div>
          {kycItems.map((item) => (
            <div key={item.id} className="grid grid-cols-4 border-b border-slate-100 px-4 py-3 text-sm">
              <span>{item.msisdn}</span>
              <span>{item.status}</span>
              <span>{item.company_name}</span>
              <span>{item.correction_reason ?? item.rejection_reason ?? ""}</span>
            </div>
          ))}
        </div>
      ) : null}
      <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
        {numbers.map((number) => (
          <button key={number.id} className="rounded border border-slate-200 bg-white p-3 text-left hover:border-signal" onClick={() => reserve(number.id)}>
            <span className="block font-medium">{number.msisdn}</span>
            <span className="text-xs text-slate-500">{number.status}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

import { Link } from "react-router-dom";
import { Building2, ShieldCheck, Store, UserRound } from "lucide-react";

const portals = [
  {
    role: "CUSTOMER",
    title: "Customer",
    body: "Reserve numbers, submit KYC, track activation, complaints, and replacement requests.",
    register: true,
    Icon: UserRound
  },
  {
    role: "SELLER",
    title: "Seller",
    body: "Verify customer KYC, handle failed activation cases, complaints, and replacements.",
    register: true,
    Icon: Store
  },
  {
    role: "COMPANY",
    title: "Company",
    body: "Manage sellers, plans, SIM inventory, node failures, analytics, and operations inboxes.",
    register: true,
    Icon: Building2
  },
  {
    role: "ADMIN",
    title: "Admin",
    body: "Control companies, sellers, inventory, activation logs, audit logs, and platform setup.",
    register: false,
    Icon: ShieldCheck
  }
];

export function LandingPage() {
  return (
    <section className="grid gap-8">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/70 lg:p-8">
        <p className="text-sm font-semibold uppercase text-signal">SIM lifecycle operations platform</p>
        <h1 className="mt-3 max-w-4xl text-5xl font-semibold tracking-normal text-ink">
          Telecom360
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          Multi-operator number reservation, KYC verification, core network activation, and
          operations intelligence in one workflow-driven platform.
        </p>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg bg-slate-50 p-4"><div className="text-2xl font-semibold">1000+</div><div className="text-sm text-slate-500">SIMs per operator</div></div>
          <div className="rounded-lg bg-slate-50 p-4"><div className="text-2xl font-semibold">Live</div><div className="text-sm text-slate-500">Reservation updates</div></div>
          <div className="rounded-lg bg-slate-50 p-4"><div className="text-2xl font-semibold">5-node</div><div className="text-sm text-slate-500">Core activation flow</div></div>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {portals.map((portal) => (
          <div key={portal.role} className="grid gap-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 hover:border-cyan-200 hover:shadow-md">
            <div>
              <div className="mb-4 grid h-11 w-11 place-items-center rounded-lg bg-cyan-50 text-signal ring-1 ring-cyan-100">
                <portal.Icon size={22} />
              </div>
              <div className="text-xs font-semibold uppercase text-signal">{portal.role}</div>
              <h2 className="mt-1 text-xl font-semibold">{portal.title} Portal</h2>
              <p className="mt-2 text-sm text-slate-600">{portal.body}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link className="rounded bg-signal px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-cyan-800" to={`/login?role=${portal.role}`}>
                Login
              </Link>
              {portal.register ? (
                <Link className="rounded border border-slate-300 px-3 py-2 text-sm font-medium hover:border-signal hover:text-signal" to={`/register?role=${portal.role}`}>
                  Register
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

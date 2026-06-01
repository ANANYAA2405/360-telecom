import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../context/AuthContext.jsx";

export function AppShell() {
  const { session, setSession } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <Link to="/" className="flex items-center gap-3 text-lg font-semibold tracking-normal text-ink">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-signal text-sm font-bold text-white">T360</span>
            <span>Telecom360</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link className="font-medium text-slate-600 hover:text-signal" to="/home">Home</Link>
            {!session?.token ? <Link className="font-medium text-slate-600 hover:text-signal" to="/">Choose portal</Link> : null}
            {session?.role ? <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold text-signal ring-1 ring-cyan-100">{session.role}</span> : null}
            {session?.token ? (
              <button className="rounded border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:border-signal hover:text-signal" onClick={() => setSession(null)}>
                Logout
              </button>
            ) : null}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

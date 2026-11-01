import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { DEMO_MODE } from "../api";
import { errorMessage } from "../api/errors";
import { hasAny, ROLE_LABEL, type Role } from "../lib/roles";
import { useAuth } from "../state/Auth";
import { useNotifications } from "../state/Notifications";
import { useTheme } from "../state/Theme";
import { useToast } from "../state/Toast";
import { ErrorBoundary } from "./ErrorBoundary";
import { Banner, Button } from "./ui";

type Item = { to: string; label: string; roles?: Role[] };

const NAV: { label?: string; items: Item[] }[] = [
  {
    items: [
      { to: "/", label: "داشبورد" },
      { to: "/notifications", label: "اعلان‌ها" },
      { to: "/profile", label: "پروفایل" },
    ],
  },
  {
    label: "مرخصی",
    items: [
      { to: "/requests", label: "درخواست‌ها", roles: ["employee", "manager", "hr"] },
      { to: "/requests/new", label: "ثبت درخواست", roles: ["employee", "manager", "hr"] },
      { to: "/calendar", label: "تقویم" },
      { to: "/timeline", label: "نوار زمانی" },
      { to: "/balances", label: "مانده سهمیه", roles: ["employee", "manager", "hr", "exec"] },
      { to: "/coverage", label: "پوشش تیم", roles: ["manager", "hr"] },
    ],
  },
  {
    label: "منابع انسانی",
    items: [
      { to: "/hr/absences", label: "ثبت غیبت", roles: ["hr"] },
      { to: "/hr/entitlements", label: "سهمیه‌ها", roles: ["hr"] },
      { to: "/hr/bradford", label: "تحلیل Bradford", roles: ["hr"] },
      { to: "/hr/import", label: "ورود گروهی", roles: ["hr"] },
      { to: "/hr/contracts", label: "قراردادها", roles: ["hr"] },
      { to: "/leave-types", label: "انواع مرخصی", roles: ["hr", "admin"] },
      { to: "/reports", label: "گزارش‌ها", roles: ["hr", "exec"] },
    ],
  },
  {
    label: "سازمان و سامانه",
    items: [
      { to: "/employees", label: "کارکنان", roles: ["hr", "admin", "manager"] },
      { to: "/organization", label: "ساختار سازمانی", roles: ["admin", "hr"] },
      { to: "/holidays", label: "تعطیلات" },
      { to: "/settings", label: "تنظیمات", roles: ["admin"] },
      { to: "/jobs", label: "Jobها و سلامت", roles: ["admin"] },
      { to: "/audit", label: "حسابرسی", roles: ["admin", "hr"] },
    ],
  },
];

/** «درخواست‌ها» برای فهرست و جزئیات فعال است، ولی «ثبت درخواست» جدا هایلایت می‌شود. */
function isNavActive(to: string, isActive: boolean, pathname: string): boolean {
  if (to === "/requests") return pathname.startsWith("/requests") && pathname !== "/requests/new";
  return isActive;
}

export function Layout() {
  const { user, logout } = useAuth();
  const { mode, toggle } = useTheme();
  const toast = useToast();
  const { unread } = useNotifications();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const firstRender = useRef(true);

  // با هر تغییر مسیر: بستن منوی موبایل، بازگشت به بالای صفحه و انتقال فوکوس به محتوا (برای کاربران صفحه‌خوان/کیبورد)
  useEffect(() => {
    setOpen(false);
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    window.scrollTo(0, 0);
    mainRef.current?.focus({ preventScroll: true });
  }, [location.pathname]);

  // Escape منوی موبایل را می‌بندد
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  if (!user) return null;
  const visible = (item: Item) => !item.roles || hasAny(user.roles, ...item.roles);

  const onLogout = async () => {
    setLeaving(true);
    try {
      await logout();
    } catch (e) {
      toast(errorMessage(e), "danger");
    } finally {
      setLeaving(false);
      navigate("/login");
    }
  };

  const initial = user.displayName.trim().slice(0, 1);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main" onClick={(e) => { e.preventDefault(); mainRef.current?.focus(); }}>پرش به محتوا</a>
      {open && <div className="overlay show" onClick={() => setOpen(false)} aria-hidden="true" />}
      <aside id="sidebar" className={`sidebar${open ? " open" : ""}`} aria-label="ناوبری اصلی">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">زش</div>
          <div>
            <strong>زکریا شیمی</strong>
            <small>سامانه مرخصی و غیبت</small>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((g, i) => {
            const items = g.items.filter(visible);
            if (!items.length) return null;
            return (
              <div key={i} role={g.label ? "group" : undefined} aria-label={g.label}>
                {g.label ? <div className="section-label" aria-hidden="true">{g.label}</div> : null}
                {items.map((it) => (
                  <NavLink
                    key={it.to}
                    to={it.to}
                    end={it.to === "/"}
                    className={({ isActive }) => (isNavActive(it.to, isActive, location.pathname) ? "active" : undefined)}
                    onClick={() => setOpen(false)}
                  >
                    {it.label}
                    {it.to === "/notifications" && unread > 0 && <span className="nav-badge" aria-label={`${unread} اعلان خوانده‌نشده`}>{unread > 99 ? "99+" : unread}</span>}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <button
            type="button"
            className="icon-btn menu-btn"
            aria-label="باز کردن منو"
            aria-expanded={open}
            aria-controls="sidebar"
            onClick={() => setOpen(true)}
          >
            ☰
          </button>
          <div className="user-chip">
            <div className="avatar" aria-hidden="true">{initial}</div>
            <div>
              <strong>{user.displayName}</strong>
              <div className="user-meta">
                {user.roles.map((r) => ROLE_LABEL[r]).join("، ")} · {user.companyName}
              </div>
            </div>
          </div>
          <div className="topbar-actions">
            <Link
              to="/notifications"
              className="icon-btn bell"
              aria-label={unread > 0 ? `اعلان‌ها، ${unread} مورد خوانده‌نشده` : "اعلان‌ها"}
              title="مرکز اعلان‌ها"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.7 21a2 2 0 0 1-3.4 0" />
              </svg>
              {unread > 0 && <span className="bell-badge" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
            </Link>
            <button
              type="button"
              className="icon-btn"
              onClick={toggle}
              aria-label={mode === "dark" ? "تغییر به پوسته روشن" : "تغییر به پوسته تیره"}
              title={mode === "dark" ? "پوسته روشن" : "پوسته تیره"}
            >
              {mode === "dark" ? "☀" : "☾"}
            </button>
            <Button variant="secondary" size="sm" loading={leaving} onClick={() => void onLogout()}>
              خروج
            </Button>
          </div>
        </header>
        <main id="main" className="content" ref={mainRef} tabIndex={-1}>
          {DEMO_MODE && (
            <Banner>
              داده و حساب‌ها برچسب <strong>Demo</strong> دارند. مرجع تصمیم Backend است؛ این حالت فقط برای بررسی رابط است.
              اتصال واقعی: <code>VITE_DEMO_MODE=false</code>
            </Banner>
          )}
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

import { FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { DEMO_MODE } from "../api";
import { DEMO_ACCOUNTS, resetDemo } from "../api/demo";
import { errorMessage } from "../api/errors";
import { Banner, Button, Card, Field, Input } from "../components/ui";
import { useDocumentTitle } from "../lib/hooks";
import { useAuth } from "../state/Auth";
import { useTheme } from "../state/Theme";
import { useToast } from "../state/Toast";

type FromState = { from?: { pathname?: string; search?: string; hash?: string } } | null;

export function LoginPage() {
  useDocumentTitle("ورود");
  const { user, login, error: authError, refresh } = useAuth();
  const { mode, toggle } = useTheme();
  const toast = useToast();
  const location = useLocation();
  const [username, setUsername] = useState(DEMO_MODE ? "sara" : "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) {
    const from = (location.state as FromState)?.from;
    const target = from?.pathname && from.pathname !== "/login" ? `${from.pathname}${from.search ?? ""}${from.hash ?? ""}` : "/";
    return <Navigate to={target} replace />;
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await login(username.trim(), DEMO_MODE ? (password || "demo-password-not-used") : password);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <Card>
        <div className="login-card">
          <div className="brand" style={{ border: 0, padding: 0, marginBottom: 16 }}>
            <div className="brand-mark" aria-hidden="true">زش</div>
            <div>
              <h1 style={{ margin: 0, fontSize: "1.05rem" }}>هلدینگ زکریا شیمی</h1>
              <small>ورود به سامانه مرخصی و غیبت</small>
            </div>
          </div>
          {DEMO_MODE && (
            <Banner>
              حالت نمایشی: رمز واقعی بررسی نمی‌شود. یکی از نقش‌های Demo را انتخاب کنید.
            </Banner>
          )}
          {authError && (
            <Banner tone="danger">
              {authError.message}{" "}
              <button type="button" className="btn ghost sm" onClick={() => void refresh()}>
                تلاش دوباره
              </button>
            </Banner>
          )}
          {error && <Banner tone="danger">{error}</Banner>}
          <form onSubmit={submit} noValidate>
            <Field label="نام کاربری" required>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                dir="ltr"
                className="ltr-input"
                autoFocus
                required
              />
            </Field>
            <Field label="رمز عبور" required={!DEMO_MODE} hint={DEMO_MODE ? "در Demo نادیده گرفته می‌شود" : undefined}>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                dir="ltr"
                className="ltr-input"
                required={!DEMO_MODE}
              />
            </Field>
            <Button type="submit" loading={busy} disabled={!username.trim() || (!DEMO_MODE && !password)} style={{ width: "100%" }}>
              {busy ? "در حال ورود…" : "ورود"}
            </Button>
          </form>
          {DEMO_MODE && (
            <div className="toolbar" style={{ marginTop: 16 }} role="group" aria-label="نقش‌های Demo">
              {DEMO_ACCOUNTS.map((a) => (
                <Button
                  key={a.username}
                  type="button"
                  variant="secondary"
                  size="sm"
                  aria-pressed={username === a.username}
                  onClick={() => setUsername(a.username)}
                >
                  {a.role}
                </Button>
              ))}
            </div>
          )}
          <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn ghost sm" onClick={toggle}>{mode === "dark" ? "پوسته روشن" : "پوسته تیره"}</button>
            {DEMO_MODE && (
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => { resetDemo(); setError(""); toast("داده Demo بازنشانی شد", "success"); }}
              >
                بازنشانی داده Demo
              </button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

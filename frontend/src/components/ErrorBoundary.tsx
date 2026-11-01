import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; fullPage?: boolean };
type State = { failed: boolean };

/** جلوی صفحه‌ی سفید را می‌گیرد: خطای رندر در یک صفحه، کل سامانه را از کار نمی‌اندازد. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // گزارش به کنسول؛ در صورت وجود سامانه‌ی پایش، اینجا متصل شود. محتوای حساس ثبت نمی‌شود.
    console.error("UI error:", error.message, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className={this.props.fullPage ? "login-wrap" : undefined}>
        <section className="card" role="alert" style={{ maxWidth: 520, margin: "0 auto" }}>
          <h2>مشکلی در نمایش این صفحه پیش آمد</h2>
          <p>خطایی غیرمنتظره رخ داد. می‌توانید صفحه را دوباره بارگذاری کنید؛ اگر ادامه داشت، به پشتیبانی اطلاع دهید.</p>
          <div className="toolbar">
            <button type="button" className="btn" onClick={() => window.location.reload()}>بارگذاری دوباره</button>
            <a className="btn secondary" href="/">بازگشت به داشبورد</a>
          </div>
        </section>
      </div>
    );
  }
}

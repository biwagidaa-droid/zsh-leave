import type { DeadlineInfo } from "../lib/deadline";

/** برچسب کوتاه مهلت تأیید (لغو خودکار)؛ برای وضعیت‌های بی‌ارتباط خط تیره نشان می‌دهد. */
export function DeadlineLabel({ info, hideEmpty }: { info: DeadlineInfo | null; hideEmpty?: boolean }) {
  if (!info) return hideEmpty ? null : <span className="muted">—</span>;
  return (
    <span className={`deadline ${info.tone}`}>
      <span className="dot" aria-hidden="true" />
      {info.label}
    </span>
  );
}

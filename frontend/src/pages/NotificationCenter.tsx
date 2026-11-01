import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/errors";
import {
  Badge, Banner, Button, Card, Checkbox, Empty, ErrorState, Field, Input, LoadingBlock, PageHeader, Segmented, Select, Tabs,
} from "../components/ui";
import { formatJalaliSafe } from "../lib/jalali";
import { categoryOfItem, countByCategory, filterNotifications, kindOfItem, targetOf } from "../lib/notificationEngine";
import {
  ALL_NOTIF_KINDS, KIND_CATEGORY, MASTER_LABEL, NOTIF_CATEGORY_LABEL, NOTIF_KIND_LABEL, SOUND_LABEL,
  type NotifCategory, type NotifMaster, type SoundId,
} from "../lib/notificationPrefs";
import { useNotifications } from "../state/Notifications";
import { useToast } from "../state/Toast";

const CATEGORIES = Object.keys(NOTIF_CATEGORY_LABEL) as NotifCategory[];

const PERMISSION_LABEL = {
  granted: "مجاز",
  denied: "مسدود (از تنظیمات مرورگر باز کنید)",
  default: "هنوز پرسیده نشده",
  unsupported: "این مرورگر پشتیبانی نمی‌کند",
} as const;

function NotificationSettings() {
  const { prefs, setPrefs, resetPrefs, permission, requestPermission, audioReady, testSound } = useNotifications();
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const soundOn = prefs.master === "on_sound";

  const toggleDesktop = async (on: boolean) => {
    if (!on) { setPrefs({ ...prefs, desktop: false }); return; }
    setAsking(true);
    try {
      const p = permission === "granted" ? "granted" : await requestPermission();
      if (p === "granted") setPrefs({ ...prefs, desktop: true });
      else toast(p === "unsupported" ? "این مرورگر اعلان دسکتاپ را پشتیبانی نمی‌کند" : "مجوز اعلان مرورگر داده نشد", "danger");
    } finally {
      setAsking(false);
    }
  };

  return (
    <Card title="تنظیمات اعلان" actions={<Button variant="ghost" size="sm" onClick={resetPrefs}>بازگشت به پیش‌فرض</Button>}>
      <Segmented
        label="حالت اعلان"
        value={prefs.master}
        onChange={(v) => setPrefs({ ...prefs, master: v as NotifMaster })}
        items={(Object.keys(MASTER_LABEL) as NotifMaster[]).map((id) => ({ id, label: MASTER_LABEL[id] }))}
      />
      {prefs.master === "off" && <Banner tone="info">در حالت خاموش، اعلان جدید نمایش یا شمارش نمی‌شود؛ اعلان‌ها همچنان در همین صفحه می‌مانند.</Banner>}
      <div className="grid grid-2">
        <Field label="صدای اعلان" hint={soundOn ? undefined : "فقط در حالت «روشن با صدا» پخش می‌شود"}>
          <Select value={prefs.soundId} disabled={!soundOn} onChange={(e) => setPrefs({ ...prefs, soundId: e.target.value as SoundId })}>
            {(Object.keys(SOUND_LABEL) as SoundId[]).map((id) => <option key={id} value={id}>{SOUND_LABEL[id]}</option>)}
          </Select>
        </Field>
        <Field label={`شدت صدا: ${Math.round(prefs.volume * 100)}٪`}>
          <Input
            type="range" min={0} max={100} step={5} className="range"
            value={Math.round(prefs.volume * 100)} disabled={!soundOn}
            onChange={(e) => setPrefs({ ...prefs, volume: Number(e.target.value) / 100 })}
          />
        </Field>
      </div>
      <div className="toolbar">
        <Button variant="secondary" size="sm" onClick={testSound} disabled={prefs.volume <= 0}>تست صدا</Button>
        {!audioReady && <span className="hint">مرورگر تا اولین کلیک یا فشردن کلید در صفحه اجازه‌ی پخش صدا نمی‌دهد؛ دکمه‌ی تست این مجوز را فعال می‌کند.</span>}
      </div>
      <div className="notif-desktop">
        <Checkbox
          label="نمایش اعلان در مرورگر (وقتی این تب در پیش‌زمینه نیست)"
          hint={`وضعیت مجوز: ${PERMISSION_LABEL[permission]}`}
          checked={prefs.desktop && permission === "granted"}
          disabled={asking || permission === "unsupported" || permission === "denied"}
          onChange={(e) => void toggleDesktop(e.target.checked)}
        />
        <p className="hint">
          اعلان مرورگر فقط تا زمانی کار می‌کند که سامانه در یکی از تب‌های باز باشد. اعلان هنگام بسته بودن مرورگر نیازمند Web Push و پشتیبانی Backend است و در این نسخه وجود ندارد.
        </p>
      </div>
      <fieldset className="field-group">
        <legend>نوع اعلان‌ها</legend>
        {CATEGORIES.map((cat) => {
          const kinds = ALL_NOTIF_KINDS.filter((k) => KIND_CATEGORY[k] === cat);
          if (!kinds.length) return null;
          return (
            <div key={cat} className="notif-kind-group">
              <div className="hint"><strong>{NOTIF_CATEGORY_LABEL[cat]}</strong></div>
              <div className="check-row">
                {kinds.map((k) => (
                  <Checkbox
                    key={k}
                    label={NOTIF_KIND_LABEL[k]}
                    checked={prefs.kinds[k]}
                    onChange={(e) => setPrefs({ ...prefs, kinds: { ...prefs.kinds, [k]: e.target.checked } })}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </fieldset>
      <p className="hint">تنظیمات روی همین مرورگر برای حساب شما ذخیره می‌شود و بین تب‌های باز هماهنگ است؛ بین دستگاه‌ها هماهنگ نمی‌شود.</p>
    </Card>
  );
}

export function NotificationsPage() {
  const toast = useToast();
  const { items, unreadAll, error, loading, reload, markRead } = useNotifications();
  const [category, setCategory] = useState<NotifCategory | "all">("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [busyId, setBusyId] = useState<number | "all" | null>(null);

  const counts = useMemo(() => countByCategory(items), [items]);
  const rows = useMemo(() => filterNotifications(items, { category, unreadOnly }), [items, category, unreadOnly]);
  const unread = items.filter((n) => !n.read);

  const mark = async (ids: number[], tag: number | "all") => {
    setBusyId(tag);
    try {
      await markRead(ids);
    } catch (e) {
      toast(errorMessage(e), "danger");
    } finally {
      setBusyId(null);
    }
  };

  const tabs = [
    { id: "all", label: `همه (${counts.all})` },
    ...CATEGORIES.map((c) => ({ id: c, label: `${NOTIF_CATEGORY_LABEL[c]} (${counts[c]})` })),
  ];

  return (
    <>
      <PageHeader
        title="مرکز اعلان‌ها"
        subtitle={`${unreadAll} اعلان خوانده‌نشده · متن اعلان‌ها بازنویسی‌شده است و نوع محرمانه ندارد`}
        actions={unread.length > 1 ? (
          <Button variant="secondary" size="sm" loading={busyId === "all"} onClick={() => void mark(unread.map((n) => n.id), "all")}>
            همه را خواندم
          </Button>
        ) : undefined}
      />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      <Tabs value={category} onChange={(v) => setCategory(v as NotifCategory | "all")} items={tabs} label="دسته‌بندی اعلان‌ها" />
      <div className="toolbar">
        <Checkbox label="فقط خوانده‌نشده‌ها" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
      </div>
      {loading && !items.length ? <LoadingBlock /> : null}
      {!loading && !rows.length && !error && (
        <Empty title="اعلانی وجود ندارد" hint={items.length ? "فیلتر دسته یا «فقط خوانده‌نشده‌ها» را تغییر دهید." : undefined} />
      )}
      <div className="stack">
        {rows.map((n) => {
          const kind = kindOfItem(n);
          const to = targetOf(n);
          return (
            <Card key={n.id}>
              <div className="card-head notif-item" style={{ alignItems: "flex-start", marginBottom: 0 }}>
                <div>
                  <strong>{n.title}</strong>
                  {!n.read && <span className="badge warn" style={{ marginInlineStart: 8 }}>جدید</span>}
                  <span style={{ marginInlineStart: 8 }}><Badge tone="muted">{NOTIF_CATEGORY_LABEL[categoryOfItem(n)]}</Badge></span>
                  <p>{n.body}</p>
                  <div className="hint">
                    {NOTIF_KIND_LABEL[kind]} · {formatJalaliSafe(n.createdAt)}
                    {n.requestId ? (
                      <> · <Link to={to} onClick={() => { if (!n.read) void mark([n.id], n.id); }}>مشاهده درخواست {n.requestId}</Link></>
                    ) : null}
                  </div>
                </div>
                {!n.read && (
                  <Button variant="secondary" size="sm" loading={busyId === n.id} onClick={() => void mark([n.id], n.id)}>خواندم</Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>
      <div className="mt"><NotificationSettings /></div>
    </>
  );
}

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { asApiError } from "../api/errors";
import type { NotificationItem } from "../api/types";
import { setUnreadBadge } from "../lib/documentChrome";
import { planAlerts, targetOf, unreadCount } from "../lib/notificationEngine";
import {
  defaultNotificationPrefs, hasPlayedHistory, loadPlayedIds, loadPrefs, prefsStorageKey, savePlayedIds, savePrefs,
  type NotificationPrefs,
} from "../lib/notificationPrefs";
import { isAudioUnlocked, playNotificationSound, unlockNotificationAudio } from "../lib/notificationSound";
import { useAuth } from "./Auth";
import { useToast } from "./Toast";

export type BrowserPermission = NotificationPermission | "unsupported";

type NotificationsState = {
  items: NotificationItem[];
  /** تعداد خوانده‌نشده‌ی مشمول تنظیمات (همان عددی که در Badge و عنوان تب می‌آید) */
  unread: number;
  /** تعداد کل خوانده‌نشده، صرف‌نظر از تنظیمات خاموش‌شده */
  unreadAll: number;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  markRead: (ids: number[]) => Promise<void>;
  prefs: NotificationPrefs;
  setPrefs: (next: NotificationPrefs) => void;
  resetPrefs: () => void;
  permission: BrowserPermission;
  requestPermission: () => Promise<BrowserPermission>;
  /** صدا فقط پس از اولین تعامل کاربر مجاز است (محدودیت Autoplay مرورگر) */
  audioReady: boolean;
  testSound: () => void;
};

const Ctx = createContext<NotificationsState | null>(null);

const POLL_MS = 30_000;
const CHANNEL = "zsh-leave-notifications";
/** رویدادی که Demo پس از ساخت اعلان جدید روی window می‌فرستد */
const DEMO_EVENT = "zsh-leave-notifications";
const MAX_DESKTOP = 3;

function currentPermission(): BrowserPermission {
  return typeof Notification === "undefined" ? "unsupported" : Notification.permission;
}

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const userId = user?.id ?? null;
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prefs, setPrefsState] = useState<NotificationPrefs>(defaultNotificationPrefs);
  const [permission, setPermission] = useState<BrowserPermission>(currentPermission);
  const [audioReady, setAudioReady] = useState(isAudioUnlocked());
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;
  const channelRef = useRef<BroadcastChannel | null>(null);
  const running = useRef(false);
  const again = useRef(false);

  const announce = useCallback((fresh: NotificationItem[], sound: boolean) => {
    const p = prefsRef.current;
    if (!fresh.length) return;
    toast(fresh.length === 1 ? `اعلان جدید: ${fresh[0].title}` : `${fresh.length} اعلان جدید دارید`, "info");
    if (sound) playNotificationSound(p.soundId, p.volume);
    if (p.desktop && currentPermission() === "granted" && (document.hidden || !document.hasFocus())) {
      for (const n of fresh.slice(0, MAX_DESKTOP)) {
        try {
          const note = new Notification(n.title, { body: n.body, tag: `zsh-leave-${n.id}`, lang: "fa", dir: "rtl" });
          note.onclick = () => { window.focus(); navigate(targetOf(n)); note.close(); };
        } catch { /* مرورگر اجازه نداد */ }
      }
    }
  }, [navigate, toast]);

  const reload = useCallback(async () => {
    if (userId == null) return;
    // درخواست‌های هم‌زمان ادغام می‌شوند؛ اگر در حین اجرا رویداد تازه‌ای رسید، یک دور دیگر اجرا می‌شود
    if (running.current) { again.current = true; return; }
    running.current = true;
    setLoading(true);
    try {
      do {
        again.current = false;
        const list = await api.notifications();
        setItems(list);
        setError(null);
        const seen = loadPlayedIds(userId);
        const baseline = !hasPlayedHistory(userId);
        const plan = planAlerts(list, seen, prefsRef.current, baseline);
        if (plan.markSeen.length || baseline) {
          savePlayedIds(userId, new Set([...seen, ...plan.markSeen]));
        }
        announce(plan.fresh, plan.sound);
      } while (again.current);
    } catch (e) {
      setError(asApiError(e).message);
    } finally {
      running.current = false;
      setLoading(false);
    }
  }, [userId, announce]);

  const broadcast = useCallback(() => {
    try { channelRef.current?.postMessage({ type: "changed", userId }); } catch { /* بسته‌شدن کانال */ }
  }, [userId]);

  const markRead = useCallback(async (ids: number[]) => {
    for (const id of ids) await api.readNotification(id);
    await reload();
    broadcast();
  }, [reload, broadcast]);

  const setPrefs = useCallback((next: NotificationPrefs) => {
    setPrefsState(next);
    if (userId != null) savePrefs(userId, next);
    broadcast();
  }, [userId, broadcast]);

  const resetPrefs = useCallback(() => setPrefs(defaultNotificationPrefs()), [setPrefs]);

  const requestPermission = useCallback(async (): Promise<BrowserPermission> => {
    if (typeof Notification === "undefined") return "unsupported";
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      return result;
    } catch {
      return currentPermission();
    }
  }, []);

  const testSound = useCallback(() => {
    unlockNotificationAudio();
    setAudioReady(isAudioUnlocked());
    const p = prefsRef.current;
    playNotificationSound(p.soundId, p.volume);
  }, []);

  // تنظیمات هر کاربر و بارگذاری اولیه
  useEffect(() => {
    if (userId == null) {
      setItems([]);
      setError(null);
      setUnreadBadge(0);
      return;
    }
    setPrefsState(loadPrefs(userId));
    void reload();
  }, [userId, reload]);

  // نظرسنجی دوره‌ای + رویدادهای هم‌زمان‌سازی
  useEffect(() => {
    if (userId == null) return;
    const poll = window.setInterval(() => { if (!document.hidden) void reload(); }, POLL_MS);
    const onDemo = () => { void reload(); };
    const onVisible = () => { if (!document.hidden) void reload(); };
    const onStorage = (e: StorageEvent) => {
      if (e.key === prefsStorageKey(userId)) setPrefsState(loadPrefs(userId));
    };
    window.addEventListener(DEMO_EVENT, onDemo);
    window.addEventListener("focus", onVisible);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("storage", onStorage);
    let channel: BroadcastChannel | null = null;
    if (typeof BroadcastChannel !== "undefined") {
      channel = new BroadcastChannel(CHANNEL);
      channel.onmessage = (e: MessageEvent) => {
        const m = e.data as { type?: string; userId?: number } | null;
        if (m?.type === "changed" && m.userId === userId) {
          setPrefsState(loadPrefs(userId));
          void reload();
        }
      };
      channelRef.current = channel;
    }
    return () => {
      window.clearInterval(poll);
      window.removeEventListener(DEMO_EVENT, onDemo);
      window.removeEventListener("focus", onVisible);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("storage", onStorage);
      channel?.close();
      channelRef.current = null;
    };
  }, [userId, reload]);

  // مرورگر تا اولین تعامل کاربر اجازه‌ی پخش صدا نمی‌دهد
  useEffect(() => {
    if (audioReady) return;
    const unlock = () => {
      unlockNotificationAudio();
      if (isAudioUnlocked()) {
        setAudioReady(true);
        window.removeEventListener("pointerdown", unlock);
        window.removeEventListener("keydown", unlock);
      }
    };
    window.addEventListener("pointerdown", unlock);
    window.addEventListener("keydown", unlock);
    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
  }, [audioReady]);

  const unread = useMemo(() => unreadCount(items, prefs), [items, prefs]);
  const unreadAll = useMemo(() => unreadCount(items), [items]);

  // عنوان تب و Badge فاویکون
  useEffect(() => { setUnreadBadge(userId == null ? 0 : unread); }, [unread, userId]);

  const value = useMemo<NotificationsState>(() => ({
    items, unread, unreadAll, loading, error, reload, markRead, prefs, setPrefs, resetPrefs,
    permission, requestPermission, audioReady, testSound,
  }), [items, unread, unreadAll, loading, error, reload, markRead, prefs, setPrefs, resetPrefs, permission, requestPermission, audioReady, testSound]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNotifications(): NotificationsState {
  const v = useContext(Ctx);
  if (!v) throw new Error("NotificationsProvider missing");
  return v;
}

# معماری

## ۱. نمای کلی
```
مرورگر (React+TS, RTL)  ──HTTPS──▶  Reverse Proxy (Caddy/Nginx)
                                        ├─▶ Frontend (فایل‌های استاتیک)
                                        └─▶ Backend (Django + DRF, Gunicorn) ──▶ PostgreSQL
                                                    ▲                          ▲
                                          Worker (مستقل) ─────────────────────┘
                                          ذخیره فایل: volume اختصاصی (خارج از webroot)
```
Redis فقط اگر در آزمون واقعی لازم شود اضافه می‌شود (تصمیم در decisions.md).

## ۲. ماژول‌های Backend (Django apps)
لایه‌بندی هر ماژول: `models` ← `selectors` (خواندن با اعمال scope) ← `services` (منطق کسب‌وکار و تراکنش) ← `api` (View/Serializer باریک).
| ماژول | مسئولیت |
|-------|---------|
| accounts | کاربر، ورود، نشست، نقش/گروه |
| organization | شرکت، واحد، سمت، پروفایل کارمند، مدیر مستقیم |
| contracts | قرارداد و دوره‌های الگوی کاری |
| calendars | تبدیل شمسی/میلادی، تعطیلات، تخمین روز کاری، تقویم |
| leave | نوع مرخصی، سیاست، درخواست، ماشین وضعیت، نظرات، پیوست، جانشین |
| entitlements | سهمیه، رویدادهای سهمیه، rollover، ورود گروهی |
| permissions | تنها نقطه تصمیم دسترسی (`PermissionService`) و redaction |
| notifications | اعلان داخلی، ایمیل، لاگ تحویل |
| audit | AuditEvent append-only |
| reports | گزارش‌ها و خروجی‌ها |
| jobs | اجرای وظایف، BackgroundJobExecution |
| core | SystemSetting، health، ابزار مشترک |

## ۳. قواعد معماری
1. تنها `LeaveRequestService` وضعیت درخواست را تغییر می‌دهد (Controller و Frontend ممنوع).
2. هر تغییر مانده با `select_for_update` روی ردیف سهمیه و در یک تراکنش، همراه EntitlementEvent.
3. هر خواندن داده از `selectors` با `PermissionService.scope(user)` فیلتر می‌شود؛ هیچ View مستقیم `Model.objects.all()` ندارد.
4. Serialization حساس فقط از `redaction.py` (تک‌نقطه‌ای) می‌گذرد؛ همان تابع برای API، تقویم، اعلان، خروجی استفاده می‌شود.
5. تاریخ‌ها: ذخیره میلادی؛ تبدیل فقط در `calendars.jalali`.
6. اعلان و ایمیل بعد از commit (`transaction.on_commit`) و با کلید یکتا برای جلوگیری از تکرار.

## ۴. Frontend
React + TypeScript، مسیریابی، لایه API با مدیریت خطا، کامپوننت تاریخ شمسی داخلی، تم روشن/تاریک با CSS variables، پشتیبانی `prefers-reduced-motion`. نقش‌ها فقط برای نمایش‌اند؛ مرجع تصمیم Backend است.

## ۵. استقرار
Docker Compose: `db`, `backend`, `worker`, `proxy` (+ `redis` اختیاری). جزئیات در deployment.md.

## ۶. استقلال از Nextcloud
هیچ وابستگی، فراخوانی یا مفهوم Nextcloud وجود ندارد. جایگزین‌ها: کاربران/نقش‌ها (accounts)، CalDAV (تقویم داخلی؛ خروجی ICS اختیاری)، Activity/Notification (notifications+audit)، Background Jobs (worker)، occ (management commands).

# گزارش فاز ۱۱ — امنیت، آزمون و استقرار

## هدف و وضعیت اولیه

هدف، اثبات کنترل دسترسی، صحت عملیات، بازیابی، پایش و استقرار است. ممیزی فقط‌خواندنی امنیتی انجام شد؛ مسیرهای احراز هویت و گردش‌کار HTTP، پیوست‌ها و گزارش‌ها در Backend موجود نیستند، بنابراین بسیاری از سناریوها قابل ارزیابی نبودند.

## ممیزی امنیتی و اصلاح

### یافته تأییدشده

تقویم `scope=org` پیش‌تر برای superuser مجاز بود و رکوردهای تأییدشده را با شناسه، نام و تاریخ کارکنان برمی‌گرداند؛ درحالی‌که ماتریس مجوز، مشاهده رکورد فردی را برای مدیر سامانه مجاز نمی‌داند.

**اصلاح:** دسترسی اکنون نیازمند عضویت در Django group با نام `HR` و پروفایل کارمندی است و queryset به شرکت همان پروفایل محدود شده است. Cross-company HR scope در مدل فعلی وجود ندارد و مجاز نشده است. قرارداد API مستند شد.

**تست:** مدیر و superuser فاقد HR group پاسخ 403 می‌گیرند؛ HR گروهی فقط رکورد شرکت پروفایل خود را می‌بیند. آزمون API افزوده‌شده موفق است.

این نگاشت موقت نقش HR به Django Group جایگزین RBAC نهایی نیست و مدیریت/تاریخچه مجوز HR هنوز تکمیل نشده است.

### اسکن وابستگی و اسرار

- `npm audit`: پس از ارتقای `react-router-dom` به 7.18.x و Vite به 6.4.x، **۰ آسیب‌پذیری شناخته‌شده**.
- `pip-audit -r backend/requirements.txt`: **No known vulnerabilities found**.
- جست‌وجوی heuristic در فایل‌های tracked فقط مسیرهای کاندید را مشخص کرد و مقدار حساس در گزارش/خروجی درج نشد؛ اسکنر تخصصی Secret و بررسی Git history اجرا نشده‌اند: **NOT VERIFIED**.
- هیچ وابستگی Backend تغییر نکرد؛ ابزار `pip-audit` فقط در محیط توسعه نصب شد و به manifest پروژه افزوده نشد.

## آزمون، داده و عملیات

| مورد | وضعیت شواهد |
|---|---|
| Backend regression روی SQLite | ۱۲۵ موفق، ۰ ناموفق؛ هشدار محدودیت SQLite برای `nulls_distinct` باقی است. |
| Frontend unit | ۳۴ موفق، ۰ ناموفق. |
| TypeScript/Vite production build | موفق. |
| Django check و migration drift | موفق؛ `No changes detected`. |
| Migration از صفر روی SQLite آزمون | در اجرای suite انجام شد. |
| Migration/قید/هم‌زمانی روی PostgreSQL | NOT VERIFIED؛ PostgreSQL در دسترس نبود. |
| تست ورود، انقضای نشست، IDOR درخواست، پیوست، اعلان و گردش سهمیه | BLOCKED/NOT IMPLEMENTED؛ مسیرهای عملیاتی مربوطه وجود ندارند. |
| Backup/Restore واقعی، RPO/RTO، restart، worker/scheduler | NOT VERIFIED؛ ابزار/زیرساخت عملیاتی تعریف یا اجرا نشده است. |
| کارایی، بار هم‌زمان و E2E | NOT RUN. |
| Logging/Monitoring عملیاتی و correlation ID | NOT VERIFIED. |

## فایل‌ها، API، Migration

- اصلاح‌شده: `backend/leave/calendar_views.py`، `backend/leave/tests/test_calendar.py` و `docs/api/api-contract.md`.
- endpoint جدیدی ایجاد نشد؛ رفتار مجوز `GET /api/v1/calendar/events/?scope=org` محدود شد.
- Migration جدیدی لازم/ایجاد نشد.
- وابستگی‌های Frontend در `package.json` و lockfile به‌روزرسانی شدند.

## موانع و تصمیم‌ها

- احراز هویت عملیاتی، RBAC سازمانی جامع، scope چندشرکتی، API درخواست/دفترکل و پیوست امن ناقص‌اند.
- PostgreSQL، سرور، ذخیره‌سازی و ابزار Backup/Restore واقعی در دسترس/پیکربندی نبودند.
- راهنمای استقرار فعلی طراحی است، نه فرایند اثبات‌شده؛ Restore و rollback اجرا نشده‌اند.
- تصمیم‌های مربوط به نقش‌های HR، Bradford، retention، backup، RPO/RTO و زیرساخت در [ثبت تصمیم‌های سازمانی](./phase-09-11-organizational-decisions.md) فهرست شده‌اند.

## وضعیت نهایی فاز

**PARTIAL / NOT READY** — یک نقص مجوز تقویم اصلاح و regression-tested شد و اسکن وابستگی‌های اعلام‌شده پاک است؛ این شواهد برای اعلام نبود آسیب‌پذیری مهم در کل سامانه یا آمادگی Production کافی نیست.

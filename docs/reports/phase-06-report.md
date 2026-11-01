# گزارش فاز ۰۶ — تقویم و سیاست‌ها

## خلاصه اجرایی

فاز ۶ نسبت به نقطه بازیابی پیشرفت عملی داشته، اما **کامل یا آماده Production نیست**. تبدیل تاریخ شمسی/میلادی حفظ شده و لایه Backend برای تقویم سازمانی، تعطیلات، Work Pattern، نسخه سیاست، APIهای پایه و محاسبه متمرکز روزهای کاری اضافه شده است. محاسبه ثبت درخواست اکنون از سیاست مؤثر در تاریخ شروع استفاده می‌کند و مقدار روز کاری را در Backend باز‌محاسبه می‌کند.

با این حال، رابط مدیریت Work Pattern و Policy و مدیریت تعطیلات بازه‌ای به API جدید متصل نشده، ساعات مرخصی در Backend یکپارچه نشده، سال مرخصی مستقل/انتقال مانده کامل نیست، و دسترسی HR سازمانی هنوز نقش/Scope قابل مدیریت ندارد. در نتیجه شرط ورود به فاز ۷ برقرار نیست.

## قبل از این مرحله

- تبدیل stateless تاریخ شمسی/میلادی و منطق پایه شمسی، تعطیلات و سیاست موجود بود.
- Frontend تقویم شمسی و صفحه تعطیلات داشت؛ API عملیاتی Backend برای تقویم، Work Pattern و Policy وجود نداشت.
- تعطیلات پایه مدل `PublicHoliday` داشت اما مدل جدید تعطیلات چندروزه و APIهای مدیریت محدود نداشت.
- گزارش وضعیت مبنا در [گزارش بازیابی](./phase-06-recovery-report.md) ثبت شده است.

## پیاده‌سازی این مرحله

- افزودن مدل سایت، Work Pattern تاریخ‌دار و نسخه تغییرناپذیر Policy.
- افزودن CalendarHoliday بازه‌ای، scopeهای national/organization/company/site، غیرفعال‌سازی منطقی، تاریخچه تغییر و Audit.
- اتصال `LeaveRequest` به snapshot نسخه Policy.
- افزودن سرویس مرکزی محاسبه روز/دقیقه کاری با الگوی مؤثر و تعطیلات؛ درخواست جدید مقدار روز کاری را در Backend کنترل می‌کند.
- انتخاب Policy بر اساس تاریخ شروع درخواست، نه تاریخ ثبت؛ یک آزمون رگرسیون این رفتار را پوشش می‌دهد.
- افزودن API تقویم شخصی/تیمی/سازمانی، فهرست تعطیلات بازه‌ای، تخمین روز کاری، Work Pattern، Policy و تاریخچه‌های مدیریتی.
- حفظ API قدیمی تعطیلات و ثبت/ویرایش/غیرفعال‌سازی تاریخچه‌دار آن.
- اتصال تقویم UI در حالت HTTP به API تقویم/تعطیلات و تطبیق پاسخ تخمین با مقادیر رشته‌ای Backend. ورودی تعطیلی قدیمی دلیل غیرفعال‌سازی را می‌گیرد.
- آخرین patch در درخواست روزانه، خطای تخمین را آشکار می‌کند؛ Backend در زمان ثبت دوباره محاسبه می‌کند.

## فایل‌ها و Migrationها

- Backend: `backend/leave/models.py`, `calendar_services.py`, `calendar_views.py`, `services.py`, `admin_services.py`, `urls.py`.
- Migrationها: `0002_calendarholidayhistory_leavepolicyversion_and_more.py` و `0003_publicholiday_is_active_publicholiday_updated_at_and_more.py`.
- تست: `backend/leave/tests/test_calendar.py`.
- Frontend: `frontend/src/api/{contract,demo,http,types}.ts`, `frontend/src/pages/{CalendarPages,OrgPages,RequestsPages}.tsx`.
- قرارداد API: `docs/api/api-contract.md`.
- فایل‌های قبلی دست‌نخورده حذف یا بازنویسی نشده‌اند؛ Migration قبلی تغییر نکرده است.

## APIهای افزوده‌شده

تمام endpointهای داده‌دار به `IsAuthenticated` پیش‌فرض پروژه متکی‌اند. مدیریت و دسترسی سازمانی مدیریتی فعلاً به `is_superuser` محدود است؛ این نقش جایگزین RBAC چندشرکتی/HR نیست.

| Method | Endpoint | کارکرد / کنترل |
|---|---|---|
| GET | `/api/v1/calendar/events/` | بازه و scope؛ شخصی، گزارش‌های مستقیم در همان شرکت، یا سازمان فقط برای superuser |
| GET | `/api/v1/calendar/holidays/` | تعطیلات بازه‌ای قابل اعمال برای کارمند/شرکت/سایت |
| GET | `/api/v1/working-days/estimate` | محاسبه Backend برای کارمند خود یا انتخاب کارمند توسط superuser |
| GET/POST | `/api/v1/calendar/work-patterns/` | خواندن الگوهای مؤثر خود؛ ساخت الگو فقط برای superuser |
| GET/POST | `/api/v1/calendar/policies/` | خواندن Policy مؤثر خود؛ ساخت نسخه فقط برای superuser |
| GET/POST | `/api/v1/calendar/holidays/manage/` | فهرست/ایجاد تعطیلی بازه‌ای؛ فقط superuser |
| PATCH/DELETE | `/api/v1/calendar/holidays/manage/{id}/` | ویرایش یا غیرفعال‌سازی تاریخچه‌دار؛ حذف نیازمند دلیل |
| GET | `/api/v1/calendar/holidays/manage/{id}/history/` | تاریخچه تعطیلی؛ فقط superuser |
| GET | `/api/v1/admin/calendar/work-patterns/` | فهرست الگوها؛ فقط superuser |
| GET | `/api/v1/admin/calendar/policies/` | تاریخچه نسخه‌های Policy؛ فقط superuser |
| GET/POST/PATCH/DELETE | `/api/v1/holidays/` و `/api/v1/holidays/{id}/` | سازگاری API قدیمی تعطیلات؛ نوشتن فقط superuser و حذف منطقی |

تاریخ ورودی و ذخیره‌سازی در API عملیاتی میلادی ISO است؛ تبدیل نمایشی شمسی از لایه تاریخ موجود استفاده می‌کند. API تبدیل مستقل قبلی حفظ شده است.

## نتایج اعتبارسنجی

- `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py check`: موفق.
- `makemigrations --check --dry-run` با تنظیم تست: `No changes detected`.
- کل Django test suite: **124 تست موفق، 0 ناموفق**.
- Frontend: `npm run build` موفق (TypeScript و Vite).
- Frontend: `npm test`: **32 تست موفق، 0 ناموفق**.
- هشدار SQLite: قید یکتایی `nulls_distinct` مدل تعطیلی قدیمی در SQLite enforce نمی‌شود؛ PostgreSQL محیط هدف است. PostgreSQL در این محیط در دسترس نبود، پس اعتبارسنجی Migration روی PostgreSQL و تاریخچه اعمال Migration انجام نشده است.
- E2E مرورگر، تست PostgreSQL، concurrency واقعی و اتصال به سامانه هویت سازمانی اجرا نشده است.

## معیارهای پذیرش

| معیار | وضعیت | توضیح |
|---|---|---|
| نمایش/تبدیل شمسی و ذخیره استاندارد | PARTIAL | تبدیل موجود و UI شمسی هست؛ همه فرم‌ها/گزارش‌ها به قرارداد متمرکز متصل و E2E نشده‌اند. |
| سال مرخصی مستقل از سال تقویمی | PARTIAL | Policy نسخه‌دار افزوده شد؛ مرز سال مرخصی، منطقه زمانی قابل تنظیم، انتقال و انقضا کامل نیست. |
| تعطیلات چندسطحی، چندروزه و تاریخچه | PARTIAL | مدل/سرویس/API و آزمون backend موجود است؛ مدیریت API جدید در UI نیست و ثبت اثر روی محاسبات تأییدشده گزارش تحلیلی ندارد. |
| Work Pattern مؤثر | PARTIAL | مدل، اعتبارسنجی، API و محاسبه تست‌شده؛ صفحه مدیریت Frontend، شیفت متغیر و الگوی قرارداد/درصد اشتغال ندارد. |
| محاسبه مرکزی روز کاری | PARTIAL | سرویس مرکزی در تخمین و ثبت روزانه مصرف می‌شود؛ مسیر مرخصی ساعتی و همه مصرف‌کننده‌های قدیمی یکپارچه نیستند. |
| Policy نسخه‌بندی‌شده و snapshot | PARTIAL | API/سرویس و پیوند snapshot پیاده شده؛ UI ایجاد Policy و قواعد کامل سال/انتقال و تعدد policy در یک بازه موجود نیست. |
| تقویم شخصی/تیمی/سازمانی و کنترل Scope | PARTIAL | API و تست محدودیت مستقیم‌گزارش/سازمان وجود دارد؛ RBAC سازمانی/HR و Timeline مستقل کامل نیست. |
| Frontend به API عملیاتی | PARTIAL | تقویم و تعطیلات بازه‌ای در HTTP mode متصل‌اند؛ APIهای Work Pattern/Policy و مدیریت CalendarHoliday در UI مصرف نمی‌شوند؛ پیش‌فرض محصول همچنان Demo است. |
| تست‌های چندشرکتی و امنیت | PARTIAL | جداسازی تعطیلی شرکت، محرمانگی رویداد و منع مدیریت غیر superuser تست شده؛ ماتریس Permission کامل/سازمانی و PostgreSQL تست نشده‌اند. |

## تصمیم‌های سازمانی و موارد باقی‌مانده

- تقویم کاری واقعی هر شرکت/سایت/واحد، ساعت شیفت، روزهای تعطیل هفتگی و قرارداد پاره‌وقت باید تأیید شود.
- مرز سال مرخصی، منطقه زمانی، مبنای تخصیص، انتقال و انقضای مانده باید تصویب و پیاده‌سازی شود.
- منبع رسمی تعطیلات و تقسیم اختیارات ملی/هلدینگ/شرکت/سایت باید تعریف شود.
- نقش HR و مدیران مجاز در Backend با Organization Scope پایدار تعریف نشده؛ superuser-only صرفاً محدودکننده موقت است.
- UI مدیریت Policy، Work Pattern، تعطیلات چندروزه و تاریخچه‌ها باقی است.
- محاسبات ساعتی باید به Work Pattern/تعطیلات در Backend وصل شود؛ اعتبارسنجی فعلی Frontend مرجع نهایی نیست.

## دروازه فاز ۷

**BLOCKED** — با وجود سبز بودن تست‌های فعلی، همه معیارهای لازم فاز ۶ تکمیل نشده‌اند. فازهای ۷ و ۸ در این مرحله شروع یا فعال نشده‌اند.

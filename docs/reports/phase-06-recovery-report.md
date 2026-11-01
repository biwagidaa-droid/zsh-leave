# گزارش بازیابی فاز ۰۶ — وضعیت مخزن در ۱ نوامبر ۲۰۲۶

## ۱. وضعیت Git

- شاخه: `main`
- `HEAD`: `edf95b9dff6eca5c199380dc980eeb71cc84ab14` (`phase:`)
- `origin/main`: همان commit
- Working tree پیش از این گزارش: پاک؛ فایل Modified، Added یا Deleted ثبت‌نشده وجود نداشت.
- آخرین commit مورد بررسی: شامل ۹ فایل است: endpoint تاریخ، URL، تست API، قرارداد API، roadmap و گزارش‌های فاز ۶ تا ۸ و گزارش نهایی.
- هیچ Migration در commit قبلی اضافه نشده است.

تغییر این گزارش تنها فایل تازه این مرحله تا پیش از ادامه توسعه است. commit یا push انجام نشده است.

## ۲. آثار اجرای قبلی و نقطه توقف

### موجود پیش از اجرای قبلی

- منطق تبدیل تاریخ در `backend/zsh_core/jalali.py`، با بازه پشتیبانی محدود و تبدیل/اعتبارسنجی شمسی و میلادی.
- منطق خالص تعطیلات در `backend/zsh_core/holidays.py`.
- تخمین روز کاری در `backend/zsh_core/workdays.py` و محاسبه سهمیه/روز مرخصی در `backend/zsh_core/policy.py`.
- تنظیمات قابل اعتبارسنجی در `backend/zsh_core/settings_schema.py`.
- مدل‌های پایه `PublicHoliday`, `PublicHolidayHistory`, `SystemSetting` و `AuditEvent` در `backend/leave/models.py`؛ Migration موجود `0001_initial`.
- UI تقویم، تعطیلات و Timeline در `frontend/src/pages/CalendarPages.tsx` و API contract/client مربوط به آن‌ها؛ در وضعیت حاضر این APIهای backend پیاده نشده‌اند.
- `frontend/src/api/index.ts` به‌طور پیش‌فرض `demoApi` را انتخاب می‌کند.

### تغییر ثبت‌شده در اجرای قبلی

- endpoint بی‌حالت `GET /api/v1/calendar/convert-date/` در `backend/leave/views.py` و `backend/leave/urls.py`.
- پنج تست مربوط به endpoint در `backend/tests/test_api_base.py`.
- قرارداد endpoint در `docs/api/api-contract.md`.
- گزارش‌های فاز ۶، ۷، ۸ و گزارش نهایی؛ roadmap فازها.
- Migration، مدل جدید، سرویس تقویم سازمانی، API تعطیلات، API Work Pattern، API سیاست نسخه‌بندی‌شده و اتصال API تقویم در Frontend ایجاد نشده است.

### آخرین نقطه معتبر

- آخرین قابلیت پیاده‌سازی‌شده: تبدیل stateless تاریخ شمسی/میلادی در backend.
- آخرین commit/finalized point: `edf95b9`.
- آخرین فایل‌های تغییرکرده قابل اثبات از commit: فایل‌های ۹گانه فهرست‌شده در commit بالا؛ Git نگه‌دارنده ترتیب زمانی ویرایش فایل‌ها نیست، بنابراین «آخرین فایل ویرایش‌شده در میان آن‌ها» از شواهد قابل تعیین نیست.
- آخرین تست موفق این بازیابی: ۱۱۰ تست backend، ۳۲ تست frontend، build frontend، Django system check و وضعیت Migration.
- بخش در حال پیاده‌سازی هنگام توقف: ادامه فاز ۶ پس از date conversion؛ هیچ مدل/API اجرایی بعدی در tree فعلی وجود ندارد.
- ناسازگاری اصلی: رابط تقویم/تعطیلات/Timeline در Frontend به endpointهایی اشاره می‌کند که backend ندارد؛ در اتصال واقعی، این صفحات operational نیستند.

## ۳. وضعیت قابلیت‌های فاز ۶

| قابلیت | وضعیت | شواهد و ارزیابی |
|---|---|---|
| تبدیل تقویم شمسی/میلادی در backend | COMPLETE (محدوده تبدیل) | `zsh_core/jalali.py`, `leave.views.convert_calendar_date`; تست API در `tests/test_api_base.py` و پوشش بیشتر در `tests/test_jalali.py`. |
| بازه تبدیل تاریخ شمسی | PARTIAL | `MIN_YEAR`/`MAX_YEAR` عمداً محدود است؛ ورودی بیرون بازه رد می‌شود. پوشش کل بازه در تست unit انجام می‌شود، اما سازگاری برای همه سال‌های تاریخی/آینده فراتر از آن ادعا نمی‌شود. |
| ورودی تاریخ شمسی در رابط کاربر | PARTIAL | ابزارها و کنترل‌های شمسی Frontend موجودند؛ قابلیت جدید فقط API دارد و API مرجع در UI مصرف نمی‌شود. |
| ذخیره‌سازی میلادی استاندارد | PARTIAL | مدل درخواست از `DateField` استفاده می‌کند؛ مسیر عملیاتی ثبت درخواست/API وجود ندارد تا end-to-end اثبات شود. |
| سال مرخصی مستقل | PARTIAL | `zsh_core.policy.leave_year_of` و bounds از تقویم Jalali/Gregorian پشتیبانی می‌کنند؛ تنظیم منطقه زمانی/مرز سفارشی/سیاست versioned و اتصال به درخواست عملیاتی کامل نیست. |
| منطق تعطیلات و محدوده پایه | PARTIAL | `zsh_core.holidays` تاریخ‌های سالانه/یک‌باره و scope رشته‌ای را محاسبه می‌کند؛ مدل `PublicHoliday` ذخیره محدود دارد. API مدیریتی و scope واقعی هلدینگ/شرکت/سایت نداریم. |
| تاریخچه تغییر تعطیلات | PARTIAL | `PublicHolidayHistory` و سرویس `add_holiday`/`delete_holiday` create/delete را ثبت می‌کنند؛ update/disable و ارزیابی اثر بر محاسبات تأییدشده پیاده نیست. |
| Work Pattern | NOT IMPLEMENTED | مدل مؤثر تاریخ‌دار برای کارکنان/شرکت/سایت/دپارتمان وجود ندارد. قرارداد و برنامه کاری قابل‌ذخیره/استفاده موجود نیست. |
| محاسبه روز کاری مرکزی | PARTIAL | `estimate_working_days` و `count_leave_days` خالص و تست‌شده‌اند؛ سرویس مرکزی production که Work Pattern و تعطیلات سازمانی واقعی را resolve کند و همه بخش‌ها آن را مصرف کنند وجود ندارد. |
| سیاست قابل مدیریت | PARTIAL | `SystemSetting`, schema و `admin_services` اعتبارسنجی/ثبت حسابرسی دارند؛ endpoint مدیریتی/Scope سازمانی و ذخیره نسخه اعمال‌شده بر درخواست وجود ندارد. |
| نسخه‌بندی سیاست و snapshot تاریخی | NOT IMPLEMENTED | مدل PolicyVersion و ارجاع به نسخه در LeaveRequest وجود ندارد؛ تغییر تنظیم می‌تواند معنای تاریخی را تغییر دهد. |
| تقویم شخصی/تیمی/سازمانی و Timeline در Backend | NOT IMPLEMENTED | Frontend componentها وجود دارند، اما endpointهای `calendar/events`، دسترسی Scope و تست مجوز ندارند. |
| API تاریخ | COMPLETE | `GET /api/v1/calendar/convert-date/` با 400 برای ورودی نامعتبر و 200 برای ورودی معتبر؛ AllowAny فقط به دلیل stateless بودن و عدم دسترسی به داده سازمانی. |
| API تعطیلات/الگو/سیاست/تقویم | NOT IMPLEMENTED | در `backend/leave/urls.py` ثبت نشده‌اند. |
| تست تاریخ و منطق خالص تعطیلات/روز کاری | COMPLETE برای منطق خالص | `test_jalali.py`, `test_settings_holidays.py`, `test_workdays.py`, `test_policy.py` اجرا و سبز هستند. |
| تست API/مجوز چندشرکتی | BLOCKED | احراز هویت واقعی، Role/Scope سمت backend و endpointهای سازمانی فراهم نیستند. |

## ۴. وابستگی‌ها و تصمیم‌های باز

### موانع فنی

- Authentication واقعی و اعمال RBAC/Organization Scope در backend تکمیل نشده است؛ نقش‌های فرانت‌اند جایگزین مجوز backend نیستند.
- مدل پایه EmployeeProfile فقط Company/Department دارد؛ Site/Unit/Position و تاریخچه انتقال سازمانی operational نیست.
- endpointهای تقویم، درخواست، سیاست و تعطیلات backend وجود ندارند.
- Migration جاری فقط `leave.0001_initial` است و schema برای Work Pattern/Policy Version/API تقویم تکمیل نشده.
- اتصال Frontend در `VITE_DEMO_MODE=false` به backend فعلی، endpointهای تقویم و Holidays را پیدا نمی‌کند.

### تصمیم‌های سازمانی لازم

- روزهای کاری رسمی هر سایت/واحد و قواعد پاره‌وقت/شیفت.
- مرز و منطقه زمانی سال مرخصی و قواعد انتقال/انقضای مانده.
- منبع رسمی تعطیلات و scope ملی/هلدینگ/شرکت/سایت؛ تقویم رسمی نباید از داده نمونه ساخته شود.
- اولویت دقیق سیاست‌ها و مواردی که سیاست پایین‌دست مجاز به override آن است.

تا تعیین تکلیف این موارد، داده نمونه به‌عنوان سیاست واقعی و API سازمانی بدون Scope نباید فعال شود.

## ۵. آزمون‌های بازیابی (اجراشده در وضعیت فعلی)

- Backend: `python3 -m unittest discover -s tests -t .` در `backend/`: **110 Passed, 0 Failed, 0 Skipped**.
- Django: `manage.py check --settings=config.settings_test`: موفق، بدون هشدار.
- Migration: `showmigrations leave --settings=config.settings_test`: فقط `0001_initial` اعمال‌شده است.
- Frontend: `npm test` در `frontend/`: **32 Passed, 0 Failed, 0 Skipped**.
- Frontend build: `npm run build`: موفق؛ `tsc --noEmit` و Vite build موفق.
- PostgreSQL عملیاتی، E2E مرورگر، آزمون مجوز بین‌شرکتی و آزمون concurrency اجرا نشده‌اند.

## ۶. آخرین نقطه ادامه

ادامه اولیه پس از این گزارش، قابلیت‌های دامنه و API فاز ۶ را با احراز هویت پیش‌فرض DRF و محدودیت مدیریتی superuser پیاده‌سازی کرد. وضعیت و حدود آن در [گزارش فاز ۶](./phase-06-report.md) آمده است. تقویم/تعطیلات، Work Pattern و Policy هنوز کامل نیستند؛ فازهای ۷ و ۸ فعال نشده‌اند.

## ۷. به‌روزرسانی پس از ادامه اجرا (۱ نوامبر ۲۰۲۶)

- مدل‌ها، Migrationهای `0002` و `0003`، سرویس مرکزی روز کاری، نسخه Policy و APIهای پایه تقویم/تعطیلات/Work Pattern/Policy اضافه شده‌اند.
- در ثبت مرخصی روزانه، Policy بر اساس تاریخ شروع درخواست انتخاب می‌شود؛ تست regression به suite افزوده شد.
- وضعیت Git اکنون دارای تغییرات unstaged گزارش‌شده در اجرای جاری است؛ هیچ تغییر قبلی حذف نشده و commit/push انجام نشده است.
- کل suite بک‌اند با `config.settings_test`: 124 تست موفق. Frontend: 32 تست و build موفق. `makemigrations --check --dry-run`: بدون تغییر مدل باقی‌مانده.
- PostgreSQL اجرا نمی‌شود؛ `makemigrations` با تنظیم پیش‌فرض PostgreSQL نتوانست اتصال migration history را بررسی کند. آزمون suite با SQLite تنظیم تست انجام شد.
- آخرین نقطه معتبر: فاز ۶ **PARTIAL**؛ UI مدیریت Policy/Work Pattern، سال مرخصی/rollover، API مجوز HR سازمانی و مسیر ساعتی Backend باقی است. ورود به فاز ۷/۸ مجاز نیست.

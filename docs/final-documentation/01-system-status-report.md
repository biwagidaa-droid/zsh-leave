# گزارش وضعیت سامانه ZSH Leave

**مبنای ارزیابی:** کد فعلی `backend/` و `frontend/`، مهاجرت‌های ۰۰۰۱ تا ۰۰۱۱ و آزمون‌های همان مخزن. این گزارش ادعای اجرای سامانه در محیط عملیاتی ندارد.

## ۱. خلاصه مدیریتی

مخزن شامل یک برنامه وب React/TypeScript و API مبتنی بر Django REST Framework است. هویت با نشست Django و Cookie مدیریت می‌شود؛ نقش‌ها و دامنه‌های سازمانی در سمت سرور محاسبه می‌شوند. چرخه اصلی درخواست مرخصی، ثبت رویداد و دفترکل سهمیه در سرویس‌های تراکنشی وجود دارد. کد، آزمون‌های واحد و یکپارچگی و رابط‌های واقعی دارد؛ اما سامانه هنوز «آماده تولید» اثبات نشده است.

| موضوع | وضعیت مستند |
|---|---|
| رابط و API اصلی مرخصی | پیاده‌سازی‌شده؛ آزمون Django کامل با SQLite در این اجرا موفق |
| آزمون فرانت‌اند | پیاده‌سازی‌شده و آزموده‌شده: ۳۴ آزمون موفق |
| TypeScript و build تولیدی | آزموده‌شده: `npm run build` موفق |
| PostgreSQL، قفل هم‌زمانی و Trigger دفترکل | پیاده‌سازی‌شده؛ در این محیط آزموده‌نشده؛ ۳ آزمون PostgreSQL-only با SQLite رد شده‌اند |
| پایش Job، ایمیل، زمان‌بندی و هشدار | ناقص/پیاده‌سازی‌نشده؛ API فهرست Job خالی می‌دهد |
| استقرار، TLS واقعی، Backup/Restore و مانیتورینگ | مسدود به زیرساخت؛ فایل Compose، CI/CD و دستورالعمل اجرایی در مخزن یافت نشد |
| آمادگی تولید | **تأیید نشده**؛ ریسک‌های سند [۰۹](09-production-readiness-checklist.md) باید رفع و با شواهد بسته شوند |

## ۲. معماری و فناوری

- **Frontend:** React 18، TypeScript، React Router 7 و Vite 6؛ فایل‌های کاربردی در `frontend/src/`، صفحات در `frontend/src/pages/` و کلاینت API در `frontend/src/api/`.
- **Backend:** Django 5.2، Django REST Framework، `drf-spectacular` و PostgreSQL از طریق `psycopg`; منطق دامنه مستقل در `backend/zsh_core/` و لایه مدل/سرویس/API در `backend/leave/`.
- **قراردادهای API:** در مسیرهای Frontend/Backend فایل serializer مستقل DRF مشاهده نشد؛ شکل JSON عمدتاً با توابع view مانند `_payload`, `_employee_json` و `_balance_json` ساخته می‌شود.
- **قرارداد ارتباط:** مسیر پایه `/api/v1`; JSON و نشست Cookie. Swagger در `/api/v1/docs/` و schema در `/api/v1/schema/`.
- **زمان/زبان:** `fa-ir`, `Asia/Tehran`, `USE_TZ=True`; منطق تقویم شمسی در `zsh_core/jalali.py`.
- **ذخیره فایل:** `MEDIA_ROOT` در `backend/media`; فایل‌های پیوست درخواست مجاز: PDF، PNG، JPEG تا ۱۰ MiB.
- **پایگاه داده:** تنظیمات پایه PostgreSQL یا SQLite؛ `settings_test.py` به‌طور ثابت SQLite است. مهاجرت‌ها در `backend/leave/migrations/`.
- **استقرار:** `config.wsgi` و `config.asgi` وجود دارد و dependency مربوط به Gunicorn نصب‌پذیر است؛ اما فایل Docker، Compose، workflow استقرار یا سرویس worker در مخزن موجود نیست.

### ساختار داده مهم

`Company`، `OrganizationSite` و `Department` ساختار سازمانی‌اند؛ `EmployeeProfile` به `auth.User` متصل و شامل شرکت، سایت، واحد، مدیر، تاریخ اشتغال و کد پرسنلی است. `RoleAssignment` نقش‌های سازمانی را با محدوده تعریف می‌کند. `LeaveRequest` به کارمند، snapshot مدیر وقت ثبت، نوع و نسخه سیاست پیوند دارد. `LeaveRequestEvent`، `LeaveRequestComment` و `AuditEvent` تاریخچه append-only هستند. `LeaveEntitlement` projection سهمیه و `EntitlementEvent` دفترکل تغییرناپذیر است. `ContractPeriod`، `WorkPattern`، `LeavePolicyVersion`، دو مدل تعطیلات، `NotificationRead` و پیوست‌ها نیز در مدل‌ها تعریف شده‌اند.

مهاجرت‌های مهم شامل گردش‌کار (۰۰۰۵)، دفترکل و backfill (۰۰۰۶ و ۰۰۰۷)، محدودیت‌های تغییرناپذیری و projection (۰۰۰۸ و ۰۰۰۹)، اتصال فرانت‌اند (۰۰۱۰) و فایل پیوست (۰۰۱۱) است.

## ۳. ورود، نشست، CSRF و امنیت

- ورود با نام کاربری/گذرواژه Django؛ `POST /api/v1/auth/login`، خروج `POST /api/v1/auth/logout`، نشست جاری `GET /api/v1/auth/me` و تغییر گذرواژه `POST /api/v1/auth/password`.
- نشست حداکثر ۸ ساعت، `HttpOnly`، `SameSite=Lax` و در حالت `DEBUG=False` Cookie امن. CSRF در middleware فعال است؛ درخواست‌های تغییردهنده با `X-CSRFToken` ارسال می‌شوند.
- محدودیت نرخ پیش‌فرض DRF: ناشناس ۲۰، کاربر واردشده ۱۲۰ و ورود ۵ درخواست در دقیقه. آزمون ورود محدودشده در مجموعه backend موجود است.
- رمزهای جدید حداقل ۱۲ نویسه و Argon2 اولویت‌دارند. Production settings، کلید حداقل ۵۰ نویسه و `ZSH_ALLOWED_HOSTS` غیرخالی را الزام می‌کند.
- تنظیم production شامل HTTPS redirect و HSTS یک‌ساله است؛ TLS، reverse proxy، دامنه‌ها و گواهی واقعی در مخزن پیکربندی/آزموده نشده‌اند.
- `settings_dev.py`، `DEBUG=True` و `CORS_ALLOW_ALL_ORIGINS=True` دارد؛ نباید برای سرویس عمومی استفاده شود. `.env.example` قالب توسعه است، خودکار بارگذاری نمی‌شود و مقدار نمونه راز تولید نیست.
- سطح امنیتی: کنترل‌های session/CSRF/RBAC، حساس‌زدایی درخواست‌های محرمانه، محدودیت فایل، لاگ ممیزی و دفاع فرمول تزریقی در کد/آزمون وجود دارد. ارزیابی مستقل نفوذ، اسکن dependency/secret و آزمون production انجام نشده است.

## ۴. نقش و سلسله‌مراتب سازمانی

نقش‌های مؤثر: `employee` (کاربر فعال دارای EmployeeProfile با `is_employee=True`)، `manager` (کارمند دارای گزارش مستقیم)، `hr` (تخصیص فعال)، `admin` (تخصیص admin؛ superuser نیز در context به admin تبدیل می‌شود) و `exec`. تاریخ پایان استخدام به‌تنهایی نقش employee را در `authorization_context` غیرفعال نمی‌کند. محدوده‌های تخصیص: `global`, `company`, `site`, `department`, `employee`. HR باید محدوده سازمانی داشته باشد؛ Executive فقط محدوده تجمیعی شرکت/سایت/واحد دارد؛ admin سراسری است.

`scoped_leave_requests` درخواست‌های شخصی، درخواست‌های دارای snapshot مدیر مستقیم در همان شرکت و محدوده HR را برمی‌گرداند. مدیر جایگزین بعدی به درخواست قدیمی دسترسی مدیریتی خودکار نمی‌گیرد. `admin` به رکوردهای درخواست فردی دسترسی ندارد؛ بااین‌حال endpointهای `balances` و `entitlements` صریحاً admin را می‌پذیرند و `_employee_rows` برای او همه کارمندان را برمی‌گرداند؛ بنابراین API دسترسی فردی به سهمیه/مانده می‌دهد، حتی اگر رابط برای admin صفحه تراز را نشان ندهد. این تفاوت باید به‌عنوان ریسک/تصمیم مجوز بررسی شود. `exec` نیز scope مستقلی برای مانده فردی ندارد. در بعضی APIهای مدیریت، شرط نقش با `has_role("hr")` بررسی و سپس رکوردها با queryهای دامنه‌ای محدود می‌شوند؛ نقش منو/رابط جایگزین مجوز سرور نیست. جزئیات در [سند ۰۸](08-role-permission-matrix.md).

**محدودیت UI:** API مدیریت تخصیص نقش موجود است، اما React client و صفحه مدیریت نقش در UI یافت نشد. ساخت حساب تازه نیز صفحه/مسیر عمومی ندارد؛ ساخت Employee توسط HR/Admin حساب با گذرواژه غیرقابل‌استفاده می‌سازد و مسیر reset/admin provisioning در UI فعلی دیده نشد.

## ۵. گردش کار مرخصی و دفترکل

وضعیت‌های اصلی در کد: `PENDING`, `ESCALATED`, `APPROVED`, `REJECTED`, `CANCELLED`, `WITHDRAWAL_PENDING`. درخواست معمول با مدیر به `PENDING` می‌رود؛ بدون مدیر/با پارامتر غیبت مدیر، ارجاع می‌شود؛ HR یا نوع بدون نیاز به تأیید می‌تواند مستقیم تأییدشده ایجاد شود. تصمیم مدیر فقط برای snapshot مدیر، در محدوده همان شرکت و برای نوع غیرمحرمانه است. HR مجاز در scope می‌تواند تصمیم بگیرد. رد و رد لغو نیازمند دلیل است. لغو درخواست باز با `cancel` و درخواست لغو مرخصی تأییدشده با چرخه `withdraw` انجام می‌شود. اصلاحیه فقط برای `APPROVED`، یک اصلاح باز در هر زمان.

ثبت، تصمیم و تغییر سهمیه در تراکنش و با قفل ردیف پیاده‌سازی شده‌اند؛ `Idempotency-Key` از تکرار عملیات جلوگیری می‌کند. محاسبه روز کاری از `WorkPattern`، تعطیلات و نسخه مؤثر سیاست می‌آید؛ نبود تنظیم معتبر به خطای بسته منتهی می‌شود.

`EntitlementEvent` رویدادهای پایه، انتقال، اصلاح، رزرو، مصرف و برگشت را نگه می‌دارد. جمع projection با دفترکل مقایسه می‌شود؛ ناسازگاری در Balance به پاسخ `409 entitlement_reconciliation` می‌انجامد. ایجاد/تغییر projection خارج از سرویس دفترکل مسدود شده است. پیاده‌سازی PostgreSQL-specific trigger و هم‌زمانی وجود دارد، اما در SQLite اثبات نمی‌شود.

## ۶. اعلان، گزارش، داده و عملیات

- اعلان‌ها از رویدادهای درخواست ساخته شده، حداکثر ۲۰۰ مورد اخیر را می‌خوانند و read state در `NotificationRead` پایدار است. ایمیل یا سامانه Push پیاده‌سازی نشده است.
- `GET /api/v1/admin/jobs/` برای admin مجاز اما خروجی ثابت `[]` دارد. Job زمان‌بندی‌شده فعال در این API دیده نمی‌شود؛ API health/readiness فقط دسترس‌پذیری فرایند/DB را می‌سنجد، نه اجرای Job.
- گزارش‌های `absences`, `balances`, `trends`, `process-health`, `bradford` تعریف شده‌اند. گروه کوچک با `privacy.min_group_size` پنهان می‌شود. مسیر `bradford` در گزارش عمومی، سری خالی و یادداشت توضیحی برمی‌گرداند؛ تحلیل Bradford صفحه HR جداگانه دارد.
- خروجی‌های `CSV/XLSX` در منطق خالص آزمون دارند، اما عملیات Export در رابط API/Frontend فعلی یافت نشد.
- شرکت/واحد/کارمند و قرارداد در UI مدیریت‌اند؛ UI تنظیم سایت/تخصیص نقش یا بازیابی گذرواژه نیست.

## ۷. پوشش واقعی Frontend API

پیشوند همه مسیرهای جدول `/api/v1` است. این جدول از `frontend/src/api/contract.ts`, `http.ts` و `backend/leave/urls.py` تطبیق داده شده؛ وضعیت اتصال به معنای سازگاری همه رفتارهای کسب‌وکار نیست.

| عملیات Frontend | روش و endpoint | پیاده‌سازی Backend / نکته |
|---|---|---|
| `login`, `logout`, `me`, `changePassword` | POST `/auth/login`, POST `/auth/logout`, GET `/auth/me`, POST `/auth/password` | موجود؛ Session/CSRF |
| `listTypes`, `saveType` | GET `/leave-types/`, POST `/leave-types/`, PATCH `/leave-types/{id}/` | موجود؛ HR/admin مدیریت، کارمند نوع‌های فعال و قابل درخواست |
| `listRequests`, `getRequest`, `createRequest`, `updateRequest` | GET/POST `/leave-requests/`, GET/PATCH `/leave-requests/{id}/` | موجود؛ scope شخصی/تیم/HR؛ شناسه نامجاز 404 |
| `actRequest` | POST `/leave-requests/{id}/{action}` | موجود؛ actionهای `approve`, `reject`, `cancel`, `withdraw`, `approve_withdraw`, `reject_withdraw`, `hr_cancel`, `amend`؛ `amend` همچنین route اختصاصی دارد |
| `listComments`, `addComment` | GET/POST `/leave-requests/{id}/comments/` | موجود؛ محرمانه فقط HR؛ comment append-only |
| `listAttachments`, `addAttachment` | GET/POST `/leave-requests/{id}/attachments/` | موجود؛ ۱–۱۰ MiB، PDF/PNG/JPEG و امضای محتوایی؛ دانلود از لینک همان پاسخ |
| `balances` | GET `/balances/?year=…&employee=…` | موجود؛ کارمند/مدیر/HR محدود به queryset خود؛ admin با شناسه صریح می‌تواند مانده فردی ببیند؛ exec بدون EmployeeProfile دسترسی کاربردی ندارد |
| `entitlements`, `adjustEntitlement` | GET `/entitlements/?year=…`, POST `/entitlements/{id}/adjust` | فهرست موجود؛ adjustment در view تعریف شده اما در probe ایزوله برای HR دامنه‌دار و admin، روی entitlement معتبر 404 داد؛ عملیات اصلاح سهمیه تا رفع/آزمون مجدد قابل اتکا نیست |
| `importEntitlements` | POST `/entitlements/import/?dry_run=0|1` | موجود؛ CSV؛ dry-run؛ commit فقط در صورت صفر سطر ردشده |
| `recordAbsence` | POST `/hr/absences/` | موجود؛ HR دامنه‌دار؛ ثبت و تأیید در عملیات تراکنشی |
| `calendar` | GET `/calendar/events/?from=…&to=…&scope=me|team|org` | موجود؛ دامنه‌های شخصی/مدیر/HR؛ برچسب خنثی برای درخواست‌های همکار |
| `calendarHolidays` | GET `/calendar/holidays/?from=…&to=…` | موجود؛ کارمند دارای پروفایل یا admin؛ تعطیلی حوزه کارمند |
| `holidays`, `saveHoliday`, `deleteHoliday` | GET/POST/PATCH/DELETE `/holidays/` و `/holidays/{id}/` | موجود؛ CRUD تعطیلات قدیمی شمسی، مدیریت فقط admin؛ حذف به‌صورت غیرفعال‌سازی |
| `notifications`, `readNotification` | GET `/notifications/`, POST `/notifications/{id}/read` | موجود؛ فقط رویدادهای قابل مشاهده کاربر |
| `employees`, `saveEmployee` | GET/POST `/employees/`, PATCH `/employees/{id}/` | موجود؛ خواندن دامنه‌ای، تغییر HR/admin؛ مدیر فهرست مستقیم محدود |
| `companies`, `saveCompany` | GET/POST `/companies/`, PATCH `/companies/{id}/` | موجود؛ تغییر فقط admin |
| `departments`, `saveDepartment` | GET/POST `/departments/`, PATCH `/departments/{id}/` | موجود؛ تغییر فقط admin (خواندن برای scope مجاز) |
| `contracts`, `saveContract` | GET/POST `/employees/{id}/contract-periods/` | موجود؛ HR در scope یا admin |
| `coverage` | GET `/coverage/?from=…&to=…` | موجود؛ manager/HR/admin؛ بازه حداکثر ۹۳ روز؛ manager تیم مستقیم |
| `reports` | GET `/reports/{kind}` | موجود؛ HR/exec؛ aggregation و حداقل گروه؛ Bradford عمومی خالی |
| `settings`, `saveSetting` | GET/POST `/admin/settings/` | موجود؛ فقط admin؛ ذخیره با دلیل و اعتبارسنجی schema |
| `jobs` | GET `/api/v1/admin/jobs/` | route موجود؛ فعلاً همیشه لیست خالی |
| `audit` | GET `/audit/events/` | موجود؛ admin همه audit تا ۵۰۰، HR رخدادهای درخواست scope خودش |
| `health` | GET `/api/v1/ready/` | موجود؛ client از آن `live=true` و `lastJob=null` مشتق می‌کند؛ health مجزای backend هم `/api/v1/health/` است |
| `estimate` | GET `/working-days/estimate?employee=…&start=…&end=…` | موجود؛ تاریخ/کارمند مجاز؛ حداکثر ۹۳ روز و خطای تنظیم تقویم |
| `clientPolicy` | GET `/policy/client` | موجود؛ فقط کاربر دارای EmployeeProfile؛ در حال حاضر `hourlyLeaveEnabled=false` |
| `bradfordNotes`, `saveBradfordNote` | GET/POST `/hr/bradford-notes/` | موجود؛ HR/admin؛ HR scope فهرست را محدود می‌کند |
| عملیات تبدیل تاریخ | GET `/calendar/convert-date/?calendar=…&date=…` | route Backend موجود؛ در `Api` رابط معمولی Frontend متدی ندارد |
| مدیریت نقش، الگوی کار، سیاست، تاریخچه تعطیلات و رویداد درخواست | مسیرهای `/admin/role-assignments/`, `/calendar/work-patterns/`, `/calendar/policies/`, `/admin/calendar/...`, `/leave-requests/{id}/events/` و `/calendar/holidays/manage/...` | backend route موجود؛ برای عملیات/بخش‌هایی از این مسیرها متد API یا صفحه متناظر در رابط معمولی یافت نشد |

**اختلاف قابل اقدام:** فرم Frontend مسیر ساعتی و فیلدهایی مانند `durationKind`, `startTime`, `durationMinutes` می‌سازد؛ `clientPolicy` فعلی ساعتی را خاموش می‌کند و serializer درخواست Backend این فیلدها را نمی‌پذیرد. بنابراین ساعتی را قابلیت قابل استفاده عملیاتی معرفی نمی‌کنیم؛ وضعیت آن نیمه‌پیاده‌سازی‌شده است.

## ۸. پوشش UI به تفکیک نقش

Router و منو در `frontend/src/App.tsx` و `components/Layout.tsx` کنترل ظاهری دارند. مجوز واقعی باید از API و ماتریس سند ۰۸ سنجیده شود.

| نقش | صفحات/اجزای واقعی قابل مشاهده | عملیات قابل مشاهده |
|---|---|---|
| همه کاربران واردشده | داشبورد، اعلان‌ها، پروفایل/تغییر رمز، تقویم، Timeline، تعطیلات | مشاهده نشست و اطلاعات پایه؛ مسیر تقویم با مجوز API |
| کارمند | درخواست‌ها، درخواست جدید، جزئیات، مانده | ثبت/مشاهده درخواست، لغو باز، درخواست لغو/اصلاح برای تأییدشده، نظر/پیوست غیرمحرمانه |
| مدیر مستقیم | درخواست‌ها، جزئیات، کارکنان، مانده، پوشش تیم | مشاهده گزارش مستقیم؛ approve/reject واجد شرایط؛ Balance/Coverage محدود |
| HR | درخواست‌ها، ثبت درخواست، غیبت، سهمیه، ورود گروهی، Bradford، قرارداد، انواع مرخصی، گزارش، کارکنان، ساختار، تعطیلات، audit | عملیات HR در scope؛ تنظیمات سامانه در UI برای HR نیست |
| مدیر سامانه | انواع مرخصی، کارکنان، ساختار سازمانی، تعطیلات، تنظیمات، Jobs/سلامت، audit | تنظیم سامانه/سازمان؛ صفحه مدیریت نقش در UI وجود ندارد؛ درخواست فردی را نمی‌بیند، اما API تراز/entitlement فردی را می‌پذیرد |
| Executive | مانده و گزارش‌ها | API گزارش تجمیعی بر اساس محدوده؛ داشبورد Executive/KPI مستقل یا صفحه مقایسه شرکت در UI دیده نشد |

## ۹. وضعیت آزمون، نقص و بدهی فنی

اجرای مشاهده‌شده در این workspace:

- `cd frontend && npm test`: **۳۴ موفق، صفر ناموفق**.
- `cd frontend && npm run build`: **موفق**؛ `tsc --noEmit` و Vite build.
- `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test`: **۱۷۶ مورد اجرا، ۱۷۳ موفق و ۳ skipped**؛ SQLite هشدار پشتیبانی‌نکردن constraint دارای `nulls_distinct`.
- `cd backend && python3 -m unittest discover -s tests -t .`: **ناموفق: ۱۳۶ آزمون، ۲۴ خطا**؛ بین علت‌های مشاهده‌شده، اجرای مجموعه Django با دیتابیس SQLite موجود/قدیمی است که ستون `site_id` ندارد. برای آزمون کامل Django از Test runner با `settings_test` استفاده شود.
- اجرای `python3 manage.py test` از ریشه نامعتبر است؛ `manage.py` داخل `backend/` است. `manage.py` پیش‌فرض `config.settings` را تنظیم می‌کند، اما چنین ماژول settings در مخزن نیست؛ باید `DJANGO_SETTINGS_MODULE` صریح باشد.
- PostgreSQL-specific concurrency/trigger tests در SQLite رد شده‌اند؛ این اجرا PostgreSQL را تأیید نمی‌کند.

شواهد، شکاف‌ها و آزمون‌های پیشنهادی در [سند ۰۲](02-complete-testing-manual.md) ثبت شده‌اند.

### نقص‌ها/ریسک‌های مشاهده‌شده

1. **ساعتی:** فرانت‌اند منطق فرم دارد، API پایه امکان/پذیرش ندارد و policy hardcoded disabled است.
2. **مدیریت نقش:** endpoint وجود دارد ولی UI/Api client متناسب نیست؛ اعطای دسترسی از UI انجام‌پذیر نیست.
3. **Job/اعلان بیرونی:** jobs خالی، email provider/ارسال ایمیل و scheduler وجود ندارد؛ مسیرهای auto-cancel و notify نباید به‌عنوان خودکار فعال فرض شوند.
4. **تنظیمات اجرای توسعه:** `settings_dev` از `ZSH_USE_SQLITE` برای override استفاده می‌کند، درحالی‌که `.env.example` `ZSH_DB_ENGINE` دارد؛ سازگاری عملیاتی تضمین نشده است.
5. **پیکربندی entrypoint:** `manage.py`, `asgi.py`, `wsgi.py` به `config.settings` پیش‌فرض اشاره می‌کنند؛ این فایل وجود ندارد.
6. **اعتماد به SQLite:** برخی قیدها/triggerهای DB و تضمین هم‌زمانی PostgreSQL در SQLite بازنمایی نمی‌شوند.
7. **بهره‌برداری:** فقدان فایل deploy، migration rollout، backup/restore، لاگ متمرکز، monitoring و runbook مستند در repository.
8. **راهکارهای ناقص UI/API:** تخصیص نقش، سیاست/WorkPattern کامل، export، فرایند کاربر جدید و reset رمز به‌عنوان UI قابل استفاده پیدا نشد.
9. **ناهمخوانی نقش/تراز:** UI تراز برای `exec` route دارد ولی API به EmployeeProfile نیازمند است و برای exec بدون پروفایل خطا می‌دهد؛ در مقابل admin در API تراز/entitlement فردی را می‌خواند/اصلاح می‌کند، با وجود نبود آن صفحه در UI. سیاست مورد انتظار باید از مالک داده تأیید شود.
10. **اصلاح دستی سهمیه:** درخواست معتبر به endpoint adjustment برای هر دو HR دامنه‌دار و admin در DB تستی disposable، 404 برگشت؛ `entitlements` list برای HR همان fixture 200 بود. این بررسی مستقل، آزمون رسمی suite نیست و مسیر اصلاح را تا رفع و آزمون مجدد مسدود می‌کند.

## ۱۰. ارزیابی آمادگی تولید

**نتیجه: آماده‌بودن برای تولید تأیید نشده است.** عبور build و آزمون Django با SQLite کافی نیست. شروط آزادسازی شامل آزمون PostgreSQL و migrationها، بررسی session/CSRF/TLS پشت proxy، آزمون تمام مجوزها و محرمانگی، فراهم‌کردن provisioning امن کاربران، backup و restore آزمایش‌شده، پایش و پاسخ حادثه و تعیین تصمیم‌های محصول درباره hourly/Jobهاست. برای معیار پذیرش قابل اندازه‌گیری به [چک‌لیست سند ۰۹](09-production-readiness-checklist.md) رجوع شود.

# راهنمای آزمون کامل و قابل تکرار

## ۱. پیش‌نیاز و دامنه اعتبار

- Python سازگار با dependencyهای `backend/requirements.txt` و Node/npm سازگار با `frontend/package-lock.json`.
- در اجرای مرجع این سند Python 3.14 و dependencyهای نصب‌شده و `frontend/node_modules` موجود بودند. PostgreSQL در این اجرای آزمون تأیید نشد.
- دستورات از ریشه repository آغاز می‌شوند. تنظیمات تست Django عمداً SQLite است؛ آزمون واقعی PostgreSQL نیازمند سرویس PostgreSQL مجزا است.
- هیچ حساب/seed استاندارد در کد مخزن پیدا نشد. برای آزمون دستی API، کاربر فعال، `EmployeeProfile`، شرکت، مدیر و RoleAssignment باید در دیتابیس disposable توسط مسئول مجاز آماده شوند. از داده واقعی کارمند استفاده نکنید.
- `.env.example` به‌خودی‌خود توسط Django بارگذاری نمی‌شود. از کپی آن به عنوان secret تولید استفاده نکنید. `config.settings` بر اساس `ZSH_ENV` تنظیمات را انتخاب می‌کند (پیش‌فرض development)؛ برای تست، module را صریح تعیین کنید.

## ۲. نصب و راه‌اندازی محلی

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

تنظیمات توسعه:

```bash
cd backend
ZSH_USE_SQLITE=1 DJANGO_SETTINGS_MODULE=config.settings_dev python3 manage.py migrate
ZSH_USE_SQLITE=1 DJANGO_SETTINGS_MODULE=config.settings_dev python3 manage.py runserver
```

این فرمان DB `backend/db.sqlite3` را به‌کار می‌برد. برای آزمون، `settings_test.py` دیتابیس SQLite با نام `backend/test.sqlite3` را تعیین می‌کند (Django test runner معمولاً DB تست موقت می‌سازد). `config.settings.py` وجود دارد و پیش‌فرض آن development است؛ همیشه برای آزمون settings تست را صریح انتخاب کنید.

برای اجرای رابط، در ترمینال جدا:

```bash
cd frontend
npm run dev
```

`frontend/src/api/http.ts` مسیر نسبی `/api/v1` می‌فرستد و `frontend/vite.config.ts` در حالت توسعه همین مسیر را به `http://127.0.0.1:8000` proxy می‌کند.

## ۳. فرمان‌های آزمون تأییدشده و نتایج مشاهده‌شده

| هدف | فرمان | نتیجه اجرای این گزارش |
|---|---|---|
| کل آزمون‌های Django و منطق خالص متصل به آن | `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test` | **۱۷۶ مورد اجرا؛ ۱۷۳ موفق، ۳ skipped، صفر ناموفق**؛ اجرا با SQLite؛ هشدار constraint `nulls_distinct` |
| آزمون‌های UI logic | `cd frontend && npm test` | **۳۴ موفق، صفر ناموفق** |
| type-check و build عملیاتی Frontend | `cd frontend && npm run build` | **موفق**؛ `tsc --noEmit` + `vite build` |
| بررسی پیکربندی Django | `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py check` | **موفق؛ ۰ مشکل** |
| بررسی اختلاف migration مدل/فایل | `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py makemigrations --check --dry-run` | **موفق؛ No changes detected** |
| اجرای `python3 manage.py test` از ریشه | از ریشه | نامعتبر چون `manage.py` در `backend/` است؛ `config.settings` وجود دارد و به‌صورت پیش‌فرض development را انتخاب می‌کند، پس در backend نیز برای تست settings را صریح کنید |

برای اجرای تکرارپذیر یک کلاس:

```bash
cd backend
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test leave.tests.test_workflow_api.LeaveWorkflowApiTests
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test leave.tests.test_entitlement_ledger.EntitlementLedgerTests
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test leave.tests.test_frontend_api.FrontendApiTests
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test tests.test_authentication.AuthenticationApiTests
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test tests.test_rbac.RBACApiTests
```

کلاس‌ها/ماژول‌ها در source test وجود دارند. فرمان‌های انتخابی بالا در این نوبت جداگانه اجرا نشده‌اند؛ موفقیت اجرای کل suite جایگزین ثبت خروجی مستقل آنها نیست.

## ۴. آزمون‌های موجود و پوشش شناخته‌شده

| حوزه | فایل/کلاس‌های واقعی | سناریوهای کدشده |
|---|---|---|
| پایه/سلامت/تقویم | `tests.test_api_base`، `tests.test_jalali` | health/readiness، تبدیل/اعتبار تاریخ شمسی، مرز کبیسه |
| احراز هویت | `tests.test_authentication.AuthenticationApiTests` | CSRF، نشست، چرخش نشست، ورود نامعتبر و rate-limit، logout، رمز جدید، metadata نقش |
| RBAC | `tests.test_rbac.RBACPolicyTests` و `RBACApiTests` | scope شرکت/سایت/واحد، جلوگیری از عبور بین شرکت، snapshot مدیر، اطلاعات محرمانه، IDOR، جلوگیری از self-escalation |
| API UI | `leave.tests.test_frontend_api.FrontendApiTests` | تطبیق مسیر کلاینت، صفحات HR، اعلان خوانده‌شده، پیوست، settings/health |
| گردش کار | `leave.tests.test_workflow_api.LeaveWorkflowApiTests` | lifecycle، replay idempotency، scope، گذار وضعیت، تصمیم/comment محرمانه |
| سرویس مجاز | `leave.tests.test_authorized_services.AuthorizedLeaveServiceTests` | نقش از caller پذیرفته نمی‌شود، selector دامنه‌ای، snapshot مدیر، تصمیم محرمانه |
| دفترکل | `leave.tests.test_entitlement_ledger.EntitlementLedgerTests` | رزرو، approve، reject، برگشت، انتقال/انقضا، reconciliation، قفل projection، درخواست چندساله |
| PostgreSQL | `PostgreSQLEntitlementConcurrencyTests` | دو رزرو موازی، approve موازی، trigger تغییرناپذیری؛ فقط در vendor PostgreSQL |
| تقویم و policy | `leave.tests.test_calendar` | اولویت/نسخه مؤثر، تعطیلی چندروزه، fail-closed، سیاست و API تقویم |
| خروجی/ورود داده | `tests.test_exports_imports_reports` | CSV/XLSX، formula injection، خطاهای CSV، حد گروه و Bradford |
| UI logic | `frontend/tests/*.test.ts` (۷ فایل) | حالت demo، deadline، Bradford، chart، مرخصی ساعتی client، اعلان |

## ۵. روش سناریوهای API دستی

برای اجرای درخواست‌ها، از URL محلی، کاربر آزمایشی و Cookie/CSRF خودتان استفاده کنید. مقدار `<...>` placeholder است؛ مقدار واقعی یا secret در مستندات درج نشده است.

```bash
BASE=http://127.0.0.1:8000
# CSRF cookie را از GET عمومی/ورود بگیرید؛ endpoint auth/me برای ناشناس 401 می‌دهد.
curl -i -c /tmp/zsh-cookies "$BASE/api/v1/auth/me"
CSRF=$(awk '$6=="csrftoken"{print $7}' /tmp/zsh-cookies)
curl -i -b /tmp/zsh-cookies -c /tmp/zsh-cookies \
  -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF" \
  -d '{"username":"<test-user>","password":"<test-password>"}' \
  "$BASE/api/v1/auth/login"
```

درخواست‌های POST/PATCH/DELETE بعدی نیز Cookie نشست و `X-CSRFToken` لازم دارند. ورود، به‌طور معمول Cookie جدید/نشست چرخیده می‌دهد؛ پس Cookie jar را نگه دارید. برای عملیات گردش کار، `Idempotency-Key: <unique-test-key>` بفرستید. نمونه بدنه JSON را با `curl -X POST ... -d '<JSON>'` ارسال کنید. دستور عمومی به‌تنهایی fixture ایجاد نمی‌کند. Vite در `frontend/vite.config.ts` درخواست `/api` را به `http://127.0.0.1:8000` proxy می‌کند.

## ۶. سناریوهای پذیرش

هر سناریوی زیر برای اجرای دستی به حساب‌ها و رکوردهای مصنوعی نیاز دارد. ستون «تغییر داده» اثر مورد انتظار در صورت اجرای موفق است؛ این بخش، ادعای اجرای سناریو در این نوبت نیست. Cleanup فقط روی دیتابیس disposable انجام شود؛ تاریخچه append-only را با حذف مستقیم پاک نکنید.

### احراز هویت و مجوز

| ID / هدف | نقش، پیش‌شرط و داده آزمون | گام و درخواست دقیق | پاسخ/تغییر داده مورد انتظار | معیار Pass/Fail و پاک‌سازی |
|---|---|---|---|---|
| AUTH-01 ورود معتبر | کاربر فعال با رمز آزمایشی | ابتدا GET `/api/v1/auth/me` برای CSRF؛ سپس POST `/api/v1/auth/login` با `{"username":"<u>","password":"<p>"}` | 200، `roles` و metadata؛ نشست احراز‌شده و رویداد audit ورود | Pass اگر نشست rotation و نقش فعلی بازتاب یابد؛ logout کنید |
| AUTH-02 ورود نامعتبر/کاربر غیرفعال | ناشناس؛ credential نادرست و سپس کاربر غیرفعال | POST همان login؛ برای فعال‌نبودن از fixture غیرفعال | 401 با پیام عمومی؛ عدم نشست؛ رویداد failed ثبت می‌شود | Pass اگر جزئیات حساب فاش نشود؛ fixture را حذف/غیرفعال نگه دارید |
| AUTH-03 CSRF و logout | نشست مجاز و jar cookie | POST logout یک بار بدون CSRF و سپس با CSRF | اول 403 و نشست باقی؛ دوم 204 و نشست نامعتبر | Pass با دو حالت؛ خروج کنید |
| AUTH-04 رمز عبور | کاربر واردشده | `POST /api/v1/auth/password` بدنه `{"current":"<old>","next":"<new-valid>"}`؛ یک بار با current غلط و یک بار درست | غلط: 400؛ درست: 204، نشست حفظ و AuditEvent تغییر رمز | Pass اگر رمز جدید طبق validator پذیرفته و قبلی رد شود؛ رمز آزمایشی را طبق رویه محیط حذف کنید |
| AUTH-05 rate limit | ناشناس، IP تست، endpoint ورود | حداقل ۶ POST login در بازه نرخ (auth_login=5/min) | پس از سهمیه پاسخ 429 | Pass اگر محدودیت اعمال شود؛ برای تکرار به پنجره جدید صبر کنید |
| RBAC-01 مالکیت و IDOR | دو کارمند شرکت‌های A/B؛ یک درخواست A؛ session کارمند B | GET `/api/v1/leave-requests/<id-A>/` و GET `/api/v1/working-days/estimate?employee=<employee-A>&start=2026-11-02&end=2026-11-02` | 404 بدون افشای وجود؛ هیچ تغییر DB | Pass اگر B رکورد A یا وجود آن را نبیند؛ fixtureها را پاک‌سازی محیطی کنید |
| RBAC-02 scope HR | HR شرکت A، کارمند/درخواست در A و B | GET `/api/v1/employees/` و `/api/v1/leave-requests/`؛ سپس درخواست مشخص B | فقط A؛ B نامرئی/404؛ بدون تغییر | Pass اگر scope سایت/واحد نیز به کل شرکت گسترش نیابد |
| RBAC-03 مدیر مستقیم | مدیر snapshot درخواست، مدیر جدید بعد از تغییر manager، مدیر شرکت دیگر | GET درخواست با هر سه session و POST action از مدیر جدید | snapshot سابق مجاز در scope؛ مدیر جدید/دیگر شرکت 404 یا 403؛ حالت/ledger تغییر نمی‌کند | Pass اگر مسیر تصمیم با `can_decide_leave_request` همخوان باشد |
| RBAC-04 نقش محرمانه | HR هم‌دامنه، مدیر مستقیم، کارمند مالک، admin، exec؛ درخواست با نوع confidential | GET جزئیات، comments، attachments و تقویم؛ ارسال اقدام approve به‌عنوان manager | مدیر/کارمند غیرمجاز: نوع/دلیل خنثی/پنهان، محتوای فرعی 403؛ تصمیم مدیر 403؛ HR دامنه‌دار جزئیات می‌بیند | Pass اگر Canary در پاسخ نقش‌های غیرمجاز ظاهر نشود؛ فایل‌های آزمون را حذف/محدود کنید |
| RBAC-05 تخصیص نقش | admin و کاربر هدف غیرخود؛ scope معتبر و نامعتبر | POST `/api/v1/admin/role-assignments/` با `{"userId":<id>,"role":"hr","scope":"company","companyId":<id>}`؛ سپس DELETE `/api/v1/admin/role-assignments/<assignmentId>/` | 201؛ AuditEvent؛ بعد revoke 204 و نقش بی‌درنگ حذف؛ self-grant 400 | Pass اگر cross-company/نقش نامعتبر رد و self escalation ناممکن باشد؛ revoke تخصیص آزمایشی |

### چرخه مرخصی و سهمیه

| ID / هدف | نقش، پیش‌شرط و داده آزمون | گام و درخواست دقیق | پاسخ/تغییر داده مورد انتظار | معیار Pass/Fail و پاک‌سازی |
|---|---|---|---|---|
| LEAVE-01 ثبت معتبر | کارمند فعال، مدیر، policy/work pattern مؤثر، نوع requestable، entitlements در صورت مشمول‌بودن | POST `/api/v1/leave-requests/` با `{"leaveTypeKey":"<key>","start":"<YYYY-MM-DD>","end":"<YYYY-MM-DD>","reason":"<test>","replacementId":null,"workingDays":"<calculated>"}` و `Idempotency-Key` یکتا | 201؛ status معمولاً `PENDING`; Request + Event/Audit و رزرو دفترکل برای نوع مشمول | Pass اگر محاسبه server با تقویم برابر باشد؛ در دیتابیس آزمون با workflow مجاز ببندید |
| LEAVE-02 ورودی نامعتبر/مرزی | کارمند؛ تاریخ نامعتبر، start>end، روز<=0، note خالی، طول >۹۳ روز برای estimate | POST بالا با داده نامعتبر؛ GET `/api/v1/working-days/estimate?employee=&start=2026-11-02&end=2027-03-01` | 400/422 یا 409 برای تقویم؛ Request ایجاد نشود | Pass اگر هیچ رزرو/event ایجاد نشود؛ هیچ پاک‌سازی داده‌ای لازم نیست |
| LEAVE-03 overlap و replay | درخواست باز از همان کارمند در همان بازه | POST یک درخواست هم‌پوشان با کلید جدید؛ سپس replay درخواست موفق با همان کلید و payload یکسان | overlap: 409؛ replay: همان resource، نه رکورد دوم | Pass اگر درخواست/رزرو تکراری ثبت نشود |
| LEAVE-04 مجوز مدیر و تصمیم | `PENDING` غیرمحرمانه با manager snapshot؛ مدیر و کارمند جدا | POST `/api/v1/leave-requests/<id>/approve` با `{"reason":""}`؛ reject با `{"reason":"<علت آزمون>"}` در fixture جدا | مدیر صحیح approve: status `APPROVED`; reject: `REJECTED` و دلیل لازم؛ Event/Audit و ledger انتقال اتمی | Pass اگر کارمند approve و مدیر غیرمجاز رد شوند؛ برای هر مسیر fixture مستقل |
| LEAVE-05 ارجاع/ردشده | درخواست `ESCALATED` و HR در scope | درخواست approve توسط مدیر و سپس HR در fixture جدا | مدیر 403؛ HR به `APPROVED` می‌رساند؛ یک تصمیم/رویداد | Pass اگر ارجاع فقط HR تصمیم بگیرد؛ داده تست را با event مسیر معتبر ببندید |
| LEAVE-06 لغو و لغو پس از تأیید | درخواست باز مالک؛ درخواست Approved جدا؛ تصمیم‌گیر برای withdrawal | POST `/cancel` روی باز؛ POST `/withdraw` روی Approved؛ سپس تصمیم `/approve_withdraw` یا `/reject_withdraw` | باز→`CANCELLED`; Approved→`WITHDRAWAL_PENDING`; approve withdrawal→`CANCELLED` و برگشت مصرف؛ reject→`APPROVED` | Pass اگر هر اثر دفترکل یک‌بار و اتمیک باشد |
| LEAVE-07 اصلاح و رقابت اصلاحیه | درخواست Approved، مالک/HR، یک اصلاح فعال | POST `/amend` با `{"start":"<date>","end":"<date>","reason":"<test>"}`؛ اصلاح دوم قبل از تصمیم؛ سپس تصمیم اصلاحیه | اول 201 و رکورد `supersedes`; دوم 409؛ تأیید اصلاح، original=`CANCELLED` و اصلاحیه=`APPROVED`؛ رد اصلاح اصل را حفظ می‌کند | Pass اگر یک اصلاح فعال و ledger بدون دوباره‌شماری بماند؛ fixture را با workflow ببندید |
| LEAVE-08 comment و attachment | درخواست مجاز غیرمحرمانه؛ فایل ساختگی PDF معتبر و فایل نامعتبر | POST comments `{"body":"یادداشت آزمون"}`؛ POST multipart `file=@<valid.pdf>`؛ GET download؛ سپس MIME/signature ناسازگار و فایل >۱۰ MiB | comment 201 و Event/Audit؛ پیوست 201؛ نامعتبر 400؛ دانلود خصوصی no-store | Pass اگر فقط PDF/PNG/JPEG سازگار پذیرفته شود؛ حذف فایل‌ها فقط در فضای تست |
| LEDGER-01 اصلاح دستی/CSV | HR دامنه‌دار یا admin، entitlement تستی، CSV هدر مطابق UI `personnel_code,type,year,days` | POST `/api/v1/entitlements/<id>/adjust` با `{"days":"1.0","reason":"<test>"}` و key؛ POST `/api/v1/entitlements/import/?dry_run=1` سپس `dry_run=0` با `{"csv":"personnel_code,type,year,days\\n<code>,<type>,<year>,<days>"}` | **هدف پذیرش** adjustment: پاسخ موفق، رویداد دفترکل و projection سازگار؛ dry-run بدون ledger؛ commit فقط اگر `rejected=0` و هر خط معتبر باشد. کد view نقش و scope را کنترل و سرویس را فراخوانی می‌کند؛ آزمون مستقیم API این عملیات در suite موجود یافت نشد و این ممیزی آن را اجرا نکرد | Pass فقط پس از تطبیق projection/ledger در محیط disposable؛ نتیجه runtime نامعلوم است. از شناسه/نوع/داده synthetic استفاده کنید؛ import را جداگانه تست کنید |
| LEDGER-02 reconciliation | entitlement آزمایشی و eventهای مشروع | GET `/api/v1/balances/?year=<year>` و مقایسه جمع event/projection | در تطبیق، balance؛ در ناسازگاری 409؛ تغییر DB در GET ندارد | Pass با تابع reconciliation/آزمون؛ projection را دستی تخریب نکنید |
| LEDGER-03 چندساله و carry-forward | سیاست سال و سهمیه دو سال مجاور؛ درخواست دو ساله | ثبت از workflow و خواندن entitlements/balances | سهمیه بین سال‌ها بر اساس سهم روزکاری؛ eventهای مربوطه جمعاً برابر روزها | Pass اگر sum برابر درخواست و transfer فقط available باشد؛ این سناریو به setup سرویس نیاز دارد |
| CONC-01 رزرو هم‌زمان | PostgreSQL disposable جدا از production، کاربر DB مجاز به ساخت test DB، entitlement کافی، دو درخواست و دو اتصال؛ متغیرهای لازم `ZSH_SECRET_KEY` (حداقل ۵۰ نویسه)، `ZSH_ALLOWED_HOSTS` و `ZSH_DB_PASSWORD` و `ZSH_DB_*` فقط به DB آزمون اشاره کنند | از `backend/`: `DJANGO_SETTINGS_MODULE=config.settings_prod python3 manage.py test leave.tests.test_entitlement_ledger.PostgreSQLEntitlementConcurrencyTests.test_parallel_reservations_serialize_without_lost_ledger_entries` | دو event رزرو، بدون lost update | Pass فقط با DB PostgreSQL disposable؛ هرگز settings/credential/DB تولید را به test runner ندهید؛ SQLite نتیجه معتبر نمی‌دهد |
| CONC-02 approve هم‌زمان و immutability | همان PostgreSQL disposable و env بالا | جداگانه اجرا کنید: `DJANGO_SETTINGS_MODULE=config.settings_prod python3 manage.py test leave.tests.test_entitlement_ledger.PostgreSQLEntitlementConcurrencyTests.test_parallel_approval_replays_one_atomic_posting` و `DJANGO_SETTINGS_MODULE=config.settings_prod python3 manage.py test leave.tests.test_entitlement_ledger.PostgreSQLEntitlementConcurrencyTests.test_database_trigger_rejects_journal_updates` | یک posting مصرف؛ UPDATE مستقیم event به خطای DB | Pass اگر هر دو آزمون عبور کنند؛ این اجرا به علت SQLite skipped است |

### تقویم، گزارش و تنظیمات

| ID / هدف | نقش، پیش‌شرط و داده آزمون | گام و درخواست دقیق | پاسخ/تغییر داده مورد انتظار | معیار Pass/Fail و پاک‌سازی |
|---|---|---|---|---|
| CAL-01 روزکاری/تعطیلات | Employee با pattern و policy معتبر، بازه کوتاه شامل روز کاری/تعطیل | GET `/working-days/estimate?employee=<id>&start=<date>&end=<date>`؛ GET `/calendar/holidays/?from=<date>&to=<date>` | `days`, `estimated=false`, policy/work-pattern IDs؛ بدون تغییر DB | Pass اگر pattern، تعطیلات و اثر تاریخ مؤثر درست باشند؛ API مستقل از UI |
| CAL-02 حدود calendar و RBAC | کارمند، مدیر مستقیم، HR scoped و admin | GET `/calendar/events/?from=<date>&to=<date>&scope=me|team|org`; هر نقش هر scope | 200 فقط scope مجاز؛ invalid scope 400، دسترسی غیرمجاز 403؛ فقط درخواست‌های تقویمی انتخاب‌شده | Pass اگر org فقط HR scoped و team فقط manager باشد |
| API-01 تمام مسیرهای Frontend | کاربر نقش مناسب و browser devtools | بازکردن صفحات واقعی جدول API سند ۰۱؛ مشاهده Network و تطبیق روش/path | پاسخ سازگار با قرارداد؛ CRUD فقط mutation مجاز؛ تفاوت method/path ثبت نقص | Pass اگر همه callها route واقعی داشته و جواب schema قابل مصرف باشد |
| REPORT-01 گزارش و حداقل گروه | HR/exec در scope با داده ساختگی کمتر/برابر/بیشتر حداقل گروه | GET `/reports/absences`, `/reports/balances`, `/reports/trends`, `/reports/process-health`, `/reports/bradford` | بدون PII؛ گروه کوچک پنهان؛ Bradford endpoint عمومی series خالی | Pass اگر داده کم‌شمار از پاسخ aggregate قابل استنتاج نباشد |
| CONF-01 آزمون Canary کامل | نام نوع/دلیل/یادداشت مصنوعی یکتا؛ نقش مجاز و غیرمجاز | در درخواست محرمانه، GET detail/comments/attachments، calendar، notifications، balances، report و audit | فقط HR در scope جزئیات مجاز؛ پاسخ مدیر/مالک/جانشین و خروجی‌های عمومی فاقد Canary | Pass اگر جستجوی Canary در همه پاسخ‌های غیرمجاز صفر باشد؛ پاک‌سازی با درخواست/تست disposable |
| ADMIN-01 تنظیم و audit | admin، کلید معتبر در `settings_schema.DEFS`، دلیل | GET `/admin/settings/`; POST همان مسیر `{"key":"<key>","value":<value>,"reason":"<علت>"}`؛ GET `/audit/events/` | تغییر معتبر + audit؛ مقدار نامعتبر 400؛ غیرadmin 403 | Pass اگر تغییر فقط با دلیل و validator schema انجام شود |

## ۷. Production/PostgreSQL/Integration موارد لازم ولی اجرا‌نشده

1. در PostgreSQL disposable، `ZSH_SECRET_KEY` معتبر (حداقل ۵۰ نویسه)، `ZSH_ALLOWED_HOSTS` غیرخالی و همه `ZSH_DB_*` را فقط به همان DB آزمون تنظیم کنید. سپس از `backend/` فرمان‌های زیر را اجرا کنید:

   ```bash
   ZSH_ENV=production DJANGO_SETTINGS_MODULE=config.settings_prod python3 manage.py migrate --plan
   ZSH_ENV=production DJANGO_SETTINGS_MODULE=config.settings_prod python3 manage.py migrate
   ```

   `migrate --check` جای اجرای مهاجرت روی دیتابیس خالی نیست. `config.settings` نیز موجود است و با `ZSH_ENV=production` به settings تولیدی می‌رود؛ module صریح در این مثال برای جلوگیری از ابهام است.
2. اجرای `PostgreSQLEntitlementConcurrencyTests` با settings جداگانه آزمون؛ از اتصال تولید استفاده نکنید.
3. backup/restore: repository فرمان/ابزار یا job تأییدشده ندارد؛ پس از تعیین زیرساخت، معیارها در سند ۰۹.
4. E2E مرورگر، ایمیل، ارسال فایل در object storage، restart، TLS و alerting در این نوبت اجرا نشده‌اند.
5. آزمون امنیتی مستقل، dependency audit و secret scan اجرا نشده‌اند.

## ۸. تمیزکاری

از DB disposable استفاده کنید؛ Django TestCase با teardown، دیتابیس تست را پاک می‌کند. داده API دستی را از طریق workflow/مسیر مجاز در محیط تست ببندید یا کل دیتابیس تست را پس از اطمینان از نام DB حذف کنید. فایل پیوست را فقط از media directory کاملاً مشخص و مخصوص تست پاک کنید. هیچ‌گاه در DB مشترک/تولید `flush`, حذف دستی Event دفترکل یا حذف رکورد audit اجرا نکنید.

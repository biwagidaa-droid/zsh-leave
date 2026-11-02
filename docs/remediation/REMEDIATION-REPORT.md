# گزارش اصلاحات

## وضعیت فعلی ممیزی مستقل — ۲ نوامبر ۲۰۲۶

این گزارش شامل snapshot فازهای گذشته است و ادعاهای «سایر فازها پیاده‌سازی نشده‌اند» وضعیت فعلی را نشان نمی‌دهند. Employment authorization، invitation/activation، hierarchy/sites، imports/ledger، Bradford، scheduler, audit triggers, attachment security, notification delivery و backup/restore اکنون در کد/آزمون هستند؛ شواهد کامل و status هر حوزه در [گزارش نهایی Backend](./BACKEND-FINAL-AUDIT.md) آمده است. محدودیت‌های deployment، audit `TRUNCATE`, Bradford provisional، scanner و backup production همچنان بازند.

## فاز ۱ — حریم خصوصی انواع محرمانه

| یافته | ریشه | اقدام | آزمون | وضعیت |
|---|---|---|---|---|
| Balance و entitlement شامل کلید/برچسب/مبلغ محرمانه بود | مسیر production فیلتر `visible_balance_types` را استفاده نمی‌کرد؛ selector عمومی admin/personal/team نیز دامنه HR را مخلوط می‌کرد | اعمال فیلتر به ازای کارمند با `visible_balance_types` و بررسی دامنه HR؛ balances از selector دامنه‌دار؛ entitlements از `scoped_hr_employees` که personal/team scope را جدا نگه می‌دارد | آزمون employee، manager، HR مجاز، HR شرکت دیگر، HR با profile خارج از دامنه و admin | FIXED AND VERIFIED برای endpointهای آزموده‌شده |
| گزارش‌های executive می‌توانستند نوع و شمار confidential را آشکار کنند | دسته‌بندی absence برچسب نوع را نشان می‌داد؛ trends/process-health/balances همه درخواست‌ها را می‌شمردند | حذف نوع محرمانه از داده تجمیعی executive؛ HR دامنه‌دار همچنان داده‌های دامنه خود را می‌بیند | آزمون absences، trends، process-health و balances برای executive و absences برای HR | FIXED AND VERIFIED برای routeهای آزموده‌شده |
| شمارش پوشش روزانه confidential را در تجمیع manager وارد می‌کرد | `awayCount` بدون فیلتر confidentiality ساخته می‌شد | فقط درخواست غیرمحرمانه در خروجی manager؛ HR مجاز همچنان پوشش کامل دامنه خود را دارد | آزمون دو روز جدا با غیبت محرمانه/عادی برای manager و HR | FIXED AND VERIFIED |
| API export گزارش یافت نشد | `urls.py` مسیر export ندارد؛ `zsh_core.exports` فقط serializer CSV/XLSX است | هیچ endpoint export قابل اصلاح در این فاز نبود؛ مسیرهای فایل‌محور دیگر باید در مراحل بعدی دوباره بررسی شوند | بررسی routeها و call-siteهای API | NOT REPRODUCED به‌عنوان endpoint گزارش موجود |

**وضعیت Gate حریم خصوصی کلی: NOT VERIFIED.** مسیرهای balance، entitlement، گزارش و coverage اصلاح شدند؛ این نتیجه جای ممیزی کامل timeline، اعلان، Bradford، همه endpointها و exportهای واقعی را نمی‌گیرد.

## فاز ۲ — ثبت غیبت HR

| یافته | ریشه | اقدام | آزمون | وضعیت |
|---|---|---|---|---|
| HR درخواست را دوبار transition می‌داد | `submit_request` برای HR همان ابتدا `APPROVED` می‌ساخت؛ سپس approve نامعتبر بود | حذف approve دوم؛ ایجاد مستقیم از مسیر service در وضعیت نهایی و ثبت یک رویداد `submit` از خالی به `APPROVED` | ایجاد موفق، وضعیت، یک event/audit و اثر دفترکل | FIXED AND VERIFIED |
| نبود header از idempotency عبور می‌کرد | endpoint در نبود `Idempotency-Key` کلید UUID تازه می‌ساخت | کلید الزامی؛ UI موجود از قبل کلید ارسال می‌کند | درخواست بدون کلید 422؛ replay با همان کلید منبع واحد را می‌دهد | FIXED AND VERIFIED |
| fingerprint بخشی از ورودی را نادیده می‌گرفت | `workingDays` و `replacementId` در payload ثبت نمی‌شدند | fingerprint شامل همه فیلدهای اثرگذار است | استفاده از همان کلید با ورودی متفاوت 409 | FIXED AND VERIFIED |
| دسترسی خارج دامنه و rollback | تست رگرسیون برای actor غیر HR، HR خارج دامنه و خطای اعتبارسنجی موجود نبود | تست‌های 403/404 و rollback رویداد/حسابرسی/idempotency افزوده شد | آزمون API SQLite | FIXED AND VERIFIED |

## فاز ۳ — مجوز کاتالوگ سراسری LeaveType

| یافته | ریشه | اقدام | آزمون | وضعیت |
|---|---|---|---|---|
| HR دامنه‌دار می‌توانست تنظیمات سراسری LeaveType را بخواند/تغییر دهد | endpoint، `has_role("hr")` را به‌عنوان مجوز نوشتن می‌پذیرفت؛ مدل LeaveType شرکت ندارد | افزودن `leave_type.global.manage` فقط برای admin سراسری/superuser؛ الزام permission در API و سرویس؛ HR فقط metadata فعال را می‌خواند؛ دلیل و before/after/actor/time/correlation ID در AuditEvent | آزمون منع create/update/confidential/counts/approval/deactivate و self-grant؛ آزمون عملیات مجاز admin، سیاست خواندن و نبود audit موفقیت کاذب؛ کل backend: ۱۸۹ تست، ۳ skipped | FIXED AND VERIFIED |

## سایر فازها

فازهای lifecycle/offboarding، activation، RBAC سازمانی کامل، Bradford، scheduler، audit append-only، PostgreSQL، ادغام Frontend گسترده و آمادگی استقرار در این بازه پیاده‌سازی یا تأیید نشده‌اند. برای ادامه، `PROGRESS.md` را ببینید.

## فاز چرخه استخدام و offboarding — راستی‌آزمایی مستقل

**وضعیت: BLOCKED / NOT VERIFIED — نقص دسترسی بازتولید شد.** هیچ تغییر مؤثر چرخه استخدام در backend باقی نمانده است. diff اولیه فقط یک فیلد `session_version` و مدل تاریخچه استخدام اضافه می‌کرد، بدون migration، استفاده در authentication یا اتصال به authorization. تست‌ها با آن مدل ناقص ۲۶ خطای schema دادند؛ تغییر ناقص حذف شد.

| بررسی | نتیجه | شواهد |
|---|---|---|
| دسترسی employee منقضی | **FAIL — bypass تأیید شد** | `end_date=2026-10-31` و کاربر فعال در 2026-11-01 هنوز نقش employee داشت |
| اختیار manager منقضی | **FAIL — bypass تأیید شد** | manager منقضی نقش manager و `can_decide_leave_request=True` داشت |
| employee فعال معمولی | مجاز | probe نقش employee را برای اشتغال جاری تأیید کرد |
| کاربر غیرفعال | رد شد | `User.is_active=False` هیچ نقش authorization نگرفت |
| عدم اثر جانبی رد درخواست | تأیید برای endpoint موجود HR | آزمون 403/404 و rollback ورودی نامعتبر، بدون request/event/audit/idempotency |
| migration سازگار | schema فعلی بدون تغییر | `makemigrations --check --dry-run` موفق؛ هیچ migration چرخه استخدامی تولید/اعمال نشده |
| session/token revocation | **NOT VERIFIED** | فقط Django database session یافت شد؛ refresh/API token یا service ابطال نشست وجود ندارد |

قانون هدف برای پیاده‌سازی بعدی این است که روز `end_date` آخرین روز اشتغال و شامل همان روز باشد و تاریخ جاری از `timezone.localdate()` گرفته شود. این قانون هنوز در سرویس و API اجرا نشده است. رفتار تعلیق/خاتمه، درخواست‌های در انتظار، rehire و ابطال نشست باید پیش از اعلام رفع نقص پیاده‌سازی و آزموده شوند. شواهد فرمان‌ها و محدودیت‌ها در `PROGRESS.md` آمده‌اند.

## فاز ورود CSV سهمیه مرخصی — بازیابی و اصلاح

**وظیفه:** شناسایی تکرارها و جلوگیری از ثبت گروهی ناسازگار در ورود CSV سهمیه.

**وضعیت بازیابی:** هنگام شروع این فاز، تغییرات parser مشترک، سرویس اعتبارسنجی
و مسیر بازاعتبارسنجی در تراکنش از قبل در worktree وجود داشتند، اما تست و
مستندات این فاز کامل نبودند. تغییرات موجود حفظ و پیش از ادامه بررسی شدند.

| یافته | ریشه | اقدام | آزمون/شواهد | وضعیت |
|---|---|---|---|---|
| کلید یکتای کسب‌وکار کارمند + نوع مرخصی + سال است | قید مدل `uniq_entitlement` روی سه فیلد | همان کلید برای تشخیص تکرار درون فایل و پایگاه داده استفاده می‌شود | تست تکرار در فایل، تکرار DB و دو ترکیب کلید متفاوت | FIXED |
| Preview و commit می‌توانستند قواعد متفاوتی داشته باشند و نتیجه preview کهنه می‌شد | parser مستقل API و نبود بازاعتبارسنجی داخل تراکنش | سرویس اعتبارسنجی مشترک؛ commit اعتبارسنجی را در تراکنش تکرار و ردیف‌های مرجع را قفل می‌کند | تست هم‌خوانی preview/commit و ایجاد رکورد پس از preview | FIXED |
| فایل دارای یک ردیف خطا ممکن بود به‌صورت جزئی ثبت شود | قواعد all-or-nothing باید در مرز تراکنش اعمال شود | حفظ سیاست A-13؛ هیچ سهمیه/رویدادی پس از خطای ردیف یا شکست دفترکل باقی نمی‌ماند | تست ورودی نامعتبر و rollback هنگام شکست ایجاد ledger | FIXED |
| خطاهای ساختار CSV باید قابل اقدام باشند | ردیف کوتاه/بلند، header و encoding نیازمند نتیجه صریح‌اند | کد خطا و شماره سطر؛ رد header تکراری/اضافی، تعداد ستون نادرست، UTF-8 نامعتبر و CSV malformed | تست‌های parser و endpoint | FIXED |

مشخصات فارسی کسب‌وکار و قالب فایل در
[`entitlement-csv-import-fa.md`](../entitlement-csv-import-fa.md) ثبت شده است.
فایل‌های Frontend و migrationها تغییر نکردند. تست هم‌زمانی مخصوص PostgreSQL
تعریف شده، اما در SQLite اجرا نمی‌شود و تا زمان اجرای آن روی PostgreSQL
**NOT VERIFIED** باقی می‌ماند.

اعتبارسنجی نهایی: مجموعه کامل backend با فرمان
`cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test`
با **۲۸۵ تست موفق و ۷ تست skip** پایان یافت. تست‌های متمرکز import، دفترکل و
parser نیز **۴۳ تست موفق و ۴ تست skip** داشتند. `manage.py check` بدون خطا بود،
`makemigrations --check --dry-run` تغییر جدیدی گزارش نکرد و `git diff --check`
تمیز بود. تست‌های قفل/رقابت PostgreSQL به دلیل استفاده از SQLite در این محیط
جزو موارد skip هستند.

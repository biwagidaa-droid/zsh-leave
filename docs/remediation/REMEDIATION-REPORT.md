# گزارش اصلاحات

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

## سایر فازها

فازهای lifecycle/offboarding، activation، RBAC سازمانی کامل، Bradford، scheduler، audit append-only، PostgreSQL، ادغام Frontend گسترده و آمادگی استقرار در این بازه پیاده‌سازی یا تأیید نشده‌اند. برای ادامه، `PROGRESS.md` را ببینید.

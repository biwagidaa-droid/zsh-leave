# دروازه آمادگی تولید

## نتیجه ممیزی مستقل — ۲ نوامبر ۲۰۲۶

جدول قبلی پایین‌تر وضعیت snapshot زمان فازهای قبلی است و از نظر PostgreSQL، lifecycle، notification و backup به‌روز نیست. نتایج فعلی در [ممیزی نهایی Backend](./BACKEND-FINAL-AUDIT.md) و گزارش‌های امنیت، PostgreSQL و عملیات آمده‌اند. وضعیت gateها اکنون: A Authorization **PASS** برای مسیرهای آزموده‌شده؛ B Confidentiality **PASS** برای endpoint/exportهای دارای regression؛ C Workflow **PASS**؛ D Employment lifecycle **PASS** با session denial در درخواست بعدی؛ E Activation **PASS**؛ F Data integrity **PASS**؛ G PostgreSQL **PASS** روی PostgreSQL 17.11 آزمایشی؛ H Frontend خارج از scope؛ I Jobs **NOT VERIFIED در deployment**؛ J Deployment/operations **NOT VERIFIED**؛ Audit **NOT VERIFIED کلی** به علت TRUNCATE/role grants؛ Attachments **NOT VERIFIED در محیط production**. نتیجهٔ کلی همچنان **NOT READY FOR PRODUCTION** است.

هیچ gate کلی با این تغییرات PASS اعلام نمی‌شود. نتیجه هر مورد براساس شواهد همین فازها است.

| Gate | وضعیت | شاهد/مانع |
|---|---|---|
| A — حریم خصوصی | NOT VERIFIED کلی | balance، entitlements، executive reports و coverage manager آزموده و اصلاح شدند؛ ممیزی همه timeline/notification/exportها انجام نشده است. |
| B — Authorization | NOT VERIFIED | scopeهای balance/HR absence آزموده شدند؛ ماتریس تمام endpointها، site/department و global configuration باقی است. |
| C — Workflow | PARTIAL / FIXED AND VERIFIED برای HR absence | ایجاد مستقیم approved، ledger، event، idempotency و rollback آزموده شد؛ همه transitionها/هم‌زمانی workflow بازبینی کامل نشده‌اند. |
| D — Employee lifecycle | NOT VERIFIED | end_date، suspension، session revocation و rehire فاز بعدی است. |
| E — Account activation | NOT VERIFIED | invitation و password setup هنوز بررسی/پیاده‌سازی نشده است. |
| F — Data integrity | PARTIAL | migration drift و آزمون‌های SQLite موفق‌اند؛ hierarchy/import/append-only کامل بررسی نشده است. |
| G — PostgreSQL | BLOCKED / NOT VERIFIED | SQLite تست شد؛ ۳ آزمون PostgreSQL-only رد شدند؛ اتصال واقعی PostgreSQL برقرار/تأیید نشد. |
| H — Frontend | NOT VERIFIED کلی | ۳۴ تست و production build موفق؛ بازبینی کامل API contracts/role UX/E2E انجام نشده است. |
| I — Jobs | IMPLEMENTED / NOT VERIFIED IN PRODUCTION | مدیریت اجرای DB-backed، retry محدود، readiness، API وضعیت و نمونه systemd timer وجود دارد؛ نصب timer، پیکربندی سیاست‌ها و آزمون PostgreSQL/production هنوز انجام نشده است. |
| J — Deployment | NOT VERIFIED | static prod settings بررسی اولیه شده؛ TLS proxy، secrets در محیط واقعی، backup/restore و monitoring اجرا/تأیید نشده‌اند. |
| K — Testing | PARTIAL | آزمون‌های موجود سبز؛ PostgreSQL/E2E و lint مستقل در دسترس نبودند. |

## پیش‌نیازهای محیط production

`config.settings_prod` به `ZSH_SECRET_KEY` با حداقل ۵۰ نویسه، `ZSH_ALLOWED_HOSTS` غیرخالی، `ZSH_DB_PASSWORD` و PostgreSQL نیاز دارد. `DEBUG=False`، cookie امن، redirect HTTPS و HSTS در تنظیمات دیده می‌شوند. پیکربندی reverse proxy، trusted forwarded headers، CORS، سرویس ایمیل، backup، restore، alerting و scheduler باید پیش از release در محیط مقصد تعریف و آزموده شوند.

## نتیجه

**NOT READY FOR PRODUCTION.** این تغییرات دو نقص مهم را با آزمون اصلاح می‌کنند، اما Gateهای A/B/D/E/G/I/J و تکمیل آزمون‌های production هنوز بسته نشده‌اند.

# محدودیت‌ها و تصمیم‌های باز

## وضعیت مستقل فعلی — ۲ نوامبر ۲۰۲۶

این بخش، موارد بررسی‌شده را از فهرست تاریخی پایین‌تر جدا می‌کند. PostgreSQL 17.11 اکنون با کل suite اجرا شد (۳۷۷ passed، صفر skipped)، employment authorization، activation، notification delivery و backup/restore synthetic در کد/آزمون حاضرند. محدودیت‌های باز فعلی عبارت‌اند از: PostgreSQL `TRUNCATE` می‌تواند `AuditEvent` را پاک کند؛ production role grants، volume/scanner، systemd deployment، monitoring، SMTP واقعی، offsite backup و restore production موجود/آزموده نیستند؛ Bradford همچنان `provisional` است؛ push/SMS و provider bounce webhook نداریم. جزئیات و شواهد: [ممیزی نهایی](./BACKEND-FINAL-AUDIT.md)، [PostgreSQL](./POSTGRESQL-EVIDENCE.md)، [عملیات](./PRODUCTION-OPERATIONS.md).

این فهرست وضعیت را از کد/مستندات مشاهده‌شده جدا می‌کند؛ موارد «بررسی‌نشده» به معنی پیاده‌سازی سالم یا معیوب نیستند.

## یافته‌های قطعی

- تنظیم زمان‌بندی و اجرای Job، persistence، API وضعیت و نمونه systemd timer پیاده‌سازی شده‌اند؛ نصب/فعال‌بودن timer، alerting و آزمون production هنوز تأیید نشده است. rollover و expiration پیش‌فرض خاموش‌اند تا سیاست سازمانی تصویب شود.
- `/api/v1/reports/bradford` در حال حاضر series خالی و توضیح بازگشت می‌دهد؛ تابع pure Bradford وجود دارد، اما analytics endpoint کامل نیست.
- route گزارش export در `backend/leave/urls.py` وجود ندارد. `zsh_core.exports` فقط CSV/XLSX را serialize می‌کند؛ آن را قابلیت export API کامل فرض نکنید.
- Backend آزمون در این فاز SQLite بود و سه آزمون هم‌زمانی/trigger PostgreSQL اجرا نشدند.
- هشدار SQLite برای `PublicHoliday` constraint با `nulls_distinct` باقی است.

## بررسی‌نشده یا ناقص

- بررسی مؤثر بودن end_date در authorization، قطع نشست در offboarding و rehire.
- invitation امن، activation، password setup و revocation.
- ممیزی RBAC همه endpointها، global LeaveType configuration، سلسله‌مراتب company/department/manager و عملیات Site.
- کاربری/سیاست Bradford، دسترسی اختیاری settings و UI loading/error در roleهای متفاوت.
- alerting/retention متمرکز و استقرار واقعی systemd هنوز تأیید نشده است.
- append-only بودن database-level و coverage حسابرسی mutationها.
- PostgreSQL سازگاری queryها، مهاجرت‌ها و triggerهای کامل.
- CORS، proxy trust، TLS واقعی، backup/restore، monitoring، media persistence و deployment واقعی.
- E2E مرورگر و lint اختصاصی.
- API ساعت مرخصی در `client_policy` خاموش (`hourlyLeaveEnabled=false`) است؛ frontend منطق نمایشی/محاسباتی دارد، اما قابلیت production اثبات نشده.
- تنظیمات business مانند دوره سال مرخصی، قواعد Bradford و retention همچنان به تصمیم سازمان نیاز دارند؛ مستند تصمیمات موجود را بررسی کنید.

## گام بعد

ادامه از `PROGRESS.md`: فاز ۳، یکپارچه‌سازی تعریف وضعیت مؤثر استخدام با authorization مشترک و افزودن regression test برای end date گذشته/آینده، بدون غیرفعال‌کردن دسترسی زودهنگام برای end date آینده.

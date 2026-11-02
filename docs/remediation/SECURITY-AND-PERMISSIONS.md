# امنیت و مجوزها — وضعیت فعلی ممیزی

## تکمیل ممیزی مستقل — ۲ نوامبر ۲۰۲۶

ماتریس پایین‌تر محدود به فازهای اولیه است. Audit نهایی، HR scope union، global LeaveType، IDOR، lifecycle، activation، exports، notification confidentiality و PostgreSQL row triggers را دوباره با suite کامل بررسی کرد. Employment authorization اکنون در `authorization_context` نیز کنترل می‌شود. PostgreSQL `TRUNCATE` همچنان bypass تأییدشده است و Gate 6 **NOT VERIFIED** باقی می‌ماند؛ جزئیات در [SECURITY-VERIFICATION.md](./SECURITY-VERIFICATION.md) است.

## اصل اجرای مجوز

Backend مرجع مجوز است. `authorization_context` نقش‌ها را از کاربر فعال، profile و `RoleAssignment` فعال می‌سازد؛ selectorهای `scoped_employees` و `scoped_hr_leave_requests` دامنه را در query اعمال می‌کنند. این سند وضعیت بررسی‌شده فازهای ۱ تا ۳ را ثبت می‌کند و ادعای ممیزی کامل همه APIها نیست.

## ماتریس حداقلی مسیرهای بررسی‌شده

| نقش | Balance | Entitlements | گزارش جمعی | Coverage | ثبت غیبت HR |
|---|---|---|---|---|---|
| کارمند | فقط خود؛ انواع محرمانه حذف می‌شوند | 403 | 403 | 403 | 403 |
| مدیر | self/direct-report در selector؛ نوع محرمانه حذف | 403 | 403 | شمار فقط غیرمحرمانه در زیرمجموعه | 403 |
| HR دامنه‌دار | فقط employeeهای selector؛ داده محرمانه فقط برای employee داخل scope | فقط HR و فقط employeeهای `scoped_hr_employees`؛ personal/team دسترسی خارج assignment به entitlement اضافه نمی‌کند | HR دامنه‌دار، شامل داده محرمانه | دامنه HR | فقط employee داخل scope |
| Executive | selector balance می‌تواند دامنه کارمند خود/تیم داشته باشد اما confidential حذف می‌شود | 403 | فقط aggregate؛ داده محرمانه حذف | 403 | 403 |
| Admin | دسترسی عمومی به balance ندارد؛ selector عادی و 404 | 403 مگر نقش HR scoped مستقل | 403 | براساس نقش واقعی؛ admin تنها کافی نیست | براساس HR assignment واقعی و scope |

این جدول محدود به endpointهای بررسی‌شده است؛ **ماتریس جامع permission برای تمام عملیات هنوز تکمیل نشده است**.

## قواعد confidential اعمال‌شده

- داده درخواست محرمانه در scope مجاز HR قابل مشاهده است؛ مدیر و نقش‌های دیگر نوع/برچسب/مانده آن را از balance و aggregateهای بررسی‌شده نمی‌گیرند.
- گزارش executive از رکوردهای confidential برای absences، trends، process-health و balance aggregate استفاده نمی‌کند.
- Coverage مدیر، `awayCount` را با درخواست‌های غیرمحرمانه محاسبه می‌کند. HR scoped می‌تواند aggregate کامل محدوده خود را ببیند.
- privacy group-size موجود همچنان برای گروه‌های کوچک اعمال می‌شود.
- `LeaveType` taxonomy سراسری و بدون اتصال به شرکت است. scoped HR فقط انواع فعال را برای کار HR می‌خواند و مجوز نوشتن ندارد؛ employee/manager فقط انواع فعال و قابل درخواست را می‌خوانند؛ admin global همه انواع را می‌خواند. `leave_type.global.manage` مختص admin سراسری/superuser است.
- ایجاد/ویرایش/غیرفعال‌سازی LeaveType از API و سرویس ادمین هر دو نیازمند permission و دلیل‌اند؛ AuditEvent append-only ثبت actor، before/after، دلیل، timestamp و `X-Correlation-ID` اختیاری را ذخیره می‌کند. حذف، bulk mutation و import برای LeaveType route پشتیبانی‌شده ندارند.
- route گزارش export در `leave/urls.py` وجود ندارد؛ serializerهای CSV/XLSX به‌تنهایی endpoint داده نیستند.

## دامنه و چرخه حساب

کد RoleAssignment از scopeهای global/company/site/department/employee پشتیبانی می‌کند؛ برای HR، grant جهانی مجاز نیست. تطبیق scopeهای site/department و lifecycle استخدامی در فازهای بعدی باید سرتاسری آزموده شود. ورود، خروج نشست، `/auth/me` و تغییر گذرواژه وجود دارند؛ invitation/activation، قطع نشست‌های موجود در زمان offboarding و refresh/API token در این فاز بررسی نشده‌اند.

## حسابرسی

فاز ۲ یک LeaveRequestEvent و AuditEvent یکتا برای ثبت HR را آزموده و atomic بودن rollback را بررسی می‌کند. حفاظت append-only در سطح ORM/DB برای همه مدل‌های حساس، bulk operation و retention در این فاز ممیزی نشده است؛ به معنی تأیید کامل audit design نیست.

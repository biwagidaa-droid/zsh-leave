# مدل داده

سطح محرمانگی: **P** عمومی داخلی، **I** داخلی، **C** محرمانه (HR/مجاز)، **S** حساس‌ترین (اسناد پزشکی/نوع محرمانه).
همه PKها `bigint`؛ زمان‌ها UTC؛ تاریخ‌های تقویمی `date` میلادی.

| جدول | دلیل وجود | محرمانگی | قیود و ایندکس مهم |
|------|-----------|----------|-------------------|
| User | هویت و ورود | I | username/email یکتا؛ is_active؛ بدون حذف فیزیکی |
| EmployeeProfile | اطلاعات سازمانی؛ FK به User, Company, Department, Position, manager(User) | I/C | personnel_code یکتا در شرکت؛ CHECK(manager≠خود)؛ is_employee (حساب‌های سرویس/مهمان false) |
| Company / Department / Position | ساختار چندشرکتی | P | Department درختی با parent؛ یکتایی کد در شرکت |
| EmploymentContract / ContractPeriod | الگوی کاری تاریخی | C | بازه‌های ContractPeriod هم‌پوشان نباشند (EXCLUDE constraint روی daterange)؛ work_days bitmask، contract_percent |
| LeaveType | تعریف نوع | I (نام نوع محرمانه: S) | key یکتا؛ پرچم‌ها: requires_approval, employee_requestable, requires_note, requires_replacement, counts_against_balance, confidential, calendar_visibility, enabled, sort_order؛ CHECK(confidential ⇒ ¬employee_requestable) |
| LeavePolicy | سیاست به‌ازای شرکت/گروه (carry-over، مهلت‌ها، آستانه‌ها) | I | یکتا (scope, effective_from) |
| LeaveRequest | قلب سامانه | C (S برای نوع محرمانه) | FK employee, manager_snapshot, type, replacement, supersedes؛ status با CHECK؛ CHECK(start≤end, working_days>0)؛ ایندکس (employee,status)، (manager,status)، (start,end)، (status,created_at)؛ **UNIQUE جزئی**: یک supersedes فعال برای هر اصل؛ **EXCLUDE** برای هم‌پوشانی APPROVED یک کارمند (در صورت سیاست) |
| LeaveRequestComment | بحث | C | request FK؛ در نوع محرمانه ممنوع برای غیر HR |
| LeaveRequestEvent | تاریخچه درخواست، append-only | C | بدون UPDATE/DELETE (trigger) |
| LeaveAttachment | پیوست | S | مسیر ذخیره تصادفی؛ sha256؛ mime بررسی‌شده؛ سقف اندازه/تعداد |
| LeaveEntitlement | تصویر تخصیص سهمیه (کارمند، نوع، سال) | C | UNIQUE(employee,type,year)؛ base, carry_over, manual_adjustment (decimal 5,1)، قابل تطبیق با دفترکل |
| EntitlementEvent | دفترکل append-only سهمیه | C | تغییرات پایه/انتقال/اصلاح/رزرو/مصرف، request و reversal اختیاری، قبل/بعد/دلیل/عامل؛ کلید idempotency یکتا؛ قفل ردیف سهمیه |
| PublicHoliday / PublicHolidayHistory | تعطیلات ثبت‌شده دستی (شمسی؛ سالانه یا یک‌بار) و تاریخچه append-only | P | UNIQUE(scope, jalali_year, month, day) با nulls_distinct=False (نیازمند PostgreSQL ≥ 15)؛ اسکوپ: ملی/شرکت/منطقه |
| Notification | اعلان داخلی | C | dedupe_key یکتا؛ فقط متن بازنویسی‌شده (redacted) |
| EmailDeliveryLog | نتیجه ارسال | I | وضعیت، خطا (بدون محتوای حساس) |
| AuditEvent | حسابرسی مرکزی | C | append-only؛ actor, action, entity, before/after (redacted), reason, result, origin |
| BackgroundJobExecution | وضعیت Jobها | I | job, started, finished, status, error |
| SystemSetting | تنظیمات داشبورد مدیریت؛ مقدار فقط با `settings_schema` اعتبارسنجی و ذخیره می‌شود | I | key یکتا؛ تغییر با دلیل الزامی → AuditEvent؛ مقدار خراب هنگام خواندن خطا می‌دهد |
| Role / UserRole | نقش‌های چندگانه با scope (شرکت/واحد) | I | یکتا (user, role, scope) |
| ImportBatch | تاریخچه ورود گروهی | C | فایل‌hash، dry_run، نتیجه |

## ماندگاری و حذف
حذف فیزیکی کارمند/درخواست ممنوع؛ غیرفعال‌سازی یا ناشناس‌سازی طبق سیاست نگهداری (OQ-10).

## فرمول مانده (قطعی، به‌همراه تصمیم C-3)
```
کل = base + carry_over + manual_adjustment
استفاده‌شده = Σ postingهای دفترکل مصرف (مانده statusهای APPROVED و WITHDRAWAL_PENDING)
رزروشده     = Σ postingهای دفترکل رزرو (مانده statusهای PENDING و ESCALATED)
مانده        = کل − استفاده‌شده
قابل استفاده = کل − استفاده‌شده − رزروشده
```
هر تغییر سهمیه، رزرو، تأیید، آزادسازی، برگشت، انتقال و انقضا در یک تراکنش و با کلید idempotency ثبت می‌شود. رزرو و مصرف هرگز منفی نمی‌شوند؛ مقدار قابل استفاده می‌تواند طبق رفتار قبلی منفی باشد. درخواست‌های چندساله با تقویم سال مرخصی نسخه سیاست تقسیم می‌شوند. فقط انواع `counts_against_balance` اثر دارند. `LeaveEntitlement` projection تخصیص است؛ مدل و triggerهای DB نوشتن تخصیص بدون posting متناظر را رد می‌کنند و تغییر/حذف رویدادهای دفترکل ممنوع است. اختلاف projection و دفترکل reconciliation failure محسوب می‌شود.

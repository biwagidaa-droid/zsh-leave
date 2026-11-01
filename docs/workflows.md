# گردش کار و ماشین وضعیت

## انتقال‌های مجاز (تنها مسیر: `LeaveRequestService`)
| از | رویداد | به | شرط/اثر |
|----|--------|----|---------|
| — | ثبت | PENDING | یا APPROVED اگر نوع requires_approval=false؛ یا ESCALATED اگر مدیر ندارد/غایب است |
| PENDING | تأیید مدیر | APPROVED | مدیر همان snapshot؛ نوع محرمانه ممنوع؛ روز کاری بازبینی شود |
| PENDING/ESCALATED | رد | REJECTED | دلیل اجباری |
| PENDING | ویرایش کارمند | PENDING | در جا + اعلان مجدد |
| PENDING/ESCALATED | لغو کارمند | CANCELLED | بدون اثر مانده |
| PENDING | timeout | ESCALATED | `UPDATE … WHERE status='PENDING'` شرطی (race-safe) |
| ESCALATED | تأیید HR | APPROVED | |
| APPROVED | درخواست ویرایش | (درخواست جدید PENDING با supersedes) | فقط یک اصلاح فعال؛ 409 در تلاش دوم |
| جدید(supersedes) | تأیید | APPROVED؛ اصل → CANCELLED | یک تراکنش؛ مانده یک‌بار محاسبه |
| جدید(supersedes) | رد | REJECTED؛ اصل APPROVED می‌ماند | |
| APPROVED | درخواست لغو | WITHDRAWAL_PENDING | ممنوع اگر اصلاح فعال دارد (409) |
| WITHDRAWAL_PENDING | تأیید | CANCELLED | مانده آزاد می‌شود |
| WITHDRAWAL_PENDING | رد | APPROVED | |
| هر وضعیت | HR override | طبق مجوز | دلیل اجباری، حسابرسی |
| — | ثبت HR | APPROVED | بدون مسیر تأیید؛ نوع‌های HR-only |

حالت‌های پایانی: REJECTED، CANCELLED.

## اعتبارسنجی ثبت
start≤end؛ روز کاری مثبت؛ سازگاری با طول بازه؛ عدم هم‌پوشانی طبق سیاست؛ جانشین فعال، غیر از خود؛ نوع enabled و employee_requestable؛ گذشته‌نگر طبق سیاست؛ مانده منفی هشدار نه مسدود (مگر سیاست).

## Jobها (idempotent، ثبت در BackgroundJobExecution)
1. **Reminder** روزانه: به مدیر پیش از مهلت؛ کلید dedupe روزانه.
2. **Escalation** ساعتی: ارجاع شرطی؛ مدیر غایب هم لحاظ می‌شود.
3. **YearRollover** روزانه: فقط یک‌بار در سال به‌ازای (کارمند,نوع,سال) با کلید idempotency؛ انقضای مانده انتقالی.
4. **Retention** (اختیاری) طبق سیاست.
مهلت‌ها «روز کاری» محاسبه می‌شوند (تعطیلات در نظر گرفته می‌شوند).

## نقشه آزمون
هر ردیف جدول بالا حداقل یک تست واحد + یک تست هم‌زمانی/مجوز دارد (testing.md).

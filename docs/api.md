# API (v1) — طراحی اولیه

پایه: `/api/v1/`، JSON، نشست+CSRF (و توکن برای یکپارچه‌سازی بعدی)، صفحه‌بندی `?page&page_size` (حداکثر ۱۰۰)، مرتب‌سازی `?ordering=`، خطا: `{ "code", "message_fa", "fields": {} }`. مستند OpenAPI از drf-spectacular در `/api/v1/schema/`. مسیرهای Auth پیاده‌سازی شده‌اند؛ سایر مسیرهای این سند طراحی هستند مگر آنجا که در قرارداد API وضعیت اجرا مشخص شده باشد.

| گروه | Endpoint | روش | نقش‌ها | نکات |
|------|----------|-----|--------|------|
| Auth | `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/password` | POST/GET | همه | پیاده‌سازی‌شده؛ نشست، CSRF، محدودسازی ورود و ثبت تلاش ناموفق |
| Account activation | `/auth/activate` | POST | عمومی، با توکن یک‌بارمصرف | تنظیم رمز با validator جنگو، تطبیق ایمیل و محدودسازی نرخ؛ پاسخ خطا عمومی |
| Users/Employees | `/employees/`, `/employees/{id}/` | GET/POST/PATCH | HR، مدیر (فقط خواندنِ زیرمجموعه)، سامانه | scope؛ `siteId` اختیاری و اعتبارسنجی‌شده در نوشتن؛ `siteId` و `siteName` در خروجی |
| Employee invitations | `/employees/{id}/invitation/`, `/invitation/revoke`, `/suspend` | POST | HR دامنه‌دار، مدیر سامانه | ارسال/ارسال مجدد، لغو دعوت یا تعلیق؛ توکن قبلی باطل می‌شود؛ بدون Frontend |
| Organization | `/companies/`, `/departments/`, `/positions/`, `/sites/`, `/sites/{id}/` | GET/POST/PATCH؛ حذف سایت فقط در نبود وابستگی | مدیر سامانه؛ HR شرکتی برای سایت‌های همان شرکت | شرکت والد مستقیم سایت است؛ مالکیت سایت تغییرناپذیر؛ بایگانی با `isActive=false`؛ حذف دارای وابسته ممنوع |
| Contracts | `/employees/{id}/contract-periods/` | GET/POST | HR | عدم هم‌پوشانی بازه |
| Leave types | `/leave-types/` | GET؛ POST/PATCH | همه (فیلترشده)؛ HR/سامانه | نوع محرمانه برای غیر HR حذف می‌شود |
| Requests | `/leave-requests/` GET/POST؛ `/{id}/` GET/PATCH؛ `/{id}/approve|reject|cancel|withdraw|amend` POST | | طبق ماتریس | پیاده‌سازی Phase D؛ همه نوشتن‌ها Idempotency-Key دارند؛ انتقال، اصلاح، رویداد و Audit اتمیک |
| HR record | `/hr/absences/` POST | | HR دامنه‌دار | ایجاد مستقیم در وضعیت `APPROVED`؛ `Idempotency-Key` الزامی؛ رویداد ثبت و اثر دفترکل در همان تراکنش |
| Comments | `/leave-requests/{id}/comments/` | GET/POST | طرفین مجاز | پیاده‌سازی‌شده؛ ممنوع برای نوع محرمانه غیر HR |
| Event history | `/leave-requests/{id}/events/` | GET | مالک، مدیر snapshot، HR مجاز | پیاده‌سازی‌شده؛ دلیل رویداد محرمانه فقط برای HR |
| Attachments | `/leave-requests/{id}/attachments/` POST؛ `/attachments/{id}/download` GET | | HR/مالک مجاز | هر دانلود ثبت می‌شود |
| Balances | `/balances/?year=&employee=` | GET | کارمند خود؛ مدیر زیرمجموعه؛ HR | |
| Entitlements | `/entitlements/` CRUD؛ `/{id}/adjust` POST؛ `/import/?dry_run=` POST | | HR | adjust با `reason`؛ import با ImportBatch |
| Estimate | `/working-days/estimate?employee&start&end` | GET | کارمند/HR | خروجی برچسب `estimated:true` |
| Coverage | `/coverage/?from&to&department` | GET | مدیر/HR | شمارش بدون افشای نوع |
| Calendar | `/calendar/events/?from&to&scope=me|team|org` | GET | طبق scope | redacted |
| Holidays | `/holidays/` CRUD؛ `/holidays/import|export` | | مشاهده همه؛ مدیریت HR | تاریخچه |
| Notifications | `/notifications/` GET؛ `/{id}/read` POST | | مالک | |
| Reports | `/reports/balances|absences|trends|process-health|bradford` | GET | HR (scope)؛ ارشد (تجمیعی) | |
| Exports | `/exports/{report}.csv|xlsx` | GET | همان مجوز گزارش | ضد Formula Injection |
| Admin | `/admin/settings/`, `/admin/roles/`, `/admin/jobs/` | | مدیر سامانه | تغییر → Audit |
| Audit | `/audit/events/` | GET | سامانه، HR مجاز | فقط خواندن |
| Health | `/health/live`, `/health/ready` | GET | عمومی (بدون جزئیات حساس) | شامل DB و آخرین اجرای Job |

برای قرارداد جزئی ورودی، پاسخ، خطاها و حسابرسی API، به `api/api-contract.md` مراجعه کنید.

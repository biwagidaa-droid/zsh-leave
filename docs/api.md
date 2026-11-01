# API (v1) — طراحی اولیه

پایه: `/api/v1/`، JSON، نشست+CSRF (و توکن برای یکپارچه‌سازی بعدی)، صفحه‌بندی `?page&page_size` (حداکثر ۱۰۰)، مرتب‌سازی `?ordering=`، خطا: `{ "code", "message_fa", "fields": {} }`. مستند OpenAPI از drf-spectacular در `/api/v1/schema/`. وضعیت: طراحی‌شده، پیاده‌سازی‌نشده.

| گروه | Endpoint | روش | نقش‌ها | نکات |
|------|----------|-----|--------|------|
| Auth | `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/password` | POST/GET | همه | Rate limit؛ ثبت ورود ناموفق |
| Users/Employees | `/employees/`, `/employees/{id}/` | GET/POST/PATCH | HR، مدیر (فقط خواندنِ زیرمجموعه)، سامانه | scope؛ جستجوی جانشین `/employees/search` فقط افراد فعال و مجاز |
| Organization | `/companies/`, `/departments/`, `/positions/` | CRUD | مدیر سامانه | ممنوعیت حذف دارای وابسته |
| Contracts | `/employees/{id}/contract-periods/` | GET/POST | HR | عدم هم‌پوشانی بازه |
| Leave types | `/leave-types/` | GET؛ POST/PATCH | همه (فیلترشده)؛ HR/سامانه | نوع محرمانه برای غیر HR حذف می‌شود |
| Requests | `/leave-requests/` GET/POST؛ `/{id}/` GET/PATCH؛ `/{id}/approve|reject|cancel|withdraw|amend|escalate` POST | | طبق ماتریس | همه انتقال‌ها از سرویس؛ reject با `reason`؛ 409 برای تعارض |
| HR record | `/hr/absences/` POST/PATCH | | HR | مستقیم APPROVED |
| Comments | `/leave-requests/{id}/comments/` | GET/POST | طرفین مجاز | ممنوع برای نوع محرمانه غیر HR |
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

برای هر endpoint هنگام پیاده‌سازی: ورودی، پاسخ، خطاها و رویداد حسابرسی در OpenAPI تکمیل می‌شود.

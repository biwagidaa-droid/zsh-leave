# سیاست و عملیات اعلان‌های ZSH Leave

## موجودی مسیرها

| رخداد | منبع واقعی | in-app | email خارج از سامانه |
|---|---|---|---|
| ثبت درخواست کارکنان | `LeaveRequestEvent: submit` از سرویس workflow | بله؛ از event feed | صف می‌شود برای کارمند، مدیر جاری و HR دارای scope؛ actor حذف می‌شود |
| ثبت غیبت توسط HR | همان `submit` با `origin=hr` | بله | مانند ثبت درخواست؛ فقط کاربران مجاز فعلی، به‌جز actor |
| تأیید/رد | `approve` و `reject` | بله | اعلان generic برای مخاطبان مجاز |
| لغو/درخواست لغو/تصمیم آن | `cancel`، `hr_cancel`، `request_withdraw`، `approve_withdraw`، `reject_withdraw` | بله | اعلان generic برای مخاطبان مجاز |
| اصلاح/اصلاحیه | `correct`، `amend`، `amend_approve` و `amendment_approve/reject` | بله | اعلان generic برای مخاطبان مجاز؛ eventهای فقط توضیح/comment در email نیستند |
| دعوت | `EmployeeInvitation` و AuditEvent | خیر؛ دعوت، feed درخواست نیست | فوری از provider مشترک ارسال می‌شود. توکن خام برای retry در DB ذخیره نمی‌شود؛ موفقیت فقط وقتی `send_email` یک پیام را به backend بسپارد، `sent` محسوب می‌شود؛ خطا وضعیت را pending نگه می‌دارد |
| فعال‌سازی موفق | AuditEvent `activation.succeeded` و invitation مصرف‌شده | خیر | ایمیل تأیید بدون لینک/جزئیات از outbox؛ token یا رمز در آن نیست |
| یادآوری مدیر برای درخواست معوق | event `reminder` و قید idempotency در `JobEffect` | بله | outbox نیز ساخته می‌شود؛ job retry باعث event/email تکراری نمی‌شود |
| ارجاع درخواست معوق | event `escalate` | بله | اعلان generic برای مخاطبان مجاز فعلی |
| تخصیص اولیه سهمیه، اصلاح، انتقال و انقضا | `EntitlementEvent` از ledger | در feed فعلی درخواست نیست | اعلان generic برای کارمند مالک حساب؛ هیچ مقدار/نوع محرمانه در متن نیست |
| تقویم، تغییر policy، تعلیق/خاتمه، خطای فعال‌سازی، رویدادهای Audit عمومی | Audit/history موجود | بسته به endpoint خودشان؛ NotificationRead برای آن‌ها وجود ندارد | email صف نمی‌شود مگر یکی از رخدادهای مشخص بالا |

**تفکیک کانال:** in-app بر eventهای درخواست و جدول `NotificationRead` تکیه دارد؛ وجود event یا read marker فقط ثبت/خوانده‌شدن داخل سامانه است. ایمیل از `NotificationDelivery` و backend Django استفاده می‌کند. در کد provider برای push notification یا SMS وجود ندارد. SMTP در این پروژه webhook/bounce را ارائه نمی‌کند، بنابراین وضعیت `delivered` به‌طور خودکار ثبت نمی‌شود.

## حریم خصوصی و مخاطبان

پیام‌های درخواست و سهمیه عمداً generic هستند: کاربر باید وارد سامانه شود تا محتوای مجاز را ببیند. subject/body ایمیل شامل نوع مرخصی، دلیل، توضیح تصمیم، تاریخ، مدت، اطلاعات پزشکی یا نام کارمند دیگر نیست. invitation تنها پیام دارای activation URL است؛ URL فقط در لحظه ارسال ساخته می‌شود، raw token در outbox یا log ذخیره نمی‌شود و link به وضعیت همان دعوت متصل است.

مخاطب درخواست از DB در زمان event پیشنهاد می‌شود، ولی پیش از هر ارسال دوباره اعتبارسنجی می‌شود: کارمند باید همان employee فعال باشد؛ مدیر باید هنوز مدیر جاری همان کارمند باشد؛ HR باید role assignment فعال و scope منطبق فعلی داشته باشد. snapshot مدیر تاریخی به‌تنهایی مجوز ایمیل نیست. مدیرِ فاقد HR برای درخواست confidential حذف می‌شود؛ HR فقط در scope مجاز می‌ماند. user غیرفعال، خارج از اشتغال، بدون ایمیل یا فاقد دسترسی جاری وضعیت `unavailable` می‌گیرد و ارسال نمی‌شود. actor هر event از گیرندگان همان event حذف می‌شود.

## وضعیت و تلاش مجدد

`NotificationDelivery.status` معناهای زیر را دارد:

| وضعیت | معنی |
|---|---|
| `queued` | برای ارسال آماده یا منتظر retry است؛ هنوز ارسال ادعا نمی‌شود |
| `sending` | worker این رکورد را claim کرده است |
| `sent` | email backend یک پیام را پذیرفته است؛ **به معنی تحویل به inbox نیست** |
| `delivered` | فقط اگر provider آینده receipt معتبر تحویل ارائه کند قابل ثبت است؛ در اتصال فعلی خودکار تولید نمی‌شود |
| `failed` | رد قطعی/permanent یا تمام‌شدن retryها؛ ارسال خودکار تمام شده است |
| `unavailable` | provider تنظیم نیست، هویت/مجوز مقصد از بین رفته، یا نتیجهٔ ارسال نامعلوم است؛ ارسال ادعا نشده و مورد مبهم خودکار تکرار نمی‌شود |

کلید یکتای idempotency برای هر event و recipient جلوی fanout تکراری را می‌گیرد. job نیز با `(job_name, scheduled_for)` یکتا است؛ delivery موفق در replay دوباره فرستاده نمی‌شود. برای provider error صریح 4xx SMTP، حداکثر ۳ تلاش با فاصلهٔ ۵ و ۱۵ دقیقه انجام می‌شود. خطای دائمی `failed` می‌شود. قطع ارتباطی که ممکن است پس از پذیرش provider رخ داده باشد `unavailable/DeliveryOutcomeUnknown` می‌شود، نه retry؛ این انتخاب duplicate را کم می‌کند اما ممکن است نیازمند بررسی دستی باشد. رکورد `sending` که lease پانزده‌دقیقه‌ای آن منقضی شود نیز `unavailable` می‌شود تا ایمیل مبهم کورکورانه تکرار نشود.

Worker هر پنج دقیقه و به‌صورت پیش‌فرض حداکثر ۵۰ پیام در هر اجرا را پردازش می‌کند. `ZSH_NOTIFICATION_BATCH_LIMIT` بازهٔ ۱ تا ۵۰۰ دارد. این حد، سقف محلی است؛ rate limit provider، quota ساعتی و bounce باید در تنظیمات سرویس ایمیل سازمان نیز اعمال/پایش شوند. job در `run_scheduled_jobs` و قفل/ثبت اجرای DB موجود ادغام شده است. وضعیت aggregate را بدون نمایش ایمیل/گیرنده ببینید:

```sh
cd backend
DJANGO_SETTINGS_MODULE=config.settings_prod python manage.py notification_delivery_status
DJANGO_SETTINGS_MODULE=config.settings_prod python manage.py run_scheduled_jobs
```

برای مشاهده retryها/آخرین خطا، دسترسی مستقیم فقط‌خواندنی به جدول delivery را با نقش عملیاتی محدود به کار ببرید؛ recipient را در log/ticket کپی نکنید. `last_error_code` فقط کد امن است، نه متن exception یا credential.

## پیکربندی و محیط توسعه

Production از environment امن یا secret manager استفاده کند؛ هیچ credential در source, database delivery payload، مستند عمومی یا log قرار نگیرد:

- `ZSH_EMAIL_ENABLED=1` برای opt-in صریح ارسال
- `ZSH_EMAIL_BACKEND`؛ پیش‌فرض production Django SMTP است
- `ZSH_EMAIL_HOST`, `ZSH_EMAIL_PORT`, `ZSH_EMAIL_USER`, `ZSH_EMAIL_PASSWORD`
- `ZSH_EMAIL_USE_TLS` یا `ZSH_EMAIL_USE_SSL`؛ هم‌زمانی هر دو مجاز نیست
- `ZSH_DEFAULT_FROM_EMAIL` و `ZSH_PUBLIC_BASE_URL`؛ برای دعوت، URL باید HTTPS باشد
- `ZSH_NOTIFICATION_BATCH_LIMIT` اختیاری؛ پیش‌فرض ۵۰، بازهٔ ۱ تا ۵۰۰

در development، backend پیش‌فرض `locmem` و `ZSH_EMAIL_ENABLED` پیش‌فرض خاموش است؛ پیام واقعی ارسال نمی‌شود مگر operator هم backend خارجی و هم enablement را عمداً تنظیم کند. از console backend برای دعوت استفاده نکنید چون activation link را چاپ می‌کند. Testها provider را با locmem یا mock کنترل می‌کنند.

## محدودیت‌های provider و عملیات

Provider فعلی adapter نازکی بر Django email backend است؛ SMTP acceptance فقط `sent` ثبت می‌کند. SMTP DSN, provider webhook, bounce/complaint processing، provider-side idempotency key، push و SMS در repository پیاده نشده‌اند. تا زمان ادغام provider دارای event امضاشده، هیچ receipt یا bounce را حدس نزنید. خطای provider با کد ثابت/کلاس exception ثبت می‌شود و متن خام exception، credential و body پیام ذخیره نمی‌شوند.

دعوت به علت وجود secret یک‌بارمصرف در متن، با provider مشترک در همان درخواست ارسال می‌شود و retry jobی ندارد؛ ارسال مجدد از endpoint دعوت، invitation قبلی را revoke و token تازه می‌سازد. ایمیل‌های workflow و activation confirmation در outbox صف می‌شوند. این تفاوت عمدی است تا activation token خام داخل DB قابل بازیابی قرار نگیرد.

آزمون هدفمند:

```sh
cd backend
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test \
  leave.tests.test_notification_delivery \
  leave.tests.test_invitations \
  leave.tests.test_scheduled_jobs \
  leave.tests.test_frontend_api
```

این integration از PostgreSQL/SMTP واقعی استفاده نمی‌کند؛ backend، رسید واقعی تحویل و bounce در محیط production باید جداگانه با provider منتخب آزموده شوند.

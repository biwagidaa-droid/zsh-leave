# راهنمای مدیر سامانه و عملیات

نقش `admin`، پیکربندی فنی و ساختار را مدیریت می‌کند اما در `scoped_leave_requests` به درخواست فردی دسترسی ندارد. `is_superuser` نیز admin می‌شود؛ دسترسی داده مرخصی با مجوز HR برابر نیست.

## پیکربندی و نصب محلی

متغیرهای خوانده‌شده در settings:

| متغیر | کاربرد |
|---|---|
| `ZSH_ENV` | در `config/settings.py` برای انتخاب module dev/test/prod استفاده می‌شود؛ پیش‌فرض `development` است |
| `ZSH_DEBUG` | settings پایه DEBUG؛ `settings_dev` آن را روی True بازنویسی می‌کند |
| `ZSH_SECRET_KEY` | کلید Django؛ production لازم و حداقل ۵۰ نویسه |
| `ZSH_ALLOWED_HOSTS` | فهرست comma-separated؛ production غیرخالی لازم |
| `ZSH_DB_ENGINE`, `ZSH_DB_NAME`, `ZSH_DB_USER`, `ZSH_DB_PASSWORD`, `ZSH_DB_HOST`, `ZSH_DB_PORT` | اتصال settings_base |
| `ZSH_CSRF_TRUSTED_ORIGINS` | فهرست originهای trusted |
| `ZSH_USE_SQLITE` | override خاص `settings_dev.py`; `1` SQLite |

نمونه `.env.example` شامل مقدارهای صرفاً توسعه است و Django dotenv loader در مخزن دیده نشد. `settings_prod.py` PostgreSQL را اجباری می‌کند و password DB می‌خواهد. کلیدها را در مستند، Git یا log قرار ندهید.

`config/settings.py` یک wrapper واقعی است که `ZSH_ENV` را به `settings_dev`, `settings_test` یا `settings_prod` نگاشت می‌کند؛ مقدار ناشناخته نیز به development می‌افتد. برای فرمان‌های عملیاتی settings را صریح تعیین کنید تا تصادفاً development انتخاب نشود:

```bash
cd backend
ZSH_USE_SQLITE=1 DJANGO_SETTINGS_MODULE=config.settings_dev python3 manage.py migrate
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test
```

برای production می‌توان `ZSH_ENV=production` را به wrapper داد یا `DJANGO_SETTINGS_MODULE=config.settings_prod` را مستقیم تعیین کرد. `.env.example` خودکار بارگذاری نمی‌شود. خود deployment/runner و secret management باید جداگانه فراهم و در محیط هدف آزموده شوند. هیچ `createsuperadmin` یا `seed_demo` command در repository یافت نشد.

## مدیریت کاربر، نقش و سازمان

- کاربران Django و EmployeeProfile به‌صورت جداگانه مدیریت می‌شوند. UI مدیریت employee هنگام ایجاد حساب، نام کاربری تولید و password unusable می‌گذارد؛ provisioning/login امن برای آن باید سازمانی تعریف شود. در `authorization_context`، `end_date` به‌تنهایی نقش employee را نمی‌بندد؛ خاتمه دسترسی باید با غیرفعال‌سازی حساب یا `is_employee=False` نیز همراه باشد.
- نقش‌ها در `RoleAssignment` هستند: admin-global؛ HR شرکت/سایت/واحد/کارمند؛ exec شرکت/سایت/واحد. manager از رابطه مستقیم EmployeeProfile به دست می‌آید.
- endpoint admin نقش‌ها `/api/v1/admin/role-assignments/` و جزئیات DELETE دارد؛ UI/متد frontend وجود ندارد. اعطای نقش به خود ممنوع، grant/revoke ممیزی و لغو آخرین admin برای actor غیر-superuser ممنوع است.
- company/department از UI سازمانی مدیریت‌پذیر است؛ سایت‌مدیریت UI جدا ندارد. رکوردها را فقط در سازمان/داده واقعی پس از اعتبارسنجی مرجع بسازید.

## امنیت، نشست و تنظیمات کسب‌وکار

`SessionAuthentication`, `CsrfViewMiddleware`, `HttpOnly`, `SameSite=Lax`, cookie secure در non-debug، throttleها، گذرواژه minimum 12 و Argon2 در settings هستند. `settings_prod.py` HTTPS redirect/HSTS را فعال می‌کند. TLS خود سرویس، proxy headerها، سیاست TLS cipher، CSP، rate-limit در لبه و WAF در مخزن تعریف نشده‌اند؛ با استقرار واقعی آزمون شوند.

تنظیمات schema-backed در «تنظیمات سامانه» یا GET/POST `/api/v1/admin/settings/` موجودند؛ تغییر با دلیل audit می‌شود. هر تنظیم مقدار مجاز خودش را در `zsh_core/settings_schema.py` دارد. محرمانگی `privacy.*`, حداقل گروه، تنظیمات سیاست/گردش کار را خارج از تصمیم مالک محصول تغییر ندهید.

## مهاجرت، DB، فایل و بازیابی

- مهاجرت‌های `backend/leave/migrations/0001_initial.py` تا `0011_request_attachments.py` منبع schema هستند.
- پیش از migration، backup و نسخه DB را ثبت کنید؛ در pre-prod همان migrationها را روی PostgreSQL واقعی/نسخه سازگار آزمایش کنید.
- SQLite برای آزمون سبک است؛ قیود `nulls_distinct` و trigger/locking PostgreSQL را کامل تضمین نمی‌کند.
- فایل پیوست در `MEDIA_ROOT` محلی ذخیره می‌شود. استراتژی volume/object storage، رمزگذاری در حالت سکون، retention و نسخه پشتیبان فایل به‌صورت deployment موجود نیست.
- دستور pg_dump/restore، retention، کلید رمزگذاری، restore runbook یا backup خودکار در repository تعریف نشده؛ دستور عمومی امن را تا انتخاب نسخه/زیرساخت سازمانی توصیه نمی‌کنیم.

## لاگ، سلامت و عیب‌یابی

`LOGGING` console-based و Django/leave سطح INFO است. Login رویداد audit می‌نویسد و failure پیام generically log می‌شود. سامانه log aggregation، alert، retention و redaction مرکزی را در مخزن پیکربندی نکرده است. `/api/v1/health/` وضعیت زنده و `/api/v1/ready/` اتصال `SELECT 1` را گزارش می‌دهد؛ readiness آزمون migration، worker، storage یا mail نیست. صفحه Jobs از `/api/v1/admin/jobs/` مقدار خالی می‌گیرد.

| مشکل | بررسی |
|---|---|
| برنامه با تنظیمات development اجرا شده است | `ZSH_ENV` را در محیط همان process روی `production` بگذارید یا `DJANGO_SETTINGS_MODULE=config.settings_prod` را صریح تعیین کنید؛ `config.settings` در نبود `ZSH_ENV` به development برمی‌گردد |
| شکست ستون یا schema SQLite | دیتابیس disposable بسازید و migration/test runner صحیح اجرا کنید؛ schema را دستی patch نکنید |
| API 403/404 | نقش، scope RoleAssignment، EmployeeProfile، شرکت و manager snapshot را بررسی کنید |
| 409 سهمیه | دفترکل و projection را از طریق سرویس/reconciliation مجاز بررسی؛ Event را مستقیم اصلاح نکنید |
| نشست/CSRF | cookie jar، `X-CSRFToken`, HTTPS و same-site/proxy را بررسی کنید |
| upload ناموفق | فایل غیرخالی و حداکثر ۱۰ MiB باشد؛ پسوند/Content-Type/signature را تطبیق دهید و دسترسی `MEDIA_ROOT` را بررسی کنید |

## استقرار و عملیات بازیابی

Docker/Compose، CI/CD، reverse proxy، scheduler، worker و فرآیند restore عملی در مخزن وجود ندارد. `gunicorn` در dependency است. نمونه فرمان اجرای WSGI با فرض آماده‌بودن environment و DB:

```bash
cd backend
ZSH_ENV=production gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

این نمونه جایگزین تنظیم TLS/reverse proxy، secret manager، media persistence، migration sequencing، backup/restore، health probes یا تأیید استقرار نیست. پیش از deploy، مسئول هر مورد و روش آزمون آن را تعیین کنید. سند [۰۹](09-production-readiness-checklist.md) gateهای پذیرش را فهرست می‌کند.

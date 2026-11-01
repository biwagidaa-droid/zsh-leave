# استقرار، پشتیبان‌گیری، بازیابی

وضعیت: طراحی؛ **هیچ‌کدام در این محیط اجرا نشده** (Docker/PostgreSQL در دسترس نیست).

## سرویس‌ها (Docker Compose)
`db` (PostgreSQL، volume)، `backend`، `worker` (Jobها)، `proxy` (TLS)، `redis` فقط در صورت نیاز. تنظیمات از `.env` (نمونه `.env.example` بدون راز واقعی).

## نصب
1. کپی `.env.example` → `.env` و تنظیم SECRET_KEY، DB، ALLOWED_HOSTS و SMTP. پیکربندی SMTP برای ارسال دعوت کارکنان در production لازم است؛ راهنمای متغیرها در [چرخه عمر حساب کارمند](./account-lifecycle-fa.md) است.
2. `docker compose up -d --build`
3. `docker compose exec backend python manage.py migrate`
4. `docker compose exec backend python manage.py createcachetable zsh_cache` برای cache مشترک محدودسازی درخواست.
5. ایجاد مدیر سامانه با `createsuperadmin`.
6. بارگذاری داده نمونه فقط در Demo (`seed_demo`).

## پشتیبان‌گیری
`pg_dump -Fc` شبانه + کپی volume پیوست‌ها؛ رمزگذاری با کلید جدا؛ نگهداری چرخشی.

## بازیابی (باید در محیط جدا آزمون شود)
ایجاد DB خالی → `pg_restore` → بازگردانی volume فایل‌ها → `migrate --check` → Health → مقایسه شمارش رکوردها و مجموع مانده با قبل از پشتیبان. گزارش آزمون در `docs/test-report.md`.

## پیش‌نیازهای شبکه داخلی
گواهی TLS داخلی، SMTP داخلی (OQ-13)، دسترسی ذخیره‌سازی/پشتیبان، DNS، فهرست کاربران اولیه و ساختار سازمانی (OQ-11)، مالک سیاست مرخصی در HR.

در production، `ZSH_EMAIL_ENABLED=1`، `ZSH_EMAIL_HOST`، `ZSH_DEFAULT_FROM_EMAIL` و `ZSH_PUBLIC_BASE_URL` با HTTPS را از secret manager/config امن سرویس تنظیم کنید. اگر ارائه‌دهنده آماده نباشد، دعوت در وضعیت pending می‌ماند و API خطای ارسال را اعلام می‌کند؛ هرگز `ZSH_INVITATION_EXPOSE_DEV_LINKS` را در production فعال نکنید.

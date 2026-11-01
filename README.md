# سامانه مدیریت مرخصی ZSH

این مخزن شامل رابط React/TypeScript و API مبتنی بر Django REST Framework برای مدیریت درخواست‌های مرخصی، تقویم کاری، مجوزهای سازمانی و دفترکل سهمیه است. این README راه‌اندازی توسعه و فرمان‌های آزمون را معرفی می‌کند؛ تأیید آمادگی تولید نیست.

## اجزای مخزن

- `backend/leave/`: مدل‌های Django، API، مجوزها، گردش‌کار، تقویم و سرویس دفترکل.
- `backend/zsh_core/`: منطق دامنه مستقل از Django، شامل تاریخ شمسی، روزکاری، workflow، گزارش‌ها و ورود/خروج داده.
- `backend/leave/migrations/`: مهاجرت‌های schema از `0001_initial` تا `0011_request_attachments`.
- `frontend/src/`: رابط React، مسیرها، صفحات و کلاینت API.
- [مستندات نهایی](docs/final-documentation/README.md): راهنماهای کاربران، ماتریس مجوز، دفترچه آزمون و ارزیابی آمادگی تولید.

## پیش‌نیاز

Python سازگار با `backend/requirements.txt` و Node/npm سازگار با `frontend/package-lock.json` لازم است. برای توسعه محلی:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

تنظیم `config.settings` از متغیر `ZSH_ENV` استفاده می‌کند و بدون آن به development برمی‌گردد. فایل `.env.example` خودکار بارگذاری نمی‌شود. نمونه راه‌اندازی محلی با SQLite:

```bash
cd backend
ZSH_ENV=development ZSH_USE_SQLITE=1 python3 manage.py migrate
ZSH_ENV=development ZSH_USE_SQLITE=1 python3 manage.py runserver
```

در ترمینال جداگانه، رابط را اجرا کنید:

```bash
cd frontend
npm run dev
```

Vite مسیر `/api` را به `http://127.0.0.1:8000` proxy می‌کند. این تنظیم برای توسعه محلی است، نه استقرار تولید.

## آزمون و build

از ریشه مخزن:

```bash
cd backend
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py check
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py makemigrations --check --dry-run
cd ../frontend
npm test
npm run build
```

در اجرای این ممیزی: آزمون Backend شامل ۱۷۶ مورد بود (۱۷۳ موفق، ۳ مورد PostgreSQL-only ردشده در SQLite)، آزمون Frontend شامل ۳۴ مورد موفق بود، `check` بدون مشکل و `makemigrations --check --dry-run` بدون تغییر بود؛ build فرانت‌اند نیز موفق شد. هشدار SQLite درباره پشتیبانی‌نکردن قید `nulls_distinct` باقی است؛ این نتایج آزمون PostgreSQL یا محیط production محسوب نمی‌شوند.

## استقرار

تنظیمات production در `config.settings_prod` قرار دارد و به PostgreSQL، کلید معتبر و `ZSH_ALLOWED_HOSTS` نیاز دارد. این مخزن manifest استقرار، CI/CD، reverse proxy، backup/restore یا پایش عملیاتی فراهم نمی‌کند. قبل از استفاده واقعی، [چک‌لیست آمادگی تولید](docs/final-documentation/09-production-readiness-checklist.md) و [راهنمای مدیر سامانه](docs/final-documentation/06-system-administrator-guide.md) را بررسی و همه gateهای محیط هدف را با شواهد ببندید.

## وضعیت اصلاحات مهندسی

گزارش baseline، شواهد آزمون، محدودیت‌ها و وضعیت gateهای این remediation در [مستندات اصلاح](docs/remediation/PROGRESS.md) نگهداری می‌شود. نتایج فعلی به معنی آمادگی production نیست.

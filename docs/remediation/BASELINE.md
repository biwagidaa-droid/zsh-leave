# خط مبنا و کشف مخزن

## معماری مشاهده‌شده

- Backend در `backend/` یک Django 5.2 + Django REST Framework است. `backend/leave/` مدل‌ها، API، مجوزها، سرویس و مهاجرت‌ها را دارد؛ منطق دامنه مستقل‌تر در `backend/zsh_core/` قرار دارد.
- تنظیمات در `backend/config/` به development، test و production تقسیم شده‌اند. پایگاه داده هدف production PostgreSQL است؛ تنظیم آزمون فعلی SQLite است.
- Frontend یک SPA با React 18، TypeScript، Vite و React Router در `frontend/src/` است. کلاینت API واقعی در `frontend/src/api/http.ts` و adapter نمایشی در `frontend/src/api/demo.ts` قرار دارد.
- تاریخچه مهاجرت در زمان شروع تا `0011_request_attachments` بود. مهاجرتی در این فاز اضافه یا تغییر داده نشد.
- احراز هویت نشست/CSRF است. `leave.authorization` زمینه نقش و دامنه سازمانی را از کاربر و انتساب‌های جاری می‌سازد.
- مستند معماری می‌گوید scheduler/worker پس‌زمینه هنوز پیاده‌سازی نشده است؛ endpoint مدیریت Job نیز در حال حاضر `[]` برمی‌گرداند.
- راهنمای مخزن و اسناد فنی موجودند؛ هیچ `AGENTS.md` یا دستور پروژه‌ای جداگانه‌ای در فهرست فایل‌های ردیابی‌شده یافت نشد.

## محیط شروع و دستورات

محیط ثبت‌شده: Python 3.14.2، Django 5.2.18، Node 24.22.2، npm 11.19.1. وابستگی‌های Python شامل Django، DRF، psycopg و openpyxl در محیط موجود بودند؛ `frontend/node_modules` برای اجرای npm حاضر بود.

فرمان‌های اجراشده از ریشه مناسب:

```bash
cd backend
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py check
DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py makemigrations --check --dry-run

cd frontend
npm test
npm run build
```

نتیجه خط مبنای پیش از تغییر: Backend، ۱۷۶ تست، موفق، ۳ ردشده به‌علت نیاز به PostgreSQL؛ Frontend، ۳۴ تست موفق؛ build شامل `tsc --noEmit` و Vite موفق؛ Django check و migration drift موفق.

## محدودیت‌های خط مبنا

- آزمون‌های Backend با SQLite اجرا می‌شوند. هشدار `models.W047` درباره عدم پشتیبانی SQLite از unique constraint با `nulls_distinct` دیده شد.
- `pg_isready` در محیط نصب نبود؛ PostgreSQL production در این فاز اجرا/تأیید نشده است. سه آزمون هم‌زمانی و trigger در کلاس `PostgreSQLEntitlementConcurrencyTests` صریحاً فقط روی PostgreSQL اجرا می‌شوند.
- اسکریپت lint جداگانه در manifest فرانت‌اند وجود ندارد. build بررسی TypeScript را اجرا می‌کند.
- دستورات اولیه‌ای که از مسیر ریشه اجرا شدند به‌علت قرارداشتن `manage.py` و `package.json` در زیرپوشه‌ها اجرا نشدند؛ فرمان‌های اصلاح‌شده بالا نتیجه واقعی baseline هستند.

## یافته‌های تأییدشده از مسیر اجرای کد

1. مسیر `/api/v1/balances/` همه entitlementهای مشمول را به `_balance_json` می‌فرستاد؛ serializer کلید، برچسب، مانده و مبلغ confidential را برمی‌گرداند. `visible_balance_types` در منطق دامنه وجود داشت، اما در این مسیر API فراخوانی نمی‌شد.
2. `/api/v1/entitlements/` برچسب‌ها و مقادیر confidential را برمی‌گرداند و مسیر admin نیز مجاز بود؛ انتخاب کارمند از selector دارای bypass عمومی admin استفاده می‌کرد.
3. `/api/v1/reports/absences` گزارش را بر اساس `leave_type__label_fa` گروه‌بندی می‌کرد، بدون حذف نوع confidential. گزارش‌های executive نیز از شمارش کل درخواست‌ها استفاده می‌کردند.
4. `/api/v1/coverage/` تعداد افراد غایب در هر روز را برای مدیر و HR می‌شمرد؛ درخواست confidential از تجمیع مدیر حذف نمی‌شد.
5. `/api/v1/hr/absences/` هم `submit_request` و هم `apply_event(..., "approve")` را اجرا می‌کرد، در حالی که `initial_status` برای actor نوع HR وضعیت `APPROVED` می‌سازد. همچنین کلید تکرار در نبود header تصادفی می‌شد و payload اثرگذار `workingDays`/`replacementId` را fingerprint نمی‌کرد.

این مسیرها در فازهای ۱ و ۲ اصلاح و با آزمون API پوشش داده شدند. سایر حوزه‌های مأموریت هنوز baseline کامل و تکرارپذیر ندارند؛ وضعیتشان در `PROGRESS.md` و `KNOWN-LIMITATIONS.md` صریح است.

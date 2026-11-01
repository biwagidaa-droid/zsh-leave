# چک‌لیست اجرای اولین‌بار روی سرور (دارای Docker/Python/PostgreSQL)

این مراحل **در این محیط اجرا نشده‌اند**؛ نتیجه هر مرحله را برای ثبت در `test-report.md` بفرستید.

1. `python3 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt argon2-cffi`
2. تنظیم متغیرها: `ZSH_SECRET_KEY`, `ZSH_DB_PASSWORD`, `ZSH_DB_HOST`, (`ZSH_DEBUG=1` فقط توسعه)
3. `cd backend && python manage.py check` — هر خطا را عیناً بفرستید.
4. `python manage.py makemigrations leave && python manage.py migrate`
5. تست هسته (بدون DB): `python3 -m unittest discover -s tests -t .` (انتظار: 105 تست OK)
6. نسخه واقعی وابستگی‌ها: `pip freeze` → قفل نسخه؛ `pip-audit`.
7. گزارش خروجی هر مرحله (موفق/ناموفق) برای مرحله بعد.

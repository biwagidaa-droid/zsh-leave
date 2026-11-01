# ZSH Leave Management — سامانه مدیریت مرخصی و غیبت هلدینگ زکریا شیمی

- `docs/`: تحلیل، طراحی، تصمیم‌ها (`decisions.md`)، گزارش آزمون (`test-report.md`)، چک‌لیست سرور.
- `backend/zsh_core`: منطق خالص (تقویم شمسی، سیاست و سهمیه، روز کاری، مانده، ماشین وضعیت) — **105 تست اجراشده و موفق**.
- `backend/leave`, `backend/config`: اسکلت Django (مدل‌ها و سرویس‌ها) — **فقط نحو بررسی شده؛ اجرا نشده**.
اجرای تست‌ها: `cd backend && python3 -m unittest discover -s tests -t .`

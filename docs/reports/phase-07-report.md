# گزارش فاز ۰۷ — Jobها و اعلان‌ها

## الف) خلاصه اجرایی

فاز ۷ **اجرا نشده و مسدود است**. بک‌اند فاقد مدل Notification، صف/Worker/Scheduler، تاریخچه اجرایی Job، Outbox و APIهای اعلان است. منطق UI و Demo اعلان‌ها معادل سرویس واقعی یا اجرای پس‌زمینه پایدار نیست و به‌عنوان قابلیت عملیاتی گزارش نمی‌شود.

## ب) فایل‌های تغییرکرده

فایل عملیاتی مختص فاز ۷ در این نوبت تغییر نکرده است. گزارش و وضعیت فاز در اسناد roadmap/report ثبت شده‌اند. فایل حذف‌شده‌ای وجود ندارد.

## ج) دیتابیس

هیچ مدل Job، Notification، Delivery، Preference یا Outbox عملیاتی و هیچ Migration مربوط به فاز ۷ وجود ندارد.

## د) API

API واقعی برای Job Status/History/Retry/Trigger/Health یا Notification/Count/Read/Preferences وجود ندارد. Permission، Scope و نتیجه تست: قابل ارزیابی نیست؛ endpointی ایجاد نشده است.

## هـ) Frontend

رابط اعلان و منطق مرورگر در پروژه وجود دارد، اما API پیش‌فرض پروژه Demo است و سرویس اعلان پایدار backend پشت آن نیست. اجرای backend واقعی، تنظیمات ذخیره‌شده سمت سرور و تحویل قابل‌اعتماد ایمیل/Browser/Sound تأیید نشده است. Responsive و E2E برای جریان عملیاتی اجرا نشده‌اند.

## و) تست‌ها

- Backend regression suite: ۱۲۴ Passed، ۰ Failed، ۰ Skipped؛ این تست‌ها قابلیت‌های Job/Notification را پوشش نمی‌دهند.
- Frontend suite: ۳۲ Passed، ۰ Failed، ۰ Skipped؛ تست‌های منطق رابط/Demo هستند و تحویل backend را اثبات نمی‌کنند.
- تست اختصاصی فاز ۷: Passed ۰، Failed ۰؛ این فاز شروع نشده است.

فاز ۷ در این اجرا عمداً آغاز نشد، چون دروازه پذیرش فاز ۶ هنوز برقرار نیست.

## ز) موارد باقی‌مانده

- تکمیل هویت و مجوز سرور، سپس انتخاب/پیکربندی زیرساخت واحد Job.
- طراحی idempotency، retry، timeout، قفل هم‌زمانی و Job history قبل از فعال‌سازی عملیات حساس.
- نیاز به تأیید سازمان برای reminder، escalation، auto-cancel، rollover، expiry و retention.
- Notification service، transactional outbox، dedupe و تنظیمات کاربر باید عملیاتی شوند.

## ح) وضعیت پذیرش

تمام معیارهای پذیرش فاز ۷ **BLOCKED / NOT TESTED** هستند؛ اجرای دوباره، ارسال اعلان، Jobهای حساس و کنترل دسترسی backend در این مرحله برقرار یا اثبات نشده‌اند.

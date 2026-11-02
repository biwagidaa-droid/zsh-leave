# اجرای زمان‌بندی‌شده کارهای پس‌زمینه

## وضعیت و معماری

اجرای کارها با یک فرمان یک‌باره Django انجام می‌شود؛ وابستگی صف یا worker جداگانه اضافه نشده است. در production، `systemd timer` هر دقیقه فرمان را اجرا می‌کند. PostgreSQL advisory lock به‌ازای هر نام کار، قفل ردیف برای claim و قید یکتای `(job_name, scheduled_for)` اجرای هم‌زمان/تکراری را مهار می‌کنند. شروع attempt پیش از اجرای handler commit می‌شود؛ اگر process قطع شود، lease قدیمی پس از ۱۵ دقیقه قابل بازیابی است. SQLite فقط برای اجرای محلی تک‌فرآیندی است و backend تولید باید PostgreSQL باشد.

تا زمانی که timer نصب و `ZSH_JOB_SCHEDULER_ENABLED=1` تنظیم نشده باشد، API وضعیت `scheduler_not_configured` می‌دهد. صرف وجود فرمان یا ردیف‌های Job به معنی فعال بودن زمان‌بند نیست.

## عملیات ثبت‌شده

منطقه زمانی برنامه از `TIME_ZONE` جنگو خوانده می‌شود؛ تنظیم production فعلی `Asia/Tehran` است. زمان‌بندی روزانه بر ساعت محلی سازمان محاسبه می‌شود، نه ساعت میزبان. ساعت محلی ۰۰:۱۵ انتخاب شده است. در زمان محلی مبهم، بار اول ساعت (fold=0) انتخاب می‌شود؛ اگر زمان محلی ناموجود باشد، زمان به اولین دقیقه معتبر بعدی جابه‌جا می‌شود. زمان‌های interval نیز بر اساس ساعت محلی و یک‌بار در هر slot محلی محاسبه می‌شوند.

| کار | هدف و زمان‌بندی | واجد شرایط | اثر و کلید تکرارپذیری |
|---|---|---|---|
| `overdue_escalation` | هر ۵ دقیقه؛ پس از `workflow.escalate_after_working_days` روز کاری | درخواست `PENDING`؛ روزهای کاری از فردای تاریخ ثبت با تقویم/الگوی ذخیره‌شده درخواست محاسبه می‌شود؛ مقدار خالی، کار را غیرفعال می‌کند | انتقال شرطی وضعیت به `ESCALATED` از سرویس workflow، همراه رخداد و AuditEvent؛ کلید کسب‌وکار وضعیت فعلی `PENDING` است و تغییر هم‌زمان مدیر را بازنویسی نمی‌کند. |
| `manager_reminders` | هر ۵ دقیقه؛ پس از `workflow.reminder_after_working_days` روز کاری | درخواست `PENDING` دارای مدیر ثبت‌شده؛ مقدار خالی، کار را غیرفعال می‌کند | یک اعلان درون‌برنامه‌ای، email outbox و AuditEvent؛ قید یکتای `JobEffect.effect_key=leave-request-reminder:<request-id>` مانع event تکراری است. |
| `notification_delivery` | هر ۵ دقیقه، فقط وقتی delivery صف‌شده/قابل‌بازیابی وجود دارد | حداکثر `ZSH_NOTIFICATION_BATCH_LIMIT` پیام (پیش‌فرض ۵۰، سقف ۵۰۰) | provider ایمیل را با idempotency، مجوز جاری، status مستقل، retry محدود و خطای امن پردازش می‌کند؛ جزئیات در [سیاست اعلان](./notifications-fa.md). |
| `entitlement_expiration` | روزانه ۰۰:۱۵ و پیش از انتقال | کارمند فعال در تاریخ اجرا و استحقاق سال قبل بر اساس سیاست مؤثر او؛ فقط وقتی `jobs.expire_carry_over=true` | انقضای مؤلفه carry-over از سرویس دفترکل؛ رزرو/مصرف و اعتبار پایه حذف نمی‌شوند. کلید دفترکل از entitlement و `scheduled-expiration:<current-leave-year>` ساخته می‌شود. |
| `carry_forward` | روزانه ۰۰:۱۵، پس از انقضا | کارمند فعال و استحقاق سال قبل؛ فقط وقتی `jobs.carry_forward_policy` برابر `unlimited` یا `capped` باشد | ایجاد/استفاده مجدد استحقاق سال جاری از سرویس دفترکل؛ فقط مانده قابل‌استفاده منتقل می‌شود. کلید رویداد از منبع و `scheduled-carry-forward:<current-leave-year>` ساخته می‌شود. `capped` نیازمند `jobs.carry_forward_cap` است. |

تنظیم پیش‌فرض انتقال `none` و انقضا `false` است؛ این تصمیم‌های مالی بدون تصویب سازمان فعال نمی‌شوند. تغییر سیاست از `/api/v1/admin/settings/` فقط برای مدیر سامانه مجاز است و مانند سایر تنظیمات حسابرسی می‌شود.

یادآوری، ارجاع، delivery ایمیل صف، انتقال و انقضا عملیات دوره‌ای پیاده‌سازی‌شده‌اند. انقضای دعوت به‌صورت تنبل هنگام استفاده بررسی می‌شود؛ خود ایمیل دعوت برای حفظ محرمانگی token یک‌بارمصرف در درخواست ارسال می‌شود. delivery jobهای ایمیل وضعیت `sent` را فقط به‌معنی پذیرش backend ثبت می‌کنند؛ SMTP webhook، bounce، push و SMS وجود ندارد. یادداشت‌گذاری اعلان، لغو خودکار و سایر کارهای دوره‌ای زمان‌بندی نشده‌اند.

## تلاش مجدد، خطا و حسابرسی

- هر نوبت با نام کار، زمان نوبت، شروع/پایان، وضعیت، شمار تلاش، خلاصه محدود نتیجه، کد خطای امن و correlation ID ثبت می‌شود.
- خطای اتصال/timeout موقت حداکثر سه تلاش برای همان نوبت دارد؛ فاصله تلاش‌ها ۵ و سپس ۱۵ دقیقه است. نوبت جدید برای همان کار تا پایان تلاش مجدد معوق آغاز نمی‌شود.
- خطاهای اعتبارسنجی/سیاست و خطاهای ناشناخته retry خودکار نمی‌شوند. خطای موردی در batch ثبت می‌شود و وضعیت `partial_failure` می‌گیرد؛ خطاهای DB/شبکه موقت کل نوبت را برای retry علامت می‌زنند.
- هر درخواست در batch جداگانه از سرویس مجاز/دفترکل پردازش می‌شود. اثرهای موفق تکرارپذیرند؛ خرابی یک رکورد باعث تکرار اعلان، رویداد دفترکل یا ارجاع نمی‌شود.
- endpoint فقط برای مدیر سامانه قابل مشاهده است و نام کارمند، متن درخواست، traceback و پیام خام exception را برنمی‌گرداند. جزئیات نتیجه فقط تعداد و کدهای ثابت خطاست.
- اجرای دستی HTTP وجود ندارد. فرمان مدیریت نیز به‌طور پیش‌فرض با زمان‌بند غیرفعال متوقف می‌شود؛ اجرای محلی یک‌باره فقط با `DEBUG=True` و گزینه صریح `--enable-local` ممکن است.

## استقرار production (systemd)

پیش‌نیازها: PostgreSQL مشترک با backend، محیط مجازی و checkout در مسیرهای نمونه زیر، کاربر سیستم `zsh-leave`، و فایل محیطی محرمانه `/etc/zsh-leave/zsh-leave.env` با دسترسی فقط برای root و سرویس. فایل محیط باید پیکربندی معتبر `config.settings_prod` را داشته باشد، از جمله:

```ini
ZSH_ENV=production
ZSH_JOB_SCHEDULER_ENABLED=1
ZSH_SECRET_KEY=<secret>
ZSH_ALLOWED_HOSTS=<production-hosts>
ZSH_DB_NAME=zsh
ZSH_DB_USER=<database-user>
ZSH_DB_PASSWORD=<secret>
ZSH_DB_HOST=<postgres-host>
ZSH_DB_PORT=5432
```

پس از نصب/انتشار همان نسخه کد backend و اجرای migration، همین فایل محیط باید برای web process نیز بارگذاری شود. برای یک DB مشترک فقط یک timer فعال کنید (قفل DB همچنان اجرای تکراری تصادفی را مهار می‌کند):

```sh
sudo install -o root -g zsh-leave -m 0640 deploy/systemd/zsh-leave-jobs.service /etc/systemd/system/
sudo install -o root -g root -m 0644 deploy/systemd/zsh-leave-jobs.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zsh-leave-jobs.timer
sudo systemctl start zsh-leave-jobs.service
sudo systemctl status zsh-leave-jobs.timer
sudo journalctl -u zsh-leave-jobs.service
```

مسیرهای `/opt/zsh-leave`، `/etc/zsh-leave/zsh-leave.env` و نام کاربر در unit نمونه باید با محل واقعی نصب هماهنگ شوند. `systemctl list-timers zsh-leave-jobs.timer` وجود زمان‌بند را تأیید می‌کند؛ `GET /api/v1/admin/jobs/` آخرین heartbeat و اجرای ثبت‌شده را نشان می‌دهد. `GET /api/v1/ready/` در production تا heartbeat تازه (حداکثر ۱۵ دقیقه) پاسخ آماده نمی‌دهد. پس از توقف timer، هشدار readiness و `scheduler.stale` را بررسی کنید.

## توسعه محلی

زمان‌بند خودکار در development/test خاموش است. برای اجرای کنترل‌شده یک‌باره:

```sh
cd backend
ZSH_ENV=development python manage.py run_scheduled_jobs --enable-local
```

اجرای محلی heartbeat production را جعل نمی‌کند و API در صورت خاموش بودن پیکربندی همچنان `scheduler_not_configured` گزارش می‌دهد.

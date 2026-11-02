# راهنمای پشتیبان‌گیری و بازیابی ZSH Leave

**وضعیت شواهد:** پشتیبان‌گیری production: **NOT VERIFIED**؛ restore روی زیرساخت production: **NOT RUN**. یک restore drill مصنوعی و ایزوله با PostgreSQL 17 در Docker موفق شد؛ این شواهد ظرفیت، offsite copy، RPO/RTO یا قابلیت بازیابی محیط production را اثبات نمی‌کنند.

## دامنه داده و مرزهای پشتیبان

| داده | محل پایدار | روش حفاظت |
|---|---|---|
| داده‌های سازمان، حساب‌ها، درخواست‌ها، سیاست‌ها، تنظیمات، سهمیه و ledger | PostgreSQL در `settings_prod` | `pg_dump` فرمت custom، رمزگذاری‌شده |
| Audit، تاریخچهٔ درخواست/تقویم و سوابق تغییر append-only | مدل‌های دیتابیس از جمله `AuditEvent`، `LeaveRequestEvent`، `CalendarHolidayHistory` و `EntitlementEvent` | همراه کل دیتابیس |
| پیوست‌های HR | کل `ZSH_ATTACHMENT_ROOT` خصوصی؛ در production باید خارج از repository و پایدار باشد. `MEDIA_ROOT` قدیمی را تا تأیید پایان مهاجرت/حذف legacy copy نیز جداگانه حفظ کنید | archive هم‌زمان با DB، رمزگذاری‌شده، SHA-256 برای هر فایل |
| اجرای job، اثرهای idempotency و heartbeat زمان‌بند | PostgreSQL (`JobExecution`، `JobEffect`، `SchedulerHeartbeat`) | همراه کل دیتابیس |
| گزارش Export | فایل دائمی در سرور ساخته نمی‌شود؛ CSV/XLSX در پاسخ HTTP stream می‌شود. ثبت Audit export در PostgreSQL است | فایل خروجی پس از دانلود مسئولیت گیرنده است؛ سوابق Audit با DB حفظ می‌شوند |
| cache و session | جدول PostgreSQL؛ موقت/قابل بازسازی | در dump DB می‌آیند؛ پاک‌سازی cache/session در staging مجاز است و باید پیش از مقایسهٔ شمارش‌ها انجام شود. جدول cache منبع دادهٔ کسب‌وکار نیست |
| تنظیمات و Secrets اجرایی | secret manager یا فایل محیطی خارج از repository، مانند `/etc/zsh-leave/zsh-leave.env` | در backup برنامه کپی نمی‌شوند؛ بازیابی از secret manager و چرخش امن |
| کد و static assets | release artifact یا checkout نسخه‌دار؛ دادهٔ اصلی نیستند | نسخهٔ منتشرشده را جداگانه نگه‌داری کنید؛ `static` قابل بازسازی است |

مقادیر `ZSH_SECRET_KEY`، `ZSH_DB_PASSWORD`، SMTP password و کلید خصوصی age هرگز داخل script، این مخزن، inventory یا backup unencrypted قرار نمی‌گیرند. inventory رمزگذاری‌شده شامل نسخهٔ برنامه، هویت منطقی DB (نام/کاربر/نسخهٔ PostgreSQL)، migration headها، شمارش مدل‌ها، شمارش تاریخچه، تطبیق ledger و فهرست مسیر/اندازه/SHA-256 فایل‌ها است.

Runtime secrets و configuration باید جداگانه در secret manager ثبت و دسترس‌پذیری بازیابی‌شان آزموده شود: `ZSH_SECRET_KEY`، `ZSH_DB_*`، `ZSH_ALLOWED_HOSTS`، `ZSH_CSRF_TRUSTED_ORIGINS`، `ZSH_TRUSTED_PROXY_IPS`، `ZSH_ATTACHMENT_ROOT`، تنظیمات SMTP (`ZSH_EMAIL_*`, `ZSH_PUBLIC_BASE_URL`)، scanner (`ZSH_ATTACHMENT_SCANNER`) و فعال‌سازی scheduler. مقادیر هر محیط staging باید با production متفاوت/مجزا باشند؛ public identity age برای backup و private identity برای decrypt در دو trust boundary جدا نگهداری شوند.

## سیاست هدف

این baseline عملیاتی تا تصویب مالک داده/امنیت پیشنهاد می‌شود؛ جایگزین الزام قانونی/سازمانی نیست:

- **تناوب:** یک snapshot کامل و سازگار هر شب؛ هشدار اگر آخرین نسخهٔ موفق بیش از ۲۶ ساعت عمر داشته باشد. اجرای روزانه باید با اپراتور و maintenance window هماهنگ شود.
- **نگهداری:** ۳۵ نسخهٔ روزانه، ۱۲ نسخهٔ هفتگی و ۱۲ نسخهٔ پایان ماه. حذف خودکار در script نیست؛ lifecycle در مخزن مستقل باید با آزمون و مجوز جدا پیکربندی شود.
- **رمزگذاری:** age با public recipient سازمان. مقصد و کپی انتقال باید encrypted-at-rest و انتقال با TLS باشد. private identity در secret manager/آفلاین جدا از حساب/سامانهٔ backup نگهداری شود؛ دسترسی decrypt به دو نقش محدود و audit شود.
- **دسترسی:** account سرویس backup فقط خواندن DB و فایل پیوست و نوشتن مقصد را داشته باشد؛ restore فقط با credential محدود staging. دسترسی production admin و backup decrypt جدا باشند. فایل‌ها/دایرکتوری مقصد با حداقل مجوز و دسترسی auditشده محافظت شوند.
- **کپی مستقل:** پس از تولید، نسخه به account/محدودهٔ خطای جدا از host و volume برنامه منتقل شود؛ versioning/object lock یا کنترل معادل، و آزمون بازیابی مستقل الزامی است. خروجی محلی script به‌تنهایی offsite محسوب نمی‌شود.
- **یکپارچگی:** SHA-256 روی artifactهای رمز‌شده، احراز صحت age با decrypt کامل، `pg_restore --list` برای ساختار dump، `tar -tzf` برای archive فایل، inventory و بررسی کامل پس از restore. backup را تا پایان restore drill موفق «قابل بازیابی» اعلام نکنید.
- **RPO هدف:** حداکثر ۲۴ ساعت از آخرین snapshot موفق؛ این هدف با backup شبانه و هشدار stale قابل تحقق است، اما در این deployment اندازه‌گیری/تضمین نشده است.
- **RTO هدف:** حداکثر ۴ ساعت برای بازیابی یک محیط staging/سرویس از snapshot شناخته‌شده. این عدد هنوز با حجم واقعی DB/فایل و ظرفیت مقصد آزموده نشده و تضمین production نیست.
- **آزمون بازیابی:** هر سه ماه یک‌بار و پس از تغییر روش backup، migration عمده یا storage؛ staging باید از cluster/credential production جدا باشد. هر اجرای موفق با زمان، نسخه، DB مبدأ، مدت، شمارش‌ها، نتیجهٔ ledger، فایل‌ها و health ثبت شود.

## پیش‌نیاز و اجرای Backup

روش فعلی فقط برای deploymentی است که PostgreSQL و storage فایل محلیِ خصوصی را در دسترس سرویس backup قرار دهد. نصب PostgreSQL client سازگار با major version DB، `age`, `tar`, `sha256sum`, `flock`, Python virtualenv برنامه لازم است. recipient عمومی `ZSH_BACKUP_AGE_RECIPIENT` و مسیر مقصد باید از پیکربندی مدیریت‌شده به process برسند؛ password DB از محیط امن موجود در production خوانده می‌شود. هیچ‌یک را در command line history یا repository قرار ندهید.

تا وقتی snapshot سازگار database و filesystem در deployment موجود نیست، writerها باید متوقف شوند. ابتدا همهٔ web/API writerها و uploader/importerهای خارجی را drain/stop کنید، سپس `zsh-leave-jobs.timer` و اجرای جاری job را متوقف و پایان آن را تأیید کنید. پیکربندی واقعی web unit در این repository نیست؛ نام unit را از مدیر deployment بگیرید. صرف توقف timer کافی نیست اگر job یا writer دیگری هنوز فعال باشد. این روش maintenance window دارد؛ برای حذف downtime باید بعداً از snapshot اتمیک/هماهنگ PostgreSQL و storage با ابزار پشتیبانی‌شدهٔ محیط استفاده شود.

پس از تأیید توقف همهٔ writerها، از shell مجاز backup که secretهای production را از secret manager دریافت کرده، اجرا کنید:

```sh
export DJANGO_SETTINGS_MODULE=config.settings_prod
export ZSH_BACKUP_QUIESCED=1
export ZSH_BACKUP_DIR=/mnt/independent-backup/zsh-leave
export ZSH_BACKUP_AGE_RECIPIENT='age1...'
export ZSH_APP_VERSION='release-or-commit-id'
bash deploy/backup/zsh-leave-backup.sh
```

`ZSH_BACKUP_QUIESCED=1` فقط attestation اپراتور است و وضعیت سرویس‌ها را خودکار بررسی نمی‌کند. script نسخهٔ برنامه، PostgreSQL custom dump، archive کل `ZSH_ATTACHMENT_ROOT` و inventory را به‌صورت جداگانه با age رمز می‌کند و SHA-256 artifactها را در `SHA256SUMS` می‌نویسد. هر snapshot در دایرکتوری تازه با مجوز `0700` ساخته می‌شود؛ script نسخه‌های پیشین را overwrite یا حذف نمی‌کند. پس از اتمام، سرویس‌ها را طبق change procedure محیط دوباره فعال و readiness را بررسی کنید.

ابتدا بررسی محلی artifact:

```sh
cd /mnt/independent-backup/zsh-leave/<snapshot-id>
sha256sum -c SHA256SUMS
```

سپس snapshot کامل را به مقصد مستقلِ رمزگذاری‌شده با versioning/immutability منتقل و رسید انتقال، زمان، snapshot ID، نسخهٔ برنامه و وضعیت موفقیت را در سامانهٔ مانیتورینگ ثبت کنید. اگر انتقال مستقل یا alerting پیکربندی نشده، اجرای موفق محلی را backup production کامل تلقی نکنید.

## Restore Drill فقط در Staging ایزوله

**هرگز** این دستورات را با credential، host، DB name یا attachment root production اجرا نکنید. DB مقصد باید روی cluster staging جدا، خالی، با credential staging و نام متمایز باشد. هیچ دستور `DROP DATABASE` یا `pg_restore --clean` در این روش وجود ندارد. DB هدف را پیشاپیش به‌صورت تازه و خالی توسط DBA staging بسازید؛ اگر خالی بودن آن قابل اثبات نیست، متوقف شوید.

1. نسخهٔ snapshot و دسترسی staging را ثبت کنید. private identity age را از secret manager امن staging بگیرید؛ آن را در مخزن یا shell history نگذارید. دایرکتوری موقت restore روی scratch رمزگذاری‌شده بسازید.
2. checksumها و کامل‌بودن snapshot را بررسی کنید؛ کپی مقصد باید `COMPLETE` داشته باشد:

```sh
cd /mnt/independent-backup/zsh-leave/<snapshot-id>
test -f COMPLETE
sha256sum -c SHA256SUMS
```

3. متغیرهای مقصد را از پیکربندی امن staging تزریق کنید؛ password و identity را در command line history یا repository قرار ندهید. `ZSH_RESTORE_DB_NAME` باید با `zsh_restore_` شروع شود، host/port باید با مبدأ فرق داشته باشد، DB تازه ساخته و خالی باشد، و storage/scratch مسیرهای staging مستقل باشند. `ZSH_RESTORE_ISOLATED=YES` فقط پس از بازبینی مستقل cluster و credential staging تنظیم شود. محیط لازم برای Django production settings (`ZSH_SECRET_KEY`، `ZSH_ALLOWED_HOSTS` و سایر تنظیمات staging) را هم از secret manager تأمین کنید. سپس از root checkout و با virtualenv برنامه اجرا کنید:

```sh
export ZSH_RESTORE_ISOLATED=YES
export ZSH_RESTORE_DB_HOST='<staging-postgres-host>'
export ZSH_RESTORE_DB_PORT='5432'
export ZSH_RESTORE_DB_NAME='zsh_restore_<snapshot-id>'
export ZSH_RESTORE_DB_USER='<staging-restore-role>'
export ZSH_RESTORE_ATTACHMENT_ROOT='/srv/zsh-leave-staging/attachments-restore'
export ZSH_RESTORE_SCRATCH='/secure-staging-scratch'
export ZSH_BACKUP_AGE_IDENTITY_FILE='/run/secrets/zsh-backup-age-identity'
export PATH='/opt/zsh-leave/venv/bin:'"$PATH"
bash deploy/backup/zsh-leave-restore-staging.sh \
  /mnt/independent-backup/zsh-leave/<snapshot-id>
```

script پیش از restore، checksum و marker را بررسی، inventory را decrypt، نام DB/host مبدأ را با مقصد مقایسه، خالی‌بودن DB و attachment directory را تأیید و از اجرای `pg_restore --clean` یا حذف DB پرهیز می‌کند. سپس restore، migration، `migrate --check`، Django `check` و `verify_backup --compare` را اجرا می‌کند. این guardها جایگزین تأیید انسانی cluster staging نیستند؛ هرگز متغیرهای staging را با credential/host production مقداردهی نکنید. verifier در صورت اختلاف migration head، شمارش مدل‌ها، فایل/اندازه/hash، history یا reconciliation سهمیه exit غیرصفر می‌دهد؛ constraintهای FK را هم از طریق backend بررسی می‌کند. خروجی سالم باید `errors: []` و `database_vendor: postgresql` داشته باشد.

اگر اجرای restore پس از شروع `pg_restore` یا استخراج فایل شکست خورد، مقصد staging را آلوده/ناقص فرض کنید؛ سرویس staging را منتشر نکنید و script را روی همان DB یا directory نیمه‌پر دوباره اجرا نکنید. حفظ log و تشخیص خطا را انجام دهید و از DBA بخواهید یک DB خالی و media directory تازهٔ staging بسازد. پاک‌سازی فقط همان resource staging با تأیید مالک محیط انجام شود؛ script عمداً هیچ دیتابیس یا فایل مقصدی را حذف نمی‌کند.

4. health را از endpoint staging پس از اجرای job scheduler staging و heartbeat تازه بررسی کنید؛ از host و نام staging استفاده کنید:

```sh
curl --fail --silent --show-error https://<staging-host>/api/v1/health/
curl --fail --silent --show-error https://<staging-host>/api/v1/ready/
```

صحت HTTP به‌تنهایی restore موفق نیست. گزارش drill باید checksum/decrypt، `pg_restore --list`، نسخه و migrationها، DB مقصد، `record_counts`، integrity فایل‌ها، Audit/history، ledger بدون inconsistency، health/readiness و مدت کل را شامل شود. در پایان credential staging/دسترسی موقت را طبق رویهٔ سازمان پاک‌سازی/لغو کنید. script scratch plaintext را حذف می‌کند؛ در SSD حذف فایل تضمین secure erase نیست، پس scratch باید از ابتدا encrypted و موقت باشد.

## بازیابی رخدادها

- **خرابی DB:** توقف writerها و حفظ log/شواهد؛ DBA تشخیص دهد cluster قابل تعمیر است یا باید DB جدید provision شود. ابتدا آخرین snapshot با checksum درست را در cluster جدا restore و تمام gateهای بالا را اجرا کنید. cutover یا restore روی production نیازمند change و approval مستقل است؛ در این task انجام نمی‌شود.
- **حذف تصادفی داده:** snapshot پیش از حذف را در DB staging جدا restore کنید. دادهٔ موردنیاز را با مالک HR/DBA تطبیق دهید و با روش مجاز/ممیزی‌شده به production بازگردانید؛ جایگزینی کل DB production برای بازیابی یک رکورد مجاز نیست.
- **از دست‌رفتن media:** اگر DB سالم است، archive پیوست همان snapshot زمانی را در storage staging بازگردانی و inventory را اجرا کنید. اگر DB و فایل هر دو از دست رفته‌اند، آن‌ها را فقط از یک snapshot جفت‌شده restore کنید؛ ترکیب DB و media با timestamp متفاوت می‌تواند لینک پیوست را خراب کند.
- **migration ناموفق:** rollout را متوقف، خطا و schema وضعیت فعلی را حفظ و ثبت کنید. migration را دستی معکوس یا DB زنده را overwrite نکنید. روی staging از snapshot قبل از migration restore کنید، migration اصلاحی/forward را با تیم توسعه آزمایش و سپس rollout جدید را جداگانه تصویب کنید.
- **افشای credential:** دسترسی مظنون را revoke و credentialهای DB، Django، SMTP و operator را از secret manager rotate کنید؛ نشست/کلید Django و اثر بر کاربران را طبق incident plan مدیریت کنید. افشای DB credential به‌خودی‌خود با restore حل نمی‌شود. اگر private age identity افشا شد، محرمانگی همهٔ نسخه‌های قابل decrypt را compromised فرض کنید، recipient جدید بسازید، دسترسی مقصد را بررسی و نسخه‌های لازم را با key جدید رمزگذاری کنید؛ کلید قدیمی را تا پایان retention امن نگه دارید مگر افشای آن نیاز به حذف فوری نسخه‌ها داشته باشد. logها و نسخه‌های immutable را برای بررسی حفظ کنید.

## پایش، شواهد و تأیید

در این repository، logها فقط به console می‌روند؛ log aggregation، alert، backup scheduler، offsite replication، object lock و retention اجرایی پیکربندی نشده‌اند. deployment باید برای شکست command/انتقال، artifact قدیمی‌تر از ۲۶ ساعت، کمبود فضای دیسک، شکست decrypt/checksum و تأخیر/شکست drill هشدار مرکزی داشته باشد. لاگ عملیاتی نباید password، private key یا محتوای فایل را ثبت کند.

## شواهد Restore Drill محلی

در ۲ نوامبر ۲۰۲۶ یک drill کامل با دو PostgreSQL 17.11 container تازه و جداگانه، کلید age موقت و DB/media ساختگی اجرا شد؛ به هیچ محیط یا credential production متصل نشد. نسخهٔ کد آزمایشی `local-restore-drill-v1` بود. snapshot دوم پس از provision کردن `zsh_cache` روی منبع ساخته شد؛ checksum هر سه artifact رمزگذاری‌شده موفق بود و restore runner آن را به DB خالی `zsh_restore_drill2` روی container مستقل `staging2` بازیابی کرد.

- تمام ۳۷ migrationهای نصب‌شده تا `leave.0019_attachment_security` موجود و `migrate --check` موفق بود؛ `manage.py check` بدون خطا.
- مقایسهٔ inventory موفق با `errors: []`، `database_vendor: postgresql`، FK check برابر `checked` و یک entitlement بدون ناسازگاری.
- شمارش‌های کلیدی پس از restore: ۱ شرکت، ۱ حساب و پروفایل کارمند، ۱ درخواست، ۱ پیوست، ۱ entitlement و ۱ رویداد ledger؛ ۲ رویداد audit، ۱ رویداد درخواست، ۱ اجرای job و ۱ اثر job.
- یک فایل پیوست ۳۷ بایتی با SHA-256 یکسان بازیابی شد؛ tar listing و `pg_restore --list` موفق بودند.
- `run_scheduled_jobs` heartbeat تازه ثبت کرد؛ Django test Client با middleware production هر دو endpoint سلامت و readiness را با status 200 پاسخ داد و DB/scheduler را `healthy` گزارش کرد. Gunicorn، proxy/TLS یا مسیر شبکهٔ واقعی آزموده نشد.

این نتیجه تنها ثابت می‌کند snapshot مصنوعیِ ساخته‌شده با همین script در همین drill قابل restore بوده است. مقصد offsite، زمان‌بندی/retention production، هشدار، scratch واقعی، بار/حجم production و secret manager آزموده نشدند. به همین دلیل وضعیت backup production همچنان **NOT VERIFIED** است و هیچ snapshot واقعی را تا موفقیت drill مستقل همان محیط «معتبر/قابل بازیابی» تلقی نکنید.

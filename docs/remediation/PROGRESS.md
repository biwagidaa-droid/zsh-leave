# پیشرفت پروژه اصلاح

## فاز فعلی

فاز ۳ — چرخه استخدام و offboarding: شروع‌نشده. آخرین فازهای تکمیل‌شده: فاز ۰، فاز ۱ و فاز ۲.

## تکمیل‌شده

- **فاز ۰ — Discovery/Baseline:** ساختار مخزن، branch/status، مستندات معماری/امنیت، فرمان‌های baseline و محدودیت PostgreSQL ثبت شد.
- **فاز ۱ — Critical privacy (سطح‌های بررسی‌شده):** confidential balance/entitlements، گزارش‌های executive و `coverage.awayCount` مدیر با regression tests فیلتر شدند. Gate حریم خصوصی کلی همچنان NOT VERIFIED.
- **فاز ۲ — HR absence:** endpoint به ایجاد مستقیم `APPROVED` تغییر کرد؛ approve دوم حذف شد؛ idempotency key الزامی و fingerprint کامل شد؛ تست event/audit، ledger، replay، scope و rollback افزوده شد.

## فایل‌های تغییر‌یافته

- `backend/leave/frontend_api_views.py`
- `backend/leave/authorization.py`
- `backend/leave/tests/test_frontend_api.py`
- `backend/leave/tests/test_workflow_api.py`
- `docs/api.md`
- `docs/api/api-contract.md`
- `docs/final-documentation/05-hr-user-guide.md`
- `docs/remediation/BASELINE.md`
- `docs/remediation/REMEDIATION-REPORT.md`
- `docs/remediation/SECURITY-AND-PERMISSIONS.md`
- `docs/remediation/WORKFLOW-AND-BUSINESS-RULES.md`
- `docs/remediation/TEST-EVIDENCE.md`
- `docs/remediation/PRODUCTION-GATE.md`
- `docs/remediation/KNOWN-LIMITATIONS.md`
- `docs/remediation/PROGRESS.md`

## آزمون‌ها

- `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test`: ۱۸۱ آزمون، ۰ شکست، ۳ skipped (PostgreSQL-only).
- `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py check`: موفق.
- `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py makemigrations --check --dry-run`: موفق، تغییر مهاجرت ندارد.
- `cd frontend && npm test`: ۳۴ passed.
- `cd frontend && npm run build`: موفق؛ TypeScript و Vite.
- `git diff --check`: موفق.

## موانع شناخته‌شده

- PostgreSQL در این محیط validate نشد؛ `pg_isready` نصب نیست و تست‌ها SQLite هستند.
- scheduler وجود ندارد، Bradford endpoint placeholder است و export API در routeها یافت نشد.
- چرخه استخدام، activation، ممیزی کامل RBAC/audit، PostgreSQL compatibility و production deployment هنوز تکمیل/تأیید نشده‌اند.

## گام بعدی دقیق

1. جست‌وجو و trace تمام authorization checks که `EmployeeProfile.is_employee` یا `User.is_active` را مصرف می‌کنند؛ رفتار `end_date` و شروع آینده را در model/API فعلی reproduce کنید.
2. یک helper مرکزی وضعیت مؤثر استخدام تعریف کنید و آن را به مسیر authorization مرکزی متصل کنید، بدون تغییر زودهنگام User admin برای HR.
3. regression tests برای اشتغال فعال، پایان آینده، پایان گذشته، profile غیرفعال و managerهای پایان‌یافته اضافه کنید.
4. تست‌های backend متمرکز، سپس full suite و migration check اجرا کنید؛ migration فقط در صورت نیاز schema و با مسیر سازگار افزوده شود.
5. شواهد و فایل‌های این پوشه را با نتایج واقعی به‌روز کنید و سپس فاز ۴ را شروع کنید.

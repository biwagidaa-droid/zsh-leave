# شواهد آزمون

## اجرا پس از اصلاحات

محیط: Python 3.14.2 / Django 5.2.18، Node 24.22.2 / npm 11.19.1. Backend روی SQLite آزمون اجرا شد.

| فرمان | نتیجه واقعی |
|---|---|
| `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py test` | موفق؛ ۱۸۱ آزمون، ۳ skipped، ۰ شکست |
| `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py check` | موفق؛ بدون خطای system check |
| `cd backend && DJANGO_SETTINGS_MODULE=config.settings_test python3 manage.py makemigrations --check --dry-run` | موفق؛ `No changes detected` |
| `cd frontend && npm test` | موفق؛ ۳۴ passed، ۰ failed، ۰ skipped |
| `cd frontend && npm run build` | موفق؛ `tsc --noEmit` و Vite production build |
| `git diff --check` | موفق؛ whitespace error گزارش نشد |

سه مورد skipped کلاس `PostgreSQLEntitlementConcurrencyTests` هستند: دو آزمون هم‌زمانی رزرو/تأیید دفترکل و آزمون trigger ضد تغییر. شرط کلاس `connection.vendor == "postgresql"` است.

## آزمون‌های رگرسیون جدید

- `test_confidential_balances_require_hr_scope`: کارمند، مدیر، HR در scope، HR شرکت دیگر و admin؛ confidential balance/labels و `coverage.awayCount`.
- `test_entitlements_hide_confidential_data_outside_hr_scope`: نقش کارمند، HR مجاز و HR خارج scope.
- همان آزمون، HR دارای employee profile خارج از HR assignment را نیز می‌سنجد؛ personal scope نباید به entitlements سازمانی HR اضافه شود.
- `test_executive_reports_exclude_confidential_records_and_balances`: absences، trends، process-health و balances؛ به‌علاوه دسترسی HR به absences در scope.
- `test_hr_absence_is_directly_approved_and_idempotent`: 422 بدون کلید، وضعیت approved، event/audit یکتا، اثر دفترکل و عدم duplicate/replay، و 409 برای payload متفاوت.
- `test_hr_absence_rejects_unauthorized_and_rolls_back_invalid_submission`: 403، 404 خارج دامنه، rollback درخواست/event/audit/idempotency.

## محدودیت شواهد

- PostgreSQL اجرا نشد؛ `pg_isready` نصب نبود و تنظیم اتصال integration test فراهم نبود. موفقیت SQLite معادل تأیید PostgreSQL نیست.
- E2E مرورگر، تست بار، lint مستقل، backup/restore، migration روی PostgreSQL و تست production settings/deployment اجرا نشدند.
- Frontend در این تغییر کد نداشت؛ test/build برای اطمینان از عدم regression مجدداً اجرا شد.

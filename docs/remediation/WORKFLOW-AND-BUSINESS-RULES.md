# گردش‌کار و قواعد کسب‌وکار — شواهد فازهای ۱ و ۲

## وضعیت‌های دیده‌شده در کد

مدل درخواست مقادیر `PENDING`، `ESCALATED`، `APPROVED`، `REJECTED`، `CANCELLED` و `WITHDRAWAL_PENDING` را می‌پذیرد. قواعد جزئی transition در `zsh_core/workflow.py` قرار دارند؛ این گزارش جای بازبینی کامل همه مسیرهای اصلاح/لغو/بازگشایی نیست.

- درخواست employee با نیاز به تأیید و manager حاضر، به `PENDING` می‌رود؛ نبود manager یا manager غایب می‌تواند `ESCALATED` بسازد.
- ثبت HR در `initial_status` مستقیماً `APPROVED` می‌شود. نوعی که تأیید نمی‌خواهد نیز مستقیم تأیید می‌شود.
- لغو درخواست تأییدنشده و درخواست لغو مرخصی تأییدشده مسیرهای جدا دارند؛ وضعیت نهایی و سیاست دقیق همه مسیرها هنوز در فاز workflow کامل بررسی نشده‌اند.

## ثبت غیبت HR اصلاح‌شده

`POST /api/v1/hr/absences/`:

1. نقش HR و scope employee بررسی می‌شود.
2. یک `Idempotency-Key` الزامی است؛ payload fingerprint شامل employee، leave type، تاریخ‌ها، روزکاری، دلیل و جانشین است.
3. `submit_request` یک بار اجرا می‌شود. نتیجه برای actor از نوع HR مستقیماً `APPROVED` است؛ endpoint دیگر `approve` دوم اجرا نمی‌کند.
4. یک رویداد `submit` با `from_status=""` و `to_status="APPROVED"` و یک audit `leave.submit` ثبت می‌شود.
5. اثر دفترکل در صورت مشمول‌بودن نوع مرخصی داخل همان تراکنش ثبت می‌شود.
6. درخواست، رویداد، audit، ledger و idempotency با شکست عملیات rollback می‌شوند.
7. replay همان actor/key/payload همان درخواست را برمی‌گرداند؛ ورودی متفاوت با همان key، 409 می‌دهد.

Frontend واقعی از قبل برای `recordAbsence` هدر `Idempotency-Key` می‌فرستاد. نبود هدر اکنون 422 است.

## مانده‌ها و Bradford

مانده balance endpoint از entitlement ledger گرفته می‌شود. آزمون HR absence نشان می‌دهد ایجاد درخواست تأییدشده نوع مشمول یک واحد را به `used` می‌افزاید، و replay آن مصرف را دوبرابر نمی‌کند.

تابع دامنه Bradford در `zsh_core/reports.py` فرمول `S² × D` را پیاده می‌کند، با ادغام دوره‌های هم‌پوشان/متصل و برش بازه. اما endpoint عمومی گزارش Bradford فعلاً توضیح و series خالی برمی‌گرداند؛ سیاست روزکاری، دامنه‌ها و پیاده‌سازی کامل analytics تأیید نشده است. این مورد برای فاز ۶ باز است.

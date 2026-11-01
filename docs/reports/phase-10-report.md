# گزارش فاز ۱۰ — Frontend و تجربه کاربری

## هدف و وضعیت اولیه

هدف، اتصال قابل اتکا به Backend واقعی و جلوگیری از نمایش Demo به‌عنوان داده عملیاتی است. Frontend React/TypeScript/Vite مسیرهای متعدد دارد، اما Client شامل Demo و مسیرهای HTTP فراتر از API موجود است؛ اتصال کامل، E2E و رفتار واکنش‌گرا اثبات نشده‌اند.

## قابلیت‌ها و وضعیت

| قابلیت | وضعیت | شواهد |
|---|---|---|
| احراز هویت و گردش‌کار واقعی | BLOCKED | Backend فعلی مسیر login/logout/me و API درخواست عملیاتی ندارد. |
| داشبوردها، Inbox و گزارش‌ها | PARTIAL | صفحات و Client وجود دارند؛ داده‌محور بودن API در Backend اثبات نشده است. |
| مرخصی ساعتی | PARTIAL | اعتبارسنجی/نمایش کلاینتی موجود است؛ محاسبه و اعتبارسنجی مرجع Backend و سهمیه ساعتی عملیاتی موجود نیست. |
| پیوست | NOT IMPLEMENTED عملیاتی | پیوست Demo فقط در Demo mode نمایش داده می‌شود؛ در HTTP mode پیام عدم پشتیبانی نشان داده می‌شود. |
| فارسی، RTL و شمسی | PARTIAL / NOT VERIFIED | اجزای RTL و تبدیل/ورودی شمسی وجود دارند؛ آزمون مرورگری در اندازه‌های مختلف اجرا نشده است. |
| Error/Loading/Empty | PARTIAL | بعضی صفحات این وضعیت‌ها را دارند؛ تغییرات زیر چند fallback خطاپوش مشخص را حذف کردند. |
| آزمون E2E | NOT IMPLEMENTED | Playwright یا E2E مرورگر یافت/اجرا نشد. |

## تغییرات انجام‌شده

- Demo به حالت توسعه محدود شد؛ build غیرتوسعه همیشه API واقعی را انتخاب می‌کند و فعال‌سازی صریح Demo هنگام اجرای برنامه عملیاتی خطا می‌دهد.
- برای حالت Demo در توسعه/Production تست واحد اضافه شد.
- پاسخ 404/501 در Client برای تنظیمات مرخصی و یادداشت Bradford دیگر به مقدار پیش‌فرض/فهرست خالی تبدیل نمی‌شود.
- خطای API در Dashboard، صفحه ثبت درخواست، وضعیت سلامت، Bradford و فهرست کارکنان مانده قابل مشاهده/تلاش مجدد است؛ دریافت ناقص قرارداد در Bradford با تقویم پیش‌فرض جایگزین نمی‌شود.
- CSV نمونه فقط در Demo mode پیش‌پر می‌شود.
- کنترل افزودن پیوست نمایشی فقط در Demo mode وجود دارد؛ در HTTP mode، نبود API امن به‌صراحت اعلام می‌شود.
- وابستگی‌های `react-router-dom` و `vite` برای رفع advisories ارتقا یافتند.

## فایل‌های جدید و اصلاح‌شده

- جدید: `frontend/src/api/mode.ts`، `frontend/tests/apiMode.test.ts`.
- اصلاح‌شده: `frontend/src/api/index.ts`، `frontend/src/api/http.ts`، `frontend/src/pages/AdminPages.tsx`، `BradfordPage.tsx`، `DashboardPage.tsx`، `HrPages.tsx` و `RequestsPages.tsx`.
- اصلاح وابستگی: `frontend/package.json` و `frontend/package-lock.json`.
- هیچ Backend API یا Migration برای این فاز ایجاد نشد.

## آزمون‌ها و نتیجه

- `cd frontend && npm test`: ۳۴ موفق، ۰ ناموفق، ۰ skipped.
- `cd frontend && npm run build`: TypeScript و Vite build موفق با Vite 6.4.5.
- `cd frontend && npm audit`: ۰ آسیب‌پذیری شناخته‌شده.
- E2E، تست واقعی API، تست موبایل/دسکتاپ مرورگر و آزمون دسترس‌پذیری خودکار اجرا نشدند.

## موارد باقی‌مانده و تصمیم‌ها

- بیشتر Client endpointها در Backend وجود ندارند؛ کاربر عملیاتی به API واقعی کامل دسترسی ندارد.
- نبود upload/download امن و endpoint مرخصی ساعتی مانع تکمیل این قابلیت‌هاست.
- فونت Vazirmatn از شبکه خارجی در مستندات قبلی ذکر شده؛ self-host و سیاست CSP نیازمند تکمیل است.
- تکمیل responsive، accessibility و E2E نیازمند مسیرهای API عملیاتی و محیط مرورگر است.

## وضعیت نهایی فاز

**PARTIAL / BLOCKED** — محدودسازی Demo و مدیریت بخشی از خطاها پیاده و آزموده شده، اما معیار اتصال کامل صفحات، مرخصی ساعتی Backend، Inbox عملیاتی و آزمون E2E برآورده نشده است.

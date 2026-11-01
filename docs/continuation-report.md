# گزارش ادامه توسعه (Frontend)

تاریخ: ۹ آبان ۱۴۰۵ — دامنه: فقط `frontend/`. پوشه‌های `backend/` و `docs/` قبلی دست نخورده‌اند (فقط دو گزارش این مأموریت به `docs/` افزوده شد).

## ۱. وضعیت پروژه در شروع کار
- آرشیو **بدون `.git`** بود؛ دستورات Git قابل اجرا نبود (جزئیات: `continuation-audit-report.md`). برای مقایسه، یک نسخه پایه از پروژه گرفته شد.
- `tsc` و `vite build` سالم بودند، ولی `node_modules` ویندوزی بود (با `npm ci` روی Linux بازسازی شد).
- لایه منطق و Demo برای لغو خودکار، مرخصی ساعتی، اعلان و Bradford توسط Cursor نوشته شده بود، ولی **هیچ صفحه‌ای** آن را مصرف نمی‌کرد.

## ۲. وضعیت تغییرات قبلی Cursor
همه حفظ شد؛ هیچ فایل یا تابعی حذف نشد. تنها اصلاح‌های ماهیتی روی کار Cursor:
- گزارش `bradford` در `demo.ts` اعداد ثابت و ساختگی داشت؛ با محاسبه از داده واقعی Store دمو جایگزین شد.
- `notifications()` در Demo اکنون شبیه‌سازی لغو خودکار را هم اجرا می‌کند (فقط وقتی جلسه Demo باز است).
- `notificationPrefs.ts`: فقط توابع افزوده شد (ذخیره/بارگذاری تنظیمات، برچسب‌ها).
- `leaveDisplay.ts`: پارامتر اختیاری `withMonthName` افزوده شد.
- `NotificationsPage` از `AdminPages.tsx` به `NotificationCenter.tsx` منتقل شد (همه قابلیت‌های قبلی حفظ شد؛ `AdminPages` آن را re-export می‌کند).

## ۳. از قبل کامل بود (فقط لایه منطق/Demo)
منطق لغو خودکار، منطق مرخصی ساعتی، فرمول Bradford، تنظیمات و نوع‌ها، `createRequest` ساعتی در Demo، رویداد تقویم، `AUTO_CANCELLED`، کتابخانه صدا و عنوان/فاویکون.

## ۴. تکمیل‌شده توسط Claude

| قابلیت | آنچه اکنون در UI کار می‌کند |
|---|---|
| **مرخصی ساعتی** | انتخابگر روزانه/ساعتی در فرم ثبت (فقط وقتی سیاست فعال است)؛ تاریخ شمسی، ساعت شروع/پایان، مدت محاسبه‌شده و معادل روز کاری (برچسب «تخمین»)؛ اعتبارسنجی ساعت (ترتیب، سقف، ساعات کاری، تعطیل، روز کاری از `estimate`)؛ بررسی تداخل با درخواست‌های فعال (ساعتی و روزانه)؛ نمایش در فهرست، جزئیات، کارتابل/صف تأیید، داشبورد، تقویم، نوار زمانی، گزارش‌ها (تفکیک روزانه/ساعتی). مرخصی روزانه بدون تغییر رفتار. |
| **لغو خودکار** | ستون «مهلت تأیید» در فهرست؛ کارت جزئیات (وضعیت مهلت، زمان انقضا، آخرین روز تصمیم، زمان و علت لغو خودکار، N قفل‌شده روی درخواست)؛ پیام مهلت در فرم ثبت؛ آمار HR (سیاست، لغوشده خودکار، نزدیک به انقضا) در داشبورد؛ کنترل فعال/غیرفعال به‌صورت منوی انتخاب در تنظیمات؛ پردازش دوباره درخواست‌های تأییدشده/ردشده/لغوشده با تست پوشش داده شد. |
| **اعلان پیشرفته** | `NotificationsProvider` (نظرسنجی ۳۰ ثانیه‌ای، رویداد Demo، BroadcastChannel، `storage`)؛ مرکز اعلان با دسته‌بندی، فیلتر «فقط خوانده‌نشده»، «خواندم»، «همه را خواندم»، لینک به درخواست؛ تنظیمات: روشن با صدا/بی‌صدا/خاموش، انتخاب صدا، شدت صدا، تست صدا، فعال/غیرفعال هر نوع؛ زنگ و Badge در نوار بالا و منو؛ شمارنده در عنوان تب و Badge قرمز فاویکون؛ جلوگیری از اعلان تکراری (مجموعه «پخش‌شده‌ها» مشترک بین تب‌ها)؛ اولین بارگذاری بی‌صدا؛ اعلان مرورگر با مجوز صریح کاربر؛ رعایت Autoplay (صدا پس از اولین تعامل). |
| **نمودارها** | `DonutChart` (حلقه‌ای/دایره‌ای) و `ColumnChart` با SVG داخلی: سایه چندلایه، Hover/Focus، Tooltip، انیمیشن (با احترام به reduced-motion)، پالت استاندارد با پوسته تیره، Responsive، Skeleton، Empty، Error، متن جایگزین قابل‌خواندن. در گزارش‌ها (انتخاب حلقه‌ای/دایره‌ای/میله‌ای؛ میله‌ای قبلی حفظ شد)، داشبورد HR و Bradford. |
| **Bradford** | صفحه `/hr/bradford` (فقط HR): بازه ۳۰/۹۰/۱۸۰/۳۶۵/سفارشی؛ فیلتر شرکت/دپارتمان/مدیر؛ تعداد دوره، مجموع روز، امتیاز، مقایسه با دوره قبل، توزیع سطوح، روند ماهانه، مقایسه واحدها، ۱۰ نفر برتر، فهرست «نیازمند بررسی HR»، پنل جزئیات کارمند + یادداشت HR؛ آستانه‌ها، انواع مشمول و سیاست تبدیل ساعتی قابل ویرایش (با دلیل و ثبت در حسابرسی). |

قواعد Bradford اعمال‌شده: فقط تأییدشده و گذشته؛ فقط انواع مشمول (پیش‌فرض: استعلاجی)؛ فقط روز کاری (الگوی قرارداد در صورت وجود، وگرنه الگوی پیش‌فرض سازمان با اعلام در پنل)؛ تعطیلات رعایت می‌شود؛ غیبت‌هایی که بینشان روز کاری نیست یک دوره‌اند؛ ساعتی فقط با سیاست تبدیل و به‌صورت کسری از روز؛ رکورد ناقص امتیاز نمی‌سازد؛ اگر فهرست غیبت‌ها کامل بارگذاری نشود امتیازی نمایش داده نمی‌شود.

## ۵. هنوز ناقص / محدودیت‌ها
- ثبت **غیبت ساعتی توسط HR** (`HrAbsencePage`) افزوده نشد؛ فرم HR فقط روزانه است.
- **ویرایش** درخواست ساعتی از UI وجود ندارد (در کد قبلی هم UI ویرایش نبود).
- هماهنگی تب‌ها در **Demo** فقط برای تنظیمات و اعلان‌های پخش‌شده است؛ چون Store دمو در `sessionStorage` هر تب جداست، فهرست اعلان بین تب‌های Demo هم‌گام نمی‌شود (با Backend واقعی از سرور خوانده می‌شود).
- مسیر `/settings` همچنان فقط برای مدیر سامانه است (طبق ماتریس مجوزها)؛ HR آستانه‌ها و انواع Bradford را از همان صفحه Bradford ویرایش می‌کند، که در Backend واقعی تابع مجوز سرور است.
- جابه‌جایی دستی کاربر بین ساعت‌ها در مرورگرهای بدون پشتیبانی `type="time"` به ورودی متنی تبدیل می‌شود.
- مرور بصری در مرورگر واقعی (اسکرین‌شات، Responsive روی دستگاه) انجام **نشد**؛ فقط smoke test با jsdom (بخش ۹).

## ۶. فایل‌های ایجادشده (frontend)
`src/lib/`: `bradfordAnalysis.ts`، `deadline.ts`، `holidayDates.ts`، `notificationEngine.ts` — `src/components/`: `charts.tsx`، `Deadline.tsx` — `src/pages/`: `BradfordPage.tsx`، `NotificationCenter.tsx` — `src/state/Notifications.tsx` — `src/styles/features.css` — `scripts/run-tests.mjs` — `tests/`: `autoCancel`، `hourlyLeave`، `bradford`، `notifications`، `charts` (`*.test.ts`) — و `docs/continuation-audit-report.md`، `docs/continuation-report.md`.

## ۷. فایل‌های تغییرکرده
`package.json` (فقط اسکریپت `test`)، `App.tsx`، `api/demo.ts`، `components/Layout.tsx`، `components/ui.tsx` (افزودن `Segmented`)، `lib/leaveDisplay.ts`، `lib/notificationPrefs.ts`، `pages/AdminPages.tsx`، `pages/CalendarPages.tsx`، `pages/DashboardPage.tsx`، `pages/HrPages.tsx`، `pages/RequestsPages.tsx`، `styles/global.css` (یک خط `@import`)، `styles/tokens.css` (پالت نمودار). `CHANGES.md` یک بخش افزوده شد. وابستگی جدیدی نصب نشد.

## ۸. وضعیت API و نیازمندی‌های Backend
تفکیک سه سطح: **پیاده‌سازی‌شده در Frontend** / **آماده اتصال** / **نیازمند توسعه Backend**.

| مورد | وضعیت |
|---|---|
| UI مرخصی ساعتی، لغو خودکار، اعلان، نمودار، Bradford | پیاده‌سازی‌شده؛ با **Demo** عملیاتی |
| ارسال `durationKind/startTime/endTime/durationMinutes` در `POST /leave-requests/` | آماده اتصال؛ **نیازمند Backend** (فیلد و اعتبارسنجی و محاسبه روز، تداخل، تقویم) |
| `autoCancelPolicyDays/expiresAt/autoCancelledAt/autoCancelReason`، وضعیت `AUTO_CANCELLED` | **نیازمند Backend** |
| **اجرای واقعی لغو خودکار** | **نیازمند Backend** (Job زمان‌بندی‌شده). در مرورگر بسته هیچ لغوی انجام نمی‌شود؛ شبیه‌سازی Demo فقط هنگام باز بودن جلسه است. |
| `GET /policy/client` | آماده اتصال؛ در نبود آن مقادیر پیش‌فرض (`DEFAULT_CLIENT_POLICY`) |
| اعلان خارج از مرورگر (Web Push)، اعلان وقتی مرورگر بسته است | **نیازمند زیرساخت Web Push و Backend**؛ عملیاتی معرفی نمی‌شود |
| `kind/category` روی `NotificationItem` | آماده؛ اگر سرور نفرستد نوع از متن حدس زده می‌شود |
| Bradford: API تجمیعی | **توصیه می‌شود** (`/hr/bradford`)؛ فعلاً تحلیل در مرورگر روی همه صفحه‌های `/leave-requests/` (تا ۴۰ صفحه) انجام می‌شود و در صورت کامل نبودن داده امتیاز نمایش داده نمی‌شود |
| `/hr/bradford-notes/`، `PATCH`/ذخیره تنظیمات Bradford | **نیازمند Backend** (نقش HR) |
| ثبت `POST /leave-requests/{id}/{action}` بدون اسلش پایانی | بدون تغییر؛ هماهنگی Router (یادداشت قبلی تیم) |

## ۹. نتایج تست
- **آزمون واحد** (`npm test`): ۳۲ تست، **۳۲ موفق، ۰ ناموفق** (لغو خودکار، مرخصی ساعتی، Bradford، موتور اعلان، ریاضیات نمودار). دو شکست اولیه از اشتباه خود آزمون‌ها بود (قالب مدت و پنجشنبه تعطیل) و آزمون اصلاح شد؛ کد محصول تغییر نکرد.
- **Smoke test jsdom** (خارج از پروژه، با ورود Demo به‌عنوان HR): ورود، داشبورد HR، فرم ساعتی، فهرست و جزئیات (لغو خودکار نمونه Demo)، مرکز اعلان، Bradford، گزارش‌ها، تقویم — ۱۲ بررسی موفق. تنها `console.error`ها هشدارهای `act()` خود jsdom بودند.
- Lint: ESLint در پروژه پیکربندی نشده؛ اجرا نشد (به‌جای آن `tsc` با `strict` و `noUnused*`).
- تست‌های Backend: اجرا/تغییر داده نشد (خارج از محدوده).
- بررسی Responsive در مرورگر واقعی: انجام نشد.

## ۱۰. نتیجه Build
`npm run build` (شامل `tsc --noEmit`): **موفق** — JS ≈ ۳۴۰ kB (gzip ≈ ۱۰۸ kB)، CSS ≈ ۲۶ kB.

## ۱۱. مشکلات باقی‌مانده
۱. نبود Git در آرشیو. ۲. فونت Vazirmatn از Google Fonts (یادداشت قبلی؛ پیشنهاد self-host). ۳. `FormatDurationFa` برای ۱ ساعت رقم فارسی و برای بقیه لاتین نشان می‌دهد (کد Cursor؛ تغییر نیافت). ۴. تنظیمات تکراری seed/EXTRA_SETTINGS در `demo.ts` (بی‌ضرر). ۵. هشدار: داده Bradford دمو شامل سابقه‌ی ساختگی «علی رضایی» است و برچسب Demo دارد.

## ۱۲. پیشنهاد ادامه
Backend: فیلدهای ساعتی، Job لغو خودکار، `/policy/client`، API تجمیعی Bradford، یادداشت‌ها. Frontend: ثبت غیبت ساعتی برای HR، ESLint، آزمون مرورگر (Playwright) با بازبینی Responsive/تیره، self-host فونت.

## متن پیشنهادی Commit (انجام نشده)
```
feat(frontend): hourly leave UI, auto-cancel deadlines, notification center, SVG charts, Bradford HR dashboard

- hourly/daily toggle with validation, overlap check; shown in lists, detail, calendar, timeline
- approval deadline column/card, HR overview; boolean settings as select
- NotificationsProvider: sound, silent/off, tab title + favicon badge, cross-tab sync, dedupe, browser notifications
- in-house Donut/Pie/Column SVG charts (dark mode, tooltip, skeleton/empty/error)
- /hr/bradford dashboard + analysis lib; demo bradford report now computed
- unit tests (node:test via esbuild), no new dependencies
```

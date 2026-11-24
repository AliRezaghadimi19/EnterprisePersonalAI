# سامانه هوش مصنوعی سازمانی | Enterprise AI Platform

پلتفرم جامع چت هوش مصنوعی سازمانی با احراز هویت داخلی و Active Directory، پایگاه دانش (RAG)، مدیریت مدل‌ها و سهمیه‌بندی مصرف — با رابط کاربری فارسی راست‌به‌چپ.

## معماری

| سرویس | تکنولوژی | پورت |
|---|---|---|
| Backend | Python 3.11 + FastAPI + Uvicorn | 8000 |
| Frontend | Next.js 14 + Tailwind CSS (RTL, Vazirmatn) | 3000 |
| Database | SQLite (تعبیه‌شده، سوارشده روی volume داکر) | — |

## اجرای سریع با داکر

```bash
# 1) کلون پروژه
git clone https://github.com/AliRezaghadimi19/EnterprisePersonalAI.git
cd EnterprisePersonalAI

# 2) فایل تنظیمات را بسازید (یا .env موجود را نگه دارید)
cp .env.example .env

# 3) بیلد و اجرای همه سرویس‌ها
docker compose up -d --build

# 4) بررسی سلامت
docker compose ps
curl http://localhost:8000/api/v1/health
```

سپس مرورگر را باز کنید:

- 🌐 اپلیکیشن: http://localhost:3000
- 📚 مستندات API (Swagger): http://localhost:8000/docs

### حساب پیش‌فرض مدیر کل

| نام کاربری | رمز عبور |
|---|---|
| `admin` | `Enterprise@Admin123!` |

⚠️ در محیط عملیاتی حتماً مقدارهای `SUPER_ADMIN_PASSWORD`، `SECRET_KEY` و `FERNET_KEY` را در فایل `.env` تغییر دهید.

### اجرای داکر - نکات

- **پایگاه داده**: SQLite روی volume داکر (`backend_data`) ذخیره می‌شود — داده‌ها بین ری‌استارت و ری‌بیلد کانتینر باقی می‌مانند.
- **مسیر دیتابیس**: متغیر `DB_PATH` (پیش‌فرض `/data/enterprise_ai.db`) در کانتینر.
- **آدرس API فرانت**: در زمان build از `NEXT_PUBLIC_API_URL` در compose خوانده می‌شود. اگر می‌خواهید فرانت روی سرور دیگری به بک‌اند وصل شود، این متغیر را در `.env` تغییر دهید و دوباره بیلد کنید.
- **ورود به کانتینر بک‌اند** (برای خطایابی یا دسترسی مستقیم به دیتابیس):
  ```bash
  docker compose exec backend bash
  docker compose exec backend sqlite3 /data/enterprise_ai.db
  ```
- **استاپ و پاک‌سازی کامل**:
  ```bash
  docker compose down          # توقف کانتینرها (داده‌ها باقی می‌مانند)
  docker compose down -v       # توقف و حذف کامل داده‌ها
  ```

### رفتار سیاست‌های پاسخ‌دهی

- **FREE_AI**: کاربر می‌تواند هر سؤالی بپرسد — خارج از پایگاه دانش هم پاسخ می‌گیرد.
- **HYBRID**: اگر پایگاه دانش جواب در دامنه‌ای داشته باشد، از آن استفاده می‌شود؛ در غیر این صورت مدل آزادانه پاسخ می‌دهد.
- **KNOWLEDGE_ONLY**: کاربر فقط از پایگاه دانش پاسخ می‌گیرد؛ سؤالات خارج از دامنه رد می‌شوند.

### حذف گفتگو

- کاربر می‌تواند گفتگوهای خودش را حذف کند (دکمه حذف با hover در لیست گفتگوها) — گفتگو برای کاربر مخفی می‌شود اما برای ادمین در بخش «مکالمات» با نشان «حذف‌شده توسط کاربر» باقی می‌ماند.
- ادمین می‌تواند گفتگو را به‌طور کامل حذف کند (حذف فیزیکی از دیتابیس).

## اجرای بدون داکر (حالت مستقل)

بک‌اند به‌صورت مستقل با SQLite هم اجرا می‌شود (بدون نیاز به هیچ وابستگی خارجی):

```bash
cd backend
python run_server.py          # سرور مستقل روی http://localhost:8000
# یا با FastAPI:
uvicorn app.main:app --port 8000
```

و فرانت‌اند:

```bash
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

## پیکربندی

همه تنظیمات از طریق فایل `.env` (بر اساس `.env.example`) انجام می‌شود — هیچ مقدار حساسی داخل کد هارد‌کد نشده است. متغیرهای مهم:

| متغیر | توضیح |
|---|---|
| `SECRET_KEY` | کلید امضای JWT (در عملیاتی حتماً عوض کنید) |
| `FERNET_KEY` | کلید رمزنگاری کلیدهای API و رمز AD (Base64 ۳۲ بایت) |
| `SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` | اعتبارنامه مدیر کل اولیه |
| `AUTH_MODE` | روش ورود مجاز: `BOTH` (پیش‌فرض)، `LOCAL_ONLY`، `AD_ONLY` |
| `DEFAULT_RESPONSE_POLICY` | سیاست پاسخ پیش‌فرض: `HYBRID`، `KNOWLEDGE_ONLY`، `FREE_AI` |
| `DEFAULT_AI_LANGUAGE` | زبان پیش‌فرض پاسخ: `fa` یا `en` |
| `DB_PATH` | مسیر فایل SQLite (در داکر: `/data/enterprise_ai.db`) |
| `UPLOAD_DIR` | مسیر ذخیره فایل‌های آپلودی |
| `NEXT_PUBLIC_API_URL` | آدرس API از نگاه فرانت‌اند (در زمان build) |

## ساختار پروژه

```
├── backend/
│   ├── app/
│   │   ├── api/v1/          # اندپوینت‌های REST (auth, users, chat, knowledge, ...)
│   │   ├── core/            # تنظیمات، دیتابیس، امنیت، LDAP
│   │   ├── schemas/         # مدل‌های Pydantic
│   │   ├── services/        # منطق کسب‌وکار (AI Gateway, RAG, ...)
│   │   └── tests/           # تست‌های واحد
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/app/             # صفحات Next.js App Router (فارسی RTL)
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## قابلیت‌ها

- ✅ احراز هویت محلی + Active Directory/LDAP با provision خودکار کاربران
- ✅ کنترل دسترسی نقش‌محور (RBAC) با نقش‌های سیستمی پیش‌فرض
- ✅ AI Gateway چند-سرویس‌دهنده: OpenAI، Gemini، Anthropic، Ollama — با مدل جایگزین (fallback) خودکار در خطا
- ✅ پایگاه دانش سازمانی با جستجوی معنایی (RAG + embeddings) و آپلود فایل متنی
- ✅ چت سازمانی با تاریخچه، ارجاع به منابع (citations) و سیاست‌های پاسخ‌دهی
- ✅ سهمیه‌بندی روزانه/ماهانه سؤال و توکن به تفکیک کاربر و گروه
- ✅ لاگ ممیزی کامل (Audit Log) رخدادهای امنیتی و عملیات مدیریتی
- ✅ رمزنگاری Fernet برای کلیدهای API و اعتبارنامه‌های AD
- ✅ پنل ادمین کامل ۲۰ صفحه‌ای: داشبورد با نمودار، کاربران، گروه‌ها، نقش‌ها، تنظیمات AD، هوش مصنوعی، پایگاه دانش، اشتراک‌ها، سهمیه‌ها، فایل‌ها، مکالمات، لاگ درخواست‌ها، گزارش‌ها، مصرف API، تنظیمات سامانه و پشتیبان‌گیری
- ✅ خروجی CSV سازگار با اکسل فارسی (BOM) و پشتیبان‌گیری JSON از کل دیتابیس
- ✅ حذف گفتگو توسط کاربر (نرم) با حفظ تاریخچه برای ادمین
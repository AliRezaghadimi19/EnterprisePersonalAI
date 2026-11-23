# سامانه هوش مصنوعی سازمانی | Enterprise AI Platform

پلتفرم جامع چت هوش مصنوعی سازمانی با احراز هویت داخلی و Active Directory، پایگاه دانش (RAG)، مدیریت مدل‌ها و سهمیه‌بندی مصرف — با رابط کاربری فارسی راست‌به‌چپ.

## معماری

| سرویس | تکنولوژی | پورت |
|---|---|---|
| Backend | Python 3.11 + FastAPI + Uvicorn | 8000 |
| Frontend | Next.js 14 + Tailwind CSS (RTL, Vazirmatn) | 3000 |
| Database | PostgreSQL 16 + pgvector | 5432 |
| Cache / Rate Limit | Redis 7.2 | 6379 |
| Object Storage | MinIO (سازگار با S3) | 9000 / 9001 |

## اجرای سریع با داکر

```bash
# 1) فایل تنظیمات را بسازید (یا .env موجود را نگه دارید)
cp .env.example .env

# 2) بیلد و اجرای همه سرویس‌ها
docker compose up -d --build

# 3) بررسی سلامت
docker compose ps
curl http://localhost:8000/health
```

سپس مرورگر را باز کنید:

- 🌐 اپلیکیشن: http://localhost:3000
- 📚 مستندات API (Swagger): http://localhost:8000/docs

### حساب پیش‌فرض مدیر کل

| نام کاربری | رمز عبور |
|---|---|
| `admin` | `Enterprise@Admin123!` |

⚠️ در محیط عملیاتی حتماً مقدارهای `SUPER_ADMIN_PASSWORD`، `SECRET_KEY` و `FERNET_KEY` را در فایل `.env` تغییر دهید.

## اجرای بدون داکر (حالت مستقل)

بک‌اند به‌صورت مستقل با SQLite هم اجرا می‌شود (بدون نیاز به هیچ وابستگی خارجی):

```bash
cd backend
python run_server.py          # سرور مستقل روی http://localhost:8000
# یا با FastAPI:
uvicorn app.main:app --port 8000
```

## ساختار پروژه

```
├── backend/
│   ├── app/
│   │   ├── api/v1/          # اندپوینت‌های REST (auth, users, chat, knowledge, ...)
│   │   ├── core/            # تنظیمات، دیتابیس، امنیت، LDAP
│   │   ├── schemas/         # مدل‌های Pydantic
│   │   ├── services/        # منطق کسب‌وکار (AI Gateway, RAG, ...)
│   │   └── tests/           # تست‌های واحد
│   ├── init-scripts/        # اسکریپت‌های اولیه Postgres (pgvector)
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
- ✅ AI Gateway چند-سرویس‌دهنده: OpenAI، Gemini، Anthropic، Ollama
- ✅ پایگاه دانش سازمانی با جستجوی معنایی (RAG + pgvector)
- ✅ چت سازمانی با تاریخچه، ارجاع به منابع و سیاست‌های پاسخ‌دهی
- ✅ سهمیه‌بندی روزانه/ماهانه سؤال و توکن به تفکیک کاربر و گروه
- ✅ لاگ ممیزی کامل (Audit Log) رخدادهای امنیتی
- ✅ رمزنگاری Fernet برای کلیدهای API و اعتبارنامه‌های AD

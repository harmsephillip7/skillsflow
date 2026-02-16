# SkillsFlow ERP - Deployment Guide

## Quick Start for Production Deployment

### Prerequisites
- PostgreSQL database (Neon, Supabase, Railway, or similar)
- Python 3.11+
- Node.js (for Vercel CLI, optional)

---

## Database Setup

### 1. Create PostgreSQL Database

**Option A: Neon (Recommended - Free tier)**
1. Sign up at [neon.tech](https://neon.tech)
2. Create a new project
3. Copy the connection string: `postgresql://user:password@host/database?sslmode=require`

**Option B: Supabase (Free tier)**
1. Sign up at [supabase.com](https://supabase.com)
2. Create new project
3. Settings > Database > Connection string (URI)

### 2. Configure Environment Variables

Create a `.env` file (DO NOT commit to git) or set in your hosting platform:

```bash
# Required
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
DJANGO_SECRET_KEY=your-super-secret-key-min-50-chars
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,.vercel.app

# Security (required for HTTPS)
CSRF_TRUSTED_ORIGINS=https://your-domain.com

# Optional - Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@your-domain.com
```

### 3. Generate a Secret Key
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Run Migrations
```bash
python manage.py migrate
```

### 5. Load Initial Data
```bash
# Load core reference data (users, qualifications, workflows, etc.)
python manage.py loaddata core_data.json

# OR load full deployment data
python manage.py loaddata deployment_data.json
```

---

## ⚠️ Important Considerations

**Vercel is a serverless platform** primarily designed for frontend applications and serverless functions. Django works on Vercel but with significant limitations:

### Limitations on Vercel:
1. **No persistent filesystem** - SQLite database won't work
2. **Cold start times** - First request may be slow
3. **Function timeouts** - Max 30 seconds (Hobby) or 60s (Pro)
4. **No background tasks** - Celery won't work on Vercel
5. **No persistent media storage** - Need external storage (S3, Azure Blob)

### What Works:
- ✅ Django views and templates
- ✅ Static files (via WhiteNoise)
- ✅ External PostgreSQL database
- ✅ External Redis (for sessions)
- ✅ API endpoints

---

## Prerequisites

1. **Vercel Account** - Sign up at [vercel.com](https://vercel.com)
2. **Vercel CLI** - Install globally
3. **External PostgreSQL Database** - Options:
   - [Neon](https://neon.tech) - Free tier available
   - [Supabase](https://supabase.com) - Free tier available
   - [Railway](https://railway.app)
   - [PlanetScale](https://planetscale.com)
   - [ElephantSQL](https://elephantsql.com)

---

## Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

---

## Step 2: Set Up External Database

### Option A: Neon (Recommended - Free)
1. Go to [neon.tech](https://neon.tech) and create account
2. Create a new project
3. Copy the connection string:
   ```
   postgresql://user:password@host/database?sslmode=require
   ```

### Option B: Supabase (Free)
1. Go to [supabase.com](https://supabase.com)
2. Create new project
3. Go to Settings > Database > Connection string
4. Copy the URI connection string

---

## Step 3: Environment Variables

Set these in Vercel Dashboard or via CLI:

```bash
# Required
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
DJANGO_SECRET_KEY=your-super-secret-key-generate-a-new-one
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=.vercel.app,your-domain.com

# CSRF
CSRF_TRUSTED_ORIGINS=https://your-app.vercel.app,https://your-domain.com

# CORS (if you have a separate frontend)
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

### Generate a new SECRET_KEY:
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Step 4: Deploy to Vercel

### Method 1: Via CLI
```bash
cd skillsflow

# Login to Vercel
vercel login

# Deploy (first time - will prompt for settings)
vercel

# Deploy to production
vercel --prod
```

### Method 2: Via GitHub Integration
1. Push code to GitHub
2. Go to [vercel.com/new](https://vercel.com/new)
3. Import your GitHub repository
4. Configure:
   - Framework Preset: Other
   - Root Directory: `skillsflow`
   - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Output Directory: (leave empty)
5. Add environment variables
6. Deploy

---

## Step 5: Run Migrations

After deployment, you need to run migrations against your production database:

```bash
# Set the DATABASE_URL locally temporarily
export DATABASE_URL="postgresql://user:password@host/database?sslmode=require"

# Run migrations
cd skillsflow
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

Or use the Vercel CLI to run commands:
```bash
vercel env pull .env.local
source .env.local
python manage.py migrate
```

---

## Step 6: Media Files (Optional)

For media file uploads, configure external storage:

### AWS S3
```python
# settings.py
if not DEBUG:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
```

### Azure Blob Storage
```python
# settings.py
if not DEBUG:
    DEFAULT_FILE_STORAGE = 'storages.backends.azure_storage.AzureStorage'
    AZURE_ACCOUNT_NAME = os.environ.get('AZURE_ACCOUNT_NAME')
    AZURE_ACCOUNT_KEY = os.environ.get('AZURE_ACCOUNT_KEY')
    AZURE_CONTAINER = os.environ.get('AZURE_CONTAINER')
```

---

## Troubleshooting

### Error: "Function timeout"
- Reduce database queries
- Add caching
- Upgrade to Vercel Pro for longer timeouts

### Error: "Cold start"
- First request may take 5-10 seconds
- Use Vercel's cron to keep warm

### Error: "Database connection"
- Ensure DATABASE_URL is set correctly
- Check SSL requirements (`?sslmode=require`)

### Error: "Static files not loading"
- Run `collectstatic` in build command
- Ensure WhiteNoise middleware is configured

---

## Alternative Deployment Options

For a Django app of this size with Celery tasks, consider:

1. **Railway** - Better Django support, includes Celery
2. **Render** - Native Django support
3. **Fly.io** - Docker-based, good for full-stack
4. **DigitalOcean App Platform** - Full Django support
5. **Heroku** - Classic Django deployment

These platforms support:
- Persistent databases
- Background workers (Celery)
- Media file storage
- Longer running processes

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `DJANGO_DEBUG` | Yes | Set to `False` |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | Yes | Full URLs with https:// |
| `REDIS_URL` | No | For caching (optional on Vercel) |
| `AWS_ACCESS_KEY_ID` | No | For S3 media storage |
| `AWS_SECRET_ACCESS_KEY` | No | For S3 media storage |
| `AWS_STORAGE_BUCKET_NAME` | No | For S3 media storage |

---

## Quick Deploy Checklist

- [ ] Create Vercel account
- [ ] Set up external PostgreSQL database
- [ ] Generate new DJANGO_SECRET_KEY
- [ ] Configure environment variables in Vercel
- [ ] Deploy via CLI or GitHub
- [ ] Run migrations
- [ ] Create superuser
- [ ] Test the deployment
- [ ] Configure custom domain (optional)

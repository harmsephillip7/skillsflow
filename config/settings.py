"""
Django settings for SkillsFlow ERP project.
Production settings should override via environment variables.
"""

from pathlib import Path
import os
from datetime import timedelta

# Load environment variables from .env file (for local development)
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-change-this-in-production-very-long-secret-key-here'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

# Allowed hosts - include Vercel domains
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,.vercel.app').split(',')

# CSRF trusted origins for Vercel
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS', 
    'http://localhost:8000,http://127.0.0.1:8000'
).split(',')

# Vercel deployment detection
VERCEL_ENV = os.environ.get('VERCEL', False)
if VERCEL_ENV:
    DEBUG = False
    ALLOWED_HOSTS = ['.vercel.app', '.now.sh'] + ALLOWED_HOSTS


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third party apps
    'ninja',
    'corsheaders',
    'simple_history',
    'django_filters',
    
    # Local apps
    'core.apps.CoreConfig',
    'tenants.apps.TenantsConfig',
    'learners.apps.LearnersConfig',
    'academics.apps.AcademicsConfig',
    'assessments.apps.AssessmentsConfig',
    'logistics.apps.LogisticsConfig',
    'crm.apps.CrmConfig',
    'corporate.apps.CorporateConfig',
    'finance.apps.FinanceConfig',
    'lms_sync.apps.LmsSyncConfig',
    'portals.apps.PortalsConfig',
    'reporting.apps.ReportingConfig',
    'workflows.apps.WorkflowsConfig',  # Workflow engine for user journeys
    'trade_tests.apps.TradeTestsConfig',  # Trade test management
    'intakes.apps.IntakesConfig',  # Intake and enrollment management
    'integrations.apps.IntegrationsConfig',  # Integration Hub for external services
    'tenders.apps.TendersConfig',  # Tender management and web scraping
    'hr.apps.HrConfig',  # Human Resources management
    'support.apps.SupportConfig',  # Support ticketing and knowledge base
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.campus_context',  # Campus switcher context
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# PostgreSQL for both development and production (via Neon)
# Set DATABASE_URL environment variable to your Neon connection string
# Example: postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    # Fallback to SQLite for local development without DATABASE_URL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Custom User Model
AUTH_USER_MODEL = 'core.User'


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-za'

TIME_ZONE = 'Africa/Johannesburg'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =====================================================
# CORS Settings
# =====================================================
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',')

CORS_ALLOW_CREDENTIALS = True


# =====================================================
# Redis & Celery Settings
# =====================================================
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'sync-moodle-enrollments': {
        'task': 'lms_sync.tasks.sync_all_enrollments',
        'schedule': timedelta(hours=1),
    },
    'sync-moodle-grades': {
        'task': 'lms_sync.tasks.sync_all_grades',
        'schedule': timedelta(hours=6),
    },
    'check-overdue-invoices': {
        'task': 'finance.tasks.mark_overdue_invoices',
        'schedule': timedelta(hours=24),
    },
    'send-payment-reminders': {
        'task': 'finance.tasks.send_payment_reminders',
        'schedule': timedelta(hours=24),
    },
    'process-scheduled-reports': {
        'task': 'reporting.tasks.process_scheduled_reports',
        'schedule': timedelta(hours=1),
    },
}


# =====================================================
# Cache Settings
# =====================================================
# Use Redis in production, local memory for development
if REDIS_URL and not DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }


# =====================================================
# Session Settings
# =====================================================
# Use database sessions for development (no Redis required)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 7  # 7 days
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True


# =====================================================
# Email Settings
# =====================================================
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@skillsflow.co.za')


# =====================================================
# File Storage (Azure/S3)
# =====================================================
USE_CLOUD_STORAGE = os.environ.get('USE_CLOUD_STORAGE', 'False').lower() == 'true'

if USE_CLOUD_STORAGE:
    # Azure Blob Storage
    AZURE_ACCOUNT_NAME = os.environ.get('AZURE_ACCOUNT_NAME', '')
    AZURE_ACCOUNT_KEY = os.environ.get('AZURE_ACCOUNT_KEY', '')
    AZURE_CONTAINER = os.environ.get('AZURE_CONTAINER', 'media')
    DEFAULT_FILE_STORAGE = 'storages.backends.azure_storage.AzureStorage'


# =====================================================
# Logging
# =====================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# =====================================================
# Security Settings (Production)
# =====================================================
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True


# =====================================================
# Django Ninja API Settings
# =====================================================
NINJA_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}


# =====================================================
# Simple History Settings
# =====================================================
SIMPLE_HISTORY_REVERT_DISABLED = True


# =====================================================
# Application Settings
# =====================================================

# PDF Generation
WEASYPRINT_BASEURL = os.environ.get('WEASYPRINT_BASEURL', '/')

# WhatsApp API
WHATSAPP_API_VERSION = 'v17.0'
WHATSAPP_API_BASE_URL = 'https://graph.facebook.com'

# QCTO/NLRD Settings
QCTO_PROVIDER_CODE = os.environ.get('QCTO_PROVIDER_CODE', '')
NLRD_API_URL = os.environ.get('NLRD_API_URL', '')

# PayFast Settings
PAYFAST_MERCHANT_ID = os.environ.get('PAYFAST_MERCHANT_ID', '')
PAYFAST_MERCHANT_KEY = os.environ.get('PAYFAST_MERCHANT_KEY', '')
PAYFAST_PASSPHRASE = os.environ.get('PAYFAST_PASSPHRASE', '')
PAYFAST_SANDBOX = DEBUG

# Sage Intacct
SAGE_INTACCT_SENDER_ID = os.environ.get('SAGE_INTACCT_SENDER_ID', '')

# OpenAI API
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Anthropic API
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# =====================================================
# Authentication Settings
# =====================================================
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

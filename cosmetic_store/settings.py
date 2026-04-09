import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_URL = '/static/'

# Optional: if you want a project-level static folder
#STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_DIRS = []



# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
#SECRET_KEY = 'django-insecure-3s(3(b9vnp25b-+f1init!8%2@e-0yx_g*p5b7zjk#nwx0&ypd'
SECRET_KEY = os.environ.get('SECRET_KEY','test123')
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

allowed_hosts = os.environ.get('ALLOWED_HOSTS')
ALLOWED_HOSTS = (
    [host.strip() for host in allowed_hosts.split(',') if host.strip()]
    if allowed_hosts
    else ['*']
)

csrf_trusted_origins = os.environ.get('CSRF_TRUSTED_ORIGINS')
if csrf_trusted_origins:
    CSRF_TRUSTED_ORIGINS = [
        origin.strip()
        for origin in csrf_trusted_origins.split(',')
        if origin.strip()
    ]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'store',
]
SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cosmetic_store.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # Optional global templates folder
        'APP_DIRS': True,                  # Looks for templates inside apps
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'cosmetic_store.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

#DATABASES = {
 #   'default': {
 #       'ENGINE': 'django.db.backends.mysql',
 #       'NAME': 'beautyhub_db',
 #       'USER': 'root',
 #       'PASSWORD': 'root123',
  #      'HOST': '127.0.0.1',
  #      'PORT': '3306',
  #  }
#}

database_url = os.environ.get('DATABASE_URL')
render_disk_path = os.environ.get('RENDER_DISK_PATH')
sqlite_path = os.environ.get('SQLITE_PATH')

default_sqlite_path = BASE_DIR / 'db.sqlite3'
if render_disk_path:
    default_sqlite_path = Path(render_disk_path) / 'db.sqlite3'
if sqlite_path:
    default_sqlite_path = Path(sqlite_path)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(default_sqlite_path),
    }
}

if database_url:
    try:
        import dj_database_url
    except ImportError:
        dj_database_url = None

    if dj_database_url is not None:
        DATABASES['default'] = dj_database_url.parse(
            database_url,
            conn_max_age=int(os.environ.get('DB_CONN_MAX_AGE', '600')),
            ssl_require=os.environ.get('DB_SSL_REQUIRE', 'true').lower() == 'true',
        )

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

#STATIC_URL = 'static/'
STATIC_URL = '/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

production_security_enabled = (
    not DEBUG
    and os.environ.get(
        'ENABLE_PRODUCTION_SECURITY',
        os.environ.get('RENDER', 'false'),
    ).lower() == 'true'
)

if production_security_enabled:
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'true').lower() == 'true'
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))

AUTHENTICATION_BACKENDS = [
    'store.auth_backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_CURRENCY = os.environ.get('RAZORPAY_CURRENCY', 'INR')

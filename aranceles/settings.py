from pathlib import Path
import os
import logging
import sys
import gc

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-change-this')

# SECURITY WARNING: don't run with debug turned on in production!
# CORREGIDO: Detectar DEBUG de forma más robusta
DEBUG_ENV = os.environ.get('DJANGO_DEBUG', 'False')
DEBUG = DEBUG_ENV.lower() in ('true', '1', 'yes', 'on')

# Para desarrollo local, forzar DEBUG=True si no está configurado
if not os.environ.get('DJANGO_DEBUG') and SECRET_KEY == 'dev-secret-key-change-this':
    DEBUG = True
    
print(f"DEBUG MODE: {DEBUG}")  # Para verificar

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
if not DEBUG:
    ALLOWED_HOSTS.extend(['excel-os.onrender.com', '*.onrender.com'])

# ================================
# OPTIMIZACIONES CRÍTICAS PARA RENDER GRATUITO
# ================================

# Configurar garbage collection MUY agresivo
gc.set_threshold(50, 5, 5)  # Default es (700, 10, 10)

# Configurar pandas para usar MÍNIMA memoria
import pandas as pd
pd.set_option('mode.copy_on_write', True)
pd.set_option('display.max_columns', 10)  # REDUCIDO de 20
pd.set_option('display.max_rows', 50)     # NUEVO límite

# Límites de memoria ULTRA restrictivos para Render gratuito
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # REDUCIDO a 5MB (era 10MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024    # REDUCIDO a 5MB (era 10MB)
FILE_UPLOAD_PERMISSIONS = 0o644

# Configuración específica para Render
if not DEBUG:
    USE_FILE_LOGGING = False  # NUNCA usar archivos en producción
    TEMP_DIR = '/tmp'  # Usar /tmp en lugar de /dev/shm que puede no existir
    
    # CONFIGURACIÓN CRÍTICA: Límites de procesamiento
    MAX_EXCEL_ROWS = 1000      # NUEVO: máximo 1000 filas por Excel
    MAX_CONCURRENT_PROCESS = 1  # NUEVO: solo 1 proceso a la vez
    FORCE_GC_EVERY_REQUEST = True  # NUEVO: GC después de cada request
else:
    USE_FILE_LOGGING = True
    TEMP_DIR = None
    MAX_EXCEL_ROWS = 5000
    MAX_CONCURRENT_PROCESS = 2
    FORCE_GC_EVERY_REQUEST = False

# ================================
# APLICACIONES MÍNIMAS
# ================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.contenttypes',  # Necesario para admin
    'django.contrib.auth',          # Necesario para admin
    'django.contrib.sessions',      # Necesario para formularios
    'django.contrib.messages',      # Para mensajes flash
    'django.contrib.staticfiles',   # Para archivos estáticos
    'excel_app',
]

# ================================
# MIDDLEWARE MÍNIMO
# ================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Solo agregar middlewares personalizados si la app excel_app existe
try:
    import excel_app.middleware
    MIDDLEWARE.extend([
        'excel_app.middleware.FileUploadSecurityMiddleware',
        'excel_app.middleware.RequestLoggingMiddleware', 
        'excel_app.middleware.ResponseTimeMiddleware',
        'excel_app.middleware.FileCleanupMiddleware',
        'excel_app.middleware.ExcelProcessingMiddleware',  # DEBE IR AL FINAL
    ])
except ImportError:
    pass

# Solo agregar cleanup middleware en producción
if not DEBUG:
    try:
        MIDDLEWARE.append('excel_app.middleware.FileCleanupMiddleware')
    except:
        pass

ROOT_URLCONF = 'aranceles.urls'

# ================================
# TEMPLATES MÍNIMOS
# ================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'django.contrib.auth.context_processors.auth',
            ],
        },
    },
]

WSGI_APPLICATION = 'aranceles.wsgi.application'

# ================================
# BASE DE DATOS MÍNIMA
# ================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,  # Timeout para SQLite
        }
    }
}

# ================================
# CONFIGURACIÓN INTERNACIONAL
# ================================
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = False  # DESHABILITADO para ahorrar memoria
USE_TZ = True

# ================================
# ARCHIVOS ESTÁTICOS OPTIMIZADOS
# ================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Solo usar WhiteNoise en producción
if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files con límites
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ================================
# LOGGING ULTRA MINIMALISTA PARA RENDER
# ================================
if not DEBUG and not USE_FILE_LOGGING:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
                'stream': sys.stdout,
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': 'ERROR',
                'propagate': False,
            },
            'excel_app': {
                'handlers': ['console'],
                'level': 'ERROR',
                'propagate': False,
            },
        },
    }
else:
    # Logging para desarrollo (mínimo)
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    }

# ================================
# CONFIGURACIÓN DE SEGURIDAD
# ================================
if not DEBUG:
    # Solo para producción
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
else:
    # Para desarrollo - DESHABILITAR COMPLETAMENTE SSL
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = None
    SECURE_BROWSER_XSS_FILTER = False
    SECURE_CONTENT_TYPE_NOSNIFF = False
    X_FRAME_OPTIONS = 'SAMEORIGIN'
    
    # Variables adicionales para asegurar HTTP
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    
    # CRÍTICO: Deshabilitar redirecciones HTTPS
    USE_TLS = False
    SECURE_REDIRECT_EXEMPT = []

# ================================
# CONFIGURACIÓN EXCEL ULTRA OPTIMIZADA
# ================================
EXCEL_PROCESSING = {
    'MAX_ROWS_IN_MEMORY': MAX_EXCEL_ROWS,
    'CHUNK_SIZE': 100,  # REDUCIDO de 500
    'ALLOWED_EXTENSIONS': ['.xlsx', '.xls'],
    'MAX_FILE_SIZE': FILE_UPLOAD_MAX_MEMORY_SIZE,
    'TEMP_DIR': TEMP_DIR,
    'FORCE_GC': FORCE_GC_EVERY_REQUEST,
    'MAX_CONCURRENT': MAX_CONCURRENT_PROCESS,
}

# Validación de passwords mínima
AUTH_PASSWORD_VALIDATORS = []  # Remover validadores para ahorrar memoria

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================================
# CONFIGURACIONES ADICIONALES PARA RENDER
# ================================
# Session settings para ahorrar memoria
SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Cache settings (usar memoria local)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'OPTIONS': {
            'MAX_ENTRIES': 100,  # Límite bajo
        }
    }
}

# ================================
# CONFIGURACIÓN ESPECÍFICA PARA DESARROLLO LOCAL
# ================================
if DEBUG:
    # Asegurar que no hay redirecciones SSL en desarrollo
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = None
    
    # Configuraciones adicionales para desarrollo
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1', '0.0.0.0'])
    
    # Deshabilitar WhiteNoise en desarrollo
    if 'whitenoise.middleware.WhiteNoiseMiddleware' in MIDDLEWARE:
        MIDDLEWARE.remove('whitenoise.middleware.WhiteNoiseMiddleware')

# Print de verificación
print(f"SECURE_SSL_REDIRECT: {globals().get('SECURE_SSL_REDIRECT', 'Not set')}")
print(f"ALLOWED_HOSTS: {ALLOWED_HOSTS}")
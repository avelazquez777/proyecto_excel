# gunicorn.conf.py - Configuración ULTRA optimizada para Render gratuito
import os
import gc

# === CONFIGURACIÓN CRÍTICA PARA RENDER GRATUITO ===
bind = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
workers = 1  # CRÍTICO: Solo 1 worker para evitar OOM
worker_class = "sync"
worker_connections = 100  # REDUCIDO de 1000
timeout = 120  # REDUCIDO de 300 segundos
keepalive = 2

# === LÍMITES CRÍTICOS DE MEMORIA ===
max_requests = 50  # DRASTICAMENTE REDUCIDO de 500
max_requests_jitter = 10  # REDUCIDO de 50
worker_tmp_dir = "/dev/shm"  # Usar memoria compartida si existe

# === CONFIGURACIONES DE RECICLAJE AGRESIVO ===
preload_app = True  # Precargar para ahorrar memoria
worker_rlimit_nofile = 100  # REDUCIDO de 1000

# === LÍMITES DE MEMORIA AGRESIVOS ===
def when_ready(server):
    """Configurar límites cuando el servidor está listo"""
    import resource
    # Limitar memoria virtual a 400MB (Render gratuito tiene ~512MB)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (400 * 1024 * 1024, 400 * 1024 * 1024))
    except:
        pass

def worker_int(worker):
    """Manejar interrupción del worker"""
    worker.log.info("Worker received INT or QUIT signal")
    gc.collect()  # Forzar garbage collection

def pre_fork(server, worker):
    """Antes de crear worker"""
    gc.collect()  # Limpiar memoria antes de fork

def post_fork(server, worker):
    """Después de crear worker"""
    worker.log.info("Worker spawned (pid: %s)", worker.pid)
    # Configurar garbage collection agresivo
    gc.set_threshold(50, 5, 5)  # Más agresivo que el default (700, 10, 10)

def pre_request(worker, req):
    """Antes de cada request"""
    # Limpiar memoria antes de procesar request
    gc.collect()

def post_request(worker, req, environ, resp):
    """Después de cada request"""
    # Limpiar memoria después de cada request
    gc.collect()

# === CONFIGURACIÓN DE DJANGO ===
django_settings_module = "aranceles.settings"
pythonpath = "."

# === LOGGING MINIMALISTA ===
accesslog = "-"
errorlog = "-"
loglevel = "warning"  # CAMBIADO de "info" a "warning"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)s'  # Formato más corto

# === TIMEOUTS REDUCIDOS ===
graceful_timeout = 60  # REDUCIDO de 120
worker_abort_timeout = 30  # NUEVO: timeout para abortar workers problemáticos
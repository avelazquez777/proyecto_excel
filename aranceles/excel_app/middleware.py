# excel_app/middleware.py
import logging
import traceback
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
import time

logger = logging.getLogger(__name__)

class ExcelProcessingMiddleware:
    """Middleware personalizado para manejo de errores en procesamiento de Excel"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        
        try:
            response = self.get_response(request)
            
            # Log tiempo de procesamiento para requests largos
            processing_time = time.time() - start_time
            if processing_time > 5:  # Más de 5 segundos
                logger.info(f"Request lento: {request.path} - {processing_time:.2f}s")
            
            return response
            
        except Exception as e:
            return self.handle_exception(request, e)

    def handle_exception(self, request, exception):
        """Maneja excepciones no controladas"""
        
        # Log del error
        logger.error(f"Error no controlado en {request.path}: {exception}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Para requests AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': True,
                'message': 'Error interno del servidor'
            }, status=500)
        
        # Para requests normales, mostrar página de error amigable
        if '/excel/' in request.path:
            return self.render_excel_error(request, exception)
        
        # Para otros casos, dejar que Django maneje
        raise exception

    def render_excel_error(self, request, exception):
        """Renderiza página de error específica para la app de Excel"""
        
        error_context = {
            'error_title': 'Error en el Sistema',
            'error_message': 'Ha ocurrido un error inesperado.',
            'show_details': settings.DEBUG,
            'exception_details': str(exception) if settings.DEBUG else None,
        }
        
        # Categorizar errores comunes
        error_str = str(exception).lower()
        
        if 'memory' in error_str or isinstance(exception, MemoryError):
            error_context.update({
                'error_title': 'Error de Memoria',
                'error_message': 'Los archivos son demasiado grandes para procesar. Intente con archivos más pequeños.',
                'suggestions': [
                    'Reduzca el tamaño de los archivos Excel',
                    'Divida el procesamiento en lotes más pequeños',
                    'Contacte al administrador si el problema persiste'
                ]
            })
            
        elif 'permission' in error_str or 'access' in error_str:
            error_context.update({
                'error_title': 'Error de Permisos',
                'error_message': 'Error de permisos del sistema.',
                'suggestions': [
                    'Contacte al administrador del sistema',
                    'Verifique que tenga permisos para subir archivos'
                ]
            })
            
        elif 'timeout' in error_str:
            error_context.update({
                'error_title': 'Timeout de Procesamiento',
                'error_message': 'El procesamiento tomó demasiado tiempo.',
                'suggestions': [
                    'Intente con archivos más pequeños',
                    'Divida el procesamiento en partes',
                    'Intente nuevamente en unos minutos'
                ]
            })
            
        elif 'disk' in error_str or 'space' in error_str:
            error_context.update({
                'error_title': 'Error de Espacio en Disco',
                'error_message': 'No hay suficiente espacio en el servidor.',
                'suggestions': [
                    'Intente más tarde',
                    'Use archivos más pequeños',
                    'Contacte al administrador'
                ]
            })
        
        return render(request, 'excel_app/error.html', error_context, status=500)


class FileUploadSecurityMiddleware:
    """Middleware de seguridad para uploads de archivos"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificar uploads antes del procesamiento
        if request.method == 'POST' and request.FILES:
            try:
                self.validate_uploads(request)
            except SuspiciousOperation as e:
                logger.warning(f"Upload sospechoso desde {request.META.get('REMOTE_ADDR')}: {e}")
                return JsonResponse({'error': 'Upload no válido'}, status=400)
        
        return self.get_response(request)

    def validate_uploads(self, request):
        """Valida archivos subidos por seguridad"""
        
        for file_key, uploaded_file in request.FILES.items():
            # Verificar extensión
            if not uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
                raise SuspiciousOperation(f"Extensión no permitida: {uploaded_file.name}")
            
            # Verificar tamaño máximo general
            max_size = 15 * 1024 * 1024  # 15MB límite absoluto
            if uploaded_file.size > max_size:
                raise SuspiciousOperation(f"Archivo demasiado grande: {uploaded_file.name}")
            
            # Verificar nombre de archivo por caracteres sospechosos
            suspicious_chars = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
            for char in suspicious_chars:
                if char in uploaded_file.name:
                    raise SuspiciousOperation(f"Nombre de archivo sospechoso: {uploaded_file.name}")


class RequestLoggingMiddleware:
    """Middleware para logging de requests importantes"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log requests de upload
        if request.method == 'POST' and '/excel/' in request.path:
            self.log_upload_request(request)
        
        response = self.get_response(request)
        
        # Log respuestas de error
        if response.status_code >= 400:
            logger.warning(f"Error response {response.status_code} for {request.path}")
        
        return response

    def log_upload_request(self, request):
        """Log información de requests de upload"""
        files_info = []
        total_size = 0
        
        for file_key, uploaded_file in request.FILES.items():
            files_info.append(f"{file_key}: {uploaded_file.name} ({uploaded_file.size} bytes)")
            total_size += uploaded_file.size
        
        logger.info(f"Upload request from {request.META.get('REMOTE_ADDR', 'unknown')}")
        logger.info(f"Files: {', '.join(files_info)}")
        logger.info(f"Total size: {total_size} bytes")
        
        # Log datos del formulario (sin información sensible)
        if 'mes' in request.POST:
            logger.info(f"Mes: {request.POST['mes']}")


class ResponseTimeMiddleware:
    """Middleware para monitorear tiempos de respuesta"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Calcular tiempo de procesamiento
        processing_time = time.time() - start_time
        
        # Agregar header de tiempo (útil para debugging)
        response['X-Processing-Time'] = f"{processing_time:.3f}s"
        
        # Log requests lentos
        if processing_time > 10:  # Más de 10 segundos
            logger.warning(
                f"Slow request: {request.path} - {processing_time:.2f}s "
                f"from {request.META.get('REMOTE_ADDR', 'unknown')}"
            )
        
        # Log para procesamiento de Excel
        if '/excel/procesar/' in request.path:
            if processing_time > 60:  # Más de 1 minuto
                logger.warning(f"Long Excel processing: {processing_time:.2f}s")
            else:
                logger.info(f"Excel processing completed in {processing_time:.2f}s")
        
        return response


# Configuración para agregar a settings.py:
"""
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Middlewares personalizados (agregar al final)
    'excel_app.middleware.FileUploadSecurityMiddleware',
    'excel_app.middleware.RequestLoggingMiddleware', 
    'excel_app.middleware.ResponseTimeMiddleware',
    'excel_app.middleware.ExcelProcessingMiddleware',  # Este debe ir al final
]
"""

def cleanup_old_files():
    """Limpia archivos ZIP de más de 24 horas"""
    from django.conf import settings
    from pathlib import Path
    import time
    
    output_dir = Path(settings.MEDIA_ROOT) / "outputs"
    if not output_dir.exists():
        return
    
    now = time.time()
    one_day = 24 * 60 * 60
    
    for zip_file in output_dir.glob("*.zip"):
        try:
            if now - zip_file.stat().st_mtime > one_day:
                zip_file.unlink()
                logger.info(f"Archivo antiguo eliminado: {zip_file.name}")
        except Exception as e:
            logger.warning(f"Error eliminando archivo antiguo: {e}")

class FileCleanupMiddleware:
    """Middleware que limpia archivos antiguos ocasionalmente"""
    def __init__(self, get_response):
        self.get_response = get_response
        self.last_cleanup = 0
    
    def __call__(self, request):
        # Limpiar cada 4 horas aproximadamente (14400 segundos)
        import time
        now = time.time()
        if now - self.last_cleanup > 14400:  # 4 horas
            cleanup_old_files()
            self.last_cleanup = now
        
        return self.get_response(request)
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.contrib import messages
from django.conf import settings
from pathlib import Path
import os, mimetypes, logging
from datetime import datetime

from .forms import ExcelUploadForm
from .utils import procesar_excel_maestro_django, verificar_directorios

logger = logging.getLogger(__name__)

class ProcessingError(Exception):
    """Excepción personalizada para errores de procesamiento"""
    pass

def index(request):
    """Vista principal con el formulario de carga"""
    form = ExcelUploadForm()
    return render(request, 'excel_app/index.html', {'form': form})

def procesar_excel(request):
    """Procesa los archivos Excel subidos y genera el ZIP con los resultados"""
    logger.info("=== INICIO PROCESAMIENTO EN VISTA ===")
    
    if request.method != 'POST':
        return redirect('excel_app:index')
    
    form = ExcelUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        logger.error(f"Formulario inválido: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return render(request, 'excel_app/index.html', {'form': form})
    
    # Archivos temporales que necesitaremos limpiar
    temp_files = []
    
    try:
        # Obtener datos del formulario
        mes = form.cleaned_data['mes']
        excel_maestro_actual = request.FILES['excel_maestro_actual']
        excel_maestro_anterior = request.FILES.get('excel_maestro_anterior')
        traductor_personalizado = request.FILES.get('traductor_personalizado')
        
        logger.info(f"Procesando para mes: {mes}")
        logger.info(f"Excel actual: {excel_maestro_actual.name} ({excel_maestro_actual.size} bytes)")
        
        # Determinar modo de procesamiento
        tiene_excel_anterior = excel_maestro_anterior is not None
        if tiene_excel_anterior:
            logger.info(f"Excel anterior: {excel_maestro_anterior.name} ({excel_maestro_anterior.size} bytes)")
            logger.info("MODO: Procesamiento inteligente con comparación")
        else:
            logger.info("MODO: Procesamiento completo (todas las obras sociales)")
        
        if traductor_personalizado:
            logger.info(f"Traductor personalizado: {traductor_personalizado.name} ({traductor_personalizado.size} bytes)")
        
        # Verificar directorios
        upload_dir, output_dir = verificar_directorios()
        
        # Guardar archivos temporalmente
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Guardar Excel maestro actual
        maestro_actual_path = upload_dir / f"maestro_actual_{timestamp}_{excel_maestro_actual.name}"
        with open(maestro_actual_path, 'wb+') as destination:
            for chunk in excel_maestro_actual.chunks():
                destination.write(chunk)
        temp_files.append(maestro_actual_path)
        logger.info(f"Excel actual guardado en: {maestro_actual_path}")
        
        # Guardar Excel maestro anterior si existe
        maestro_anterior_path = None
        if excel_maestro_anterior:
            maestro_anterior_path = upload_dir / f"maestro_anterior_{timestamp}_{excel_maestro_anterior.name}"
            with open(maestro_anterior_path, 'wb+') as destination:
                for chunk in excel_maestro_anterior.chunks():
                    destination.write(chunk)
            temp_files.append(maestro_anterior_path)
            logger.info(f"Excel anterior guardado en: {maestro_anterior_path}")
        
        # Guardar traductor personalizado si existe
        traductor_path = None
        if traductor_personalizado:
            traductor_path = upload_dir / f"traductor_{timestamp}_{traductor_personalizado.name}"
            with open(traductor_path, 'wb+') as destination:
                for chunk in traductor_personalizado.chunks():
                    destination.write(chunk)
            temp_files.append(traductor_path)
            logger.info(f"Traductor personalizado guardado en: {traductor_path}")
        
        # Procesar con la función de utils.py
        logger.info("Iniciando procesamiento con función de utils...")
        try:
            zip_resultado, info_procesamiento = procesar_excel_maestro_django(
                ruta_excel_actual=str(maestro_actual_path),
                mes=mes,
                ruta_excel_anterior=str(maestro_anterior_path) if maestro_anterior_path else None,
                ruta_traductor=str(traductor_path) if traductor_path else None
            )
            logger.info(f"Procesamiento completado. ZIP generado en: {zip_resultado}")
        except Exception as e:
            logger.error(f"Error en procesamiento: {str(e)}", exc_info=True)
            raise ProcessingError(f"Error procesando archivos: {str(e)}")
        
        # Verificar que el archivo ZIP se generó correctamente
        zip_path = Path(zip_resultado)
        if not zip_path.exists():
            raise ProcessingError("No se pudo generar el archivo de resultados")
        
        if zip_path.stat().st_size < 100:
            raise ProcessingError("El archivo generado está vacío o corrupto")
        
        # Preparar información para el template
        context = {
            'archivo_zip': zip_path.name,
            'info_procesamiento': info_procesamiento,
            'mes': mes,
            'timestamp': timestamp,
            'maestro_actual_nombre': excel_maestro_actual.name,
            'maestro_anterior_nombre': excel_maestro_anterior.name if excel_maestro_anterior else None,
            'traductor_usado': info_procesamiento.get('traductor_usado', 'default'),
            'archivos_generados': info_procesamiento.get('archivos_generados', 0),
            'archivos_omitidos': info_procesamiento.get('archivos_omitidos', 0),
            'cambios_detectados': info_procesamiento.get('cambios_detectados', False),
            'excel_cambios_generado': info_procesamiento.get('excel_cambios_generado', False),
            'modo_procesamiento': info_procesamiento.get('modo_procesamiento', 'completo'),
            'tiene_excel_anterior': tiene_excel_anterior
        }
        
        logger.info("=== PROCESAMIENTO COMPLETADO EXITOSAMENTE ===")
        
        # Mostrar mensaje de éxito apropiado según el modo
        if tiene_excel_anterior and info_procesamiento.get('excel_cambios_generado'):
            messages.success(
                request, 
                f"Procesamiento completado con comparación: {info_procesamiento.get('archivos_generados', 0)} "
                f"archivos individuales + Excel de cambios globales para el mes {mes}"
            )
        elif tiene_excel_anterior:
            messages.info(
                request,
                f"Procesamiento completado: No se detectaron cambios entre maestros. "
                f"{info_procesamiento.get('archivos_generados', 0)} archivos procesados."
            )
        else:
            messages.success(
                request, 
                f"Procesamiento completo completado: {info_procesamiento.get('archivos_generados', 0)} "
                f"archivos generados para el mes {mes}"
            )
        
        return render(request, 'excel_app/resultado.html', context)
        
    except ProcessingError as e:
        logger.error(f"Error de procesamiento: {e}")
        messages.error(request, str(e))
        return render(request, 'excel_app/index.html', {'form': form})
        
    except FileNotFoundError as e:
        logger.error(f"Archivo no encontrado: {e}")
        messages.error(request, "Uno de los archivos necesarios no se encontró")
        return render(request, 'excel_app/index.html', {'form': form})
        
    except PermissionError as e:
        logger.error(f"Error de permisos: {e}")
        messages.error(request, "Error de permisos del sistema. Contacte al administrador")
        return render(request, 'excel_app/index.html', {'form': form})
        
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        messages.error(request, f"Error inesperado: {str(e)}")
        return render(request, 'excel_app/index.html', {'form': form})
        
    finally:
        # Limpiar archivos temporales
        logger.info("Limpiando archivos temporales...")
        for temp_file in temp_files:
            try:
                if temp_file and Path(temp_file).exists():
                    Path(temp_file).unlink()
                    logger.debug(f"Archivo temporal eliminado: {temp_file}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo temporal {temp_file}: {e}")


def descargar_archivo(request, archivo_nombre):
    """Descarga un archivo ZIP generado"""
    logger.info(f"Solicitando descarga del archivo: {archivo_nombre}")

    if not _is_safe_filename(archivo_nombre):
        logger.warning(f"Archivo no seguro o inválido: {archivo_nombre}")
        raise Http404("Archivo no válido")

    file_path = Path(settings.MEDIA_ROOT) / "outputs" / archivo_nombre
    logger.debug(f"Ruta del archivo: {file_path}")

    if not file_path.exists():
        logger.error(f"Archivo no encontrado: {file_path}")
        messages.error(request, "Archivo no disponible")
        return redirect('excel_app:index')

    if not os.access(file_path, os.R_OK):
        logger.error(f"No hay permisos de lectura para: {file_path}")
        messages.error(request, "Archivo sin permisos de lectura")
        return redirect('excel_app:index')

    mime_type, _ = mimetypes.guess_type(str(file_path))
    logger.info(f"MIME type detectado: {mime_type or 'application/zip'}")

    try:
        response = HttpResponse(file_path.read_bytes(), content_type=mime_type or "application/zip")
        response['Content-Disposition'] = f'attachment; filename="{archivo_nombre}"'
        response['Content-Length'] = file_path.stat().st_size
        logger.info(f"Archivo {archivo_nombre} preparado para descarga ({file_path.stat().st_size} bytes)")
        return response
    except Exception as e:
        logger.error(f"Error al leer o enviar el archivo: {e}", exc_info=True)
        messages.error(request, "Error al enviar el archivo")
        return redirect('excel_app:index')


def descargar(request):
    """Descarga el último ZIP disponible"""
    output_dir = Path(settings.MEDIA_ROOT) / "outputs"
    logger.info(f"Buscando archivos ZIP en: {output_dir}")

    try:
        archivos = sorted(
            output_dir.glob("*.zip"), 
            key=lambda f: f.stat().st_mtime, 
            reverse=True
        )
        if not archivos:
            logger.warning("No hay archivos ZIP disponibles para descargar")
            messages.warning(request, "No hay archivos disponibles para descargar")
            return redirect('excel_app:index')

        ultimo_archivo = archivos[0].name
        logger.info(f"Último archivo disponible: {ultimo_archivo}")
        return descargar_archivo(request, ultimo_archivo)
        
    except Exception as e:
        logger.error(f"Error al intentar descargar el último ZIP: {e}", exc_info=True)
        messages.error(request, f"Error al descargar archivo: {str(e)}")
        return redirect('excel_app:index')


def _is_safe_filename(filename):
    """Verifica que el nombre de archivo sea seguro"""
    if not filename or len(filename) > 255:
        return False
    
    if '..' in filename or not filename.lower().endswith('.zip'):
        return False
    
    forbidden = ['/', '\\', '<', '>', ':', '"', '|', '?', '*']
    return not any(c in filename for c in forbidden)


def status(request):
    """Verifica el estado del sistema y directorios"""
    try:
        upload_dir, output_dir = verificar_directorios()
        
        status = {
            'upload_dir_exists': upload_dir.exists(),
            'upload_dir_writable': os.access(upload_dir, os.W_OK),
            'output_dir_exists': output_dir.exists(),
            'output_dir_writable': os.access(output_dir, os.W_OK),
        }
        
        # Verificar espacio disponible
        try:
            du = os.statvfs(upload_dir)
            available_space_mb = (du.f_bavail * du.f_frsize) // (1024*1024)
            status['available_space_mb'] = available_space_mb
            status['low_space'] = available_space_mb < 100
        except (OSError, AttributeError):
            # statvfs no disponible en Windows
            status['available_space_mb'] = None
            status['low_space'] = False
        
        # Contar archivos en directorios
        try:
            status['upload_files_count'] = len(list(upload_dir.glob('*')))
            status['output_files_count'] = len(list(output_dir.glob('*.zip')))
        except:
            status['upload_files_count'] = 0
            status['output_files_count'] = 0
        
        # Verificar traductor por defecto
        traductor_default = Path(settings.MEDIA_ROOT) / 'traductor_default.xlsx'
        status['traductor_default_exists'] = traductor_default.exists()
        
        # Estado general del sistema
        status['healthy'] = all([
            status['upload_dir_writable'], 
            status['output_dir_writable'], 
            not status.get('low_space', False)
        ])
        
        return JsonResponse(status)
        
    except Exception as e:
        logger.error(f"Error verificando estado: {e}")
        return JsonResponse({
            'healthy': False, 
            'error': str(e)
        }, status=500)
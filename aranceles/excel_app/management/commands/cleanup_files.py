from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
import os
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Limpia archivos temporales y antiguos de la aplicación de Excel'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=2,
            help='Días de antigüedad para eliminar archivos (por defecto: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué archivos se eliminarían sin eliminarlos realmente'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar eliminación sin confirmación'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(f"Iniciando limpieza de archivos más antiguos que {days} días...")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN: No se eliminarán archivos realmente"))
        
        # Directorios a limpiar
        directories = [
            Path(settings.MEDIA_ROOT) / 'uploads',
            Path(settings.MEDIA_ROOT) / 'outputs',
            Path(settings.BASE_DIR) / 'temp',
        ]
        
        # Si existe FILE_UPLOAD_TEMP_DIR
        if hasattr(settings, 'FILE_UPLOAD_TEMP_DIR'):
            directories.append(Path(settings.FILE_UPLOAD_TEMP_DIR))
        
        total_cleaned = 0
        total_size = 0
        
        for directory in directories:
            if not directory.exists():
                continue
                
            self.stdout.write(f"\nLimpiando directorio: {directory}")
            cleaned, size = self.clean_directory(directory, days, dry_run, force)
            total_cleaned += cleaned
            total_size += size
        
        # Limpiar logs antiguos también
        logs_cleaned, logs_size = self.clean_old_logs(days, dry_run, force)
        total_cleaned += logs_cleaned
        total_size += logs_size
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Limpieza completada: {total_cleaned} archivos, "
                f"{self.format_bytes(total_size)} liberados"
            )
        )
        
        if not dry_run:
            logger.info(f"Cleanup completado: {total_cleaned} archivos eliminados, {total_size} bytes liberados")

    def clean_directory(self, directory, days, dry_run, force):
        """Limpia archivos antiguos de un directorio"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        cleaned_count = 0
        total_size = 0
        
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    try:
                        file_stat = file_path.stat()
                        
                        # Verificar si el archivo es antiguo
                        if file_stat.st_mtime < cutoff_time:
                            file_size = file_stat.st_size
                            
                            if dry_run:
                                self.stdout.write(
                                    f"  [DRY-RUN] Eliminaría: {file_path.name} "
                                    f"({self.format_bytes(file_size)}) - "
                                    f"{self.format_age(file_stat.st_mtime)}"
                                )
                            else:
                                if self.should_delete_file(file_path, force):
                                    file_path.unlink()
                                    self.stdout.write(
                                        f"  ✓ Eliminado: {file_path.name} "
                                        f"({self.format_bytes(file_size)})"
                                    )
                            
                            cleaned_count += 1
                            total_size += file_size
                            
                    except (OSError, PermissionError) as e:
                        self.stdout.write(
                            self.style.ERROR(f"  ✗ Error con {file_path.name}: {e}")
                        )
            
            # Eliminar directorios vacíos
            if not dry_run:
                self.remove_empty_dirs(directory)
                        
        except PermissionError:
            self.stdout.write(
                self.style.ERROR(f"Sin permisos para acceder a {directory}")
            )
        
        return cleaned_count, total_size

    def clean_old_logs(self, days, dry_run, force):
        """Limpia logs antiguos"""
        logs_dir = Path(settings.BASE_DIR) / 'logs'
        if not logs_dir.exists():
            return 0, 0
        
        self.stdout.write(f"\nLimpiando logs antiguos en: {logs_dir}")
        
        # Solo limpiar archivos de log rotativos (.log.1, .log.2, etc.)
        # Mantener los logs principales (.log)
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        cleaned_count = 0
        total_size = 0
        
        for log_file in logs_dir.glob('*.log.*'):  # Solo archivos rotativos
            try:
                file_stat = log_file.stat()
                if file_stat.st_mtime < cutoff_time:
                    file_size = file_stat.st_size
                    
                    if dry_run:
                        self.stdout.write(
                            f"  [DRY-RUN] Eliminaría log: {log_file.name} "
                            f"({self.format_bytes(file_size)})"
                        )
                    else:
                        log_file.unlink()
                        self.stdout.write(
                            f"  ✓ Log eliminado: {log_file.name} "
                            f"({self.format_bytes(file_size)})"
                        )
                    
                    cleaned_count += 1
                    total_size += file_size
                    
            except (OSError, PermissionError) as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Error con log {log_file.name}: {e}")
                )
        
        return cleaned_count, total_size

    def should_delete_file(self, file_path, force):
        """Determina si un archivo debe ser eliminado"""
        
        # Archivos críticos que nunca eliminar
        critical_files = ['.gitkeep', 'README.md', '__init__.py']
        if file_path.name in critical_files:
            return False
        
        # Si es forzado, eliminar directamente
        if force:
            return True
        
        # Para archivos grandes, pedir confirmación
        if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
            response = input(f"Eliminar archivo grande {file_path.name} "
                           f"({self.format_bytes(file_path.stat().st_size)})? [y/N]: ")
            return response.lower() in ['y', 'yes']
        
        return True

    def remove_empty_dirs(self, directory):
        """Elimina directorios vacíos recursivamente"""
        try:
            for dir_path in directory.rglob('*/'):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                        self.stdout.write(f"  ✓ Directorio vacío eliminado: {dir_path.name}")
                    except OSError:
                        pass  # Directorio no está realmente vacío o sin permisos
        except Exception:
            pass  # Ignorar errores en esta operación secundaria

    def format_bytes(self, bytes_size):
        """Formatea bytes en unidades legibles"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"

    def format_age(self, timestamp):
        """Formatea la edad de un archivo"""
        age_seconds = time.time() - timestamp
        age_days = age_seconds / (24 * 60 * 60)
        
        if age_days < 1:
            hours = age_seconds / 3600
            return f"{hours:.1f} horas"
        elif age_days < 30:
            return f"{age_days:.1f} días"
        else:
            months = age_days / 30
            return f"{months:.1f} meses"


# Para usar este comando:
# python manage.py cleanup_files
# python manage.py cleanup_files --days=3 --dry-run
# python manage.py cleanup_files --days=1 --force

# También puedes agregar esto al crontab para ejecutar automáticamente:
# 0 2 * * * /path/to/python /path/to/manage.py cleanup_files --days=7 --force
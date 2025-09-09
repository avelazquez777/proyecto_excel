#!/bin/bash
# cleanup_conflicts.sh - Script para limpiar conflictos y optimizar para Render

echo "=== LIMPIANDO CONFLICTOS Y OPTIMIZANDO PARA RENDER ==="

# 1. Eliminar archivos conflictivos de Flask
echo "Eliminando archivos Flask conflictivos..."
rm -f app.py wsgi.py start.sh 2>/dev/null || true

# 2. Limpiar archivos de log que consumen espacio
echo "Limpiando logs..."
rm -rf logs/ 2>/dev/null || true
find . -name "*.log" -delete 2>/dev/null || true

# 3. Limpiar archivos temporales y cache
echo "Limpiando cache y temporales..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true

# 4. Limpiar media uploads antiguos
echo "Limpiando uploads antiguos..."
find media/uploads/ -type f -mtime +1 -delete 2>/dev/null || true

# 5. Optimizar base de datos SQLite
echo "Optimizando base de datos..."
if [ -f "db.sqlite3" ]; then
    echo "VACUUM;" | sqlite3 db.sqlite3 2>/dev/null || true
fi

# 6. Verificar estructura de directorios necesarios
echo "Verificando directorios..."
mkdir -p media/uploads media/outputs static staticfiles

# 7. Crear archivos .gitkeep si no existen
touch media/uploads/.gitkeep media/outputs/.gitkeep

# 8. Mostrar uso de espacio después de limpieza
echo "=== ESPACIO USADO DESPUÉS DE LIMPIEZA ==="
du -sh . 2>/dev/null || echo "No se pudo calcular el espacio"
df -h . 2>/dev/null || echo "No se pudo obtener info del disco"

echo "=== LIMPIEZA COMPLETADA ==="
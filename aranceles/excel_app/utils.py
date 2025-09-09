# excel_app/utils.py
import pandas as pd
import io
import zipfile
from pathlib import Path
import unicodedata
import os
from django.conf import settings
import logging
import tempfile
import shutil

logger = logging.getLogger(__name__)

# --- FUNCIONES AUXILIARES ---
def normalizar_texto(s):
    """Normaliza texto removiendo acentos y convirtiendo a mayúsculas"""
    if s is None:
        return ""
    s = str(s).strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.split())

def limpiar_importe_raw(v):
    """Limpia valores monetarios y los convierte a float"""
    if pd.isna(v):
        return 0.0
    s = str(v).strip().replace("$", "").replace(" ", "")
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        valor = float(s)
        return valor if valor > 0 else 0.0
    except:
        return 0.0

def validar_codigo(cod):
    """Valida que un código sea correcto"""
    if pd.isna(cod):
        return False
    cod_str = str(cod).strip()
    if cod_str in ['', '0', '00000000', 'nan', '#N/A', 'N/A']:
        return False
    try:
        return int(float(cod_str)) > 0
    except:
        return False

def determinar_concepto(cod_desde, cod_hasta, tipo_calculado):
    """Determina el concepto numérico según la lógica del negocio"""
    try:
        cod_desde_int = int(float(cod_desde)) if cod_desde else 0
        cod_hasta_int = int(float(cod_hasta)) if cod_hasta else 0
        
        # Si cualquier código está en el rango 42M-43M -> concepto 1
        if (42000000 <= cod_desde_int <= 43000000) or (42000000 <= cod_hasta_int <= 43000000):
            return 1
        
        # Si no está en el rango especial, depende del tipo
        if tipo_calculado == "M":
            return 4
        elif tipo_calculado == "V":
            return 1
        else:
            return 4
    except:
        return 4

def determinar_tipo(valor):
    """Determina el tipo según el valor del importe"""
    try:
        valor_float = float(valor) if valor else 0
        if valor_float < 14000000:
            return "M"
        elif 40000000 <= valor_float <= 44000000:
            return "C"
        else:
            return "V"
    except:
        return "V"

def cargar_traductor(ruta_traductor):
    """Carga el archivo Excel traductor y devuelve diccionarios de mapeo"""
    logger.info(f"Cargando traductor desde: {ruta_traductor}")
    
    if not Path(ruta_traductor).exists():
        raise FileNotFoundError(f"Archivo traductor no encontrado: {ruta_traductor}")
    
    try:
        df_traductor = pd.read_excel(ruta_traductor)
    except Exception as e:
        logger.error(f"Error leyendo traductor: {e}")
        raise ValueError(f"Error leyendo archivo traductor: {e}")
    
    if df_traductor.empty:
        raise ValueError("El archivo traductor está vacío")
    
    # Normalizar nombres de columnas
    df_traductor.columns = [normalizar_texto(col) for col in df_traductor.columns]

    traductor_por_concepto = {}
    traductor_por_cod_os = {}

    for _, fila in df_traductor.iterrows():
        try:
            concepto = normalizar_texto(str(fila.iloc[0]))
            cod_os = str(fila.iloc[1]).strip()
            cod_desde = str(fila.iloc[2]).strip()
            cod_hasta = str(fila.iloc[3]).strip()
            
            if not validar_codigo(cod_desde) or not validar_codigo(cod_hasta):
                continue
                
            # Formatear códigos con 8 dígitos
            cod_desde = str(int(float(cod_desde))).zfill(8)
            cod_hasta = str(int(float(cod_hasta))).zfill(8)
            
            # Mapear por concepto
            if concepto:
                traductor_por_concepto[concepto] = {
                    'cod_os': cod_os,
                    'cod_desde': cod_desde,
                    'cod_hasta': cod_hasta
                }
            
            # Mapear por código OS
            if cod_os and cod_os not in ['nan', '#N/A', 'N/A', '']:
                traductor_por_cod_os[cod_os] = {
                    'concepto': concepto,
                    'cod_desde': cod_desde,
                    'cod_hasta': cod_hasta
                }
        except Exception as e:
            logger.warning(f"Error procesando fila del traductor: {e}")
            continue

    logger.info(f"Traductor cargado: {len(traductor_por_concepto)} conceptos, {len(traductor_por_cod_os)} códigos")
    
    if len(traductor_por_concepto) == 0 and len(traductor_por_cod_os) == 0:
        raise ValueError("El traductor no contiene datos válidos")
    
    return traductor_por_concepto, traductor_por_cod_os

def buscar_en_traductor(concepto, cod_os, traductor_concepto, traductor_cod_os):
    """Busca en los traductores por concepto o código OS"""
    concepto_normalizado = normalizar_texto(str(concepto))
    cod_os_str = str(cod_os).strip()
    
    # Primero buscar por concepto
    if concepto_normalizado in traductor_concepto:
        return traductor_concepto[concepto_normalizado]
    
    # Si no se encuentra, buscar por código OS
    if cod_os_str in traductor_cod_os:
        return traductor_cod_os[cod_os_str]
    
    return None

def procesar_maestro_individual(df, obra_col, traductor_concepto, traductor_cod_os):
    """Procesa un Excel maestro para una columna (obra social) específica"""
    datos_obra = {}
    
    for _, fila in df.iterrows():
        try:
            cod_os = str(fila.iloc[0]).strip()
            concepto = str(fila.iloc[1]).strip()
            
            # Obtener valor de la obra social
            if obra_col not in df.columns:
                logger.warning(f"Columna {obra_col} no encontrada en el DataFrame")
                continue
                
            valor = limpiar_importe_raw(fila[obra_col])
            
            if valor <= 0:
                continue
                
            # Buscar en traductor
            resultado = buscar_en_traductor(concepto, cod_os, traductor_concepto, traductor_cod_os)
            if resultado:
                cod_desde = resultado["cod_desde"]
                cod_hasta = resultado["cod_hasta"]
                
                if not validar_codigo(cod_desde) or not validar_codigo(cod_hasta):
                    continue
                
                clave = f"{normalizar_texto(concepto)}_{cod_os}"
                datos_obra[clave] = {
                    "concepto_original": concepto,
                    "cod_os": cod_os,
                    "cod_desde": cod_desde,
                    "cod_hasta": cod_hasta,
                    "valor": valor
                }
                
        except Exception as e:
            logger.warning(f"Error procesando fila: {e}")
            continue
            
    return datos_obra

def comparar_maestros_global(datos_actual, datos_anterior, obras_cols, df_actual, df_anterior):
    """Compara maestros actual y anterior para detectar cambios - IMPLEMENTACIÓN CORREGIDA"""
    logger.info("Iniciando comparación de maestros...")
    filas = []

    # Mapear cod_os -> concepto para ambos períodos
    codos_a_concepto_anterior = {v["cod_os"]: v["concepto_original"] for v in datos_anterior.values()}
    codos_a_concepto_actual = {v["cod_os"]: v["concepto_original"] for v in datos_actual.values()}

    codos_todos = set(list(codos_a_concepto_anterior.keys()) + list(codos_a_concepto_actual.keys()))
    logger.info(f"Comparando {len(codos_todos)} códigos únicos...")

    cambios_detectados = 0
    
    for cod_os in codos_todos:
        concepto_antes = codos_a_concepto_anterior.get(cod_os)
        concepto_actual = codos_a_concepto_actual.get(cod_os)

        # Determinar estado del cambio
        if concepto_antes and concepto_actual:
            if concepto_antes != concepto_actual:
                estado = "Modificado"
                cambios_detectados += 1
            else:
                continue  # Sin cambios
        elif concepto_antes and not concepto_actual:
            estado = "Eliminado"
            cambios_detectados += 1
        elif concepto_actual and not concepto_antes:
            estado = "Nuevo"
            cambios_detectados += 1
        else:
            continue

        # Crear fila de cambios
        fila = {
            "cod_os_antes": cod_os if concepto_antes else "",
            "cod_os_actual": cod_os if concepto_actual else "",
            "concepto_antes": concepto_antes if concepto_antes else "",
            "concepto_actual": concepto_actual if concepto_actual else "",
            "estado": estado
        }

        # Agregar valores por obra social
        for obra_col in obras_cols:
            valor = ""
            if concepto_actual:
                try:
                    # Buscar valor en el DataFrame actual
                    mask = (df_actual.iloc[:,0].astype(str) == cod_os) & \
                           (df_actual.iloc[:,1].astype(str) == concepto_actual)
                    if mask.any() and obra_col in df_actual.columns:
                        valor = limpiar_importe_raw(df_actual.loc[mask, obra_col].iloc[0])
                except:
                    valor = ""
            else:
                valor = "Eliminado"
            
            fila[normalizar_texto(obra_col)] = valor

        filas.append(fila)

    # Crear DataFrame de cambios
    df_cambios_global = pd.DataFrame(filas)
    if not df_cambios_global.empty:
        df_cambios_global["repetido"] = ""
        # Detectar duplicados
        duplicados = df_cambios_global[df_cambios_global.duplicated(
            subset=["cod_os_actual","concepto_actual"], keep=False
        )]
        if not duplicados.empty:
            df_cambios_global.loc[duplicados.index, "repetido"] = "Repetido"

    logger.info(f"Cambios detectados: {cambios_detectados}")
    return df_cambios_global

def detectar_obras_sociales_con_cambios(datos_actual, datos_anterior, obras_cols, df_actual, df_anterior, traductor_concepto, traductor_cod_os):
    """
    FUNCIÓN CORREGIDA: Detecta qué obras sociales tienen cambios en sus valores
    Devuelve set de obras sociales que deben procesarse
    """
    logger.info("Detectando obras sociales con cambios...")
    obras_con_cambios = set()
    
    # Si no hay anterior, procesar todas
    if not datos_anterior:
        logger.info("No hay maestro anterior, procesando todas las obras sociales")
        return set(obras_cols)
    
    # Comparar valores por obra social
    for obra_col in obras_cols:
        if obra_col not in df_anterior.columns:
            logger.info(f"Obra social {obra_col} es nueva, se procesará")
            obras_con_cambios.add(obra_col)
            continue
            
        # Comparar valores específicos de esta obra social
        datos_obra_actual = procesar_maestro_individual(df_actual, obra_col, traductor_concepto, traductor_cod_os)
        datos_obra_anterior = procesar_maestro_individual(df_anterior, obra_col, traductor_concepto, traductor_cod_os)
        
        # Detectar cambios en los valores
        cambios_en_obra = False
        
        # Verificar códigos nuevos o eliminados
        claves_actual = set(datos_obra_actual.keys())
        claves_anterior = set(datos_obra_anterior.keys())
        
        if claves_actual != claves_anterior:
            cambios_en_obra = True
        else:
            # Verificar cambios en valores
            for clave in claves_actual:
                if clave in claves_anterior:
                    valor_actual = datos_obra_actual[clave].get('valor', 0)
                    valor_anterior = datos_obra_anterior[clave].get('valor', 0)
                    if abs(valor_actual - valor_anterior) > 0.01:  # Tolerancia para flotantes
                        cambios_en_obra = True
                        break
        
        if cambios_en_obra:
            logger.info(f"Cambios detectados en obra social: {obra_col}")
            obras_con_cambios.add(obra_col)
    
    logger.info(f"Obras sociales con cambios: {len(obras_con_cambios)} de {len(obras_cols)}")
    return obras_con_cambios

def obtener_traductor_default():
    """Obtiene la ruta del traductor por defecto"""
    traductor_path = Path(settings.MEDIA_ROOT) / 'traductor_default.xlsx'
    return str(traductor_path) if traductor_path.exists() else None

def verificar_directorios():
    """Verifica y crea los directorios necesarios"""
    try:
        upload_dir = Path(settings.MEDIA_ROOT) / 'uploads'
        output_dir = Path(settings.MEDIA_ROOT) / 'outputs'
        
        upload_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Verificar permisos de escritura
        test_file = output_dir / '.test_write'
        try:
            test_file.write_text('test')
            test_file.unlink()
        except Exception as e:
            logger.error(f"Sin permisos de escritura en {output_dir}: {e}")
            raise PermissionError(f"Sin permisos de escritura en directorio de salida")
        
        logger.info(f"Directorios verificados: upload={upload_dir}, output={output_dir}")
        return upload_dir, output_dir
        
    except Exception as e:
        logger.error(f"Error verificando directorios: {e}")
        raise

def procesar_excel_maestro_django(ruta_excel_actual, mes="2025-09", 
                                 ruta_excel_anterior=None, ruta_traductor=None):
    """
    FUNCIÓN PRINCIPAL CORREGIDA
    1. Procesa Excel maestro actual
    2. Compara con maestro anterior (si existe)
    3. Genera Excels individuales
    4. Crea un ZIP con todos los archivos generados
    """

    logger.info("=== INICIO PROCESAMIENTO COMPLETO ===")
    logger.info(f"Excel actual: {ruta_excel_actual}")
    logger.info(f"Excel anterior: {ruta_excel_anterior}")
    logger.info(f"Traductor: {ruta_traductor}")
    logger.info(f"Mes: {mes}")

    temp_files = []
    zip_path = None

    try:
        # Verificar directorios
        upload_dir, output_dir = verificar_directorios()

        # Verificar archivo actual
        if not Path(ruta_excel_actual).exists():
            raise FileNotFoundError(f"Archivo maestro actual no encontrado: {ruta_excel_actual}")

        # Obtener traductor
        if ruta_traductor is None:
            ruta_traductor = obtener_traductor_default()
            if ruta_traductor is None:
                raise ValueError("No se encontró traductor por defecto. Sube uno personalizado.")

        logger.info(f"Usando traductor: {ruta_traductor}")

        # Cargar traductor
        traductor_concepto, traductor_cod_os = cargar_traductor(ruta_traductor)

        # Cargar maestro actual
        logger.info("Cargando maestro actual...")
        df_actual = pd.read_excel(ruta_excel_actual)
        if df_actual.empty:
            raise ValueError("El Excel maestro actual está vacío")

        cols = list(df_actual.columns)
        if len(cols) < 3:
            raise ValueError("El Excel debe tener al menos 3 columnas: cod_os, concepto y obras sociales")

        obras_cols = cols[2:]
        logger.info(f"Obras sociales encontradas: {len(obras_cols)} columnas")

        # Cargar maestro anterior
        df_anterior = None
        tiene_maestro_anterior = False
        if ruta_excel_anterior and Path(ruta_excel_anterior).exists():
            try:
                df_anterior = pd.read_excel(ruta_excel_anterior)
                if not df_anterior.empty:
                    tiene_maestro_anterior = True
            except Exception as e:
                logger.warning(f"Error leyendo maestro anterior: {e}")

        # ================================
        # Nombre del ZIP basado en la fecha
        # ================================
        try:
            fecha = pd.to_datetime(mes, format="%Y-%m")
            mes_nombre = fecha.strftime("%B").capitalize()
            anio = fecha.strftime("%Y")
            nombre_periodo = f"{anio} {mes_nombre}"
        except Exception:
            nombre_periodo = mes  # fallback si algo falla

        zip_filename = f"Valores Excel Individual {nombre_periodo}.zip"
        zip_path = output_dir / zip_filename
        logger.info(f"ZIP a generar: {zip_path}")

        # Info de salida
        info = {
            'archivos_generados': 0,
            'archivos_omitidos': 0,
            'cambios_detectados': False,
            'excel_cambios_generado': False,
            'modo_procesamiento': 'completo',
            'traductor_usado': 'personalizado' if ruta_traductor != obtener_traductor_default() else 'default'
        }

        # ============
        # Procesamiento
        # ============
        datos_actual_total, datos_anterior_total = {}, {}

        for obra_col in obras_cols:
            datos_obra_actual = procesar_maestro_individual(df_actual, obra_col, traductor_concepto, traductor_cod_os)
            datos_actual_total.update(datos_obra_actual)

            if df_anterior is not None and obra_col in df_anterior.columns:
                datos_obra_anterior = procesar_maestro_individual(df_anterior, obra_col, traductor_concepto, traductor_cod_os)
                datos_anterior_total.update(datos_obra_anterior)

        # Excel de cambios globales
        cambios_temp_path = None
        if tiene_maestro_anterior and datos_anterior_total:
            df_cambios_global = comparar_maestros_global(datos_actual_total, datos_anterior_total, obras_cols, df_actual, df_anterior)
            if not df_cambios_global.empty:
                cambios_temp_path = output_dir / f"cambios_global_{mes}.xlsx"
                df_cambios_global.to_excel(cambios_temp_path, index=False)
                info['cambios_detectados'] = True
                info['excel_cambios_generado'] = True
                temp_files.append(cambios_temp_path)

        # Determinar obras sociales a procesar
        if tiene_maestro_anterior:
            obras_a_procesar = detectar_obras_sociales_con_cambios(
                datos_actual_total, datos_anterior_total, obras_cols,
                df_actual, df_anterior, traductor_concepto, traductor_cod_os
            )
            info['modo_procesamiento'] = 'inteligente'
        else:
            obras_a_procesar = set(obras_cols)

        # =====================
        # Crear el archivo ZIP
        # =====================
        archivos_agregados = 0
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            if cambios_temp_path and cambios_temp_path.exists():
                zf.write(cambios_temp_path, f"cambios_global_{mes}.xlsx")

            for obra_col in obras_a_procesar:
                try:
                    obra_norm = normalizar_texto(obra_col)
                    datos_actual = procesar_maestro_individual(df_actual, obra_col, traductor_concepto, traductor_cod_os)

                    if not datos_actual:
                        info['archivos_omitidos'] += 1
                        continue

                    datos_finales = []
                    for clave, data in datos_actual.items():
                        valor = data["valor"]
                        cod_desde = data["cod_desde"]
                        cod_hasta = data["cod_hasta"]
                        tipo = determinar_tipo(valor)
                        concepto_num = determinar_concepto(cod_desde, cod_hasta, tipo)

                        datos_finales.append({
                            "nom_id": "1",
                            "coddesde": str(int(float(cod_desde))).zfill(8) if validar_codigo(cod_desde) else "",
                            "codhasta": str(int(float(cod_hasta))).zfill(8) if validar_codigo(cod_hasta) else "",
                            "concepto": str(concepto_num),
                            "importe": str(valor),
                            "tipo": tipo,
                            "plan_nombre": "",
                            "prof_nombre": "",
                            "pre_matp": "0",
                            "area": "D"
                        })

                    if not datos_finales:
                        info['archivos_omitidos'] += 1
                        continue

                    df_final = pd.DataFrame(datos_finales)
                    df_final['importe_num'] = pd.to_numeric(df_final['importe'], errors='coerce')
                    df_final = df_final.sort_values("importe_num", ascending=False).drop_duplicates(
                        subset=["coddesde", "codhasta"], keep="first"
                    )
                    df_final = df_final.drop('importe_num', axis=1)

                    bio = io.BytesIO()
                    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
                        df_final.to_excel(writer, index=False, sheet_name="Datos")
                    bio.seek(0)

                    safe_name = ''.join(c for c in normalizar_texto(obra_col) if c.isalnum() or c in '-_')
                    filename = f"{safe_name}_{mes}.xlsx"

                    zf.writestr(filename, bio.read())
                    archivos_agregados += 1

                except Exception as e:
                    logger.error(f"Error procesando {obra_col}: {e}")
                    info['archivos_omitidos'] += 1
                    continue

        info['archivos_generados'] = archivos_agregados

        if not zip_path.exists() or zip_path.stat().st_size < 100:
            raise ValueError("El archivo ZIP no se generó correctamente")

        logger.info("=== PROCESAMIENTO COMPLETADO ===")
        logger.info(f"ZIP generado: {zip_path} ({info['archivos_generados']} archivos)")

        return str(zip_path), info

    except Exception as e:
        logger.error(f"Error en procesamiento: {e}", exc_info=True)
        raise e

    finally:
        for temp_file in temp_files:
            try:
                if temp_file and Path(temp_file).exists():
                    Path(temp_file).unlink()
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo temporal {temp_file}: {e}")

# excel_app/forms.py
from django import forms
import pandas as pd
from datetime import datetime
import io

class ExcelUploadForm(forms.Form):
    excel_maestro_actual = forms.FileField(
        label='Excel Maestro Actual',
        help_text='Excel con los datos actuales de obras sociales (obligatorio)',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )
    
    excel_maestro_anterior = forms.FileField(
        label='Excel Maestro Anterior',
        help_text='Excel anterior para comparación (opcional)',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )
    
    traductor_personalizado = forms.FileField(
        label='Traductor Personalizado',
        help_text='Excel traductor personalizado (opcional, si no se sube se usa el predeterminado)',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )
    
    mes = forms.CharField(
        label='Mes',
        help_text='Formato: YYYY-MM (ej: 2025-09)',
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '2025-09',
            'pattern': r'\d{4}-\d{2}'
        })
    )
    
    def clean_mes(self):
        mes = self.cleaned_data.get('mes')
        if mes:
            try:
                year, month = mes.split('-')
                if len(year) != 4 or len(month) != 2:
                    raise forms.ValidationError("Formato incorrecto. Use YYYY-MM")
                
                year_int = int(year)
                month_int = int(month)
                
                if not (1 <= month_int <= 12):
                    raise forms.ValidationError("Mes debe estar entre 01 y 12")
                
                # Validar que no sea una fecha muy futura
                current_year = datetime.now().year
                if year_int > current_year + 2:
                    raise forms.ValidationError(f"Año no puede ser mayor a {current_year + 2}")
                
                if year_int < 2020:
                    raise forms.ValidationError("Año debe ser 2020 o posterior")
                    
            except (ValueError, IndexError):
                raise forms.ValidationError("Formato debe ser YYYY-MM (ej: 2025-09)")
        return mes
    
    def clean_excel_maestro_actual(self):
        return self._validate_excel_file(
            'excel_maestro_actual', 
            required=True,
            max_size_mb=10,
            check_content=True
        )
    
    def clean_excel_maestro_anterior(self):
        return self._validate_excel_file(
            'excel_maestro_anterior', 
            required=False,
            max_size_mb=10,
            check_content=True
        )
    
    def clean_traductor_personalizado(self):
        return self._validate_excel_file(
            'traductor_personalizado', 
            required=False,
            max_size_mb=5,
            check_content=True
        )
    
    def _validate_excel_file(self, field_name, required=True, max_size_mb=10, check_content=True):
        """Validación robusta de archivos Excel"""
        file = self.cleaned_data.get(field_name)
        
        if not file and required:
            raise forms.ValidationError("Este campo es obligatorio")
        
        if not file:
            return file
        
        # Validar extensión
        if not file.name.lower().endswith(('.xlsx', '.xls')):
            raise forms.ValidationError("Solo se permiten archivos Excel (.xlsx, .xls)")
        
        # Validar tamaño
        max_size = max_size_mb * 1024 * 1024
        if file.size > max_size:
            raise forms.ValidationError(f"El archivo no debe superar los {max_size_mb}MB")
        
        if file.size < 100:  # Archivo muy pequeño, probablemente corrupto
            raise forms.ValidationError("El archivo parece estar vacío o corrupto")
        
        # Validar que el archivo sea realmente un Excel legible
        if check_content:
            try:
                # Intentar leer el archivo como Excel
                file.seek(0)  # Volver al inicio
                content = file.read()
                file.seek(0)  # Volver al inicio para el procesamiento posterior
                
                # Crear un objeto BytesIO para pandas
                excel_buffer = io.BytesIO(content)
                
                # Intentar leer con pandas
                df = pd.read_excel(excel_buffer, nrows=1)  # Solo leer la primera fila para validar
                
                if df.empty:
                    raise forms.ValidationError("El archivo Excel está vacío")
                    
            except pd.errors.ParserError:
                raise forms.ValidationError("El archivo no es un Excel válido o está corrupto")
            except Exception as e:
                if "not supported" in str(e).lower():
                    raise forms.ValidationError("Formato de Excel no soportado. Use .xlsx o .xls")
                else:
                    raise forms.ValidationError("Error al leer el archivo Excel. Verifique que no esté corrupto")
        
        return file
    
    def clean(self):
        """Validaciones cruzadas entre campos"""
        cleaned_data = super().clean()
        
        excel_actual = cleaned_data.get('excel_maestro_actual')
        excel_anterior = cleaned_data.get('excel_maestro_anterior')
        
        # Si hay excel anterior, validar que sean diferentes
        if excel_actual and excel_anterior:
            if excel_actual.name == excel_anterior.name and excel_actual.size == excel_anterior.size:
                raise forms.ValidationError(
                    "El Excel actual y anterior parecen ser el mismo archivo. "
                    "Por favor, suba archivos diferentes o deje el anterior vacío."
                )
        
        return cleaned_data
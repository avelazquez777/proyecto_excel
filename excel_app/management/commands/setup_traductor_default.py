from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
import pandas as pd

class Command(BaseCommand):
    help = 'Crea un traductor por defecto de ejemplo'

    def handle(self, *args, **options):
        traductor_path = Path(settings.MEDIA_ROOT) / 'traductor_default.xlsx'
        
        # Crear directorio media si no existe
        Path(settings.MEDIA_ROOT).mkdir(exist_ok=True)
        
        # Datos de ejemplo para el traductor
        datos_ejemplo = {
            'Concepto': [
                'CONSULTA MEDICA',
                'ANALISIS CLINICOS', 
                'RADIOGRAFIA',
                'ECOGRAFIA',
                'INTERNACION'
            ],
            'cod_os': [
                '001',
                '002',
                '003',
                '004',
                '005'
            ],
            'cod_desde': [
                '10010001',
                '20010001',
                '30010001',
                '42010001',
                '50010001'
            ],
            'cod_hasta': [
                '10019999',
                '20019999',
                '30019999',
                '42019999',
                '50019999'
            ]
        }
        
        df = pd.DataFrame(datos_ejemplo)
        df.to_excel(traductor_path, index=False)
        
        self.stdout.write(
            self.style.SUCCESS(f'Traductor por defecto creado en: {traductor_path}')
        )
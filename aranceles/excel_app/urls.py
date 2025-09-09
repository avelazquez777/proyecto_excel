from django.urls import path
from . import views

app_name = 'excel_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('procesar/', views.procesar_excel, name='procesar_excel'),
    path('descargar/<str:archivo_nombre>/', views.descargar_archivo, name='descargar_archivo'),
    path('descargar/', views.descargar, name='descargar_ultimo'),
    path('status/', views.status, name='status'),
]

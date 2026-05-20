from django.urls import path

from .views import health, tushare_catalog, tushare_sync_status

urlpatterns = [
    path('health/', health, name='health'),
    path('tushare/catalog/', tushare_catalog, name='tushare-catalog'),
    path('tushare/sync/status/', tushare_sync_status, name='tushare-sync-status'),
]

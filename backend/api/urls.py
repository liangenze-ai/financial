from django.urls import path

from .views import health, quant_stock_diagnosis, tushare_catalog, tushare_sync_status

urlpatterns = [
    path('health/', health, name='health'),
    path('quant/stock-diagnosis/', quant_stock_diagnosis, name='quant-stock-diagnosis'),
    path('tushare/catalog/', tushare_catalog, name='tushare-catalog'),
    path('tushare/sync/status/', tushare_sync_status, name='tushare-sync-status'),
]

from django.http import JsonResponse

from api.models import SyncJob
from api.services.postgres import TABLES, TUSHARE_CATALOG


def serialize_job(job):
    if not job:
        return {'status': 'idle', 'message': 'No sync job has been started.'}

    return {
        'name': job.name,
        'status': job.status,
        'start_date': job.start_date,
        'end_date': job.end_date,
        'current_date': job.current_date,
        'current_step': job.current_step,
        'processed_dates': job.processed_dates,
        'message': job.message,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'updated_at': job.updated_at.isoformat() if job.updated_at else None,
    }


def health(request):
    return JsonResponse({'status': 'ok', 'service': 'finance-backend', 'database': 'postgresql'})


def tushare_sync_status(request):
    job = SyncJob.objects.filter(name='tushare_market_data').first()
    return JsonResponse(serialize_job(job))


def tushare_catalog(request):
    return JsonResponse({
        'database': 'postgresql',
        'tables': TABLES,
        'tushare_catalog': TUSHARE_CATALOG,
    })

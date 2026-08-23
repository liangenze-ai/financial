from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from api.models import SyncJob
from api.services.quant_baseline import TARGETS, diagnose_quant_stock, diagnose_quant_stock_combined
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


@require_GET
def quant_stock_diagnosis(request):
    ts_code = (request.GET.get('ts_code') or '').strip()
    trade_date = (request.GET.get('trade_date') or '').strip()
    target = (request.GET.get('target') or 'all').strip()
    feature_version = (request.GET.get('feature_version') or 'v1').strip()
    diagnosis_config = getattr(settings, 'QUANT_STOCK_DIAGNOSIS', {})
    primary_artifacts_dir = diagnosis_config.get('primary_artifacts_dir')
    fallback_artifacts_dir = diagnosis_config.get('fallback_artifacts_dir')
    switch_months = diagnosis_config.get('switch_months') or []

    if not ts_code:
        return JsonResponse({'error': 'ts_code is required.'}, status=400)
    if not trade_date:
        return JsonResponse({'error': 'trade_date is required.'}, status=400)
    if target not in {'all', *TARGETS.keys()}:
        return JsonResponse({'error': f'target must be one of: all, {", ".join(TARGETS)}.'}, status=400)

    try:
        if target == 'all':
            result = diagnose_quant_stock_combined(
                ts_code=ts_code,
                trade_date=trade_date,
                artifacts_dir=primary_artifacts_dir,
                fallback_artifacts_dir=fallback_artifacts_dir,
                switch_months=switch_months,
                feature_version=feature_version,
                write_report=False,
            )
        else:
            result = diagnose_quant_stock(
                ts_code=ts_code,
                trade_date=trade_date,
                artifacts_dir=primary_artifacts_dir,
                fallback_artifacts_dir=fallback_artifacts_dir,
                switch_months=switch_months,
                feature_version=feature_version,
                target_name=target,
                write_report=False,
            )
    except ValueError as exc:
        message = str(exc)
        status = 404 if 'was not found' in message or 'No diagnostic rows found' in message else 400
        return JsonResponse({'error': message}, status=status)
    except FileNotFoundError as exc:
        return JsonResponse({'error': str(exc)}, status=503)

    return JsonResponse(result['summary'], json_dumps_params={'ensure_ascii': False})

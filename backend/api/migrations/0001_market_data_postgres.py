from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='StockBasic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ts_code', models.CharField(max_length=24, unique=True)),
                ('symbol', models.CharField(blank=True, db_index=True, max_length=24, null=True)),
                ('name', models.CharField(blank=True, db_index=True, max_length=80, null=True)),
                ('area', models.CharField(blank=True, max_length=80, null=True)),
                ('industry', models.CharField(blank=True, max_length=120, null=True)),
                ('market', models.CharField(blank=True, max_length=40, null=True)),
                ('list_date', models.CharField(blank=True, max_length=8, null=True)),
                ('is_hs', models.CharField(blank=True, max_length=8, null=True)),
                ('tushare_meta', models.JSONField(blank=True, default=dict)),
            ],
            options={'db_table': 'tushare_stock_basic'},
        ),
        migrations.CreateModel(
            name='SyncJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=80, unique=True)),
                ('status', models.CharField(max_length=24)),
                ('start_date', models.CharField(blank=True, max_length=8, null=True)),
                ('end_date', models.CharField(blank=True, max_length=8, null=True)),
                ('current_date', models.CharField(blank=True, default='', max_length=8)),
                ('current_step', models.CharField(blank=True, default='', max_length=40)),
                ('processed_dates', models.IntegerField(default=0)),
                ('message', models.TextField(blank=True, default='')),
            ],
            options={'db_table': 'system_sync_jobs'},
        ),
        migrations.CreateModel(
            name='DailyBasic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ts_code', models.CharField(max_length=24)),
                ('trade_date', models.CharField(max_length=8)),
                ('close', models.FloatField(blank=True, null=True)),
                ('turnover_rate', models.FloatField(blank=True, null=True)),
                ('volume_ratio', models.FloatField(blank=True, null=True)),
                ('pe_ttm', models.FloatField(blank=True, null=True)),
                ('pb', models.FloatField(blank=True, null=True)),
                ('ps_ttm', models.FloatField(blank=True, null=True)),
                ('dv_ttm', models.FloatField(blank=True, null=True)),
                ('total_mv', models.FloatField(blank=True, null=True)),
                ('circ_mv', models.FloatField(blank=True, null=True)),
                ('tushare_meta', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'db_table': 'tushare_stock_daily_basic',
                'indexes': [models.Index(fields=['trade_date', 'ts_code'], name='tushare_sto_trade__8bcc1e_idx')],
                'constraints': [models.UniqueConstraint(fields=('ts_code', 'trade_date'), name='uniq_daily_basic_ts_code_date')],
            },
        ),
        migrations.CreateModel(
            name='DailyQuote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ts_code', models.CharField(max_length=24)),
                ('trade_date', models.CharField(max_length=8)),
                ('open', models.FloatField(blank=True, null=True)),
                ('high', models.FloatField(blank=True, null=True)),
                ('low', models.FloatField(blank=True, null=True)),
                ('close', models.FloatField(blank=True, null=True)),
                ('pre_close', models.FloatField(blank=True, null=True)),
                ('change', models.FloatField(blank=True, null=True)),
                ('pct_chg', models.FloatField(blank=True, null=True)),
                ('vol', models.FloatField(blank=True, null=True)),
                ('amount', models.FloatField(blank=True, null=True)),
                ('tushare_meta', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'db_table': 'tushare_stock_daily',
                'indexes': [models.Index(fields=['trade_date', 'ts_code'], name='tushare_sto_trade__475249_idx')],
                'constraints': [models.UniqueConstraint(fields=('ts_code', 'trade_date'), name='uniq_daily_ts_code_date')],
            },
        ),
        migrations.CreateModel(
            name='TradeCal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('exchange', models.CharField(max_length=16)),
                ('cal_date', models.CharField(max_length=8)),
                ('is_open', models.IntegerField(blank=True, db_index=True, null=True)),
                ('pretrade_date', models.CharField(blank=True, max_length=8, null=True)),
                ('tushare_meta', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'db_table': 'tushare_trade_cal',
                'indexes': [models.Index(fields=['is_open', 'cal_date'], name='tushare_tra_is_open_c53b8b_idx')],
                'constraints': [models.UniqueConstraint(fields=('exchange', 'cal_date'), name='uniq_trade_cal_exchange_date')],
            },
        ),
    ]

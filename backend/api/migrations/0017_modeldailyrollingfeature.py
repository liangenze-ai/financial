from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0016_modelsamplev1"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelDailyRollingFeature",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ts_code", models.CharField(max_length=24)),
                ("trade_date", models.CharField(max_length=8)),
                ("ma20", models.FloatField(blank=True, null=True)),
                ("ma60", models.FloatField(blank=True, null=True)),
                ("vol_20", models.FloatField(blank=True, null=True)),
                ("amount_ma20", models.FloatField(blank=True, null=True)),
            ],
            options={
                "db_table": "model_daily_rolling_features",
                "db_table_comment": "Daily rolling features for quant model samples",
                "indexes": [
                    models.Index(fields=["trade_date", "ts_code"], name="ix_model_roll_date_code"),
                    models.Index(fields=["ts_code", "trade_date"], name="ix_model_roll_code_date"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("ts_code", "trade_date"), name="uniq_model_daily_rolling_feature"),
                ],
            },
        ),
    ]

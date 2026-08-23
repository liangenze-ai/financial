from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_adjfactor_balancesheet_cashflowstatement_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "COMMENT ON COLUMN tushare_margin_detail.rzye IS '融资余额，单位元'",
                "COMMENT ON COLUMN tushare_margin_detail.rqye IS '融券余额，单位元'",
                "COMMENT ON COLUMN tushare_margin_detail.rzmre IS '融资买入额，单位元'",
                "COMMENT ON COLUMN tushare_margin_detail.rqyl IS '融券余量，单位股'",
                "COMMENT ON COLUMN tushare_margin_detail.rzche IS '融资偿还额，单位元'",
                "COMMENT ON COLUMN tushare_margin_detail.rqchl IS '融券偿还量，单位股'",
                "COMMENT ON COLUMN tushare_margin_detail.rqmcl IS '融券卖出量，单位股'",
                "COMMENT ON COLUMN tushare_margin_detail.rzrqye IS '融资融券余额，单位元'",
            ],
            reverse_sql=[
                "COMMENT ON COLUMN tushare_margin_detail.rzye IS NULL",
                "COMMENT ON COLUMN tushare_margin_detail.rqye IS NULL",
                "COMMENT ON COLUMN tushare_margin_detail.rzmre IS NULL",
                "COMMENT ON COLUMN tushare_margin_detail.rqyl IS NULL",
                "COMMENT ON COLUMN tushare_margin_detail.rzche IS NULL",
                "COMMENT ON COLUMN tushare_margin_detail.rqchl IS NULL",
                "COMMENT ON COLUMN tushare_margin_detail.rqmcl IS NULL",
                "COMMENT ON COLUMN tushare_margin_detail.rzrqye IS NULL",
            ],
        ),
    ]

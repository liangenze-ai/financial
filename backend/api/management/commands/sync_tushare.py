from api.services.tushare_sync import (sync_adj_factor_data, sync_balancesheet_data, sync_block_trade_data,
                                       sync_cashflow_data, sync_daily_basic_data, sync_daily_quote_data,
                                       sync_dividend_data, sync_express_data, sync_fina_indicator_data,
                                       sync_forecast_data, sync_hk_hold_data, sync_income_data, sync_index_basic_data,
                                       sync_index_classify_data, sync_index_daily_data, sync_index_member_all_data,
                                       sync_margin_data, sync_margin_detail_data, sync_market_data, sync_moneyflow_data,
                                       sync_namechange_data, sync_pledge_detail_data, sync_pledge_stat_data,
                                       sync_repurchase_data, sync_share_float_data, sync_st_risk_data,
                                       sync_stk_factor_pro_data, sync_stk_limit_data, sync_stk_premarket_data,
                                       sync_stock_basic_data, sync_stock_company_data, sync_stock_hsgt_data,
                                       sync_stock_st_data, sync_suspend_d_data, sync_top_inst_data, sync_top_list_data,
                                       sync_trade_cal_data)
from config.logging_setup import logger
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync A-share market data from TuShare with resumable progress."

    def add_arguments(self, parser):
        parser.add_argument(
            "--table",
            choices=[
                "all",
                "stock_basic",
                "trade_cal",
                "stk_premarket",
                "stock_st",
                "st",
                "stock_hsgt",
                "namechange",
                "stock_company",
                "daily",
                "daily_basic",
                "adj_factor",
                "fina_indicator",
                "income",
                "balancesheet",
                "cashflow",
                "index_basic",
                "index_daily",
                "index_classify",
                "index_member_all",
                "moneyflow",
                "margin_detail",
                "hk_hold",
                "suspend_d",
                "stk_limit",
                "share_float",
                "pledge_stat",
                "stk_factor_pro",
                "margin",
                "pledge_detail",
                "forecast",
                "express",
                "block_trade",
                "top_list",
                "top_inst",
                "dividend",
                "repurchase",
                "market_data",
                "model_core",
            ],
            default="market_data",
            help="TuShare table or sync group to sync.",
        )
        parser.add_argument(
            "--start-date",
            dest="start_date",
            help="Start date, e.g. 20240101. Omit to continue from the latest stored date.",
        )
        parser.add_argument("--end-date", dest="end_date", help="End date, e.g. 20240501. Omit to sync through today.")
        parser.add_argument(
            "--full",
            action="store_true",
            help="Use the earliest configured full-sync start date for date based tables.",
        )
        parser.add_argument("--no-resume", action="store_true", help="Restart from the beginning of the date range.")

    def handle(self, *args, **options):
        table = options["table"]
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        full = options.get("full")
        resume = not options.get("no_resume")
        logger.info(
            "sync_tushare command started: table={}, start_date={}, end_date={}, full={}, resume={}",
            table,
            start_date,
            end_date,
            full,
            resume,
        )

        try:
            if table == "stock_basic":
                result = sync_stock_basic_data()
            elif table == "trade_cal":
                result = sync_trade_cal_data(start_date=start_date, end_date=end_date)
            elif table == "stk_premarket":
                result = sync_stk_premarket_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "stock_st":
                result = sync_stock_st_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "st":
                result = sync_st_risk_data()
            elif table == "stock_hsgt":
                result = sync_stock_hsgt_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "namechange":
                result = sync_namechange_data()
            elif table == "stock_company":
                result = sync_stock_company_data()
            elif table == "daily":
                result = sync_daily_quote_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "daily_basic":
                result = sync_daily_basic_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "adj_factor":
                result = sync_adj_factor_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "fina_indicator":
                result = sync_fina_indicator_data(start_date=start_date, end_date=end_date)
            elif table == "income":
                result = sync_income_data(start_date=start_date, end_date=end_date)
            elif table == "balancesheet":
                result = sync_balancesheet_data(start_date=start_date, end_date=end_date)
            elif table == "cashflow":
                result = sync_cashflow_data(start_date=start_date, end_date=end_date)
            elif table == "index_basic":
                result = sync_index_basic_data()
            elif table == "index_daily":
                result = sync_index_daily_data(start_date=start_date, end_date=end_date, full=full)
            elif table == "index_classify":
                result = sync_index_classify_data()
            elif table == "index_member_all":
                result = sync_index_member_all_data()
            elif table == "moneyflow":
                result = sync_moneyflow_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "margin_detail":
                result = sync_margin_detail_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "hk_hold":
                result = sync_hk_hold_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "suspend_d":
                result = sync_suspend_d_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "stk_limit":
                result = sync_stk_limit_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "share_float":
                result = sync_share_float_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "pledge_stat":
                result = sync_pledge_stat_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "stk_factor_pro":
                result = sync_stk_factor_pro_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "margin":
                result = sync_margin_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "pledge_detail":
                result = sync_pledge_detail_data(start_date=start_date, end_date=end_date)
            elif table == "forecast":
                result = sync_forecast_data(start_date=start_date, end_date=end_date)
            elif table == "express":
                result = sync_express_data(start_date=start_date, end_date=end_date)
            elif table == "block_trade":
                result = sync_block_trade_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "top_list":
                result = sync_top_list_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "top_inst":
                result = sync_top_inst_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "dividend":
                result = sync_dividend_data(start_date=start_date, end_date=end_date)
            elif table == "repurchase":
                result = sync_repurchase_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == "model_core":
                result = {
                    "stock_basic": sync_stock_basic_data(),
                    "trade_cal": sync_trade_cal_data(start_date=start_date, end_date=end_date),
                    "market_data": sync_market_data(start_date=start_date, end_date=end_date, resume=resume, full=full),
                    "adj_factor": sync_adj_factor_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "index_basic": sync_index_basic_data(),
                    "index_daily": sync_index_daily_data(start_date=start_date, end_date=end_date, full=full),
                    "index_classify": sync_index_classify_data(),
                    "index_member_all": sync_index_member_all_data(),
                    "moneyflow": sync_moneyflow_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "margin_detail": sync_margin_detail_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "stock_st": sync_stock_st_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    "suspend_d": sync_suspend_d_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "stk_limit": sync_stk_limit_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "share_float": sync_share_float_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "pledge_stat": sync_pledge_stat_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "fina_indicator": sync_fina_indicator_data(start_date=start_date, end_date=end_date),
                    "income": sync_income_data(start_date=start_date, end_date=end_date),
                    "balancesheet": sync_balancesheet_data(start_date=start_date, end_date=end_date),
                    "cashflow": sync_cashflow_data(start_date=start_date, end_date=end_date),
                    "stk_factor_pro": sync_stk_factor_pro_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "margin": sync_margin_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    "pledge_detail": sync_pledge_detail_data(start_date=start_date, end_date=end_date),
                    "forecast": sync_forecast_data(start_date=start_date, end_date=end_date),
                    "express": sync_express_data(start_date=start_date, end_date=end_date),
                    "block_trade": sync_block_trade_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "top_list": sync_top_list_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    "top_inst": sync_top_inst_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    "dividend": sync_dividend_data(start_date=start_date, end_date=end_date),
                    "repurchase": sync_repurchase_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                }
            elif table == "all":
                result = {
                    "stock_basic": sync_stock_basic_data(),
                    "trade_cal": sync_trade_cal_data(start_date=start_date, end_date=end_date),
                    "stk_premarket": sync_stk_premarket_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "stock_st": sync_stock_st_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    "stock_hsgt": sync_stock_hsgt_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "st": sync_st_risk_data(),
                    "namechange": sync_namechange_data(),
                    "stock_company": sync_stock_company_data(),
                    "adj_factor": sync_adj_factor_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "fina_indicator": sync_fina_indicator_data(start_date=start_date, end_date=end_date),
                    "income": sync_income_data(start_date=start_date, end_date=end_date),
                    "balancesheet": sync_balancesheet_data(start_date=start_date, end_date=end_date),
                    "cashflow": sync_cashflow_data(start_date=start_date, end_date=end_date),
                    "index_basic": sync_index_basic_data(),
                    "index_daily": sync_index_daily_data(start_date=start_date, end_date=end_date, full=full),
                    "index_classify": sync_index_classify_data(),
                    "index_member_all": sync_index_member_all_data(),
                    "moneyflow": sync_moneyflow_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "margin_detail": sync_margin_detail_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "suspend_d": sync_suspend_d_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "stk_limit": sync_stk_limit_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "share_float": sync_share_float_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "pledge_stat": sync_pledge_stat_data(
                        start_date=start_date, end_date=end_date, full=full, resume=resume
                    ),
                    "market_data": sync_market_data(
                        start_date=start_date,
                        end_date=end_date,
                        resume=resume,
                        full=full,
                    ),
                }
            else:
                result = sync_market_data(
                    start_date=start_date,
                    end_date=end_date,
                    resume=resume,
                    full=full,
                )
        except Exception as exc:
            logger.exception(f"sync_tushare command failed: {exc}")
            raise

        logger.info("sync_tushare command finished: result={}", result)
        self.stdout.write(self.style.SUCCESS(str(result)))

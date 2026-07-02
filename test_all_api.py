# -*- coding: utf-8 -*-
"""
QMT Bridge 全量 API 测试脚本
逐个测试所有接口，输出通过/失败状态汇总
"""
import json
import time
import sys

from qmt_client import QMTClient

client = QMTClient()

# 测试结果收集
results = {"pass": [], "fail": [], "skip": []}


def test(name, func, skip=False):
    """执行单个测试用例"""
    if skip:
        results["skip"].append(name)
        print(f"  SKIP  {name}")
        return
    try:
        ret = func()
        # 判断是否返回了错误
        if isinstance(ret, dict) and ret.get("error") and ret.get("status_code"):
            results["fail"].append(name)
            print(f"  FAIL  {name}  -> {ret}")
        else:
            results["pass"].append(name)
            # 截断过长的输出
            out = json.dumps(ret, ensure_ascii=False, default=str)
            if len(out) > 200:
                out = out[:200] + "..."
            print(f"  PASS  {name}  -> {out}")
    except Exception as e:
        results["fail"].append(name)
        print(f"  FAIL  {name}  -> {str(e)}")


# ============================================================
# 1. 兼容路由（原有）
# ============================================================
print("\n========== 1. 兼容路由 ==========")
test("get_holding", lambda: client.get_holding("stock"))
test("get_total_money", lambda: client.get_total_money("stock"))
test("get_available_money", lambda: client.get_available_money("stock"))
test("python_version", lambda: client.python_version())

# ============================================================
# 2. ContextInfo 属性
# ============================================================
print("\n========== 2. ContextInfo 属性 ==========")
test("get_context_period", lambda: client.get_context_period())
test("get_context_barpos", lambda: client.get_context_barpos())
test("get_context_time_tick_size", lambda: client.get_context_time_tick_size())
test("get_context_stockcode", lambda: client.get_context_stockcode())
test("get_context_dividend_type", lambda: client.get_context_dividend_type())
test("get_context_market", lambda: client.get_context_market())
test("get_context_do_back_test", lambda: client.get_context_do_back_test())
test("get_context_benchmark", lambda: client.get_context_benchmark())
test("get_context_capital", lambda: client.get_context_capital())
test("get_context_universe", lambda: client.get_context_universe())
test("get_context_start", lambda: client.get_context_start())
test("get_context_end", lambda: client.get_context_end())

# ============================================================
# 3. ContextInfo 设置
# ============================================================
print("\n========== 3. ContextInfo 设置 ==========")
# set_universe / set_account 会改变策略状态，谨慎测试
test("set_universe", lambda: client.set_universe(["600000.SH", "000001.SZ"]), skip=True)
test("set_account", lambda: client.set_account("200133"), skip=True)
test("set_output_index_property", lambda: client.set_output_index_property("test_idx", 0, "white"), skip=True)

# ============================================================
# 4. 数据查询
# ============================================================
print("\n========== 4. 数据查询 ==========")
test("get_stock_name", lambda: client.get_stock_name("600000.SH"))
test("get_open_date", lambda: client.get_open_date("600000.SH"))
test("get_last_volume", lambda: client.get_last_volume("600000.SH"))
test("get_bar_timetag", lambda: client.get_bar_timetag(0))
test("get_tick_timetag", lambda: client.get_tick_timetag())
test("get_sector", lambda: client.get_sector("000300.SH"))
test("get_industry", lambda: client.get_industry("CSRC餐饮业"))
test("get_stock_list_in_sector", lambda: client.get_stock_list_in_sector("沪深A股"))
test("get_weight_in_index", lambda: client.get_weight_in_index("000300.SH", "600000.SH"))
test("get_contract_multiplier", lambda: client.get_contract_multiplier("IF"))
test("get_risk_free_rate", lambda: client.get_risk_free_rate(0))
test("get_date_location", lambda: client.get_date_location("20250101"))
test("get_history_data", lambda: client.get_history_data(5, "1d", "close"))
test("get_market_data", lambda: client.get_market_data("close", "600000.SH", "20250101", "20250601"))
test("get_market_data_ex", lambda: client.get_market_data_ex(["600000.SH", "000001.SZ"]))
test("get_full_tick", lambda: client.get_full_tick("600000.SH"))
test("get_divid_factors", lambda: client.get_divid_factors("600000.SH"))
test("get_main_contract", lambda: client.get_main_contract("CU"))
test("timetag_to_datetime", lambda: client.timetag_to_datetime(1704067200000))
test("get_total_share", lambda: client.get_total_share("600000.SH"))
test("get_trading_dates", lambda: client.get_trading_dates("600000.SH", "20250101", "20250131"))
test("get_svol", lambda: client.get_svol("600000.SH"))
test("get_bvol", lambda: client.get_bvol("600000.SH"))
test("get_longhubang", lambda: client.get_longhubang(["600000.SH"], "20250601", "20250630"))
test("get_top10_share_holder", lambda: client.get_top10_share_holder(["600000.SH"]))
test("get_option_detail", lambda: client.get_option_detail("10003720"))
test("get_turnover_rate", lambda: client.get_turnover_rate(["600000.SH"], "20250601", "20250630"))
test("get_etf_info", lambda: client.get_etf_info("510050.SH"))
test("get_etf_iopv", lambda: client.get_etf_iopv("510050.SH"))
test("get_instrumentdetail", lambda: client.get_instrumentdetail("600000.SH"))
test("get_contract_expire_date", lambda: client.get_contract_expire_date("IF2501"))
test("get_option_undl_data", lambda: client.get_option_undl_data("510050"))
test("get_financial_data", lambda: client.get_financial_data("REVSQ", "600000.SH", "20240101", "20241231"))
test("get_factor_data", lambda: client.get_factor_data("alpha1", "600000.SH", "20240101", "20241231"))
test("get_his_st_data", lambda: client.get_his_st_data("600000.SH"))
test("get_his_index_data", lambda: client.get_his_index_data("000001.SH"))
test("get_all_subscription", lambda: client.get_all_subscription())
test("get_option_list", lambda: client.get_option_list("510050"))
test("get_his_contract_list", lambda: client.get_his_contract_list("IF"))
test("get_option_iv", lambda: client.get_option_iv("10003720"))
test("bsm_price", lambda: client.bsm_price("C", 2.5, 2.5, 0.03, 0.2, 30, 0))
test("bsm_iv", lambda: client.bsm_iv("C", 2.5, 2.5, 0.1, 0.03, 30, 0))
test("get_local_data", lambda: client.get_local_data("600000.SH", "20250101", "20250601"))
test("get_close_price", lambda: client.get_close_price("600000.SH", "1d", 1704067200000))
test("get_close_price_by_date", lambda: client.get_close_price_by_date("600000.SH", "1d", "20250101"))
test("download_history_data", lambda: client.download_history_data("600000.SH"), skip=True)

# ============================================================
# 5. 订阅
# ============================================================
print("\n========== 5. 订阅 ==========")
test("subscribe_quote", lambda: client.subscribe_quote("600000.SH", "1d"))
test("subscribe_whole_quote", lambda: client.subscribe_whole_quote(["600000.SH"]))
test("get_sub_tick_cache", lambda: client.get_sub_tick_cache())
test("get_sub_quote_cache", lambda: client.get_sub_quote_cache())
test("unsubscribe_quote", lambda: client.unsubscribe_quote(0))

# ============================================================
# 6. 判定函数
# ============================================================
print("\n========== 6. 判定函数 ==========")
test("is_last_bar", lambda: client.is_last_bar())
test("is_new_bar", lambda: client.is_new_bar())
test("is_suspended_stock", lambda: client.is_suspended_stock("600000.SH"))
test("is_sector_stock", lambda: client.is_sector_stock("沪深A股", "SH", "600000.SH"))
test("is_typed_stock", lambda: client.is_typed_stock(4, "SH", "600000.SH"))
test("get_industry_name_of_stock", lambda: client.get_industry_name_of_stock("CSRC", "600000.SH"))

# ============================================================
# 7. 交易函数（只测不实际下单的查询类接口）
# ============================================================
print("\n========== 7. 交易函数 ==========")
# 下单类接口跳过，避免实盘误操作
test("buy_stock", lambda: client.buy_stock("600000.SH", 10.0, 100), skip=True)
test("sell_stock", lambda: client.sell_stock("600000.SH", 10.0, 100), skip=True)
test("passorder", lambda: client.passorder(23, 1101, "600000.SH", 11, 10.0, 100), skip=True)
test("algo_passorder", lambda: client.algo_passorder(23, 1101, "600000.SH", -1, 10.0, 100), skip=True)
test("smart_algo_passorder", lambda: client.smart_algo_passorder(23, 1101, "600000.SH", -1, 10.0, 100, "VWAP"), skip=True)
test("order_lots", lambda: client.order_lots("600000.SH", 1), skip=True)
test("order_value", lambda: client.order_value("600000.SH", 10000), skip=True)
test("order_percent", lambda: client.order_percent("600000.SH", 0.1), skip=True)
test("order_target_value", lambda: client.order_target_value("600000.SH", 10000), skip=True)
test("order_target_percent", lambda: client.order_target_percent("600000.SH", 0.5), skip=True)
test("order_shares", lambda: client.order_shares("600000.SH", 100), skip=True)
test("cancel_order_by_id", lambda: client.cancel_order_by_id("12345"), skip=True)

# ============================================================
# 8. 期货交易
# ============================================================
print("\n========== 8. 期货交易 ==========")
test("buy_open", lambda: client.buy_open("IF2501", 1), skip=True)
test("buy_close_tdayfirst", lambda: client.buy_close_tdayfirst("IF2501", 1), skip=True)
test("buy_close_ydayfirst", lambda: client.buy_close_ydayfirst("IF2501", 1), skip=True)
test("sell_open", lambda: client.sell_open("IF2501", 1), skip=True)
test("sell_close_tdayfirst", lambda: client.sell_close_tdayfirst("IF2501", 1), skip=True)
test("sell_close_ydayfirst", lambda: client.sell_close_ydayfirst("IF2501", 1), skip=True)

# ============================================================
# 9. 任务管理
# ============================================================
print("\n========== 9. 任务管理 ==========")
test("cancel_task", lambda: client.cancel_task("task_1"), skip=True)
test("pause_task", lambda: client.pause_task("task_1"), skip=True)
test("resume_task", lambda: client.resume_task("task_1"), skip=True)
test("do_order", lambda: client.do_order(), skip=True)

# ============================================================
# 10. 账户/订单查询
# ============================================================
print("\n========== 10. 账户/订单查询 ==========")
test("get_trade_detail_data_position", lambda: client.get_trade_detail_data("stock", "position"))
test("get_trade_detail_data_account", lambda: client.get_trade_detail_data("stock", "account"))
test("get_trade_detail_data_order", lambda: client.get_trade_detail_data("stock", "order"))
test("get_trade_detail_data_deal", lambda: client.get_trade_detail_data("stock", "deal"))
test("get_value_by_order_id", lambda: client.get_value_by_order_id("12345"))
test("get_last_order_id", lambda: client.get_last_order_id())
test("can_cancel_order", lambda: client.can_cancel_order("12345"))
test("get_debt_contract", lambda: client.get_debt_contract())
test("get_assure_contract", lambda: client.get_assure_contract())
test("get_enable_short_contract", lambda: client.get_enable_short_contract())
test("get_ipo_data", lambda: client.get_ipo_data())
test("get_new_purchase_limit", lambda: client.get_new_purchase_limit())
test("get_smart_algo_param", lambda: client.get_smart_algo_param(["VWAP"]))
test("query_credit_account", lambda: client.query_credit_account())
test("query_credit_opvolume", lambda: client.query_credit_opvolume())

# ============================================================
# 11. 引用函数
# ============================================================
print("\n========== 11. 引用函数 ==========")
test("ext_data", lambda: client.ext_data("测试指标", "600000.SH"))
test("ext_data_rank", lambda: client.ext_data_rank("测试指标", "600000.SH"))
test("ext_data_rank_range", lambda: client.ext_data_rank_range("测试指标", "600000.SH", "20250101", "20250601"))
test("ext_data_range", lambda: client.ext_data_range("测试指标", "600000.SH", "20250101", "20250601"))
test("get_factor_value", lambda: client.get_factor_value("alpha1", "600000.SH"))
test("get_factor_rank", lambda: client.get_factor_rank("alpha1", "600000.SH"))

# ============================================================
# 12. 板块管理
# ============================================================
print("\n========== 12. 板块管理 ==========")
test("get_sector_list", lambda: client.get_sector_list())
# 以下会修改板块数据，谨慎测试
test("create_sector", lambda: client.create_sector("", "测试板块"), skip=True)
test("create_sector_folder", lambda: client.create_sector_folder("", "测试文件夹"), skip=True)
test("reset_sector_stock_list", lambda: client.reset_sector_stock_list("测试板块", ["600000.SH"]), skip=True)
test("add_stock_to_sector", lambda: client.add_stock_to_sector("测试板块", "600000.SH"), skip=True)
test("remove_stock_from_sector", lambda: client.remove_stock_from_sector("测试板块", "600000.SH"), skip=True)

# ============================================================
# 13. 兼容方法
# ============================================================
print("\n========== 13. 兼容方法 ==========")
test("get_order_status", lambda: client.get_order_status())
test("cancel_all_orders", lambda: client.cancel_all_orders(), skip=True)
test("cancel_order", lambda: client.cancel_order("600000.SH", 100), skip=True)
test("get_deal", lambda: client.get_deal())

# ============================================================
# 14. 系统
# ============================================================
print("\n========== 14. 系统 ==========")
test("close", lambda: client.close(), skip=True)


# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
print(f"  PASS: {len(results['pass'])}")
print(f"  FAIL: {len(results['fail'])}")
print(f"  SKIP: {len(results['skip'])}  (下单/修改类接口，需手动测试)")
print("=" * 60)

if results["fail"]:
    print("\n失败列表:")
    for name in results["fail"]:
        print(f"  - {name}")
    sys.exit(1)
else:
    print("\n所有可测试接口全部通过!")
    sys.exit(0)

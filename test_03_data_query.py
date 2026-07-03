# -*- coding: utf-8 -*-
"""
测试3: 数据查询（行情、历史、财务、基本面）
独立运行: python test_03_data_query.py
"""
import time
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF, TEST_STOCK, TEST_INDEX, FINANCE_STOCK
)

setup_logging("test_03_data_query")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

# 先下载历史数据（覆盖足够长时间范围，确保后续接口有数据可用）
# download_history_data是异步的，需要等待数据写入本地
print("\n========== 下载历史数据 ==========")
assert_test(results, "download_history_data(ETF)", lambda: client.download_history_data(TEST_ETF, start_time="20240101", end_time="20261231"), [
    (("result",), lambda v: v is True, "下载结果为True"),
])
assert_test(results, "download_history_data(财务)", lambda: client.download_history_data(FINANCE_STOCK, start_time="20240101", end_time="20261231"))
assert_test(results, "download_history_data(沪深300)", lambda: client.download_history_data("000300.SH", start_time="20240101", end_time="20261231"))
print("  等待数据下载写入本地...")
time.sleep(5)

# 验证数据是否可用（用get_local_data确认数据已下载完成）
print("\n========== 验证下载数据 ==========")
verify_data = client.get_local_data(TEST_ETF, "20250101", "20250601")
has_data = isinstance(verify_data, dict) and verify_data.get("data") not in [None, {}, ""]
print("  数据验证: {}".format("OK" if has_data else "数据可能未就绪"))
if not has_data:
    print("  额外等待5秒...")
    time.sleep(5)

# 行情数据
print("\n========== 行情数据 ==========")
assert_test(results, "get_stock_name", lambda: client.get_stock_name(TEST_ETF), [
    (("name",), lambda v: "ETF" in str(v) or "证券" in str(v), "股票名包含ETF或证券"),
])
assert_test(results, "get_open_date", lambda: client.get_open_date(TEST_ETF), [
    (("open_date",), lambda v: v is not None and v > 0, "上市日期>0"),
])
assert_test(results, "get_full_tick", lambda: client.get_full_tick(TEST_ETF), [
    ((TEST_ETF, "lastPrice"), lambda v: v is not None and v > 0, "最新价>0"),
    ((TEST_ETF, "volume"), lambda v: v is not None and v > 0, "成交量>0"),
])
assert_test(results, "get_market_data", lambda: client.get_market_data("close", TEST_ETF, "20250101", "20250601"), [
    (("data", "close"), lambda v: v is not None and len(v) > 0, "有收盘价数据"),
])
assert_test(results, "get_market_data_ex", lambda: client.get_market_data_ex(
    [TEST_ETF], fields="open,high,low,close,volume", period="1d", start_time="20250101", end_time="20250131"), [
    (("data", TEST_ETF, "close"), lambda v: v is not None and len(v) > 0, "有close数据"),
])
assert_test(results, "get_sector", lambda: client.get_sector(TEST_INDEX), [
    (("stocks",), lambda v: isinstance(v, list) and len(v) > 0, "指数成份股列表非空"),
])
assert_test(results, "get_stock_list_in_sector", lambda: client.get_stock_list_in_sector("沪深A股"), [
    (("stocks",), lambda v: isinstance(v, list) and len(v) > 100, "沪深A股数量>100"),
])
assert_test(results, "get_instrumentdetail", lambda: client.get_instrumentdetail(TEST_ETF), [
    (("detail", "InstrumentName"), lambda v: "ETF" in str(v) or "证券" in str(v), "名称含ETF或证券"),
])
assert_test(results, "get_svol", lambda: client.get_svol(TEST_ETF), [
    (("svol",), lambda v: v is not None and v > 0, "卖量>0"),
])
assert_test(results, "get_bvol", lambda: client.get_bvol(TEST_ETF), [
    (("bvol",), lambda v: v is not None and v > 0, "买量>0"),
])
assert_test(results, "get_close_price_by_date", lambda: client.get_close_price_by_date(TEST_ETF, "1d", "20250102"), [
    (("close_price",), lambda v: v is not None and v > 0, "收盘价>0"),
])
assert_test(results, "timetag_to_datetime", lambda: client.timetag_to_datetime(1704067200000), [
    (("datetime",), lambda v: "2024" in str(v), "时间戳转换正确"),
])
assert_test(results, "bsm_price", lambda: client.bsm_price("C", 2.5, 2.5, 0.03, 0.2, 30, 0), [
    (("price",), lambda v: v is not None and v > 0, "BSM价格>0"),
])
assert_test(results, "bsm_iv", lambda: client.bsm_iv("C", 2.5, 2.5, 0.1, 0.03, 30, 0), [
    (("iv",), lambda v: v is not None and v > 0, "隐含波动率>0"),
])
assert_test(results, "get_etf_iopv", lambda: client.get_etf_iopv("510050.SH"), [
    (("iopv",), lambda v: v is not None and v > 0, "IOPV>0"),
])

# 财务数据（字段格式: 表名.字段名，如 ASHAREINCOME.net_profit_incl_min_int_inc）
print("\n========== 财务数据 ==========")
assert_test(results, "get_financial_data", lambda: client.get_financial_data(
    "ASHAREINCOME.net_profit_incl_min_int_inc,CAPITALSTRUCTURE.total_capital,PERSHAREINDEX.s_fa_eps_basic",
    FINANCE_STOCK, "20240101", "20241231"), [
    (("data",), lambda v: v is not None and v != {} and v != 0, "财务数据非空"),
])
assert_test(results, "get_trading_dates", lambda: client.get_trading_dates("000300.SH", "20250101", "20250630", count=100), [
    (("dates",), lambda v: isinstance(v, list) and len(v) > 0, "交易日列表非空"),
])
assert_test(results, "get_turnover_rate", lambda: client.get_turnover_rate([TEST_STOCK], "20250601", "20250630"))

# 其他数据接口
print("\n========== 其他数据接口 ==========")
assert_test(results, "get_last_volume", lambda: client.get_last_volume(TEST_ETF))
assert_test(results, "get_bar_timetag", lambda: client.get_bar_timetag(-1))
assert_test(results, "get_tick_timetag", lambda: client.get_tick_timetag())
assert_test(results, "get_industry", lambda: client.get_industry("CSRC计算机通信和其他电子设备制造业"))
assert_test(results, "get_weight_in_index", lambda: client.get_weight_in_index(TEST_INDEX, TEST_ETF))
assert_test(results, "get_contract_multiplier", lambda: client.get_contract_multiplier("IF"))
assert_test(results, "get_risk_free_rate", lambda: client.get_risk_free_rate(0))
assert_test(results, "get_date_location", lambda: client.get_date_location("20250101"))
assert_test(results, "get_history_data", lambda: client.get_history_data(5, "1d", "close", stock_list=TEST_ETF), [
    (("data",), lambda v: v is not None and v != {} and len(v) > 0, "历史数据非空"),
])
assert_test(results, "get_divid_factors", lambda: client.get_divid_factors(TEST_ETF))
assert_test(results, "get_main_contract", lambda: client.get_main_contract("CU"))
assert_test(results, "get_total_share", lambda: client.get_total_share(TEST_ETF))
assert_test(results, "get_longhubang", lambda: client.get_longhubang([TEST_STOCK], "20250601", "20250630"))
assert_test(results, "get_top10_share_holder", lambda: client.get_top10_share_holder([TEST_STOCK]))
assert_test(results, "get_option_detail", lambda: client.get_option_detail("10003720"))
assert_test(results, "get_etf_info", lambda: client.get_etf_info("510050.SH"))
assert_test(results, "get_contract_expire_date", lambda: client.get_contract_expire_date("IF2501"))
assert_test(results, "get_option_undl_data", lambda: client.get_option_undl_data("510050"))
assert_test(results, "get_factor_data", lambda: client.get_factor_data("a", TEST_STOCK, "20240101", "20241231"))
# 注意: get_factor_data/get_factor_value 依赖handlebar上下文，HTTP handler中无法调用
# 如需使用，请在QMT策略的handlebar回调中直接调用
assert_test(results, "get_his_st_data", lambda: client.get_his_st_data(TEST_STOCK))
assert_test(results, "get_his_index_data", lambda: client.get_his_index_data(TEST_INDEX))
assert_test(results, "get_all_subscription", lambda: client.get_all_subscription())
assert_test(results, "get_option_list", lambda: client.get_option_list("510050.SH"))
assert_test(results, "get_his_contract_list", lambda: client.get_his_contract_list("IF"))
assert_test(results, "get_option_iv", lambda: client.get_option_iv("10003720"))
assert_test(results, "get_local_data", lambda: client.get_local_data(TEST_ETF, "20250101", "20250601"))
assert_test(results, "get_close_price", lambda: client.get_close_price(TEST_ETF, "1d", 1704067200000))

ok = print_summary(results)
sys.exit(0 if ok else 1)

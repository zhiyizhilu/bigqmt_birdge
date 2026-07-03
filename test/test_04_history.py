# -*- coding: utf-8 -*-
"""
测试4: 历史数据 + 交易日期
先下载数据，再测试历史数据相关接口
独立运行: python test_04_history.py
"""
import time
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF, TEST_INDEX, TEST_STOCK
)

setup_logging("test_04_history")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# 下载历史数据
# ============================================================
print("\n========== 下载历史数据 ==========")
assert_test(results, "download_history_data(ETF)", lambda: client.download_history_data(TEST_ETF, start_time="20240101", end_time="20261231"), [
    (("result",), lambda v: v is True, "下载结果为True"),
])
assert_test(results, "download_history_data(沪深300)", lambda: client.download_history_data("000300.SH", start_time="20240101", end_time="20261231"))
print("  等待数据下载写入本地...")
time.sleep(5)

# ============================================================
# 历史数据
# ============================================================
print("\n========== 历史数据 ==========")
assert_test(results, "get_history_data", lambda: client.get_history_data(5, "1d", "close", stock_list=TEST_ETF), [
    (("data",), lambda v: v is not None and v != {} and len(v) > 0, "历史数据非空"),
])
assert_test(results, "get_local_data", lambda: client.get_local_data(TEST_ETF, "20250101", "20250601"))
assert_test(results, "get_trading_dates", lambda: client.get_trading_dates("000300.SH", "20250101", "20250630", count=100), [
    (("dates",), lambda v: isinstance(v, list) and len(v) > 0, "交易日列表非空"),
])
assert_test(results, "get_bar_timetag", lambda: client.get_bar_timetag(-1))
assert_test(results, "get_tick_timetag", lambda: client.get_tick_timetag())
assert_test(results, "get_date_location", lambda: client.get_date_location("20250101"))
assert_test(results, "timetag_to_datetime", lambda: client.timetag_to_datetime(1704067200000), [
    (("datetime",), lambda v: "2024" in str(v), "时间戳转换正确"),
])
assert_test(results, "get_divid_factors", lambda: client.get_divid_factors(TEST_STOCK))
assert_test(results, "get_weight_in_index", lambda: client.get_weight_in_index(TEST_INDEX, TEST_STOCK), [
    (("weight",), lambda v: v is not None and v > 0, "权重>0"),
])

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

# -*- coding: utf-8 -*-
"""
测试3: 实时行情数据
先下载数据，再测试行情相关接口
独立运行: python test_03_quote.py
"""
import time
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF, TEST_STOCK
)

setup_logging("test_03_quote")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# 先下载历史数据（覆盖足够长时间范围，确保后续接口有数据可用）
# ============================================================
print("\n========== 下载历史数据 ==========")
assert_test(results, "download_history_data", lambda: client.download_history_data(TEST_ETF, start_time="20240101", end_time="20261231"), [
    (("result",), lambda v: v is True, "下载结果为True"),
])
print("  等待数据下载写入本地...")
time.sleep(5)

# 验证数据是否可用
verify_data = client.get_local_data(TEST_ETF, "20250101", "20250601")
has_data = isinstance(verify_data, dict) and verify_data.get("data") not in [None, {}, ""]
print("  数据验证: {}".format("OK" if has_data else "数据可能未就绪"))
if not has_data:
    print("  额外等待5秒...")
    time.sleep(5)

# ============================================================
# 行情数据
# ============================================================
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
assert_test(results, "get_svol", lambda: client.get_svol(TEST_ETF), [
    (("svol",), lambda v: v is not None and v > 0, "卖量>0"),
])
assert_test(results, "get_bvol", lambda: client.get_bvol(TEST_ETF), [
    (("bvol",), lambda v: v is not None and v > 0, "买量>0"),
])
assert_test(results, "get_last_volume", lambda: client.get_last_volume(TEST_ETF))
assert_test(results, "get_close_price", lambda: client.get_close_price(TEST_ETF, "1d", 1704067200000))
assert_test(results, "get_close_price_by_date", lambda: client.get_close_price_by_date(TEST_ETF, "1d", "20250102"), [
    (("close_price",), lambda v: v is not None and v > 0, "收盘价>0"),
])
assert_test(results, "get_turnover_rate", lambda: client.get_turnover_rate([TEST_STOCK], startTime="20260101", endTime="20260631"), [
    (("turnover_rate",), lambda v: v is not None and v > 0, "换手率>0"),
])
assert_test(results, "get_instrumentdetail", lambda: client.get_instrumentdetail(TEST_ETF), [
    (("detail", "InstrumentName"), lambda v: "ETF" in str(v) or "证券" in str(v), "名称含ETF或证券"),
])
assert_test(results, "get_market_time", lambda: client.get_market_time(), [
    (("data",), lambda v: v is not None, "数据不为空"),
])
assert_test(results, "get_etf_iopv", lambda: client.get_etf_iopv("510050.SH"), [
    (("iopv",), lambda v: v is not None and v > 0, "IOPV>0"),
])
assert_test(results, "get_etf_info", lambda: client.get_etf_info("510050.SH"))

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

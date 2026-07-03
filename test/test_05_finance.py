# -*- coding: utf-8 -*-
"""
测试5: 财务/基本面数据
独立运行: python test_05_finance.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF, TEST_STOCK, TEST_INDEX, FINANCE_STOCK
)

setup_logging("test_05_finance")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# 财务数据
# ============================================================
print("\n========== 财务数据 ==========")
assert_test(results, "get_financial_data", lambda: client.get_financial_data(
    "ASHAREINCOME.net_profit_incl_min_int_inc",
    FINANCE_STOCK, "20260101", "20261231"), [
    (("data",), lambda v: v is not None and v != {} and v != 0, "财务数据非空"),
])
assert_test(results, "get_raw_financial_data", lambda: client.get_raw_financial_data(
    "ASHAREINCOME.net_profit_incl_min_int_inc",
    FINANCE_STOCK, "20260101", "20261231"), [
    (("data",), lambda v: v is not None and v != {}, "原始财务数据非空"),
])

# ============================================================
# 基本面数据
# ============================================================
print("\n========== 基本面数据 ==========")
assert_test(results, "get_longhubang", lambda: client.get_longhubang([TEST_STOCK], "20260101", "20261231"))
assert_test(results, "get_top10_share_holder", lambda: client.get_top10_share_holder([TEST_STOCK]))
assert_test(results, "get_his_st_data", lambda: client.get_his_st_data(TEST_STOCK))
assert_test(results, "get_his_index_data", lambda: client.get_his_index_data(TEST_INDEX))
assert_test(results, "get_st_status", lambda: client.get_st_status(TEST_STOCK))
assert_test(results, "get_total_share", lambda: client.get_total_share(TEST_STOCK))
assert_test(results, "get_risk_free_rate", lambda: client.get_risk_free_rate(0))

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

# -*- coding: utf-8 -*-
"""
测试1: 兼容路由 + 兼容方法
独立运行: python test_01_compat.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF
)

setup_logging("test_01_compat")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

# ============================================================
# 兼容路由
# ============================================================
print("\n========== 兼容路由 ==========")
assert_test(results, "get_holding", lambda: client.get_holding("stock"), [
    (("513090.SH",), lambda v: v is not None, "持仓中有513090.SH"),
])
assert_test(results, "get_total_money", lambda: client.get_total_money("stock"), [
    (("total_money",), lambda v: v is not None and v > 0, "总资产>0"),
])
assert_test(results, "get_available_money", lambda: client.get_available_money("stock"), [
    (("available_money",), lambda v: v is not None and v > 0, "可用资金>0"),
])
assert_test(results, "python_version", lambda: client.python_version(), [
    (("python_version",), lambda v: "3.6" in str(v), "Python版本为3.6"),
])

# ============================================================
# 兼容方法
# ============================================================
print("\n========== 兼容方法 ==========")
assert_test(results, "get_order_status", lambda: client.get_order_status(), [
    (("orders",), lambda v: isinstance(v, list), "订单为列表"),
])
assert_test(results, "get_deal", lambda: client.get_deal(), [
    (("deals",), lambda v: isinstance(v, list), "成交为列表"),
])

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

# -*- coding: utf-8 -*-
"""
测试7: 北向资金 + 港股通数据
独立运行: python test_07_cross_border.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient
)

setup_logging("test_07_cross_border")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# 北向资金
# ============================================================
print("\n========== 北向资金 ==========")
assert_test(results, "get_north_finance_change", lambda: client.get_north_finance_change("1d"))

# ============================================================
# 港股通
# ============================================================
print("\n========== 港股通 ==========")
assert_test(results, "get_hkt_exchange_rate", lambda: client.get_hkt_exchange_rate())
assert_test(results, "get_hkt_details", lambda: client.get_hkt_details("00700.HK"))
assert_test(results, "get_hkt_statistics", lambda: client.get_hkt_statistics("00700.HK"))

# ============================================================
# 板块股票列表
# ============================================================
print("\n========== 板块股票列表 ==========")
assert_test(results, "get_stock_list_in_sector", lambda: client.get_stock_list_in_sector("沪深A股"), [
    (("stocks",), lambda v: isinstance(v, list) and len(v) > 100, "沪深A股数量>100"),
])

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

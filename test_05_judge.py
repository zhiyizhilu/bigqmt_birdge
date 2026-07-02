# -*- coding: utf-8 -*-
"""
测试5: 判定函数 + 板块管理
独立运行: python test_05_judge.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF, TEST_STOCK
)

setup_logging("test_05_judge")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

# ============================================================
# 判定函数
# ============================================================
print("\n========== 判定函数 ==========")
assert_test(results, "is_last_bar", lambda: client.is_last_bar(), [
    (("is_last_bar",), lambda v: v is not None, "返回值非空"),
])
assert_test(results, "is_suspended_stock", lambda: client.is_suspended_stock(TEST_ETF), [
    (("is_suspended",), lambda v: v is False, "513090未停牌"),
])
assert_test(results, "get_industry_name_of_stock", lambda: client.get_industry_name_of_stock("CSRC", TEST_STOCK), [
    (("industry_name",), lambda v: v is not None and len(str(v)) > 0, "行业名非空"),
])
assert_test(results, "is_new_bar", lambda: client.is_new_bar())
assert_test(results, "is_sector_stock", lambda: client.is_sector_stock("沪深A股", "SH", TEST_ETF))
assert_test(results, "is_typed_stock", lambda: client.is_typed_stock(4, "SH", TEST_ETF))

# ============================================================
# 板块管理
# ============================================================
print("\n========== 板块管理 ==========")
assert_test(results, "get_sector_list", lambda: client.get_sector_list(), [
    (("data",), lambda v: v is not None, "板块列表非空"),
])

ok = print_summary(results)
sys.exit(0 if ok else 1)

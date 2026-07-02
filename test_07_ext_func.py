# -*- coding: utf-8 -*-
"""
测试7: 引用函数（ext_data / factor）
独立运行: python test_07_ext_func.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF
)

setup_logging("test_07_ext_func")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

print("\n========== 引用函数 ==========")
assert_test(results, "ext_data", lambda: client.ext_data("测试指标", TEST_ETF))
assert_test(results, "ext_data_rank", lambda: client.ext_data_rank("测试指标", TEST_ETF))
assert_test(results, "ext_data_rank_range", lambda: client.ext_data_rank_range("测试指标", TEST_ETF, "20250101", "20250601"))
assert_test(results, "ext_data_range", lambda: client.ext_data_range("测试指标", TEST_ETF, "20250101", "20250601"))
assert_test(results, "get_factor_value", lambda: client.get_factor_value("alpha1", TEST_ETF))
assert_test(results, "get_factor_rank", lambda: client.get_factor_rank("alpha1", TEST_ETF))

ok = print_summary(results)
sys.exit(0 if ok else 1)

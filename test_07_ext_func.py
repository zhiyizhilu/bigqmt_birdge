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
# 注意: ext_data/ext_data_rank 等引用函数需要策略中预先定义的指标名
# get_factor_value/get_factor_rank 需要有效的因子名且依赖handlebar上下文
# 以下测试使用假指标名/因子名，仅验证接口不报错，返回值为null/0/{}是预期行为
assert_test(results, "ext_data", lambda: client.ext_data("测试指标", TEST_ETF))
assert_test(results, "ext_data_rank", lambda: client.ext_data_rank("测试指标", TEST_ETF))
assert_test(results, "ext_data_rank_range", lambda: client.ext_data_rank_range("测试指标", TEST_ETF, "20250101", "20250601"))
assert_test(results, "ext_data_range", lambda: client.ext_data_range("测试指标", TEST_ETF, "20250101", "20250601"))
assert_test(results, "get_factor_value", lambda: client.get_factor_value("alpha1", TEST_ETF))
assert_test(results, "get_factor_rank", lambda: client.get_factor_rank("alpha1", TEST_ETF))

ok = print_summary(results)
sys.exit(0 if ok else 1)

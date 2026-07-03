# -*- coding: utf-8 -*-
"""
测试11: 扩展函数 + 因子 + 公式
独立运行: python test_11_ext.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_STOCK
)

setup_logging("test_11_ext")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# 引用函数
# ============================================================
print("\n========== 引用函数 ==========")
# 注意: ext_data/ext_data_rank 等引用函数需要策略中预先定义的指标名
# 以下测试使用假指标名，仅验证接口不报错，返回值为null/0/{}是预期行为
assert_test(results, "ext_data", lambda: client.ext_data("test_indicator", TEST_STOCK))
assert_test(results, "ext_data_rank", lambda: client.ext_data_rank("test_indicator", TEST_STOCK))
assert_test(results, "ext_data_rank_range", lambda: client.ext_data_rank_range("test_indicator", TEST_STOCK, "20260101", "20260601"))
assert_test(results, "ext_data_range", lambda: client.ext_data_range("test_indicator", TEST_STOCK, "20260101", "20260601"))

# get_ext_all_data: 已被QMT官方删除，应返回错误提示
assert_test(results, "get_ext_all_data(deleted)", lambda: client.get_ext_all_data("test", TEST_STOCK))

# ============================================================
# 因子
# ============================================================
print("\n========== 因子 ==========")
# get_factor_value/get_factor_rank 需要有效的因子名且依赖handlebar上下文
# 以下测试使用假因子名，仅验证接口不崩溃
assert_test(results, "get_factor_value", lambda: client.get_factor_value("alpha1", TEST_STOCK))
assert_test(results, "get_factor_rank", lambda: client.get_factor_rank("alpha1", TEST_STOCK))

# ============================================================
# 公式 + 篮子
# ============================================================
print("\n========== 公式 + 篮子 ==========")
# call_formula: 调用VBA组合模型（需要有效公式名，预期会失败但验证接口不崩溃）
assert_test(results, "call_formula", lambda: client.call_formula("test_formula", []))
assert_test(results, "load_stk_list", lambda: client.load_stk_list("", ""))
assert_test(results, "load_stk_vol_list", lambda: client.load_stk_vol_list("", ""))
assert_test(results, "get_basket", lambda: client.get_basket("default"))
assert_test(results, "set_basket", lambda: client.set_basket("test_basket", [TEST_STOCK]))

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

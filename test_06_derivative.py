# -*- coding: utf-8 -*-
"""
测试6: 期权/期货/BSM/指数成份股
独立运行: python test_06_derivative.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF, TEST_INDEX, TEST_OPTION
)

setup_logging("test_06_derivative")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# 期权数据
# ============================================================
print("\n========== 期权数据 ==========")
assert_test(results, "get_option_detail", lambda: client.get_option_detail("10003720"))
assert_test(results, "get_option_detail_data", lambda: client.get_option_detail_data("10003720"))
assert_test(results, "get_option_list", lambda: client.get_option_list("510050.SH"))
assert_test(results, "get_option_iv", lambda: client.get_option_iv("10003720"))
assert_test(results, "get_option_undl_data", lambda: client.get_option_undl_data("510050"))
assert_test(results, "get_option_subject_position", lambda: client.get_option_subject_position("stock"))
assert_test(results, "get_comb_option", lambda: client.get_comb_option("stock"))

# ============================================================
# 期货数据
# ============================================================
print("\n========== 期货数据 ==========")
assert_test(results, "get_contract_multiplier", lambda: client.get_contract_multiplier("IF"))
assert_test(results, "get_main_contract", lambda: client.get_main_contract("CU"))
assert_test(results, "get_contract_expire_date", lambda: client.get_contract_expire_date("IF2501"))
assert_test(results, "get_his_contract_list", lambda: client.get_his_contract_list("IF"))
assert_test(results, "get_all_subscription", lambda: client.get_all_subscription())

# ============================================================
# BSM定价
# ============================================================
print("\n========== BSM定价 ==========")
assert_test(results, "bsm_price", lambda: client.bsm_price("C", 2.5, 2.5, 0.03, 0.2, 30, 0), [
    (("price",), lambda v: v is not None and v > 0, "BSM价格>0"),
])
assert_test(results, "bsm_iv", lambda: client.bsm_iv("C", 2.5, 2.5, 0.1, 0.03, 30, 0), [
    (("iv",), lambda v: v is not None and v > 0, "隐含波动率>0"),
])

# ============================================================
# 指数成份股
# ============================================================
print("\n========== 指数成份股 ==========")
assert_test(results, "get_sector", lambda: client.get_sector(TEST_INDEX), [
    (("stocks",), lambda v: isinstance(v, list) and len(v) > 0, "指数成份股列表非空"),
])

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

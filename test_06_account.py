# -*- coding: utf-8 -*-
"""
测试6: 账户/订单查询
独立运行: python test_06_account.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient
)

setup_logging("test_06_account")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

print("\n========== 账户/订单查询 ==========")
assert_test(results, "get_trade_detail_data_position", lambda: client.get_trade_detail_data("stock", "position"), [
    (("data",), lambda v: isinstance(v, list), "持仓数据为列表"),
])
assert_test(results, "get_trade_detail_data_account", lambda: client.get_trade_detail_data("stock", "account"), [
    (("data",), lambda v: isinstance(v, list) and len(v) > 0, "账户数据非空"),
])
assert_test(results, "get_trade_detail_data_order", lambda: client.get_trade_detail_data("stock", "order"))
assert_test(results, "get_trade_detail_data_deal", lambda: client.get_trade_detail_data("stock", "deal"))
assert_test(results, "get_last_order_id", lambda: client.get_last_order_id(), [
    (("last_order_id",), lambda v: v is not None, "返回值非空"),
])
assert_test(results, "get_smart_algo_param", lambda: client.get_smart_algo_param(["VWAP"]), [
    (("data", "VWAP"), lambda v: isinstance(v, list) and len(v) > 0, "VWAP参数列表非空"),
])
assert_test(results, "get_value_by_order_id", lambda: client.get_value_by_order_id("12345"))
assert_test(results, "can_cancel_order", lambda: client.can_cancel_order("12345"))
assert_test(results, "get_debt_contract", lambda: client.get_debt_contract())
assert_test(results, "get_assure_contract", lambda: client.get_assure_contract())
assert_test(results, "get_enable_short_contract", lambda: client.get_enable_short_contract())
assert_test(results, "get_ipo_data", lambda: client.get_ipo_data())
assert_test(results, "get_new_purchase_limit", lambda: client.get_new_purchase_limit())
assert_test(results, "query_credit_account", lambda: client.query_credit_account())
assert_test(results, "query_credit_opvolume", lambda: client.query_credit_opvolume())

ok = print_summary(results)
sys.exit(0 if ok else 1)

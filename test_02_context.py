# -*- coding: utf-8 -*-
"""
测试2: ContextInfo 属性
独立运行: python test_02_context.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient
)

setup_logging("test_02_context")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

print("\n========== ContextInfo 属性 ==========")
assert_test(results, "get_context_period", lambda: client.get_context_period(), [
    (("period",), lambda v: v is not None and len(str(v)) > 0, "period非空"),
])
assert_test(results, "get_context_barpos", lambda: client.get_context_barpos(), [
    (("barpos",), lambda v: v is not None, "barpos非空"),
])
assert_test(results, "get_context_stockcode", lambda: client.get_context_stockcode(), [
    (("stockcode",), lambda v: v is not None and len(str(v)) > 0, "stockcode非空"),
])
assert_test(results, "get_context_market", lambda: client.get_context_market(), [
    (("market",), lambda v: v in ("SH", "SZ", "IF", "DL"), "market为有效交易所"),
])
assert_test(results, "get_context_dividend_type", lambda: client.get_context_dividend_type(), [
    (("dividend_type",), lambda v: v in ("front_ratio", "back_ratio", "front", "back", "follow"), "dividend_type有效值"),
])

ok = print_summary(results)
sys.exit(0 if ok else 1)

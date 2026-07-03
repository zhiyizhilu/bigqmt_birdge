# -*- coding: utf-8 -*-
"""
测试2: ContextInfo 属性 + 设置
独立运行: python test_02_context.py
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF
)

setup_logging("test_02_context")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# ContextInfo 只读属性
# ============================================================
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

# ============================================================
# 手续费/滑点 获取与设置
# ============================================================
print("\n========== 手续费/滑点 ==========")
assert_test(results, "get_commission", lambda: client.get_commission(), [
    (("commission",), lambda v: v is not None, "手续费不为None"),
])
assert_test(results, "get_slippage", lambda: client.get_slippage(), [
    (("slippage",), lambda v: v is not None, "滑点不为None"),
])
# set_commission: 设置手续费模式（0=按比例, 1=按固定金额）
assert_test(results, "set_commission", lambda: client.set_commission(0), [
    (("status",), lambda v: v == "success", "设置成功"),
])
# set_slippage: 设置滑点（0=不滑点, 1=按比例滑点）
assert_test(results, "set_slippage", lambda: client.set_slippage(0), [
    (("status",), lambda v: v == "success", "设置成功"),
])

# get_net_value: 获取净值（依赖handlebar上下文，可能返回0或None）
assert_test(results, "get_net_value", lambda: client.get_net_value(0))

# ============================================================
# Universe / Account 设置
# ============================================================
print("\n========== Universe/Account 设置 ==========")
assert_test(results, "set_universe", lambda: client.set_universe([TEST_ETF]))
assert_test(results, "set_account", lambda: client.set_account("stock"))

ok = print_summary(results)
sys.exit(0 if ok else 1)

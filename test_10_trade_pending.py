# -*- coding: utf-8 -*-
"""
测试10: 交易 - Phase1 挂单→验证→撤单
委托价格远离现价，不会成交
独立运行: python test_10_trade_pending.py [--yes]
"""
import json
import sys
import time
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TRADE_STOCK, PRICE_OFFSET, GAP_OFFSET, is_trading_hours,
    confirm_auto, get_current_price, wait,
    get_active_orders, assert_order_exists, assert_no_active_orders
)

setup_logging("test_10_trade_pending")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

AUTO_YES = "--yes" in sys.argv
_confirm = lambda msg: confirm_auto(msg, AUTO_YES)

if not is_trading_hours():
    print("  ⚠️  当前不在交易时段，委托/撤单验证可能不生效")

# 获取现价
current_price = get_current_price(client)
if not current_price:
    print("  错误：无法获取 {} 现价，请确认QMT服务已启动".format(TRADE_STOCK))
    sys.exit(1)

buy_pending_price = round(current_price - GAP_OFFSET, 3)
sell_pending_price = round(current_price + GAP_OFFSET, 3)
print("  现价: {:.3f}, 买入挂单价: {:.3f}, 卖出挂单价: {:.3f}".format(
    current_price, buy_pending_price, sell_pending_price))

# ============================================================
# Phase 1: 挂单→验证→撤单
# ============================================================
print("\n========== Phase 1: 挂单→验证→撤单 ==========")
print("  委托价格远离现价，不会成交")

# 先清理残留
assert_test(results, "cancel_all_orders(清理残留)", lambda: client.cancel_all_orders())
wait(1)

# buy_stock 低于现价买入
assert_test(results, "buy_stock(挂单)", lambda: client.buy_stock(
    TRADE_STOCK, buy_pending_price, 100, pr_type=11),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
assert_order_exists(results, client, "buy_stock", TRADE_STOCK)

# sell_stock 高于现价卖出
assert_test(results, "sell_stock(挂单)", lambda: client.sell_stock(
    TRADE_STOCK, sell_pending_price, 100, pr_type=11),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
assert_order_exists(results, client, "sell_stock", TRADE_STOCK)

# passorder 通用下单
assert_test(results, "passorder(挂单)", lambda: client.passorder(
    0, 1101, TRADE_STOCK, 11, buy_pending_price, 100),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
assert_order_exists(results, client, "passorder", TRADE_STOCK)

wait(1)

# 获取真实order_id用于撤单测试
active_orders = get_active_orders(client, TRADE_STOCK)
real_order_id = None
if active_orders:
    real_order_id = active_orders[0].get("m_strOrderSysID") or active_orders[0].get("order_sys_id")
    print("  当前活跃委托: {} 笔, 首笔ID: {}".format(len(active_orders), real_order_id))
else:
    print("  警告：无活跃委托，撤单测试将使用fake_id")

# cancel_order_by_id
if real_order_id:
    assert_test(results, "cancel_order_by_id(真实ID)", lambda: client.cancel_order_by_id(real_order_id),
        [(("status",), lambda v: v == "success", "status=success")],
        dangerous=True, confirm_func=_confirm)
else:
    assert_test(results, "cancel_order_by_id(fake_id)", lambda: client.cancel_order_by_id("fake_id_test"))

wait(1)

# cancel_order 按股票撤单
assert_test(results, "cancel_order(按股票撤单)", lambda: client.cancel_order(TRADE_STOCK, 100),
    dangerous=True, confirm_func=_confirm)
wait(1)

# cancel_all_orders 一键全撤
assert_test(results, "cancel_all_orders(一键全撤)", lambda: client.cancel_all_orders(),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
wait(1)

# 断言：撤单后无残留
assert_no_active_orders(results, client, TRADE_STOCK, "Phase1撤单验证")

ok = print_summary(results)
sys.exit(0 if ok else 1)

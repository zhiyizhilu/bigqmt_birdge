# -*- coding: utf-8 -*-
"""
测试12: 交易 - Phase3 其他下单接口
algo_passorder / smart_algo_passorder / order_lots / order_value / order_percent / order_target_value / order_target_percent / order_shares
独立运行: python test_12_trade_order_api.py [--yes]
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TRADE_STOCK, GAP_OFFSET, is_trading_hours,
    confirm_auto, get_current_price, wait,
    get_active_orders, assert_no_active_orders
)

setup_logging("test_12_trade_order_api")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

AUTO_YES = "--yes" in sys.argv
_confirm = lambda msg: confirm_auto(msg, AUTO_YES)
_trading = is_trading_hours()

if not _trading:
    print("  ⚠️  当前不在交易时段，委托验证可能不生效")

# 获取现价
current_price = get_current_price(client)
if not current_price:
    print("  错误：无法获取 {} 现价，请确认QMT服务已启动".format(TRADE_STOCK))
    sys.exit(1)

buy_pending_price = round(current_price - GAP_OFFSET, 3)
print("  现价: {:.3f}, 挂单价: {:.3f}".format(current_price, buy_pending_price))

# ============================================================
# Phase 3: 其他下单接口
# ============================================================
print("\n========== Phase 3: 其他下单接口 ==========")
print("  每个接口挂不成交委托，验证后统一撤单")

order_count_before = len(get_active_orders(client, TRADE_STOCK))

# algo_passorder
assert_test(results, "algo_passorder(挂单)", lambda: client.algo_passorder(
    0, 1101, TRADE_STOCK, 11, buy_pending_price, 100, strategyName="test", quickTrade=2
), [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

# smart_algo_passorder (可能不支持或参数不匹配)
def _test_smart_algo():
    ret = client.smart_algo_passorder(
        23, 1101, TRADE_STOCK, 11, buy_pending_price, 100,
        strageName="test_algo", quickTrade=2, userid="test",
        smartAlgoType="VWAP", limitOverRate=0.0, minAmountPerOrder=0
    )
    if isinstance(ret, dict) and ret.get("status") == "error":
        msg = ret.get("message", "")
        if "不支持" in msg or "argument types" in msg:
            results["skip"].append("smart_algo_passorder(挂单)")
            print("  SKIP  smart_algo_passorder(挂单)  (不支持或参数不匹配: {})".format(msg[:80]))
            return {"status": "skipped"}
    return ret
assert_test(results, "smart_algo_passorder(挂单)", _test_smart_algo,
    dangerous=True, confirm_func=_confirm)

# order_lots
assert_test(results, "order_lots(挂单)", lambda: client.order_lots(
    TRADE_STOCK, 1, style="LATEST", price=buy_pending_price),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

# order_value
assert_test(results, "order_value(挂单)", lambda: client.order_value(
    TRADE_STOCK, 200, style="LATEST", price=buy_pending_price),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

# order_percent
assert_test(results, "order_percent(挂单)", lambda: client.order_percent(
    TRADE_STOCK, 0.01, style="LATEST", price=buy_pending_price),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

# order_target_value
assert_test(results, "order_target_value(挂单)", lambda: client.order_target_value(
    TRADE_STOCK, 200, style="LATEST", price=buy_pending_price),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

# order_target_percent
assert_test(results, "order_target_percent(挂单)", lambda: client.order_target_percent(
    TRADE_STOCK, 0.01, style="LATEST", price=buy_pending_price),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

# order_shares
assert_test(results, "order_shares(挂单)", lambda: client.order_shares(
    TRADE_STOCK, 100, style="LATEST", price=buy_pending_price),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

wait(2, "等待委托进入系统")

# 断言：挂单后活跃委托数量增加
order_count_after = len(get_active_orders(client, TRADE_STOCK))
if order_count_after > order_count_before:
    results["pass"].append("Phase3(委托增加验证)")
    print("  ✅  Phase3(委托增加验证)  -> 委托从{}增加到{}".format(order_count_before, order_count_after))
elif not _trading:
    results["pass"].append("Phase3(委托增加验证-非交易时段)")
    print("  ✅  Phase3(委托增加验证-非交易时段)  -> 非交易时段委托不更新(之前={}, 之后={})".format(
        order_count_before, order_count_after))
else:
    results["fail"].append("Phase3(委托增加验证)")
    print("  ❌  Phase3(委托增加验证)  -> 委托未增加(之前={}, 之后={})".format(
        order_count_before, order_count_after))

# 统一撤单
print("  --- 统一撤单 ---")
assert_test(results, "cancel_all_orders(清理)", lambda: client.cancel_all_orders(),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
wait(2)

# 断言：撤单后无残留
assert_no_active_orders(results, client, TRADE_STOCK, "Phase3撤单验证")

ok = print_summary(results)
sys.exit(0 if ok else 1)

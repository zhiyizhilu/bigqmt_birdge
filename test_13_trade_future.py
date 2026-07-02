# -*- coding: utf-8 -*-
"""
测试13: 交易 - Phase4 期货交易
期货接口若无期货账户，下单会废单
独立运行: python test_13_trade_future.py [--yes]
"""
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    FUTURE_STOCK, is_trading_hours, confirm_auto, get_current_price,
    wait, get_active_orders
)

setup_logging("test_13_trade_future")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

AUTO_YES = "--yes" in sys.argv
_confirm = lambda msg: confirm_auto(msg, AUTO_YES)

if not is_trading_hours():
    print("  ⚠️  当前不在交易时段，期货委托验证可能不生效")

# ============================================================
# Phase 4: 期货交易
# ============================================================
print("\n========== Phase 4: 期货交易 ==========")
print("  期货接口若无期货账户，下单会废单")

# 获取期货价格
future_price = None
try:
    tick = client.get_full_tick(FUTURE_STOCK)
    if isinstance(tick, dict) and FUTURE_STOCK in tick:
        future_price = tick[FUTURE_STOCK].get("lastPrice", 0)
except Exception:
    pass
if not future_price:
    future_price = 3500.0
fp_low = round(future_price * 0.95, 1)
fp_high = round(future_price * 1.05, 1)
print("  期货价格: {} (或默认3500), 买入挂单: {}, 卖出挂单: {}".format(future_price, fp_low, fp_high))

assert_test(results, "buy_open(挂单)", lambda: client.buy_open(
    FUTURE_STOCK, 1, style="LATEST", price=fp_low),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
assert_test(results, "sell_open(挂单)", lambda: client.sell_open(
    FUTURE_STOCK, 1, style="LATEST", price=fp_high),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)

wait(2)

# 期货委托验证
future_active = get_active_orders(client)
if future_active:
    results["pass"].append("期货(委托验证)")
    print("  ✅  期货(委托验证)  -> 有{}笔活跃委托".format(len(future_active)))
else:
    results["skip"].append("期货(委托验证)")
    print("  SKIP  期货(委托验证)  -> 无活跃委托（可能无期货账户）")

# 撤单
assert_test(results, "cancel_all_orders(期货清理)", lambda: client.cancel_all_orders(),
    dangerous=True, confirm_func=_confirm)
wait(1)

ok = print_summary(results)
sys.exit(0 if ok else 1)

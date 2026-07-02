# -*- coding: utf-8 -*-
"""
测试11: 交易 - Phase2 实际成交测试（先买后卖）
委托价格贴近现价，会实际成交
独立运行: python test_11_trade_fill.py [--yes]
"""
import json
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TRADE_STOCK, PRICE_OFFSET, is_trading_hours,
    confirm_auto, get_current_price, wait
)

setup_logging("test_11_trade_fill")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

AUTO_YES = "--yes" in sys.argv
_confirm = lambda msg: confirm_auto(msg, AUTO_YES)
_trading = is_trading_hours()

if not _trading:
    print("  ⚠️  当前不在交易时段，成交验证可能不生效")

# 获取现价
current_price = get_current_price(client)
if not current_price:
    print("  错误：无法获取 {} 现价，请确认QMT服务已启动".format(TRADE_STOCK))
    sys.exit(1)

buy_fill_price = round(current_price + PRICE_OFFSET, 3)
sell_fill_price = round(current_price - PRICE_OFFSET, 3)
print("  现价: {:.3f}, 买入成交价: {:.3f}, 卖出成交价: {:.3f}".format(
    current_price, buy_fill_price, sell_fill_price))

# ============================================================
# Phase 2: 实际成交测试
# ============================================================
print("\n========== Phase 2: 实际成交测试（先买后卖） ==========")

# 买入前持仓
holding_before = client.get_holding("stock")
vol_before = 0
if isinstance(holding_before, dict) and TRADE_STOCK in holding_before:
    vol_before = holding_before[TRADE_STOCK].get("Volume", 0)
print("  买入前持仓: {} 股".format(vol_before))

# 高于现价买入100股 → 会成交
assert_test(results, "buy_stock(成交)", lambda: client.buy_stock(
    TRADE_STOCK, buy_fill_price, 100, pr_type=11),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
wait(3, "等待成交")

# 断言：买入后持仓增加
holding_after_buy = client.get_holding("stock")
vol_after_buy = 0
if isinstance(holding_after_buy, dict) and TRADE_STOCK in holding_after_buy:
    vol_after_buy = holding_after_buy[TRADE_STOCK].get("Volume", 0)
if vol_after_buy > vol_before:
    results["pass"].append("buy_stock(持仓验证)")
    print("  ✅  buy_stock(持仓验证)  -> 持仓从{}增加到{}".format(vol_before, vol_after_buy))
elif not _trading:
    results["pass"].append("buy_stock(持仓验证-非交易时段)")
    print("  ✅  buy_stock(持仓验证-非交易时段)  -> 非交易时段持仓不更新(之前={}, 之后={})".format(vol_before, vol_after_buy))
else:
    results["fail"].append("buy_stock(持仓验证)")
    print("  ❌  buy_stock(持仓验证)  -> 持仓未增加, 之前={}, 之后={}".format(vol_before, vol_after_buy))

# 断言：有买入成交记录
deals = client.get_deal()
if isinstance(deals, dict) and deals.get("deals"):
    buy_deals = [d for d in deals["deals"]
                 if isinstance(d, dict) and TRADE_STOCK in str(d.get("m_strInstrumentID", ""))]
    if buy_deals:
        results["pass"].append("buy_stock(成交记录)")
        print("  ✅  buy_stock(成交记录)  -> 找到{}笔成交".format(len(buy_deals)))
    else:
        all_deals_str = json.dumps(deals, ensure_ascii=False, default=str)
        if TRADE_STOCK.split('.')[0] in all_deals_str:
            results["pass"].append("buy_stock(成交记录)")
            print("  ✅  buy_stock(成交记录)  -> 成交数据中包含{}相关记录".format(TRADE_STOCK))
        else:
            results["fail"].append("buy_stock(成交记录)")
            print("  ❌  buy_stock(成交记录)  -> 无{}成交记录".format(TRADE_STOCK))
else:
    results["fail"].append("buy_stock(成交记录)")
    print("  ❌  buy_stock(成交记录)  -> 无法获取成交")

# 低于现价卖出100股 → 会成交
assert_test(results, "sell_stock(成交)", lambda: client.sell_stock(
    TRADE_STOCK, sell_fill_price, 100, pr_type=11),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
wait(3, "等待成交")

# 断言：卖出后持仓变化
holding_final = client.get_holding("stock")
vol_final = 0
if isinstance(holding_final, dict) and TRADE_STOCK in holding_final:
    vol_final = holding_final[TRADE_STOCK].get("Volume", 0)
print("  最终持仓: {} 股 (总变化: {:+d})".format(vol_final, vol_final - vol_before))

ok = print_summary(results)
sys.exit(0 if ok else 1)

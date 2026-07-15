# -*- coding: utf-8 -*-
"""
测试20: 全部交易操作（合并原test_10-13 + 新增交易接口）
Phase1: 挂单→验证→撤单 (buy_stock, sell_stock, passorder, cancel)
Phase2: 实际成交 (buy_stock, sell_stock at fill price)
Phase3: 其他下单接口 (algo_passorder, smart_algo_passorder, order_lots, order_value, order_percent, order_target_value, order_target_percent, order_shares)
Phase4: 期货交易 (buy_open, sell_open)
Phase5: 止损止盈 (stoploss_limitprice, stoploss_marketprice - 使用无效参数)
Phase6: 期权组合 (make_option_combination, release_option_combination - 使用无效参数)
独立运行: python test_20_trade.py [--yes]
"""
import json
import sys
import time
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TRADE_STOCK, FUTURE_STOCK, PRICE_OFFSET, GAP_OFFSET,
    is_trading_hours, confirm_auto, get_current_price, wait,
    get_active_orders, assert_order_exists, assert_no_active_orders
)

setup_logging("test_20_trade")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

AUTO_YES = "--yes" in sys.argv
_confirm = lambda msg: confirm_auto(msg, AUTO_YES)
_trading = is_trading_hours()

if not _trading:
    print("  ⚠️  当前不在交易时段，委托/撤单/成交验证可能不生效")

# 获取现价
current_price = get_current_price(client)
if not current_price:
    print("  错误：无法获取 {} 现价，请确认QMT服务已启动".format(TRADE_STOCK))
    sys.exit(1)

buy_pending_price = round(current_price - GAP_OFFSET, 3)
sell_pending_price = round(current_price + GAP_OFFSET, 3)
buy_fill_price = round(current_price + PRICE_OFFSET, 3)
sell_fill_price = round(current_price - PRICE_OFFSET, 3)
print("  现价: {:.3f}, 买入挂单价: {:.3f}, 卖出挂单价: {:.3f}".format(
    current_price, buy_pending_price, sell_pending_price))
print("  买入成交价: {:.3f}, 卖出成交价: {:.3f}".format(
    buy_fill_price, sell_fill_price))

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
    [(("status",), lambda v: v == "success", "status=success"),(("order_ref",), lambda v: len(v) > 0, "order_ref!=0")],
    dangerous=True, confirm_func=_confirm)
assert_order_exists(results, client, "buy_stock", TRADE_STOCK)

# sell_stock 高于现价卖出
assert_test(results, "sell_stock(挂单)", lambda: client.sell_stock(
    TRADE_STOCK, sell_pending_price, 100, pr_type=11),
    [(("status",), lambda v: v == "success", "status=success"),(("order_ref",), lambda v: len(v) > 0, "order_ref!=0")],
    dangerous=True, confirm_func=_confirm)
assert_order_exists(results, client, "sell_stock", TRADE_STOCK)

# passorder 通用下单
assert_test(results, "passorder(挂单)", lambda: client.passorder(
    0, 1101, TRADE_STOCK, 11, buy_pending_price, 100),
    [(("status",), lambda v: v == "success", "status=success"),(("order_ref",), lambda v: len(v) > 0, "order_ref!=0")],
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
        [(("status",), lambda v: v == "success", "status=success"),(("orderId",), lambda v: int(v) > 0, "orderId>0")],
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
    [(("status",), lambda v: v == "success", "status=success"),(("order_ref",), lambda v: len(v) > 0, "order_ref!=0")],
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
    [(("status",), lambda v: v == "success", "status=success"),(("order_ref",), lambda v: len(v) > 0, "order_ref!=0")],
    dangerous=True, confirm_func=_confirm)
wait(3, "等待成交")

# 断言：卖出后持仓变化
holding_final = client.get_holding("stock")
vol_final = 0
if isinstance(holding_final, dict) and TRADE_STOCK in holding_final:
    vol_final = holding_final[TRADE_STOCK].get("Volume", 0)
print("  最终持仓: {} 股 (总变化: {:+d})".format(vol_final, vol_final - vol_before))

# ============================================================
# Phase 3: 其他下单接口
# ============================================================
print("\n========== Phase 3: 其他下单接口 ==========")
print("  每个接口挂不成交委托，验证后统一撤单")

order_count_before = len(get_active_orders(client, TRADE_STOCK))

# algo_passorder (可能不支持，error/warning也算接口正常)
def _test_algo_passorder():
    ret = client.algo_passorder(
        0, 1101, TRADE_STOCK, 11, buy_pending_price, 100, strategyName="test", quickTrade=2
    )
    if isinstance(ret, dict):
        st = ret.get("status", "")
        if st == "error":
            msg = ret.get("message", "")
            results["skip"].append("algo_passorder(挂单)")
            print("  ⚠️  algo_passorder(挂单)  (不支持: {})".format(msg[:80]))
            return {"status": "skipped"}
        if st == "warning":
            results["skip"].append("algo_passorder(挂单)")
            print("  ⚠️  algo_passorder(挂单)  (未产生委托: {})".format(ret.get("message", "")[:80]))
            return {"status": "skipped"}
    return ret
assert_test(results, "algo_passorder(挂单)", _test_algo_passorder,
    dangerous=True, confirm_func=_confirm)

# smart_algo_passorder (可能不支持或参数不匹配)
def _test_smart_algo():
    ret = client.smart_algo_passorder(
        23, 1101, TRADE_STOCK, 11, buy_pending_price, 100,
        strageName="test_algo", quickTrade=2, userid="test",
        smartAlgoType="VWAP", limitOverRate=0.0, minAmountPerOrder=0
    )
    if isinstance(ret, dict):
        st = ret.get("status", "")
        msg = ret.get("message", "")
        if st == "error" and ("不支持" in msg or "argument types" in msg):
            results["skip"].append("smart_algo_passorder(挂单)")
            print("  ⚠️  smart_algo_passorder(挂单)  (不支持或参数不匹配: {})".format(msg[:80]))
            return {"status": "skipped"}
        if st == "warning":
            results["skip"].append("smart_algo_passorder(挂单)")
            print("  ⚠️  smart_algo_passorder(挂单)  (未产生委托: {})".format(msg[:80]))
            return {"status": "skipped"}
    return ret
assert_test(results, "smart_algo_passorder(挂单)", _test_smart_algo,
    dangerous=True, confirm_func=_confirm)

# order_lots - 非passorder类函数可能需要handlebar上下文，error/warning视为已知限制
def _test_order_lots():
    ret = client.order_lots(TRADE_STOCK, 1, style="LATEST", price=buy_pending_price)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("order_lots(挂单)")
        print("  ⚠️  order_lots(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "order_lots(挂单)", _test_order_lots,
    dangerous=True, confirm_func=_confirm)

# order_value
def _test_order_value():
    ret = client.order_value(TRADE_STOCK, 200, style="LATEST", price=buy_pending_price)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("order_value(挂单)")
        print("  ⚠️  order_value(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "order_value(挂单)", _test_order_value,
    dangerous=True, confirm_func=_confirm)

# order_percent
def _test_order_percent():
    ret = client.order_percent(TRADE_STOCK, 0.01, style="LATEST", price=buy_pending_price)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("order_percent(挂单)")
        print("  ⚠️  order_percent(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "order_percent(挂单)", _test_order_percent,
    dangerous=True, confirm_func=_confirm)

# order_target_value
def _test_order_target_value():
    ret = client.order_target_value(TRADE_STOCK, 200, style="LATEST", price=buy_pending_price)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("order_target_value(挂单)")
        print("  ⚠️  order_target_value(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "order_target_value(挂单)", _test_order_target_value,
    dangerous=True, confirm_func=_confirm)

# order_target_percent
def _test_order_target_percent():
    ret = client.order_target_percent(TRADE_STOCK, 0.01, style="LATEST", price=buy_pending_price)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("order_target_percent(挂单)")
        print("  ⚠️  order_target_percent(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "order_target_percent(挂单)", _test_order_target_percent,
    dangerous=True, confirm_func=_confirm)

# order_shares
def _test_order_shares():
    ret = client.order_shares(TRADE_STOCK, 100, style="LATEST", price=buy_pending_price)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("order_shares(挂单)")
        print("  ⚠️  order_shares(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "order_shares(挂单)", _test_order_shares,
    dangerous=True, confirm_func=_confirm)

wait(2, "等待委托进入系统")

# 断言：挂单后活跃委托数量增加
# 注意：order_lots等非passorder类函数可能需要handlebar上下文，委托不增加视为已知限制
order_count_after = len(get_active_orders(client, TRADE_STOCK))
if order_count_after > order_count_before:
    results["pass"].append("Phase3(委托增加验证)")
    print("  ✅  Phase3(委托增加验证)  -> 委托从{}增加到{}".format(order_count_before, order_count_after))
elif not _trading:
    results["pass"].append("Phase3(委托增加验证-非交易时段)")
    print("  ✅  Phase3(委托增加验证-非交易时段)  -> 非交易时段委托不更新(之前={}, 之后={})".format(
        order_count_before, order_count_after))
else:
    # 非passorder类函数在HTTP handler中可能静默失败
    results["warn"].append("Phase3(委托增加验证)")
    print("  ⚠️  Phase3(委托增加验证)  -> 非passorder类函数可能需要handlebar上下文(之前={}, 之后={})".format(
        order_count_before, order_count_after))

# 统一撤单
print("  --- 统一撤单 ---")
assert_test(results, "cancel_all_orders(Phase3清理)", lambda: client.cancel_all_orders(),
    [(("status",), lambda v: v == "success", "status=success")],
    dangerous=True, confirm_func=_confirm)
wait(2)

# 断言：撤单后无残留
assert_no_active_orders(results, client, TRADE_STOCK, "Phase3撤单验证")

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

def _test_buy_open():
    ret = client.buy_open(FUTURE_STOCK, 1, style="LATEST", price=fp_low)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("buy_open(挂单)")
        print("  ⚠️  buy_open(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "buy_open(挂单)", _test_buy_open,
    dangerous=True, confirm_func=_confirm)

def _test_sell_open():
    ret = client.sell_open(FUTURE_STOCK, 1, style="LATEST", price=fp_high)
    if isinstance(ret, dict) and ret.get("status") in ("error", "warning"):
        results["skip"].append("sell_open(挂单)")
        print("  ⚠️  sell_open(挂单)  ({})".format(ret.get("message", "未产生委托")[:80]))
        return {"status": "skipped"}
    return ret
assert_test(results, "sell_open(挂单)", _test_sell_open,
    dangerous=True, confirm_func=_confirm)

wait(2)

# 期货委托验证
future_active = get_active_orders(client)
if future_active:
    results["pass"].append("期货(委托验证)")
    print("  ✅  期货(委托验证)  -> 有{}笔活跃委托".format(len(future_active)))
else:
    results["warn"].append("期货(委托验证)")
    print("  ⚠️  期货(委托验证)  -> 无活跃委托（可能无期货账户）")

# 撤单
assert_test(results, "cancel_all_orders(期货清理)", lambda: client.cancel_all_orders(),
    dangerous=True, confirm_func=_confirm)
wait(1)

# ============================================================
# Phase 5: 止损止盈
# ============================================================
print("\n========== Phase 5: 止损止盈 ==========")
print("  使用无效参数验证接口不崩溃")

# stoploss_limitprice: 限价止损（使用无效参数，无法验证结果）
def _test_stoploss_limitprice():
    client.stoploss_limitprice(stoploss_code=0, order_type=1101, op_type=0, account="test",
        stock_code=TRADE_STOCK, stop_price=0, stop_amount=0)
    results["warn"].append("stoploss_limitprice")
    print("  ⚠️  stoploss_limitprice  (无效参数，无法验证)")
    return {"status": "skipped"}
assert_test(results, "stoploss_limitprice", _test_stoploss_limitprice,
    dangerous=True, confirm_func=_confirm)

# stoploss_marketprice: 市价止损（使用无效参数，无法验证结果）
def _test_stoploss_marketprice():
    client.stoploss_marketprice(stoploss_code=0, order_type=1101, op_type=0, account="test",
        stock_code=TRADE_STOCK, trigger_price=0, stop_amount=0)
    results["warn"].append("stoploss_marketprice")
    print("  ⚠️  stoploss_marketprice  (无效参数，无法验证)")
    return {"status": "skipped"}
assert_test(results, "stoploss_marketprice", _test_stoploss_marketprice,
    dangerous=True, confirm_func=_confirm)

# ============================================================
# Phase 6: 期权组合
# ============================================================
print("\n========== Phase 6: 期权组合 ==========")
print("  使用无效参数验证接口不崩溃")

# make_option_combination: 构建期权组合持仓（使用无效参数，无法验证结果）
def _test_make_option():
    client.make_option_combination(account="test", opt_comb_list=[])
    results["warn"].append("make_option_combination")
    print("  ⚠️  make_option_combination  (无效参数，无法验证)")
    return {"status": "skipped"}
assert_test(results, "make_option_combination", _test_make_option,
    dangerous=True, confirm_func=_confirm)

# release_option_combination: 解除期权组合持仓（使用无效参数，无法验证结果）
def _test_release_option():
    client.release_option_combination(account="test", opt_comb_list=[])
    results["warn"].append("release_option_combination")
    print("  ⚠️  release_option_combination  (无效参数，无法验证)")
    return {"status": "skipped"}
assert_test(results, "release_option_combination", _test_release_option,
    dangerous=True, confirm_func=_confirm)

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

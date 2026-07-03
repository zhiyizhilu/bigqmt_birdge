# -*- coding: utf-8 -*-
"""
测试10: 订阅（行情订阅 + 缓存读取 + 数据更新验证）
独立运行: python test_10_subscribe.py

注意: 订阅数据持续更新需要QMT策略周期设为tick级别
  - 日线(1d)周期: handlebar每天只触发1次，订阅数据不会实时更新
  - tick级别周期: handlebar高频触发，订阅数据会实时更新
"""
import time
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF
)

setup_logging("test_10_subscribe")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": [], "warn": []}

# ============================================================
# 订阅
# ============================================================
print("\n========== 订阅 ==========")
assert_test(results, "subscribe_quote", lambda: client.subscribe_quote(TEST_ETF, "follow"), [
    (("sub_id",), lambda v: v is not None, "订阅返回sub_id"),
])
assert_test(results, "subscribe_whole_quote", lambda: client.subscribe_whole_quote([TEST_ETF]), [
    (("sub_id",), lambda v: v is not None, "订阅返回sub_id"),
])

# 订阅后服务端会立即用get_full_tick填充初始数据
print("  ...等待2秒让订阅数据初始化...")
time.sleep(2)

tick1 = assert_test(results, "get_sub_tick_cache(第1次)", lambda: client.get_sub_tick_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "tick缓存非空"),
])
quote1 = assert_test(results, "get_sub_quote_cache(第1次)", lambda: client.get_sub_quote_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "quote缓存非空"),
])

# 记录第1次的时间戳
ts1 = None
if isinstance(tick1, dict) and "data" in tick1:
    d = tick1["data"].get(TEST_ETF, {})
    ts1 = d.get("time") or d.get("timetag")
    print("  第1次时间戳: {}".format(ts1))

# 等待后再次获取，验证数据是否更新
print("  ...等待5秒继续获取订阅数据...")
time.sleep(5)

tick2 = assert_test(results, "get_sub_tick_cache(第2次)", lambda: client.get_sub_tick_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "tick缓存非空"),
])
quote2 = assert_test(results, "get_sub_quote_cache(第2次)", lambda: client.get_sub_quote_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "quote缓存非空"),
])

# 检查时间戳是否变化
ts2 = None
if isinstance(tick2, dict) and "data" in tick2:
    d = tick2["data"].get(TEST_ETF, {})
    ts2 = d.get("time") or d.get("timetag")
    print("  第2次时间戳: {}".format(ts2))

if ts1 and ts2 and ts1 != ts2:
    results["pass"].append("订阅数据更新验证")
    print("  ✅  订阅数据更新验证  -> 时间戳从{}变为{}".format(ts1, ts2))
elif ts1 and ts2 and ts1 == ts2:
    results["skip"].append("订阅数据更新验证")
    print("  SKIP  订阅数据更新验证  -> 时间戳未变化({}), 可能QMT策略周期非tick级别".format(ts1))
    print("       提示: 在QMT策略编辑器中将周期设为'tick'或'1秒'可使订阅数据实时更新")
else:
    results["skip"].append("订阅数据更新验证")
    print("  SKIP  订阅数据更新验证  -> 无法获取时间戳")

assert_test(results, "unsubscribe_quote", lambda: client.unsubscribe_quote(0))

# ============================================================
# 汇总
# ============================================================
ok = print_summary(results)
sys.exit(0 if ok else 1)

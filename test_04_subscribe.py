# -*- coding: utf-8 -*-
"""
测试4: 订阅（行情订阅 + 缓存读取）
独立运行: python test_04_subscribe.py
"""
import time
import sys
from test_base import (
    setup_logging, assert_test, print_summary, QMTClient,
    TEST_ETF
)

setup_logging("test_04_subscribe")
client = QMTClient()
results = {"pass": [], "fail": [], "skip": []}

print("\n========== 订阅 ==========")
assert_test(results, "subscribe_quote", lambda: client.subscribe_quote(TEST_ETF, "1d"), [
    (("sub_id",), lambda v: v is not None, "订阅返回sub_id"),
])
assert_test(results, "subscribe_whole_quote", lambda: client.subscribe_whole_quote([TEST_ETF]), [
    (("sub_id",), lambda v: v is not None, "订阅返回sub_id"),
])

# 订阅后服务端会立即用get_full_tick填充初始数据
print("  ...等待2秒让订阅数据初始化...")
time.sleep(2)

assert_test(results, "get_sub_tick_cache", lambda: client.get_sub_tick_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "tick缓存非空(订阅时自动填充)"),
])
assert_test(results, "get_sub_quote_cache", lambda: client.get_sub_quote_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "quote缓存非空(订阅时自动填充)"),
])
assert_test(results, "unsubscribe_quote", lambda: client.unsubscribe_quote(0))

ok = print_summary(results)
sys.exit(0 if ok else 1)

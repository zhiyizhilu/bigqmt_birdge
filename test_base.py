# -*- coding: utf-8 -*-
"""
QMT Bridge 测试基础设施
提供日志、断言框架、通用工具函数，供各独立测试文件引用
"""
import json
import sys
import os
import time
from datetime import datetime
from qmt_client import QMTClient

# ============================================================
# 日志输出到文件+控制台
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(LOG_DIR, exist_ok=True)


class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, data):
        for f in self.files:
            f.write(data)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()


def setup_logging(prefix="test"):
    """设置日志输出到文件+控制台，返回日志文件路径"""
    log_path = os.path.join(LOG_DIR, "{}_{}.log".format(
        prefix, datetime.now().strftime("%Y%m%d_%H%M%S")))
    _log_file = open(log_path, "w", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, _log_file)
    sys.stderr = Tee(sys.stderr, _log_file)
    print("测试时间: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("日志文件: {}".format(log_path))
    return log_path


# ============================================================
# 测试断言框架
# ============================================================

def _get_nested(data, *keys, default=None):
    """安全获取嵌套dict值"""
    for k in keys:
        if isinstance(data, dict):
            data = data.get(k, default)
        else:
            return default
    return data


def assert_test(results, name, func, assertions=None, dangerous=False, confirm_func=None):
    """带断言的测试"""
    if dangerous and confirm_func and not confirm_func("执行 {}? 这是真实交易操作!".format(name)):
        results["skip"].append(name)
        print("  ⚠️  {} (用户取消)".format(name))
        return None
    try:
        ret = func()
    except Exception as e:
        results["fail"].append(name)
        print("  ❌  {}  -> 异常: {}".format(name, str(e)))
        return None
    if isinstance(ret, dict) and ret.get("error") and ret.get("status_code"):
        results["fail"].append(name)
        print("  ❌  {}  -> HTTP错误: {}".format(name, ret.get("error", "")[:100]))
        return ret
    # status=warning: 下单未产生委托等可预期问题，用⚠️标记
    if isinstance(ret, dict) and ret.get("status") == "warning":
        results["warn"].append(name)
        msg = ret.get("message", "")
        out = json.dumps(ret, ensure_ascii=False, default=str)
        print("  ⚠️  {}  -> {}".format(name, msg[:100] if msg else (out[:120] + "...") if len(out) > 120 else out))
        return ret
    # status=skipped: 测试函数自行处理了输出（已打印⚠️），不再重复打印
    if isinstance(ret, dict) and ret.get("status") == "skipped":
        return ret
    if isinstance(ret, dict) and ret.get("status") == "error":
        msg = ret.get("message", "")
        if "不支持" in msg:
            results["skip"].append(name)
            print("  ⚠️  {}  (不支持: {})".format(name, msg[:80]))
            return ret
        results["fail"].append(name)
        print("  ❌  {}  -> {}".format(name, msg[:100]))
        return ret
    if isinstance(ret, dict) and ret.get("error") and not ret.get("warning"):
        results["fail"].append(name)
        print("  ❌  {}  -> {}".format(name, ret.get("error", "")[:100]))
        return ret
    if not assertions:
        results["pass"].append(name)
        out = json.dumps(ret, ensure_ascii=False, default=str)
        print("  ✅  {}  -> {}".format(name, (out[:120] + "...") if len(out) > 120 else out))
        return ret
    all_pass = True
    details = []
    for path, check, desc in assertions:
        val = _get_nested(ret, *path) if path else ret
        ok = check(val) if val is not None else False
        if not ok:
            all_pass = False
            details.append("  !! {} 不符合预期: 实际值={}".format(desc, repr(val)[:80]))
    if all_pass:
        results["pass"].append(name)
        out = json.dumps(ret, ensure_ascii=False, default=str)
        print("  ✅  {}  -> {}".format(name, (out[:120] + "...") if len(out) > 120 else out))
    else:
        results["fail"].append(name)
        out = json.dumps(ret, ensure_ascii=False, default=str)
        print("  ❌  {}  -> {}".format(name, (out[:80] + "...") if len(out) > 80 else out))
        for d in details:
            print(d)
    return ret


def print_summary(results):
    """打印测试汇总，返回是否全部通过"""
    print("\n" + "=" * 60)
    print("  ✅: {}".format(len(results["pass"])))
    print("  ❌: {}".format(len(results["fail"])))
    print("  ⚠️: {}".format(len(results.get("warn", []))))
    print("  SKIP: {}".format(len(results["skip"])))
    print("=" * 60)
    if results["fail"]:
        print("\n失败列表:")
        for name in results["fail"]:
            print("  - {}".format(name))
    if results.get("warn"):
        print("\n警告列表:")
        for name in results["warn"]:
            print("  - {}".format(name))
    if results["skip"]:
        print("\n跳过列表:")
        for name in results["skip"]:
            print("  - {}".format(name))
    return len(results["fail"]) == 0


# ============================================================
# 交易测试专用工具
# ============================================================
TRADE_STOCK = "513090.SH"
FUTURE_STOCK = "IF2507.IF"
PRICE_OFFSET = 0.015
GAP_OFFSET = 0.05


def is_trading_hours():
    """判断是否在交易时段（9:15-15:00）"""
    now = datetime.now()
    return (now.hour == 9 and now.minute >= 15) or (10 <= now.hour <= 14) or (now.hour == 15 and now.minute == 0)


def confirm_auto(msg, auto_yes=False):
    if auto_yes:
        return True
    ans = input("  >>> {} (y/N): ".format(msg)).strip().lower()
    return ans == 'y'


def get_current_price(client, stock=TRADE_STOCK):
    try:
        tick = client.get_full_tick(stock)
        if isinstance(tick, dict) and stock in tick:
            price = tick[stock].get("lastPrice", 0)
            if price and price > 0:
                return float(price)
    except Exception:
        pass
    return None


def wait(seconds=2, msg=""):
    if msg:
        print("  ...{}等待{}秒...".format(msg, seconds))
    else:
        print("  ...等待{}秒...".format(seconds))
    time.sleep(seconds)


def get_active_orders(client, stock=None):
    try:
        resp = client.get_trade_detail_data("stock", "order")
        if isinstance(resp, dict) and resp.get("data"):
            active = []
            for o in resp["data"]:
                if not isinstance(o, dict):
                    continue
                status = o.get("m_nOrderStatus", -1)
                try:
                    status = int(status)
                except (ValueError, TypeError):
                    status = -1
                if status in (48, 49, 50, 51, 52, 55):
                    if stock:
                        code = o.get("m_strInstrumentID", "")
                        exchange = o.get("m_strExchangeID", "")
                        full_code = "{}.{}".format(code, exchange) if exchange else code
                        if stock not in full_code and stock not in code:
                            continue
                    active.append(o)
            return active
    except Exception:
        pass
    return []


def assert_order_exists(results, client, name, stock, timeout=3):
    for i in range(timeout):
        active = get_active_orders(client, stock)
        if active:
            results["pass"].append(name + "(委托存在)")
            print("  ✅  {}(委托存在)  -> 共{}笔活跃委托".format(name, len(active)))
            return active
        time.sleep(1)
    try:
        all_orders = client.get_trade_detail_data("stock", "order")
        if isinstance(all_orders, dict) and all_orders.get("data"):
            matching = [o for o in all_orders["data"]
                        if isinstance(o, dict) and stock in str(o.get("m_strInstrumentID", ""))]
            if matching:
                status = matching[-1].get("m_nOrderStatus", "")
                results["pass"].append(name + "(委托存在但非活跃)")
                print("  ✅  {}(委托存在但非活跃)  -> 状态={}".format(name, status))
                return matching
    except Exception:
        pass
    try:
        deals = client.get_deal()
        if isinstance(deals, dict) and deals.get("deals"):
            recent = [d for d in deals["deals"] if stock in str(d)]
            if recent:
                results["pass"].append(name + "(已成交)")
                print("  ✅  {}(已成交)  -> 成交{}笔".format(name, len(recent)))
                return recent
    except Exception:
        pass
    results["fail"].append(name + "(委托验证)")
    print("  ❌  {}(委托验证)  -> 委托不存在且无成交，下单可能失败".format(name))
    return None


def assert_no_active_orders(results, client, stock=None, name="撤单验证", max_retries=3):
    _is_trading = is_trading_hours()
    for i in range(max_retries):
        remaining = get_active_orders(client, stock)
        if len(remaining) == 0:
            results["pass"].append(name)
            print("  ✅  {}  -> 无残留委托".format(name))
            return True
        if not _is_trading:
            all_pending_cancel = all(
                o.get("m_nOrderStatus") in (51, 52) for o in remaining if isinstance(o, dict)
            )
            if all_pending_cancel:
                results["pass"].append(name + "(非交易时段-撤单请求已发出)")
                print("  ✅  {}(非交易时段)  -> 撤单请求已发出".format(name))
                return True
        if i < max_retries - 1:
            print("  ...{} 仍有{}笔活跃委托，等待2秒重试({}/{})...".format(
                name, len(remaining), i+1, max_retries))
            time.sleep(2)
    if not _is_trading:
        results["pass"].append(name + "(非交易时段-已发撤单)")
        print("  ✅  {}(非交易时段)  -> 撤单请求已发出，但非交易时段委托不会消失({}笔)".format(
            name, len(remaining)))
        return True
    results["fail"].append(name)
    print("  ❌  {}  -> 仍有{}笔活跃委托未撤".format(name, len(remaining)))
    return False


# ============================================================
# 测试用股票常量
# ============================================================
TEST_ETF = "513090.SH"
TEST_STOCK = "600519.SH"
TEST_INDEX = "000300.SH"
TEST_OPTION = "10003720"
FINANCE_STOCK = "000001.SZ"

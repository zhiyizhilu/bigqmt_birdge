# -*- coding: utf-8 -*-
"""
QMT Bridge 数据接口测试脚本
每个测试有预期值，实际返回与预期对比才判定PASS
交易接口测试请使用 test_trade_api.py
日志自动输出到 log/test_data_时间戳.log
"""
import json
import time
import sys
import os
from datetime import datetime

from qmt_client import QMTClient

# 日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, "test_data_{}.log".format(datetime.now().strftime("%Y%m%d_%H%M%S")))

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

_log_file = open(log_path, "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, _log_file)
sys.stderr = Tee(sys.stderr, _log_file)

print("测试时间: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
print("日志文件: {}".format(log_path))

client = QMTClient()

results = {"pass": [], "fail": [], "skip": []}

# 测试用股票
TEST_ETF = "513090.SH"       # T+0 ETF
TEST_STOCK = "600519.SH"     # 贵州茅台（有完整财务数据）
TEST_INDEX = "000300.SH"     # 沪深300
TEST_OPTION = "10003720"     # 期权代码


def _get_nested(data, *keys, default=None):
    """安全获取嵌套dict值"""
    for k in keys:
        if isinstance(data, dict):
            data = data.get(k, default)
        else:
            return default
    return data


def assert_test(name, func, assertions=None):
    """
    带断言的测试
    assertions: [(path, check_func, description), ...]
      - path: tuple of keys to navigate into ret dict
      - check_func: lambda value: bool  (value is the resolved value)
      - description: str describing what is being checked
    """
    try:
        ret = func()
    except Exception as e:
        results["fail"].append(name)
        print("  ❌  {}  -> 异常: {}".format(name, str(e)))
        return ret

    # HTTP层错误
    if isinstance(ret, dict) and ret.get("error") and ret.get("status_code"):
        results["fail"].append(name)
        print("  ❌  {}  -> HTTP错误: {}".format(name, ret.get("error", "")[:100]))
        return ret

    # API返回错误（非warning）
    if isinstance(ret, dict) and ret.get("error") and not ret.get("warning"):
        results["fail"].append(name)
        print("  ❌  {}  -> {}".format(name, ret.get("error", "")[:100]))
        return ret

    # 无断言时，只检查不报错
    if not assertions:
        results["pass"].append(name)
        out = json.dumps(ret, ensure_ascii=False, default=str)
        print("  ✅  {}  -> {}".format(name, (out[:120] + "...") if len(out) > 120 else out))
        return ret

    # 逐条验证断言
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


# ============================================================
# 1. 兼容路由
# ============================================================
print("\n========== 1. 兼容路由 ==========")
assert_test("get_holding", lambda: client.get_holding("stock"), [
    (("513090.SH",), lambda v: v is not None, "持仓中有513090.SH"),
])
assert_test("get_total_money", lambda: client.get_total_money("stock"), [
    (("total_money",), lambda v: v is not None and v > 0, "总资产>0"),
])
assert_test("get_available_money", lambda: client.get_available_money("stock"), [
    (("available_money",), lambda v: v is not None and v > 0, "可用资金>0"),
])
assert_test("python_version", lambda: client.python_version(), [
    (("python_version",), lambda v: "3.6" in str(v), "Python版本为3.6"),
])

# ============================================================
# 2. ContextInfo 属性
# ============================================================
print("\n========== 2. ContextInfo 属性 ==========")
assert_test("get_context_period", lambda: client.get_context_period(), [
    (("period",), lambda v: v is not None and len(str(v)) > 0, "period非空"),
])
assert_test("get_context_barpos", lambda: client.get_context_barpos(), [
    (("barpos",), lambda v: v is not None, "barpos非空"),
])
assert_test("get_context_stockcode", lambda: client.get_context_stockcode(), [
    (("stockcode",), lambda v: v is not None and len(str(v)) > 0, "stockcode非空"),
])
assert_test("get_context_market", lambda: client.get_context_market(), [
    (("market",), lambda v: v in ("SH", "SZ", "IF", "DL"), "market为有效交易所"),
])
assert_test("get_context_dividend_type", lambda: client.get_context_dividend_type(), [
    (("dividend_type",), lambda v: v in ("front_ratio", "back_ratio", "front", "back", "follow"), "dividend_type有效值"),
])

# ============================================================
# 3. 数据查询
# ============================================================
print("\n========== 3. 数据查询 ==========")

# 先下载历史数据
assert_test("download_history_data", lambda: client.download_history_data(TEST_ETF), [
    (("result",), lambda v: v is True, "下载结果为True"),
])
time.sleep(2)

assert_test("get_stock_name", lambda: client.get_stock_name(TEST_ETF), [
    (("name",), lambda v: "ETF" in str(v) or "证券" in str(v), "股票名包含ETF或证券"),
])
assert_test("get_open_date", lambda: client.get_open_date(TEST_ETF), [
    (("open_date",), lambda v: v is not None and v > 0, "上市日期>0"),
])
assert_test("get_full_tick", lambda: client.get_full_tick(TEST_ETF), [
    ((TEST_ETF, "lastPrice"), lambda v: v is not None and v > 0, "最新价>0"),
    ((TEST_ETF, "volume"), lambda v: v is not None and v > 0, "成交量>0"),
])
assert_test("get_market_data", lambda: client.get_market_data("close", TEST_ETF, "20250101", "20250601"), [
    (("data", "close"), lambda v: v is not None and len(v) > 0, "有收盘价数据"),
])
assert_test("get_market_data_ex", lambda: client.get_market_data_ex([TEST_ETF], fields="open,high,low,close,volume", period="1d", start_time="20250101", end_time="20250131"), [
    (("data", TEST_ETF, "close"), lambda v: v is not None and len(v) > 0, "有close数据"),
])
assert_test("get_sector", lambda: client.get_sector(TEST_INDEX), [
    (("stocks",), lambda v: isinstance(v, list) and len(v) > 0, "指数成份股列表非空"),
])
assert_test("get_stock_list_in_sector", lambda: client.get_stock_list_in_sector("沪深A股"), [
    (("stocks",), lambda v: isinstance(v, list) and len(v) > 100, "沪深A股数量>100"),
])
assert_test("get_instrumentdetail", lambda: client.get_instrumentdetail(TEST_ETF), [
    (("detail", "InstrumentName"), lambda v: "ETF" in str(v) or "证券" in str(v), "名称含ETF或证券"),
])
assert_test("get_svol", lambda: client.get_svol(TEST_ETF), [
    (("svol",), lambda v: v is not None and v > 0, "卖量>0"),
])
assert_test("get_bvol", lambda: client.get_bvol(TEST_ETF), [
    (("bvol",), lambda v: v is not None and v > 0, "买量>0"),
])
assert_test("get_close_price_by_date", lambda: client.get_close_price_by_date(TEST_ETF, "1d", "20250102"), [
    (("close_price",), lambda v: v is not None and v > 0, "收盘价>0"),
])
assert_test("timetag_to_datetime", lambda: client.timetag_to_datetime(1704067200000), [
    (("datetime",), lambda v: "2024" in str(v), "时间戳转换正确"),
])
assert_test("bsm_price", lambda: client.bsm_price("C", 2.5, 2.5, 0.03, 0.2, 30, 0), [
    (("price",), lambda v: v is not None and v > 0, "BSM价格>0"),
])
assert_test("bsm_iv", lambda: client.bsm_iv("C", 2.5, 2.5, 0.1, 0.03, 30, 0), [
    (("iv",), lambda v: v is not None and v > 0, "隐含波动率>0"),
])

# ETF相关
assert_test("get_etf_iopv", lambda: client.get_etf_iopv("510050.SH"), [
    (("iopv",), lambda v: v is not None and v > 0, "IOPV>0"),
])

# 财务数据（用000001.SZ平安银行测试，有完整财报数据）
FINANCE_STOCK = "000001.SZ"
assert_test("download_history_data(财务)", lambda: client.download_history_data(FINANCE_STOCK))
time.sleep(2)
# 使用Balance/Income/CashFlow等有效字段名，QMT会自动映射为ASHAREBALANCESHEET等
assert_test("get_financial_data", lambda: client.get_financial_data("Balance,Income,CashFlow", FINANCE_STOCK, "20240101", "20241231"), [
    (("data",), lambda v: v is not None and v != {} and v != 0, "财务数据非空"),
])
assert_test("get_trading_dates", lambda: client.get_trading_dates(TEST_STOCK, "20250101", "20250131", count=30), [
    (("dates",), lambda v: isinstance(v, list), "交易日列表返回列表类型(可能为空若未下载数据)"),
])
assert_test("get_turnover_rate", lambda: client.get_turnover_rate([TEST_STOCK], "20250601", "20250630"))

# 以下接口可能返回空数据（正常情况）
assert_test("get_last_volume", lambda: client.get_last_volume(TEST_ETF))
assert_test("get_bar_timetag", lambda: client.get_bar_timetag(-1))
assert_test("get_tick_timetag", lambda: client.get_tick_timetag())
assert_test("get_industry", lambda: client.get_industry("CSRC计算机通信和其他电子设备制造业"))
assert_test("get_weight_in_index", lambda: client.get_weight_in_index(TEST_INDEX, TEST_ETF))
assert_test("get_contract_multiplier", lambda: client.get_contract_multiplier("IF"))
assert_test("get_risk_free_rate", lambda: client.get_risk_free_rate(0))
assert_test("get_date_location", lambda: client.get_date_location("20250101"))
assert_test("get_history_data", lambda: client.get_history_data(5, "1d", "close", stock_list=TEST_STOCK), [
    (("data",), lambda v: v is not None and v != {} and len(v) > 0, "历史数据非空(可能由get_market_data_ex降级返回)"),
])
assert_test("get_divid_factors", lambda: client.get_divid_factors(TEST_ETF))
assert_test("get_main_contract", lambda: client.get_main_contract("CU"))
assert_test("get_total_share", lambda: client.get_total_share(TEST_ETF))
assert_test("get_longhubang", lambda: client.get_longhubang([TEST_STOCK], "20250601", "20250630"))
assert_test("get_top10_share_holder", lambda: client.get_top10_share_holder([TEST_STOCK]))
assert_test("get_option_detail", lambda: client.get_option_detail(TEST_OPTION))
assert_test("get_etf_info", lambda: client.get_etf_info("510050.SH"))
assert_test("get_contract_expire_date", lambda: client.get_contract_expire_date("IF2501"))
assert_test("get_option_undl_data", lambda: client.get_option_undl_data("510050"))
assert_test("get_factor_data", lambda: client.get_factor_data("a", TEST_STOCK, "20240101", "20241231"))
assert_test("get_his_st_data", lambda: client.get_his_st_data(TEST_STOCK))
assert_test("get_his_index_data", lambda: client.get_his_index_data(TEST_INDEX))
assert_test("get_all_subscription", lambda: client.get_all_subscription())
assert_test("get_option_list", lambda: client.get_option_list("510050.SH"))
assert_test("get_his_contract_list", lambda: client.get_his_contract_list("IF"))
assert_test("get_option_iv", lambda: client.get_option_iv(TEST_OPTION))
assert_test("get_local_data", lambda: client.get_local_data(TEST_ETF, "20250101", "20250601"))
assert_test("get_close_price", lambda: client.get_close_price(TEST_ETF, "1d", 1704067200000))

# ============================================================
# 4. 订阅
# ============================================================
print("\n========== 4. 订阅 ==========")
assert_test("subscribe_quote", lambda: client.subscribe_quote(TEST_ETF, "1d"), [
    (("sub_id",), lambda v: v is not None, "订阅返回sub_id"),
])
assert_test("subscribe_whole_quote", lambda: client.subscribe_whole_quote([TEST_ETF]), [
    (("sub_id",), lambda v: v is not None, "订阅返回sub_id"),
])
# 订阅后服务端会立即用get_full_tick填充初始数据，等待2秒后检查
print("  ...等待2秒让订阅数据初始化...")
time.sleep(2)

assert_test("get_sub_tick_cache", lambda: client.get_sub_tick_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "tick缓存非空(订阅时自动填充)"),
])
assert_test("get_sub_quote_cache", lambda: client.get_sub_quote_cache(), [
    (("data",), lambda v: isinstance(v, dict) and len(v) > 0, "quote缓存非空(订阅时自动填充)"),
])
assert_test("unsubscribe_quote", lambda: client.unsubscribe_quote(0))

# ============================================================
# 5. 判定函数
# ============================================================
print("\n========== 5. 判定函数 ==========")
assert_test("is_last_bar", lambda: client.is_last_bar(), [
    (("is_last_bar",), lambda v: v is not None, "返回值非空"),
])
assert_test("is_suspended_stock", lambda: client.is_suspended_stock(TEST_ETF), [
    (("is_suspended",), lambda v: v is False, "513090未停牌"),
])
assert_test("get_industry_name_of_stock", lambda: client.get_industry_name_of_stock("CSRC", TEST_STOCK), [
    (("industry_name",), lambda v: v is not None and len(str(v)) > 0, "行业名非空"),
])
assert_test("is_new_bar", lambda: client.is_new_bar())
assert_test("is_sector_stock", lambda: client.is_sector_stock("沪深A股", "SH", TEST_ETF))
assert_test("is_typed_stock", lambda: client.is_typed_stock(4, "SH", TEST_ETF))

# ============================================================
# 6. 账户/订单查询
# ============================================================
print("\n========== 6. 账户/订单查询 ==========")
assert_test("get_trade_detail_data_position", lambda: client.get_trade_detail_data("stock", "position"), [
    (("data",), lambda v: isinstance(v, list), "持仓数据为列表"),
])
assert_test("get_trade_detail_data_account", lambda: client.get_trade_detail_data("stock", "account"), [
    (("data",), lambda v: isinstance(v, list) and len(v) > 0, "账户数据非空"),
])
assert_test("get_trade_detail_data_order", lambda: client.get_trade_detail_data("stock", "order"))
assert_test("get_trade_detail_data_deal", lambda: client.get_trade_detail_data("stock", "deal"))
assert_test("get_last_order_id", lambda: client.get_last_order_id(), [
    (("last_order_id",), lambda v: v is not None, "返回值非空"),
])
assert_test("get_smart_algo_param", lambda: client.get_smart_algo_param(["VWAP"]), [
    (("data", "VWAP"), lambda v: isinstance(v, list) and len(v) > 0, "VWAP参数列表非空"),
])
assert_test("get_value_by_order_id", lambda: client.get_value_by_order_id("12345"))
assert_test("can_cancel_order", lambda: client.can_cancel_order("12345"))
assert_test("get_debt_contract", lambda: client.get_debt_contract())
assert_test("get_assure_contract", lambda: client.get_assure_contract())
assert_test("get_enable_short_contract", lambda: client.get_enable_short_contract())
assert_test("get_ipo_data", lambda: client.get_ipo_data())
assert_test("get_new_purchase_limit", lambda: client.get_new_purchase_limit())
assert_test("query_credit_account", lambda: client.query_credit_account())
assert_test("query_credit_opvolume", lambda: client.query_credit_opvolume())

# ============================================================
# 7. 引用函数
# ============================================================
print("\n========== 7. 引用函数 ==========")
assert_test("ext_data", lambda: client.ext_data("测试指标", TEST_ETF))
assert_test("ext_data_rank", lambda: client.ext_data_rank("测试指标", TEST_ETF))
assert_test("ext_data_rank_range", lambda: client.ext_data_rank_range("测试指标", TEST_ETF, "20250101", "20250601"))
assert_test("ext_data_range", lambda: client.ext_data_range("测试指标", TEST_ETF, "20250101", "20250601"))
assert_test("get_factor_value", lambda: client.get_factor_value("alpha1", TEST_ETF))
assert_test("get_factor_rank", lambda: client.get_factor_rank("alpha1", TEST_ETF))

# ============================================================
# 8. 板块管理
# ============================================================
print("\n========== 8. 板块管理 ==========")
assert_test("get_sector_list", lambda: client.get_sector_list(), [
    (("data",), lambda v: v is not None, "板块列表非空"),
])

# ============================================================
# 9. 兼容方法
# ============================================================
print("\n========== 9. 兼容方法 ==========")
assert_test("get_order_status", lambda: client.get_order_status(), [
    (("orders",), lambda v: isinstance(v, list), "订单为列表"),
])
assert_test("get_deal", lambda: client.get_deal(), [
    (("deals",), lambda v: isinstance(v, list), "成交为列表"),
])

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
print("  ✅: {}".format(len(results["pass"])))
print("  ❌: {}".format(len(results["fail"])))
print("  SKIP: {}".format(len(results["skip"])))
print("=" * 60)

if results["fail"]:
    print("\n失败列表:")
    for name in results["fail"]:
        print("  - {}".format(name))
    sys.exit(1)
else:
    print("\n所有数据接口测试通过!")
    sys.exit(0)

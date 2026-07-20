#encoding:gbk

import json
import locale
from tornado.web import Application, RequestHandler, HTTPError
from tornado.ioloop import IOLoop
import logging
import os

# 自定义
ACCOUNT_ID = '你的QMT账号'
TOKEN = "123456789"
PORT = 8888


# ===================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
locale.setlocale(locale.LC_CTYPE, 'chinese')


def safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error("{} 调用失败: {}".format(func.__name__, e))
        return None


def _clean_nan(obj):
    """递归清理NaN/Inf，转为None（JSON标准不支持NaN/Inf）"""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_nan(i) for i in obj]
    return obj


def safe_json_dumps(obj, **kwargs):
    """安全JSON序列化，处理DataFrame/numpy/自定义对象等不可序列化类型"""
    try:
        import pandas as pd
        import numpy as np
        _has_pd = True
        _has_np = True
    except ImportError:
        _has_pd = False
        _has_np = False

    _nan_converted_count = [0]  # 用list以便在闭包中修改

    def _convert(o):
        # None直接返回
        if o is None:
            return None
        # bool必须先判断（bool是int子类）
        if isinstance(o, bool):
            return o
        # int直接返回
        if isinstance(o, int):
            return o
        # float需要检查NaN/Inf
        if isinstance(o, float):
            import math
            if math.isnan(o) or math.isinf(o):
                _nan_converted_count[0] += 1
                return None
            return o
        # str直接返回
        if isinstance(o, str):
            return o
        # pandas 类型
        if _has_pd:
            if isinstance(o, pd.DataFrame):
                return o.to_dict(orient='list')
            if isinstance(o, pd.Series):
                return o.tolist()
            if hasattr(pd, 'Panel') and isinstance(o, pd.Panel):
                result = {}
                for item in o.items:
                    result[str(item)] = o[item].to_dict(orient='list')
                return result
        # numpy 类型
        if _has_np:
            if isinstance(o, np.ndarray):
                return o.tolist()
            if isinstance(o, (np.integer,)):
                return int(o)
            if isinstance(o, (np.floating,)):
                v = float(o)
                import math
                if math.isnan(v) or math.isinf(v):
                    _nan_converted_count[0] += 1
                    return None
                return v
            if isinstance(o, np.bool_):
                return bool(o)
        # dict / list / tuple 递归处理
        if isinstance(o, dict):
            return {str(k): _convert(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_convert(i) for i in o]
        # 未知不可序列化对象，转为字符串
        try:
            json.dumps(o)
            return o
        except Exception:
            return str(o)

    try:
        converted = _convert(obj)
        result = json.dumps(converted, **kwargs)
        if _nan_converted_count[0] > 0:
            logger.info("[safe_json_dumps] NaN/Inf转None: 共{}处, 输出长度={}".format(
                _nan_converted_count[0], len(result)))
        return result
    except Exception as e:
        logger.error("[safe_json_dumps] JSON序列化失败: {}, 原始类型: {}, NaN转了{}处".format(
            e, type(obj).__name__, _nan_converted_count[0]))
        try:
            return json.dumps({"error": u"数据序列化失败: {}".format(str(e))}, ensure_ascii=True)
        except Exception:
            return '{"error": "data serialization failed"}'


# ============= 订阅数据缓存 =============
_sub_tick_cache = {}       # subscribe_whole_quote 回调缓存 {code: {field: val, ...}}
_sub_quote_cache = {}      # subscribe_quote 回调缓存 {sub_id: {timetag, open, ...}}

# HTTP Server 实例（用于停止监听）
_http_server = None


def _extract_attrs(obj):
    """从QMT返回对象中提取属性字典，递归处理嵌套对象"""
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        pd = None
        np = None
    import math
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): _extract_attrs(v) for k, v in obj.items()}
    if isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_extract_attrs(i) for i in obj]
    # pandas DataFrame/Series
    if pd and hasattr(obj, 'to_dict') and callable(obj.to_dict):
        try:
            return obj.to_dict(orient='list') if hasattr(obj, 'columns') else obj.tolist()
        except Exception:
            pass
    # numpy 类型
    if np:
        try:
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                v = float(obj)
                if math.isnan(v) or math.isinf(v):
                    return None
                return v
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except Exception:
            pass
    # QMT 自定义对象：提取m_开头和有意义的属性（排除数字索引等无意义属性）
    if hasattr(obj, '__dict__') or hasattr(obj, '__slots__'):
        attrs = {}
        for attr in dir(obj):
            if attr.startswith('_'):
                continue
            # 只提取m_开头或常见有意义属性，跳过数字索引和特殊属性
            if not attr.startswith('m_') and not attr[0:1].isalpha():
                continue
            # 跳过纯数字字符串属性（QMT对象的数字索引）
            try:
                int(attr)
                continue
            except (ValueError, TypeError):
                pass
            # 跳过QMT对象的特殊方法属性
            if attr in ('count', 'index', 'items', 'keys', 'values'):
                continue
            try:
                val = getattr(obj, attr)
                if callable(val):
                    continue
                attrs[attr] = _extract_attrs(val)
            except Exception:
                pass
        return attrs
    # 其他不可序列化对象
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


def _whole_quote_callback(data):
    """subscribe_whole_quote 的回调，将推送数据存入缓存"""
    try:
        logger.info("whole_quote_callback 被调用, data类型: {}".format(type(data).__name__))
        if isinstance(data, dict):
            for code, tick in data.items():
                _sub_tick_cache[str(code)] = _extract_attrs(tick)
            logger.info("whole_quote_callback 缓存更新, 共{}只股票: {}".format(
                len(_sub_tick_cache), list(_sub_tick_cache.keys())[:5]))
        else:
            # 单对象推送
            attrs = _extract_attrs(data)
            if isinstance(attrs, dict):
                code = attrs.get('sInstrumentID', attrs.get('stockcode', ''))
                if code:
                    _sub_tick_cache[str(code)] = attrs
                    logger.info("whole_quote_callback 缓存更新(单对象): {}".format(code))
    except Exception as e:
        logger.error("whole_quote_callback 异常: {}".format(e))


def _quote_callback(data):
    """subscribe_quote 的回调，将推送数据存入缓存
    当result_type='dict'时，data格式为 {stock_code: {field: value, ...}}
    当result_type=''时，data格式为 {stock_code: DataFrame}
    """
    try:
        logger.info("quote_callback 被调用, data类型: {}".format(type(data).__name__))
        if isinstance(data, dict):
            # result_type='dict' 或 result_type='' 的回调都传入dict
            for code, val in data.items():
                _sub_quote_cache[str(code)] = _extract_attrs(val)
            logger.info("quote_callback 缓存更新, 共{}条: {}".format(
                len(_sub_quote_cache), list(_sub_quote_cache.keys())[:5]))
        else:
            attrs = _extract_attrs(data)
            code = ''
            if isinstance(attrs, dict):
                code = attrs.get('sInstrumentID', attrs.get('stockcode', ''))
            if not code:
                code = str(len(_sub_quote_cache))
            _sub_quote_cache[code] = attrs
            logger.info("quote_callback 缓存更新(单对象): {}".format(code))
    except Exception as e:
        logger.error("quote_callback 异常: {}".format(e))


# ============= BaseHandler =============

AUTH_EXEMPT = set()


def no_auth(cls):
    AUTH_EXEMPT.add(cls)
    return cls


class BaseHandler(RequestHandler):
    def prepare(self):
        if self.__class__ not in AUTH_EXEMPT:
            token = self.request.headers.get('X-Token')
            if token != TOKEN:
                raise HTTPError(401, "认证失败：token 无效或缺失")

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")

    def write_error(self, status_code, **kwargs):
        self.finish(json.dumps({
            "error": self._reason,
            "status_code": status_code
        }, ensure_ascii=True))

    def ctx(self):
        return self.application.ContextInfo

    def acc(self):
        return self.application.accountID

    def _collect_order_ids(self):
        """收集当前活跃委托的ID集合，用于后续排重委托"""
        try:
            orders = get_trade_detail_data(self.acc(), 'stock', 'order', 'qmt') or []
            ids = set()
            for order in orders:
                ref = getattr(order, 'm_strOrderSysID', '') or ''
                if not ref:
                    ref = str(getattr(order, 'm_nOrderId', ''))
                if ref:
                    ids.add(str(ref))
            return ids
        except Exception:
            return set()

    def _find_new_order_ref(self, stock_code, exclude_ids, max_wait=5):
        """排除已知委托ID后，查找新增的委托订单
        同时检查委托列表和成交记录（委托可能瞬间成交后从委托列表消失）
        返回 (found, order_ref)
        """
        import time as _time
        _time.sleep(0.5)
        for _i in range(int(max_wait / 0.5)):
            try:
                # 先查委托列表
                orders = get_trade_detail_data(self.acc(), 'stock', 'order', 'qmt') or []
                logger.info("[_find_new_order_ref] 第{}次查询委托列表: {}条".format(_i+1, len(orders)))
                for order in reversed(orders):
                    ref = getattr(order, 'm_strOrderSysID', '') or ''
                    if not ref:
                        ref = str(getattr(order, 'm_nOrderId', ''))
                    if not ref or str(ref) in exclude_ids:
                        continue
                    order_stock = getattr(order, 'm_strInstrumentID', '') or ''
                    order_exchange = getattr(order, 'm_strExchangeID', '') or ''
                    full_code = "{}.{}".format(order_stock, order_exchange) if order_exchange else order_stock
                    if stock_code and full_code and stock_code not in full_code:
                        logger.info("[_find_new_order_ref] 跳过委托代码不匹配: code={}, ref={}".format(full_code, ref))
                        continue
                    logger.info("[_find_new_order_ref] 从委托列表找到: stock={}, ref={}".format(full_code, ref))
                    return True, str(ref)
                # 检查是否有任何新委托
                current_ids = set()
                for order in orders:
                    ref = getattr(order, 'm_strOrderSysID', '') or ''
                    if not ref:
                        ref = str(getattr(order, 'm_nOrderId', ''))
                    if ref:
                        current_ids.add(str(ref))
                new_ids = current_ids - exclude_ids
                if new_ids:
                    logger.info("[_find_new_order_ref] 发现新委托但股票不匹配, new_ids={}".format(list(new_ids)[:3]))
                    return True, list(new_ids)[0]

                # 委托列表为空或无新委托，检查成交记录（委托可能已瞬间成交）
                deals = get_trade_detail_data(self.acc(), 'stock', 'deal', 'qmt') or []
                logger.info("[_find_new_order_ref] 第{}次查询成交记录: {}条".format(_i+1, len(deals)))
                for deal in reversed(deals):
                    ref = getattr(deal, 'm_strOrderSysID', '') or ''
                    if not ref:
                        ref = str(getattr(deal, 'm_nOrderId', ''))
                    if not ref or str(ref) in exclude_ids:
                        continue
                    deal_stock = getattr(deal, 'm_strInstrumentID', '') or ''
                    deal_exchange = getattr(deal, 'm_strExchangeID', '') or ''
                    full_code = "{}.{}".format(deal_stock, deal_exchange) if deal_exchange else deal_stock
                    if stock_code and full_code and stock_code not in full_code:
                        continue
                    logger.info("[_find_new_order_ref] 从成交记录找到: stock={}, ref={}".format(full_code, ref))
                    return True, str(ref)
                # 检查成交记录中是否有任何新委托ID
                deal_ids = set()
                for deal in deals:
                    ref = getattr(deal, 'm_strOrderSysID', '') or ''
                    if not ref:
                        ref = str(getattr(deal, 'm_nOrderId', ''))
                    if ref:
                        deal_ids.add(str(ref))
                new_deal_ids = deal_ids - exclude_ids
                if new_deal_ids:
                    logger.info("[_find_new_order_ref] 成交记录发现新ID但股票不匹配, ids={}".format(list(new_deal_ids)[:3]))
                    return True, list(new_deal_ids)[0]
            except Exception as e:
                logger.info("[_find_new_order_ref] 查询异常: {}".format(e))
            _time.sleep(0.5)
        logger.info("[_find_new_order_ref] 查询超时({}s)，未找到新委托".format(max_wait))
        return False, ""
# ============= 1. ContextInfo 属性 =============
# ContextInfo.period - 获取当前周期
class ContextPeriodHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"period": self.ctx().period}, ensure_ascii=True))

# ContextInfo.barpos - 获取当前K线索引号
class ContextBarposHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"barpos": self.ctx().barpos}, ensure_ascii=True))

# ContextInfo.time_tick_size - 获取当前K线数目
class ContextTimeTickSizeHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"time_tick_size": self.ctx().time_tick_size}, ensure_ascii=True))

# ContextInfo.stockcode - 获取当前主图品种代码
class ContextStockCodeHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"stockcode": self.ctx().stockcode}, ensure_ascii=True))

# ContextInfo.dividend_type - 获取当前复权方式
class ContextDividendTypeHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"dividend_type": self.ctx().dividend_type}, ensure_ascii=True))

# ContextInfo.market - 获取当前主图市场
class ContextMarketHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"market": self.ctx().market}, ensure_ascii=True))

# ContextInfo.do_back_test - 是否开启回测模式
class ContextDoBackTestHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"do_back_test": self.ctx().do_back_test}, ensure_ascii=True))

# ContextInfo.benchmark - 获取回测基准
class ContextBenchmarkHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"benchmark": self.ctx().benchmark}, ensure_ascii=True))

# ContextInfo.capital - 获取回测初始资金
class ContextCapitalHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"capital": self.ctx().capital}, ensure_ascii=True))

# ContextInfo.get_universe() - 获取股票池中的股票
class ContextUniverseHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"universe": self.ctx().get_universe()}, ensure_ascii=True))

# ContextInfo.start - 获取回测开始时间
class ContextStartHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"start": self.ctx().start}, ensure_ascii=True))

# ContextInfo.end - 获取回测结束时间
class ContextEndHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"end": self.ctx().end}, ensure_ascii=True))


# ============= 2. 数据查询 (ContextInfo get_*) =============
# ContextInfo.get_stock_name() - 根据代码获取股票名称
class StockNameHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_stock_name, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "name": ret}, ensure_ascii=True))

# get_open_date() - 根据代码获取上市时间
class OpenDateHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_open_date, stockcode)
        self.write(safe_json_dumps({"stockcode": stockcode, "open_date": ret}, ensure_ascii=True))

# ContextInfo.get_last_volume() - 获取最新流通股本
class LastVolumeHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_last_volume, stockcode)
        if ret is None:
            self.write(json.dumps({"error": "获取流通股本失败"}, ensure_ascii=True))
            return
        self.write(json.dumps({"stockcode": stockcode, "last_volume": ret}, ensure_ascii=True))

# ContextInfo.get_bar_timetag() - 获取K线时间戳
class BarTimetagHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        index = int(data.get('index', -1))
        ret = safe_call(self.ctx().get_bar_timetag, index)
        self.write(json.dumps({"index": index, "timetag": ret}, ensure_ascii=True))

# ContextInfo.get_tick_timetag() - 获取最新分笔时间戳
class TickTimetagHandler(BaseHandler):
    def get(self):
        ret = safe_call(self.ctx().get_tick_timetag)
        self.write(json.dumps({"timetag": ret}, ensure_ascii=True))

# ContextInfo.get_sector() - 获取指数成份股
class SectorHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        sector = data.get('sector', '')
        realtime = data.get('realtime', '0')
        if not sector:
            self.write(json.dumps({"error": "need args sector"}, ensure_ascii=True))
            return
        ret = safe_call(self.ctx().get_sector, sector, int(realtime) if realtime != '0' else 0)
        self.write(json.dumps({"sector": sector, "stocks": ret or []}, ensure_ascii=True))

# ContextInfo.get_industry() - 获取行业成份股
class IndustryHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        industry = data.get('industry', '')
        if not industry:
            self.write(json.dumps({"error": "need args industry"}, ensure_ascii=True))
            return
        print(industry)
        ret = safe_call(self.ctx().get_industry, industry)
        self.write(json.dumps({"industry": industry, "stocks": ret or []}, ensure_ascii=True))

# ContextInfo.get_stock_list_in_sector() - 获取板块成份股
class StockListInSectorHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        sectorname = data.get('sectorname', '')
        if not sectorname:
            self.write(json.dumps({"error": "need args sectorname"}, ensure_ascii=True))
            return
        ret = safe_call(self.ctx().get_stock_list_in_sector, sectorname)
        self.write(json.dumps({"sectorname": sectorname, "stocks": ret or []}, ensure_ascii=True))

# ContextInfo.get_weight_in_index() - 获取指数中权重
class WeightInIndexHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        indexcode = data.get('indexcode', '')
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_weight_in_index, indexcode, stockcode)
        self.write(json.dumps({"indexcode": indexcode, "stockcode": stockcode, "weight": ret}, ensure_ascii=True))

# ContextInfo.get_contract_multiplier() - 获取合约乘数
class ContractMultiplierHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        contractcode = data.get('contractcode', '')
        ret = safe_call(self.ctx().get_contract_multiplier, contractcode)
        self.write(json.dumps({"contractcode": contractcode, "multiplier": ret}, ensure_ascii=True))

# ContextInfo.get_risk_free_rate() - 获取无风险利率
class RiskFreeRateHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        index = int(data.get('index', '-1'))
        ret = safe_call(self.ctx().get_risk_free_rate, index)
        self.write(json.dumps({"index": index, "risk_free_rate": ret}, ensure_ascii=True))

# ContextInfo.get_date_location() - 获取日期对应的K线索引
class DateLocationHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        strdate = data.get('strdate', '')
        ret = safe_call(self.ctx().get_date_location, strdate)
        self.write(json.dumps({"strdate": strdate, "location": ret}, ensure_ascii=True))

# ContextInfo.get_history_data() - 获取历史行情数据(多品种字典)
# 注意: 此API依赖handlebar上下文，HTTP handler中可能无法获取数据
# 建议使用 get_market_data / get_market_data_ex / get_local_data 替代
class HistoryDataHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            length = int(data.get('len', '10'))
            period = data.get('period', '1d')
            field = data.get('field', 'close')
            dividend_type = data.get('dividend_type', 'none')
            # dividend_type应为字符串（QMT API默认'none'），兼容整数输入
            if isinstance(dividend_type, int):
                _div_map = {0: 'none', 1: 'front', 2: 'back', 3: 'front_ratio', 4: 'follow'}
                dividend_type = _div_map.get(dividend_type, 'none')
            skip_paused = data.get('skip_paused', True)
            if isinstance(skip_paused, str):
                skip_paused = skip_paused.lower() == 'true'
            # 支持可选的stock_list参数用于临时设置universe
            stock_list = data.get('stock_list', '')
            stocks = []
            if stock_list:
                stocks = stock_list.split(',') if isinstance(stock_list, str) else [stock_list]
                safe_call(self.ctx().set_universe, stocks)
            logger.info("[HistoryData] 请求参数: length={}, period={}, field={}, dividend_type={}, skip_paused={}, stocks={}".format(
                length, period, field, dividend_type, skip_paused, stocks))

            # 步骤1: 直接调用 get_history_data
            ret = safe_call(self.ctx().get_history_data, length, period, field, dividend_type, skip_paused)
            logger.info("[HistoryData] 步骤1 get_history_data返回: type={}, is_None={}, repr={}".format(
                type(ret).__name__, ret is None, repr(ret)[:500] if ret is not None else 'None'))
            # 检查返回值是否为空（None、空dict、空DataFrame等）
            ret_is_empty = (ret is None or ret == {} or
                           (hasattr(ret, 'empty') and ret.empty) or
                           (isinstance(ret, dict) and len(ret) == 0))
            if not ret_is_empty:
                logger.info("[HistoryData] 步骤1成功，直接返回")
                self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
                return
            logger.info("[HistoryData] 步骤1返回空，ret_is_empty={}".format(ret_is_empty))

            # get_history_data 依赖handlebar上下文，在HTTP handler中返回空
            # 降级方案: 优先get_local_data(已确认可用) > get_market_data_ex
            if not stocks:
                logger.info("[HistoryData] 未提供stock_list，无法自动降级")
                self.write(json.dumps({"error": "获取历史数据失败。get_history_data依赖handlebar上下文，且未提供stock_list参数，无法自动降级"}, ensure_ascii=True))
                return
            try:
                # 计算默认日期范围（覆盖2年，确保能找到下载数据）
                import datetime as _dt
                now_dt = _dt.datetime.now()
                default_end = now_dt.strftime('%Y%m%d')
                default_start = (now_dt - _dt.timedelta(days=730)).strftime('%Y%m%d')
                logger.info("[HistoryData] 降级日期范围: {} ~ {}".format(default_start, default_end))

                # 步骤2: 优先用 get_local_data（直接调用已确认可用）
                # 签名: get_local_data(stock_code, start_time, end_time, period, divid_type, count)
                local_ret = None
                try:
                    logger.info("[HistoryData] 步骤2 get_local_data(stock={}, start={}, end={}, period={}, divid_type='none', count=-1)".format(
                        stocks[0], default_start, default_end, period))
                    local_ret = self.ctx().get_local_data(stocks[0], default_start, default_end, period, 'none', -1)
                    logger.info("[HistoryData] 步骤2 get_local_data返回: type={}, is_None={}, repr={}".format(
                        type(local_ret).__name__ if local_ret is not None else 'None',
                        local_ret is None,
                        repr(local_ret)[:500] if local_ret is not None else 'None'))
                    if local_ret is not None:
                        if hasattr(local_ret, 'empty') and local_ret.empty:
                            logger.info("[HistoryData] 步骤2 get_local_data返回空DataFrame")
                            local_ret = None
                        elif hasattr(local_ret, 'shape'):
                            logger.info("[HistoryData] 步骤2 DataFrame shape={}, columns={}".format(
                                local_ret.shape, list(local_ret.columns) if hasattr(local_ret, 'columns') else 'N/A'))
                except Exception as e2:
                    logger.info("[HistoryData] 步骤2 get_local_data失败: {}".format(e2))
                    local_ret = None

                if local_ret is not None:
                    # get_local_data返回可能是dict或DataFrame，统一序列化
                    if hasattr(local_ret, 'to_dict'):
                        result_data = local_ret.to_dict()
                    else:
                        result_data = local_ret
                    json_str = safe_json_dumps({"data": result_data, "note": "由get_local_data替代返回"}, ensure_ascii=True)
                    logger.info("[HistoryData] 步骤2成功, 输出长度={}, 前200字符={}".format(len(json_str), json_str[:200]))
                    self.write(json_str)
                    return

                # 步骤3: 用 get_market_data_ex 作为备用
                logger.info("[HistoryData] 步骤2返回空，尝试步骤3 get_market_data_ex")
                alt_ret = None
                for div_type in ['follow', 'front_ratio', 'front', 'back', 'none']:
                    try:
                        logger.info("[HistoryData] 步骤3 get_market_data_ex(fields=[{}], stocks={}, period={}, start={}, end={}, count=-1, div_type={})".format(
                            field, stocks, period, default_start, default_end, div_type))
                        alt_ret = self.ctx().get_market_data_ex([field], stocks, period, default_start, default_end, -1, div_type)
                        logger.info("[HistoryData] 步骤3 get_market_data_ex(div_type={}): type={}, is_None={}, repr={}".format(
                            div_type, type(alt_ret).__name__ if alt_ret is not None else 'None',
                            alt_ret is None,
                            repr(alt_ret)[:500] if alt_ret is not None else 'None'))
                    except Exception as e_div:
                        logger.info("[HistoryData] 步骤3 get_market_data_ex(div_type={})失败: {}".format(div_type, e_div))
                        alt_ret = None
                    if alt_ret is not None:
                        break

                # 检查返回结果是否真的有数据
                has_real_data = False
                if alt_ret and isinstance(alt_ret, dict):
                    for k, v in alt_ret.items():
                        logger.info("[HistoryData] 步骤3 key={}, value_type={}, is_empty_df={}".format(
                            k, type(v).__name__,
                            (hasattr(v, 'empty') and v.empty) if hasattr(v, 'empty') else 'N/A'))
                        if v is not None and not (hasattr(v, 'empty') and v.empty) and not v == {}:
                            has_real_data = True
                            if hasattr(v, 'shape'):
                                logger.info("[HistoryData] 步骤3 DataFrame shape={}, columns={}".format(v.shape, list(v.columns) if hasattr(v, 'columns') else 'N/A'))
                            break
                        elif isinstance(v, dict) and v:
                            has_real_data = True
                            break

                if alt_ret and has_real_data:
                    # 将DataFrame转为dict
                    result = {}
                    for k, v in alt_ret.items():
                        if hasattr(v, 'to_dict'):
                            result[k] = v.to_dict()
                        elif hasattr(v, 'empty') and v.empty:
                            result[k] = {}
                        else:
                            result[k] = v
                    json_str = safe_json_dumps({"data": result, "note": "由get_market_data_ex替代返回"}, ensure_ascii=True)
                    logger.info("[HistoryData] 步骤3成功, 输出长度={}, 前200字符={}".format(len(json_str), json_str[:200]))
                    self.write(json_str)
                    return

                logger.info("[HistoryData] 所有降级方案均失败")
            except Exception as e2:
                logger.error("[HistoryData] 降级失败: {}".format(e2))
            self.write(json.dumps({"error": "获取历史数据失败。get_history_data依赖handlebar上下文，get_local_data/get_market_data_ex降级也未返回有效数据。可能需要先download_history_data或检查日期范围"}, ensure_ascii=True))
        except Exception as e:
            logger.exception("[HistoryData] handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_market_data() - 获取行情数据(DataFrame)
class MarketDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        fields = data.get('fields', '')
        stock_code = data.get('stock_code', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        period = data.get('period', '1d')
        dividend_type = data.get('dividend_type', 'none')
        count = int(data.get('count', '-1'))
        fields_list = [f.strip() for f in fields.split(',')] if fields else []
        stock_list = [s.strip() for s in stock_code.split(',')] if stock_code else []
        try:
            ret = self.ctx().get_market_data(fields_list, stock_list, start_time, end_time, True, period, dividend_type, count)
        except Exception as e:
            logger.error("get_market_data 调用失败: {}".format(e))
            self.write(json.dumps({"error": "获取行情数据失败: {}".format(str(e))}, ensure_ascii=True))
        if ret is None:
            self.write(json.dumps({"error": "获取行情数据失败，API返回None"}, ensure_ascii=True))
            return
        if hasattr(ret, 'to_dict'):
            ret = ret.to_dict()
        self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))

# ContextInfo.get_market_data_ex() - 获取扩展行情(Level2)
class MarketDataExHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        fields = data.get('fields', '')
        stock_code = data.get('stock_code', '')
        period = data.get('period', 'follow')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        count = int(data.get('count', '-1'))
        dividend_type = data.get('dividend_type', 'follow')
        fields_list = [f.strip() for f in fields.split(',')] if fields else []
        stock_list = [s.strip() for s in stock_code.split(',')] if stock_code else []
        try:
            ret = self.ctx().get_market_data_ex(fields_list, stock_list, period, start_time, end_time, count, dividend_type)
        except Exception as e:
            logger.error("get_market_data_ex 调用失败: {}".format(e))
            self.write(json.dumps({"error": "获取扩展行情失败: {}".format(str(e))}, ensure_ascii=True))
        if ret is None:
            self.write(json.dumps({"error": "获取扩展行情失败，API返回None"}, ensure_ascii=True))
            return
        result = {}
        for k, v in ret.items():
            if hasattr(v, 'to_dict'):
                result[k] = v.to_dict()
            elif hasattr(v, 'empty') and v.empty:
                result[k] = {}
            else:
                result[k] = str(v)
        self.write(safe_json_dumps({"data": result}, ensure_ascii=True))

# ContextInfo.get_full_tick() - 获取分笔数据
class FullTickHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stocks = data.get('stocks', '')
        if not stocks:
            self.write(json.dumps({"error": "need args stocks"}, ensure_ascii=True))
            return
        code_list = [s.strip() for s in stocks.split(',')]
        ret = safe_call(self.ctx().get_full_tick, code_list)
        if not ret:
            self.write(json.dumps({"error": "获取分笔行情失败"}, ensure_ascii=True))
            return
        self.write(json.dumps(ret, ensure_ascii=True, default=str))

# ContextInfo.get_divid_factors() - 获取除权除息和复权因子
class DividFactorsHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_divid_factors, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "factors": ret or {}}, ensure_ascii=True))

# ContextInfo.get_main_contract() - 获取期货主力合约
class MainContractHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        codemarket = data.get('codemarket', '')
        ret = safe_call(self.ctx().get_main_contract, codemarket)
        self.write(json.dumps({"codemarket": codemarket, "main_contract": ret}, ensure_ascii=True))

# timetag_to_datetime() - 毫秒时间戳转日期时间
class TimetagToDatetimeHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        timetag = int(data.get('timetag', '0'))
        fmt = data.get('format', '%Y-%m-%d %H:%M:%S')
        ret = safe_call(timetag_to_datetime, timetag, fmt)
        self.write(json.dumps({"timetag": timetag, "datetime": ret}, ensure_ascii=True))

# ContextInfo.get_total_share() - 获取总股本
class TotalShareHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_total_share, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "total_share": ret}, ensure_ascii=True))

# ContextInfo.get_trading_dates() - 获取交易日列表
# QMT签名: get_trading_dates(stockcode, start_date, end_date, count, period)
# count: 返回的交易日数量，-1表示按日期范围返回全部
# 注意: 此API依赖handlebar上下文，HTTP handler中返回None
# 降级方案: 用get_local_data获取本地数据，从时间戳key中提取交易日
class TradingDatesHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')
        count = data.get('count', '')
        period = data.get('period', '1d')
        count_int = int(count) if count != '' and count is not None else -1
        logger.info("[TradingDates] 请求: stockcode={}, start={}, end={}, count={}, period={}".format(
            stockcode, start_date, end_date, count_int, period))
        try:
            # 方式1: 直接调用get_trading_dates
            ret = self.ctx().get_trading_dates(stockcode, start_date, end_date, count_int, period)
            logger.info("[TradingDates] 方式1返回: type={}, is_None={}, len={}".format(
                type(ret).__name__, ret is None, len(ret) if ret is not None else 'N/A'))
            if ret is None and count_int == -1:
                # count=-1可能不被支持，尝试用大数值替代
                logger.info("[TradingDates] count=-1返回None，尝试count=10000")
                ret = self.ctx().get_trading_dates(stockcode, start_date, end_date, 10000, period)
                logger.info("[TradingDates] 重试返回: type={}, is_None={}, len={}".format(
                    type(ret).__name__, ret is None, len(ret) if ret is not None else 'N/A'))
            if ret and not (isinstance(ret, (list, tuple)) and len(ret) == 0):
                logger.info("[TradingDates] 方式1成功, 日期数={}".format(len(ret) if hasattr(ret, '__len__') else 'N/A'))
                self.write(json.dumps({"dates": ret}, ensure_ascii=True, default=str))
                return

            # 方式2: get_trading_dates依赖handlebar上下文，降级用get_local_data提取交易日
            logger.info("[TradingDates] 方式1返回空，降级用get_local_data提取交易日")
            if stockcode:
                try:
                    local_ret = self.ctx().get_local_data(stockcode, start_date, end_date, period, 'none', -1)
                    logger.info("[TradingDates] get_local_data返回: type={}, is_None={}".format(
                        type(local_ret).__name__ if local_ret is not None else 'None', local_ret is None))
                    if local_ret is not None:
                        # 从返回数据的key中提取日期
                        trading_dates = []
                        if isinstance(local_ret, dict):
                            for ts_key in local_ret.keys():
                                try:
                                    # key可能是毫秒时间戳(str)或日期字符串
                                    if isinstance(ts_key, str) and ts_key.isdigit():
                                        ts = int(ts_key)
                                        import datetime as _dt
                                        dt = _dt.datetime.fromtimestamp(ts / 1000.0)
                                        trading_dates.append(dt.strftime('%Y%m%d'))
                                    else:
                                        trading_dates.append(str(ts_key))
                                except Exception:
                                    trading_dates.append(str(ts_key))
                        elif hasattr(local_ret, 'index'):
                            # DataFrame: 从index提取日期
                            for idx in local_ret.index:
                                try:
                                    if hasattr(idx, 'strftime'):
                                        trading_dates.append(idx.strftime('%Y%m%d'))
                                    else:
                                        trading_dates.append(str(idx))
                                except Exception:
                                    trading_dates.append(str(idx))
                        # 按count限制数量
                        if count_int > 0 and len(trading_dates) > count_int:
                            trading_dates = trading_dates[:count_int]
                        logger.info("[TradingDates] 方式2提取交易日: count={}".format(len(trading_dates)))
                        if trading_dates:
                            self.write(json.dumps({"dates": trading_dates, "note": "由get_local_data提取"}, ensure_ascii=True))
                            return
                        else:
                            logger.info("[TradingDates] 方式2提取结果为空")
                except Exception as e2:
                    logger.info("[TradingDates] get_local_data降级失败: {}".format(e2))

            self.write(json.dumps({"dates": [], "warning": "获取交易日失败。get_trading_dates依赖handlebar上下文，get_local_data降级也未返回有效数据。可能需要先download_history_data"}, ensure_ascii=True))
        except Exception as e:
            logger.error("[TradingDates] 调用失败: {}".format(e))
            self.write(json.dumps({"dates": [], "error": str(e)}, ensure_ascii=True))

# ContextInfo.get_svol() - 获取内盘成交量
class SvolHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_svol, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "svol": ret}, ensure_ascii=True))

# ContextInfo.get_bvol() - 获取外盘成交量
class BvolHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_bvol, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "bvol": ret}, ensure_ascii=True))

# ContextInfo.get_longhubang() - 获取龙虎榜数据
class LonghubangHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stock_list = data.get('stock_list', '')
        startTime = data.get('startTime', '')
        endTime = data.get('endTime', '')
        slist = [s.strip() for s in stock_list.split(',')] if stock_list else []
        ret = safe_call(self.ctx().get_longhubang, slist, startTime, endTime)
        if hasattr(ret, 'to_dict'):
            ret = ret.to_dict()
        self.write(json.dumps({"data": ret} if ret else {"error": "获取龙虎榜数据失败"}, ensure_ascii=True, default=str))

# get_top10_share_holder() - 获取十大股东数据
# 返回可能是 Series/DataFrame/Panel，需要安全序列化
class Top10ShareHolderHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stock_list = data.get('stock_list', '')
        data_name = data.get('data_name', 'holder')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        slist = [s.strip() for s in stock_list.split(',')] if stock_list else []
        ret = safe_call(self.ctx().get_top10_share_holder, slist, data_name, start_time, end_time)
        if ret is None:
            self.write(safe_json_dumps({"error": "获取十大股东数据失败"}, ensure_ascii=True))
        else:
            import pandas as pd
            if isinstance(ret, pd.Panel):
                # Panel -> dict of DataFrames
                result = {}
                for item in ret.items:
                    result[item] = ret[item].to_dict(orient='list')
                self.write(safe_json_dumps({"data": result}, ensure_ascii=True))
            elif isinstance(ret, pd.DataFrame):
                self.write(safe_json_dumps({"data": ret.to_dict(orient='list')}, ensure_ascii=True))
            elif isinstance(ret, pd.Series):
                self.write(safe_json_dumps({"data": ret.to_dict()}, ensure_ascii=True))
            else:
                self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))

# ContextInfo.get_option_detail_data() - 获取期权详细信息
class OptionDetailHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        optioncode = data.get('optioncode', '')
        ret = safe_call(self.ctx().get_option_detail_data, optioncode)
        self.write(json.dumps({"optioncode": optioncode, "detail": ret or {}}, ensure_ascii=True))

# ContextInfo.get_turnover_rate() - 获取换手率
class TurnoverRateHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stock_list = data.get('stock_list', '')
        startTime = data.get('startTime', '')
        endTime = data.get('endTime', '')
        slist = [s.strip() for s in stock_list.split(',')] if stock_list else []
        try:
            ret = self.ctx().get_turnover_rate(slist, startTime, endTime)
            if ret is None:
                self.write(json.dumps({"error": "获取换手率失败，API返回None"}, ensure_ascii=True))
            elif hasattr(ret, 'empty') and ret.empty:
                self.write(json.dumps({"data": {}, "warning": "返回空DataFrame，可能无该时段数据"}, ensure_ascii=True))
            elif hasattr(ret, 'to_dict'):
                self.write(safe_json_dumps({"data": ret.to_dict()}, ensure_ascii=True))
            else:
                self.write(json.dumps({"data": ret}, ensure_ascii=True, default=str))
        except Exception as e:
            logger.error("get_turnover_rate 调用失败: {}".format(e))
            self.write(json.dumps({"error": "获取换手率失败: {}".format(str(e))}, ensure_ascii=True))

# get_etf_info() - 获取ETF申赎清单及成分股
class EtfInfoHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(get_etf_info, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "info": ret or {}}, ensure_ascii=True, default=str))

# get_etf_iopv() - 获取ETF基金份额参考净值
class EtfIopvHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(get_etf_iopv, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "iopv": ret}, ensure_ascii=True))

# ContextInfo.get_instrumentdetail() - 获取合约详细信息
class InstrumentDetailHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().get_instrumentdetail, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "detail": ret or {}}, ensure_ascii=True, default=str))

# ContextInfo.get_contract_expire_date() - 获取期货合约到期日
class ContractExpireDateHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        codemarket = data.get('codemarket', '')
        ret = safe_call(self.ctx().get_contract_expire_date, codemarket)
        self.write(json.dumps({"codemarket": codemarket, "expire_date": ret}, ensure_ascii=True))

# ContextInfo.get_option_undl_data() - 获取期权标的对应的期权品种列表
class OptionUndlDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        undl_code_ref = data.get('undl_code_ref', '')
        ret = safe_call(self.ctx().get_option_undl_data, undl_code_ref)
        self.write(json.dumps({"data": ret or []}, ensure_ascii=True, default=str))

# ContextInfo.get_financial_data() - 获取财务数据
# 批量用法字段格式: 表名.字段名 (如 ASHAREINCOME.net_profit_incl_min_int_inc)
# 单值用法: get_financial_data(tabname, colname, market, code, report_type, barpos)
_FINANCIAL_TABLE_MAP = {
    'BALANCE': 'ASHAREBALANCESHEET',
    'INCOME': 'ASHAREINCOME',
    'CASHFLOW': 'ASHARECASHFLOW',
    'CAPITAL': 'CAPITALSTRUCTURE',
    'HOLDERNUM': 'SHAREHOLDER',
    'TOP10HOLDER': 'TOP10HOLDER',
    'TOP10FLOWHOLDER': 'TOP10FLOWHOLDER',
    'PERSHAREINDEX': 'PERSHAREINDEX',
}

# 各表默认字段（当只传表名时自动补全）
_FINANCIAL_DEFAULT_FIELDS = {
    'ASHAREBALANCESHEET': 'ASHAREBALANCESHEET.total_equity',
    'ASHAREINCOME': 'ASHAREINCOME.net_profit_incl_min_int_inc',
    'ASHARECASHFLOW': 'ASHARECASHFLOW.net_cash_flows_oper_act',
    'CAPITALSTRUCTURE': 'CAPITALSTRUCTURE.total_capital',
    'PERSHAREINDEX': 'PERSHAREINDEX.s_fa_eps_basic',
}

def _resolve_financial_fields(fields):
    """将字段名转换为QMT API接受的格式
    支持格式:
      - 'ASHAREINCOME.net_profit_incl_min_int_inc' (直接使用)
      - 'Income' -> 'ASHAREINCOME' (表名映射，需补全字段)
      - 'ASHAREINCOME' (直接表名，需补全字段)
    """
    resolved = []
    for f in fields:
        upper = f.upper()
        # 已经是 表名.字段名 格式，直接使用
        if '.' in f:
            resolved.append(f)
        elif upper in _FINANCIAL_TABLE_MAP:
            # 友好名 -> 表名，补全默认字段
            table = _FINANCIAL_TABLE_MAP[upper]
            resolved.append(_FINANCIAL_DEFAULT_FIELDS.get(table, table))
        elif upper in _FINANCIAL_DEFAULT_FIELDS:
            # 已经是表名，补全默认字段
            resolved.append(_FINANCIAL_DEFAULT_FIELDS[upper])
        else:
            resolved.append(f)  # 保持原样
    return resolved

class FinancialDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        tabname = data.get('tabname', '')
        colname = data.get('colname', '')
        market = data.get('market', '')
        code = data.get('code', '')
        report_type = data.get('report_type', 'report_time')
        barpos = int(data.get('barpos', '-1'))
        try:
            if tabname and colname and market and code:
                # 单值用法: get_financial_data(tabname, colname, market, code, report_type, barpos)
                logger.info("[FinancialData] 单值模式: tabname={}, colname={}, market={}, code={}".format(
                    tabname, colname, market, code))
                ret = self.ctx().get_financial_data(tabname, colname, market, code, report_type, barpos)
                logger.info("[FinancialData] 单值返回: type={}, repr={}".format(
                    type(ret).__name__, repr(ret)[:500] if ret is not None else 'None'))
            else:
                field_list = data.get('fieldList', '')
                stock_list = data.get('stockList', '')
                start_date = data.get('startDate', '')
                end_date = data.get('endDate', '')
                rtype = data.get('report_type', 'announce_time')
                fields = [f.strip() for f in field_list.split(',')] if field_list else []
                stocks = [s.strip() for s in stock_list.split(',')] if stock_list else []
                # 将字段名转换为 表名.字段名 格式
                resolved_fields = _resolve_financial_fields(fields)
                logger.info("[FinancialData] 批量模式: fields={} -> resolved={}, stocks={}, start={}, end={}, rtype={}".format(
                    fields, resolved_fields, stocks, start_date, end_date, rtype))
                if not resolved_fields:
                    # 未指定字段时，默认查询常用报表的关键字段
                    resolved_fields = [
                        'ASHAREINCOME.net_profit_incl_min_int_inc',
                        'CAPITALSTRUCTURE.total_capital',
                        'PERSHAREINDEX.s_fa_eps_basic',
                    ]
                    logger.info("[FinancialData] 使用默认字段: {}".format(resolved_fields))

                # 批量用法: get_financial_data(fieldList, stockList, startDate, endDate, report_type)
                ret = None

                # 方式1: list参数版（标准用法，字段格式为 表名.字段名）
                try:
                    logger.info("[FinancialData] 方式1调用: get_financial_data(resolved_fields={}, stocks={}, start={}, end={}, rtype={})".format(
                        resolved_fields, stocks, start_date, end_date, rtype))
                    ret = self.ctx().get_financial_data(resolved_fields, stocks, start_date, end_date, rtype)
                    logger.info("[FinancialData] 方式1返回: type={}, is_None={}, repr={}".format(
                        type(ret).__name__, ret is None,
                        repr(ret)[:800] if ret is not None else 'None'))
                    # 详细检查返回内容是否包含NaN
                    if ret is not None:
                        import math
                        nan_count = 0
                        total_count = 0
                        if isinstance(ret, dict):
                            for k, v in ret.items():
                                if isinstance(v, dict):
                                    for k2, v2 in v.items():
                                        total_count += 1
                                        if isinstance(v2, float) and (math.isnan(v2) or math.isinf(v2)):
                                            nan_count += 1
                        logger.info("[FinancialData] 方式1 NaN统计: total={}, nan={}, 全部NaN={}".format(
                            total_count, nan_count, nan_count > 0 and nan_count == total_count))
                except Exception as e1:
                    logger.info("[FinancialData] 方式1(list参数) 失败: {}".format(e1))

                # 方式2: 只传表名（不带字段名），部分QMT版本支持
                if ret is None and len(stocks) >= 1:
                    table_names = [f.split('.')[0] if '.' in f else f for f in resolved_fields]
                    try:
                        logger.info("[FinancialData] 方式2调用: get_financial_data(table_names={}, stocks={}, start={}, end={}, rtype={})".format(
                            table_names, stocks, start_date, end_date, rtype))
                        ret = self.ctx().get_financial_data(table_names, stocks, start_date, end_date, rtype)
                        logger.info("[FinancialData] 方式2返回: type={}, is_None={}, repr={}".format(
                            type(ret).__name__, ret is None,
                            repr(ret)[:800] if ret is not None else 'None'))
                    except Exception as e2:
                        logger.info("[FinancialData] 方式2(仅表名) 失败: {}".format(e2))

            if ret is None:
                self.write(json.dumps({"error": "获取财务数据失败，API返回None。正确字段格式: 表名.字段名 (如 ASHAREINCOME.net_profit_incl_min_int_inc)。有效表名: ASHAREBALANCESHEET/ASHAREINCOME/ASHARECASHFLOW/CAPITALSTRUCTURE/PERSHAREINDEX"}, ensure_ascii=True))
            elif hasattr(ret, 'empty') and ret.empty:
                self.write(json.dumps({"data": {}, "warning": "返回空DataFrame，可能字段名或日期范围无效"}, ensure_ascii=True))
            elif hasattr(ret, 'to_dict'):
                ret_dict = ret.to_dict()
                logger.info("[FinancialData] to_dict后: type={}, keys={}, repr={}".format(
                    type(ret_dict).__name__, list(ret_dict.keys()) if isinstance(ret_dict, dict) else 'N/A',
                    repr(ret_dict)[:500]))
                json_str = safe_json_dumps({"data": ret_dict}, ensure_ascii=True)
                logger.info("[FinancialData] safe_json_dumps输出长度={}, 前200字符={}".format(
                    len(json_str), json_str[:200]))
                self.write(json_str)
            elif isinstance(ret, (int, float, str)):
                logger.info("[FinancialData] 标量值: type={}, value={}".format(type(ret).__name__, repr(ret)[:200]))
                self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
            else:
                logger.info("[FinancialData] 其他类型: type={}, repr={}".format(
                    type(ret).__name__, repr(ret)[:500]))
                json_str = safe_json_dumps({"data": ret}, ensure_ascii=True)
                logger.info("[FinancialData] safe_json_dumps输出长度={}, 前200字符={}".format(
                    len(json_str), json_str[:200]))
                self.write(json_str)
        except Exception as e:
            logger.exception("[FinancialData] 调用失败: {}".format(e))
            try:
                self.write(json.dumps({"error": "获取财务数据失败: {}".format(str(e))}, ensure_ascii=True))
            except Exception:
                self.write(json.dumps({"error": "获取财务数据失败(内部错误序列化失败)"}, ensure_ascii=True))

# ContextInfo.get_factor_data() - 获取多因子数据
# 注意: 因子名需要是QMT内置因子，如 'alpha1','alpha2',... 或自定义因子名
# 该API也可能依赖handlebar上下文
class FactorDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        field_list = data.get('fieldList', '')
        stock_list = data.get('stockList', '')
        stock_code = data.get('stockCode', '')
        start_date = data.get('startDate', '')
        end_date = data.get('endDate', '')
        fields = [f.strip() for f in field_list.split(',')] if field_list else []
        logger.info("[FactorData] 请求参数: fields={}, stock_code={}, stock_list={}, start={}, end={}".format(
            fields, stock_code, stock_list, start_date, end_date))
        try:
            ret = None
            # 方式1: ContextInfo.get_factor_data (部分QMT版本支持)
            if stock_code:
                try:
                    logger.info("[FactorData] 方式1: ContextInfo.get_factor_data(fields={}, stock_code={}, start={}, end={})".format(
                        fields, stock_code, start_date, end_date))
                    ret = self.ctx().get_factor_data(fields, stock_code, start_date, end_date)
                    logger.info("[FactorData] 方式1返回: type={}, is_None={}, repr={}".format(
                        type(ret).__name__, ret is None,
                        repr(ret)[:500] if ret is not None else 'None'))
                    if ret is not None:
                        import math
                        if isinstance(ret, float) and (math.isnan(ret) or math.isinf(ret)):
                            logger.info("[FactorData] 方式1返回NaN/Inf float值")
                except Exception as e1:
                    logger.info("[FactorData] 方式1 ContextInfo.get_factor_data 失败: {}".format(e1))
            if ret is None and stock_list:
                stocks = [s.strip() for s in stock_list.split(',')] if stock_list else []
                try:
                    logger.info("[FactorData] 方式1b: ContextInfo.get_factor_data(fields={}, stocks={}, start={}, end={})".format(
                        fields, stocks, start_date, end_date))
                    ret = self.ctx().get_factor_data(fields, stocks, start_date, end_date)
                    logger.info("[FactorData] 方式1b返回: type={}, is_None={}, repr={}".format(
                        type(ret).__name__, ret is None,
                        repr(ret)[:500] if ret is not None else 'None'))
                except Exception as e2:
                    logger.info("[FactorData] 方式1b ContextInfo.get_factor_data(stocks) 失败: {}".format(e2))
            # 方式2: 全局函数 get_factor_value(factorname, stockcode, deviation, ContextInfo)
            # 注意: 此函数依赖handlebar上下文，HTTP handler中可能返回None
            if ret is None and stock_code and fields:
                try:
                    func = globals().get('get_factor_value')
                    logger.info("[FactorData] 方式2: 全局get_factor_value存在={}, factor={}, stock={}".format(
                        func is not None, fields[0], stock_code))
                    if func:
                        ret = func(fields[0], stock_code, 0, self.ctx())
                        logger.info("[FactorData] 方式2返回: type={}, is_None={}, repr={}".format(
                            type(ret).__name__, ret is None,
                            repr(ret)[:500] if ret is not None else 'None'))
                        if ret is not None:
                            import math
                            if isinstance(ret, float) and (math.isnan(ret) or math.isinf(ret)):
                                logger.info("[FactorData] 方式2返回NaN/Inf float值")
                except Exception as e3:
                    logger.info("[FactorData] 方式2 get_factor_value 失败: {}".format(e3))
            if ret is None:
                logger.info("[FactorData] 所有方式均返回None")
                self.write(json.dumps({"error": "获取因子数据失败，API返回None。注意: get_factor_value依赖handlebar上下文，HTTP handler中无法调用。需在策略handlebar回调中使用。"}, ensure_ascii=True))
            elif hasattr(ret, 'empty') and ret.empty:
                logger.info("[FactorData] 返回空DataFrame")
                self.write(json.dumps({"data": {}, "warning": "返回空DataFrame，可能因子名无效"}, ensure_ascii=True))
            elif hasattr(ret, 'to_dict'):
                ret_dict = ret.to_dict()
                logger.info("[FactorData] to_dict后: type={}, repr={}".format(
                    type(ret_dict).__name__, repr(ret_dict)[:500]))
                json_str = safe_json_dumps({"data": ret_dict}, ensure_ascii=True)
                logger.info("[FactorData] safe_json_dumps输出长度={}, 前200字符={}".format(
                    len(json_str), json_str[:200]))
                self.write(json_str)
            else:
                logger.info("[FactorData] 其他类型: type={}, repr={}".format(
                    type(ret).__name__, repr(ret)[:500]))
                json_str = safe_json_dumps({"data": ret}, ensure_ascii=True)
                logger.info("[FactorData] safe_json_dumps输出长度={}, 前200字符={}".format(
                    len(json_str), json_str[:200]))
                self.write(json_str)
        except Exception as e:
            logger.error("[FactorData] 调用失败: {}".format(e))
            self.write(json.dumps({"error": "获取因子数据失败: {}".format(str(e))}, ensure_ascii=True))

# ContextInfo.get_his_st_data() - 获取历史ST数据
class HisStDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockCode = data.get('stockCode', '')
        ret = safe_call(self.ctx().get_his_st_data, stockCode)
        self.write(json.dumps({"stockCode": stockCode, "data": ret or {}}, ensure_ascii=True))

# ContextInfo.get_his_index_data() - 获取历史指数数据
class HisIndexDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        index = data.get('index', '')
        ret = safe_call(self.ctx().get_his_index_data, index)
        self.write(json.dumps({"index": index, "data": ret or {}}, ensure_ascii=True, default=str))

# ContextInfo.get_all_subscription() - 获取当前所有行情订阅信息
class AllSubscriptionHandler(BaseHandler):
    def get(self):
        ret = safe_call(self.ctx().get_all_subscription)
        self.write(json.dumps({"subscriptions": ret or {}}, ensure_ascii=True, default=str))

# ContextInfo.get_option_list() - 获取指定期权列表
class OptionListHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            undl_code = data.get('undl_code', '')
            dedate = data.get('dedate', '')
            opttype = data.get('opttype', '')
            isavailable = data.get('isavailable', True)
            if isinstance(isavailable, str):
                isavailable = isavailable.lower() == 'true'
            ret = safe_call(self.ctx().get_option_list, undl_code, dedate, opttype, isavailable)
            self.write(safe_json_dumps({"option_list": ret or []}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_option_list handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_his_contract_list() - 获取过期合约列表
class HisContractListHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        market = data.get('market', '')
        ret = safe_call(self.ctx().get_his_contract_list, market)
        self.write(json.dumps({"market": market, "contracts": ret or []}, ensure_ascii=True))

# ContextInfo.get_option_iv() - 获取期权实时隐含波动率
class OptionIvHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        optioncode = data.get('optioncode', '')
        ret = safe_call(self.ctx().get_option_iv, optioncode)
        self.write(json.dumps({"optioncode": optioncode, "iv": ret}, ensure_ascii=True))

# ContextInfo.bsm_price() - BS模型计算欧式期权理论价格
class BsmPriceHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        optionType = data.get('optionType', 'C')
        objectPrices = data.get('objectPrices', '')
        strikePrice = float(data.get('strikePrice', '0'))
        riskFree = float(data.get('riskFree', '0'))
        sigma = float(data.get('sigma', '0'))
        days = int(data.get('days', '0'))
        dividend = float(data.get('dividend', '0'))
        try:
            op = float(objectPrices)
        except ValueError:
            op = [float(x) for x in objectPrices.split(',')]
        ret = safe_call(self.ctx().bsm_price, optionType, op, strikePrice, riskFree, sigma, days, dividend)
        self.write(json.dumps({"price": ret}, ensure_ascii=True, default=str))

# ContextInfo.bsm_iv() - BS模型计算欧式期权隐含波动率
class BsmIvHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        optionType = data.get('optionType', 'C')
        objectPrices = float(data.get('objectPrices', '0'))
        strikePrice = float(data.get('strikePrice', '0'))
        optionPrice = float(data.get('optionPrice', '0'))
        riskFree = float(data.get('riskFree', '0'))
        days = int(data.get('days', '0'))
        dividend = float(data.get('dividend', '0'))
        ret = safe_call(self.ctx().bsm_iv, optionType, objectPrices, strikePrice, optionPrice, riskFree, days, dividend)
        self.write(json.dumps({"iv": ret}, ensure_ascii=True))

# ContextInfo.get_local_data() - 从本地获取行情数据
class LocalDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stock_code = data.get('stock_code', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        period = data.get('period', '1d')
        divid_type = data.get('divid_type', 'none')
        count = int(data.get('count', '-1'))
        ret = safe_call(self.ctx().get_local_data, stock_code, start_time, end_time, period, divid_type, count)
        if ret is None:
            self.write(json.dumps({"error": "获取本地行情失败"}, ensure_ascii=True))
            return
        self.write(json.dumps({"data": ret}, ensure_ascii=True, default=str))

# ContextInfo.subscribe_quote() - 订阅行情数据（带回调缓存）
class SubscribeQuoteHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stock_code = data.get('stock_code', '')
        period = data.get('period', 'follow')
        dividend_type = data.get('dividend_type', 'follow')
        # 使用result_type='dict'，回调收到 {stock_code: {field: value}} 格式
        ret = safe_call(self.ctx().subscribe_quote, stock_code, period, dividend_type, 'dict', _quote_callback)
        # 订阅后立即用get_full_tick填充初始数据（避免等回调时缓存为空）
        if stock_code:
            codes = [s.strip() for s in stock_code.split(',')] if isinstance(stock_code, str) else [stock_code]
            try:
                tick_data = self.ctx().get_full_tick(codes)
                if tick_data and isinstance(tick_data, dict):
                    for code, tick in tick_data.items():
                        _sub_quote_cache[str(code)] = _extract_attrs(tick)
                    logger.info("subscribe_quote 初始数据填充, 共{}只: {}".format(
                        len(tick_data), list(tick_data.keys())[:5]))
            except Exception as e:
                logger.info("subscribe_quote 初始数据填充失败: {}".format(e))
        self.write(json.dumps({"status": "success" if ret is not None else "failed", "sub_id": ret}, ensure_ascii=True))

# ContextInfo.unsubscribe_quote() - 反订阅行情数据
class UnsubscribeQuoteHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        sub_id = int(data.get('sub_id', '0'))
        safe_call(self.ctx().unsubscribe_quote, sub_id)
        self.write(json.dumps({"status": "success", "sub_id": sub_id}, ensure_ascii=True))

# ContextInfo.get_close_price() - 获取指定时间的收盘价
# QMT签名: get_close_price(market, stockCode, realTimetag, period=86400000, dividType=0)
class ClosePriceHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        period = data.get('period', '1d')
        timetag = int(data.get('timetag', '0'))
        # 解析market和stockCode
        parts = stockcode.split('.') if '.' in stockcode else ('', stockcode)
        market = parts[1] if len(parts) == 2 else ''
        code = parts[0] if len(parts) == 2 else stockcode
        # period转毫秒
        period_ms = int(data.get('period_ms', 86400000))
        divid_type = int(data.get('divid_type', '0'))
        ret = safe_call(self.ctx().get_close_price, market, code, timetag, period_ms, divid_type)
        self.write(safe_json_dumps({"stockcode": stockcode, "period": period, "timetag": timetag, "close_price": ret}, ensure_ascii=True))

# ContextInfo.get_close_price_by_date() - 获取指定日期的收盘价
# QMT原生无此方法，用 get_market_data 实现
class ClosePriceByDateHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        period = data.get('period', '1d')
        strdate = data.get('strdate', '')
        dividend_type = data.get('dividend_type', 'none')
        ret_data = safe_call(self.ctx().get_market_data,
                             ['close'], [stockcode], strdate, strdate,
                             True, period, dividend_type, -1)
        close_price = None
        if ret_data is not None:
            # 返回可能是 Series/DataFrame/数值
            import pandas as pd
            if isinstance(ret_data, pd.DataFrame):
                if not ret_data.empty:
                    close_price = float(ret_data.iloc[0, 0])
            elif isinstance(ret_data, pd.Series):
                if not ret_data.empty:
                    close_price = float(ret_data.iloc[0])
            elif isinstance(ret_data, (int, float)):
                close_price = float(ret_data)
        self.write(safe_json_dumps({"stockcode": stockcode, "period": period, "strdate": strdate, "close_price": close_price}, ensure_ascii=True))

# ContextInfo.subscribe_whole_quote() - 订阅全推行情（带回调缓存）
class SubscribeWholeQuoteHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        code_list = data.get('code_list', '')
        if not code_list:
            self.write(json.dumps({"error": "need args code_list"}, ensure_ascii=True))
            return
        codes = [s.strip() for s in code_list.split(',')]
        ret = safe_call(self.ctx().subscribe_whole_quote, codes, _whole_quote_callback)
        # 订阅后立即用get_full_tick填充初始数据（避免等回调时缓存为空）
        try:
            tick_data = self.ctx().get_full_tick(codes)
            if tick_data and isinstance(tick_data, dict):
                for code, tick in tick_data.items():
                    _sub_tick_cache[str(code)] = _extract_attrs(tick)
                logger.info("subscribe_whole_quote 初始数据填充, 共{}只: {}".format(
                    len(tick_data), list(tick_data.keys())[:5]))
        except Exception as e:
            logger.info("subscribe_whole_quote 初始数据填充失败: {}".format(e))
        self.write(json.dumps({"status": "success" if ret is not None else "failed", "sub_id": ret}, ensure_ascii=True))

# 获取订阅缓存的全推行情数据
class SubTickCacheHandler(BaseHandler):
    def get(self):
        global _sub_tick_cache
        try:
            if _sub_tick_cache:
                codes = list(_sub_tick_cache.keys())
                tick_data = self.ctx().get_full_tick(codes)
                if tick_data and isinstance(tick_data, dict):
                    result = {}
                    for code, tick in tick_data.items():
                        result[str(code)] = _extract_attrs(tick)
                    self.write(safe_json_dumps({"data": result}, ensure_ascii=True))
                    return
        except Exception as e:
            logger.info("[SubTickCache] get_full_tick获取失败: {}".format(e))
        self.write(safe_json_dumps({"data": _sub_tick_cache}, ensure_ascii=True))

# 获取订阅缓存的行情数据
class SubQuoteCacheHandler(BaseHandler):
    def get(self):
        global _sub_quote_cache
        try:
            if _sub_quote_cache:
                codes = list(_sub_quote_cache.keys())
                tick_data = self.ctx().get_full_tick(codes)
                if tick_data and isinstance(tick_data, dict):
                    result = {}
                    for code, tick in tick_data.items():
                        result[str(code)] = _extract_attrs(tick)
                    self.write(safe_json_dumps({"data": result}, ensure_ascii=True))
                    return
        except Exception as e:
            logger.info("[SubQuoteCache] get_full_tick获取失败: {}".format(e))
        self.write(safe_json_dumps({"data": _sub_quote_cache}, ensure_ascii=True))

# ContextInfo.set_universe() - 设置股票池
class SetUniverseHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stock_list = data.get('stock_list', '')
        if not stock_list:
            self.write(json.dumps({"error": "need args stock_list"}, ensure_ascii=True))
            return
        stocks = [s.strip() for s in stock_list.split(',')]
        safe_call(self.ctx().set_universe, stocks)
        self.write(json.dumps({"status": "success", "stock_list": stocks}, ensure_ascii=True))

# ContextInfo.set_account() - 设置账号
class SetAccountHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        accountid = data.get('accountid', '')
        if not accountid:
            self.write(json.dumps({"error": "need args accountid"}, ensure_ascii=True))
            return
        safe_call(self.ctx().set_account, accountid)
        self.write(json.dumps({"status": "success", "accountid": accountid}, ensure_ascii=True))

# download_history_data() - 下载历史数据到本地
class DownloadHistoryDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        period = data.get('period', '1d')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        if not stockcode:
            self.write(json.dumps({"error": "need args stockcode"}, ensure_ascii=True))
            return
        ret = safe_call(download_history_data, stockcode, period, start_time, end_time)
        self.write(json.dumps({"status": "success", "stockcode": stockcode, "result": ret}, ensure_ascii=True))

# ContextInfo.set_output_index_property() - 设置指标输出属性
class SetOutputIndexPropertyHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        index_name = data.get('index_name', '')
        draw_style = int(data.get('draw_style', '0'))
        color = data.get('color', 'white')
        noaxis = data.get('noaxis', False)
        nodraw = data.get('nodraw', False)
        noshow = data.get('noshow', False)
        safe_call(self.ctx().set_output_index_property, index_name, draw_style, color, noaxis, nodraw, noshow)
        self.write(json.dumps({"status": "success", "index_name": index_name}, ensure_ascii=True))


# ============= 3. 判定函数 (is_*) =============
# ContextInfo.is_last_bar() - 判定是否为最后一根K线
class IsLastBarHandler(BaseHandler):
    def get(self):
        ret = safe_call(self.ctx().is_last_bar)
        self.write(json.dumps({"is_last_bar": ret}, ensure_ascii=True))

# ContextInfo.is_new_bar() - 判定是否为新的K线
class IsNewBarHandler(BaseHandler):
    def get(self):
        ret = safe_call(self.ctx().is_new_bar)
        self.write(json.dumps({"is_new_bar": ret}, ensure_ascii=True))

# ContextInfo.is_suspended_stock() - 判定股票是否停牌
class IsSuspendedStockHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stockcode = data.get('stockcode', '')
        ret = safe_call(self.ctx().is_suspended_stock, stockcode)
        self.write(json.dumps({"stockcode": stockcode, "is_suspended": ret}, ensure_ascii=True))

# is_sector_stock() - 判定股票是否在指定板块中
class IsSectorStockHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        sectorname = data.get('sectorname', '')
        market = data.get('market', '')
        stockcode = data.get('stockcode', '')
        ret = safe_call(is_sector_stock, sectorname, market, stockcode)
        self.write(json.dumps({"sectorname": sectorname, "stockcode": stockcode, "is_in_sector": ret}, ensure_ascii=True))

# is_typed_stock() - 判定股票是否属于某个类别
class IsTypedStockHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        stocktypenum = int(data.get('stocktypenum', '0'))
        market = data.get('market', '')
        stockcode = data.get('stockcode', '')
        ret = safe_call(is_typed_stock, stocktypenum, market, stockcode)
        self.write(json.dumps({"stocktypenum": stocktypenum, "stockcode": stockcode, "result": ret}, ensure_ascii=True))

# get_industry_name_of_stock() - 获取股票行业分类名称
class GetIndustryNameOfStockHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        industryType = data.get('industryType', '')
        stockcode = data.get('stockcode', '')
        ret = safe_call(get_industry_name_of_stock, industryType, stockcode)
        self.write(json.dumps({"industryType": industryType, "stockcode": stockcode, "industry_name": ret}, ensure_ascii=True))


# ============= 4. 交易函数 =============
# passorder() - 综合交易下单(支持股票买卖等)
class PassorderHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            opType = int(data['opType'])
            orderType = int(data.get('orderType', 1101))
            stock = data['stock']
            pr_type = int(data.get('prType', 11))
            price = float(data['price'])
            volume = int(data['volume'])
            quickTrade = int(data.get('quickTrade', 2))
            strategy_name = data.get('strategyName', 'qmt') or 'qmt'
            reason = data.get('reason', '') or ''
            # passorder 第8参数(strategyName)必须为'qmt'，否则QMT不下单
            # 将原始 strategy_name 合并到 reason(投资备注) 中
            combined_reason = '{}_{}'.format(strategy_name, reason) if reason else strategy_name
            if not combined_reason:
                combined_reason = 'qmt'
            combined_reason = combined_reason[:24]  # 投资备注长度限制24
            logger.info("[Passorder] opType={}, orderType={}, stock={}, prType={}, price={}, volume={}, quickTrade={}, strategyName='qmt', reason='{}'".format(
                opType, orderType, stock, pr_type, price, volume, quickTrade, combined_reason))
            before_ids = self._collect_order_ids()
            order_ref = passorder(opType, orderType, self.acc(), stock, pr_type, price, volume, 'qmt', quickTrade, combined_reason, self.ctx())
            logger.info("[Passorder] 返回: type={}, repr={}".format(
                type(order_ref).__name__, repr(order_ref)[:200] if order_ref is not None else 'None'))
            ref_str = str(order_ref) if order_ref is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                logger.info("[Passorder] 未直接返回订单号，尝试查询确认委托")
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
            self.write(json.dumps({
                "status": "success",
                "opType": opType,
                "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("passorder下单异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# algo_passorder() - 算法交易下单
class AlgoPassorderHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            before_ids = self._collect_order_ids()
            order_ref = algo_passorder(
                int(data['opType']), int(data.get('orderType', 1101)),
                self.acc(), stock, int(data.get('prType', -1)),
                float(data['price']), int(data['volume']),
                data.get('strategyName', ''), int(data.get('quickTrade', 2)),
                data.get('userOrderId', ''), data.get('userOrderParam', {}),
                self.ctx()
            )
            logger.info("[AlgoPassorder] 返回: type={}, repr={}".format(
                type(order_ref).__name__ if order_ref is not None else 'None',
                repr(order_ref)[:200] if order_ref is not None else 'None'))
            ref_str = str(order_ref) if order_ref is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                else:
                    self.write(json.dumps({
                        "status": "warning", "order_ref": "",
                        "message": "算法下单未返回委托，可能不支持或handlebar上下文缺失"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({"status": "success", "order_ref": ref_str if ref_str else "unknown"}, ensure_ascii=True))
        except Exception as e:
            logger.exception("algo_passorder异常")
            self.write(json.dumps({"status": "error", "message": "算法下单失败: {}".format(str(e))}, ensure_ascii=True))

# smart_algo_passorder() - 智能算法交易下单
# 官方签名: smart_algo_passorder(opType, orderType, accountid, orderCode, prType, price,
#   volume, strageName, quickTrade, userid, smartAlgoType, limitOverRate,
#   minAmountPerOrder, [targetPriceLevel, startTime, endTime, limitControl], ContextInfo)
class SmartAlgoPassorderHandler(BaseHandler):
    def post(self):
        try:
            # 判断smart_algo_passorder是全局函数还是ContextInfo方法
            func = globals().get('smart_algo_passorder') or getattr(self.ctx(), 'smart_algo_passorder', None)
            if func is None:
                self.write(json.dumps({"status": "error", "message": "当前QMT版本不支持smart_algo_passorder（智能算法交易）"}, ensure_ascii=True))
                return
            data = json.loads(self.request.body)
            order_ref = func(
                int(data['opType']),                          # opType
                int(data.get('orderType', 1101)),             # orderType
                self.acc(),                                   # accountid
                data['stock'],                                # orderCode
                int(data.get('prType', 11)),                  # prType (智能算法仅支持11限价/12市价)
                float(data['price']),                         # price
                int(data['volume']),                          # volume
                data.get('strageName', ''),                   # strageName (策略名，不可缺省)
                int(data.get('quickTrade', 2)),               # quickTrade
                data.get('userid', ''),                       # userid (自定义编号)
                data['smartAlgoType'],                        # smartAlgoType (如"VWAP","TWAP")
                float(data.get('limitOverRate', 0)),          # limitOverRate (量比比例)
                int(data.get('minAmountPerOrder', 0)),        # minAmountPerOrder
                data.get('targetPriceLevel', 0),              # targetPriceLevel (可选)
                data.get('startTime', ''),                    # startTime
                data.get('endTime', ''),                      # endTime
                data.get('limitControl', 0),                  # limitControl (可选)
                self.ctx()                                    # ContextInfo
            )
            logger.info("[SmartAlgoPassorder] 返回: type={}, repr={}".format(
                type(order_ref).__name__ if order_ref is not None else 'None',
                repr(order_ref)[:200] if order_ref is not None else 'None'))
            ref_str = str(order_ref) if order_ref is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                self.write(json.dumps({
                    "status": "warning", "order_ref": ref_str,
                    "message": "智能算法下单未返回有效委托，可能不支持或需要轮询"
                }, ensure_ascii=True))
                return
            self.write(json.dumps({"status": "success", "order_ref": ref_str}, ensure_ascii=True))
        except Exception as e:
            logger.exception("smart_algo_passorder异常")
            self.write(json.dumps({"status": "error", "message": "智能算法下单失败: {}".format(str(e))}, ensure_ascii=True))

# order_lots() - 指定手数交易
class OrderLotsHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            logger.info("[OrderLots] stock={}, lots={}, style={}, price={}".format(
                stock, data['lots'], data.get('style', 'LATEST'), data.get('price', 0)))
            before_ids = self._collect_order_ids()
            ret = order_lots(stock, int(data['lots']), data.get('style', 'LATEST'),
                       float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[OrderLots] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                    logger.info("[OrderLots] 委托确认成功, ref={}".format(ref_str))
                else:
                    logger.warning("[OrderLots] 委托未生效，下单可能失败")
                    self.write(json.dumps({
                        "status": "error", "action": "order_lots", "stock": stock,
                        "message": "下单未返回委托，可能需要在handlebar上下文中调用"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "order_lots", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("order_lots异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# order_value() - 指定价值交易
class OrderValueHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            logger.info("[OrderValue] stock={}, value={}".format(stock, data['value']))
            before_ids = self._collect_order_ids()
            ret = order_value(stock, float(data['value']), data.get('style', 'LATEST'),
                        float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[OrderValue] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                    logger.info("[OrderValue] 委托确认成功, ref={}".format(ref_str))
                else:
                    logger.warning("[OrderValue] 委托未生效，下单可能失败")
                    self.write(json.dumps({
                        "status": "error", "action": "order_value", "stock": stock,
                        "message": "下单未返回委托，可能需要在handlebar上下文中调用"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "order_value", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("order_value异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# order_percent() - 指定比例交易
class OrderPercentHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            before_ids = self._collect_order_ids()
            ret = order_percent(stock, float(data['percent']), data.get('style', 'LATEST'),
                          float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[OrderPercent] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                else:
                    logger.warning("[OrderPercent] 委托未生效，下单可能失败")
                    self.write(json.dumps({
                        "status": "error", "action": "order_percent", "stock": stock,
                        "message": "下单未返回委托，可能需要在handlebar上下文中调用"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "order_percent", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("order_percent异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# order_target_value() - 指定目标价值交易
class OrderTargetValueHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            before_ids = self._collect_order_ids()
            ret = order_target_value(stock, float(data['tar_value']), data.get('style', 'LATEST'),
                               float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[OrderTargetValue] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                else:
                    logger.warning("[OrderTargetValue] 委托未生效，下单可能失败")
                    self.write(json.dumps({
                        "status": "error", "action": "order_target_value", "stock": stock,
                        "message": "下单未返回委托，可能需要在handlebar上下文中调用"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "order_target_value", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("order_target_value异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# order_target_percent() - 指定目标比例交易
class OrderTargetPercentHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            before_ids = self._collect_order_ids()
            ret = order_target_percent(stock, float(data['tar_percent']), data.get('style', 'LATEST'),
                                 float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[OrderTargetPercent] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                else:
                    logger.warning("[OrderTargetPercent] 委托未生效，下单可能失败")
                    self.write(json.dumps({
                        "status": "error", "action": "order_target_percent", "stock": stock,
                        "message": "下单未返回委托，可能需要在handlebar上下文中调用"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "order_target_percent", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("order_target_percent异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# order_shares() - 指定股数交易
class OrderSharesHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            before_ids = self._collect_order_ids()
            ret = order_shares(stock, int(data['shares']), data.get('style', 'LATEST'),
                         float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[OrderShares] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                else:
                    logger.warning("[OrderShares] 委托未生效，下单可能失败")
                    self.write(json.dumps({
                        "status": "error", "action": "order_shares", "stock": stock,
                        "message": "下单未返回委托，可能需要在handlebar上下文中调用"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "order_shares", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("order_shares异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))


# ============= 5. 期货交易 =============
# buy_open() - 期货买入开仓
class FuturesBuyOpenHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            before_ids = self._collect_order_ids()
            ret = buy_open(stock, int(data['amount']), data.get('style', 'LATEST'),
                     float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[FuturesBuyOpen] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                else:
                    # 在期货账户用期货账户下单，默认失败，返回warning而非error
                    self.write(json.dumps({
                        "status": "warning", "action": "buy_open", "stock": stock,
                        "order_ref": "",
                        "message": "下单未返回委托，请确认期货账户是否handlebar上下文缺失"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "buy_open", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("buy_open异常")
            self.write(json.dumps({"status": "error", "message": "期货买入开仓失败: {}".format(str(e))}, ensure_ascii=True))

# buy_close_tdayfirst() - 期货买入平仓(平今优先)
class FuturesBuyCloseTdayFirstHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            ret = buy_close_tdayfirst(stock, int(data['amount']), data.get('style', 'LATEST'),
                                float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[FuturesBuyCloseTdayFirst] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            self.write(json.dumps({
                "status": "success" if ref_str and ref_str != "None" and ref_str != "0" else "warning",
                "action": "buy_close_tdayfirst", "stock": stock,
                "order_ref": ref_str if ref_str and ref_str != "None" else ""
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("buy_close_tdayfirst异常")
            self.write(json.dumps({"status": "error", "message": "期货买入平仓(平今)失败: {}".format(str(e))}, ensure_ascii=True))

# buy_close_ydayfirst() - 期货买入平仓(平昨优先)
class FuturesBuyCloseYdayFirstHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            ret = buy_close_ydayfirst(stock, int(data['amount']), data.get('style', 'LATEST'),
                                float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[FuturesBuyCloseYdayFirst] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            self.write(json.dumps({
                "status": "success" if ref_str and ref_str != "None" and ref_str != "0" else "warning",
                "action": "buy_close_ydayfirst", "stock": stock,
                "order_ref": ref_str if ref_str and ref_str != "None" else ""
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("buy_close_ydayfirst异常")
            self.write(json.dumps({"status": "error", "message": "期货买入平仓(平昨)失败: {}".format(str(e))}, ensure_ascii=True))

# sell_open() - 期货卖出开仓
class FuturesSellOpenHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            before_ids = self._collect_order_ids()
            ret = sell_open(stock, int(data['amount']), data.get('style', 'LATEST'),
                      float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[FuturesSellOpen] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                else:
                    self.write(json.dumps({
                        "status": "warning", "action": "sell_open", "stock": stock,
                        "order_ref": "",
                        "message": "下单未返回委托，请确认期货账户是否handlebar上下文缺失"
                    }, ensure_ascii=True))
                    return
            self.write(json.dumps({
                "status": "success", "action": "sell_open", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("sell_open异常")
            self.write(json.dumps({"status": "error", "message": "期货卖出开仓失败: {}".format(str(e))}, ensure_ascii=True))

# sell_close_tdayfirst() - 期货卖出平仓(平今优先)
class FuturesSellCloseTdayFirstHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            ret = sell_close_tdayfirst(stock, int(data['amount']), data.get('style', 'LATEST'),
                                 float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[FuturesSellCloseTdayFirst] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            self.write(json.dumps({
                "status": "success" if ref_str and ref_str != "None" and ref_str != "0" else "warning",
                "action": "sell_close_tdayfirst", "stock": stock,
                "order_ref": ref_str if ref_str and ref_str != "None" else ""
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("sell_close_tdayfirst异常")
            self.write(json.dumps({"status": "error", "message": "期货卖出平仓(平今)失败: {}".format(str(e))}, ensure_ascii=True))

# sell_close_ydayfirst() - 期货卖出平仓(平昨优先)
class FuturesSellCloseYdayFirstHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            ret = sell_close_ydayfirst(stock, int(data['amount']), data.get('style', 'LATEST'),
                                 float(data.get('price', 0)), self.ctx(), data.get('accId', self.acc()))
            logger.info("[FuturesSellCloseYdayFirst] 返回: type={}, repr={}".format(
                type(ret).__name__ if ret is not None else 'None', repr(ret)[:200] if ret is not None else 'None'))
            ref_str = str(ret) if ret is not None else ""
            self.write(json.dumps({
                "status": "success" if ref_str and ref_str != "None" and ref_str != "0" else "warning",
                "action": "sell_close_ydayfirst", "stock": stock,
                "order_ref": ref_str if ref_str and ref_str != "None" else ""
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("sell_close_ydayfirst异常")
            self.write(json.dumps({"status": "error", "message": "期货卖出平仓(平昨)失败: {}".format(str(e))}, ensure_ascii=True))


# ============= 6. 任务管理 =============
# cancel_task() - 撤销任务
class CancelTaskHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            taskId = data['taskId']
            accountType = data.get('accountType', 'stock')
            ret = cancel_task(taskId, self.acc(), accountType, self.ctx())
            self.write(json.dumps({"status": "success" if ret else "failed", "taskId": taskId}, ensure_ascii=True))
        except Exception as e:
            logger.exception("cancel_task异常")
            self.write(json.dumps({"status": "error", "message": "撤销任务失败: {}".format(str(e))}, ensure_ascii=True))

# pause_task() - 暂停任务
class PauseTaskHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            taskId = data['taskId']
            accountType = data.get('accountType', 'stock')
            ret = pause_task(taskId, self.acc(), accountType, self.ctx())
            self.write(json.dumps({"status": "success" if ret else "failed", "taskId": taskId}, ensure_ascii=True))
        except Exception as e:
            logger.exception("pause_task异常")
            self.write(json.dumps({"status": "error", "message": "暂停任务失败: {}".format(str(e))}, ensure_ascii=True))

# resume_task() - 继续任务
class ResumeTaskHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            taskId = data['taskId']
            accountType = data.get('accountType', 'stock')
            ret = resume_task(taskId, self.acc(), accountType, self.ctx())
            self.write(json.dumps({"status": "success" if ret else "failed", "taskId": taskId}, ensure_ascii=True))
        except Exception as e:
            logger.exception("resume_task异常")
            self.write(json.dumps({"status": "error", "message": "继续任务失败: {}".format(str(e))}, ensure_ascii=True))

# do_order() - 实时触发前一根bar信号函数
class DoOrderHandler(BaseHandler):
    def post(self):
        try:
            do_order(self.ctx())
            self.write(json.dumps({"status": "success", "message": "信号已触发"}, ensure_ascii=True))
        except Exception as e:
            logger.exception("do_order异常")
            self.write(json.dumps({"status": "error", "message": "触发信号失败: {}".format(str(e))}, ensure_ascii=True))


# ============= 7. 账户/订单查询 =============
# get_trade_detail_data() - 获取交易明细(持仓/委托/成交/资金)
class TradeDetailDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        account = data.get('account', 'stock')
        datatype = data.get('datatype', 'position')
        ret = safe_call(get_trade_detail_data, self.acc(), account, datatype, 'qmt')
        if ret is None:
            ret = []
        result = [_extract_attrs(obj) for obj in ret]
        self.write(safe_json_dumps({"data": result}, ensure_ascii=True))

# get_value_by_order_id() - 根据委托号获取委托/成交信息
class ValueByOrderIdHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        orderId = data.get('orderId', '')
        accountType = data.get('accountType', 'stock')
        datatype = data.get('datatype', 'ORDER')
        ret = safe_call(get_value_by_order_id, orderId, self.acc(), accountType, datatype)
        if ret:
            self.write(safe_json_dumps({"orderId": orderId, "data": _extract_attrs(ret)}, ensure_ascii=True))
        else:
            self.write(json.dumps({"orderId": orderId, "data": {}}, ensure_ascii=True))

# get_last_order_id() - 获取最新委托/成交的委托号
class LastOrderIdHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        account = data.get('account', 'stock')
        datatype = data.get('datatype', 'ORDER')
        ret = safe_call(get_last_order_id, self.acc(), account, datatype, 'qmt')
        self.write(json.dumps({"last_order_id": ret}, ensure_ascii=True))

# can_cancel_order() - 查询委托是否可撤销
class CanCancelOrderHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        orderId = data.get('orderId', '')
        accountType = data.get('accountType', 'stock')
        ret = safe_call(can_cancel_order, orderId, self.acc(), accountType)
        self.write(json.dumps({"orderId": orderId, "can_cancel": ret}, ensure_ascii=True))

# get_debt_contract() - 获取两融负债合约明细
class DebtContractHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        accId = data.get('accId', self.acc())
        ret = safe_call(get_debt_contract, accId)
        result = [_extract_attrs(obj) for obj in (ret or [])]
        self.write(safe_json_dumps({"data": result}, ensure_ascii=True))

# get_assure_contract() - 获取两融担保标的明细
class AssureContractHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        accId = data.get('accId', self.acc())
        ret = safe_call(get_assure_contract, accId)
        result = [_extract_attrs(obj) for obj in (ret or [])]
        self.write(safe_json_dumps({"data": result}, ensure_ascii=True))

# get_enable_short_contract() - 获取可融券明细
class EnableShortContractHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        accId = data.get('accId', self.acc())
        ret = safe_call(get_enable_short_contract, accId)
        result = [_extract_attrs(obj) for obj in (ret or [])]
        self.write(safe_json_dumps({"data": result}, ensure_ascii=True))

# get_ipo_data() - 获取当日新股新债信息
class IpoDataHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        typ = data.get('type', '')
        ret = safe_call(get_ipo_data, typ)
        self.write(json.dumps({"data": ret or {}}, ensure_ascii=True, default=str))

# get_new_purchase_limit() - 获取新股申购额度
class NewPurchaseLimitHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        accid = data.get('accid', self.acc())
        ret = safe_call(get_new_purchase_limit, accid)
        self.write(json.dumps({"data": ret or {}}, ensure_ascii=True, default=str))

# cancel() - 单笔撤单
class CancelOrderHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            orderId = data.get('orderId', '')
            accountType = data.get('accountType', 'stock')
            if not orderId:
                self.write(json.dumps({"status": "error", "message": "need args orderId"}, ensure_ascii=True))
                return
            cancel(orderId, self.acc(), accountType, self.ctx())
            self.write(json.dumps({"status": "success", "orderId": orderId}, ensure_ascii=True))
        except Exception as e:
            logger.exception("cancel异常")
            self.write(json.dumps({"status": "error", "message": "撤单失败: {}".format(str(e))}, ensure_ascii=True))

# get_smart_algo_param() - 获取智能算法参数
class SmartAlgoParamHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        algo_list = data.get('algoList', '')
        if isinstance(algo_list, str):
            algos = [s.strip() for s in algo_list.split(',')] if algo_list else []
        else:
            algos = algo_list
        ret = safe_call(get_smart_algo_param, algos)
        if hasattr(ret, 'to_dict'):
            ret = ret.to_dict()
        self.write(json.dumps({"data": ret} if ret is not None else {"error": "获取智能算法参数失败"}, ensure_ascii=True, default=str))

# query_credit_account() - 查询两融账户（异步触发）
class QueryCreditAccountHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        accid = data.get('accid', self.acc())
        seq = int(data.get('seq', '0'))
        ret = safe_call(query_credit_account, accid, seq)
        self.write(json.dumps({"status": "submitted", "accid": accid, "seq": seq, "result": str(ret) if ret else "async"}, ensure_ascii=True))

# query_credit_opvolume() - 查询两融最大可下单量（异步触发）
class QueryCreditOpvolumeHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        accid = data.get('accid', self.acc())
        seq = int(data.get('seq', '0'))
        optype = data.get('optype', '')
        code = data.get('code', '')
        price = float(data.get('price', '0'))
        volume = int(data.get('volume', '0'))
        ret = safe_call(query_credit_opvolume, accid, seq, optype, code, price, volume)
        self.write(json.dumps({"status": "submitted", "accid": accid, "seq": seq, "result": str(ret) if ret else "async"}, ensure_ascii=True))


# ============= 8. 引用函数 (ext_data) =============
# ext_data() - 获取扩展数据数值
class ExtDataHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            extdataname = data.get('extdataname', '')
            stockcode = data.get('stockcode', '')
            deviation = int(data.get('deviation', '0'))
            ret = safe_call(ext_data, extdataname, stockcode, deviation, self.ctx())
            # 将不可序列化的返回值转为字符串
            if ret is not None and not isinstance(ret, (bool, int, float, str, list, dict)):
                ret = str(ret)
            result = _clean_nan({"extdataname": extdataname, "stockcode": stockcode, "value": ret})
            self.write(json.dumps(result, ensure_ascii=True))
        except Exception as e:
            logger.exception("ext_data handler error")
            self.write(json.dumps({"extdataname": "", "stockcode": "", "value": None, "error": str(e)}, ensure_ascii=True))

# ext_data_rank() - 获取扩展数据排名
class ExtDataRankHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        extdataname = data.get('extdataname', '')
        stockcode = data.get('stockcode', '')
        deviation = int(data.get('deviation', '0'))
        ret = safe_call(ext_data_rank, extdataname, stockcode, deviation, self.ctx())
        self.write(json.dumps({"extdataname": extdataname, "stockcode": stockcode, "rank": ret}, ensure_ascii=True))

# get_factor_value() - 获取因子数据
class GetFactorValueHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            factorname = data.get('factorname', '')
            stockcode = data.get('stockcode', '')
            deviation = int(data.get('deviation', '0'))
            ret = safe_call(get_factor_value, factorname, stockcode, deviation, self.ctx())
            # 将不可序列化的返回值转为字符串
            if ret is not None and not isinstance(ret, (bool, int, float, str, list, dict)):
                ret = str(ret)
            result = _clean_nan({"factorname": factorname, "stockcode": stockcode, "value": ret})
            self.write(json.dumps(result, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_factor_value handler error")
            self.write(json.dumps({"factorname": "", "stockcode": "", "value": None, "error": str(e)}, ensure_ascii=True))

# get_factor_rank() - 获取因子数据排名
class GetFactorRankHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        factorname = data.get('factorname', '')
        stockcode = data.get('stockcode', '')
        deviation = int(data.get('deviation', '0'))
        ret = safe_call(get_factor_rank, factorname, stockcode, deviation, self.ctx())
        self.write(json.dumps({"factorname": factorname, "stockcode": stockcode, "rank": ret}, ensure_ascii=True))

# ext_data_rank_range() - 获取扩展数据排名范围
class ExtDataRankRangeHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        extdataname = data.get('extdataname', '')
        stockcode = data.get('stockcode', '')
        begintime = data.get('begintime', '')
        endtime = data.get('endtime', '')
        ret = safe_call(ext_data_rank_range, extdataname, stockcode, begintime, endtime, self.ctx())
        if hasattr(ret, 'to_dict'):
            ret = ret.to_dict()
        self.write(json.dumps({"extdataname": extdataname, "stockcode": stockcode, "data": ret}, ensure_ascii=True, default=str))

# ext_data_range() - 获取扩展数据值范围
class ExtDataRangeHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        extdataname = data.get('extdataname', '')
        stockcode = data.get('stockcode', '')
        begintime = data.get('begintime', '')
        endtime = data.get('endtime', '')
        ret = safe_call(ext_data_range, extdataname, stockcode, begintime, endtime, self.ctx())
        if hasattr(ret, 'to_dict'):
            ret = ret.to_dict()
        self.write(json.dumps({"extdataname": extdataname, "stockcode": stockcode, "data": ret}, ensure_ascii=True, default=str))


# ============= 8.5 板块管理 =============
# create_sector() - 创建板块
class CreateSectorHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        parent_node = data.get('parent_node', '')
        sector_name = data.get('sector_name', '')
        overwrite = data.get('overwrite', 'true').lower() == 'true'
        if not sector_name:
            self.write(json.dumps({"status": "error", "message": "need args sector_name"}, ensure_ascii=True))
            return
        ret = safe_call(create_sector, parent_node, sector_name, overwrite)
        self.write(json.dumps({"status": "success", "sector_name": sector_name, "result": ret}, ensure_ascii=True))

# create_sector_folder() - 创建板块文件夹
class CreateSectorFolderHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        parent_node = data.get('parent_node', '')
        folder_name = data.get('folder_name', '')
        overwrite = data.get('overwrite', 'true').lower() == 'true'
        if not folder_name:
            self.write(json.dumps({"status": "error", "message": "need args folder_name"}, ensure_ascii=True))
            return
        ret = safe_call(create_sector_folder, parent_node, folder_name, overwrite)
        self.write(json.dumps({"status": "success", "folder_name": folder_name, "result": ret}, ensure_ascii=True))

# get_sector_list() - 获取板块目录
class SectorListHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        node = data.get('node', '')
        ret = safe_call(get_sector_list, node)
        self.write(json.dumps({"node": node, "data": ret or []}, ensure_ascii=True, default=str))

# reset_sector_stock_list() - 重置板块成分股
class ResetSectorStockListHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        sector = data.get('sector', '')
        stock_list = data.get('stock_list', '')
        if not sector:
            self.write(json.dumps({"error": "need args sector"}, ensure_ascii=True))
            return
        stocks = [s.strip() for s in stock_list.split(',')] if stock_list else []
        ret = safe_call(reset_sector_stock_list, sector, stocks)
        self.write(json.dumps({"status": "success" if ret else "failed", "sector": sector}, ensure_ascii=True))

# add_stock_to_sector() - 添加股票到板块
class AddStockToSectorHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        sector = data.get('sector', '')
        stock_code = data.get('stock_code', '')
        if not sector or not stock_code:
            self.write(json.dumps({"error": "need args sector and stock_code"}, ensure_ascii=True))
            return
        ret = safe_call(add_stock_to_sector, sector, stock_code)
        self.write(json.dumps({"status": "success" if ret else "failed", "sector": sector, "stock_code": stock_code}, ensure_ascii=True))

# remove_stock_from_sector() - 从板块移除股票
class RemoveStockFromSectorHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        sector = data.get('sector', '')
        stock_code = data.get('stock_code', '')
        if not sector or not stock_code:
            self.write(json.dumps({"error": "need args sector and stock_code"}, ensure_ascii=True))
            return
        ret = safe_call(remove_stock_from_sector, sector, stock_code)
        self.write(json.dumps({"status": "success" if ret else "failed", "sector": sector, "stock_code": stock_code}, ensure_ascii=True))


# ============= 9. 原有 Handler（保持兼容） =============
# get_trade_detail_data('position') - 查询持仓列表(封装格式)
class HoldingHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        account = data.get('account', 'stock')
        positions = safe_call(get_trade_detail_data, self.acc(), account, 'position') or []
        holding = {}
        for position in positions:
            stock = position.m_strInstrumentID + '.' + position.m_strExchangeID
            holding[stock] = {
                'StockCode': stock,
                'StockName': position.m_strInstrumentName,
                'Direction': position.m_nDirection,
                'Volume': position.m_nVolume,
                'OpenPrice': position.m_dOpenPrice,
                'FloatProfit': position.m_dFloatProfit,
                'MarketValue': position.m_dMarketValue,
                'StockHolder': position.m_strStockHolder,
                'FrozenVolume': position.m_nFrozenVolume,
                'CanUseVolume': position.m_nCanUseVolume,
                'OnRoadVolume': position.m_nOnRoadVolume,
                'YesterdayVolume': position.m_nYesterdayVolume,
                'LastPrice': position.m_dLastPrice,
                'ProfitRate': position.m_dProfitRate,
                'FutureTradeType': position.m_eFutureTradeType,
                'ExpireDate': position.m_strExpireDate
            }
        self.write(json.dumps(holding, ensure_ascii=True))

# get_trade_detail_data('account') - 查询总资产
class TotalMoneyHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        account = data.get('account', 'stock')
        _data = safe_call(get_trade_detail_data, self.acc(), account, 'account')
        info = _data[0] if _data else None
        if not info:
            self.write(json.dumps({"error": "资金数据获取失败"}, ensure_ascii=True))
            return
        self.write(json.dumps({"total_money": round(info.m_dBalance, 2)}, ensure_ascii=True))

# get_trade_detail_data('account') - 查询可用资金
class AvailableMoneyHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        account = data.get('account', 'stock')
        _data = safe_call(get_trade_detail_data, self.acc(), account, 'account')
        info = _data[0] if _data else None
        if not info:
            self.write(json.dumps({"error": "资金数据获取失败"}, ensure_ascii=True))
            return
        self.write(json.dumps({"available_money": round(info.m_dAvailable, 2)}, ensure_ascii=True))

# passorder(23) - 简化买入下单(封装passorder)
class BuyHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            price = float(data['price'])
            volume = int(data['volume'])
            pr_type = data.get('prType', 11)
            strategy_name = data.get('strategyName', 'qmt') or 'qmt'  # pyright: ignore[reportAny]
            reason = data.get('reason', '') or ''
            # passorder 第8参数(strategyName)必须为'qmt'，否则QMT不下单
            # 将原始 strategy_name 合并到 reason(投资备注) 中
            combined_reason = '{}_{}'.format(strategy_name, reason) if reason else strategy_name
            if not combined_reason:
                combined_reason = 'qmt'
            combined_reason = combined_reason[:24]  # 投资备注长度限制24
            before_ids = self._collect_order_ids()
            logger.info("[Buy] passorder(23, 1101, {}, {}, {}, {}, {}, 'qmt', 2, '{}')".format(
                self.acc(), stock, pr_type, price, volume, combined_reason))
            order_ref = passorder(23, 1101, self.acc(), stock, pr_type, price, volume, 'qmt', 2, combined_reason, self.ctx())
            logger.info("[Buy] passorder返回: type={}, repr={}".format(
                type(order_ref).__name__, repr(order_ref)[:200] if order_ref is not None else 'None'))
            # passorder可能返回None(异步下单)或订单号
            ref_str = str(order_ref) if order_ref is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                # 异步下单未直接返回订单号，尝试查询确认委托
                logger.info("[Buy] passorder未直接返回订单号，尝试查询确认委托")
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                    logger.info("[Buy] 委托确认成功, ref={}".format(ref_str))
                else:
                    ref_str = ""
            self.write(json.dumps({
                "status": "success", "action": "buy", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("买入下单异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# passorder(24) - 简化卖出下单(封装passorder)
class SellHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data['stock']
            price = float(data['price'])
            volume = int(data['volume'])
            pr_type = data.get('prType', 11)
            strategy_name = data.get('strategyName', 'qmt') or 'qmt'
            reason = data.get('reason', '') or ''
            # passorder 第8参数(strategyName)必须为'qmt'，否则QMT不下单
            # 将原始 strategy_name 合并到 reason(投资备注) 中
            combined_reason = '{}_{}'.format(strategy_name, reason) if reason else strategy_name
            if not combined_reason:
                combined_reason = 'qmt'
            combined_reason = combined_reason[:24]  # 投资备注长度限制24
            before_ids = self._collect_order_ids()
            logger.info("[Sell] passorder(24, 1101, {}, {}, {}, {}, {}, 'qmt', 2, '{}')".format(
                self.acc(), stock, pr_type, price, volume, combined_reason))
            order_ref = passorder(24, 1101, self.acc(), stock, pr_type, price, volume, 'qmt', 2, combined_reason, self.ctx())
            logger.info("[Sell] passorder返回: type={}, repr={}".format(
                type(order_ref).__name__, repr(order_ref)[:200] if order_ref is not None else 'None'))
            ref_str = str(order_ref) if order_ref is not None else ""
            if not ref_str or ref_str == "None" or ref_str == "0" or ref_str == "-1":
                logger.info("[Sell] passorder未直接返回订单号，尝试查询确认委托")
                found, new_ref = self._find_new_order_ref(stock, before_ids)
                if found:
                    ref_str = new_ref
                    logger.info("[Sell] 委托确认成功, ref={}".format(ref_str))
                else:
                    ref_str = ""
            self.write(json.dumps({
                "status": "success", "action": "sell", "stock": stock,
                "order_ref": ref_str if ref_str else "unknown"
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("卖出下单异常")
            self.write(json.dumps({"status": "error", "message": "下单失败: {}".format(str(e))}, ensure_ascii=True))

# get_trade_detail_data('order') - 查询委托状态列表
class OrderStatusHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        account = data.get('account', 'stock')
        orders = safe_call(get_trade_detail_data, self.acc(), account, 'order', 'qmt') or []
        rets = []
        for order in orders:
            rets.append(_extract_attrs(order))
        self.write(safe_json_dumps({"orders": rets}, ensure_ascii=True))

# cancel() - 全部撤单
class CancelAllHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            account = data.get('account', 'stock')
            orders = safe_call(get_trade_detail_data, self.acc(), account, 'order', 'qmt') or []
            canceled_list = []
            for order in orders:
                if can_cancel_order(order.m_strOrderSysID, self.acc(), account):
                    cancel(order.m_strOrderSysID, self.acc(), account, self.ctx())
                    canceled_list.append({
                        "order_sys_id": order.m_strOrderSysID,
                        "stock": order.m_strInstrumentID,
                        "volume_left": order.m_nVolumeTotal
                    })
            self.write(json.dumps({
                "status": "success",
                "message": "已发出 {} 笔撤单请求".format(len(canceled_list)),
                "canceled_orders": canceled_list
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("全部撤单异常")
            self.write(json.dumps({"status": "error", "message": "撤单失败: {}".format(str(e))}, ensure_ascii=True))


class CancelByRuleHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock = data.get('stock')
            cancel_volume = int(data.get('volume', 0))
            account = data.get('account', 'stock')
            if not stock or cancel_volume <= 0:
                self.write(json.dumps({"status": "error", "message": "参数错误：必须提供 stock 且 volume > 0"}, ensure_ascii=True))
                return
            orders = safe_call(get_trade_detail_data, self.acc(), account, 'order', 'qmt') or []
            target_orders = []
            for order in orders:
                order_code = "{}.{}".format(order.m_strInstrumentID, order.m_strExchangeID)
                if order.m_nVolumeTotal + order.m_nVolumeTraded == cancel_volume and order_code == stock and can_cancel_order(order.m_strOrderSysID, self.acc(), account):
                    target_orders.append(order)
            if not target_orders:
                self.write(json.dumps({"status": "failed", "message": "未找到符合条件的活跃订单"}, ensure_ascii=True))
                return
            canceled_ids = []
            for t_order in target_orders:
                cancel(t_order.m_strOrderSysID, self.acc(), account, self.ctx())
                canceled_ids.append(t_order.m_strOrderSysID)
            self.write(json.dumps({
                "status": "success",
                "message": "匹配到 {} 笔订单并发出撤单请求".format(len(target_orders)),
                "canceled_sys_ids": canceled_ids
            }, ensure_ascii=True))
        except Exception as e:
            logger.exception("规则撤单异常")
            self.write(json.dumps({"status": "error", "message": "撤单失败: {}".format(str(e))}, ensure_ascii=True))

# cancel() - 按股票+数量匹配规则撤单
# sys: Python版本信息
class PythonVersionHandler(BaseHandler):
    def get(self):
        import sys
        version_info = {
            "python_version": sys.version,
            "python_version_info": {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro,
                "releaselevel": sys.version_info.releaselevel,
                "serial": sys.version_info.serial,
            }
        }
        self.write(json.dumps(version_info, ensure_ascii=True))

# sys: 关闭HTTP服务
class ShutdownHandler(BaseHandler):
    def post(self):
        global _http_server
        logger.info("收到关闭请求，服务器即将停止...")
        self.write(json.dumps({"status": "success", "message": "服务器正在关闭..."}, ensure_ascii=True))
        self.finish()
        if _http_server:
            _http_server.stop()
            try:
                _http_server.close_all_connections()
            except Exception:
                pass
            _http_server = None
        IOLoop.current().add_callback(IOLoop.current().stop)

# get_trade_detail_data('deal') - 查询成交明细
class DealHandler(BaseHandler):
    def post(self):
        data = json.loads(self.request.body)
        account = data.get('account', 'stock')
        deals = safe_call(get_trade_detail_data, self.acc(), account, 'deal', 'qmt') or []
        rets = []
        for deal in deals:
            rets.append(_extract_attrs(deal))
        self.write(safe_json_dumps({"deals": rets}, ensure_ascii=True))


# ============= 路由注册 =============
# ContextInfo.get_commission() - 获取手续费率
class CommissionHandler(BaseHandler):
    def post(self):
        try:
            ret = safe_call(self.ctx().get_commission)
            self.write(safe_json_dumps({"commission": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_commission handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_slippage() - 获取滑点
class SlippageHandler(BaseHandler):
    def post(self):
        try:
            ret = safe_call(self.ctx().get_slippage)
            self.write(safe_json_dumps({"slippage": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_slippage handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.set_commission() - 设置手续费率
class SetCommissionHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            comtype = data.get('comtype', '')
            com = data.get('com', 'none')
            if com == 'none':
                safe_call(self.ctx().set_commission, 0, comtype)
            else:
                safe_call(self.ctx().set_commission, comtype, com)
            self.write(json.dumps({"status": "success"}, ensure_ascii=True))
        except Exception as e:
            logger.exception("set_commission handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.set_slippage() - 设置滑点
class SetSlippageHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            b_flag = data.get('b_flag', '')
            slippage = data.get('slippage', 'none')
            if slippage == 'none':
                safe_call(self.ctx().set_slippage, b_flag)
            else:
                safe_call(self.ctx().set_slippage, b_flag, slippage)
            self.write(json.dumps({"status": "success"}, ensure_ascii=True))
        except Exception as e:
            logger.exception("set_slippage handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_net_value() - 获取净值
class NetValueHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            barpositon = int(data.get('barpositon', '0'))
            ret = safe_call(self.ctx().get_net_value, barpositon)
            self.write(safe_json_dumps({"net_value": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_net_value handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_raw_financial_data() - 获取原始财务数据
class RawFinancialDataHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            fieldList = data.get('fieldList', '')
            stockList = data.get('stockList', '')
            startDate = data.get('startDate', '')
            endDate = data.get('endDate', '')
            report_type = data.get('report_type', 'report_time')
            data_type = data.get('data_type', 'dict')
            fields = [f.strip() for f in fieldList.split(',')] if fieldList else []
            stocks = [s.strip() for s in stockList.split(',')] if stockList else []
            ret = safe_call(self.ctx().get_raw_financial_data, fields, stocks, startDate, endDate, report_type, data_type)
            if ret is None:
                self.write(json.dumps({"error": "获取原始财务数据失败，API返回None"}, ensure_ascii=True))
            else:
                self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_raw_financial_data handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_north_finance_change() - 获取北向资金变化
class NorthFinanceChangeHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            period = data.get('period', '')
            ret = safe_call(self.ctx().get_north_finance_change, period)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_north_finance_change handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# get_hkt_exchange_rate() - 获取港股通汇率
class HktExchangeRateHandler(BaseHandler):
    def post(self):
        try:
            func = globals().get('get_hkt_exchange_rate')
            if func:
                ret = safe_call(func)
            else:
                ret = safe_call(self.ctx().get_hkt_exchange_rate)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_hkt_exchange_rate handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_hkt_details() - 获取港股通明细
class HktDetailsHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock_code = data.get('stock_code', '')
            ret = safe_call(self.ctx().get_hkt_details, stock_code)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_hkt_details handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_hkt_statistics() - 获取港股通统计
class HktStatisticsHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock_code = data.get('stock_code', '')
            ret = safe_call(self.ctx().get_hkt_statistics, stock_code)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_hkt_statistics handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# get_market_time() - 获取市场时间
class MarketTimeHandler(BaseHandler):
    def post(self):
        try:
            func = globals().get('get_market_time')
            if func:
                ret = safe_call(func)
            else:
                ret = safe_call(self.ctx().get_market_time)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_market_time handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_option_detail_data() - 获取期权详细数据(新接口)
class OptionDetailDataHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stockcode = data.get('stockcode', '')
            ret = safe_call(self.ctx().get_option_detail_data, stockcode)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_option_detail_data handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.load_stk_list() - 加载板块成分股列表
class LoadStkListHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            dirfile = data.get('dirfile', '')
            namefile = data.get('namefile', '')
            ret = safe_call(self.ctx().load_stk_list, dirfile, namefile)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("load_stk_list handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.load_stk_vol_list() - 加载板块成分股成交量列表
class LoadStkVolListHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            dirfile = data.get('dirfile', '')
            namefile = data.get('namefile', '')
            ret = safe_call(self.ctx().load_stk_vol_list, dirfile, namefile)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("load_stk_vol_list handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# ContextInfo.get_ext_all_data() - 已被QMT官方删除
class ExtAllDataHandler(BaseHandler):
    def post(self):
        try:
            self.write(json.dumps({"error": "get_ext_all_data已被QMT官方删除，请使用ext_data/ext_data_range替代"}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_ext_all_data handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# stoploss_limitprice() - 限价止损
class StoplossLimitpriceHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stoplossCode = data.get('stoplossCode', '')
            orderType = int(data.get('orderType', '0'))
            opType = int(data.get('opType', '0'))
            account = data.get('account', self.acc())
            stockCode = data.get('stockCode', '')
            stopPrice = float(data.get('stopPrice', '0'))
            stopAmount = float(data.get('stopAmount', '0'))
            priceType = int(data.get('priceType', '0'))
            price = float(data.get('price', '0'))
            volume = int(data.get('volume', '0'))
            strategyName = data.get('strategyName', '')
            quickTrade = int(data.get('quickTrade', '0'))
            userid = data.get('userid', '')
            func = globals().get('stoploss_limitprice')
            if func:
                ret = safe_call(func, stoplossCode, orderType, opType, account, stockCode,
                                stopPrice, stopAmount, priceType, price, volume,
                                strategyName, quickTrade, userid, self.ctx())
            else:
                ret = None
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("stoploss_limitprice handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# stoploss_marketprice() - 市价止损
class StoplossMarketpriceHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stoplossCode = data.get('stoplossCode', '')
            orderType = int(data.get('orderType', '0'))
            opType = int(data.get('opType', '0'))
            account = data.get('account', self.acc())
            stockCode = data.get('stockCode', '')
            triggerPrice = float(data.get('triggerPrice', '0'))
            stopAmount = float(data.get('stopAmount', '0'))
            priceType = int(data.get('priceType', '0'))
            volume = int(data.get('volume', '0'))
            strategyName = data.get('strategyName', '')
            quickTrade = int(data.get('quickTrade', '0'))
            userid = data.get('userid', '')
            func = globals().get('stoploss_marketprice')
            if func:
                ret = safe_call(func, stoplossCode, orderType, opType, account, stockCode,
                                triggerPrice, stopAmount, priceType, volume,
                                strategyName, quickTrade, userid, self.ctx())
            else:
                ret = None
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("stoploss_marketprice handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# make_option_combination() - 期权组合构建
class MakeOptionCombinationHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            account = data.get('account', self.acc())
            optCombList = data.get('optCombList', [])
            hedgeRatio = data.get('hedgeRatio', '')
            quickTrade = int(data.get('quickTrade', '0'))
            userid = data.get('userid', '')
            func = globals().get('make_option_combination')
            if func:
                ret = safe_call(func, account, optCombList, hedgeRatio, quickTrade, userid, self.ctx())
            else:
                ret = None
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("make_option_combination handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# release_option_combination() - 期权组合拆解
class ReleaseOptionCombinationHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            account = data.get('account', self.acc())
            optCombList = data.get('optCombList', [])
            quickTrade = int(data.get('quickTrade', '0'))
            userid = data.get('userid', '')
            func = globals().get('release_option_combination')
            if func:
                ret = safe_call(func, account, optCombList, quickTrade, userid, self.ctx())
            else:
                ret = None
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("release_option_combination handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# get_basket() - 获取一篮子股票
class GetBasketHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            basket_name = data.get('basket_name', '')
            func = globals().get('get_basket')
            if func:
                ret = safe_call(func, basket_name)
            else:
                ret = safe_call(self.ctx().get_basket, basket_name)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_basket handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# set_basket() - 设置一篮子股票
class SetBasketHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            basket_name = data.get('basket_name', '')
            stock_list = data.get('stock_list', [])
            func = globals().get('set_basket')
            if func:
                ret = safe_call(func, basket_name, stock_list)
            else:
                ret = safe_call(self.ctx().set_basket, basket_name, stock_list)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("set_basket handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# call_formula() - 调用公式
class CallFormulaHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            formula_name = data.get('formula_name', '')
            params = data.get('params', [])
            func = globals().get('call_formula')
            if func:
                ret = safe_call(func, formula_name, *params)
            else:
                ret = safe_call(self.ctx().call_formula, formula_name, *params)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("call_formula handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# get_unclosed_compacts() - 获取未平仓合约
class UnclosedCompactsHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            account = data.get('account', self.acc())
            stockCode = data.get('stockCode', '')
            compactType = data.get('compactType', '')
            func = globals().get('get_unclosed_compacts')
            if func:
                ret = safe_call(func, account, stockCode, compactType)
            else:
                ret = safe_call(self.ctx().get_unclosed_compacts, account, stockCode, compactType)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_unclosed_compacts handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# get_closed_compacts() - 获取已平仓合约
class ClosedCompactsHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            account = data.get('account', self.acc())
            stockCode = data.get('stockCode', '')
            compactType = data.get('compactType', '')
            func = globals().get('get_closed_compacts')
            if func:
                ret = safe_call(func, account, stockCode, compactType)
            else:
                ret = safe_call(self.ctx().get_closed_compacts, account, stockCode, compactType)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_closed_compacts handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# get_option_subject_position() - 获取期权标的持仓
class OptionSubjectPositionHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            account = data.get('account', self.acc())
            optCode = data.get('optCode', '')
            func = globals().get('get_option_subject_position')
            if func:
                ret = safe_call(func, account, optCode)
            else:
                ret = safe_call(self.ctx().get_option_subject_position, account, optCode)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_option_subject_position handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# get_comb_option() - 获取期权组合
class CombOptionHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            account = data.get('account', self.acc())
            func = globals().get('get_comb_option')
            if func:
                ret = safe_call(func, account)
            else:
                ret = safe_call(self.ctx().get_comb_option, account)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("get_comb_option handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))

# st_status() - 获取ST状态
class StStatusHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            stock_code = data.get('stock_code', '')
            func = globals().get('st_status')
            if func:
                ret = safe_call(func, stock_code)
            else:
                # 备注说明 get_st_status
                func2 = globals().get('get_st_status')
                if func2:
                    ret = safe_call(func2, stock_code)
                else:
                    ret = safe_call(self.ctx().get_his_st_data, stock_code)
            self.write(safe_json_dumps({"data": ret}, ensure_ascii=True))
        except Exception as e:
            logger.exception("st_status handler error")
            self.write(json.dumps({"error": str(e)}, ensure_ascii=True))


# ============= 路由注册 =============
def make_app():
    return Application([

        # 原有兼容路由
        (r"/api/holding", HoldingHandler),
        (r"/api/money/total", TotalMoneyHandler),
        (r"/api/money/available", AvailableMoneyHandler),
        (r"/api/order/buy", BuyHandler),
        (r"/api/order/sell", SellHandler),
        (r"/api/order/status", OrderStatusHandler),
        (r"/api/order/cancel_all", CancelAllHandler),
        (r"/api/order/cancel_order", CancelByRuleHandler),
        (r"/api/order/deal", DealHandler),

        # ContextInfo 属性
        (r"/api/context/period", ContextPeriodHandler),
        (r"/api/context/barpos", ContextBarposHandler),
        (r"/api/context/time_tick_size", ContextTimeTickSizeHandler),
        (r"/api/context/stockcode", ContextStockCodeHandler),
        (r"/api/context/dividend_type", ContextDividendTypeHandler),
        (r"/api/context/market", ContextMarketHandler),
        (r"/api/context/do_back_test", ContextDoBackTestHandler),
        (r"/api/context/benchmark", ContextBenchmarkHandler),
        (r"/api/context/capital", ContextCapitalHandler),
        (r"/api/context/universe", ContextUniverseHandler),
        (r"/api/context/start", ContextStartHandler),
        (r"/api/context/end", ContextEndHandler),

        # 数据查询
        (r"/api/data/stock_name", StockNameHandler),
        (r"/api/data/open_date", OpenDateHandler),
        (r"/api/data/last_volume", LastVolumeHandler),
        (r"/api/data/bar_timetag", BarTimetagHandler),
        (r"/api/data/tick_timetag", TickTimetagHandler),
        (r"/api/data/sector", SectorHandler),
        (r"/api/data/industry", IndustryHandler),
        (r"/api/data/stock_list_in_sector", StockListInSectorHandler),
        (r"/api/data/weight_in_index", WeightInIndexHandler),
        (r"/api/data/contract_multiplier", ContractMultiplierHandler),
        (r"/api/data/risk_free_rate", RiskFreeRateHandler),
        (r"/api/data/date_location", DateLocationHandler),
        (r"/api/data/history_data", HistoryDataHandler),
        (r"/api/data/market_data", MarketDataHandler),
        (r"/api/data/market_data_ex", MarketDataExHandler),
        (r"/api/data/full_tick", FullTickHandler),
        (r"/api/data/divid_factors", DividFactorsHandler),
        (r"/api/data/main_contract", MainContractHandler),
        (r"/api/data/timetag_to_datetime", TimetagToDatetimeHandler),
        (r"/api/data/total_share", TotalShareHandler),
        (r"/api/data/trading_dates", TradingDatesHandler),
        (r"/api/data/svol", SvolHandler),
        (r"/api/data/bvol", BvolHandler),
        (r"/api/data/longhubang", LonghubangHandler),
        (r"/api/data/top10_share_holder", Top10ShareHolderHandler),
        (r"/api/data/option_detail", OptionDetailHandler),
        (r"/api/data/turnover_rate", TurnoverRateHandler),
        (r"/api/data/etf_info", EtfInfoHandler),
        (r"/api/data/etf_iopv", EtfIopvHandler),
        (r"/api/data/instrumentdetail", InstrumentDetailHandler),
        (r"/api/data/contract_expire_date", ContractExpireDateHandler),
        (r"/api/data/option_undl_data", OptionUndlDataHandler),
        (r"/api/data/financial_data", FinancialDataHandler),
        (r"/api/data/factor_data", FactorDataHandler),
        (r"/api/data/his_st_data", HisStDataHandler),
        (r"/api/data/his_index_data", HisIndexDataHandler),
        (r"/api/data/all_subscription", AllSubscriptionHandler),
        (r"/api/data/option_list", OptionListHandler),
        (r"/api/data/his_contract_list", HisContractListHandler),
        (r"/api/data/option_iv", OptionIvHandler),
        (r"/api/data/bsm_price", BsmPriceHandler),
        (r"/api/data/bsm_iv", BsmIvHandler),
        (r"/api/data/local_data", LocalDataHandler),
        (r"/api/data/close_price", ClosePriceHandler),
        (r"/api/data/close_price_by_date", ClosePriceByDateHandler),
        (r"/api/data/download_history_data", DownloadHistoryDataHandler),

        # 订阅
        (r"/api/data/subscribe_quote", SubscribeQuoteHandler),
        (r"/api/data/unsubscribe_quote", UnsubscribeQuoteHandler),
        (r"/api/data/subscribe_whole_quote", SubscribeWholeQuoteHandler),
        (r"/api/data/sub_tick_cache", SubTickCacheHandler),
        (r"/api/data/sub_quote_cache", SubQuoteCacheHandler),

        # ContextInfo 设置
        (r"/api/context/set_universe", SetUniverseHandler),
        (r"/api/context/set_account", SetAccountHandler),
        (r"/api/context/set_output_index_property", SetOutputIndexPropertyHandler),

        # 判定函数
        (r"/api/check/is_last_bar", IsLastBarHandler),
        (r"/api/check/is_new_bar", IsNewBarHandler),
        (r"/api/check/is_suspended_stock", IsSuspendedStockHandler),
        (r"/api/check/is_sector_stock", IsSectorStockHandler),
        (r"/api/check/is_typed_stock", IsTypedStockHandler),
        (r"/api/check/get_industry_name_of_stock", GetIndustryNameOfStockHandler),

        # 交易
        (r"/api/trade/passorder", PassorderHandler),
        (r"/api/trade/algo_passorder", AlgoPassorderHandler),
        (r"/api/trade/smart_algo_passorder", SmartAlgoPassorderHandler),
        (r"/api/trade/order_lots", OrderLotsHandler),
        (r"/api/trade/order_value", OrderValueHandler),
        (r"/api/trade/order_percent", OrderPercentHandler),
        (r"/api/trade/order_target_value", OrderTargetValueHandler),
        (r"/api/trade/order_target_percent", OrderTargetPercentHandler),
        (r"/api/trade/order_shares", OrderSharesHandler),

        # 期货交易
        (r"/api/trade/futures/buy_open", FuturesBuyOpenHandler),
        (r"/api/trade/futures/buy_close_tdayfirst", FuturesBuyCloseTdayFirstHandler),
        (r"/api/trade/futures/buy_close_ydayfirst", FuturesBuyCloseYdayFirstHandler),
        (r"/api/trade/futures/sell_open", FuturesSellOpenHandler),
        (r"/api/trade/futures/sell_close_tdayfirst", FuturesSellCloseTdayFirstHandler),
        (r"/api/trade/futures/sell_close_ydayfirst", FuturesSellCloseYdayFirstHandler),

        # 任务管理
        (r"/api/trade/cancel_task", CancelTaskHandler),
        (r"/api/trade/pause_task", PauseTaskHandler),
        (r"/api/trade/resume_task", ResumeTaskHandler),
        (r"/api/trade/do_order", DoOrderHandler),

        # 账户/订单查询
        (r"/api/trade/trade_detail_data", TradeDetailDataHandler),
        (r"/api/trade/value_by_order_id", ValueByOrderIdHandler),
        (r"/api/trade/last_order_id", LastOrderIdHandler),
        (r"/api/trade/can_cancel_order", CanCancelOrderHandler),
        (r"/api/trade/debt_contract", DebtContractHandler),
        (r"/api/trade/assure_contract", AssureContractHandler),
        (r"/api/trade/enable_short_contract", EnableShortContractHandler),
        (r"/api/trade/ipo_data", IpoDataHandler),
        (r"/api/trade/new_purchase_limit", NewPurchaseLimitHandler),
        (r"/api/trade/cancel", CancelOrderHandler),
        (r"/api/trade/smart_algo_param", SmartAlgoParamHandler),
        (r"/api/trade/query_credit_account", QueryCreditAccountHandler),
        (r"/api/trade/query_credit_opvolume", QueryCreditOpvolumeHandler),

        # 引用函数
        (r"/api/ext/ext_data", ExtDataHandler),
        (r"/api/ext/ext_data_rank", ExtDataRankHandler),
        (r"/api/ext/get_factor_value", GetFactorValueHandler),
        (r"/api/ext/get_factor_rank", GetFactorRankHandler),
        (r"/api/ext/ext_data_rank_range", ExtDataRankRangeHandler),
        (r"/api/ext/ext_data_range", ExtDataRangeHandler),

        # 板块管理
        (r"/api/sector/create", CreateSectorHandler),
        (r"/api/sector/create_folder", CreateSectorFolderHandler),
        (r"/api/sector/list", SectorListHandler),
        (r"/api/sector/reset_stocks", ResetSectorStockListHandler),
        (r"/api/sector/add_stock", AddStockToSectorHandler),
        (r"/api/sector/remove_stock", RemoveStockFromSectorHandler),

        # 系统
        (r"/api/data/commission", CommissionHandler),
        (r"/api/data/slippage", SlippageHandler),
        (r"/api/data/net_value", NetValueHandler),
        (r"/api/data/raw_financial_data", RawFinancialDataHandler),
        (r"/api/data/north_finance_change", NorthFinanceChangeHandler),
        (r"/api/data/hkt_exchange_rate", HktExchangeRateHandler),
        (r"/api/data/hkt_details", HktDetailsHandler),
        (r"/api/data/hkt_statistics", HktStatisticsHandler),
        (r"/api/data/market_time", MarketTimeHandler),
        (r"/api/data/option_detail_data", OptionDetailDataHandler),
        (r"/api/data/load_stk_list", LoadStkListHandler),
        (r"/api/data/load_stk_vol_list", LoadStkVolListHandler),
        (r"/api/data/get_basket", GetBasketHandler),
        (r"/api/data/set_basket", SetBasketHandler),
        (r"/api/data/st_status", StStatusHandler),

        # 查询API - ContextInfo属性
        (r"/api/context/set_commission", SetCommissionHandler),
        (r"/api/context/set_slippage", SetSlippageHandler),

        # 查询API - 扩展数据
        (r"/api/ext/ext_all_data", ExtAllDataHandler),
        (r"/api/ext/call_formula", CallFormulaHandler),

        # 查询API - 交易
        (r"/api/trade/stoploss_limitprice", StoplossLimitpriceHandler),
        (r"/api/trade/stoploss_marketprice", StoplossMarketpriceHandler),
        (r"/api/trade/make_option_combination", MakeOptionCombinationHandler),
        (r"/api/trade/release_option_combination", ReleaseOptionCombinationHandler),
        (r"/api/trade/unclosed_compacts", UnclosedCompactsHandler),
        (r"/api/trade/closed_compacts", ClosedCompactsHandler),
        (r"/api/data/option_subject_position", OptionSubjectPositionHandler),
        (r"/api/data/comb_option", CombOptionHandler),

        # ϵͳ
        (r"/api/sys/python_version", PythonVersionHandler),
        (r"/api/sys/shutdown", ShutdownHandler),

    ], debug=False)


def _kill_port_occupier(port):
    """杀掉占用指定端口的外部进程（排除当前QMT进程自身）
    注意: subprocess不在QMT白名单中，改用os.system"""
    try:
        my_pid = os.getpid()
        # 用os.system替代subprocess（QMT白名单限制）
        os.system('netstat -ano | findstr :{} | findstr LISTENING > _port_check.tmp 2>&1'.format(port))
        try:
            with open('_port_check.tmp', 'r') as f:
                result = f.read().strip()
            os.remove('_port_check.tmp')
        except Exception:
            result = ''
        if result:
            for line in result.split('\n'):
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != my_pid:
                        logger.info("端口 {} 被外部进程 PID:{} 占用，尝试终止".format(port, pid))
                        os.system('taskkill /F /PID {}'.format(pid))
                        time.sleep(1)
                        logger.info("已终止进程 PID:{}".format(pid))
                    elif pid.isdigit() and int(pid) == my_pid:
                        logger.info("端口 {} 被当前进程(PID:{})占用，依赖SO_REUSEADDR解决".format(port, my_pid))
    except Exception as e:
        logger.info("检查端口占用: {}".format(e))


def _health_check():
    """IOLoop启动后自检：用非阻塞HTTP请求验证服务是否真正可用"""
    from tornado.httpclient import AsyncHTTPClient
    url = "http://127.0.0.1:{}/api/sys/python_version".format(PORT)

    def _on_response(response):
        if response.error:
            logger.error("QMT HTTP Server 自检失败！服务可能未正常启动: {}".format(response.error))
        else:
            logger.info("QMT HTTP Server 自检通过！服务已就绪 http://127.0.0.1:{}".format(PORT))

    try:
        http = AsyncHTTPClient()
        http.fetch(url, _on_response, method='GET',
                   headers={'X-Token': TOKEN}, request_timeout=5)
    except Exception as e:
        logger.error("QMT HTTP Server 自检请求失败: {}".format(e))


def init(ContextInfo):
    global _http_server
    try:
        # 先清理可能残留的旧server
        if _http_server is not None:
            try:
                _http_server.stop()
            except Exception:
                pass
            _http_server = None

        ContextInfo.accountID = ACCOUNT_ID
        if account:
            ContextInfo.accountID = str(account)

        # 设置交易账号（passorder/get_trade_detail_data等交易函数依赖此设置）
        # 缺少set_account会导致passorder静默返回None、get_trade_detail_data返回空
        try:
            ContextInfo.set_account(ContextInfo.accountID)
            logger.info("已设置交易账号: {}".format(ContextInfo.accountID))
        except Exception as e:
            logger.error("set_account失败: {}".format(e))

        address = '127.0.0.1'

        logger.info("QMT HTTP Server 启动于 http://{}:{} (账号ID: {})".format(address, PORT, ContextInfo.accountID))
        app = make_app()
        app.ContextInfo = ContextInfo
        app.accountID = ContextInfo.accountID

        from tornado.httpserver import HTTPServer
        # 直接用HTTPServer.listen()，不使用socket包（QMT白名单限制）
        # 端口占用时先清理再启动
        _kill_port_occupier(PORT)
        _http_server = HTTPServer(app)
        try:
            _http_server.listen(PORT, address=address)
        except Exception as listen_err:
            logger.info("listen失败: {}, 再次清理端口占用后重试".format(listen_err))
            _kill_port_occupier(PORT)
            time.sleep(1)
            _http_server = HTTPServer(app)
            _http_server.listen(PORT, address=address)
        logger.info("QMT HTTP Server 已监听 http://{}:{}".format(address, PORT))
        # 注册自检回调：IOLoop启动1秒后自动请求自身验证服务可用
        IOLoop.current().call_later(1.0, _health_check)
        IOLoop.current().start()
    except Exception as e:
        logger.exception("server start failed: {}".format(e))


_handlebar_count = [0]

def handlebar(ContextInfo):
    """QMT策略handlebar回调 - 非直接交易数据通过查询接口直接用get_full_tick获取"""
    _handlebar_count[0] += 1


def stop(ContextInfo):
    """QMT策略停止时回调，关闭HTTP服务监听"""
    global _http_server
    try:
        if _http_server:
            # 先停止接受新连接
            _http_server.stop()
            # 关闭所有已有连接
            try:
                _http_server.close_all_connections()
            except Exception:
                pass
            _http_server = None
            logger.info("QMT HTTP Server 已停止监听")
        # 停止IOLoop，使init()中的start()返回
        IOLoop.current().add_callback(IOLoop.current().stop)
    except Exception as e:
        logger.exception("server stop failed: {}".format(e))

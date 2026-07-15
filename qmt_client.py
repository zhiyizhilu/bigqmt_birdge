# -*- coding: utf-8 -*-
# author公众号：可转债量化分析
import requests
import json

TOKEN = "123456789"


class QMTClient:
    def __init__(self, base_url="http://127.0.0.1:8888"):
        """QMT客户端初始化

        参数:
            base_url: str, QMT HTTP服务地址，默认为 'http://127.0.0.1:8888'

        返回:
            无（构造函数）
        """
        self.base = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json; charset=utf-8"})
        self.session.headers.update({"X-Token": TOKEN})

    def _req(self, method, path, **kwargs):
        """内部HTTP请求方法，统一处理请求发送、响应解析和异常捕获

        参数:
            method: str, HTTP方法，如 'GET' 或 'POST'
            path: str, API路径，如 '/api/holding'
            **kwargs: dict, 传递给 requests.Session.request 的额外参数（如 json=）

        返回:
            dict - 请求结果，直接返回服务端 JSON 响应体。
            不同 API 的返回格式各异（无统一 'data' 包装层），具体见各方法文档。
            请求失败时:
            {
                "error": "错误描述",    # str, 错误信息
                "status_code": 500,    # int, HTTP状态码
                "raw_body": "..."      # str, 原始响应体（可选）
            }
        """
        url = "{}{}".format(self.base, path)
        try:
            resp = self.session.request(method, url, timeout=10, **kwargs)
            # 强制用utf-8解码，避免Windows下requests默认用ISO-8859-1导致中文乱码
            resp.encoding = 'utf-8'
            try:
                result = resp.json()
                if resp.status_code >= 400 and isinstance(result, dict):
                    result["status_code"] = resp.status_code
                return result
            except ValueError as je:
                if resp.status_code >= 400:
                    return {"error": "HTTP {} - {}".format(resp.status_code, resp.text[:200]), "status_code": resp.status_code}
                print("  [DEBUG] JSON解析失败, path={}, status={}, body={}".format(
                    path, resp.status_code, resp.text[:300]))
                return {"error": "JSON解析失败: {}".format(str(je)), "status_code": resp.status_code, "raw_body": resp.text[:500]}
        except requests.RequestException as e:
            resp_text = ''
            if hasattr(e, 'response') and e.response is not None:
                resp_text = e.response.text[:300]
            return {"error": str(e), "status_code": getattr(e.response, 'status_code', 500), "raw_body": resp_text}

    def get_holding(self, account='stock'):
        """查询当前持仓

        参数:
            account: str, 账户类型，默认 'stock'（股票账户）

        返回:
            dict - 以股票代码为key的持仓字典
            {
                "513090.SH": {
                    "StockCode": "513090.SH",           # str, 股票代码（带交易所后缀）
                    "StockName": "香港证券ETF易方达",     # str, 股票名称
                    "Direction": 48,                     # int, 方向
                    "Volume": 100,                       # int, 持仓数量
                    "OpenPrice": 18.33,                  # float, 开仓价
                    "FloatProfit": 0.0,                  # float, 浮动盈亏
                    "MarketValue": 1833.0,               # float, 市值
                    "StockHolder": "A121871190",         # str, 股东代码
                    "FrozenVolume": 0,                   # int, 冻结数量
                    "CanUseVolume": 100,                 # int, 可用数量
                    "OnRoadVolume": 0,                   # int, 在途数量
                    "YesterdayVolume": 100,              # int, 昨日数量
                    "LastPrice": 18.33,                  # float, 最新价
                    "ProfitRate": 0.0,                   # float, 盈亏比例
                    "FutureTradeType": 48,               # int, 期货交易类型
                    "ExpireDate": ""                     # str, 到期日
                },
                ...
            }
        """
        return self._req('POST', f'/api/holding', json={"account": account})

    def get_total_money(self, account='stock'):
        """查询总资金

        参数:
            account: str, 账户类型，默认 'stock'（股票账户）

        返回:
            dict - 总资金信息
            {
                "total_money": 9988177.97          # float, 总资产金额
            }
        """
        return self._req('POST', f'/api/money/total', json={"account": account})

    def get_available_money(self, account='stock'):
        """查询可用资金

        参数:
            account: str, 账户类型，默认 'stock'（股票账户）

        返回:
            dict - 可用资金信息
            {
                "available_money": 9130915.27      # float, 可用资金金额
            }
        """
        return self._req('POST', f'/api/money/available', json={"account": account})

    def buy_stock(self, stock, price, volume, pr_type=11, strategy_name='', reason=''):
        """买入股票

        prType(下单选价类型):（特别的对于套利：这个prType只对篮子起作用,期货的采用默认的方式）
        -1:无效(只对于algo_passorder起作用)
        0:卖5价
        1:卖4价
        2:卖3价
        3:卖2价
        4:卖1价
        5:最新价
        6:买1价
        7:买2价(组合不支持)
        8:买3价(组合不支持)
        9:买4价(组合不支持)
        10:买5价(组合不支持)
        11:（指定价）模型价（只对单股情况支持,对组合交易不支持）
        12:涨跌涨停价
        13:挂单价
        14:对手价
        18:市价最优价[郑商所][期货]
        19:市价即成剩撤[大商所][期货]
        20:市价全额成交或撤[大商所][期货]
        21:市价最优一档即成剩撤[中金所][期货]
        22:市价最优五档即成剩撤[中金所][期货]
        23:市价最优一档即成剩转[中金所][期货]
        24:市价最优五档即成剩转[中金所][期货]
        26:限价即时全部成交否则撤单[上交所|深交所][期权]
        27:市价即成剩撤[上交所][期权]
        28:市价即全成否则撤[上交所][期权]
        29:市价剩转限价[上交所][期权]
        42:最优五档即时成交剩余撤销申报[上交所][股票]
        43:最优五档即时成交剩转限价申报[上交所][股票]
        44:对手方最优价格委托[上交所[股票]][深交所[股票][期权]]
        45:本方最优价格委托[上交所[股票]][深交所[股票][期权]]
        46:即时成交剩余撤销委托[深交所][股票][期权]
        47:最优五档即时成交剩余撤销委托[深交所][股票][期权]
        48:全额成交或撤销委托[深交所][股票][期权]
        49:盘后定价

        参数:
            stock: str, 股票代码，如 '600000.SH'
            price: float, 下单价格
            volume: int, 下单数量（股）
            pr_type: int, 选价类型，默认 11（指定价/模型价）
            strategy_name: str, 投资备注/策略名称，如 'DDE_Buy'，默认为空
            reason: str, 下单原因，如 '止盈'，默认为空

        返回:
            dict - 下单结果
            下单成功:
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型
                "stock": "600000.SH",              # str, 股票代码
                "message": "下单成功"
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述",              # str, 错误信息
                "stock": "600000.SH"
            }
            下单未产生委托（如无对应账户）:
            {
                "status": "warning",
                "message": "期货无账户",            # str, 警告信息
                "stock": "600000.SH"
            }
        """
        return self._req('POST', '/api/order/buy', json={
            "stock": stock, "price": price, "volume": volume, "prType": pr_type,
            "strategyName": strategy_name, "reason": reason
        })

    def sell_stock(self, stock, price, volume, pr_type=11, strategy_name='', reason=''):
        """卖出股票

        prType(下单选价类型): 同 buy_stock 中的说明

        参数:
            stock: str, 股票代码，如 '600000.SH'
            price: float, 下单价格
            volume: int, 下单数量（股）
            pr_type: int, 选价类型，默认 11（指定价/模型价）
            strategy_name: str, 投资备注/策略名称，如 'DDE_Sell'，默认为空
            reason: str, 下单原因，如 '止盈'，默认为空

        返回:
            dict - 下单结果
            下单成功:
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "sell",                  # str, 操作类型
                "stock": "600000.SH",              # str, 股票代码
                "message": "下单成功"
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述",              # str, 错误信息
                "stock": "600000.SH"
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "警告信息",              # str, 警告信息
                "stock": "600000.SH"
            }
        """
        return self._req('POST', '/api/order/sell', json={
            "stock": stock, "price": price, "volume": volume, "prType": pr_type,
            "strategyName": strategy_name, "reason": reason
        })

    def get_sector(self, sector):
        """查询板块成分股

        参数:
            sector: str, 板块代码，如 '000300.SH'（沪深300）

        返回:
            dict - 板块成分股列表
            {
                "data": [
                    "600000.SH",                    # str, 股票代码
                    "600009.SH",
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/sector', json={
            "sector": sector,
        })

    def get_industry(self, industry):
        """查询行业成分股

        参数:
            industry: str, 行业名称，如 'CSRC餐饮业'

        返回:
            dict - 行业成分股列表
            {
                "data": [
                    "600000.SH",                    # str, 股票代码
                    "000001.SZ",
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/industry', json={
            "industry": industry,
        })

    def get_full_tick(self, stocks):
        """获取最新全推行情数据

        参数:
            stocks: str, 股票代码，如 '600000.SH'（多只用逗号分隔）

        返回:
            dict - 以股票代码为key的行情字典（无 'data' 包装层）
            {
                "600000.SH": {
                    "time": 1783308600000,            # int, 时间戳(毫秒)
                    "timetag": "20260706 11:30:00",   # str, 时间标签
                    "lastPrice": 7.55,                # float, 最新价
                    "open": 7.52,                     # float, 开盘价
                    "high": 7.60,                     # float, 最高价
                    "low": 7.48,                      # float, 最低价
                    "lastClose": 7.50,                # float, 昨收价
                    "volume": 1000000,                # float, 成交量
                    "amount": 7550000.0,              # float, 成交额
                    "pvolume": 100000000,             # float, 成交量(股)
                    "stockStatus": 3,                 # int, 股票状态
                    "openInt": 13,                    # int, 未平仓量
                    "settlementPrice": 0.0,           # float, 结算价
                    "lastSettlementPrice": 7.50,      # float, 昨结算价
                    "bidPrice": [7.54, 7.53, ...],    # list, 买1-5价
                    "askPrice": [7.55, 7.56, ...],    # list, 卖1-5价
                    "bidVol": [500, 300, ...],        # list, 买1-5量
                    "askVol": [300, 200, ...]         # list, 卖1-5量
                },
                ...
            }
        """
        return self._req('POST', f'/api/data/full_tick', json={
            "stocks": stocks})

    def get_market_data_ex(self, stock_code, fields='', period='follow', start_time='', end_time='', count=-1, dividend_type='follow'):
        """获取K线行情数据（扩展版）

        参数:
            stock_code: str 或 list, 股票代码，如 '600000.SH' 或 ['600000.SH', '000001.SZ']
            fields: str 或 list, 字段列表，如 ['open', 'high', 'low', 'close']，默认为空（返回全部字段）
            period: str, K线周期，默认 'follow'。可选值:
                '1m', '5m', '15m', '30m', '1h', '1d', '1w', '1mon', 'follow'
            start_time: str, 开始时间，如 '20240101'，默认为空
            end_time: str, 结束时间，如 '20241231'，默认为空
            count: int, 数据条数，-1表示全部，默认 -1
            dividend_type: str, 复权类型，默认 'follow'。可选值:
                'none'(不复权), 'front'(前复权), 'back'(后复权), 'follow'

        返回:
            dict - K线行情数据
            {
                "data": {
                    "600000.SH": {
                        "times": [1704067200000, ...],    # list[int], 时间戳列表(毫秒)
                        "open": [7.52, ...],              # list[float], 开盘价列表
                        "high": [7.60, ...],              # list[float], 最高价列表
                        "low": [7.48, ...],               # list[float], 最低价列表
                        "close": [7.55, ...],             # list[float], 收盘价列表
                        "volume": [1000000, ...],         # list[float], 成交量列表
                        "amount": [7550000.0, ...]        # list[float], 成交额列表
                    }
                }
            }
        """
        stock_str = ','.join(stock_code) if isinstance(stock_code, list) else stock_code
        fields_str = ','.join(fields) if isinstance(fields, list) else fields
        return self._req('POST', '/api/data/market_data_ex', json={
            "stock_code": stock_str, "fields": fields_str, "period": period,
            "start_time": start_time, "end_time": end_time, "count": count,
            "dividend_type": dividend_type
        })

    def get_order_status(self, account='stock'):
        """查询当日委托状态

        EEntrustStatus //委托状态
        ENTRUST_STATUS_WAIT_END: 0 //委托状态已经在 ENTRUST_STATUS_CANCELED 或以上，但是成交数额还不够，等成交回报来
        ENTRUST_STATUS_UNREPORTED: 48 //未报
        ENTRUST_STATUS_WAIT_REPORTING: 49 //待报
        ENTRUST_STATUS_REPORTED: 50 //已报
        ENTRUST_STATUS_REPORTED_CANCEL: 51 //已报待撤
        ENTRUST_STATUS_PARTSUCC_CANCEL: 52 //部成待撤
        ENTRUST_STATUS_PART_CANCEL: 53 //部撤
        ENTRUST_STATUS_CANCELED: 54 //已撤
        ENTRUST_STATUS_PART_SUCC: 55 //部成
        ENTRUST_STATUS_SUCCEEDED: 56 //已成
        ENTRUST_STATUS_JUNK: 57 //废单
        ENTRUST_STATUS_DETERMINED: 86 //已确认
        ENTRUST_STATUS_UNKNOWN: 255 //未知

        参数:
            account: str, 账户类型，默认 'stock'

        返回:
            dict - 委托列表
            {
                "orders": [
                    {
                        "m_strInstrumentID": "600000",         # str, 股票代码（不含交易所后缀）
                        "m_strExchangeID": "SH",               # str, 交易所
                        "m_nEntrustStatus": 50,                # int, 委托状态（见上方枚举）
                        "m_nDirection": 48,                    # int, 委托方向（48=买入, 49=卖出）
                        "m_eEntrustType": 48,                  # int, 委托类型
                        "m_dLimitPrice": 7.55,                 # float, 委托限价
                        "m_nVolumeTotalOriginal": 100,         # int, 委托数量
                        "m_dTradedPrice": 7.55,                # float, 成交均价
                        "m_nVolumeTraded": 100,                # int, 已成交数量
                        "m_dTradeAmount": 75500.0,             # float, 成交金额
                        "m_strOrderRef": "7692771559857651379",# str, 委托内部引用号（长ID）
                        "m_strOrderSysID": "8384",             # str, 委托系统编号（短ID，即order_id）
                        ...其他QMT委托字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', f'/api/order/status', json={"account": account})

    def cancel_all_orders(self, account='stock'):
        """一键撤销所有活跃状态的订单（危险操作）

        参数:
            account: str, 账户类型，默认 'stock'

        返回:
            dict - 撤单结果
            {
                "status": "success",
                "message": "已撤销N笔订单",                # str, 结果说明
                "canceled_orders": [                       # list, 已撤销的订单列表
                    {
                        "m_strInstrumentID": "600000.SH",  # str, 股票代码
                        "m_strOrderRef": "12345",          # str, 委托引用号
                        "m_nEntrustStatus": 54             # int, 委托状态
                    },
                    ...
                ]
            }
        """
        return self._req('POST', f'/api/order/cancel_all', json={"account": account})

    def cancel_order(self, stock, volume, account='stock'):
        """根据股票代码和未成交数量撤单

        请注意：如果该股票有多笔未成交数量相同的订单，会被全部撤销！

        参数:
            stock: str, 股票代码，如 '600000.SH'
            volume: int, 未成交数量
            account: str, 账户类型，默认 'stock'

        返回:
            dict - 撤单结果
            {
                "status": "success",
                "message": "已撤销订单",                    # str, 结果说明
                "canceled_orders": [                       # list, 已撤销的订单列表
                    {
                        "m_strInstrumentID": "600000.SH",  # str, 股票代码
                        "m_strOrderRef": "12345",          # str, 委托引用号
                        "m_nEntrustStatus": 54             # int, 委托状态
                    }
                ]
            }
        """
        return self._req('POST', '/api/order/cancel_order', json={
            "stock": stock,
            "volume": volume,
            "account": account
        })

    def python_version(self):
        """获取QMT Python版本信息

        参数:
            无

        返回:
            dict - Python版本信息
            {
                "python_version": "3.6.8 ...",              # str, 完整Python版本字符串
                "python_version_info": {
                    "major": 3,                             # int, 主版本号
                    "minor": 6,                             # int, 次版本号
                    "micro": 8,                             # int, 修订号
                    "releaselevel": "final",                # str, 发布级别
                    "serial": 0                             # int, 序列号
                }
            }
        """
        return self._req('GET', '/api/sys/python_version')

    def close(self):
        """关闭整个QMT HTTP服务

        参数:
            无

        返回:
            dict - 关闭结果
            {
                "status": "success",
                "message": "服务已关闭"                     # str, 结果说明
            }
        """
        return self._req('POST', '/api/sys/shutdown')

    # ============= ContextInfo 属性 =============
    def get_context_period(self):
        """获取当前ContextInfo的K线周期

        参数:
            无

        返回:
            dict - K线周期
            {
                "period": "tick"                           # str, K线周期，如 'tick'/'1m'/'5m'/'1d'/'1w' 等
            }
        """
        return self._req('GET', '/api/context/period')

    def get_context_barpos(self):
        """获取当前K线Bar的位置索引

        参数:
            无

        返回:
            dict - Bar位置索引
            {
                "barpos": 0                                # int, 当前Bar在K线序列中的位置
            }
        """
        return self._req('GET', '/api/context/barpos')

    def get_context_time_tick_size(self):
        """获取当前分笔数据的时间粒度

        参数:
            无

        返回:
            dict - 时间粒度
            {
                "time_tick_size": 0                        # int, 分笔时间粒度（秒）
            }
        """
        return self._req('GET', '/api/context/time_tick_size')

    def get_context_stockcode(self):
        """获取当前ContextInfo的主图股票代码

        参数:
            无

        返回:
            dict - 股票代码
            {
                "stockcode": "600000.SH"                   # str, 股票代码
            }
        """
        return self._req('GET', '/api/context/stockcode')

    def get_context_dividend_type(self):
        """获取当前ContextInfo的复权类型

        参数:
            无

        返回:
            dict - 复权类型
            {
                "dividend_type": "front"                   # str, 复权类型: 'none'/'front'/'back'
            }
        """
        return self._req('GET', '/api/context/dividend_type')

    def get_context_market(self):
        """获取当前ContextInfo的市场代码

        参数:
            无

        返回:
            dict - 市场代码
            {
                "market": "SH"                             # str, 市场代码，如 'SH'/'SZ'
            }
        """
        return self._req('GET', '/api/context/market')

    def get_context_do_back_test(self):
        """获取当前是否处于回测模式

        参数:
            无

        返回:
            dict - 回测标志
            {
                "do_back_test": false                      # bool, true表示回测模式，false表示实盘/模拟
            }
        """
        return self._req('GET', '/api/context/do_back_test')

    def get_context_benchmark(self):
        """获取当前ContextInfo的基准标的

        参数:
            无

        返回:
            dict - 基准标的
            {
                "benchmark": ""                            # str, 基准标的代码，空字符串表示未设置
            }
        """
        return self._req('GET', '/api/context/benchmark')

    def get_context_capital(self):
        """获取当前ContextInfo的初始资金

        参数:
            无

        返回:
            dict - 初始资金
            {
                "capital": -1.0                            # float, 初始资金金额，-1.0表示未设置
            }
        """
        return self._req('GET', '/api/context/capital')

    def get_context_universe(self):
        """获取当前ContextInfo的股票池

        参数:
            无

        返回:
            dict - 股票池
            {
                "universe": []                             # list[str], 股票池代码列表
            }
        """
        return self._req('GET', '/api/context/universe')

    def get_context_start(self):
        """获取当前ContextInfo的回测/数据起始时间

        参数:
            无

        返回:
            dict - 起始时间
            {
                "start": "-1"                              # str, 起始时间，"-1"表示未设置
            }
        """
        return self._req('GET', '/api/context/start')

    def get_context_end(self):
        """获取当前ContextInfo的回测/数据结束时间

        参数:
            无

        返回:
            dict - 结束时间
            {
                "end": "-1"                                # str, 结束时间，"-1"表示未设置
            }
        """
        return self._req('GET', '/api/context/end')

    # ============= ContextInfo 设置 =============
    def set_universe(self, stock_list):
        """设置当前ContextInfo的股票池

        参数:
            stock_list: str 或 list, 股票代码列表，如 ['600000.SH', '000001.SZ'] 或 '600000.SH,000001.SZ'

        返回:
            dict - 设置结果
            {
                "status": "success",
                "universe": ["600000.SH", "000001.SZ"]     # list[str], 设置后的股票池
            }
        """
        return self._req('POST', '/api/context/set_universe', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list
        })

    def set_account(self, accountid):
        """设置当前ContextInfo的交易账户

        参数:
            accountid: str, 账户ID

        返回:
            dict - 设置结果
            {
                "status": "success",
                "accountid": "12345678"                    # str, 设置后的账户ID
            }
        """
        return self._req('POST', '/api/context/set_account', json={
            "accountid": accountid
        })

    def set_output_index_property(self, index_name, draw_style=0, color='white',
                                  noaxis=False, nodraw=False, noshow=False):
        """设置输出指标线的显示属性

        参数:
            index_name: str, 指标线名称
            draw_style: int, 画线样式，默认 0。常见值:
                0: 线型
                1: 柱状
                2: 柱状(上)
                3: 柱状(下)
                其他QMT支持的画线样式
            color: str, 颜色，默认 'white'。如 'red', 'green', 'blue', 'yellow' 等
            noaxis: bool, 是否不显示坐标轴，默认 False
            nodraw: bool, 是否不画线，默认 False
            noshow: bool, 是否不显示，默认 False

        返回:
            dict - 设置结果
            {
                "status": "success",
                "index_name": "MA5",                       # str, 指标线名称
                "draw_style": 0,                           # int, 画线样式
                "color": "white"                           # str, 颜色
            }
        """
        return self._req('POST', '/api/context/set_output_index_property', json={
            "index_name": index_name, "draw_style": draw_style, "color": color,
            "noaxis": noaxis, "nodraw": nodraw, "noshow": noshow
        })

    # ============= 数据查询 =============
    def get_stock_name(self, stockcode):
        """获取股票名称

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 股票名称
            {
                "stockcode": "600988.SH",                   # str, 股票代码
                "name": "赤峰黄金"                          # str, 股票名称
            }
        """
        return self._req('POST', '/api/data/stock_name', json={"stockcode": stockcode})

    def get_open_date(self, stockcode):
        """获取股票上市日期

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 上市日期
            {
                "stockcode": "600988.SH",                   # str, 股票代码
                "open_date": 0                              # int, 上市日期，0表示无数据
            }
        """
        return self._req('POST', '/api/data/open_date', json={"stockcode": stockcode})

    def get_last_volume(self, stockcode):
        """获取股票最新成交量

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 最新成交量
            {
                "stockcode": "600988.SH",                   # str, 股票代码
                "last_volume": 1426381496                   # int, 最新成交量
            }
        """
        return self._req('POST', '/api/data/last_volume', json={"stockcode": stockcode})

    def get_bar_timetag(self, index=-1):
        """获取K线Bar的时间标签

        参数:
            index: int, Bar索引，-1表示最后一根Bar，默认 -1

        返回:
            dict - 时间标签
            {
                "data": 1704067200000                      # int, 时间标签(毫秒级时间戳)
            }
        """
        return self._req('POST', '/api/data/bar_timetag', json={"index": index})

    def get_tick_timetag(self):
        """获取当前分笔数据的时间标签

        参数:
            无

        返回:
            dict - 分笔时间标签
            {
                "timetag": 1783321206000                    # int, 时间标签(毫秒级时间戳)
            }
        """
        return self._req('GET', '/api/data/tick_timetag')

    def get_stock_list_in_sector(self, sectorname):
        """获取板块下的股票列表

        参数:
            sectorname: str, 板块名称，如 '沪深300'

        返回:
            dict - 股票列表
            {
                "sectorname": "沪深A股",                    # str, 板块名称
                "stocks": [
                    "600000.SH",                           # str, 股票代码
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/stock_list_in_sector', json={"sectorname": sectorname})

    def get_weight_in_index(self, indexcode, stockcode):
        """获取股票在指数中的权重

        参数:
            indexcode: str, 指数代码，如 '000300.SH'
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 权重信息
            {
                "indexcode": "000300.SH",                   # str, 指数代码
                "stockcode": "600988.SH",                   # str, 股票代码
                "weight": 0.0                               # float, 权重比例
            }
        """
        return self._req('POST', '/api/data/weight_in_index', json={
            "indexcode": indexcode, "stockcode": stockcode
        })

    def get_contract_multiplier(self, contractcode):
        """获取期货合约乘数

        参数:
            contractcode: str, 合约代码，如 'IF2401.IF'

        返回:
            dict - 合约乘数
            {
                "contractcode": "IF2401.IF",                 # str, 合约代码
                "multiplier": 1                              # int, 合约乘数
            }
        """
        return self._req('POST', '/api/data/contract_multiplier', json={"contractcode": contractcode})

    def get_risk_free_rate(self, index=-1):
        """获取无风险利率

        参数:
            index: int, 数据索引，-1表示最新值，默认 -1

        返回:
            dict - 无风险利率
            {
                "index": -1,                                # int, 数据索引
                "risk_free_rate": 3.5                       # float, 无风险利率
            }
        """
        return self._req('POST', '/api/data/risk_free_rate', json={"index": index})

    def get_date_location(self, strdate):
        """获取指定日期在K线序列中的位置

        参数:
            strdate: str, 日期字符串，如 '20240101'

        返回:
            dict - 日期位置
            {
                "strdate": "20240101",                      # str, 日期字符串
                "location": 0                               # int, 在K线序列中的位置索引
            }
        """
        return self._req('POST', '/api/data/date_location', json={"strdate": strdate})

    def get_history_data(self, length=10, period='1d', field='close', dividend_type='none', skip_paused=True, stock_list=''):
        """获取历史数据

        参数:
            length: int, 数据长度，默认 10
            period: str, K线周期，默认 '1d'。可选: '1m'/'5m'/'1d'/'1w' 等
            field: str, 字段名，默认 'close'。可选: 'open'/'high'/'low'/'close'/'volume'/'amount' 等
            dividend_type: str, 复权类型，默认 'none'。可选: 'none'/'front'/'back'
            skip_paused: bool, 是否跳过停牌数据，默认 True
            stock_list: str, 股票代码列表（逗号分隔），默认为空（使用当前股票池）

        返回:
            dict - 历史数据
            {
                "data": {
                    "600000.SH": {
                        "close": [7.55, 7.60, ...]          # list[float], 收盘价序列
                    },
                    "000001.SZ": {
                        "close": [12.50, 12.60, ...]        # list[float], 收盘价序列
                    }
                },
                "note": "由get_local_data替代返回"          # str, 说明信息
            }
        """
        return self._req('POST', '/api/data/history_data', json={
            "len": length, "period": period, "field": field,
            "dividend_type": dividend_type, "skip_paused": skip_paused,
            "stock_list": stock_list
        })

    def get_market_data(self, fields='', stock_code='', start_time='', end_time='',
                        period='1d', dividend_type='none', count=-1):
        """获取市场行情数据

        参数:
            fields: str, 字段列表（逗号分隔），默认为空（全部字段）
            stock_code: str, 股票代码，如 '600000.SH'，默认为空
            start_time: str, 开始时间，如 '20240101'，默认为空
            end_time: str, 结束时间，如 '20241231'，默认为空
            period: str, K线周期，默认 '1d'
            dividend_type: str, 复权类型，默认 'none'
            count: int, 数据条数，-1表示全部，默认 -1

        返回:
            dict - 行情数据
            {
                "data": {
                    "600000.SH": {
                        "times": [1704067200000, ...],      # list[int], 时间戳列表
                        "open": [7.52, ...],                # list[float], 开盘价
                        "high": [7.60, ...],                # list[float], 最高价
                        "low": [7.48, ...],                 # list[float], 最低价
                        "close": [7.55, ...],               # list[float], 收盘价
                        "volume": [1000000, ...],           # list[float], 成交量
                        "amount": [7550000.0, ...]          # list[float], 成交额
                    }
                }
            }
        """
        return self._req('POST', '/api/data/market_data', json={
            "fields": fields, "stock_code": stock_code, "start_time": start_time,
            "end_time": end_time, "period": period, "dividend_type": dividend_type, "count": count
        })

    def get_divid_factors(self, stockcode):
        """获取股票除权除息因子

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 除权除息因子
            {
                "stockcode": "600988.SH",                   # str, 股票代码
                "factors": {...}                            # dict, 除权除息因子数据
            }
        """
        return self._req('POST', '/api/data/divid_factors', json={"stockcode": stockcode})

    def get_main_contract(self, codemarket):
        """获取期货主力合约代码

        参数:
            codemarket: str, 品种市场代码，如 'IF'

        返回:
            dict - 主力合约代码
            {
                "codemarket": "IF",                         # str, 品种市场代码
                "main_contract": "IF"                       # str, 主力合约代码
            }
        """
        return self._req('POST', '/api/data/main_contract', json={"codemarket": codemarket})

    def timetag_to_datetime(self, timetag, fmt='%Y-%m-%d %H:%M:%S'):
        """将时间标签转换为日期时间字符串

        参数:
            timetag: int, 时间标签(毫秒级时间戳)
            fmt: str, 日期时间格式，默认 '%Y-%m-%d %H:%M:%S'

        返回:
            dict - 日期时间字符串
            {
                "timetag": 1704067200000,                   # int, 时间标签(毫秒级时间戳)
                "datetime": "2024-01-01 08:00:00"           # str, 格式化后的日期时间
            }
        """
        return self._req('POST', '/api/data/timetag_to_datetime', json={
            "timetag": timetag, "format": fmt
        })

    def get_total_share(self, stockcode):
        """获取股票总股本

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 总股本
            {
                "stockcode": "600988.SH",                   # str, 股票代码
                "total_share": 1426381496                   # int, 总股本（股）
            }
        """
        return self._req('POST', '/api/data/total_share', json={"stockcode": stockcode})

    def get_trading_dates(self, stockcode='', start_date='', end_date='', count=-1, period='1d'):
        """获取交易日期列表

        参数:
            stockcode: str, 股票代码（用于确定市场），默认为空
            start_date: str, 起始日期，如 '20240101'，默认为空
            end_date: str, 结束日期，如 '20241231'，默认为空
            count: int, 返回条数，-1表示全部，默认 -1
            period: str, 周期，默认 '1d'

        返回:
            dict - 交易日期列表
            {
                "dates": [20240102, 20240103, ...]          # list[int], 交易日期列表，格式YYYYMMDD
            }
        """
        return self._req('POST', '/api/data/trading_dates', json={
            "stockcode": stockcode, "start_date": start_date, "end_date": end_date,
            "count": count, "period": period
        })

    def get_svol(self, stockcode):
        """获取股票卖盘量

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 卖盘量
            {
                "stockcode": "600988.SH",                   # str, 股票代码
                "svol": 96440                               # int, 卖盘量
            }
        """
        return self._req('POST', '/api/data/svol', json={"stockcode": stockcode})

    def get_bvol(self, stockcode):
        """获取股票买盘量

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 买盘量
            {
                "data": 60000.0                             # float, 买盘量
            }
        """
        return self._req('POST', '/api/data/bvol', json={"stockcode": stockcode})

    def get_longhubang(self, stock_list, startTime='', endTime=''):
        """获取龙虎榜数据

        参数:
            stock_list: str 或 list, 股票代码列表，如 ['600000.SH'] 或 '600000.SH'
            startTime: str, 开始时间，如 '20240101'，默认为空
            endTime: str, 结束时间，如 '20241231'，默认为空

        返回:
            dict - 龙虎榜数据
            {
                "data": {...}                                # dict, 龙虎榜数据
            }
        """
        return self._req('POST', '/api/data/longhubang', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list,
            "startTime": startTime, "endTime": endTime
        })

    def get_top10_share_holder(self, stock_list, data_name='holder', start_time='', end_time=''):
        """获取前十大股东/流通股东数据

        参数:
            stock_list: str 或 list, 股票代码列表，如 ['600000.SH'] 或 '600000.SH'
            data_name: str, 数据类型，默认 'holder'。可选: 'holder'(股东)/'free_holder'(流通股东)
            start_time: str, 开始时间，如 '20240101'，默认为空
            end_time: str, 结束时间，如 '20241231'，默认为空

        返回:
            dict - 前十大股东数据
            {
                "data": {...}                                # dict, 前十大股东数据
            }
        """
        return self._req('POST', '/api/data/top10_share_holder', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list,
            "data_name": data_name, "start_time": start_time, "end_time": end_time
        })

    def get_option_detail(self, optioncode):
        """获取期权合约详细信息

        参数:
            optioncode: str, 期权合约代码，如 '10003720.SH'

        返回:
            dict - 期权合约详情
            {
                "optioncode": "10003720.SH",                # str, 期权合约代码
                "detail": {...}                              # dict, 期权合约详情
            }
        """
        return self._req('POST', '/api/data/option_detail', json={"optioncode": optioncode})

    def get_turnover_rate(self, stock_list, startTime='', endTime=''):
        """获取换手率数据

        参数:
            stock_list: str 或 list, 股票代码列表，如 ['600000.SH'] 或 '600000.SH'
            startTime: str, 开始时间，如 '20240101'，默认为空
            endTime: str, 结束时间，如 '20241231'，默认为空

        返回:
            dict - 换手率数据
            {
                "data": {...},                               # dict, 换手率数据
                "warning": "返回空DataFrame，可能无该时段数据"  # str, 警告信息（无数据时）
            }
        """
        return self._req('POST', '/api/data/turnover_rate', json={
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list,
            "startTime": startTime, "endTime": endTime
        })

    def get_etf_info(self, stockcode):
        """获取ETF基金信息

        参数:
            stockcode: str, ETF代码，如 '510050.SH'

        返回:
            dict - ETF基金信息
            {
                "stockcode": "510050.SH",                   # str, ETF代码
                "info": {...}                                # dict, ETF基金信息
            }
        """
        return self._req('POST', '/api/data/etf_info', json={"stockcode": stockcode})

    def get_etf_iopv(self, stockcode):
        """获取ETF实时参考净值(IOPV)

        参数:
            stockcode: str, ETF代码，如 '510050.SH'

        返回:
            dict - IOPV数据
            {
                "stockcode": "510050.SH",                   # str, ETF代码
                "iopv": 3.05                                 # float, ETF实时参考净值
            }
        """
        return self._req('POST', '/api/data/etf_iopv', json={"stockcode": stockcode})

    def get_instrumentdetail(self, stockcode):
        """获取合约/标的详细信息

        参数:
            stockcode: str, 标的代码，如 '600000.SH'

        返回:
            dict - 合约详情
            {
                "stockcode": "600988.SH",                   # str, 标的代码
                "detail": {...}                              # dict, 合约详情
            }
        """
        return self._req('POST', '/api/data/instrumentdetail', json={"stockcode": stockcode})

    def get_contract_expire_date(self, codemarket):
        """获取期货合约到期日

        参数:
            codemarket: str, 合约代码，如 'IF2401.IF'

        返回:
            dict - 到期日
            {
                "codemarket": "IF2401.IF",                   # str, 合约代码
                "expire_date": "0"                           # str, 到期日
            }
        """
        return self._req('POST', '/api/data/contract_expire_date', json={"codemarket": codemarket})

    def get_option_undl_data(self, undl_code_ref):
        """获取期权标的数据

        参数:
            undl_code_ref: str, 标的代码引用，如 '510050.SH'

        返回:
            dict - 期权标的数据
            {
                "data": [...]                                # list, 期权标的数据列表
            }
        """
        return self._req('POST', '/api/data/option_undl_data', json={"undl_code_ref": undl_code_ref})

    def get_financial_data(self, fieldList, stockList, startDate='', endDate='', report_type='announce_time'):
        """获取财务数据

        参数:
            fieldList: str 或 list, 财务字段列表，如 ['ROE', 'EPS'] 或 'ROE,EPS'
            stockList: str 或 list, 股票代码列表，如 ['600000.SH'] 或 '600000.SH'
            startDate: str, 开始日期，如 '20230101'，默认为空
            endDate: str, 结束日期，如 '20241231'，默认为空
            report_type: str, 报告期类型，默认 'announce_time'。可选:
                'announce_time'(公告日期)/'report_time'(报告期)

        返回:
            dict - 财务数据
            正常时返回财务数据；当字段格式错误时返回:
            {
                "error": "获取财务数据失败..."                # str, 错误信息
            }
        """
        return self._req('POST', '/api/data/financial_data', json={
            "fieldList": ','.join(fieldList) if isinstance(fieldList, list) else fieldList,
            "stockList": ','.join(stockList) if isinstance(stockList, list) else stockList,
            "startDate": startDate, "endDate": endDate, "report_type": report_type
        })

    def get_factor_data(self, fields, stock_code_or_list, start_date='', end_date=''):
        """获取因子数据

        参数:
            fields: str 或 list, 因子字段列表，如 ['MA5', 'MA10'] 或 'MA5,MA10'
            stock_code_or_list: str 或 list, 股票代码或列表，如 '600000.SH' 或 ['600000.SH', '000001.SZ']
            start_date: str, 开始日期，如 '20240101'，默认为空
            end_date: str, 结束日期，如 '20241231'，默认为空

        返回:
            dict - 因子数据
            {
                "data": null                                # 无数据时返回null
            }
        """
        return self._req('POST', '/api/data/factor_data', json={
            "fieldList": ','.join(fields) if isinstance(fields, list) else fields,
            "stockCode": stock_code_or_list if isinstance(stock_code_or_list, str) else '',
            "stockList": ','.join(stock_code_or_list) if isinstance(stock_code_or_list, list) else '',
            "startDate": start_date, "endDate": end_date
        })

    def get_his_st_data(self, stockCode):
        """获取历史ST数据

        参数:
            stockCode: str, 股票代码，如 '600000.SH'

        返回:
            dict - ST历史数据
            {
                "stockCode": "600988.SH",                   # str, 股票代码
                "data": {...}                                # dict, ST历史数据
            }
        """
        return self._req('POST', '/api/data/his_st_data', json={"stockCode": stockCode})

    def get_his_index_data(self, index):
        """获取历史指数数据

        参数:
            index: str, 指标名称，如 'MA'、'MACD'

        返回:
            dict - 历史指标数据
            {
                "index": "000300.SH",                       # str, 指标名称
                "data": {...}                                # dict, 历史指标数据
            }
        """
        return self._req('POST', '/api/data/his_index_data', json={"index": index})

    def get_all_subscription(self):
        """获取所有当前订阅信息

        参数:
            无

        返回:
            dict - 订阅列表
            {
                "subscriptions": {...}                       # dict, 订阅信息
            }
        """
        return self._req('GET', '/api/data/all_subscription')

    def get_option_list(self, undl_code, dedate='', opttype='', isavailable=True):
        """获取期权合约列表

        参数:
            undl_code: str, 标的代码，如 '510050.SH'
            dedate: str, 到期月份，如 '202401'，默认为空（全部月份）
            opttype: str, 期权类型，默认为空。可选: 'C'(认购)/'P'(认沽)/''(全部)
            isavailable: bool, 是否只返回可交易合约，默认 True

        返回:
            dict - 期权合约列表
            {
                "option_list": [...]                         # list, 期权合约列表
            }
        """
        return self._req('POST', '/api/data/option_list', json={
            "undl_code": undl_code, "dedate": dedate, "opttype": opttype, "isavailable": isavailable
        })

    def get_his_contract_list(self, market):
        """获取历史合约列表（期货）

        参数:
            market: str, 市场代码，如 'IF'

        返回:
            dict - 历史合约列表
            {
                "market": "IF",                              # str, 市场代码
                "contracts": [...]                           # list, 历史合约列表
            }
        """
        return self._req('POST', '/api/data/his_contract_list', json={"market": market})

    def get_option_iv(self, optioncode):
        """获取期权隐含波动率

        参数:
            optioncode: str, 期权合约代码，如 '10003720.SH'

        返回:
            dict - 隐含波动率
            {
                "optioncode": "10003720.SH",                # str, 期权合约代码
                "iv": 0.0                                    # float, 隐含波动率
            }
        """
        return self._req('POST', '/api/data/option_iv', json={"optioncode": optioncode})

    def bsm_price(self, optionType='C', objectPrices='', strikePrice=0, riskFree=0, sigma=0, days=0, dividend=0):
        """BSM模型计算期权理论价格

        参数:
            optionType: str, 期权类型，默认 'C'。'C': 认购(Call)/'P': 认沽(Put)
            objectPrices: str 或 float, 标的价格，如 2.5
            strikePrice: float, 行权价，默认 0
            riskFree: float, 无风险利率，默认 0
            sigma: float, 波动率，默认 0
            days: float, 剩余天数，默认 0
            dividend: float, 股息率，默认 0

        返回:
            dict - BSM理论价格，可能返回500错误
        """
        return self._req('POST', '/api/data/bsm_price', json={
            "optionType": optionType, "objectPrices": objectPrices,
            "strikePrice": strikePrice, "riskFree": riskFree, "sigma": sigma,
            "days": days, "dividend": dividend
        })

    def bsm_iv(self, optionType='C', objectPrices=0, strikePrice=0, optionPrice=0, riskFree=0, days=0, dividend=0):
        """BSM模型计算隐含波动率

        参数:
            optionType: str, 期权类型，默认 'C'。'C': 认购(Call)/'P': 认沽(Put)
            objectPrices: float, 标的价格，默认 0
            strikePrice: float, 行权价，默认 0
            optionPrice: float, 期权市场价格，默认 0
            riskFree: float, 无风险利率，默认 0
            days: float, 剩余天数，默认 0
            dividend: float, 股息率，默认 0

        返回:
            dict - 隐含波动率
            {
                "iv": 0.0                                   # float, 隐含波动率
            }
        """
        return self._req('POST', '/api/data/bsm_iv', json={
            "optionType": optionType, "objectPrices": objectPrices,
            "strikePrice": strikePrice, "optionPrice": optionPrice,
            "riskFree": riskFree, "days": days, "dividend": dividend
        })

    def get_local_data(self, stock_code, start_time='', end_time='', period='1d', divid_type='none', count=-1):
        """获取本地缓存的K线数据

        参数:
            stock_code: str, 股票代码，如 '600000.SH'
            start_time: str, 开始时间，如 '20240101'，默认为空
            end_time: str, 结束时间，如 '20241231'，默认为空
            period: str, K线周期，默认 '1d'
            divid_type: str, 复权类型，默认 'none'
            count: int, 数据条数，-1表示全部，默认 -1

        返回:
            dict - 本地K线数据
            {
                "data": {...}                                # dict, 本地K线数据
            }
        """
        return self._req('POST', '/api/data/local_data', json={
            "stock_code": stock_code, "start_time": start_time, "end_time": end_time,
            "period": period, "divid_type": divid_type, "count": count
        })

    def get_close_price(self, stockcode, period='1d', timetag=0):
        """根据时间标签获取收盘价

        参数:
            stockcode: str, 股票代码，如 '600000.SH'
            period: str, K线周期，默认 '1d'
            timetag: int, 时间标签(毫秒级时间戳)，0表示最新，默认 0

        返回:
            dict - 收盘价
            {
                "stockcode": "600988.SH",                   # str, 股票代码
                "period": "1d",                              # str, K线周期
                "timetag": 0,                                # int, 时间标签
                "close_price": -1.0                          # float, 收盘价
            }
        """
        return self._req('POST', '/api/data/close_price', json={
            "stockcode": stockcode, "period": period, "timetag": timetag
        })

    def get_close_price_by_date(self, stockcode, period='1d', strdate=''):
        """根据日期字符串获取收盘价

        参数:
            stockcode: str, 股票代码，如 '600000.SH'
            period: str, K线周期，默认 '1d'
            strdate: str, 日期字符串，如 '20240101'，默认为空

        返回:
            dict - 收盘价
            {
                "stockcode": "600988.SH",                    # str, 股票代码
                "period": "1d",                               # str, K线周期
                "strdate": "20260704",                        # str, 日期字符串
                "close_price": -1.0                           # float, 收盘价（-1.0表示无数据）
            }
        """
        return self._req('POST', '/api/data/close_price_by_date', json={
            "stockcode": stockcode, "period": period, "strdate": strdate
        })

    def download_history_data(self, stockcode, period='1d', start_time='', end_time=''):
        """下载历史数据到本地

        参数:
            stockcode: str, 股票代码，如 '600000.SH'
            period: str, K线周期，默认 '1d'
            start_time: str, 开始时间，如 '20200101'，默认为空
            end_time: str, 结束时间，如 '20241231'，默认为空

        返回:
            dict - 下载结果
            {
                "status": "success",
                "message": "下载完成"                        # str, 结果说明
            }
        """
        return self._req('POST', '/api/data/download_history_data', json={
            "stockcode": stockcode, "period": period, "start_time": start_time, "end_time": end_time
        })

    # ============= 订阅 =============
    def subscribe_quote(self, stock_code, period='follow', dividend_type='follow'):
        """订阅行情数据

        参数:
            stock_code: str, 股票代码，如 '600000.SH'
            period: str, K线周期，默认 'follow'。可选: '1m'/'5m'/'1d'/'follow' 等
            dividend_type: str, 复权类型，默认 'follow'

        返回:
            dict - 订阅结果
            {
                "status": "success",
                "sub_id": 1                                  # int, 订阅ID，用于取消订阅
            }
        """
        return self._req('POST', '/api/data/subscribe_quote', json={
            "stock_code": stock_code, "period": period, "dividend_type": dividend_type
        })

    def subscribe_whole_quote(self, code_list):
        """订阅全推行情，推送数据会自动缓存，通过 get_sub_tick_cache() 轮询获取

        参数:
            code_list: str 或 list, 股票代码列表，如 ['600000.SH', '000001.SZ'] 或 '600000.SH'

        返回:
            dict - 订阅结果
            {
                "status": "success",
                "sub_id": 2                                  # int, 订阅ID
            }
        """
        return self._req('POST', '/api/data/subscribe_whole_quote', json={
            "code_list": ','.join(code_list) if isinstance(code_list, list) else code_list
        })

    def get_sub_tick_cache(self):
        """获取 subscribe_whole_quote 订阅缓存的最新推送数据

        参数:
            无

        返回:
            dict - 缓存的Tick数据
            {
                "data": {
                    "600000.SH": {
                        "m_strCode": "600000.SH",           # str, 股票代码
                        "m_dNow": 7.55,                     # float, 最新价
                        "m_dVolume": 1000000,               # float, 成交量
                        "m_dAmount": 7550000.0,             # float, 成交额
                        "m_dBidPrice1": 7.54,               # float, 买1价
                        "m_dBidVol1": 500,                  # float, 买1量
                        "m_dAskPrice1": 7.55,               # float, 卖1价
                        "m_dAskVol1": 300,                  # float, 卖1量
                        ...其他行情字段
                    }
                }
            }
        """
        return self._req('GET', '/api/data/sub_tick_cache')

    def get_sub_quote_cache(self):
        """获取 subscribe_quote 订阅缓存的最新推送数据

        参数:
            无

        返回:
            dict - 缓存的K线推送数据
            {
                "data": {
                    "600000.SH": {
                        "times": [1704067200000, ...],      # list[int], 时间戳列表
                        "open": [7.52, ...],                # list[float], 开盘价
                        "high": [7.60, ...],                # list[float], 最高价
                        "low": [7.48, ...],                 # list[float], 最低价
                        "close": [7.55, ...],               # list[float], 收盘价
                        "volume": [1000000, ...],           # list[float], 成交量
                        "amount": [7550000.0, ...]          # list[float], 成交额
                    }
                }
            }
        """
        return self._req('GET', '/api/data/sub_quote_cache')

    def unsubscribe_quote(self, sub_id):
        """取消行情订阅

        参数:
            sub_id: int, 订阅ID（由 subscribe_quote 或 subscribe_whole_quote 返回）

        返回:
            dict - 取消结果
            {
                "status": "success",
                "message": "已取消订阅",                     # str, 结果说明
                "sub_id": 1                                  # int, 已取消的订阅ID
            }
        """
        return self._req('POST', '/api/data/unsubscribe_quote', json={"sub_id": sub_id})

    # ============= 判定函数 =============
    def is_last_bar(self):
        """判断当前Bar是否为最后一根Bar

        参数:
            无

        返回:
            dict - 是否最后一根Bar
            {
                "is_last_bar": false                         # bool, True表示当前Bar是最后一根
            }
        """
        return self._req('GET', '/api/check/is_last_bar')

    def is_new_bar(self):
        """判断当前是否产生了新的Bar

        参数:
            无

        返回:
            dict - 是否新Bar
            {
                "is_new_bar": true                           # bool, True表示产生了新Bar
            }
        """
        return self._req('GET', '/api/check/is_new_bar')

    def is_suspended_stock(self, stockcode):
        """判断股票是否停牌

        参数:
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 停牌状态
            {
                "stockcode": "600988.SH",                    # str, 股票代码
                "is_suspended": false                        # bool, True表示停牌
            }
        """
        return self._req('POST', '/api/check/is_suspended_stock', json={"stockcode": stockcode})

    def is_sector_stock(self, sectorname, market, stockcode):
        """判断股票是否属于指定板块

        参数:
            sectorname: str, 板块名称，如 '沪深300'
            market: str, 市场代码，如 'SH'
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 是否属于板块
            {
                "sectorname": "沪深A股",                     # str, 板块名称
                "stockcode": "600988",                       # str, 股票代码
                "is_in_sector": 1                            # int, 1表示属于该板块，0表示不属于
            }
        """
        return self._req('POST', '/api/check/is_sector_stock', json={
            "sectorname": sectorname, "market": market, "stockcode": stockcode
        })

    def is_typed_stock(self, stocktypenum, market, stockcode):
        """判断股票是否属于指定类型

        参数:
            stocktypenum: int, 股票类型编号
            market: str, 市场代码，如 'SH'
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 是否属于指定类型
            {
                "stocktypenum": 5,                           # int, 股票类型编号
                "stockcode": "600988",                       # str, 股票代码
                "result": 0                                  # int, 0表示不属于该类型，非0表示属于
            }
        """
        return self._req('POST', '/api/check/is_typed_stock', json={
            "stocktypenum": stocktypenum, "market": market, "stockcode": stockcode
        })

    def get_industry_name_of_stock(self, industryType, stockcode):
        """获取股票所属行业名称

        参数:
            industryType: str, 行业分类类型，如 'CSRC'(证监会)/'SW'(申万)
            stockcode: str, 股票代码，如 '600000.SH'

        返回:
            dict - 行业名称
            {
                "industryType": 1,                            # int, 行业分类类型
                "stockcode": "600988.SH",                    # str, 股票代码
                "industry_name": null                        # str or null, 行业名称（无匹配时为null）
            }
        """
        return self._req('POST', '/api/check/get_industry_name_of_stock', json={
            "industryType": industryType, "stockcode": stockcode
        })

    # ============= 交易函数 =============
    def passorder(self, opType, orderType=1101, stock='', prType=11, price=0, volume=0, quickTrade=2, strategy_name='qmt', reason=''):
        """通用下单接口(passorder)

        参数:
            opType: int, 操作类型。常见值:
                0: 买入
                1: 卖出
                2: 买入开仓(期货)
                3: 卖出平仓(期货)
                4: 卖出开仓(期货)
                5: 买入平仓(期货)
                6: 买入开仓(期权)
                7: 卖出平仓(期权)
                8: 卖出开仓(期权)
                9: 买入平仓(期权)
                23: 融资买入
                24: 融券卖出
                25: 买券还券
                26: 卖券还款
                27: 直接还款
                ...其他操作类型
            orderType: int, 订单类型，默认 1101。常见值:
                1101: 股票普通买卖
                1102: 信用交易
                ...其他订单类型
            stock: str, 股票/合约代码，如 '600000.SH'，默认为空
            prType: int, 选价类型，默认 11（指定价/模型价），详见 buy_stock 中的说明
            price: float, 下单价格，默认 0
            volume: int, 下单数量，默认 0
            quickTrade: int, 快速交易标志，默认 2。
                0: 不使用快速交易
                1: 快速交易（仅当前Bar）
                2: 快速交易（合并同方向订单）
            strategy_name: str, 投资备注/策略名称，如 'qmt'，默认 'qmt'
            reason: str, 下单原因，如 '止盈'，默认为空

        返回:
            dict - 下单结果
            下单成功:
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "警告信息"               # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/passorder', json={
            "opType": opType, "orderType": orderType, "stock": stock,
            "prType": prType, "price": price, "volume": volume, "quickTrade": quickTrade,
            "strategyName": strategy_name, "reason": reason
        })

    def algo_passorder(self, opType, orderType=1101, stock='', prType=-1, price=0, volume=0,
                       strategyName='', quickTrade=2, userOrderId='', userOrderParam=None):
        """算法下单接口(algo_passorder)

        参数:
            opType: int, 操作类型，参见 passorder 中的说明
            orderType: int, 订单类型，默认 1101
            stock: str, 股票/合约代码，默认为空
            prType: int, 选价类型，默认 -1（仅对algo_passorder有效的无效值）
            price: float, 下单价格，默认 0
            volume: int, 下单数量，默认 0
            strategyName: str, 算法策略名称，默认为空
            quickTrade: int, 快速交易标志，默认 2
            userOrderId: str, 用户自定义订单ID，默认为空
            userOrderParam: dict, 用户自定义订单参数，默认为空

        返回:
            dict - 算法下单结果
            下单成功:
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "警告信息"               # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/algo_passorder', json={
            "opType": opType, "orderType": orderType, "stock": stock,
            "prType": prType, "price": price, "volume": volume,
            "strategyName": strategyName, "quickTrade": quickTrade,
            "userOrderId": userOrderId, "userOrderParam": userOrderParam or {}
        })

    def smart_algo_passorder(self, opType, orderType=1101, stock='', prType=11, price=0, volume=0,
                             strageName='', quickTrade=2, userid='',
                             smartAlgoType='', limitOverRate=0, minAmountPerOrder=0,
                             targetPriceLevel=0, startTime='', endTime='', limitControl=0):
        """智能算法下单接口

        参数:
            opType: int, 操作类型，参见 passorder 中的说明
            orderType: int, 订单类型，默认 1101
            stock: str, 股票/合约代码，默认为空
            prType: int, 选价类型，默认 11
            price: float, 下单价格，默认 0
            volume: int, 下单数量，默认 0
            strageName: str, 策略名称，默认为空
            quickTrade: int, 快速交易标志，默认 2
            userid: str, 用户ID，默认为空
            smartAlgoType: str, 智能算法类型，默认为空
            limitOverRate: float, 涨跌幅限制比例，默认 0
            minAmountPerOrder: float, 单笔最小金额，默认 0
            targetPriceLevel: int, 目标价格档位，默认 0
            startTime: str, 开始时间，如 '09:30:00'，默认为空
            endTime: str, 结束时间，如 '14:57:00'，默认为空
            limitControl: int, 限制控制，默认 0

        返回:
            dict - 智能算法下单结果
            下单成功:
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "警告信息"               # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/smart_algo_passorder', json={
            "opType": opType, "orderType": orderType, "stock": stock,
            "prType": prType, "price": price, "volume": volume,
            "strageName": strageName, "quickTrade": quickTrade, "userid": userid,
            "smartAlgoType": smartAlgoType, "limitOverRate": limitOverRate,
            "minAmountPerOrder": minAmountPerOrder,
            "targetPriceLevel": targetPriceLevel,
            "startTime": startTime, "endTime": endTime,
            "limitControl": limitControl
        })

    def order_lots(self, stock, lots, style='LATEST', price=0, accId=''):
        """按手数下单（1手=100股）

        参数:
            stock: str, 股票代码，如 '600000.SH'
            lots: int, 下单手数（1手=100股）
            style: str, 下单风格，默认 'LATEST'。可选: 'LATEST'(最新价)/'MARKET'(市价)/具体价格
            price: float, 指定价格（当style为具体价格时使用），默认 0
            accId: str, 账户ID，默认为空（使用默认账户）

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
        """
        return self._req('POST', '/api/trade/order_lots', json={
            "stock": stock, "lots": lots, "style": style, "price": price, "accId": accId
        })

    def order_value(self, stock, value, style='LATEST', price=0, accId=''):
        """按金额下单

        参数:
            stock: str, 股票代码，如 '600000.SH'
            value: float, 下单金额（元）
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
        """
        return self._req('POST', '/api/trade/order_value', json={
            "stock": stock, "value": value, "style": style, "price": price, "accId": accId
        })

    def order_percent(self, stock, percent, style='LATEST', price=0, accId=''):
        """按总资产比例下单

        参数:
            stock: str, 股票代码，如 '600000.SH'
            percent: float, 下单比例（0~1之间的值，如0.1表示10%）
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
        """
        return self._req('POST', '/api/trade/order_percent', json={
            "stock": stock, "percent": percent, "style": style, "price": price, "accId": accId
        })

    def order_target_value(self, stock, tar_value, style='LATEST', price=0, accId=''):
        """调整持仓到目标市值

        参数:
            stock: str, 股票代码，如 '600000.SH'
            tar_value: float, 目标市值（元）
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型(买/卖)
                "stock": "600000.SH"               # str, 股票代码
            }
        """
        return self._req('POST', '/api/trade/order_target_value', json={
            "stock": stock, "tar_value": tar_value, "style": style, "price": price, "accId": accId
        })

    def order_target_percent(self, stock, tar_percent, style='LATEST', price=0, accId=''):
        """调整持仓到目标比例

        参数:
            stock: str, 股票代码，如 '600000.SH'
            tar_percent: float, 目标持仓比例（0~1之间的值）
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型(买/卖)
                "stock": "600000.SH"               # str, 股票代码
            }
        """
        return self._req('POST', '/api/trade/order_target_percent', json={
            "stock": stock, "tar_percent": tar_percent, "style": style, "price": price, "accId": accId
        })

    def order_shares(self, stock, shares, style='LATEST', price=0, accId=''):
        """按股数下单

        参数:
            stock: str, 股票代码，如 '600000.SH'
            shares: int, 下单股数（正数买入，负数卖出）
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy",                   # str, 操作类型(买/卖)
                "stock": "600000.SH"               # str, 股票代码
            }
        """
        return self._req('POST', '/api/trade/order_shares', json={
            "stock": stock, "shares": shares, "style": style, "price": price, "accId": accId
        })

    def cancel_order_by_id(self, orderId, accountType='stock'):
        """根据委托引用号撤单

        参数:
            orderId: str, 委托引用号/订单ID
            accountType: str, 账户类型，默认 'stock'

        返回:
            dict - 撤单结果
            {
                "status": "success",
                "message": "撤单成功",                    # str, 结果说明
                "order_id": "12345"                       # str, 被撤订单ID
            }
        """
        return self._req('POST', '/api/trade/cancel', json={
            "orderId": orderId, "accountType": accountType
        })

    # ============= 期货交易 =============
    def buy_open(self, stock, amount, style='LATEST', price=0, accId=''):
        """期货买入开仓

        参数:
            stock: str, 合约代码，如 'IF2401.IF'
            amount: int, 开仓手数
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy_open",              # str, 操作类型
                "stock": "IF2401.IF"               # str, 合约代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托（如期货无账户）:
            {
                "status": "warning",
                "message": "期货无账户"             # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/futures/buy_open', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def buy_close_tdayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        """期货买入平仓（优先平今仓）

        参数:
            stock: str, 合约代码，如 'IF2401.IF'
            amount: int, 平仓手数
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy_close_tdayfirst",   # str, 操作类型
                "stock": "IF2401.IF"               # str, 合约代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "期货无账户"             # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/futures/buy_close_tdayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def buy_close_ydayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        """期货买入平仓（优先平昨仓）

        参数:
            stock: str, 合约代码，如 'IF2401.IF'
            amount: int, 平仓手数
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "buy_close_ydayfirst",   # str, 操作类型
                "stock": "IF2401.IF"               # str, 合约代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "期货无账户"             # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/futures/buy_close_ydayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def sell_open(self, stock, amount, style='LATEST', price=0, accId=''):
        """期货卖出开仓

        参数:
            stock: str, 合约代码，如 'IF2401.IF'
            amount: int, 开仓手数
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "sell_open",             # str, 操作类型
                "stock": "IF2401.IF"               # str, 合约代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "期货无账户"             # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/futures/sell_open', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def sell_close_tdayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        """期货卖出平仓（优先平今仓）

        参数:
            stock: str, 合约代码，如 'IF2401.IF'
            amount: int, 平仓手数
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "sell_close_tdayfirst",  # str, 操作类型
                "stock": "IF2401.IF"               # str, 合约代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "期货无账户"             # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/futures/sell_close_tdayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    def sell_close_ydayfirst(self, stock, amount, style='LATEST', price=0, accId=''):
        """期货卖出平仓（优先平昨仓）

        参数:
            stock: str, 合约代码，如 'IF2401.IF'
            amount: int, 平仓手数
            style: str, 下单风格，默认 'LATEST'
            price: float, 指定价格，默认 0
            accId: str, 账户ID，默认为空

        返回:
            dict - 下单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "sell_close_ydayfirst",  # str, 操作类型
                "stock": "IF2401.IF"               # str, 合约代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "期货无账户"             # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/futures/sell_close_ydayfirst', json={
            "stock": stock, "amount": amount, "style": style, "price": price, "accId": accId
        })

    # ============= 任务管理 =============
    def cancel_task(self, taskId, accountType='stock'):
        """取消算法交易任务

        参数:
            taskId: str, 任务ID
            accountType: str, 账户类型，默认 'stock'

        返回:
            dict - 取消结果
            {
                "status": "success",
                "message": "任务已取消",             # str, 结果说明
                "task_id": "xxx"                     # str, 已取消的任务ID
            }
        """
        return self._req('POST', '/api/trade/cancel_task', json={
            "taskId": taskId, "accountType": accountType
        })

    def pause_task(self, taskId, accountType='stock'):
        """暂停算法交易任务

        参数:
            taskId: str, 任务ID
            accountType: str, 账户类型，默认 'stock'

        返回:
            dict - 暂停结果
            {
                "status": "success",
                "message": "任务已暂停",             # str, 结果说明
                "task_id": "xxx"                     # str, 已暂停的任务ID
            }
        """
        return self._req('POST', '/api/trade/pause_task', json={
            "taskId": taskId, "accountType": accountType
        })

    def resume_task(self, taskId, accountType='stock'):
        """恢复算法交易任务

        参数:
            taskId: str, 任务ID
            accountType: str, 账户类型，默认 'stock'

        返回:
            dict - 恢复结果
            {
                "status": "success",
                "message": "任务已恢复",             # str, 结果说明
                "task_id": "xxx"                     # str, 已恢复的任务ID
            }
        """
        return self._req('POST', '/api/trade/resume_task', json={
            "taskId": taskId, "accountType": accountType
        })

    def do_order(self):
        """立即执行所有挂单

        参数:
            无

        返回:
            dict - 执行结果
            {
                "status": "success",
                "message": "订单已提交"              # str, 结果说明
            }
        """
        return self._req('POST', '/api/trade/do_order')

    # ============= 账户/订单查询 =============
    def get_trade_detail_data(self, account='stock', datatype='position'):
        """获取交易明细数据

        参数:
            account: str, 账户类型，默认 'stock'
            datatype: str, 数据类型，默认 'position'。可选值:
                'position': 持仓
                'order': 委托
                'deal': 成交
                'account': 账户资金

        返回:
            dict - 交易明细数据
            当 datatype='position' 时:
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_dMarketValue": 75500.0,          # float, 市值
                        "m_nVolume": 10000,                  # int, 持仓数量
                        "m_dAvgPrice": 7.55,                 # float, 成本价
                        "m_dProfit": 500.0,                  # float, 浮动盈亏
                        ...其他字段
                    }
                ]
            }
            当 datatype='order' 时:
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_nEntrustStatus": 50,              # int, 委托状态
                        "m_dPrice": 7.55,                    # float, 委托价格
                        "m_nVolumeTotalOriginal": 100,       # int, 委托数量
                        ...其他字段
                    }
                ]
            }
            当 datatype='deal' 时:
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_dTradedPrice": 7.55,              # float, 成交价格
                        "m_nVolumeTraded": 100,              # int, 成交数量
                        ...其他字段
                    }
                ]
            }
        """
        return self._req('POST', '/api/trade/trade_detail_data', json={
            "account": account, "datatype": datatype
        })

    def get_value_by_order_id(self, orderId, accountType='stock', datatype='ORDER'):
        """根据委托号获取委托/成交详情

        参数:
            orderId: str, 委托号/订单ID
            accountType: str, 账户类型，默认 'stock'
            datatype: str, 数据类型，默认 'ORDER'。可选: 'ORDER'(委托)/'DEAL'(成交)

        返回:
            dict - 委托/成交详情
            {
                "data": {
                    "m_strInstrumentID": "600000.SH",       # str, 股票代码
                    "m_nEntrustStatus": 56,                  # int, 委托状态
                    "m_dPrice": 7.55,                        # float, 委托价格
                    "m_nVolumeTotalOriginal": 100,            # int, 委托数量
                    "m_nVolumeTraded": 100,                   # int, 成交数量
                    "m_dTradedPrice": 7.55,                   # float, 成交均价
                    "m_strOrderRef": "12345",                 # str, 委托引用号
                    ...其他字段
                }
            }
        """
        return self._req('POST', '/api/trade/value_by_order_id', json={
            "orderId": orderId, "accountType": accountType, "datatype": datatype
        })

    def get_last_order_id(self, account='stock', datatype='ORDER'):
        """获取最新委托号

        参数:
            account: str, 账户类型，默认 'stock'
            datatype: str, 数据类型，默认 'ORDER'。可选: 'ORDER'(委托)/'DEAL'(成交)

        返回:
            dict - 最新委托号
            {
                "data": "12345"                              # str, 最新委托号
            }
        """
        return self._req('POST', '/api/trade/last_order_id', json={
            "account": account, "datatype": datatype
        })

    def can_cancel_order(self, orderId, accountType='stock'):
        """判断委托是否可撤单

        参数:
            orderId: str, 委托号/订单ID
            accountType: str, 账户类型，默认 'stock'

        返回:
            dict - 是否可撤单
            {
                "can_cancel": True                           # bool, True表示可撤单
            }
        """
        return self._req('POST', '/api/trade/can_cancel_order', json={
            "orderId": orderId, "accountType": accountType
        })

    def get_debt_contract(self, accId=''):
        """查询融资负债合约

        参数:
            accId: str, 账户ID，默认为空

        返回:
            dict - 融资负债合约列表
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_dCompactedAmount": 10000.0,       # float, 负债金额
                        "m_dRepaidAmount": 5000.0,           # float, 已还金额
                        "m_dRemainAmount": 5000.0,           # float, 剩余负债
                        "m_strCompactDate": "20240101",      # str, 签约日期
                        "m_strEndDate": "20240701",          # str, 到期日期
                        ...其他合约字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/trade/debt_contract', json={"accId": accId})

    def get_assure_contract(self, accId=''):
        """查询融券担保合约

        参数:
            accId: str, 账户ID，默认为空

        返回:
            dict - 融券担保合约列表
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_nAssureVolume": 1000,             # int, 担保数量
                        "m_dAssureAmount": 7550.0,           # float, 担保金额
                        ...其他合约字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/trade/assure_contract', json={"accId": accId})

    def get_enable_short_contract(self, accId=''):
        """查询可融券合约列表

        参数:
            accId: str, 账户ID，默认为空

        返回:
            dict - 可融券合约列表
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_nEnableVolume": 10000,            # int, 可融券数量
                        "m_dEnableAmount": 75500.0,          # float, 可融券金额
                        ...其他合约字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/trade/enable_short_contract', json={"accId": accId})

    def get_ipo_data(self, typ=''):
        """查询新股申购数据

        参数:
            typ: str, 查询类型，默认为空

        返回:
            dict - 新股申购数据
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_strInstrumentName": "xxx",        # str, 股票名称
                        "m_dPrice": 10.0,                    # float, 申购价格
                        "m_nMaxVolume": 10000,               # int, 最大申购量
                        "m_strSubscribeDate": "20240101",    # str, 申购日期
                        ...其他申购字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/trade/ipo_data', json={"type": typ})

    def get_new_purchase_limit(self, accid=''):
        """查询新股申购额度

        参数:
            accid: str, 账户ID，默认为空

        返回:
            dict - 申购额度
            {
                "data": {
                    "m_nShPurchaseLimit": 5000,              # int, 沪市申购额度
                    "m_nSzPurchaseLimit": 5000,              # int, 深市申购额度
                    "m_nCyPurchaseLimit": 0,                 # int, 创业板申购额度
                    "m_nKcPurchaseLimit": 0,                 # int, 科创板申购额度
                    ...其他额度字段
                }
            }
        """
        return self._req('POST', '/api/trade/new_purchase_limit', json={"accid": accid})

    def get_smart_algo_param(self, algoList):
        """查询智能算法参数

        参数:
            algoList: str 或 list, 算法名称列表

        返回:
            dict - 智能算法参数
            {
                "data": [
                    {
                        "m_strAlgoName": "TWAP",             # str, 算法名称
                        "m_strAlgoDesc": "时间加权平均",      # str, 算法描述
                        "m_nParamCount": 3,                  # int, 参数数量
                        ...其他算法参数字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/trade/smart_algo_param', json={
            "algoList": algoList if isinstance(algoList, list) else algoList
        })

    def query_credit_account(self, accid='', seq=0):
        """查询信用账户信息

        参数:
            accid: str, 账户ID，默认为空
            seq: int, 序列号，默认 0

        返回:
            dict - 信用账户信息
            {
                "data": {
                    "m_dTotalAsset": 100000.0,               # float, 总资产
                    "m_dNetAsset": 80000.0,                   # float, 净资产
                    "m_dMaintainRatio": 2.5,                  # float, 维持担保比例
                    "m_dAvailableCredit": 50000.0,            # float, 可用融资额度
                    ...其他信用账户字段
                }
            }
        """
        return self._req('POST', '/api/trade/query_credit_account', json={
            "accid": accid, "seq": seq
        })

    def query_credit_opvolume(self, accid='', seq=0, optype='', code='', price=0, volume=0):
        """查询信用账户可操作数量

        参数:
            accid: str, 账户ID，默认为空
            seq: int, 序列号，默认 0
            optype: str, 操作类型，默认为空
            code: str, 股票代码，默认为空
            price: float, 价格，默认 0
            volume: int, 数量，默认 0

        返回:
            dict - 可操作数量
            {
                "data": {
                    "m_nMaxBuyVolume": 10000,                 # int, 最大可买数量
                    "m_nMaxSellVolume": 5000,                 # int, 最大可卖数量
                    "m_dMaxBuyAmount": 75500.0,               # float, 最大可买金额
                    ...其他可操作数量字段
                }
            }
        """
        return self._req('POST', '/api/trade/query_credit_opvolume', json={
            "accid": accid, "seq": seq, "optype": optype, "code": code,
            "price": price, "volume": volume
        })

    # ============= 引用函数 =============
    def ext_data(self, extdataname, stockcode='', deviation=0):
        """获取外部引用数据

        参数:
            extdataname: str, 外部数据名称
            stockcode: str, 股票代码，如 '600000.SH'，默认为空
            deviation: int, 偏移量，默认 0

        返回:
            dict - 外部数据值
            {
                "data": 7.55                                 # float/int/str, 外部数据值
            }
        """
        return self._req('POST', '/api/ext/ext_data', json={
            "extdataname": extdataname, "stockcode": stockcode, "deviation": deviation
        })

    def ext_data_rank(self, extdataname, stockcode='', deviation=0):
        """获取外部引用数据的排名

        参数:
            extdataname: str, 外部数据名称
            stockcode: str, 股票代码，如 '600000.SH'，默认为空
            deviation: int, 偏移量，默认 0

        返回:
            dict - 排名值
            {
                "data": 15                                   # int, 排名（1~N）
            }
        """
        return self._req('POST', '/api/ext/ext_data_rank', json={
            "extdataname": extdataname, "stockcode": stockcode, "deviation": deviation
        })

    def ext_data_rank_range(self, extdataname, stockcode='', begintime='', endtime=''):
        """获取指定时间范围内的外部数据排名

        参数:
            extdataname: str, 外部数据名称
            stockcode: str, 股票代码，如 '600000.SH'，默认为空
            begintime: str, 开始时间，如 '20240101'，默认为空
            endtime: str, 结束时间，如 '20241231'，默认为空

        返回:
            dict - 排名数据
            {
                "data": {
                    "times": [1704067200000, ...],          # list[int], 时间戳列表
                    "ranks": [15, 12, ...]                  # list[int], 排名值列表
                }
            }
        """
        return self._req('POST', '/api/ext/ext_data_rank_range', json={
            "extdataname": extdataname, "stockcode": stockcode,
            "begintime": begintime, "endtime": endtime
        })

    def ext_data_range(self, extdataname, stockcode='', begintime='', endtime=''):
        """获取指定时间范围内的外部引用数据

        参数:
            extdataname: str, 外部数据名称
            stockcode: str, 股票代码，如 '600000.SH'，默认为空
            begintime: str, 开始时间，如 '20240101'，默认为空
            endtime: str, 结束时间，如 '20241231'，默认为空

        返回:
            dict - 外部数据序列
            {
                "data": {
                    "times": [1704067200000, ...],          # list[int], 时间戳列表
                    "values": [7.55, 7.60, ...]            # list[float], 数据值列表
                }
            }
        """
        return self._req('POST', '/api/ext/ext_data_range', json={
            "extdataname": extdataname, "stockcode": stockcode,
            "begintime": begintime, "endtime": endtime
        })

    def get_factor_value(self, factorname, stockcode='', deviation=0):
        """获取因子值

        参数:
            factorname: str, 因子名称
            stockcode: str, 股票代码，如 '600000.SH'，默认为空
            deviation: int, 偏移量，默认 0

        返回:
            dict - 因子值
            {
                "data": 0.85                                 # float, 因子值
            }
        """
        return self._req('POST', '/api/ext/get_factor_value', json={
            "factorname": factorname, "stockcode": stockcode, "deviation": deviation
        })

    def get_factor_rank(self, factorname, stockcode='', deviation=0):
        """获取因子排名

        参数:
            factorname: str, 因子名称
            stockcode: str, 股票代码，如 '600000.SH'，默认为空
            deviation: int, 偏移量，默认 0

        返回:
            dict - 因子排名
            {
                "data": 15                                   # int, 排名（1~N）
            }
        """
        return self._req('POST', '/api/ext/get_factor_rank', json={
            "factorname": factorname, "stockcode": stockcode, "deviation": deviation
        })

    # ============= 板块管理 =============
    def create_sector(self, parent_node, sector_name, overwrite=True):
        """创建自定义板块

        参数:
            parent_node: str, 父节点名称
            sector_name: str, 板块名称
            overwrite: bool, 是否覆盖已存在的板块，默认 True

        返回:
            dict - 创建结果
            {
                "status": "success",
                "message": "板块创建成功",                   # str, 结果说明
                "sector_name": "my_sector"                   # str, 创建的板块名称
            }
        """
        return self._req('POST', '/api/sector/create', json={
            "parent_node": parent_node, "sector_name": sector_name, "overwrite": overwrite
        })

    def create_sector_folder(self, parent_node, folder_name, overwrite=True):
        """创建板块文件夹

        参数:
            parent_node: str, 父节点名称
            folder_name: str, 文件夹名称
            overwrite: bool, 是否覆盖已存在的文件夹，默认 True

        返回:
            dict - 创建结果
            {
                "status": "success",
                "message": "文件夹创建成功",                 # str, 结果说明
                "folder_name": "my_folder"                   # str, 创建的文件夹名称
            }
        """
        return self._req('POST', '/api/sector/create_folder', json={
            "parent_node": parent_node, "folder_name": folder_name, "overwrite": overwrite
        })

    def get_sector_list(self, node=''):
        """获取板块列表

        参数:
            node: str, 父节点名称，默认为空（根节点）

        返回:
            dict - 板块列表
            {
                "data": [
                    {
                        "m_strSectorName": "沪深300",         # str, 板块名称
                        "m_strParentNode": "",                # str, 父节点
                        "m_nType": 1,                        # int, 板块类型
                        ...其他板块字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/sector/list', json={"node": node})

    def reset_sector_stock_list(self, sector, stock_list):
        """重置板块股票列表（覆盖式更新）

        参数:
            sector: str, 板块名称
            stock_list: str 或 list, 股票代码列表，如 ['600000.SH', '000001.SZ'] 或 '600000.SH,000001.SZ'

        返回:
            dict - 重置结果
            {
                "status": "success",
                "message": "板块股票列表已重置",             # str, 结果说明
                "sector": "my_sector",                       # str, 板块名称
                "stock_list": ["600000.SH", "000001.SZ"]     # list[str], 重置后的股票列表
            }
        """
        return self._req('POST', '/api/sector/reset_stocks', json={
            "sector": sector,
            "stock_list": ','.join(stock_list) if isinstance(stock_list, list) else stock_list
        })

    def add_stock_to_sector(self, sector, stock_code):
        """向板块添加股票

        参数:
            sector: str, 板块名称
            stock_code: str, 股票代码，如 '600000.SH'

        返回:
            dict - 添加结果
            {
                "status": "success",
                "message": "股票已添加到板块",               # str, 结果说明
                "sector": "my_sector",                       # str, 板块名称
                "stock_code": "600000.SH"                    # str, 添加的股票代码
            }
        """
        return self._req('POST', '/api/sector/add_stock', json={
            "sector": sector, "stock_code": stock_code
        })

    def remove_stock_from_sector(self, sector, stock_code):
        """从板块移除股票

        参数:
            sector: str, 板块名称
            stock_code: str, 股票代码，如 '600000.SH'

        返回:
            dict - 移除结果
            {
                "status": "success",
                "message": "股票已从板块移除",               # str, 结果说明
                "sector": "my_sector",                       # str, 板块名称
                "stock_code": "600000.SH"                    # str, 移除的股票代码
            }
        """
        return self._req('POST', '/api/sector/remove_stock', json={
            "sector": sector, "stock_code": stock_code
        })

    # ============= 新增数据接口 =============
    def get_commission(self):
        """获取当前手续费设置

        参数:
            无

        返回:
            dict - 手续费设置
            {
                "data": {
                    "m_dCommissionRate": 0.0003,             # float, 佣金费率
                    "m_dMinCommission": 5.0,                 # float, 最低佣金
                    "m_dStampRate": 0.001,                   # float, 印花税率
                    "m_dTransferRate": 0.00002,              # float, 过户费率
                    ...其他手续费字段
                }
            }
        """
        return self._req('POST', '/api/data/commission')

    def get_slippage(self):
        """获取当前滑点设置

        参数:
            无

        返回:
            dict - 滑点设置
            {
                "data": {
                    "m_dSlippage": 0.01,                     # float, 滑点值
                    ...其他滑点字段
                }
            }
        """
        return self._req('POST', '/api/data/slippage')

    def set_commission(self, comtype, com='none'):
        """设置手续费

        参数:
            comtype: str, 手续费类型
            com: str, 手续费设置，默认 'none'

        返回:
            dict - 设置结果
            {
                "status": "success",
                "message": "手续费设置成功"                  # str, 结果说明
            }
        """
        return self._req('POST', '/api/context/set_commission', json={
            "comtype": comtype, "com": com
        })

    def set_slippage(self, b_flag, slippage='none'):
        """设置滑点

        参数:
            b_flag: bool, 是否启用滑点
            slippage: str, 滑点设置，默认 'none'

        返回:
            dict - 设置结果
            {
                "status": "success",
                "message": "滑点设置成功"                    # str, 结果说明
            }
        """
        return self._req('POST', '/api/context/set_slippage', json={
            "b_flag": b_flag, "slippage": slippage
        })

    def get_net_value(self, barpositon=0):
        """获取策略净值

        参数:
            barpositon: int, Bar位置，默认 0

        返回:
            dict - 净值数据
            {
                "data": {
                    "m_dNetValue": 1.05,                     # float, 净值
                    "m_dTotalReturn": 0.05,                  # float, 总收益率
                    "m_dDailyReturn": 0.01,                  # float, 日收益率
                    ...其他净值字段
                }
            }
        """
        return self._req('POST', '/api/data/net_value', json={"barpositon": barpositon})

    def get_raw_financial_data(self, field_list, stock_list, start_date, end_date, report_type='report_time', data_type='dict'):
        """获取原始财务数据（未经处理）

        参数:
            field_list: str, 财务字段列表（逗号分隔），如 'ROE,EPS'
            stock_list: str, 股票代码列表（逗号分隔），如 '600000.SH,000001.SZ'
            start_date: str, 开始日期，如 '20230101'
            end_date: str, 结束日期，如 '20241231'
            report_type: str, 报告期类型，默认 'report_time'。可选: 'report_time'/'announce_time'
            data_type: str, 返回数据格式，默认 'dict'。可选: 'dict'/'array'

        返回:
            dict - 原始财务数据
            {
                "data": [
                    {
                        "m_strCode": "600000.SH",           # str, 股票代码
                        "m_strReportDate": "20240331",       # str, 报告期
                        "ROE": 0.12,                         # float, 净资产收益率
                        "EPS": 0.85,                         # float, 每股收益
                        ...请求的财务字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/raw_financial_data', json={
            "fieldList": field_list, "stockList": stock_list,
            "startDate": start_date, "endDate": end_date,
            "report_type": report_type, "data_type": data_type
        })

    def get_north_finance_change(self, period):
        """获取北向资金变动数据

        参数:
            period: str, 时间周期，如 '1d'/'5d'/'1m'

        返回:
            dict - 北向资金变动数据
            {
                "data": {
                    "times": [1704067200000, ...],          # list[int], 时间戳列表
                    "m_dNetInflow": [5000000.0, ...],       # list[float], 净流入(元)
                    "m_dShInflow": [3000000.0, ...],        # list[float], 沪股通流入(元)
                    "m_dSzInflow": [2000000.0, ...],        # list[float], 深股通流入(元)
                    ...其他字段
                }
            }
        """
        return self._req('POST', '/api/data/north_finance_change', json={"period": period})

    def get_hkt_exchange_rate(self):
        """获取港股通汇率

        参数:
            无

        返回:
            dict - 港股通汇率
            {
                "data": {
                    "m_dBuyRate": 0.9100,                   # float, 买入参考汇率
                    "m_dSellRate": 0.8900,                  # float, 卖出参考汇率
                    "m_dMidRate": 0.9000,                   # float, 中间参考汇率
                    ...其他汇率字段
                }
            }
        """
        return self._req('POST', '/api/data/hkt_exchange_rate')

    def get_hkt_details(self, stock_code):
        """获取港股通个股明细数据

        参数:
            stock_code: str, 股票代码，如 '00700.HK'

        返回:
            dict - 港股通个股明细
            {
                "data": [
                    {
                        "m_strCode": "00700.HK",            # str, 股票代码
                        "m_dBuyAmount": 1000000.0,           # float, 买入金额
                        "m_dSellAmount": 800000.0,           # float, 卖出金额
                        "m_dNetAmount": 200000.0,            # float, 净买入金额
                        ...其他明细字段
                    }
                ]
            }
        """
        return self._req('POST', '/api/data/hkt_details', json={"stock_code": stock_code})

    def get_hkt_statistics(self, stock_code):
        """获取港股通个股统计数据

        参数:
            stock_code: str, 股票代码，如 '00700.HK'

        返回:
            dict - 港股通个股统计
            {
                "data": {
                    "m_strCode": "00700.HK",                # str, 股票代码
                    "m_dTotalBuy": 50000000.0,               # float, 累计买入(元)
                    "m_dTotalSell": 40000000.0,              # float, 累计卖出(元)
                    "m_dTotalNet": 10000000.0,               # float, 累计净买入(元)
                    ...其他统计字段
                }
            }
        """
        return self._req('POST', '/api/data/hkt_statistics', json={"stock_code": stock_code})

    def get_market_time(self):
        """获取当前市场交易时间信息

        参数:
            无

        返回:
            dict - 市场时间信息
            {
                "data": {
                    "m_strMarket": "SH",                     # str, 市场
                    "m_dOpenTime1": 93000000,                # int, 上午开盘时间(毫秒)
                    "m_dCloseTime1": 113000000,              # int, 上午收盘时间(毫秒)
                    "m_dOpenTime2": 130000000,               # int, 下午开盘时间(毫秒)
                    "m_dCloseTime2": 150000000,              # int, 下午收盘时间(毫秒)
                    ...其他时间字段
                }
            }
        """
        return self._req('POST', '/api/data/market_time')

    def get_option_detail_data(self, stockcode):
        """获取期权合约详细数据

        参数:
            stockcode: str, 期权合约代码，如 '10003720.SH'

        返回:
            dict - 期权合约详细数据
            {
                "data": {
                    "m_strCode": "10003720.SH",             # str, 期权代码
                    "m_strName": "50ETF购1月2400",           # str, 期权名称
                    "m_dStrikePrice": 2.4,                   # float, 行权价
                    "m_nOptType": 1,                         # int, 期权类型(1:认购/0:认沽)
                    "m_strEndDate": "20240124",              # str, 到期日
                    "m_dUnderlyingPrice": 2.5,               # float, 标的当前价
                    "m_dOptionPrice": 0.12,                  # float, 期权当前价
                    "m_dIV": 0.256,                          # float, 隐含波动率
                    "m_dDelta": 0.65,                        # float, Delta值
                    "m_dGamma": 2.5,                         # float, Gamma值
                    "m_dTheta": -0.005,                      # float, Theta值
                    "m_dVega": 0.003,                        # float, Vega值
                    "m_dRho": 0.001,                         # float, Rho值
                    ...其他期权详细字段
                }
            }
        """
        return self._req('POST', '/api/data/option_detail_data', json={"stockcode": stockcode})

    def load_stk_list(self, dirfile, namefile):
        """从文件加载股票列表

        参数:
            dirfile: str, 目录文件路径
            namefile: str, 名称文件路径

        返回:
            dict - 股票列表
            {
                "data": [
                    "600000.SH",                             # str, 股票代码
                    "000001.SZ",
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/load_stk_list', json={
            "dirfile": dirfile, "namefile": namefile
        })

    def load_stk_vol_list(self, dirfile, namefile):
        """从文件加载股票量列表

        参数:
            dirfile: str, 目录文件路径
            namefile: str, 名称文件路径

        返回:
            dict - 股票量列表
            {
                "data": [
                    {
                        "code": "600000.SH",                 # str, 股票代码
                        "volume": 10000                       # int, 数量
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/load_stk_vol_list', json={
            "dirfile": dirfile, "namefile": namefile
        })

    def get_basket(self, basket_name):
        """获取篮子（组合）定义

        参数:
            basket_name: str, 篮子名称

        返回:
            dict - 篮子定义
            {
                "data": {
                    "m_strBasketName": "my_basket",          # str, 篮子名称
                    "m_lstStockList": [                      # list, 股票列表
                        {
                            "m_strCode": "600000.SH",       # str, 股票代码
                            "m_nVolume": 100,                # int, 数量
                            "m_dWeight": 0.3                 # float, 权重
                        },
                        ...
                    ]
                }
            }
        """
        return self._req('POST', '/api/data/get_basket', json={"basket_name": basket_name})

    def set_basket(self, basket_name, stock_list):
        """设置篮子（组合）定义

        参数:
            basket_name: str, 篮子名称
            stock_list: list, 股票列表

        返回:
            dict - 设置结果
            {
                "status": "success",
                "message": "篮子设置成功",                   # str, 结果说明
                "basket_name": "my_basket"                   # str, 篮子名称
            }
        """
        return self._req('POST', '/api/data/set_basket', json={
            "basket_name": basket_name, "stock_list": stock_list
        })

    def get_st_status(self, stock_code):
        """获取股票ST状态

        参数:
            stock_code: str, 股票代码，如 '600000.SH'

        返回:
            dict - ST状态
            {
                "data": {
                    "m_strCode": "600000.SH",               # str, 股票代码
                    "m_nSTStatus": 0                         # int, ST状态(0:正常/1:ST/2:*ST)
                }
            }
        """
        return self._req('POST', '/api/data/st_status', json={"stock_code": stock_code})

    # ============= 新增交易接口 =============
    def stoploss_limitprice(self, stoploss_code, order_type, op_type, account, stock_code, stop_price, stop_amount, price_type=11, price=0, volume=0, strategy_name='', quick_trade=2, userid=''):
        """限价止损单

        参数:
            stoploss_code: str, 止损代码
            order_type: int, 订单类型
            op_type: int, 操作类型
            account: str, 账户ID
            stock_code: str, 股票代码，如 '600000.SH'
            stop_price: float, 止损触发价格
            stop_amount: int, 止损数量
            price_type: int, 选价类型，默认 11
            price: float, 下单价格，默认 0
            volume: int, 下单数量，默认 0
            strategy_name: str, 策略名称，默认为空
            quick_trade: int, 快速交易标志，默认 2
            userid: str, 用户ID，默认为空

        返回:
            dict - 止损单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "stoploss",              # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "警告信息"               # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/stoploss_limitprice', json={
            "stoplossCode": stoploss_code, "orderType": order_type, "opType": op_type,
            "account": account, "stockCode": stock_code, "stopPrice": stop_price,
            "stopAmount": stop_amount, "priceType": price_type, "price": price,
            "volume": volume, "strategyName": strategy_name, "quickTrade": quick_trade, "userid": userid
        })

    def stoploss_marketprice(self, stoploss_code, order_type, op_type, account, stock_code, trigger_price, stop_amount, price_type=11, volume=0, strategy_name='', quick_trade=2, userid=''):
        """市价止损单

        参数:
            stoploss_code: str, 止损代码
            order_type: int, 订单类型
            op_type: int, 操作类型
            account: str, 账户ID
            stock_code: str, 股票代码，如 '600000.SH'
            trigger_price: float, 市价触发价格
            stop_amount: int, 止损数量
            price_type: int, 选价类型，默认 11
            volume: int, 下单数量，默认 0
            strategy_name: str, 策略名称，默认为空
            quick_trade: int, 快速交易标志，默认 2
            userid: str, 用户ID，默认为空

        返回:
            dict - 止损单结果
            {
                "status": "success",
                "order_ref": "12345",              # str, 委托引用号
                "action": "stoploss",              # str, 操作类型
                "stock": "600000.SH"               # str, 股票代码
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"               # str, 错误信息
            }
            下单未产生委托:
            {
                "status": "warning",
                "message": "警告信息"               # str, 警告信息
            }
        """
        return self._req('POST', '/api/trade/stoploss_marketprice', json={
            "stoplossCode": stoploss_code, "orderType": order_type, "opType": op_type,
            "account": account, "stockCode": stock_code, "triggerPrice": trigger_price,
            "stopAmount": stop_amount, "priceType": price_type, "volume": volume,
            "strategyName": strategy_name, "quickTrade": quick_trade, "userid": userid
        })

    def make_option_combination(self, account, opt_comb_list, hedge_ratio=1, quick_trade=2, userid=''):
        """组建期权组合

        参数:
            account: str, 账户ID
            opt_comb_list: list, 期权组合列表
            hedge_ratio: float, 对冲比例，默认 1
            quick_trade: int, 快速交易标志，默认 2
            userid: str, 用户ID，默认为空

        返回:
            dict - 组合结果
            {
                "status": "success",
                "message": "期权组合组建成功",              # str, 结果说明
                "order_ref": "12345"                        # str, 委托引用号
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"                        # str, 错误信息
            }
        """
        return self._req('POST', '/api/trade/make_option_combination', json={
            "account": account, "optCombList": opt_comb_list, "hedgeRatio": hedge_ratio,
            "quickTrade": quick_trade, "userid": userid
        })

    def release_option_combination(self, account, opt_comb_list, quick_trade=2, userid=''):
        """拆分期权组合

        参数:
            account: str, 账户ID
            opt_comb_list: list, 期权组合列表
            quick_trade: int, 快速交易标志，默认 2
            userid: str, 用户ID，默认为空

        返回:
            dict - 拆分结果
            {
                "status": "success",
                "message": "期权组合拆分成功",              # str, 结果说明
                "order_ref": "12345"                        # str, 委托引用号
            }
            下单失败:
            {
                "status": "error",
                "message": "错误描述"                        # str, 错误信息
            }
        """
        return self._req('POST', '/api/trade/release_option_combination', json={
            "account": account, "optCombList": opt_comb_list,
            "quickTrade": quick_trade, "userid": userid
        })

    def get_unclosed_compacts(self, account, stock_code='', compact_type=''):
        """查询未平仓合约

        参数:
            account: str, 账户ID
            stock_code: str, 股票代码，如 '600000.SH'，默认为空（全部）
            compact_type: str, 合约类型，默认为空（全部）

        返回:
            dict - 未平仓合约列表
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_strCompactType": "融资",          # str, 合约类型
                        "m_dCompactedAmount": 10000.0,       # float, 合约金额
                        "m_dRepaidAmount": 5000.0,           # float, 已还金额
                        "m_dRemainAmount": 5000.0,           # float, 剩余金额
                        "m_strCompactDate": "20240101",      # str, 合约日期
                        "m_strEndDate": "20240701",          # str, 到期日期
                        ...其他合约字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/trade/unclosed_compacts', json={
            "account": account, "stockCode": stock_code, "compactType": compact_type
        })

    def get_closed_compacts(self, account, stock_code='', compact_type=''):
        """查询已平仓合约

        参数:
            account: str, 账户ID
            stock_code: str, 股票代码，如 '600000.SH'，默认为空（全部）
            compact_type: str, 合约类型，默认为空（全部）

        返回:
            dict - 已平仓合约列表
            {
                "data": [
                    {
                        "m_strInstrumentID": "600000.SH",   # str, 股票代码
                        "m_strCompactType": "融资",          # str, 合约类型
                        "m_dCompactedAmount": 10000.0,       # float, 合约金额
                        "m_dRepaidAmount": 10000.0,          # float, 已还金额
                        "m_strCompactDate": "20240101",      # str, 合约日期
                        "m_strCloseDate": "20240201",        # str, 平仓日期
                        ...其他合约字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/trade/closed_compacts', json={
            "account": account, "stockCode": stock_code, "compactType": compact_type
        })

    def get_option_subject_position(self, account, opt_code=''):
        """获取期权标的持仓

        参数:
            account: str, 账户ID
            opt_code: str, 期权代码，默认为空（全部）

        返回:
            dict - 期权标的持仓
            {
                "data": [
                    {
                        "m_strOptCode": "10003720.SH",      # str, 期权代码
                        "m_strUnderlyingCode": "510050.SH",  # str, 标的代码
                        "m_nVolume": 100,                     # int, 持仓数量
                        "m_nDirection": 1,                    # int, 方向
                        ...其他持仓字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/option_subject_position', json={
            "account": account, "optCode": opt_code
        })

    def get_comb_option(self, account):
        """获取期权组合持仓

        参数:
            account: str, 账户ID

        返回:
            dict - 期权组合持仓
            {
                "data": [
                    {
                        "m_strCombCode": "xxx",               # str, 组合代码
                        "m_strOptCode1": "10003720.SH",      # str, 期权1代码
                        "m_strOptCode2": "10003721.SH",      # str, 期权2代码
                        "m_nVolume": 10,                      # int, 组合数量
                        "m_nCombType": 1,                     # int, 组合类型
                        ...其他组合字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/data/comb_option', json={"account": account})

    def call_formula(self, formula_name, params=None):
        """调用自定义公式

        参数:
            formula_name: str, 公式名称
            params: list, 公式参数列表，默认为空列表

        返回:
            dict - 公式计算结果
            {
                "data": {
                    "result": ...,                            # 公式计算结果
                    ...其他返回字段
                }
            }
        """
        return self._req('POST', '/api/ext/call_formula', json={
            "formula_name": formula_name, "params": params or []
        })

    def get_ext_all_data(self, extdataname, stockcode='', start_time='', end_time=''):
        """获取外部引用全部数据

        参数:
            extdataname: str, 外部数据名称
            stockcode: str, 股票代码，如 '600000.SH'，默认为空
            start_time: str, 开始时间，如 '20240101'，默认为空
            end_time: str, 结束时间，如 '20241231'，默认为空

        返回:
            dict - 外部引用全部数据
            {
                "data": {
                    "times": [1704067200000, ...],          # list[int], 时间戳列表
                    "values": [7.55, 7.60, ...]            # list[float], 数据值列表
                }
            }
        """
        return self._req('POST', '/api/ext/ext_all_data', json={
            "extdataname": extdataname, "stockcode": stockcode,
            "start_time": start_time, "end_time": end_time
        })

    # ============= 兼容方法(原有) =============
    def get_deal(self, account='stock'):
        """查询当日成交记录

        参数:
            account: str, 账户类型，默认 'stock'

        返回:
            dict - 成交列表
            {
                "deals": [
                    {
                        "m_strInstrumentID": "600000",         # str, 股票代码（不含交易所后缀）
                        "m_strExchangeID": "SH",               # str, 交易所
                        "m_nDirection": 48,                    # int, 委托方向（48=买入, 49=卖出）
                        "m_dPrice": 7.55,                      # float, 成交价格
                        "m_nVolume": 100,                      # int, 成交数量
                        "m_dTradeAmount": 755.0,               # float, 成交金额
                        "m_strTradeTime": "093005",            # str, 成交时间(HHmmss)
                        "m_strTradeDate": "20260706",          # str, 成交日期
                        "m_strOrderRef": "7692771559857651379",# str, 委托内部引用号（长ID）
                        "m_strOrderSysID": "8384",             # str, 委托系统编号（短ID）
                        "m_strTradeID": "0000000050050384",    # str, 成交编号
                        "m_dCommission": 0.23,                 # float, 手续费
                        "m_strInstrumentName": "浦发银行",       # str, 股票名称
                        ...其他成交字段
                    },
                    ...
                ]
            }
        """
        return self._req('POST', '/api/order/deal', json={"account": account})


# ============= 测试示例 =============
def unit_test():
    client = QMTClient()
    account_type = "stock"  # 根据实际账户调整

    # # 1. 查询资金
    print("[1] 总资金:", client.get_total_money(account_type))
    print("[2] 可用资金:", client.get_available_money(account_type))

    # # 2. 查询持仓
    print("[3] 持仓信息:", json.dumps(client.get_holding(account_type), indent=2, ensure_ascii=False))

    # orders = client.get_order_status()
    # print(orders)

    print("[4] python 版本信息:", client.python_version()) # 返回qmt python 版本信息

    # client.close()

    print("[5] 板块信息:", client.get_sector('000300.SH'))
    print("[6] 行业信息:", client.get_industry('CSRC餐饮业'))
    print("[7] 市场数据信息:", json.dumps(client.get_market_data_ex(['600000.SH', '000001.SZ']), indent=2, ensure_ascii=False))
    print("[8] 最新行情信息:", json.dumps(client.get_full_tick('600000.SH'), indent=2, ensure_ascii=False)) 
    # client.buy_stock("600000.SZ", 6.80, 100)


if __name__ == "__main__":

    unit_test()
# -*- coding: utf-8 -*-
"""
一键运行全部测试
用法:
  python run_all_tests.py           # 运行数据测试(01-07)
  python run_all_tests.py --all     # 运行全部测试(01-13, 含交易)
  python run_all_tests.py --trade   # 只运行交易测试(10-13)
  python run_all_tests.py --yes     # 交易测试自动确认
  python run_all_tests.py 3 5       # 只运行test_03和test_05
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据测试文件
DATA_TESTS = [
    "test_01_compat.py",
    "test_02_context.py",
    "test_03_data_query.py",
    "test_04_subscribe.py",
    "test_05_judge.py",
    "test_06_account.py",
    "test_07_ext_func.py",
]

# 交易测试文件
TRADE_TESTS = [
    "test_10_trade_pending.py",
    "test_11_trade_fill.py",
    "test_12_trade_order_api.py",
    "test_13_trade_future.py",
]


def run_test(script, extra_args=None):
    """运行单个测试脚本，返回是否通过"""
    path = os.path.join(SCRIPT_DIR, script)
    if not os.path.exists(path):
        print("  文件不存在: {}".format(path))
        return False
    cmd = [sys.executable, path]
    if extra_args:
        cmd.extend(extra_args)
    print("\n" + "#" * 60)
    print("# 运行: {}".format(script))
    print("#" * 60)
    ret = subprocess.call(cmd)
    passed = ret == 0
    status = "PASS" if passed else "FAIL"
    print("\n>> {} : {}".format(script, status))
    return passed


def main():
    args = sys.argv[1:]
    run_all = "--all" in args
    run_trade_only = "--trade" in args
    auto_yes = "--yes" in args
    extra_args = ["--yes"] if auto_yes else []

    # 提取数字参数（指定要运行的测试编号）
    specific_nums = []
    for a in args:
        if a.isdigit():
            specific_nums.append(int(a))

    if specific_nums:
        # 运行指定编号的测试
        all_tests = DATA_TESTS + TRADE_TESTS
        selected = []
        for n in specific_nums:
            idx = n - 1
            if 0 <= idx < len(all_tests):
                selected.append(all_tests[idx])
            else:
                print("  警告: 测试编号{}超出范围(1-{})".format(n, len(all_tests)))
        if not selected:
            print("  无有效测试编号")
            sys.exit(1)
        tests = selected
    elif run_trade_only:
        tests = TRADE_TESTS
    elif run_all:
        tests = DATA_TESTS + TRADE_TESTS
    else:
        tests = DATA_TESTS

    print("将运行 {} 个测试: ".format(len(tests)))
    for t in tests:
        print("  - {}".format(t))

    results = {}
    for t in tests:
        results[t] = run_test(t, extra_args)

    # 汇总
    print("\n" + "=" * 60)
    print("全部测试汇总:")
    print("=" * 60)
    for t, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print("  {}  {}".format(status, t))

    passed_count = sum(1 for v in results.values() if v)
    failed_count = len(results) - passed_count
    print("\n  总计: {} PASS / {} FAIL".format(passed_count, failed_count))

    if failed_count > 0:
        sys.exit(1)
    else:
        print("\n全部测试通过!")
        sys.exit(0)


if __name__ == "__main__":
    main()

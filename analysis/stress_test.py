"""查询优化对比 + 并发压力测试。

对比两组查询：
  A 优化前：对 ODS 全量文本表按金额过滤（无分区裁剪、TextFile 全扫）
  B 优化后：DWD ORC 分区表带 order_dt 分区裁剪（等价业务口径）

并发压测：并发度 1/2/4/8，每组重复 3 轮，记录平均/最大响应时间与吞吐。

用法：python analysis/stress_test.py
"""
import concurrent.futures
import json
import pathlib
import statistics
import subprocess
import time

BASE = pathlib.Path(__file__).resolve().parent
OUT = BASE / "out"
OUT.mkdir(exist_ok=True)

HIVE = ["docker", "exec", "hive-server", "beeline", "-u", "jdbc:hive2://localhost:10000",
        "-n", "hive", "--silent=true", "--showHeader=false", "--outputformat=tsv2"]

# A：无分区裁剪 + TextFile 全表扫描（ODS 层 15,600 行原始表）
Q_A = ("SELECT COUNT(*), ROUND(SUM(CASE WHEN pay_amount > 0 THEN pay_amount ELSE 0 END),2) "
       "FROM ydsh_ods.ods_order WHERE pay_amount BETWEEN 100 AND 5000;")

# B：分区裁剪 + ORC（DWD 层，等价业务口径——12 月有效订单金额）
Q_B = ("SELECT COUNT(*), ROUND(SUM(pay_amount),2) FROM ydsh_dwd.dwd_order "
       "WHERE order_dt BETWEEN '2024-12-01' AND '2024-12-31';")

# B'：同表不带分区条件的全扫，用于量化分区裁剪收益
Q_B_NOCUT = ("SELECT COUNT(*), ROUND(SUM(pay_amount),2) FROM ydsh_dwd.dwd_order;")

REPEAT = 3


def run_q(sql: str) -> float:
    t0 = time.time()
    r = subprocess.run(HIVE + ["-e", sql], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-200:])
    return time.time() - t0


def bench_serial(sql: str, label: str) -> dict:
    ts = [run_q(sql) for _ in range(REPEAT)]
    return {"query": label, "mode": "serial", "n": REPEAT,
            "avg": round(statistics.mean(ts), 2), "max": round(max(ts), 2), "min": round(min(ts), 2)}


def bench_concurrent(sql: str, label: str, workers: int, rounds: int = REPEAT) -> dict:
    lat = []
    t_start = time.time()
    for _ in range(rounds):
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            lat.extend(list(ex.map(lambda _: run_q(sql), range(workers))))
    wall = time.time() - t_start
    return {"query": label, "mode": f"concurrent-{workers}", "n": len(lat),
            "avg": round(statistics.mean(lat), 2), "max": round(max(lat), 2),
            "min": round(min(lat), 2),
            "wall_total": round(wall, 2),
            "throughput_qps": round(len(lat) / wall, 2)}


def main() -> int:
    print("== 单查询对比（串行，预热后取 3 轮均值）==")
    results = [
        bench_serial(Q_A, "A-ODS文本全扫(无分区)"),
        bench_serial(Q_B_NOCUT, "B0-DWD_ORC全扫(无分区裁剪)"),
        bench_serial(Q_B, "B-DWD_ORC分区裁剪(12月)"),
    ]
    for r in results:
        print(r)

    print("\n== 并发压测（B 查询，并发度 1/2/4/8 × 3 轮）==")
    for w in (1, 2, 4, 8):
        r = bench_concurrent(Q_B, "B-DWD_ORC分区裁剪(12月)", w)
        results.append(r)
        print(r)

    out = OUT / "stress_test.json"
    import io
    io.open(out, "w", encoding="utf-8").write(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"\n已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

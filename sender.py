# -*- coding: utf-8 -*-

import time
import os
import csv
import random
import psutil
import matplotlib.pyplot as plt
from datetime import datetime

from receiver import Receiver
from middleware_cb import CircuitBreakerMiddleware
from middleware_replica import ActiveReplicationMiddleware
from middleware_pipeline import StagePipelineMiddleware


# ============================
# Backend simulador (falhas downstream)
# ============================

class BackendSimulator:
    """
    Simula o backend (microserviços) e o link middleware->cloud:
    Retorna (ok, latency_s). A chamada dorme para simular latência.
    Pode falhar por:
      - flapping (probabilístico)
      - outage (janela de indisponibilidade)
      - slow/backpressure (latência alta + timeout)
    """

    def __init__(self, scenario_name, start_t, rng: random.Random):
        self.scenario = scenario_name
        self.start_t = start_t
        self.rng = rng

    def call(self, msg_id: str, ctx: dict):
        now = time.perf_counter()
        t = now - self.start_t

        # parâmetros base
        base_latency = float(ctx.get("base_latency_s", 0.005))
        timeout_s = float(ctx.get("timeout_s", 0.08))  # para slow/backpressure

        # cenário 1: flapping
        if self.scenario == "flapping":
            p_fail = float(ctx.get("p_fail", 0.20))
            # latência pequena e variável
            lat = base_latency + self.rng.uniform(0.0, 0.004)
            time.sleep(lat)
            if self.rng.random() < p_fail:
                return (False, lat)
            return (True, lat)

        # cenário 2: outage com retorno
        if self.scenario == "outage":
            outage_from = float(ctx.get("outage_from_s", 2.0))
            outage_to = float(ctx.get("outage_to_s", 5.0))
            lat = base_latency + self.rng.uniform(0.0, 0.004)
            time.sleep(lat)
            if outage_from <= t <= outage_to:
                return (False, lat)
            return (True, lat)

        # cenário 3: slow/backpressure
        if self.scenario == "slow":
            slow_from = float(ctx.get("slow_from_s", 2.0))
            slow_latency = float(ctx.get("slow_latency_s", 0.12))  # > timeout => falha
            if t >= slow_from:
                lat = slow_latency + self.rng.uniform(0.0, 0.02)
            else:
                lat = base_latency + self.rng.uniform(0.0, 0.004)

            time.sleep(lat)

            # timeout simula backpressure/timeouts no backend
            if lat > timeout_s:
                return (False, lat)
            return (True, lat)

        # default
        lat = base_latency
        time.sleep(lat)
        return (True, lat)


# ============================
# Medição de recursos
# ============================

def measure_resources(block_fn):
    """
    Mede CPU% (CPU time / wall), memória pico (RSS MB) e duração.
    """
    proc = psutil.Process(os.getpid())
    t0 = time.perf_counter()
    cpu0 = proc.cpu_times()
    rss_peak = proc.memory_info().rss

    def update_peak():
        nonlocal rss_peak
        rss = proc.memory_info().rss
        if rss > rss_peak:
            rss_peak = rss

    block_fn(update_peak)

    cpu1 = proc.cpu_times()
    t1 = time.perf_counter()

    cpu_time = (cpu1.user - cpu0.user) + (cpu1.system - cpu0.system)
    wall = max(t1 - t0, 1e-9)
    cpu_percent = 100.0 * (cpu_time / wall)
    mem_peak_mb = rss_peak / (1024 * 1024)
    return cpu_percent, mem_peak_mb, (t1 - t0)


# ============================
# Experimento
# ============================

def run_experiment_for_middleware(
    mw_name,
    middleware,
    scenario_name,
    total_messages=200,
    send_interval_s=0.01,
    drain_s=2.5,
    seed=123
):
    rng = random.Random(seed)
    start_t = time.perf_counter()

    receiver = Receiver()

    # contexto do cenário (ajuste fino aqui)
    ctx = {
        "base_latency_s": 0.005,
        "timeout_s": 0.08,

        # flapping
        "p_fail": 0.20,

        # outage
        "outage_from_s": 2.0,
        "outage_to_s": 5.0,

        # slow/backpressure
        "slow_from_s": 2.0,
        "slow_latency_s": 0.12,

        # pipeline stage2
        "pipeline_stage2_extra_s": 0.0,
    }

    def block(update_peak):
        for i in range(total_messages):
            msg_id = f"MSG-{i}"
            t_send = time.perf_counter()
            receiver.mark_sent(msg_id, t_send)

            middleware.process_message(
                msg_id=msg_id,
                receiver=receiver,
                t_send=t_send,
                ctx=ctx
            )

            if i % 10 == 0:
                update_peak()

            time.sleep(send_interval_s)

        # dreno (para pipeline tentar recuperar após outage)
        if hasattr(middleware, "drain"):
            middleware.drain(receiver=receiver, ctx=ctx, max_drain_s=drain_s)

    cpu_percent, mem_peak_mb, duration_s = measure_resources(block)

    # métricas
    delivered = receiver.delivered_count()
    loss = receiver.loss_rate(total_messages)
    dup_rate = receiver.duplicate_rate(total_messages)
    extra_copies = receiver.extra_copies_per_message(total_messages)

    lat = receiver.latency_stats_ms()
    throughput = delivered / max(duration_s, 1e-9)

    recovery_mean_s = None
    if hasattr(middleware, "recovery_times_s") and middleware.recovery_times_s:
        recovery_mean_s = sum(middleware.recovery_times_s) / len(middleware.recovery_times_s)

    divergence = None
    if hasattr(middleware, "replicas"):
        divergence = receiver.replica_divergence_rate(expected_replicas=int(middleware.replicas))

    middleware.close()

    return {
        "scenario": scenario_name,
        "middleware": mw_name,
        "total_messages": total_messages,
        "delivered": delivered,
        "loss_rate": loss,
        "dup_rate": dup_rate,
        "extra_copies_per_msg": extra_copies,
        "lat_mean_ms": lat["mean_ms"],
        "lat_p95_ms": lat["p95_ms"],
        "throughput_msg_s": throughput,
        "cpu_percent": cpu_percent,
        "mem_peak_mb": mem_peak_mb,
        "duration_s": duration_s,
        "recovery_mean_s": recovery_mean_s,
        "replica_divergence_rate": divergence,
    }


def build_middlewares(scenario_name, seed_base=1000):
    """
    Cria backends simulados e middlewares.
    Replicação recebe 3 backends independentes (réplicas).
    """
    start_t = time.perf_counter()
    rng_main = random.Random(seed_base)

    backend_cb = BackendSimulator(scenario_name, start_t=start_t, rng=random.Random(rng_main.randint(1, 10**9)))
    backend_pipe = BackendSimulator(scenario_name, start_t=start_t, rng=random.Random(rng_main.randint(1, 10**9)))

    backends_rep = [
        BackendSimulator(scenario_name, start_t=start_t, rng=random.Random(rng_main.randint(1, 10**9))),
        BackendSimulator(scenario_name, start_t=start_t, rng=random.Random(rng_main.randint(1, 10**9))),
        BackendSimulator(scenario_name, start_t=start_t, rng=random.Random(rng_main.randint(1, 10**9))),
    ]

    cb = CircuitBreakerMiddleware(backend=backend_cb, threshold=5, cooldown_s=1.0)
    rep = ActiveReplicationMiddleware(backends=backends_rep)
    pipe = StagePipelineMiddleware(backend=backend_pipe, max_retries=6, backoff_s=0.05)

    return {
        "Circuit Breaker": cb,
        "Replicação Ativa": rep,
        "Pipeline por Estágios": pipe,
    }


# ============================
# Saída: CSV + gráficos
# ============================

def save_csv(results, out_name):
    with open(out_name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Scenario", "Middleware",
            "Total", "Delivered",
            "LossRate", "DupRate", "ExtraCopiesPerMsg",
            "LatencyMeanMs", "LatencyP95Ms",
            "ThroughputMsgS",
            "CPUPercent", "MemPeakMB", "DurationS",
            "RecoveryMeanS", "ReplicaDivergenceRate"
        ])
        for r in results:
            w.writerow([
                r["scenario"], r["middleware"],
                r["total_messages"], r["delivered"],
                f"{r['loss_rate']:.4f}", f"{r['dup_rate']:.4f}", f"{r['extra_copies_per_msg']:.4f}",
                f"{r['lat_mean_ms']:.3f}", f"{r['lat_p95_ms']:.3f}",
                f"{r['throughput_msg_s']:.3f}",
                f"{r['cpu_percent']:.2f}", f"{r['mem_peak_mb']:.2f}", f"{r['duration_s']:.3f}",
                "" if r["recovery_mean_s"] is None else f"{r['recovery_mean_s']:.3f}",
                "" if r["replica_divergence_rate"] is None else f"{r['replica_divergence_rate']:.4f}",
            ])


def plot_two_metrics_per_scenario(
    results,
    scenario_name,
    metric_left,
    metric_right,
    label_left,
    label_right,
    y1_lim=None,
    y2_lim=None,
    title="",
    out_name="plot.png"
):
    """
    Plota 2 métricas em barras lado a lado com CORES DIFERENTES:
      - métrica esquerda: azul
      - métrica direita: laranja
    E com legendas corretas.
    """
    rows = [r for r in results if r["scenario"] == scenario_name]
    labels = [r["middleware"] for r in rows]

    v1 = [r[metric_left] for r in rows]
    v2 = [r[metric_right] for r in rows]

    x = list(range(len(labels)))
    width = 0.35

    color_left = "#1f77b4"   # azul padrão Matplotlib
    color_right = "#ff7f0e"  # laranja padrão Matplotlib

    plt.figure(figsize=(10, 6))
    ax1 = plt.gca()

    b1 = ax1.bar(
        [p - width / 2 for p in x],
        v1,
        width=width,
        label=label_left,
        color=color_left
    )
    ax1.set_ylabel(label_left)
    if y1_lim:
        ax1.set_ylim(*y1_lim)

    ax2 = ax1.twinx()
    b2 = ax2.bar(
        [p + width / 2 for p in x],
        v2,
        width=width,
        label=label_right,
        color=color_right
    )
    ax2.set_ylabel(label_right)
    if y2_lim:
        ax2.set_ylim(*y2_lim)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=10)
    plt.title(title)

    # legenda única (combina as duas)
    handles = [b1, b2]
    labels_leg = [label_left, label_right]
    plt.legend(handles, labels_leg, loc="upper left")

    plt.tight_layout()
    plt.savefig(out_name)
    plt.close()


def run_all():
    scenarios = ["flapping", "outage", "slow"]

    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for sc in scenarios:
        print(f"\n=== Rodando cenário: {sc} ===")
        mws = build_middlewares(sc, seed_base=1000)

        for name, mw in mws.items():
            r = run_experiment_for_middleware(
                mw_name=name,
                middleware=mw,
                scenario_name=sc,
                total_messages=200,
                send_interval_s=0.01,
                drain_s=3.0,
                seed=123
            )
            results.append(r)
            print(
                f"  - {name}: delivered={r['delivered']}, "
                f"loss={r['loss_rate']:.3f}, p95={r['lat_p95_ms']:.1f}ms, thr={r['throughput_msg_s']:.1f}"
            )

    csv_name = f"results_all_{timestamp}.csv"
    save_csv(results, csv_name)
    print(f"\n[OK] CSV salvo: {csv_name}")

    # Até 9 gráficos: 3 por cenário
    for sc in scenarios:
        # 1) Loss + Duplicação
        plot_two_metrics_per_scenario(
            results, sc,
            metric_left="loss_rate", metric_right="dup_rate",
            label_left="Loss rate (0–1)", label_right="Dup rate (0–1)",
            y1_lim=(0, 1), y2_lim=(0, 1),
            title=f"{sc.upper()} — Loss vs Duplicação",
            out_name=f"graph_{sc}_loss_dup_{timestamp}.png"
        )
        print(f"[OK] Gráfico: graph_{sc}_loss_dup_{timestamp}.png")

        # 2) Throughput + Latência p95
        plot_two_metrics_per_scenario(
            results, sc,
            metric_left="throughput_msg_s", metric_right="lat_p95_ms",
            label_left="Throughput (msg/s)", label_right="Latência p95 (ms)",
            title=f"{sc.upper()} — Throughput vs Latência p95",
            out_name=f"graph_{sc}_thr_lat_{timestamp}.png"
        )
        print(f"[OK] Gráfico: graph_{sc}_thr_lat_{timestamp}.png")

        # 3) CPU + Memória
        plot_two_metrics_per_scenario(
            results, sc,
            metric_left="cpu_percent", metric_right="mem_peak_mb",
            label_left="CPU (%)", label_right="Memória pico (MB)",
            title=f"{sc.upper()} — CPU vs Memória pico",
            out_name=f"graph_{sc}_cpu_mem_{timestamp}.png"
        )
        print(f"[OK] Gráfico: graph_{sc}_cpu_mem_{timestamp}.png")


def main():
    print("=== Experimentos de Tolerância a Falhas ===")
    print("1 - Rodar tudo (3 cenários × 3 middlewares) => CSV + até 9 gráficos")
    op = input("Opção: ").strip()
    if op == "1":
        run_all()
    else:
        run_all()


if __name__ == "__main__":
    main()
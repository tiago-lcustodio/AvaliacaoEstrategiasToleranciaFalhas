import math
from collections import defaultdict

class Receiver:
    """
    Coleta métricas end-to-end (sender -> middleware -> backend).
    - Latência: tempo até PRIMEIRA entrega bem-sucedida por msg_id
    - Duplicações: sucessos adicionais após o primeiro
    - Replicação: rastreia quais réplicas entregaram por msg_id
    """

    def __init__(self):
        self.sent_ts = {}
        self.first_ok_ts = {}
        self.success_count = defaultdict(int)

        # replicação: msg_id -> set(replica_id)
        self.replica_success = defaultdict(set)

    def mark_sent(self, msg_id: str, t_send: float):
        self.sent_ts[msg_id] = t_send

    def mark_success(self, msg_id: str, t_ok: float, replica_id=None):
        self.success_count[msg_id] += 1

        if msg_id not in self.first_ok_ts:
            self.first_ok_ts[msg_id] = t_ok

        if replica_id is not None:
            self.replica_success[msg_id].add(replica_id)

    def delivered_count(self):
        return len(self.first_ok_ts)

    def loss_rate(self, total_messages: int):
        if total_messages <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.delivered_count() / total_messages))

    def duplicate_rate(self, total_messages: int):
        """
        Fração de mensagens que tiveram duplicação (mais de 1 sucesso).
        (é mais interpretável do que "cópias extras / total")
        """
        if total_messages <= 0:
            return 0.0
        dup_msgs = 0
        for msg_id, c in self.success_count.items():
            if c >= 2:
                dup_msgs += 1
        return dup_msgs / total_messages

    def extra_copies_per_message(self, total_messages: int):
        """
        Média de cópias extras por mensagem (sucessos adicionais além do primeiro).
        """
        if total_messages <= 0:
            return 0.0
        extra = 0
        for msg_id, c in self.success_count.items():
            extra += max(0, c - 1)
        return extra / total_messages

    def latency_stats_ms(self):
        """
        Latência calculada só para mensagens entregues (first_ok_ts).
        """
        lats = []
        for msg_id, t_ok in self.first_ok_ts.items():
            t_send = self.sent_ts.get(msg_id)
            if t_send is None:
                continue
            lat_ms = (t_ok - t_send) * 1000.0
            if lat_ms >= 0:
                lats.append(lat_ms)

        if not lats:
            return {"mean_ms": 0.0, "p95_ms": 0.0, "count": 0}

        lats.sort()
        mean_ms = sum(lats) / len(lats)
        p95_idx = int(0.95 * (len(lats) - 1))
        p95_ms = lats[p95_idx]
        return {"mean_ms": float(mean_ms), "p95_ms": float(p95_ms), "count": len(lats)}

    def replica_divergence_rate(self, expected_replicas: int):
        """
        Para replicação ativa: taxa de mensagens cuja cardinalidade de réplicas bem sucedidas
        != expected_replicas. (mensagens divergentes entre réplicas)
        """
        if expected_replicas <= 0:
            return 0.0
        total = len(self.replica_success)
        if total == 0:
            return 0.0
        bad = 0
        for msg_id, reps in self.replica_success.items():
            if len(reps) != expected_replicas:
                bad += 1
        return bad / total
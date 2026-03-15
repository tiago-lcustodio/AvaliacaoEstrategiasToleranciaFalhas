import time
from collections import deque

class StagePipelineMiddleware:
    """
    Pipeline por Estágios com resiliência no estágio final:
    - stage1: valida/normaliza (simula custo pequeno)
    - stage2: transforma (simula custo pequeno/variável)
    - stage3: entrega ao backend com RETRIES + BACKOFF e FILA

    Isso cria diferença real nos cenários de outage/slow:
    - Em outage, ele mantém mensagens na fila e tenta entregar após retorno.
    - Em slow/backpressure, a fila pode crescer (custo: latência/mem).
    """

    def __init__(self, backend, max_retries=6, backoff_s=0.05):
        self.backend = backend
        self.max_retries = max_retries
        self.backoff_s = backoff_s

        self.q = deque()  # itens: (msg_id, attempt, next_try_time)

        # contadores
        self.enqueued = 0
        self.retried = 0

    def close(self):
        pass

    def stage1(self, msg_id: str):
        # valida/normaliza (custo mínimo)
        return msg_id

    def stage2(self, msg_id: str, ctx: dict):
        # pequena transformação (pode aumentar em overload)
        extra = float(ctx.get("pipeline_stage2_extra_s", 0.0))
        time.sleep(0.001 + extra)
        return msg_id

    def _enqueue(self, msg_id: str, attempt: int, delay_s: float):
        self.q.append((msg_id, attempt, time.perf_counter() + delay_s))
        self.enqueued += 1

    def process_message(self, msg_id: str, receiver, t_send: float, ctx: dict):
        # processa estágios 1 e 2 sempre (representa pipeline)
        try:
            mid = self.stage1(msg_id)
            mid = self.stage2(mid, ctx)
        except Exception:
            return

        # tenta entrega imediata (attempt=0)
        ok, _lat = self.backend.call(msg_id=mid, ctx=ctx)
        if ok:
            receiver.mark_success(mid, time.perf_counter())
            return

        # falhou: entra na fila para retry
        self._enqueue(mid, attempt=1, delay_s=self.backoff_s)

    def drain(self, receiver, ctx: dict, max_drain_s: float = 2.0):
        """
        Processa a fila por até max_drain_s (para permitir recuperar após outage).
        """
        t_end = time.perf_counter() + max_drain_s

        while self.q and time.perf_counter() < t_end:
            msg_id, attempt, next_try = self.q[0]
            now = time.perf_counter()
            if now < next_try:
                time.sleep(min(0.01, next_try - now))
                continue

            self.q.popleft()
            ok, _lat = self.backend.call(msg_id=msg_id, ctx=ctx)
            if ok:
                receiver.mark_success(msg_id, time.perf_counter())
                continue

            if attempt < self.max_retries:
                self.retried += 1
                backoff = self.backoff_s * (2 ** (attempt - 1))
                self._enqueue(msg_id, attempt=attempt + 1, delay_s=backoff)
            else:
                # drop final (loss)
                pass
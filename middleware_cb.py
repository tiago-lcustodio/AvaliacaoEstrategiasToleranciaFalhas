import time

class CircuitBreakerMiddleware:
    """
    Circuit Breaker minimalista e "honesto":
    - CLOSED: tenta enviar; em falha incrementa failures
    - se failures >= threshold => OPEN
    - OPEN: não tenta enviar (drop) até cooldown
    - após cooldown => HALF_OPEN: 1 tentativa teste
        - sucesso => CLOSED (registra recovery time)
        - falha => OPEN novamente
    """

    def __init__(self, backend, threshold=5, cooldown_s=1.0):
        self.backend = backend
        self.threshold = threshold
        self.cooldown_s = cooldown_s

        self.state = "CLOSED"   # CLOSED | OPEN | HALF_OPEN
        self.failures = 0
        self.opened_at = None

        self.recovery_times_s = []

    def close(self):
        pass

    def process_message(self, msg_id: str, receiver, t_send: float, ctx: dict):
        now = time.perf_counter()

        if self.state == "OPEN":
            if (now - self.opened_at) >= self.cooldown_s:
                self.state = "HALF_OPEN"
            else:
                # drop while OPEN
                return

        # HALF_OPEN: 1 tentativa
        if self.state == "HALF_OPEN":
            ok, _lat = self.backend.call(msg_id=msg_id, ctx=ctx)
            if ok:
                self.state = "CLOSED"
                if self.opened_at is not None:
                    self.recovery_times_s.append(time.perf_counter() - self.opened_at)
                self.failures = 0
                receiver.mark_success(msg_id, time.perf_counter())
            else:
                self.state = "OPEN"
                self.opened_at = time.perf_counter()
                self.failures = self.threshold
            return

        # CLOSED
        ok, _lat = self.backend.call(msg_id=msg_id, ctx=ctx)
        if ok:
            self.failures = 0
            receiver.mark_success(msg_id, time.perf_counter())
        else:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = "OPEN"
                self.opened_at = time.perf_counter()
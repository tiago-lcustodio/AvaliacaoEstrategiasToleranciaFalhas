import time

class ActiveReplicationMiddleware:
    """
    Replicação Ativa (simplificada):
    - envia para N réplicas independentes
    - considera a mensagem entregue se >=1 réplica responder OK
    - registra duplicações (quando >1 replica OK)
    - registra divergência via receiver.replica_success
    """

    def __init__(self, backends):  # lista de backends (réplicas)
        self.backends = backends
        self.replicas = len(backends)

    def close(self):
        pass

    def process_message(self, msg_id: str, receiver, t_send: float, ctx: dict):
        any_ok = False
        for r, be in enumerate(self.backends):
            ok, _lat = be.call(msg_id=msg_id, ctx=ctx)
            if ok:
                any_ok = True
                receiver.mark_success(msg_id, time.perf_counter(), replica_id=r)

        # se nenhuma replica respondeu, não marca success (loss)
        return
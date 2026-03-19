# AvaliacaoEstrategiasToleranciaFalhas  
em Middlewares MQTT para IoT

Este repositório contém a implementação experimental utilizada no artigo:

**“Avaliação de Estratégias de Tolerância a Falhas em Middlewares MQTT para IoT”**  
(Submetido à WTF 2026)

O objetivo é comparar três padrões clássicos de resiliência aplicados a middlewares MQTT:

- Circuit Breaker  
- Replicação Ativa  
- Pipeline por Estágios  

A avaliação é realizada por meio de simulações controladas de falhas no backend (downstream), em um contexto típico de arquiteturas IoT Edge–Cloud.

---

## 📌 Visão Geral

O sistema simula o seguinte fluxo:
> Sender (dispositivo IoT) → Middleware → Backend (simulado) → Receiver (métricas)


As falhas são injetadas **no backend**, representando cenários realistas onde o consumidor é instável, indisponível ou lento.

---

## ⚙️ Cenários de Falha

Os experimentos consideram três cenários:

- **flapping** → instabilidade intermitente  
- **outage** → indisponibilidade total  
- **slow** → consumidor extremamente lento (timeout/backpressure)

---

## 📊 Métricas Coletadas

- Taxa de perda (`loss_rate`)
- Taxa de duplicação (`dup_rate`)
- Cópias extras por mensagem
- Latência média e p95
- Vazão (mensagens por segundo)
- Uso de CPU (%)
- Pico de memória (MB)
- Tempo de execução
- Tempo de recuperação (Circuit Breaker)
- Divergência entre réplicas (Replicação Ativa)

Os resultados são exportados em **CSV** e visualizados via gráficos.

---

## 📁 Estrutura do Projeto
├── sender.py # Orquestra os experimentos
├── receiver.py # Coleta e calcula métricas
├── middleware_cb.py # Circuit Breaker
├── middleware_replica.py # Replicação Ativa
├── middleware_pipeline.py # Pipeline por Estágios
│
└── GerarResultadosFinais/
└── plot_results.py # Geração dos gráficos finais


---

## 🧠 Descrição dos Componentes

### `sender.py`
- Script principal
- Executa os experimentos
- Injeta falhas via `BackendSimulator`
- Mede CPU, memória e tempo
- Gera CSV com resultados

### `receiver.py`
- Responsável por métricas end-to-end
- Calcula:
  - entrega
  - perda
  - duplicação
  - latência
  - divergência entre réplicas

### `middleware_cb.py`
- Implementa Circuit Breaker
- Estados: `CLOSED`, `OPEN`, `HALF_OPEN`
- Foco: **fail-fast e contenção**

### `middleware_replica.py`
- Replicação ativa (N réplicas)
- Envio paralelo
- Foco: **alta disponibilidade**
- Custo: duplicação e CPU

### `middleware_pipeline.py`
- Pipeline com:
  - estágios
  - fila
  - retries com backoff
- Foco: **resiliência temporal**

### `plot_results.py`
- Lê os CSVs gerados
- Gera gráficos comparativos:
  - perda vs duplicação
  - vazão vs latência
  - CPU vs memória

---

## ▶️ Como Executar

### 1. Rodar os experimentos

Na raiz do projeto:

> python sender.py

Selecione:

1 - Rodar tudo

Isso irá:

Executar todos os cenários  

Testar todos os middlewares  

Gerar um arquivo .csv com timestamp  

E depois na pasta GerarResultadosFinais: 

> python plot_results.py


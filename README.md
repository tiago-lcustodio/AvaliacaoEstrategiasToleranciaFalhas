# AvaliacaoEstrategiasToleranciaFalhas em Middlewares MQTT para IoT

Este repositório contém a implementação experimental utilizada no artigo “Avaliação de Estratégias de Tolerância a Falhas em Middlewares MQTT para IoT”, submetido à WTF 2026. O objetivo do trabalho é comparar o comportamento de três padrões de resiliência — Circuit Breaker, Replicação Ativa e Pipeline por Estágios — sob diferentes cenários de falha em sistemas baseados em MQTT.

## Organização do Experimento

O sistema simula um fluxo típico de aplicações IoT, no qual um produtor envia mensagens a um middleware que, por sua vez, interage com um backend. As falhas são injetadas no backend, permitindo avaliar a capacidade do middleware em lidar com instabilidade, indisponibilidade e degradação de desempenho no downstream.

## Cenários de Falha

Os experimentos são conduzidos em três cenários: flapping, que representa instabilidade intermitente; outage, que representa indisponibilidade total do backend por um intervalo de tempo; e slow consumer, que representa degradação severa de desempenho com aumento de latência e ocorrência de timeouts.

## Métricas Avaliadas

Durante a execução dos experimentos são coletadas métricas relacionadas à confiabilidade, desempenho e custo operacional. Entre elas estão taxa de perda, taxa de duplicação, latência média e no percentil 95, vazão em mensagens por segundo, uso de CPU, pico de memória, tempo total de execução, tempo de recuperação e divergência entre réplicas.

## Estrutura do Código

O arquivo sender.py é responsável pela execução dos experimentos e pela orquestração dos cenários de falha. O receiver.py realiza a coleta e o cálculo das métricas. Os arquivos middleware_cb.py, middleware_replica.py e middleware_pipeline.py implementam, respectivamente, os padrões Circuit Breaker, Replicação Ativa e Pipeline por Estágios. A pasta GerarResultadosFinais contém o script plot_results.py, utilizado para a geração dos gráficos a partir dos resultados em formato CSV.

## Execução

Para executar os experimentos, deve-se rodar o script principal na raiz do projeto utilizando o comando “python sender.py”. Após a execução, será gerado um arquivo CSV contendo os resultados. Esse arquivo deve ser movido para a pasta GerarResultadosFinais, onde o script “python plot_results.py” pode ser executado para a geração dos gráficos comparativos.

## Considerações

Os experimentos são realizados em ambiente controlado, com parâmetros fixos e injeção programática de falhas, garantindo reprodutibilidade. A avaliação concentra-se no comportamento do middleware no trecho entre middleware e backend, não contemplando falhas no produtor ou na rede upstream.

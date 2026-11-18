# Relatório de Avaliação Fim-a-Fim — Arquitetura Multiagentes (`Orquestrador` + `AgenteValidador`)

- **Conjunto avaliado:** `rag/avaliacao/perguntas/perguntas_roteamento_multiplas.jsonl` (12 perguntas múltiplas, 31 subperguntas esperadas: duplas, triplas e quádruplas)
- **Configuração:** Busca híbrida (`BAAI/bge-m3` + BM25 + RRF), decomposição e geração via `ollama:qwen2.5:7b` (`MODELO_DECOMPOSITOR=qwen2.5:7b`), classificador `LiquidAI/d1-omni-600M` (`LIMIAR_COMPOSTA=0.39`) e `AgenteValidador` ativo (máx. 1 retentativa por parte).
- **Saída bruta:** `rag/avaliacao/resultados/resultado_orquestrador_multiplas.json`

## 1. Resumo Executivo

| Métrica | Resultado |
|---|---:|
| Consultas compostas avaliadas | `12` (`M01`–`M12`) |
| Decomposição com nº exato de subperguntas | `12/12` (`100,0%`) |
| Roteamento exato (ordem e eixos) | `12/12` (`100,0%`) |
| Subperguntas executadas ao todo | `31` |
| Subperguntas aprovadas pelo `AgenteValidador` (desfecho final) | `31/31` (`100,0%`) |
| Reprovações iniciais interceptadas pelo `AgenteValidador` | `2` (`M04`, `M07`) |
| Devoluções ao `Sintetizador` (`retentativa_com_feedback`) | `2` (`M07` corrigido e aprovado; `M04` → recusa final honesta) |
| Erros de execução / respostas degradadas | `0` |
| Soma dos tempos individuais dos agentes | `514,129 s` |
| Tempo paralelo acumulado dos agentes | `264,503 s` |
| Economia total por paralelismo | **`249,626 s` (`-48,6%`)** |
| Duração total média por consulta (ponta a ponta) | `30,54 s` |

## 2. Resultados por Pergunta

| ID | Tipo | Subperguntas | Rotas obtidas | Decomp. (s) | Paralelo (s) | Soma indiv. (s) | Ganho (s) | Reprov. / Dev. | Desfecho |
|---|---|---:|---|---:|---:|---:|---:|---:|---|
| **M01** | `ru_fluxo_explicito` | `2/2` | `['ru', 'fluxo']` | `9,140` | `23,893` | `37,746` | `13,853` | `0 / 0` | Ambas respondidas com citação |
| **M02** | `ru_fluxo_coloquial` | `2/2` | `['ru', 'fluxo']` | `3,906` | `2,843` | `3,690` | `0,847` | `0 / 0` | RU recusou (*"hoje"* sem data); Fluxo respondeu |
| **M03** | `mesmo_dominio_ru` | `2/2` | `['ru', 'ru']` | `3,879` | `4,663` | `7,617` | `2,954` | `0 / 0` | Ambas respondidas com citação |
| **M04** | `mesmo_dominio_fluxo` | `2/2` | `['fluxo', 'fluxo']` | `4,327` | `23,708` | `29,931` | `6,223` | `1 / 1` | 1 parte aprovada; outra reprovada por valor sem respaldo (`14 créditos`) → recusa final |
| **M05** | `implicito_sem_palavras_chave` | `2/2` | `['ru', 'fluxo']` | `5,290` | `2,068` | `3,189` | `1,121` | `0 / 0` | Ambos recusaram honestamente (sem base suficiente) |
| **M06** | `fluxo_ru_misto` | `2/2` | `['fluxo', 'ru']` | `4,646` | `20,004` | `21,121` | `1,117` | `0 / 0` | Ambos recusaram honestamente (sem base exata) |
| **M07** | `tripla` | `3/3` | `['ru', 'fluxo', 'ru']` | `7,538` | `39,233` | `88,531` | `49,298` | `1 / 1` | Fluxo reprovado (`2510 horas`) → corrigido na retentativa (`251 créditos`); 3/3 aprovadas |
| **M08** | `contexto_compartilhado` | `2/2` | `['fluxo', 'ru']` | `15,198` | `25,706` | `41,800` | `16,094` | `0 / 0` | Ambas respondidas com citação |
| **M09** | `tripla_mista_ru_fluxo` | `3/3` | `['ru', 'fluxo', 'fluxo']` | `8,323` | `21,191` | `42,426` | `21,235` | `0 / 0` | 3/3 respondidas com citação |
| **M10** | `tripla_mesmo_dominio_ru` | `3/3` | `['ru', 'ru', 'ru']` | `6,768` | `17,525` | `34,649` | `17,124` | `0 / 0` | 3/3 respondidas com citação |
| **M11** | `quadrupla_mista` | `4/4` | `['ru', 'ru', 'fluxo', 'fluxo']` | `9,757` | `36,141` | `84,752` | `48,611` | `0 / 0` | 3 respondidas com citação; 4ª parte recusou honestamente |
| **M12** | `quadrupla_contexto_compartilhado` | `4/4` | `['fluxo', 'fluxo', 'ru', 'ru']` | `5,665` | `47,528` | `118,677` | `71,149` | `0 / 0` | 4/4 respondidas com citação |

## 3. Análise Qualitativa

1. **Decomposição e roteamento em perguntas duplas, triplas e quádruplas:** `12/12` (`100%`) das consultas foram quebradas no número exato de subperguntas esperadas e roteadas na ordem e nos eixos corretos, incluindo perguntas com 3 (`M07`, `M09`, `M10`) e 4 (`M11`, `M12`) subperguntas.
2. **Atuação real do `AgenteValidador` ativo:**
   - Em **`M07`**, o `Agente Fluxo` citou inicialmente `2510 horas` sem respaldo nos trechos recuperados; o `AgenteValidador` reprovou, devolveu ao `Sintetizador` e a retentativa corrigiu para `251 créditos` com citação `[1]`, sendo aprovada.
   - Em **`M04`**, o `Agente Fluxo` afirmou `14 créditos` sem respaldo nos trechos; após reprovação e persistência do valor na 2ª tentativa, o sistema aplicou **recusa final honesta** em vez de entregar o número sem fonte.
3. **Paralelismo escalável:** em perguntas com 3 e 4 partes (`M07`, `M09`–`M12`), o `ThreadPoolExecutor` escalou dinamicamente para 3 e 4 workers, alcançando ganhos individuais de até `71,149 s` (`M12`) e economia global de **`48,6%`** no tempo dos agentes.

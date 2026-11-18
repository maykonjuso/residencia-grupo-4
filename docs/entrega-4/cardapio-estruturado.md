# Cardápio estruturado por compartimento

O cardápio do RU chega como texto para leitura. O monta-prato (#58, #63) precisa de dados:
quais compartimentos a bandeja tem, quantas escolhas cabem em cada um e quais opções existem
em cada trilha alimentar. Esta página documenta o JSON que liga uma coisa à outra (issue #54,
RF01) e as decisões tomadas ao interpretar o PDF.

## Como gerar

```bash
cd rag
python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09 --refeicao almoco
python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09            # as três refeições do dia
python -m rumo_rag.coleta cardapio --data 2026-11-09 --refeicao almoco        # texto do chunk, para conferir
```

Avisos de cardápio malformado saem em `stderr` e também no campo `avisos` do JSON. Data sem
cardápio na base devolve código 1 e a recusa padrão ("Não encontrei… nas fontes da base").

## De onde vem

O parser não relê o PDF: lê os chunks de cardápio de `rag/dados/chunks.jsonl`, onde cada chunk
já é uma refeição de um dia (`extracao._ler_cardapio` + `chunking.dividir`). Assim o JSON bate
item a item com o texto que o RAG cita, e a procedência (`doc_id`, `pagina`, `chunk_id`) é a
mesma que aparece nas respostas. Quando o scraper do cardápio (#50) entrar, ele alimenta a
mesma ingestão e o JSON acompanha sem mudança.

## Esquema

Validado por `rag/rumo_rag/coleta/schema_cardapio.json` (JSON Schema 2020-12).

```json
{
  "unidade": "gama",
  "data": "2026-11-09",
  "refeicao": "almoco",
  "compartimentos": [
    {"slot": "salada", "titulo": "Salada", "max": 2,
     "opcoes": [{"id": "alface-roxa", "nome": "Alface roxa", "trilha": "todas",
                 "fonte": {"doc_id": "F09", "pagina": 2, "chunk_id": "F09-0005"}}]}
  ],
  "mesa_apoio": ["água", "farinha", "molho de pimenta", "vinagre", "azeite", "sal"],
  "fonte": {"doc_id": "F09", "pagina": 2, "chunk_id": "F09-0005", "url": "https://ru.unb.br/..."},
  "avisos": []
}
```

| Campo | Valores |
|---|---|
| `refeicao` | `cafe`, `almoco`, `jantar` |
| `trilha` | `todas`, `padrao`, `ovolacto` (ovolactovegetariano), `vegano` (vegetariano estrito) |
| `fonte` em cada opção | obrigatória: a interface mostra o prato, mas a citação continua (RF03) |

## Compartimentos

| Rótulo no PDF | `slot` | `max` | Refeição |
|---|---|:---:|---|
| Salada 1, Salada 2 | `salada` | 2 | almoço, jantar |
| Molho para salada | `molho` | 1 | almoço, jantar |
| Prato principal padrão / ovolacto / vegetariano estrito | `principal` | 1 | almoço, jantar |
| Guarnição | `guarnicao` | 1 | almoço |
| Sopa · Torrada | `sopa` · `torrada` | 1 | jantar |
| Acompanhamentos | `arroz` (max 2) + `feijao` (max 1) | — | almoço, jantar |
| Sobremesa | `sobremesa` | 1 | almoço, jantar |
| Bebida (refresco de) · Bebidas | `bebida` | 1 | todas |
| Panificação · Opção extra · Gordura · Fruta | `panificacao` · `extra` · `gordura` · `fruta` | 1 | café |
| Complemento padrão / ovolacto / vegetariano estrito | `complemento` | 1 | café |

Rótulo que não está na tabela vira um compartimento genérico (`max` 1) com aviso, para que
uma semana com componente novo não derrube a interface.

## Decisões de interpretação

1. **"OU", "ou", "/" e "OPÇÃO:" separam alternativas.** "Leite integral OU Bebida de soja" são
   2 opções; "Mix de doces OPÇÃO: Frutas" também; "Manjericão / Limão" são 2 molhos.
2. **"e" não separa.** "Alho e limão" e "Manteiga ou creme vegetal" mostram por quê: o "e"
   costuma compor um único item, o "ou" é que marca a escolha.
3. **"Arroz branco e integral Feijão carioca" vira dois compartimentos.** A célula do PDF
   mescla arroz e feijão. Separamos em `arroz` com duas opções (Arroz branco, Arroz integral;
   `max` 2, porque o RU serve os dois) e `feijao`. Se o texto não seguir o padrão
   "Arroz … Feijão …", o item fica inteiro em `acompanhamentos`, com aviso.
4. **Trilhas são opções do mesmo compartimento.** As três versões do prato principal (e do
   complemento do café) ficam em `principal`/`complemento` com `max` 1, diferenciadas por
   `trilha`. A interface filtra pela trilha escolhida.
5. **Malformado gera aviso, nunca exceção.** "Pão francês ou Pão careca ou" (com "ou" solto,
   caso real do F09 em 09/11 e 12/11) vira duas opções e um aviso. Célula vazia remove o
   compartimento com aviso.
6. **"Opção extra" fica em compartimento próprio.** No F09 ela aparece justo nos dias em que a
   panificação termina em "ou" solto, o que sugere que é a terceira alternativa do pão. Como o
   PDF não diz isso, não juntamos: a interface decide como exibir.

## Verificação

`rag/testes/test_cardapio_estruturado.py` cobre os critérios de aceite da issue:

- o comando devolve JSON válido no schema, para todas as 15 refeições do F09
- cada opção aparece no texto do chunk correspondente, e nenhuma linha do chunk fica de fora
- cardápio malformado gera aviso, não exceção
- toda opção tem `doc_id` e `pagina`

```bash
cd rag && python -m unittest testes.test_cardapio_estruturado -v
```

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 18/11/2026 | 1.0 | Esquema do cardápio por compartimento, decisões de parsing e verificação (#54) | Kyara Esteves |

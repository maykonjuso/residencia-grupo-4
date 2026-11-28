from unittest.mock import patch

from rumo_rag import __main__ as cli
from rumo_rag.agentes.agente_fluxo import AgenteFluxo
from rumo_rag.agentes.mensagem import Mensagem
from rumo_rag.grafo_curricular import GrafoCurricular


def carregar_grafo():
    return GrafoCurricular.carregar_f16()


def test_extrai_nos_e_relacoes_da_transcricao_f16():
    grafo = carregar_grafo()

    assert grafo.disciplinas["FGA0313"].nome == "Requisitos de Software"
    assert grafo.disciplinas["FGA0313"].semestre == 5
    assert grafo.disciplinas["FGA0313"].creditos == 4
    assert any(
        aresta.origem == "FGA0312"
        and aresta.destino == "FGA0314"
        and not aresta.incerta
        and aresta.alternativas == ("FGA0313",)
        for aresta in grafo.arestas
    )
    assert grafo.grafo.has_edge("FGA0312", "FGA0314")
    assert grafo.grafo.has_edge("FGA0314", "FGA0317")
    assert any(aresta.relacao == "correquisito" for aresta in grafo.arestas)


def test_reprovar_em_requisitos_nao_bloqueia_testes_por_conta_do_ou_e_mds_bloqueia_cadeia():
    consulta_req = carregar_grafo().consultar(
        "Se eu reprovar em Requisitos de Software, quais disciplinas travam?"
    )

    assert consulta_req is not None
    assert "não encontrei dependentes alcançáveis por bloqueio direto" in consulta_req.conteudo.lower()
    assert "aceita pré-requisito alternativo" in consulta_req.conteudo.lower()
    assert "FGA0312" in consulta_req.conteudo
    assert "FGA0314" in consulta_req.conteudo
    assert "[1]" in consulta_req.conteudo

    # Consulta curta usando apelido dinâmico ("Requisitos") sem escrever "Requisitos de Software"
    consulta_curta = carregar_grafo().consultar(
        "Se eu reprovar em Requisitos, o que trava?"
    )
    assert consulta_curta is not None
    assert "FGA0313" in consulta_curta.conteudo

    # Reprovar em MDS (FGA0312) trava Requisitos (FGA0313), ambas as opções do OU de Testes (FGA0314), e GCES (FGA0317)
    consulta_mds = carregar_grafo().consultar(
        "Se eu reprovar em MDS, o que trava?"
    )
    assert consulta_mds is not None
    assert "Requisitos de Software (FGA0313)" in consulta_mds.conteudo
    assert "Testes de Software (FGA0314)" in consulta_mds.conteudo
    assert "Gerência de Configuração e Evolução de Software (GCES) (FGA0317)" in consulta_mds.conteudo


def test_gargalo_e_calculado_pelo_grau_de_saida_do_grafo():
    consulta = carregar_grafo().consultar(
        "Qual disciplina de Engenharia de Software destrava mais matérias?"
    )

    assert consulta is not None
    assert "CIC0004" in consulta.conteudo
    assert "FGA0312" in consulta.conteudo
    assert "FGA0158" in consulta.conteudo
    assert "FGA0146" in consulta.conteudo
    assert "FGA0313" in consulta.conteudo
    assert "FGA0314" in consulta.conteudo
    assert "setas cheias" in consulta.conteudo


def test_prerequisito_alternativo_ou_de_testes_de_software():
    grafo = carregar_grafo()
    confirmados, incertos = grafo.prerequisitos("FGA0314")
    assert incertos == []
    assert len(confirmados) == 1
    assert confirmados[0].origem == "FGA0312"
    assert confirmados[0].alternativas == ("FGA0313",)

    consulta = grafo.consultar("Quais os pré-requisitos de Testes de Software?")
    assert consulta is not None
    assert "Métodos de Desenvolvimento de Software (MDS) (FGA0312) ou Requisitos de Software (FGA0313)" in consulta.conteudo


def test_passar_em_requisitos_ou_mds_abre_testes_de_software():
    consulta_req = carregar_grafo().consultar("Passando em Requisitos de Software, o que abre?")
    assert consulta_req is not None
    assert "ficam liberadas pelo grafo: Testes de Software (FGA0314)" in consulta_req.conteudo

    consulta_mds = carregar_grafo().consultar("Passando em MDS, o que abre?")
    assert consulta_mds is not None
    assert "Requisitos de Software (FGA0313)" in consulta_mds.conteudo
    assert "Testes de Software (FGA0314)" in consulta_mds.conteudo


def test_aresta_tracejada_permanece_incerta_e_pede_confirmacao_sigaa():
    md_tracejada = """# Fluxograma — Teste
## 1º semestre de Engenharia de Software (8 créditos)
- FGA0312 Métodos de Desenvolvimento de Software (MDS) — 1-1-2-4
- FGA0313 Requisitos de Software — 1-1-2-4
## Pré-requisitos
- Para cursar Requisitos de Software (FGA0313), é preciso ter cursado antes: Métodos de Desenvolvimento de Software (MDS) (FGA0312) (seta tracejada).
"""
    grafo = GrafoCurricular.de_markdown(md_tracejada)
    confirmados, incertos = grafo.prerequisitos("FGA0313")
    assert confirmados == []
    assert len(incertos) == 1 and incertos[0].origem == "FGA0312"

    consulta = grafo.consultar("Quais os pré-requisitos de Requisitos de Software?")
    assert consulta is not None
    assert "ligação tracejada" in consulta.conteudo
    assert "confirme no SIGAA" in consulta.conteudo

    abrem = grafo.consultar("Passei em FGA0312; o que abre?")
    assert abrem is not None
    assert "ligação é tracejada" in abrem.conteudo
    assert "confirme no SIGAA" in abrem.conteudo


def test_passar_em_tres_disciplinas_calcula_o_conjunto_que_abre():
    consulta = carregar_grafo().consultar(
        "Passei em MAT0025, CIC0004 e FGA0168; o que abre?"
    )

    assert consulta is not None
    assert "Cálculo 2 (MAT0026)" in consulta.conteudo
    assert "Orientação a Objetos (FGA0158)" in consulta.conteudo
    assert "Estruturas de Dados 1 (FGA0146)" in consulta.conteudo


def test_passar_com_nome_parcial_ambiguo_lista_opcoes_sem_omitir_item():
    res = carregar_grafo().consultar_estruturado(
        "Passando em Cálculo 1, Algoritmos e Introdução à Engenharia, o que abre?"
    )

    assert res is not None
    assert "Cálculo 2 (MAT0026)" in res["texto"]
    assert "não reconheci com segurança: algoritmos" in res["texto"].lower()
    assert "CIC0004" in res["texto"]
    assert "FGA0124" in res["texto"]
    assert "FGA0163" in res["dados"]["aprovadas"]


def test_lista_de_aprovadas_avisa_disciplina_nao_reconhecida():
    res = carregar_grafo().consultar_estruturado(
        "Passei em Cálculo 1, Disciplina Inventada, o que abre?"
    )

    assert res is not None
    assert "Cálculo 2 (MAT0026)" in res["texto"]
    assert "Não reconheci: Disciplina Inventada." in res["texto"]
    assert res["dados"]["disciplinas_nao_reconhecidas"] == ["Disciplina Inventada"]


def test_nome_parcial_unico_e_resolvido_na_lista_de_aprovadas():
    res = carregar_grafo().consultar_estruturado("Passei em Compiladores; o que abre?")

    assert res is not None
    assert "FGA0003" in res["dados"]["aprovadas"]
    assert res["dados"]["disciplinas_nao_reconhecidas"] == []
    assert res["dados"]["disciplinas_ambiguas"] == {}


def test_mask_first_preserva_nomes_com_e_remove_ruido_conversacional():
    grafo = carregar_grafo()

    # Nome oficial contendo " e " não deve ser quebrado em "Algoritmos" + "Programação de Computadores"
    res_nome_com_e = grafo.consultar_estruturado(
        "Passei em Cálculo 1 e Algoritmos e Programação de Computadores, o que abre?"
    )
    assert res_nome_com_e is not None
    assert set(res_nome_com_e["dados"]["aprovadas"]) == {"MAT0025", "CIC0004"}
    assert res_nome_com_e["dados"]["disciplinas_nao_reconhecidas"] == []
    assert res_nome_com_e["dados"]["disciplinas_ambiguas"] == {}

    # Cauda conversacional após a lista não deve virar disciplina não reconhecida
    res_cauda = grafo.consultar_estruturado(
        "Fui aprovado em Cálculo 1 e quero saber quais disciplinas posso pegar no próximo semestre"
    )
    assert res_cauda is not None
    assert res_cauda["dados"]["aprovadas"] == ["MAT0025"]
    assert res_cauda["dados"]["disciplinas_nao_reconhecidas"] == []

    # Preposição repetida e padrão "O que abre com ..."
    res_prep = grafo.consultar_estruturado(
        "Passei em Cálculo 1 e em Disciplina Inventada, o que abre?"
    )
    assert res_prep is not None
    assert res_prep["dados"]["disciplinas_nao_reconhecidas"] == ["Disciplina Inventada"]

    res_abre_com = grafo.consultar_estruturado(
        "O que abre com Cálculo 1 e Disciplina Inventada?"
    )
    assert res_abre_com is not None
    assert res_abre_com["dados"]["aprovadas"] == ["MAT0025"]
    assert res_abre_com["dados"]["disciplinas_nao_reconhecidas"] == ["Disciplina Inventada"]

    # Zero disciplinas reconhecidas produz resposta limpa e evidência respaldada
    res_zero = grafo.consultar_estruturado("Passei em Magia Negra, o que abre?")
    assert res_zero is not None
    assert res_zero["dados"]["aprovadas"] == []
    assert res_zero["dados"]["disciplinas_nao_reconhecidas"] == ["Magia Negra"]
    assert "Não identifiquei disciplinas confirmadas" in res_zero["texto"]
    assert "Magia Negra" in res_zero["evidencia"]


def test_contexto_de_curso_na_lista_nao_vira_disciplina_ambigua():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    res = carregar_repositorio_grafos().consultar_estruturado(
        "Passei em Cálculo 1 e Física 1 em Eletrônica, o que abre?"
    )
    assert res is not None
    assert res["dados"]["curriculo_id"] == "eletronica-2023"
    assert set(res["dados"]["aprovadas"]) == {"MAT0025", "IFD0171"}
    assert res["dados"]["disciplinas_nao_reconhecidas"] == []
    assert res["dados"]["disciplinas_ambiguas"] == {}


def test_interface_estruturada_aprovadas_para_tool_calling():
    from rumo_rag.agentes.ferramentas import grafo_fluxo

    res = grafo_fluxo("O que abre?", aprovadas=["MAT0025", "Algoritmos", "FGA9999"])
    assert res.sucesso is True
    assert res.dados["aprovadas"] == ["MAT0025"]
    assert res.dados["disciplinas_nao_reconhecidas"] == ["FGA9999"]
    assert "Algoritmos" in res.dados["disciplinas_ambiguas"]
    assert "CIC0004" in res.trechos_evidencia[0]["texto"]
    assert "FGA0124" in res.trechos_evidencia[0]["texto"]
    assert "FGA9999" in res.trechos_evidencia[0]["texto"]


def test_orquestrador_aprova_avisos_de_ambiguidade_e_codigo_desconhecido():
    from rumo_rag.agentes.orquestrador import Orquestrador

    orq = Orquestrador()

    for pergunta, esperado in [
        (
            "Passando em Cálculo 1, Algoritmos e Introdução à Engenharia, o que abre?",
            "Não reconheci com segurança: Algoritmos",
        ),
        (
            "Passei em MAT0025 e FGA9999, o que abre?",
            "Não reconheci: FGA9999.",
        ),
        (
            "Passei em Magia Negra, o que abre?",
            "Não reconheci: Magia Negra.",
        ),
    ]:
        out = orq.executar(pergunta, backend="extrativo")
        etapas_val = [e for e in out.get("trace", []) if e.get("etapa") == "validacao_factual"]
        assert etapas_val, f"Esperava etapa validacao_factual para: {pergunta}"
        resultados = etapas_val[0]["resultados"]
        assert resultados and all(r.get("aprovado_inicial") is True and r.get("aprovado") is True for r in resultados), resultados
        assert etapas_val[0]["devolucoes_ao_sintetizador"] == []
        assert out.get("valores_sem_fonte") == []
        assert esperado in out["resposta"]


def test_siglas_derivadas_dinamicamente_e_ausencia_de_falsos_positivos():
    grafo = carregar_grafo()

    # Siglas derivadas dinamicamente das disciplinas existentes em F16
    assert [d.codigo for d in grafo.buscar_disciplinas("Quais os pré-requisitos de MDS?")] == ["FGA0312"]
    assert [d.codigo for d in grafo.buscar_disciplinas("Se eu reprovar em FSO, o que trava?")] == ["FGA0170"]
    assert [d.codigo for d in grafo.buscar_disciplinas("Quais os pré-requisitos de SBD1?")] == ["FGA0137"]
    assert [d.codigo for d in grafo.buscar_disciplinas("Se eu reprovar em GCES, o que trava?")] == ["FGA0317"]
    assert [d.codigo for d in grafo.buscar_disciplinas("Se eu reprovar em OO, o que trava?")] == ["FGA0158"]
    cods_misto = {
        d.codigo
        for d in grafo.buscar_disciplinas("Passando em Cálculo 1, APC e FAC, o que abre?")
    }
    assert cods_misto == {"MAT0025", "CIC0004", "FGA0142"}

    # Não deve confundir "pré-requisitos" com "Requisitos" nem aceitar 2 letras minúsculas ("oo")
    assert [d.codigo for d in grafo.buscar_disciplinas("Quais os pré-requisitos de Cálculo 2?")] == ["MAT0026"]
    assert grafo.buscar_disciplinas("Se eu reprovar em oo minúsculo ou pré-requisitos?") == []
    assert grafo.buscar_disciplinas("Qual o desenvolvimento do curso e quais testes existem?") == []


def test_caminho_critico_e_a_cadeia_mais_longa_de_setas_cheias():
    consulta = carregar_grafo().consultar("Qual é o caminho crítico de pré-requisitos?")

    assert consulta is not None
    assert "CIC0004" in consulta.conteudo
    assert "FGA0317" in consulta.conteudo
    assert "não uma previsão de semestres até a formatura" in consulta.conteudo


def test_agente_fluxo_responde_consulta_do_grafo_sem_chamar_llm_ou_indice():
    msg_det = Mensagem(
        remetente="Orquestrador",
        destinatario="Agente Fluxo",
        conteudo="Se eu reprovar em MDS, quais disciplinas travam?",
        contexto={"backend": "extrativo"},
    )

    with patch("rumo_rag.geracao.gerar_com_instrucoes") as gerar, patch(
        "rumo_rag.agentes.agente_fluxo.indice.buscar"
    ) as buscar:
        resp_det = AgenteFluxo().executar(msg_det)

    gerar.assert_not_called()
    buscar.assert_not_called()
    assert "FGA0313" in resp_det.conteudo
    assert "FGA0314" in resp_det.conteudo
    assert "FGA0317" in resp_det.conteudo
    assert resp_det.fontes[0]["doc_id"] == "F16"
    assert msg_det.contexto["trechos_recuperados"][0]["doc_id"] == "F16"
    assert msg_det.contexto["tempo_geracao_s"] == 0.0
    assert msg_det.contexto["ferramenta_chamada"]["redigido_por_llm"] is False

    msg_llm = Mensagem(
        remetente="Orquestrador",
        destinatario="Agente Fluxo",
        conteudo="Se eu reprovar em MDS, quais disciplinas travam?",
        contexto={"backend": "ollama"},
    )
    with patch(
        "rumo_rag.geracao.gerar_com_instrucoes",
        return_value="Reprovando em MDS (FGA0312), travam FGA0313, FGA0314 e FGA0317. [1]",
    ) as gerar_llm, patch("rumo_rag.agentes.agente_fluxo.indice.buscar") as buscar_llm:
        resp_llm = AgenteFluxo().executar(msg_llm)

    gerar_llm.assert_called_once()
    buscar_llm.assert_not_called()
    assert "FGA0314" in resp_llm.conteudo
    assert "FGA0317" in resp_llm.conteudo
    assert msg_llm.contexto["ferramenta_chamada"]["redigido_por_llm"] is True


def test_cli_padrao_encaminha_perguntas_de_impacto_ao_grafo():
    with patch("rumo_rag.__main__.indice.decompor", side_effect=AssertionError), patch(
        "rumo_rag.__main__.indice.buscar_com_subperguntas", side_effect=AssertionError
    ), patch("rumo_rag.__main__.geracao.gerar", side_effect=AssertionError), patch(
        "rumo_rag.geracao.gerar_com_instrucoes",
        return_value=(
            "Por pré-requisito alternativo (OU) em FGA0314, reprovar apenas em Requisitos "
            "não bloqueia Testes de Software se MDS já tiver sido cursada. [1]"
        ),
    ):
        resultado = cli.responder(
            "Se eu reprovar em Requisitos de Software, quais disciplinas travam?",
            backend="ollama",
        )

    assert resultado["backend"] == "grafo"
    assert resultado["redigido_por_llm"] is True
    assert resultado["valores_sem_fonte"] == []
    assert resultado["sem_citacao"] is False
    assert "FGA0314" in resultado["resposta"]
    assert resultado["fontes_citadas"][0]["doc_id"] == "F16"


def test_grafo_usa_networkx_digraph_e_valida_schema_json():
    import json
    import networkx as nx
    import pytest
    from rumo_rag.grafo_curricular import Aresta, GRAFO_JSON

    assert GRAFO_JSON.exists()
    dados = json.loads(GRAFO_JSON.read_text(encoding="utf-8"))
    GrafoCurricular.validar_json(dados)

    grafo = GrafoCurricular.carregar_json(GRAFO_JSON)
    assert isinstance(grafo.grafo, nx.DiGraph)
    assert nx.is_directed_acyclic_graph(grafo.grafo)
    assert grafo.grafo.number_of_nodes() == 47
    assert grafo.caminho_critico() == list(nx.dag_longest_path(grafo.grafo))
    assert len(grafo.caminho_critico()) == 5
    assert set(grafo.caminho_critico()) == {"CIC0004", "FGA0158", "FGA0312", "FGA0314", "FGA0317"}

    estruturado = grafo.consultar_estruturado("Qual disciplina destrava mais matérias?")
    assert estruturado is not None
    assert estruturado["tipo_consulta"] == "gargalo"
    assert estruturado["dados"]["gargalos"][0]["codigo"] == "CIC0004"

    # Detecção de ciclo no DiGraph
    with pytest.raises(ValueError, match="ciclo"):
        GrafoCurricular(
            disciplinas={
                "CIC0004": grafo.disciplinas["CIC0004"],
                "FGA0158": grafo.disciplinas["FGA0158"],
            },
            arestas=[
                Aresta("CIC0004", "FGA0158", "pre_requisito", False, "teste"),
                Aresta("FGA0158", "CIC0004", "pre_requisito", False, "teste"),
            ],
        )


def test_repositorio_cobre_todos_os_5_cursos_fcte_com_dags_validos():
    import networkx as nx
    from rumo_rag.grafo_curricular import GRAFO_JSON, RepositorioGrafos

    repo = RepositorioGrafos.carregar_json(GRAFO_JSON)
    resumos = repo.listar_curriculos()
    cursos_slug = {r["curso_slug"] for r in resumos}
    ids = {r["curriculo_id"] for r in resumos}

    assert cursos_slug == {"software", "aeroespacial", "eletronica", "automotiva", "energia"}
    assert {
        "software-2024-2",
        "aeroespacial-2025",
        "eletronica-2023",
        "automotiva-2018-2026",
        "automotiva-2027",
        "energia-2024",
    } <= ids

    for cid, grafo in repo.curriculos.items():
        assert nx.is_directed_acyclic_graph(grafo.grafo), cid
        assert grafo.vigencia["inicio"]
        assert grafo.vigencia["descricao"]


def test_aeroespacial_e_eletronica_respondem_prerequisitos_corequisitos_e_gargalos():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()

    res_aero = repo.consultar_estruturado("Quais os pré-requisitos de Mecânica do Voo em Aeroespacial?")
    assert res_aero is not None
    assert res_aero["dados"]["curriculo_id"] == "aeroespacial-2025"
    cods_aero = {c["codigo"] for c in res_aero["dados"]["confirmados"]}
    assert cods_aero == {"FGA0008", "FGA0038"}
    assert res_aero["fonte"]["doc_id"] == "F17"
    assert "PPC 2025" in res_aero["texto"]

    res_el = repo.consultar_estruturado(
        "Quais os pré-requisitos e correquisitos de Teoria de Eletrônica Digital 1 em Eletrônica?"
    )
    assert res_el is not None
    assert res_el["dados"]["curriculo_id"] == "eletronica-2023"
    assert res_el["dados"]["confirmados"][0]["codigo"] == "MAT0031"
    assert res_el["dados"]["correquisitos"][0]["codigo"] == "FGA0071"
    assert res_el["fonte"]["doc_id"] == "F21"
    assert "PPC 2023" in res_el["texto"]


def test_automotiva_coexiste_com_duas_vigencias_e_recusa_prerequisitos_sem_inventar():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()

    res_2027 = repo.consultar_estruturado(
        "Quais os pré-requisitos de Dinâmica de Veículos em Automotiva 2027?"
    )
    assert res_2027 is not None
    assert res_2027["tipo_consulta"] == "prerequisitos_indisponiveis"
    assert res_2027["dados"]["curriculo_id"] == "automotiva-2027"
    assert res_2027["dados"]["cobertura_prerequisitos"] == "indisponivel_na_base"
    assert any(o["curriculo_id"] == "automotiva-2018-2026" for o in res_2027["dados"]["outras_vigencias"])
    assert res_2027["fonte"]["doc_id"] == "F19"

    res_2018 = repo.consultar_estruturado(
        "Disciplinas do 3º nível de Engenharia Automotiva para ingressantes de 2020"
    )
    assert res_2018 is not None
    assert res_2018["tipo_consulta"] == "vigencia_curriculo"
    assert res_2018["dados"]["curriculo_id"] == "automotiva-2018-2026"
    assert any("Ergonomia" in d["nome"] or "Ondulatória" in d["nome"] for d in res_2018["dados"]["disciplinas"])
    assert all(not d["codigo_oficial"] for d in res_2018["dados"]["disciplinas"])


def test_energia_responde_grade_e_nao_inventa_prerequisitos():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()
    res_pre = repo.consultar_estruturado("Quais os pré-requisitos de Biorrefinarias em Engenharia de Energia?")
    assert res_pre is not None
    assert res_pre["tipo_consulta"] == "prerequisitos_indisponiveis"
    assert res_pre["dados"]["curriculo_id"] == "energia-2024"
    assert res_pre["fonte"]["doc_id"] == "F23"


def test_equivalencias_e_resolucao_por_codigo_antigo():
    from rumo_rag.grafo_curricular import carregar_repositorio_grafos

    repo = carregar_repositorio_grafos()

    res_eq_sw = repo.consultar_estruturado("Qual a equivalência de FGA0172?")
    assert res_eq_sw is not None
    assert res_eq_sw["tipo_consulta"] == "equivalencias"
    assert res_eq_sw["dados"]["curriculo_id"] == "software-2024-2"
    assert res_eq_sw["dados"]["equivalencias"][0]["codigo"] == "FGA0313"
    assert "FGA0172" in res_eq_sw["dados"]["equivalencias"][0]["equivalentes"]

    res_eq_el = repo.consultar_estruturado("Qual a equivalência de FGA0308 em Engenharia Eletrônica?")
    assert res_eq_el is not None
    assert res_eq_el["dados"]["curriculo_id"] == "eletronica-2023"
    assert res_eq_el["dados"]["equivalencias"][0]["equivalentes"] == ["FGA0096"]
    assert res_eq_el["fonte"]["doc_id"] == "F21"

    # Perguntar pré-requisitos usando código antigo (FGA0238 -> FGA0314 Testes de Software)
    res_antigo = repo.consultar_estruturado("Quais os pré-requisitos de FGA0238?")
    assert res_antigo is not None
    assert res_antigo["tipo_consulta"] == "prerequisitos"
    assert res_antigo["dados"]["disciplina"]["codigo"] == "FGA0314"
    assert "FGA0238" in res_antigo["texto"]

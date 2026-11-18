"""Gera o PDF de exemplo dos testes do scraper (#50), imitando o layout real do RU Gama:
uma página por refeição, tabela COMPOSIÇÃO × dias, datas sem zero à esquerda ("31/8/2026",
"1º/9/2026") como nos PDFs publicados a partir de ago/2026.

Só é preciso rodar de novo se o layout mudar:  python testes/fixtures/cardapio_gama/gerar_fixture.py
(precisa de reportlab, que não é dependência do projeto)
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

DIAS = ["2ª FEIRA", "3ª FEIRA", "4ª FEIRA", "5ª FEIRA", "6ª FEIRA"]
DATAS = ["31/8/2026", "1º/9/2026", "2/9/2026", "3/9/2026", "4/9/2026"]

REFEICOES = {
    "Café da manhã": ([
        ["BEBIDAS", "Leite integral OU Bebida de soja", "", "", "", ""],
        ["PANIFICAÇÃO", "Pão francês ou Pão careca ou", "Pão francês ou Pão integral", "Pão francês",
         "Pão francês ou Pão careca ou", "Pão integral"],
        ["FRUTA", "Maçã", "Banana", "Melancia", "Mamão", "Salada de frutas"],
    ], "Mesa de apoio: água, achocolatado, açúcar e adoçante. Cardápio sujeito a alteração."),
    "Almoço": ([
        ["SALADA 1", "Alface crespa", "Acelga", "Mix de folhas", "Alface roxa", "Repolho branco"],
        ["PRATO PRINCIPAL PADRÃO", "Frango a pizzaiolo", "Carne de sol", "Peixe ao molho",
         "Lasanha de frango", "Strogonoff de carne"],
        ["PRATO PRINCIPAL VEGETARIANO ESTRITO", "Soja refogada", "Grão de bico", "Lentilha ao sugo",
         "Yakissoba", "Moqueca de vegetais"],
        ["ACOMPANHAMENTOS", "Arroz branco e integral Feijão carioca", "", "", "", ""],
        ["SOBREMESA", "Laranja", "Mix de doces OPÇÃO: Frutas", "Banana", "Maçã", "Melancia"],
    ], "Mesa de apoio: água, farinha, molho de pimenta, vinagre, azeite e sal. Cardápio sujeito a alteração."),
    "Jantar": ([
        ["SALADA 1", "Chicória", "Repolho roxo", "Alface lisa", "Tabule", "Cenoura ralada"],
        ["SOPA", "Caldo verde", "Creme de abóbora", "Canjiquinha", "Creme de cebola", "Sopa de legumes"],
        ["ACOMPANHAMENTOS", "Arroz branco e integral Feijão preto", "", "", "", ""],
    ], "Mesa de apoio: água, farinha, molho de pimenta, vinagre, azeite e sal. Cardápio sujeito a alteração."),
}


def gerar(destino: Path) -> None:
    estilos = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(destino), pagesize=landscape(A4))
    historia = []
    for i, (refeicao, (linhas, rodape)) in enumerate(REFEICOES.items()):
        historia.append(Paragraph("CARDÁPIO SEMANAL", estilos["Title"]))
        historia.append(Paragraph(refeicao, estilos["Heading2"]))
        dados = [["COMPOSIÇÃO"] + DIAS, [""] + DATAS] + linhas
        t = Table(dados)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                               ("FONTSIZE", (0, 0), (-1, -1), 7)]))
        historia.append(t)
        historia.append(Paragraph(rodape, estilos["Normal"]))
        if i < len(REFEICOES) - 1:
            historia.append(PageBreak())
    doc.build(historia)


if __name__ == "__main__":
    gerar(Path(__file__).with_name("Gama-Semana-02-31-8-a-6-9.pdf"))

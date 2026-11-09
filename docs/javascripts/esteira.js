/* Esteira animada do RAG (página visao/esteira-rag.md). Sem dependências externas.
   Ingestão (offline): fontes → extração → chunking → embeddings → banco vetorial.
   Pergunta (online): pergunta → vetor → busca híbrida → RRF → prompt → LLM → resposta.
   Os exemplos de pergunta usam saídas reais do protótipo (window.RUMO_DEMO, de demo-dados.js). */
(function () {
  "use strict";

  var reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SVGNS = "http://www.w3.org/2000/svg";

  /* ---------- utilidades ---------- */
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function sv(tag, attrs, texto) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (texto !== undefined) e.textContent = texto;
    return e;
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function num(v, casas) { return Number(v).toFixed(casas).replace(".", ","); }
  function milhar(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function rng(semente) {   // mulberry32: mesmos "números" a cada execução
    var a = typeof semente === "string" ? hash(semente) : semente;
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function realcar(t) { return esc(t).replace(/\[(\d+)\]/g, '<b class="rm-est__cit">[$1]</b>').replace(/\n/g, "<br>"); }

  // eixo de cada fonte (rag/catalogo.yaml): F01–F10 e F13 = RU; F11, F12, F35 = apoio; resto = fluxo
  function eixoDe(docId) {
    var n = parseInt(String(docId).slice(1), 10);
    if (n === 11 || n === 12 || n === 35) return "apoio";
    return n <= 13 ? "ru" : "fluxo";
  }
  var NOME_EIXO = { ru: "RU", fluxo: "Fluxo das engenharias", apoio: "Apoio" };

  // mesmo tokenizador do BM25 em rag/rumo_rag/indice.py
  var STOP = {};
  ("a o as os de da do das dos e é em no na nos nas um uma para por com que se ao à às como mais ou qual quais " +
   "quando onde ser sua seu meu minha eu tem há").split(" ").forEach(function (w) { STOP[w] = 1; });
  var TOKEN = /\d{1,2}\/\d{1,2}(?:\/\d{2,4})?|[a-z]{2,4}\d{3,4}|[a-z0-9à-ú]+/g;
  var IDENT = /\d{1,2}\/\d{1,2}|\b[a-z]{2,4}\d{3,4}\b/;

  /* ---------- peças visuais reutilizadas ---------- */
  function barras(semente, cor, n) {
    var r = rng(semente), box = el("div", "rm-est__vetor rm-est__vetor--" + cor), valores = [];
    for (var i = 0; i < n; i++) {
      var v = (r() - 0.5) * 0.24;
      valores.push(v);
      var b = el("span", "rm-est__barra");
      var s = el("i", v < 0 ? "rm-neg" : "");
      s.style.setProperty("--h", Math.round(Math.abs(v) / 0.12 * 100) + "%");
      s.style.transitionDelay = reduzido ? "0s" : (i * 0.03) + "s";
      b.appendChild(s);
      box.appendChild(b);
    }
    var nums = valores.slice(0, 5).map(function (v) { return (v < 0 ? "−" : "") + num(Math.abs(v), 3); }).join("; ");
    return { el: box, legenda: "[" + nums + "; …] · 1.024 números" };
  }

  function rede() {   // mini rede neural que "pulsa" (o modelo de embedding / o LLM)
    var s = sv("svg", { viewBox: "0 0 120 90", class: "rm-est__rede", "aria-hidden": "true" });
    var camadas = [[20, 45, 70], [15, 35, 55, 75], [30, 60]], xs = [18, 60, 102];
    camadas.forEach(function (ys, c) {
      if (c < camadas.length - 1) ys.forEach(function (y) {
        camadas[c + 1].forEach(function (y2) { s.appendChild(sv("line", { x1: xs[c], y1: y, x2: xs[c + 1], y2: y2 })); });
      });
    });
    camadas.forEach(function (ys, c) {
      ys.forEach(function (y, i) {
        var n = sv("circle", { cx: xs[c], cy: y, r: 6 });
        n.style.animationDelay = (c * 0.25 + i * 0.1) + "s";
        s.appendChild(n);
      });
    });
    return s;
  }

  function seta() { return el("div", "rm-est__seta", "<span>→</span>"); }

  function caixaModelo(nome, sub) {
    var c = el("div", "rm-est__modelo");
    c.appendChild(rede());
    c.appendChild(el("b", "", nome));
    if (sub) c.appendChild(el("small", "", sub));
    return c;
  }

  function legendaEixos() {
    return el("div", "rm-est__legenda",
      '<span class="rm-eixo--ru"><i></i>RU</span><span class="rm-eixo--fluxo"><i></i>Fluxo das engenharias</span>' +
      '<span class="rm-eixo--apoio"><i></i>Apoio</span>');
  }

  /* ---------- mapa do banco vetorial (projeção ilustrativa em 2D) ---------- */
  var GRUPOS = [
    { eixo: "ru", x: 150, y: 120, n: 16, esp: 58, rx: 150, ry: 50 },
    { eixo: "fluxo", x: 470, y: 130, n: 46, esp: 92, rx: 470, ry: 36 },
    { eixo: "apoio", x: 310, y: 252, n: 18, esp: 56, rx: 310, ry: 314 }
  ];
  var PONTOS = (function () {
    var r = rng(7), out = [];
    GRUPOS.forEach(function (g) {
      for (var i = 0; i < g.n; i++) {
        var a = r() * Math.PI * 2, d = Math.sqrt(r()) * g.esp;
        out.push({ x: g.x + Math.cos(a) * d * 1.25, y: g.y + Math.sin(a) * d * 0.75, eixo: g.eixo });
      }
    });
    return out;
  })();

  function mapa(ctx, voar, apagado) {
    var s = sv("svg", { viewBox: "0 0 640 324", class: "rm-est__mapa" + (apagado ? " rm-apagado" : ""), role: "img",
      "aria-label": "Mapa ilustrativo do banco vetorial: cada ponto é um chunk; trechos parecidos ficam perto" });
    GRUPOS.forEach(function (g) {
      s.appendChild(sv("text", { x: g.rx, y: g.ry, class: "rm-est__mapa-rot rm-eixo--" + g.eixo, "text-anchor": "middle" }, NOME_EIXO[g.eixo]));
    });
    PONTOS.forEach(function (p, i) {
      var c = sv("circle", { r: 4.5, class: "rm-pt rm-eixo--" + p.eixo });
      if (voar && !reduzido) {
        c.style.transform = "translate(-30px, 162px)";
        c.style.opacity = "0";
        ctx.depois(120 + i * 18, function () { c.style.transform = "translate(" + p.x + "px," + p.y + "px)"; c.style.opacity = ""; });
      } else {
        c.style.transform = "translate(" + p.x + "px," + p.y + "px)";
      }
      s.appendChild(c);
    });
    return s;
  }

  /* ---------- texto de exemplo (fontes reais: F01 e F04) ---------- */
  var BRUTO = [
    ["[[PAGINA 1]]", "marca"],
    ["RESOLUÇÃO DO CONSELHO DE ADMINISTRAÇÃO Nº 0037/2025", ""],
    ["Define os grupos de usuá-", "hifen"],
    ["rios do RU da UnB e os valores das refeições", "hifen"],
    ["Art. 2º Para os fins desta Resolução, serão considera-", "hifen"],
    ["dos 4 (quatro) grupos de usuários do RU", "hifen"],
    ["1", "lixo"],
    ["Read More »", "lixo"]
  ];
  var LIMPO = [
    "[[PAGINA 1]]",
    "RESOLUÇÃO DO CONSELHO DE ADMINISTRAÇÃO Nº 0037/2025",
    "Define os grupos de usuários do RU da UnB e os valores das refeições",
    "Art. 2º Para os fins desta Resolução, serão considerados 4 (quatro) grupos de usuários do RU"
  ];
  var CABECALHO = "Valores das refeições e grupos de acesso (UnB · Diretoria do RU) · Valores das refeições e grupos > ";
  var SECOES = [
    { sec: "Grupo I", txt: "### Grupo I\nTodas as refeições gratuitas. Estudantes da PNAES com renda de até 1 salário mínimo per capita; cotistas de escola pública baixa renda; indígenas e quilombolas; …" },
    { sec: "Grupo II", txt: "### Grupo II\nFazem parte desse grupo: estudantes de graduação e de pós-graduação stricto sensu, estagiários do DGP/UnB, residentes …\nCafé da manhã: R$ 2,00\nAlmoço e jantar: R$ 4,50" },
    { sec: "Grupo III", txt: "### Grupo III\nFazem parte desse grupo: servidores, terceirizados e visitantes em geral …\nCafé da manhã: R$ 7,05\nAlmoço e jantar: R$ 15,20" }
  ];

  var REGRAS = [
    "Responda SOMENTE com os trechos numerados abaixo.",
    "Cite cada afirmação com [n].",
    "Sem resposta nos trechos: \"Não encontrei essa informação nas fontes da base.\"",
    "Não invente valores, datas, códigos ou pré-requisitos.",
    "No máximo 120 palavras."
  ];

  /* =========================================================
     FASE 1 · INGESTÃO (offline)
     ========================================================= */
  var INGESTAO = [
    {
      nome: "Fontes oficiais", sub: "36 documentos", dur: 5200,
      titulo: "1. Fontes oficiais entram no catálogo",
      texto: "Tudo começa pelos <b>36 documentos oficiais</b> da UnB: resoluções e preços do RU, cardápios semanais, PPCs, fluxogramas das engenharias, calendário acadêmico. Cada fonte é registrada com órgão, data, URL e eixo. O RUmo só responde com o que estiver aqui.",
      numeros: [["36", "fontes"], ["3", "eixos"]],
      arquivo: "rag/catalogo.yaml",
      desenhar: function (p, d, ctx) {
        var g = el("div", "rm-est__docs");
        for (var i = 1; i <= 36; i++) {
          var id = "F" + (i < 10 ? "0" : "") + i;
          var doc = el("span", "rm-est__doc rm-eixo--" + eixoDe(id), id);
          g.appendChild(doc);
          (function (doc, i) { ctx.depois(60 + i * 45, function () { doc.classList.add("rm-on"); }); })(doc, i);
        }
        p.appendChild(g);
        p.appendChild(legendaEixos());
      }
    },
    {
      nome: "Extração", sub: "PDF/HTML → texto", dur: 6200,
      titulo: "2. Extração e limpeza do texto",
      texto: "Os PDFs e páginas HTML viram <b>texto puro</b>. A limpeza junta palavras quebradas por hífen no fim da linha, corrige ligaduras perdidas e remove números de página e lixo de navegação. As marcas <code>[[PAGINA n]]</code> ficam, para a resposta poder citar a página.",
      numeros: [["pypdf", "+ pdfplumber"]],
      arquivo: "rag/rumo_rag/extracao.py",
      desenhar: function (p, d, ctx) {
        var linha = el("div", "rm-est__linha");
        var bruto = el("div", "rm-est__painel"), limpo = el("div", "rm-est__painel rm-est__painel--ok");
        bruto.appendChild(el("div", "rm-est__painel-tit", "Original (PDF da F01)"));
        limpo.appendChild(el("div", "rm-est__painel-tit", "Texto limpo (F01.txt)"));
        var lb = el("pre", "rm-est__mono"), ll = el("pre", "rm-est__mono");
        bruto.appendChild(lb); limpo.appendChild(ll);
        var linhasBrutas = BRUTO.map(function (b, i) {
          var s = el("span", "rm-est__ln rm-" + (b[1] || "ok"), esc(b[0]));
          lb.appendChild(s);
          ctx.depois(100 + i * 160, function () { s.classList.add("rm-on"); });
          return s;
        });
        ctx.depois(1700, function () { linhasBrutas.forEach(function (s) { s.classList.add("rm-marcar"); }); });
        LIMPO.forEach(function (t, i) {
          var s = el("span", "rm-est__ln" + (i === 0 ? " rm-marca" : ""), esc(t));
          ll.appendChild(s);
          ctx.depois(2700 + i * 450, function () { s.classList.add("rm-on"); });
        });
        linha.appendChild(bruto); linha.appendChild(seta()); linha.appendChild(limpo);
        p.appendChild(linha);
        p.appendChild(el("div", "rm-est__nota",
          '<span class="rm-tag rm-tag--hifen">hífen juntado</span> <span class="rm-tag rm-tag--lixo">removido</span> <span class="rm-tag rm-tag--marca">marca de página</span>'));
      }
    },
    {
      nome: "Chunking", sub: "~900 caracteres", dur: 6500,
      titulo: "3. Chunking: o texto vira pedaços",
      texto: "O LLM não lê um documento inteiro; ele lê <b>pedaços (chunks)</b>. O corte respeita a estrutura: títulos, artigos de norma, itens de edital, páginas. Cada chunk mira ~900 caracteres (máx. 1.400) e ganha um <b>cabeçalho de contexto</b> com documento e seção, que ajuda a achar trechos curtos como “Almoço e jantar: R$ 4,50”. Quando um bloco passa do limite, ele é cortado por frase com 150 caracteres repetidos entre vizinhos. Cardápios: uma refeição por chunk.",
      numeros: [["1.738", "chunks"], ["~900", "caracteres"], ["150", "de sobreposição"]],
      arquivo: "rag/rumo_rag/chunking.py",
      desenhar: function (p, d, ctx) {
        var doc = el("div", "rm-est__corte");
        doc.appendChild(el("div", "rm-est__painel-tit", "F04 · Valores das refeições e grupos de acesso"));
        var pecas = SECOES.map(function (s, i) {
          var c = el("div", "rm-est__chunk");
          var cab = el("div", "rm-est__cab", "<b>cabeçalho</b> " + esc(CABECALHO + s.sec));
          var corpo = el("div", "rm-est__txt", esc(s.txt).replace(/\n/g, "<br>"));
          var tam = el("div", "rm-est__tam", "F04-000" + (i + 1) + " · " + (CABECALHO.length + s.sec.length + s.txt.length) + " caracteres");
          c.appendChild(cab); c.appendChild(corpo); c.appendChild(tam);
          doc.appendChild(c);
          return c;
        });
        p.appendChild(doc);
        ctx.depois(1300, function () { doc.classList.add("rm-cortado"); });
        pecas.forEach(function (c, i) { ctx.depois(2000 + i * 500, function () { c.classList.add("rm-on"); }); });
      }
    },
    {
      nome: "Embeddings", sub: "bge-m3 · 1.024 dim", dur: 6000,
      titulo: "4. Embeddings: cada chunk vira um vetor",
      texto: "O modelo <b>BAAI/bge-m3</b> lê cada chunk (com o cabeçalho) e devolve <b>1.024 números</b> que representam o <i>significado</i> do texto. Textos com sentido parecido geram vetores parecidos, mesmo com palavras diferentes (“almoço” ≈ “refeição do meio-dia”). Os vetores são normalizados, para comparar por cosseno. O bge-m3 venceu o multilingual-e5-base na avaliação (MRR 0,984 × 0,932).",
      numeros: [["1.024", "dimensões"], ["fp16", "na GPU"]],
      arquivo: "rag/rumo_rag/indice.py · embed_passagens()",
      desenhar: function (p, d, ctx) {
        var linha = el("div", "rm-est__linha");
        var c = el("div", "rm-est__chunk rm-on rm-est__chunk--mini");
        c.appendChild(el("div", "rm-est__cab", "<b>F04-0002</b> · Grupo II"));
        c.appendChild(el("div", "rm-est__txt", "Estudantes de graduação…<br>Almoço e jantar: R$ 4,50"));
        var v = barras("F04-0002", "verde", 32);
        var saida = el("div", "rm-est__saida");
        saida.appendChild(v.el);
        saida.appendChild(el("code", "rm-est__nums", esc(v.legenda)));
        linha.appendChild(c); linha.appendChild(seta());
        linha.appendChild(caixaModelo("BAAI/bge-m3", "modelo de embedding"));
        linha.appendChild(seta()); linha.appendChild(saida);
        p.appendChild(linha);
        ctx.depois(900, function () { v.el.classList.add("rm-on"); });
        p.appendChild(el("div", "rm-est__nota", "Os 1.738 chunks passam por aqui, em lotes de 16."));
      }
    },
    {
      nome: "Banco vetorial", sub: "ChromaDB + BM25", dur: 6500,
      titulo: "5. Banco vetorial: os vetores são guardados",
      texto: "Os vetores vão para o <b>ChromaDB</b> (índice HNSW, distância cosseno), junto com o texto e os metadados (fonte, página, seção, URL). No mapa, cada ponto é um chunk: <b>assuntos parecidos ficam perto</b>. Em paralelo, um índice <b>BM25</b> guarda as palavras exatas, bom para datas e códigos de disciplina. Isso é feito <b>uma vez</b>; depois, cada pergunta só consulta.",
      numeros: [["1.738", "vetores"], ["HNSW", "cosseno"]],
      arquivo: "rag/rumo_rag/indice.py · indexar()",
      desenhar: function (p, d, ctx) {
        var linha = el("div", "rm-est__linha rm-est__linha--mapa");
        var lado = el("div", "rm-est__mapa-box");
        lado.appendChild(el("div", "rm-est__painel-tit", 'ChromaDB · <span class="rm-est__contador">0</span> chunks'));
        lado.appendChild(mapa(ctx, true, false));
        lado.appendChild(el("div", "rm-est__nota", "Projeção ilustrativa em 2D de vetores de 1.024 dimensões."));
        var bm = el("div", "rm-est__painel rm-est__bm25");
        bm.appendChild(el("div", "rm-est__painel-tit", "Índice BM25 · palavra → chunks"));
        [["almoço", "F03-0003 · F04-0002 · … (41)"], ["fga0314", "F16-0006 · F16-0011 · F16-0012"], ["11/11", "F09-0002 · F09-0007 · F09-0012"]].forEach(function (t, i) {
          var r = el("div", "rm-est__termo", "<code>" + t[0] + "</code><span>" + t[1] + "</span>");
          bm.appendChild(r);
          ctx.depois(1600 + i * 400, function () { r.classList.add("rm-on"); });
        });
        linha.appendChild(lado); linha.appendChild(bm);
        p.appendChild(linha);
        var cont = lado.querySelector(".rm-est__contador");
        ctx.contar(cont, 1738, 1700);
      }
    }
  ];

  /* =========================================================
     FASE 2 · PERGUNTA (online)
     ========================================================= */
  function temIdent(q) { return IDENT.test(q.toLowerCase()); }

  var CONSULTA = [
    {
      nome: "Pergunta", sub: "estudante", dur: 4500,
      titulo: "1. O estudante faz uma pergunta",
      texto: function (d) {
        return "A pergunta chega em linguagem natural, do jeito que o estudante escreveria. Hoje ela entra pela linha de comando (<code>python -m rumo_rag perguntar</code>); na Semana 4 entra pelo <code>POST /perguntar</code> do portal comum." +
          (d.id === "D7" ? " Neste exemplo, a pergunta é sobre algo que <b>não está</b> na base." : "");
      },
      numeros: [],
      arquivo: "rag/rumo_rag/__main__.py",
      desenhar: function (p, d, ctx) {
        var chat = el("div", "rm-est__chat");
        var b = el("div", "rm-est__balao rm-est__balao--eu");
        var t = el("span", "rm-est__digitando");
        b.appendChild(el("small", "", "Estudante")); b.appendChild(t);
        chat.appendChild(b);
        p.appendChild(chat);
        ctx.digitar(t, d.pergunta, 28);
      }
    },
    {
      nome: "Vira vetor", sub: "+ palavras-chave", dur: 6500,
      titulo: "2. A pergunta vira vetor e palavras-chave",
      texto: function (d) {
        return "A pergunta passa pelo <b>mesmo modelo bge-m3</b> usado nos chunks: assim ela cai no mesmo “espaço de significado”. Ao mesmo tempo, o tokenizador do BM25 tira palavras vazias (de, o, que…) e guarda os termos importantes. Perguntas compostas também são quebradas em subperguntas." +
          (temIdent(d.pergunta) ? " Aqui há uma <b>data</b>: ela vira um termo único (<code>11/11</code>), porque é exatamente o que o vetor tem dificuldade de distinguir." : "");
      },
      numeros: [["1.024", "números"]],
      arquivo: "rag/rumo_rag/indice.py · embed_consulta() · tokenizar()",
      desenhar: function (p, d, ctx) {
        var a = el("div", "rm-est__faixa");
        a.appendChild(el("div", "rm-est__faixa-tit", "Para a busca por <b>significado</b>"));
        var la = el("div", "rm-est__linha");
        la.appendChild(el("div", "rm-est__q", esc(d.pergunta)));
        la.appendChild(seta());
        la.appendChild(caixaModelo("bge-m3", ""));
        la.appendChild(seta());
        var v = barras(d.pergunta, "amarelo", 28), saida = el("div", "rm-est__saida");
        saida.appendChild(v.el); saida.appendChild(el("code", "rm-est__nums", esc(v.legenda)));
        la.appendChild(saida);
        a.appendChild(la);
        var b = el("div", "rm-est__faixa");
        b.appendChild(el("div", "rm-est__faixa-tit", "Para a busca por <b>palavras</b> (BM25)"));
        var fichas = el("div", "rm-est__fichas");
        (d.pergunta.toLowerCase().match(TOKEN) || []).forEach(function (w, i) {
          var cls = STOP[w] ? "rm-stop" : (IDENT.test(w) ? "rm-id" : "");
          var f = el("span", "rm-est__ficha " + cls, esc(w));
          fichas.appendChild(f);
          ctx.depois(1300 + i * 90, function () { f.classList.add("rm-on"); });
        });
        b.appendChild(fichas);
        p.appendChild(a); p.appendChild(b);
        ctx.depois(700, function () { v.el.classList.add("rm-on"); });
      }
    },
    {
      nome: "Busca híbrida", sub: "vetor + BM25", dur: 7000,
      titulo: "3. Busca híbrida no banco",
      texto: function (d) {
        var max = Math.max.apply(null, d.trechos_recuperados.map(function (t) { return t.similaridade || 0; }));
        var base = "A estrela é a pergunta. A <b>busca vetorial</b> acha os chunks mais próximos pelo cosseno (30 candidatos); a <b>busca BM25</b> acha os que têm as mesmas palavras (outros 30). Os números nas linhas são a similaridade real de cada trecho.";
        if (d.id === "D7") return base + " Repare: a mais alta foi só <b>" + num(max, 2) + "</b>. Nada na base fala de wi-fi; os vizinhos “mais próximos” estão longe.";
        if (temIdent(d.pergunta)) return base + " Como a pergunta tem uma data, o BM25 ganha <b>peso 3</b> na fusão: todos os dias do cardápio têm vetores quase iguais, só a palavra exata separa o 11/11.";
        return base;
      },
      numeros: [["30 + 30", "candidatos"]],
      arquivo: "rag/rumo_rag/indice.py · buscar()",
      desenhar: function (p, d, ctx) {
        var box = el("div", "rm-est__mapa-box");
        box.appendChild(el("div", "rm-est__painel-tit", "ChromaDB · vizinhos mais próximos da pergunta"));
        var s = mapa(ctx, false, true);
        var trechos = d.trechos_recuperados.slice().sort(function (a, b) { return (b.similaridade || 0) - (a.similaridade || 0); }).slice(0, 5);
        var max = trechos.length ? trechos[0].similaridade : 0;
        var q;
        if (max < 0.6) q = { x: 300, y: 172 };
        else { var g = GRUPOS.filter(function (g) { return g.eixo === eixoDe(trechos[0].doc_id); })[0]; q = { x: Math.max(g.x, 215), y: g.y + 6 }; }
        var raio = 0;
        var camada = sv("g", {});
        trechos.forEach(function (t, i) {
          var ang = (-90 + i * 72 + 20) * Math.PI / 180, r = (1 - t.similaridade) * 240;
          raio = Math.max(raio, r);
          var x = Math.max(24, Math.min(616, q.x + Math.cos(ang) * r)), y = Math.max(24, Math.min(300, q.y + Math.sin(ang) * r));
          var len = Math.hypot(x - q.x, y - q.y);
          var ln = sv("line", { x1: q.x, y1: q.y, x2: x, y2: y, class: "rm-est__liga" });
          ln.style.strokeDasharray = len; ln.style.strokeDashoffset = reduzido ? 0 : len;
          var pt = sv("circle", { cx: x, cy: y, r: 7, class: "rm-hit rm-eixo--" + eixoDe(t.doc_id) });
          // rótulo do lado com espaço, para não sair do mapa
          var dir = x < 150 ? 1 : x > 490 ? -1 : (Math.cos(ang) >= 0 ? 1 : -1);
          var rot = sv("text", { x: x + dir * 11, y: y + 4, "text-anchor": dir > 0 ? "start" : "end", class: "rm-est__hit-rot" },
            t.chunk_id + " · " + num(t.similaridade, 2));
          [ln, pt, rot].forEach(function (e) { e.classList.add("rm-oculto"); camada.appendChild(e); });
          ctx.depois(1500 + i * 380, function () {
            ln.classList.remove("rm-oculto"); ln.style.strokeDashoffset = 0;
            pt.classList.remove("rm-oculto"); rot.classList.remove("rm-oculto");
          });
        });
        var radar = sv("circle", { cx: q.x, cy: q.y, r: raio + 14, class: "rm-est__radar" });
        s.appendChild(radar);
        s.appendChild(camada);
        var est = [], k;
        for (k = 0; k < 10; k++) {
          var rr = k % 2 ? 5 : 12, a = (-90 + k * 36) * Math.PI / 180;
          est.push((q.x + Math.cos(a) * rr).toFixed(1) + "," + (q.y + Math.sin(a) * rr).toFixed(1));
        }
        s.appendChild(sv("polygon", { points: est.join(" "), class: "rm-est__estrela" }));
        s.appendChild(sv("text", { x: q.x, y: q.y + 28, "text-anchor": "middle", class: "rm-est__hit-rot rm-forte" }, "sua pergunta"));
        box.appendChild(s);
        var linha = el("div", "rm-est__linha rm-est__linha--mapa");
        linha.appendChild(box);
        var bm = el("div", "rm-est__painel rm-est__bm25");
        bm.appendChild(el("div", "rm-est__painel-tit", "BM25 procura as palavras"));
        var termos = (d.pergunta.toLowerCase().match(TOKEN) || []).filter(function (w) { return !STOP[w]; });
        var fichas = el("div", "rm-est__fichas");
        termos.forEach(function (w) { fichas.appendChild(el("span", "rm-est__ficha rm-on " + (IDENT.test(w) ? "rm-id" : ""), esc(w))); });
        bm.appendChild(fichas);
        if (temIdent(d.pergunta)) bm.appendChild(el("div", "rm-est__alerta", "Data ou código detectado → peso do BM25 × 3"));
        linha.appendChild(bm);
        p.appendChild(linha);
      }
    },
    {
      nome: "Fusão RRF", sub: "top 5", dur: 6500,
      titulo: "4. Fusão RRF: as duas listas viram uma",
      texto: "As duas listas de candidatos são combinadas pela <b>Reciprocal Rank Fusion</b>: cada trecho soma pontos pela posição em cada lista, <code>peso ÷ (60 + posição)</code>. Quem aparece bem nas duas sobe. Os <b>5 primeiros</b> seguem para o LLM. As barras mostram a nota real de cada trecho.",
      numeros: [["k = 60", "constante"], ["5", "trechos"]],
      arquivo: "rag/rumo_rag/indice.py · buscar()",
      desenhar: function (p, d, ctx) {
        var topo = el("div", "rm-est__funil");
        topo.appendChild(el("span", "rm-est__pilula", "30 do vetorial"));
        topo.appendChild(el("span", "rm-est__mais", "+"));
        topo.appendChild(el("span", "rm-est__pilula", "30 do BM25"));
        topo.appendChild(el("span", "rm-est__mais", "→"));
        topo.appendChild(el("code", "rm-est__formula", "nota = Σ peso ÷ (60 + posição)"));
        p.appendChild(topo);
        var lista = el("ol", "rm-est__rank");
        var max = Math.max.apply(null, d.trechos_recuperados.map(function (t) { return t.nota_rrf; }));
        d.trechos_recuperados.forEach(function (t, i) {
          var li = el("li", "rm-eixo--" + eixoDe(t.doc_id));
          li.innerHTML = '<span class="rm-est__n">[' + (i + 1) + ']</span>' +
            '<span class="rm-est__rank-txt"><b>' + esc(t.chunk_id) + "</b> " + esc(t.titulo) + (t.secao ? " › " + esc(t.secao.split(" > ").pop()) : "") + "</span>" +
            '<span class="rm-est__trilha"><i style="--w:' + Math.round(t.nota_rrf / max * 100) + '%"></i></span>' +
            '<code>' + num(t.nota_rrf, 4) + "</code>";
          lista.appendChild(li);
          ctx.depois(500 + i * 350, function () { li.classList.add("rm-on"); });
        });
        p.appendChild(lista);
      }
    },
    {
      nome: "Prompt", sub: "trechos + regras", dur: 6500,
      titulo: "5. O prompt é montado",
      texto: "O LLM <b>não recebe a pergunta sozinha</b>. Ele recebe as regras, os trechos numerados <code>[1]…[5]</code> (com fonte, página e seção) e, por último, a pergunta. É isso que mantém a resposta presa aos documentos.",
      numeros: [["5", "regras"], ["5", "trechos"]],
      arquivo: "rag/rumo_rag/geracao.py · montar_mensagens()",
      desenhar: function (p, d, ctx) {
        var doc = el("div", "rm-est__prompt");
        var blocos = [];
        var r = el("div", "rm-est__pbloco rm-est__pbloco--regras", "<b>system · regras</b>" + REGRAS.map(function (x, i) { return "<span>" + (i + 1) + ". " + esc(x) + "</span>"; }).join(""));
        blocos.push(r);
        d.trechos_recuperados.slice(0, 5).forEach(function (t, i) {
          blocos.push(el("div", "rm-est__pbloco rm-eixo--" + eixoDe(t.doc_id),
            "<b>[" + (i + 1) + "] Fonte " + esc(t.doc_id) + "</b> — " + esc(t.titulo) + ", p. " + t.pagina + (t.secao ? " · " + esc(t.secao.split(" > ").pop()) : "")));
        });
        blocos.push(el("div", "rm-est__pbloco rm-est__pbloco--q", "<b>Pergunta:</b> " + esc(d.pergunta)));
        blocos.forEach(function (b, i) { doc.appendChild(b); ctx.depois(200 + i * 380, function () { b.classList.add("rm-on"); }); });
        p.appendChild(doc);
      }
    },
    {
      nome: "LLM", sub: "Qwen2.5-7B", dur: function (d) { return Math.min(14000, 3200 + d.resposta.length * 22); },
      titulo: "6. O LLM escreve a resposta",
      texto: function (d) {
        return "O <b>Qwen2.5-7B-Instruct</b> roda <b>na máquina do grupo</b>, quantizado em 4 bits (~5,5 GB de uma GPU de 8 GB). A geração é determinística (sem sorteio de palavras): a mesma pergunta dá a mesma resposta. Ele escreve citando os trechos com <code>[n]</code>." +
          (d.id === "D7" ? " Como nenhum trecho responde à pergunta, ele segue a regra 3 e <b>recusa</b>, em vez de inventar." : "");
      },
      numeros: [["4 bits", "NF4"], ["0", "temperatura"]],
      arquivo: "rag/rumo_rag/geracao.py · _gerar_hf()",
      desenhar: function (p, d, ctx) {
        var linha = el("div", "rm-est__linha");
        linha.appendChild(caixaModelo("Qwen2.5-7B", "4 bits · local"));
        linha.appendChild(seta());
        var out = el("div", "rm-est__painel rm-est__painel--ok rm-est__gerado");
        out.appendChild(el("div", "rm-est__painel-tit", "gerando…"));
        var t = el("div", "rm-est__digitando");
        out.appendChild(t);
        linha.appendChild(out);
        p.appendChild(linha);
        ctx.digitar(t, d.resposta, 18, function () {
          t.innerHTML = realcar(d.resposta);
          t.classList.add("rm-fim");
          out.querySelector(".rm-est__painel-tit").textContent = "resposta pronta";
        });
      }
    },
    {
      nome: "Resposta", sub: "+ fontes", dur: 7000,
      titulo: "7. Resposta com as fontes",
      texto: function (d) {
        if (!d.fontes_citadas.length) return "Sem base, sem resposta inventada: o RUmo diz que <b>não encontrou</b> e indica quem procurar. Esse comportamento é medido: recusar quando falta fonte é uma das métricas da Entrega 1.";
        return "O código lê os <code>[n]</code> da resposta e troca cada um pela <b>fonte real</b>: documento, órgão, página e link oficial. Citação de número que não existe é descartada. O estudante pode conferir na fonte.";
      },
      numeros: [],
      arquivo: "rag/rumo_rag/geracao.py",
      desenhar: function (p, d, ctx) {
        var chat = el("div", "rm-est__chat");
        chat.appendChild(el("div", "rm-est__balao rm-est__balao--eu rm-on", "<small>Estudante</small>" + esc(d.pergunta)));
        var r = el("div", "rm-est__balao rm-est__balao--rumo", "<small>RUmo</small>" + realcar(d.resposta));
        chat.appendChild(r);
        ctx.depois(300, function () { r.classList.add("rm-on"); });
        if (d.fontes_citadas.length) {
          var fs = el("div", "rm-est__fontes");
          d.fontes_citadas.forEach(function (f, i) {
            var a = el("a", "rm-est__fonte rm-eixo--" + eixoDe(f.doc_id),
              "<b>[" + f.n + "] " + esc(f.doc_id) + " · p. " + f.pagina + "</b><span>" + esc(f.titulo) + "</span><small>" + esc(f.orgao) + " ↗</small>");
            a.href = f.url; a.target = "_blank"; a.rel = "noopener";
            fs.appendChild(a);
            ctx.depois(1200 + i * 300, function () { a.classList.add("rm-on"); });
          });
          chat.appendChild(fs);
        } else {
          var rec = el("div", "rm-est__recusa", "Recusa correta · nenhuma fonte da base trazia a resposta");
          chat.appendChild(rec);
          ctx.depois(1200, function () { rec.classList.add("rm-on"); });
        }
        p.appendChild(chat);
      }
    }
  ];

  var CENARIOS = [
    { id: "D1", nome: "Preço do almoço" },
    { id: "D2", nome: "Cardápio com data" },
    { id: "D7", nome: "Fora da base (recusa)" }
  ];

  /* =========================================================
     Montagem do componente
     ========================================================= */
  function montar(raiz) {
    if (raiz.getAttribute("data-pronto")) return;
    raiz.setAttribute("data-pronto", "1");
    var DEMO = window.RUMO_DEMO || [];
    var cens = CENARIOS.map(function (c) {
      for (var i = 0; i < DEMO.length; i++) if (DEMO[i].id === c.id) return { nome: c.nome, d: DEMO[i] };
      return null;
    }).filter(Boolean);

    var est = { modo: "ingestao", cen: 0, passo: 0, tocando: false, modoEst: "" };
    var timers = [], proximo = null;

    var ctx = {
      depois: function (ms, fn) { timers.push(setTimeout(fn, reduzido ? 0 : ms)); },
      digitar: function (alvo, texto, vel, fim) {
        if (reduzido) { alvo.textContent = texto; if (fim) fim(); return; }
        var i = 0;
        (function passo() {
          i += texto.length > 160 ? 3 : 1;
          alvo.textContent = texto.slice(0, i);
          if (i < texto.length) timers.push(setTimeout(passo, vel));
          else if (fim) fim();
        })();
      },
      contar: function (alvo, total, ms) {
        if (reduzido) { alvo.textContent = milhar(total); return; }
        var t0 = null, vivo = true;
        timers.push({ cancelar: function () { vivo = false; } });
        (function quadro(t) {
          if (!vivo) return;
          if (t0 === null) t0 = t;
          var f = Math.min(1, (t - t0) / ms);
          alvo.textContent = milhar(Math.round(total * (1 - Math.pow(1 - f, 3))));
          if (f < 1) requestAnimationFrame(quadro);
        })(performance.now());
      }
    };
    function limpar() {
      timers.forEach(function (t) { if (t && t.cancelar) t.cancelar(); else clearTimeout(t); });
      timers = [];
      clearTimeout(proximo);
    }

    // topo: modos, cenários e controles
    var topo = el("div", "rm-est__topo");
    var modos = el("div", "rm-est__modos");
    var bIng = el("button", "rm-est__modo", '<b>1</b> Ingestão <small>offline · uma vez</small>');
    var bCon = el("button", "rm-est__modo", '<b>2</b> Pergunta <small>online · a cada pergunta</small>');
    [bIng, bCon].forEach(function (b) { b.type = "button"; modos.appendChild(b); });
    if (!cens.length) bCon.disabled = true;
    bIng.addEventListener("click", function () { parar(); est.modo = "ingestao"; est.passo = 0; render(); });
    bCon.addEventListener("click", function () { parar(); est.modo = "consulta"; est.passo = 0; render(); });

    var boxCen = el("div", "rm-est__cens");
    boxCen.appendChild(el("span", "rm-est__cens-rot", "Exemplo:"));
    var bCens = cens.map(function (c, i) {
      var b = el("button", "rm-est__cen", esc(c.nome));
      b.type = "button";
      b.addEventListener("click", function () { parar(); est.cen = i; est.passo = 0; render(); });
      boxCen.appendChild(b);
      return b;
    });

    var ctr = el("div", "rm-est__ctr");
    var bAnt = el("button", "rm-est__btn rm-est__btn--sec", "◀");
    var bPlay = el("button", "rm-est__btn", "▶ Reproduzir");
    var bProx = el("button", "rm-est__btn rm-est__btn--sec", "▶|");
    var rotPasso = el("span", "rm-est__passo");
    var bTela = el("button", "rm-est__btn rm-est__btn--sec",
      '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" style="vertical-align:-2px"><path fill="none" stroke="currentColor" stroke-width="2.5" d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg>');
    bAnt.setAttribute("aria-label", "Passo anterior");
    bProx.setAttribute("aria-label", "Próximo passo");
    bTela.setAttribute("aria-label", "Tela cheia"); bTela.title = "Tela cheia";
    [bAnt, bPlay, bProx, rotPasso, bTela].forEach(function (b) { if (b.tagName === "BUTTON") b.type = "button"; ctr.appendChild(b); });
    topo.appendChild(modos); topo.appendChild(boxCen); topo.appendChild(ctr);

    // esteira
    var esteira = el("div", "rm-est__esteira");
    var trilho = el("div", "rm-est__trilho");
    var cheio = el("span", "rm-est__cheio"), pacote = el("span", "rm-est__pacote");
    trilho.appendChild(cheio); trilho.appendChild(pacote);
    var estacoes = el("div", "rm-est__estacoes");
    esteira.appendChild(trilho); esteira.appendChild(estacoes);

    // palco
    var palco = el("div", "rm-est__palco");
    var visual = el("div", "rm-est__visual");
    var info = el("div", "rm-est__info");
    info.setAttribute("aria-live", "polite");
    palco.appendChild(visual); palco.appendChild(info);

    raiz.appendChild(topo); raiz.appendChild(esteira); raiz.appendChild(palco);

    function etapas() { return est.modo === "ingestao" ? INGESTAO : CONSULTA; }
    function dado() { return cens.length ? cens[est.cen].d : null; }
    function val(v, d) { return typeof v === "function" ? v(d) : v; }

    function montarEstacoes() {
      estacoes.innerHTML = "";
      var lista = etapas();
      estacoes.style.setProperty("--n", lista.length);
      trilho.style.setProperty("--n", lista.length);
      lista.forEach(function (e, i) {
        var b = el("button", "rm-est__estacao", '<span class="rm-est__num">' + (i + 1) + "</span><b>" + e.nome + "</b><small>" + e.sub + "</small>");
        b.type = "button";
        b.addEventListener("click", function () { parar(); est.passo = i; render(); });
        estacoes.appendChild(b);
      });
      est.modoEst = est.modo;
    }

    function render() {
      limpar();
      var lista = etapas(), e = lista[est.passo], d = dado();
      if (est.modoEst !== est.modo) montarEstacoes();
      raiz.classList.toggle("rm-consulta", est.modo === "consulta");
      raiz.classList.toggle("rm-tocando", est.tocando);
      bIng.setAttribute("aria-pressed", est.modo === "ingestao");
      bCon.setAttribute("aria-pressed", est.modo === "consulta");
      bCens.forEach(function (b, i) { b.setAttribute("aria-pressed", i === est.cen); });
      boxCen.hidden = est.modo !== "consulta";

      Array.prototype.forEach.call(estacoes.children, function (b, i) {
        b.classList.toggle("rm-ativo", i === est.passo);
        b.classList.toggle("rm-feito", i < est.passo);
        if (i === est.passo) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      });
      var pos = ((est.passo + 0.5) / lista.length * 100) + "%";
      pacote.style.left = pos; cheio.style.width = pos;

      visual.innerHTML = "";
      visual.classList.remove("rm-entrar"); void visual.offsetWidth; visual.classList.add("rm-entrar");
      e.desenhar(visual, d, ctx);

      var nums = (e.numeros || []).map(function (n) { return "<span><b>" + n[0] + "</b> " + n[1] + "</span>"; }).join("");
      info.innerHTML =
        '<div class="rm-est__fase">' + (est.modo === "ingestao" ? "Fase 1 · Ingestão · offline" : "Fase 2 · Pergunta · online") + "</div>" +
        "<h4>" + e.titulo + "</h4><p>" + val(e.texto, d) + "</p>" +
        (nums ? '<div class="rm-est__numeros">' + nums + "</div>" : "") +
        '<div class="rm-est__arquivo">No código: <code>' + e.arquivo + "</code></div>";

      rotPasso.textContent = (est.passo + 1) + " / " + lista.length;
      bAnt.disabled = est.passo === 0 && est.modo === "ingestao";
      bPlay.textContent = est.tocando ? "❚❚ Pausar" : "▶ Reproduzir";
      if (est.tocando) proximo = setTimeout(avancar, val(e.dur, d) + (reduzido ? 1500 : 0));
    }

    function avancar() {
      if (est.passo < etapas().length - 1) est.passo++;
      else if (est.modo === "ingestao" && cens.length) { est.modo = "consulta"; est.passo = 0; }
      else { est.tocando = false; }
      render();
    }
    function voltar() {
      if (est.passo > 0) est.passo--;
      else if (est.modo === "consulta") { est.modo = "ingestao"; est.passo = INGESTAO.length - 1; }
      render();
    }
    function parar() { est.tocando = false; clearTimeout(proximo); }

    bPlay.addEventListener("click", function () {
      if (est.tocando) { parar(); bPlay.textContent = "▶ Reproduzir"; raiz.classList.remove("rm-tocando"); return; }
      // terminou tudo? recomeça do início
      if (est.modo === "consulta" && est.passo === CONSULTA.length - 1) { est.modo = "ingestao"; est.passo = 0; }
      est.tocando = true;
      render();
    });
    bProx.addEventListener("click", function () { parar(); avancar(); });
    bAnt.addEventListener("click", function () { parar(); voltar(); });
    bTela.addEventListener("click", function () {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (raiz.requestFullscreen) raiz.requestFullscreen();
    });
    raiz.addEventListener("keydown", function (ev) {
      if (ev.target.closest && ev.target.closest("a")) return;
      if (ev.key === "ArrowRight") { parar(); avancar(); ev.preventDefault(); }
      if (ev.key === "ArrowLeft") { parar(); voltar(); ev.preventDefault(); }
    });

    if (raiz.getAttribute("data-modo") === "consulta" && cens.length) est.modo = "consulta";
    render();
  }

  function iniciar() { document.querySelectorAll("[data-esteira]").forEach(montar); }
  if (typeof document$ !== "undefined") document$.subscribe(iniciar);  // navegação instantânea do Material
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();

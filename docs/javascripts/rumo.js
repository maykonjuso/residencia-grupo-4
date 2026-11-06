/* Interações da GitPage do RUmo (Grupo 04). Sem dependências externas.
   Respeita "prefers-reduced-motion". Os dados da demonstração vêm de demo-dados.js,
   gerado a partir de rag/avaliacao/demo_respostas.json (saídas reais do protótipo). */
(function () {
  "use strict";

  var reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.documentElement.classList.add("rm-js");
  var DEMO = window.RUMO_DEMO || [];

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function porId(id) { for (var i = 0; i < DEMO.length; i++) if (DEMO[i].id === id) return DEMO[i]; return null; }
  function realcarCitacoes(t) { return esc(t).replace(/\[(\d+)\]/g, '<b class="rm-cit">[$1]</b>'); }

  /* ---------- Fundo do hero: fichas com termos da base ---------- */
  var TERMOS = ["RU Gama", "R$ 4,50", "Grupo II", "CAD 37/2025", "almoço 11h–14h30", "vegetariano estrito",
    "FGA0314", "Cálculo 1", "MDS → Requisitos", "ABI Engenharia", "PPGEB", "2026.2", "trancamento",
    "SIGAA", "ChromaDB", "e5-base", "BM25", "RRF", "top-5", "[1][2]", "Energia · 251 cr", "Software · 235 cr",
    "Aeroespacial", "Automotiva", "Eletrônica", "Edital 24/2026", "PNAES"];

  function montarFundo(canvas) {
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var fichas = [], mouse = { x: -999, y: -999 }, w = 0, h = 0;
    function nova(y) {
      return { t: TERMOS[Math.floor(Math.random() * TERMOS.length)], x: Math.random() * w,
        y: y === undefined ? Math.random() * h : y, v: 0.15 + Math.random() * 0.35,
        a: 0.08 + Math.random() * 0.22, s: 10 + Math.random() * 4, dx: 0 };
    }
    function dimensionar() {
      var r = canvas.getBoundingClientRect();
      w = r.width; h = r.height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      fichas = [];
      for (var i = 0, n = Math.round(w * h / 16000); i < n; i++) fichas.push(nova());
    }
    function desenhar() {
      ctx.clearRect(0, 0, w, h);
      for (var i = 0; i < fichas.length; i++) {
        var f = fichas[i];
        var ddx = f.x - mouse.x, ddy = f.y - mouse.y, d = Math.sqrt(ddx * ddx + ddy * ddy);
        if (d < 110) f.dx += (ddx / (d || 1)) * 0.4;
        f.dx *= 0.92; f.x += f.dx; f.y -= f.v;
        if (f.y < -20) fichas[i] = nova(h + 20);
        var perto = d < 140 ? (1 - d / 140) : 0;
        ctx.font = "600 " + f.s + "px 'Source Code Pro', monospace";
        var largura = ctx.measureText(f.t).width;
        ctx.globalAlpha = Math.min(0.9, f.a + perto * 0.6);
        ctx.strokeStyle = perto ? "#ffcc00" : "#2fa65f";
        ctx.lineWidth = 1;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(f.x - 6, f.y - f.s, largura + 12, f.s + 8, 4);
        else ctx.rect(f.x - 6, f.y - f.s, largura + 12, f.s + 8);
        ctx.stroke();
        ctx.fillStyle = perto ? "#ffe680" : "#d6e6f5";
        ctx.fillText(f.t, f.x, f.y);
      }
      ctx.globalAlpha = 1;
      if (!reduzido) requestAnimationFrame(desenhar);
    }
    dimensionar();
    window.addEventListener("resize", dimensionar);
    var hero = canvas.parentElement;
    hero.addEventListener("mousemove", function (e) {
      var r = canvas.getBoundingClientRect();
      mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
    });
    hero.addEventListener("mouseleave", function () { mouse.x = mouse.y = -999; });
    requestAnimationFrame(desenhar);
  }

  /* ---------- Texto digitado ---------- */
  var alvoDigitado = null, timerDigitado = null;
  function digitar(alvo, palavra, velocidade, fim) {
    clearTimeout(alvo._t);
    if (reduzido) { alvo.textContent = palavra; if (fim) fim(); return; }
    var j = 0;
    (function escrever() {
      j += velocidade > 20 ? 1 : 3;
      alvo.textContent = palavra.slice(0, j);
      if (j < palavra.length) alvo._t = setTimeout(escrever, velocidade);
      else if (fim) fim();
    })();
  }
  function trocarPalavra(palavra) {
    if (!alvoDigitado) return;
    clearTimeout(timerDigitado);
    if (reduzido) { alvoDigitado.textContent = palavra; return; }
    var atual = alvoDigitado.textContent.trim();
    (function apagar() {
      if (atual.length) { atual = atual.slice(0, -1); alvoDigitado.textContent = atual || " "; timerDigitado = setTimeout(apagar, 25); }
      else digitar(alvoDigitado, palavra, 60);
    })();
  }

  /* ---------- Janela de chat do hero (respostas reais) ---------- */
  function montarDemoHero(raiz) {
    if (!raiz || !DEMO.length) return;
    var cenas = [porId("D2") || DEMO[0], porId("D4") || DEMO[1], porId("D7") || DEMO[DEMO.length - 1]];
    var palavras = ["preços e cardápio do RU", "pré-requisitos e grades", "calendário e matrícula"];
    var abas = raiz.querySelectorAll(".rm-demo__abas button");
    var q = raiz.querySelector(".rm-chat__q"), r = raiz.querySelector(".rm-chat__r");
    var lista = raiz.querySelector(".rm-chat__trechos"), fontes = raiz.querySelector(".rm-chat__fontes");
    var info = raiz.querySelector(".rm-chat__info");
    var DURACAO = 9000, atual = -1, timers = [], ciclo = null;
    raiz.style.setProperty("--rm-duracao-cena", DURACAO + "ms");
    function depois(ms, fn) { timers.push(setTimeout(fn, reduzido ? 0 : ms)); }

    function mostrar(i) {
      atual = i;
      timers.forEach(clearTimeout); timers = [];
      abas.forEach(function (b, j) { b.setAttribute("aria-selected", j === i ? "true" : "false"); });
      var c = cenas[i];
      q.textContent = ""; r.textContent = ""; fontes.textContent = ""; lista.innerHTML = "";
      info.textContent = "busca híbrida · top " + c.trechos_recuperados.length;
      c.trechos_recuperados.forEach(function (t, k) {
        var li = el("li", "", "<em>" + (k + 1) + "</em>" + esc(t.chunk_id) + " · " + esc(t.titulo.slice(0, 38)) + "…");
        lista.appendChild(li);
      });
      digitar(q, c.pergunta, 22, function () {
        lista.querySelectorAll("li").forEach(function (li, k) { depois(250 + k * 220, function () { li.classList.add("rm-on"); }); });
        depois(1500, function () {
          var resp = c.resposta.length > 260 ? c.resposta.slice(0, 257) + "…" : c.resposta;
          digitar(r, resp, 12, function () {
            fontes.textContent = c.fontes_citadas.length
              ? "fontes: " + c.fontes_citadas.map(function (f) { return f.doc_id + " p." + f.pagina; }).join(" · ")
              : "sem fonte → não respondeu";
          });
        });
      });
      trocarPalavra(palavras[i]);
      clearTimeout(ciclo);
      if (!reduzido) ciclo = setTimeout(function () { mostrar((i + 1) % cenas.length); }, DURACAO);
    }
    abas.forEach(function (b, i) { b.addEventListener("click", function () { mostrar(i); }); });
    raiz.addEventListener("mouseenter", function () { clearTimeout(ciclo); });
    raiz.addEventListener("mouseleave", function () {
      clearTimeout(ciclo);
      if (!reduzido) ciclo = setTimeout(function () { mostrar((atual + 1) % cenas.length); }, 4000);
    });
    mostrar(0);
  }

  /* ---------- Explorador de consultas ---------- */
  function montarExplorador(raiz) {
    if (!raiz || raiz.dataset.pronto || !DEMO.length) return;
    raiz.dataset.pronto = "1";
    var abas = el("div", "rm-exp__abas"); abas.setAttribute("role", "tablist");
    var painel = el("div", "rm-exp__painel"); painel.setAttribute("role", "tabpanel");
    var botoes = [];
    function mostrar(i) {
      var d = DEMO[i];
      botoes.forEach(function (b, j) { b.setAttribute("aria-selected", j === i ? "true" : "false"); b.tabIndex = j === i ? 0 : -1; });
      var citados = {};
      d.fontes_citadas.forEach(function (f) { citados[f.n] = true; });
      var html = '<div class="rm-exp__q">' + esc(d.pergunta) + "</div>";
      html += '<div class="rm-exp__col"><h4>Trechos recuperados (top ' + d.trechos_recuperados.length + ")</h4>";
      d.trechos_recuperados.forEach(function (t, k) {
        var sim = t.similaridade != null ? " · similaridade " + t.similaridade : "";
        html += '<div class="rm-exp__trecho' + (citados[k + 1] ? " rm-citado" : "") + '" style="animation-delay:' + (reduzido ? 0 : k * 80) + 'ms">' +
          '<span class="rm-exp__meta">[' + (k + 1) + "] " + esc(t.chunk_id) + " · p." + t.pagina + sim + "</span>" +
          "<b>" + esc(t.doc_id) + "</b>" + esc(t.titulo) + "<br>" + esc(t.texto.slice(0, 220)) + "…</div>";
      });
      html += '</div><div class="rm-exp__col"><h4>Resposta gerada (' + esc(d.backend_rotulo || d.backend) + ")</h4>";
      html += '<div class="rm-exp__resposta">' + realcarCitacoes(d.resposta) + "</div>";
      if (d.valores_sem_fonte && d.valores_sem_fonte.length) {
        html += '<div class="rm-exp__alerta">⚠ Valores sem fonte nos trechos: <b>' + esc(d.valores_sem_fonte.join(", ")) + "</b></div>";
      }
      html += '<div class="rm-exp__fontes"><b>Fontes citadas:</b>';
      if (!d.fontes_citadas.length) html += " nenhuma (o sistema não encontrou base para responder).";
      d.fontes_citadas.forEach(function (f) {
        html += '<a href="' + esc(f.url) + '" target="_blank" rel="noopener">[' + f.n + "] " + esc(f.doc_id) + " · " + esc(f.titulo) + " · p." + f.pagina + "</a>";
      });
      html += "</div><p class=\"legenda\">Busca " + d.tempo_busca_s + " s · geração " + d.tempo_geracao_s + " s (RTX 4060).</p></div>";
      painel.innerHTML = html;
    }
    DEMO.forEach(function (d, i) {
      var b = el("button", "rm-exp__aba", d.id + " · " + esc(d.rotulo || "") + "<small>" + d.fontes_citadas.length + " fonte(s) citada(s)</small>");
      b.type = "button"; b.setAttribute("role", "tab");
      b.addEventListener("click", function () { mostrar(i); });
      b.addEventListener("keydown", function (ev) {
        var dd = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
        if (dd) { var n = (i + dd + DEMO.length) % DEMO.length; mostrar(n); botoes[n].focus(); }
      });
      botoes.push(b); abas.appendChild(b);
    });
    raiz.appendChild(abas); raiz.appendChild(painel);
    mostrar(0);
  }

  /* =========================================================
     Diagrama animado: como o RUmo funciona e conversa com o Grupo 09
     ========================================================= */
  var NOS = {
    usuario: [12, 300, 150, 84, "Estudante", "pergunta em português"],
    portal: [196, 300, 170, 84, "Portal único", "identidade visual UnB"],
    orq: [400, 300, 185, 84, "Orquestrador", "LLM roteador"],
    api04: [630, 62, 165, 76, "API do RUmo", "POST /perguntar"],
    busca: [825, 62, 165, 76, "Busca híbrida", "bge-m3 + BM25 → RRF"],
    indice: [1020, 62, 165, 76, "ChromaDB", "banco vetorial"],
    llm04: [825, 178, 165, 76, "LLM gerador", "Qwen2.5-7B local"],
    resp04: [630, 178, 165, 76, "Resposta", "com fontes [n]"],
    base: [630, 288, 165, 70, "Base curada", "36 fontes oficiais"],
    ingest: [825, 288, 165, 70, "Ingestão", "extrair · chunk · embed"],
    api09: [630, 470, 165, 76, "API do Grupo 09", "POST /perguntar"],
    rag09: [825, 470, 165, 76, "RAG do Grupo 09", "salas e acessos"],
    base09: [1020, 470, 165, 76, "Base do G09", "plantas da FCTE"],
    resp09: [630, 600, 165, 76, "Rota", "com fontes do G09"]
  };
  var ARESTAS = {
    a_up: ["M162,325 L196,325", "comum"], a_po: ["M366,325 L400,325", "comum"],
    a_op: ["M400,360 L366,360", "comum"], a_pu: ["M196,360 L162,360", "comum"],
    a_o4: ["M585,318 C612,318 604,100 630,100", "g04"], a_4b: ["M795,100 L825,100", "g04"],
    a_bi: ["M990,100 L1020,100", "g04"], a_il: ["M1102,138 C1102,190 1030,216 990,216", "g04"],
    a_lr: ["M825,216 L795,216", "g04"], a_ro: ["M630,225 C590,225 520,255 505,300", "g04"],
    a_bg: ["M795,323 L825,323", "g04 offline"], a_gi: ["M990,323 C1160,323 1160,230 1160,138", "g04 offline"],
    a_o9: ["M585,366 C612,366 604,508 630,508", "g09"], a_9r: ["M795,508 L825,508", "g09"],
    a_rb: ["M990,508 L1020,508", "g09"], a_rr: ["M907,546 C907,638 840,638 795,638", "g09"],
    a_r9: ["M630,638 C540,638 480,470 480,384", "g09"]
  };
  var CENARIOS = [
    {
      id: "ingestao", nome: "0 · Antes das perguntas: ingestão",
      pergunta: "Etapa offline: monta a base de conhecimento e o banco vetorial.",
      passos: [
        { nos: ["base"], arestas: [], quem: "g04", titulo: "Curadoria das fontes",
          texto: "36 documentos oficiais (RU, DDS/DAC, SAA, DEG, FCTE, PPCs e fluxogramas das engenharias, PPGEB) entram no catálogo com órgão, data, URL e eixo.",
          carga: "- id: F09\n  titulo: Cardápio semanal do RU Gama — 09/11 a 15/11/2026\n  orgao: UnB · Diretoria do RU\n  eixo: ru\n  tipo: cardapio\n  url: https://ru.unb.br/wp-content/uploads/2026/11/..." },
        { nos: ["ingest"], arestas: ["a_bg"], quem: "g04", titulo: "Extração e chunking",
          texto: "PDFs com pypdf; cardápios lidos como tabela (pdfplumber) e convertidos em um registro por refeição e por dia; HTML com abas vira seções. Chunks de ~900 caracteres respeitando títulos e artigos.",
          carga: "## Almoço · quarta-feira 11/11/2026\n- Prato principal vegetariano estrito:\n  Abobrinha recheada com lentilha ao sugo\n- Guarnição: Mix de batatas assadas" },
        { nos: ["indice"], arestas: ["a_gi"], quem: "g04", titulo: "Embeddings e indexação",
          texto: "Cada chunk recebe um cabeçalho (documento + seção) e vira um vetor (BAAI/bge-m3, 1.024 dimensões). Os vetores e os metadados vão para o ChromaDB (HNSW, cosseno).",
          carga: "{\n  \"chunk_id\": \"F09-0007\",\n  \"doc_id\": \"F09\", \"pagina\": 2,\n  \"secao\": \"Almoço · quarta-feira 11/11/2026\",\n  \"eixo\": \"ru\", \"embedding\": [0.013, -0.041, ... 1024 valores]\n}" }
      ]
    },
    {
      id: "rumo", nome: "1 · Pergunta só do Grupo 04",
      pergunta: "“Qual a opção vegetariana estrita do almoço de quarta-feira (11/11) no RU Gama?”",
      passos: [
        { nos: ["usuario", "portal"], arestas: ["a_up"], quem: "comum", titulo: "O estudante pergunta no portal",
          texto: "Uma única porta de entrada para os dois sistemas, com a mesma identidade visual (cores e fontes da UnB)." },
        { nos: ["orq"], arestas: ["a_po"], quem: "comum", titulo: "O orquestrador classifica a intenção",
          texto: "Alimentação e RU são do Grupo 04. O orquestrador só encaminha; quem responde é o agente do grupo.",
          carga: "{ \"intencao\": \"ru.cardapio\", \"destinos\": [\"grupo04\"] }" },
        { nos: ["api04"], arestas: ["a_o4"], quem: "g04", titulo: "Chamada à API do RUmo",
          texto: "Contrato comum entre os grupos: pergunta em texto e contexto opcional.",
          carga: "POST /perguntar\n{\n  \"pergunta\": \"Qual a opção vegetariana estrita do almoço de quarta-feira (11/11) no RU Gama?\",\n  \"contexto\": { \"campus\": \"gama\", \"data\": \"2026-11-11\" }\n}" },
        { nos: ["busca"], arestas: ["a_4b"], quem: "g04", titulo: "Busca híbrida",
          texto: "A pergunta vira um embedding (bge-m3) e também termos para o BM25, que acerta nomes exatos como \"FGA0314\" ou \"vegetariano estrito\"." },
        { nos: ["indice"], arestas: ["a_bi"], quem: "g04", titulo: "Recuperação no ChromaDB",
          texto: "30 candidatos de cada buscador; a fusão RRF fica com os 5 melhores. No conjunto de teste, a fonte certa veio no top 5 em 100% das perguntas.",
          carga: "top 5: F09-0007 (Almoço · quarta 11/11) · F09-0006 · F08-0007 · F09-0008 · F09-0012" },
        { nos: ["llm04"], arestas: ["a_il"], quem: "g04", titulo: "O LLM recebe só os trechos",
          texto: "Os 5 trechos vão numerados [1]…[5], com regras: responder só com eles, citar cada afirmação e dizer \"Não encontrei\" quando faltar base." },
        { nos: ["resp04"], arestas: ["a_lr"], quem: "g04", titulo: "Resposta com fontes",
          texto: "As citações [n] são convertidas em fontes rastreáveis: documento, página, URL e chunk.",
          carga: "{\n  \"grupo\": \"grupo04\",\n  \"resposta\": \"Na quarta-feira, 11/11/2026, a opção vegetariana estrita do almoço é abobrinha recheada com lentilha ao sugo [1].\",\n  \"fontes\": [{ \"n\": 1, \"doc_id\": \"F09\", \"pagina\": 2,\n    \"url\": \"https://ru.unb.br/.../Gama-Semana-04-09-11-a-15-11.pdf\" }]\n}" },
        { nos: ["orq", "portal", "usuario"], arestas: ["a_ro", "a_op", "a_pu"], quem: "comum", titulo: "Volta ao estudante",
          texto: "O portal mostra a resposta e um selo por fonte (\"Grupo 04 · F09 p.2\"), com link para o documento original." }
      ]
    },
    {
      id: "integrado", nome: "2 · Pergunta que usa os dois grupos",
      pergunta: "“Estou na UAC. Como chego ao RU e o que tem no almoço hoje?”",
      passos: [
        { nos: ["usuario", "portal"], arestas: ["a_up"], quem: "comum", titulo: "Uma pergunta, dois assuntos",
          texto: "Rota dentro do campus é do Grupo 09; cardápio é do Grupo 04." },
        { nos: ["orq"], arestas: ["a_po"], quem: "comum", titulo: "O orquestrador divide a pergunta",
          texto: "O LLM roteador quebra a pergunta em subperguntas e escolhe o destino de cada uma.",
          carga: "{\n  \"subperguntas\": [\n    { \"texto\": \"Como chegar da UAC ao RU (MESP)?\", \"destino\": \"grupo09\" },\n    { \"texto\": \"O que tem no almoço do RU Gama em 11/11/2026?\", \"destino\": \"grupo04\" }\n  ]\n}" },
        { nos: ["api04", "api09"], arestas: ["a_o4", "a_o9"], quem: "comum", titulo: "Chamadas em paralelo",
          texto: "Os dois sistemas recebem o mesmo formato de requisição. Cada grupo continua dono do próprio código, base e entregáveis." },
        { nos: ["busca", "indice", "llm04", "resp04", "rag09", "base09", "resp09"],
          arestas: ["a_4b", "a_bi", "a_il", "a_lr", "a_9r", "a_rb", "a_rr"], quem: "comum", titulo: "Cada grupo responde com seu RAG",
          texto: "Grupo 04: cardápio do dia com fontes do RU. Grupo 09: rota com base no mapeamento das plantas da FCTE (implementação do Grupo 09)." },
        { nos: ["orq"], arestas: ["a_ro", "a_r9"], quem: "comum", titulo: "As respostas voltam etiquetadas",
          texto: "Cada resposta traz o campo \"grupo\" e as próprias fontes, para o estudante saber de onde veio cada parte.",
          carga: "[\n  { \"grupo\": \"grupo09\", \"resposta\": \"Saia da UAC pelo ... até o MESP.\", \"fontes\": [\"planta MESP\"] },\n  { \"grupo\": \"grupo04\", \"resposta\": \"Almoço de 11/11: ... [1]\", \"fontes\": [\"F09 p.2\"] }\n]" },
        { nos: ["portal", "usuario"], arestas: ["a_op", "a_pu"], quem: "comum", titulo: "Resposta única, fontes separadas",
          texto: "O orquestrador junta as duas partes sem misturar as fontes: \"Como chegar (Grupo 09)\" e \"O que tem no almoço (Grupo 04)\"." }
      ]
    },
    {
      id: "fora", nome: "3 · Pergunta sem base",
      pergunta: "“Qual o wifi da biblioteca da FCTE?”",
      passos: [
        { nos: ["usuario", "portal", "orq"], arestas: ["a_up", "a_po"], quem: "comum", titulo: "Pergunta fora do escopo das bases",
          texto: "O orquestrador encaminha ao RUmo, que cobre a vida acadêmica no campus." },
        { nos: ["api04", "busca", "indice"], arestas: ["a_o4", "a_4b", "a_bi"], quem: "g04", titulo: "A busca não acha uma fonte que responda",
          texto: "Os trechos mais parecidos falam da biblioteca e da rede sem fio nos PPCs, mas nenhum traz o dado pedido." },
        { nos: ["llm04", "resp04"], arestas: ["a_il", "a_lr"], quem: "g04", titulo: "O LLM se recusa a inventar",
          texto: "A regra 3 do prompt manda responder \"Não encontrei essa informação nas fontes da base.\" Isso aconteceu na demonstração real (pergunta D7).",
          carga: "{ \"grupo\": \"grupo04\", \"resposta\": \"Não encontrei essa informação nas fontes da base.\", \"fontes\": [] }" },
        { nos: ["orq", "portal", "usuario"], arestas: ["a_ro", "a_op", "a_pu"], quem: "comum", titulo: "Resposta honesta",
          texto: "Melhor dizer que não sabe e indicar o órgão (biblioteca/STI) do que dar uma informação falsa." }
      ]
    }
  ];

  function montarFluxo(raiz) {
    if (!raiz || raiz.dataset.pronto) return;
    raiz.dataset.pronto = "1";
    var NS = "http://www.w3.org/2000/svg";
    var topo = el("div", "rm-fluxo__topo");
    var corpo = el("div", "rm-fluxo__corpo");
    var info = el("div", "rm-fluxo__info");
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 1200 700");
    svg.setAttribute("class", "rm-fluxo__svg");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Diagrama: estudante, portal único, orquestrador, sistema do Grupo 04 (RAG do RU e do fluxo) e sistema do Grupo 09 (mapeamento)");
    svg.innerHTML =
      '<defs><marker id="rm-seta" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="13" markerHeight="13" orient="auto-start-reverse">' +
      '<path d="M0,0 L10,5 L0,10 z" fill="#6b7a8c"/></marker></defs>' +
      '<rect class="rm-grupo rm-grupo--comum" x="184" y="250" width="414" height="150" rx="14"/>' +
      '<text class="rm-rotulo rm-rotulo--comum" x="198" y="278">Camada comum · G04 + G09</text>' +
      '<rect class="rm-grupo rm-grupo--g04" x="612" y="8" width="584" height="365" rx="14"/>' +
      '<text class="rm-rotulo rm-rotulo--g04" x="628" y="42">Grupo 04 · RUmo (RU + fluxo)</text>' +
      '<rect class="rm-grupo rm-grupo--g09" x="612" y="412" width="584" height="282" rx="14"/>' +
      '<text class="rm-rotulo rm-rotulo--g09" x="628" y="448">Grupo 09 · mapeamento da FCTE</text>' +
      '<text class="rm-legenda-svg" x="12" y="470">linha cheia: pergunta em tempo real</text>' +
      '<text class="rm-legenda-svg" x="12" y="494">linha tracejada: preparo da base (offline)</text>' +
      '<text class="rm-legenda-svg" x="12" y="518">bolinha amarela: dados em trânsito</text>';
    var nosEl = {}, arestasEl = {};
    Object.keys(ARESTAS).forEach(function (k) {
      var p = document.createElementNS(NS, "path");
      p.setAttribute("d", ARESTAS[k][0]);
      p.setAttribute("class", "rm-aresta" + (ARESTAS[k][1].indexOf("offline") >= 0 ? " rm-aresta--offline" : "") +
        (ARESTAS[k][1].indexOf("g09") === 0 ? " rm-g09" : ""));
      svg.appendChild(p); arestasEl[k] = p;
    });
    Object.keys(NOS).forEach(function (k) {
      var n = NOS[k], g = document.createElementNS(NS, "g");
      g.setAttribute("class", "rm-no");
      g.innerHTML = '<rect x="' + n[0] + '" y="' + n[1] + '" width="' + n[2] + '" height="' + n[3] + '" rx="10"/>' +
        '<text x="' + (n[0] + n[2] / 2) + '" y="' + (n[1] + n[3] / 2 - 5) + '" text-anchor="middle">' + n[4] + "</text>" +
        '<text class="rm-sub" x="' + (n[0] + n[2] / 2) + '" y="' + (n[1] + n[3] / 2 + 18) + '" text-anchor="middle">' + n[5] + "</text>";
      svg.appendChild(g); nosEl[k] = g;
    });
    var camadaPacotes = document.createElementNS(NS, "g");
    svg.appendChild(camadaPacotes);

    var cen = 0, passo = -1, play = null;
    var botoesCen = CENARIOS.map(function (c, i) {
      var b = el("button", "rm-fluxo__cen", c.nome);
      b.type = "button";
      b.addEventListener("click", function () { parar(); escolher(i); });
      topo.appendChild(b); return b;
    });
    var ctr = el("div", "rm-fluxo__controles");
    var bAnt = el("button", "rm-fluxo__btn rm-fluxo__btn--sec", "◀");
    var bPlay = el("button", "rm-fluxo__btn", "▶ Reproduzir");
    var bProx = el("button", "rm-fluxo__btn rm-fluxo__btn--sec", "▶|");
    var rotPasso = el("span", "rm-fluxo__passo", "");
    [bAnt, bPlay, bProx].forEach(function (b) { b.type = "button"; });
    bAnt.setAttribute("aria-label", "Passo anterior"); bProx.setAttribute("aria-label", "Próximo passo");
    var bTela = el("button", "rm-fluxo__btn rm-fluxo__btn--sec", "⛶ Tela cheia");
    bTela.type = "button";
    bTela.addEventListener("click", function () {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (raiz.requestFullscreen) raiz.requestFullscreen();
    });
    ctr.appendChild(rotPasso); ctr.appendChild(bAnt); ctr.appendChild(bPlay); ctr.appendChild(bProx); ctr.appendChild(bTela);
    topo.appendChild(ctr);

    function animarPacote(path) {
      if (reduzido || !path.getTotalLength) return;
      var c = document.createElementNS(NS, "circle");
      c.setAttribute("r", "10"); c.setAttribute("class", "rm-pacote");
      camadaPacotes.appendChild(c);
      var total = path.getTotalLength(), ini = performance.now(), dur = 900;
      (function quadro(t) {
        var p = Math.min(1, (t - ini) / dur), pt = path.getPointAtLength(total * p);
        c.setAttribute("cx", pt.x); c.setAttribute("cy", pt.y);
        if (p < 1) requestAnimationFrame(quadro); else setTimeout(function () { c.remove(); }, 150);
      })(ini);
    }

    function render() {
      var c = CENARIOS[cen];
      botoesCen.forEach(function (b, i) { b.setAttribute("aria-pressed", i === cen ? "true" : "false"); });
      Object.keys(nosEl).forEach(function (k) { nosEl[k].classList.remove("rm-ativo", "rm-feito"); });
      Object.keys(arestasEl).forEach(function (k) { arestasEl[k].classList.remove("rm-ativa"); });
      for (var i = 0; i < passo; i++) c.passos[i].nos.forEach(function (n) { nosEl[n].classList.add("rm-feito"); });
      var html = '<div class="rm-fluxo__pergunta"><b>Pergunta:</b> ' + c.pergunta + "</div>";
      if (passo < 0) {
        html += '<div class="rm-fluxo__texto"><h4>Clique em ▶ Reproduzir</h4><p>Ou avance passo a passo com ▶|. Cada passo acende quem está agindo, anima a seta e mostra aqui embaixo os dados trocados.</p></div>';
        rotPasso.textContent = "0/" + c.passos.length;
      } else {
        var s = c.passos[passo];
        s.nos.forEach(function (n) { nosEl[n].classList.remove("rm-feito"); nosEl[n].classList.add("rm-ativo"); });
        s.arestas.forEach(function (a) { arestasEl[a].classList.add("rm-ativa"); animarPacote(arestasEl[a]); });
        var quem = { g04: "Grupo 04 · RUmo", g09: "Grupo 09", comum: "Camada comum" }[s.quem];
        html += '<div class="rm-fluxo__texto"><span class="rm-fluxo__quem rm-' + s.quem + '">Passo ' + (passo + 1) + " · " + quem + "</span>" +
          "<h4>" + s.titulo + "</h4><p>" + s.texto + "</p></div>" +
          (s.carga ? '<div class="rm-fluxo__dados"><span class="rm-fluxo__quem rm-comum">Dados trocados</span><pre><code>' + esc(s.carga) + "</code></pre></div>" : "");
        rotPasso.textContent = (passo + 1) + "/" + c.passos.length;
      }
      info.innerHTML = html;
    }
    function escolher(i) { cen = i; passo = -1; render(); }
    function avancar() {
      var n = CENARIOS[cen].passos.length;
      if (passo < n - 1) { passo++; render(); return true; }
      return false;
    }
    function parar() { clearInterval(play); play = null; bPlay.textContent = "▶ Reproduzir"; }
    bProx.addEventListener("click", function () { parar(); avancar(); });
    bAnt.addEventListener("click", function () { parar(); if (passo > -1) { passo--; render(); } });
    bPlay.addEventListener("click", function () {
      if (play) { parar(); return; }
      if (passo >= CENARIOS[cen].passos.length - 1) passo = -1;
      bPlay.textContent = "❚❚ Pausar";
      avancar();
      play = setInterval(function () { if (!avancar()) parar(); }, reduzido ? 1500 : 3200);
    });

    corpo.appendChild(svg); corpo.appendChild(info);
    raiz.appendChild(topo); raiz.appendChild(corpo);
    var inicial = parseInt(raiz.dataset.cenario || "1", 10);
    escolher(isNaN(inicial) ? 1 : inicial);
    var passoInicial = parseInt(raiz.dataset.passo || "-1", 10);
    while (passo < passoInicial && avancar()) {}
  }

  /* ---------- Contadores, revelação, cartões, progresso ---------- */
  function contar(e) {
    var fim = parseInt(e.dataset.contar, 10), suf = e.dataset.sufixo || "";
    var fmt = function (v) { return v.toLocaleString("pt-BR") + suf; };
    if (reduzido) { e.textContent = fmt(fim); return; }
    var inicio = performance.now(), dur = 1200;
    (function quadro(agora) {
      var p = Math.min(1, (agora - inicio) / dur);
      e.textContent = fmt(Math.round(fim * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(quadro);
    })(inicio);
  }
  function revelar() {
    var alvos = document.querySelectorAll(".rm-revelar, .rm-linha-tempo, [data-contar]");
    var aoVer = function (e) {
      e.classList.add("rm-visivel");
      if (e.dataset.contar) contar(e);
      if (e.classList.contains("rm-linha-tempo")) {
        var etapas = e.querySelectorAll(".rm-etapa"), feitas = parseInt(e.dataset.concluidas || "0", 10);
        e.style.setProperty("--rm-progresso-fases", ((feitas - 0.5) / etapas.length * 100) + "%");
        etapas.forEach(function (s, k) { if (k < feitas) setTimeout(function () { s.classList.add("rm-feita"); }, reduzido ? 0 : 400 + k * 450); });
      }
    };
    if (!("IntersectionObserver" in window)) { alvos.forEach(aoVer); return; }
    var obs = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) { if (en.isIntersecting) { aoVer(en.target); obs.unobserve(en.target); } });
    }, { threshold: 0.2 });
    alvos.forEach(function (a) { obs.observe(a); });
  }
  function cartoes() {
    document.querySelectorAll(".rm-cartao").forEach(function (c) {
      c.addEventListener("mousemove", function (e) {
        var r = c.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        c.style.setProperty("--mx", x * 100 + "%"); c.style.setProperty("--my", y * 100 + "%");
        if (!reduzido) c.style.transform = "perspective(700px) rotateX(" + ((0.5 - y) * 6) + "deg) rotateY(" + ((x - 0.5) * 6) + "deg)";
      });
      c.addEventListener("mouseleave", function () { c.style.transform = ""; });
    });
  }
  function progressoLeitura() {
    if (document.querySelector(".rm-progresso")) return;
    var barra = el("div", "rm-progresso"); barra.setAttribute("aria-hidden", "true");
    document.body.appendChild(barra);
    function atualizar() {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      barra.style.transform = "scaleX(" + (h > 0 ? window.scrollY / h : 0) + ")";
    }
    window.addEventListener("scroll", atualizar, { passive: true }); atualizar();
  }

  function iniciar() {
    alvoDigitado = document.querySelector(".rm-digitando");
    montarFundo(document.querySelector(".rm-hero__painel"));
    montarDemoHero(document.querySelector(".rm-demo"));
    montarExplorador(document.getElementById("rm-explorador"));
    document.querySelectorAll(".rm-fluxo[data-fluxo]").forEach(montarFluxo);
    revelar(); cartoes(); progressoLeitura();
  }
  if (typeof document$ !== "undefined") document$.subscribe(iniciar);  // navegação instantânea do Material
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();

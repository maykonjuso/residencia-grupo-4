/* Perfil leve no navegador do RUmo (issue #66 · RF01, RF02 · RNF06).

   Quatro campos — trilha alimentar, grupo de subsídio, curso e semestre — guardados no
   localStorage da própria pessoa. Nada do perfil vai para o servidor: o servidor devolve
   dados iguais para todo mundo (tabela de preços, cardápio) e é aqui, no navegador, que a
   resposta vira "a sua".

   Uso no chat (Milton / portal do Grupo 09):

     import * as perfil from "./rumo-perfil.js";
     const api = perfil.criarCliente({ base: "https://<rumo-api>" });
     const r = await api.perguntar("quanto custa o almoço?");
     const minha = perfil.respostaDePreco(perfil.carregar(), await api.precos(), "quanto custa o almoço?");
     // minha?.texto -> "Almoço: R$ 4,50 — valor do Grupo II, o grupo salvo no seu perfil. [F04, p. 1]"

   Sem dependências e sem build: é um módulo ES que roda direto no navegador e no Node (testes).
*/

export const CHAVE = "rumo.perfil.v1";
export const EVENTO = "rumo:perfil";

export const TRILHAS = {
  padrao: "Padrão",
  ovolacto: "Ovolactovegetariano",
  vegano: "Vegetariano estrito",
};
export const GRUPOS = { I: "Grupo I", II: "Grupo II", III: "Grupo III", IV: "Grupo IV" };
export const CAMPOS = ["trilha", "grupo", "curso", "semestre"];
const REFEICAO_NOME = { cafe: "Café da manhã", almoco: "Almoço", jantar: "Jantar" };

/* ------------------------------------------------------------------ armazenamento */

function armazenamento(storage) {
  if (storage) return storage;
  try {
    return globalThis.localStorage || null;
  } catch (_) {
    return null; // modo privado / iframe sem storage: o perfil só não persiste
  }
}

/** Normaliza um campo. Valor inválido vira null (e é descartado ao salvar). */
export function validar(campo, valor) {
  if (valor === undefined || valor === null || valor === "") return null;
  const v = String(valor).trim();
  if (campo === "trilha") return Object.prototype.hasOwnProperty.call(TRILHAS, v) ? v : null;
  if (campo === "grupo") {
    const g = v.toUpperCase().replace(/^GRUPO\s+/, "");
    return Object.prototype.hasOwnProperty.call(GRUPOS, g) ? g : null;
  }
  if (campo === "curso") return v.slice(0, 60) || null;
  if (campo === "semestre") {
    const n = parseInt(v, 10);
    return n >= 1 && n <= 12 ? n : null;
  }
  return null;
}

/** Perfil salvo, só com campos válidos. Sem perfil (ou storage indisponível) → {}. */
export function carregar(storage) {
  const s = armazenamento(storage);
  if (!s) return {};
  let bruto;
  try {
    bruto = JSON.parse(s.getItem(CHAVE) || "{}");
  } catch (_) {
    return {}; // conteúdo corrompido: comporta-se como sem perfil
  }
  const perfil = {};
  for (const campo of CAMPOS) {
    const v = validar(campo, bruto[campo]);
    if (v !== null) perfil[campo] = v;
  }
  if (Array.isArray(bruto.recusou)) perfil.recusou = bruto.recusou.filter((c) => CAMPOS.includes(c));
  return perfil;
}

function avisar(perfil) {
  try {
    if (typeof globalThis.dispatchEvent === "function" && typeof CustomEvent === "function") {
      globalThis.dispatchEvent(new CustomEvent(EVENTO, { detail: perfil }));
    }
  } catch (_) { /* ambiente sem eventos (Node): ignora */ }
}

/** Mescla e salva. Campo com valor vazio/null é removido. Devolve o perfil resultante. */
export function salvar(parcial, storage) {
  const s = armazenamento(storage);
  const perfil = { ...carregar(s) };
  for (const campo of CAMPOS) {
    if (!(campo in parcial)) continue;
    const v = validar(campo, parcial[campo]);
    if (v === null) delete perfil[campo];
    else perfil[campo] = v;
  }
  if (Array.isArray(parcial.recusou)) perfil.recusou = [...new Set([...(perfil.recusou || []), ...parcial.recusou])];
  if (s) s.setItem(CHAVE, JSON.stringify(perfil));
  avisar(perfil);
  return perfil;
}

/** Apaga tudo: o sistema volta ao comportamento genérico. */
export function apagar(storage) {
  const s = armazenamento(storage);
  if (s) s.removeItem(CHAVE);
  avisar({});
}

/** Deve o Milton oferecer guardar este campo? (não tem valor e a pessoa não recusou) */
export function deveOferecer(perfil, campo) {
  return !perfil[campo] && !(perfil.recusou || []).includes(campo);
}

/* ------------------------------------------------------------------ preço */

const sem_acento = (t) => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function ehPerguntaDePreco(texto) {
  return /\b(quanto (custa|e|eh|fica|pago)|preco|precos|valor(es)?|custa|pagar|pago|tarifa)\b/.test(sem_acento(texto));
}

export function refeicaoDaPergunta(texto) {
  const t = sem_acento(texto);
  if (/\bcafe\b/.test(t)) return "cafe";
  if (/\balmoco\b/.test(t)) return "almoco";
  if (/\bjanta(r)?\b/.test(t)) return "jantar";
  return null;
}

export function formatarReais(valor) {
  return "R$ " + Number(valor).toFixed(2).replace(".", ",");
}

function citacao(fonte) {
  return fonte ? `[${fonte.doc_id}, p. ${fonte.pagina}]` : "";
}

/**
 * Resposta de preço personalizada, ou null quando deve valer a resposta genérica
 * (pergunta não é de preço, perfil sem grupo, ou grupo sem valor na base).
 * Sempre diz de qual grupo veio o número e cita a fonte.
 */
export function respostaDePreco(perfil, tabela, pergunta) {
  if (!perfil || !perfil.grupo || !ehPerguntaDePreco(pergunta)) return null;
  const doGrupo = tabela && tabela.grupos && tabela.grupos[perfil.grupo];
  if (!doGrupo) return null;
  const pedida = refeicaoDaPergunta(pergunta);
  const refeicoes = (pedida ? [pedida] : ["cafe", "almoco", "jantar"]).filter((r) => doGrupo[r]);
  if (!refeicoes.length) return null;

  const itens = refeicoes.map((r) => ({ refeicao: r, valor: doGrupo[r].valor, fonte: doGrupo[r].fonte }));
  const grupo = GRUPOS[perfil.grupo];
  const partes = itens.map((i) => `${REFEICAO_NOME[i.refeicao]}: ${i.valor === 0 ? "gratuito" : formatarReais(i.valor)}`);
  const fontes = [...new Set(itens.map((i) => citacao(i.fonte)))].join(" ");
  return {
    grupo: perfil.grupo,
    itens,
    texto: `${partes.join(" · ")} — valor do ${grupo}, o grupo salvo no seu perfil. ${fontes}`.trim(),
  };
}

/* ------------------------------------------------------------------ cardápio */

/**
 * Cópia do cardápio (JSON da #54) com a trilha da pessoa primeiro em cada compartimento
 * e marcada com destaque: true. Sem trilha no perfil → cópia sem mudança.
 */
export function ordenarCardapio(cardapio, trilha) {
  const copia = JSON.parse(JSON.stringify(cardapio));
  if (!trilha || !TRILHAS[trilha]) return copia;
  const peso = (o) => (o.trilha === trilha ? 0 : o.trilha === "todas" ? 1 : 2);
  for (const comp of copia.compartimentos || []) {
    const temTrilhas = comp.opcoes.some((o) => o.trilha !== "todas");
    comp.opcoes = comp.opcoes
      .map((o, i) => ({ o, i }))
      .sort((a, b) => peso(a.o) - peso(b.o) || a.i - b.i)
      .map(({ o }) => (temTrilhas && o.trilha === trilha ? { ...o, destaque: true } : o));
  }
  return copia;
}

/* ------------------------------------------------------------------ cliente da API */

/**
 * Corpo do POST /perguntar. Lista fechada de campos: o perfil nunca entra aqui,
 * nem o curso (que a API aceitaria). É o que garante o critério "nada vai para o servidor".
 */
export function corpoDaPergunta(pergunta, { data, campus = "gama" } = {}) {
  const contexto = { campus };
  if (data) contexto.data = data;
  return { pergunta: String(pergunta), contexto };
}

export function criarCliente({ base = "", token = "", fetch: f = globalThis.fetch } = {}) {
  const url = (caminho) => base.replace(/\/$/, "") + caminho;
  async function json(resp) {
    if (!resp.ok) throw new Error(`RUmo respondeu ${resp.status}`);
    return resp.json();
  }
  let precosCache = null;
  return {
    perguntar(pergunta, contexto) {
      const headers = { "Content-Type": "application/json" };
      if (token) headers.Authorization = "Bearer " + token;
      return f(url("/perguntar"), {
        method: "POST",
        headers,
        body: JSON.stringify(corpoDaPergunta(pergunta, contexto)),
      }).then(json);
    },
    precos() {
      if (!precosCache) precosCache = f(url("/precos")).then(json).catch((e) => { precosCache = null; throw e; });
      return precosCache;
    },
    cardapio(data, refeicao) {
      const q = new URLSearchParams({ data, refeicao });
      return f(url("/cardapio?" + q)).then(json);
    },
  };
}

/* ------------------------------------------------------------------ interface */

function el(tag, attrs = {}, filhos = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "texto") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const f of [].concat(filhos)) if (f) e.append(f);
  return e;
}

function resumo(perfil) {
  const partes = [];
  if (perfil.grupo) partes.push(GRUPOS[perfil.grupo]);
  if (perfil.trilha) partes.push(TRILHAS[perfil.trilha]);
  if (perfil.curso) partes.push(perfil.curso);
  if (perfil.semestre) partes.push(perfil.semestre + "º semestre");
  return partes.join(" · ");
}

/**
 * Faixa sempre visível com o perfil atual, botão de editar e de apagar.
 * (Risco da issue: perfil errado gera resposta errada com cara de certa.)
 */
export function montarPainel(alvo, { storage, aoMudar } = {}) {
  function desenhar(editando = false) {
    const perfil = carregar(storage);
    alvo.replaceChildren();
    alvo.classList.add("rumo-perfil");

    if (!editando) {
      const vazio = !resumo(perfil);
      alvo.append(
        el("span", { class: "rumo-perfil__rotulo", texto: "Seu perfil (só neste navegador): " }),
        el("strong", { "data-teste": "resumo", texto: vazio ? "nenhum — respostas genéricas" : resumo(perfil) }),
        el("button", { type: "button", texto: vazio ? "Preencher" : "Editar", onclick: () => desenhar(true) }),
        vazio ? null : el("button", {
          type: "button", "data-teste": "apagar", texto: "Apagar perfil",
          onclick: () => { apagar(storage); desenhar(); aoMudar && aoMudar({}); },
        }),
      );
      return;
    }

    const opcoes = (mapa, atual) => [el("option", { value: "", texto: "—" })].concat(
      Object.entries(mapa).map(([v, t]) => {
        const o = el("option", { value: v, texto: t });
        if (String(atual) === v) o.selected = true;
        return o;
      }));
    const grupo = el("select", { name: "grupo" }, opcoes(GRUPOS, perfil.grupo || ""));
    const trilha = el("select", { name: "trilha" }, opcoes(TRILHAS, perfil.trilha || ""));
    const curso = el("input", { name: "curso", maxlength: "60", placeholder: "ex.: Engenharia de Software" });
    curso.value = perfil.curso || "";
    const semestre = el("input", { name: "semestre", type: "number", min: "1", max: "12" });
    semestre.value = perfil.semestre || "";

    const form = el("form", {
      onsubmit: (ev) => {
        ev.preventDefault();
        const novo = salvar({ grupo: grupo.value, trilha: trilha.value, curso: curso.value, semestre: semestre.value }, storage);
        desenhar();
        aoMudar && aoMudar(novo);
      },
    }, [
      el("label", {}, ["Grupo de subsídio ", grupo]),
      el("label", {}, ["Trilha alimentar ", trilha]),
      el("label", {}, ["Curso ", curso]),
      el("label", {}, ["Semestre ", semestre]),
      el("button", { type: "submit", texto: "Salvar" }),
      el("button", { type: "button", texto: "Cancelar", onclick: () => desenhar() }),
    ]);
    alvo.append(form);
  }
  desenhar();
  globalThis.addEventListener && globalThis.addEventListener(EVENTO, () => desenhar());
  return { atualizar: () => desenhar() };
}

/**
 * "Quer que eu lembre seu grupo?" — oferecida no contexto, uma pergunta por vez.
 * Recusar grava a recusa (no próprio navegador) para não perguntar de novo.
 */
export function ofertaDeGrupo(alvo, { storage, aoEscolher } = {}) {
  const caixa = el("div", { class: "rumo-oferta", "data-teste": "oferta-grupo" }, [
    el("span", { texto: "Quer que eu lembre seu grupo? Assim, da próxima vez, respondo só o seu valor. " }),
  ]);
  for (const [g, nome] of Object.entries(GRUPOS)) {
    caixa.append(el("button", {
      type: "button", texto: nome,
      onclick: () => { const p = salvar({ grupo: g }, storage); caixa.remove(); aoEscolher && aoEscolher(p); },
    }));
  }
  caixa.append(el("button", {
    type: "button", texto: "Não, obrigado",
    onclick: () => { salvar({ recusou: ["grupo"] }, storage); caixa.remove(); },
  }));
  alvo.append(caixa);
  return caixa;
}

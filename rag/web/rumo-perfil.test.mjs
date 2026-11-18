// Critérios de aceite da issue #66 no módulo do navegador.
// Rodar:  cd rag && node --test web/
import { test } from "node:test";
import assert from "node:assert/strict";
import * as perfil from "./rumo-perfil.js";

function memoria() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    dump: () => [...m.values()].join(""),
  };
}

const fonte = { doc_id: "F04", pagina: 1, chunk_id: "F04-0002" };
const TABELA = {
  grupos: {
    I: { cafe: { valor: 0, fonte }, almoco: { valor: 0, fonte }, jantar: { valor: 0, fonte } },
    II: { cafe: { valor: 2, fonte }, almoco: { valor: 4.5, fonte }, jantar: { valor: 4.5, fonte } },
    III: { cafe: { valor: 7.05, fonte }, almoco: { valor: 15.2, fonte }, jantar: { valor: 15.2, fonte } },
    IV: { cafe: { valor: 1.5, fonte }, almoco: { valor: 2.5, fonte }, jantar: { valor: 2.5, fonte } },
  },
};

const CARDAPIO = {
  unidade: "gama", data: "2026-11-09", refeicao: "almoco",
  compartimentos: [
    { slot: "salada", titulo: "Salada", max: 2, opcoes: [
      { id: "alface-roxa", nome: "Alface roxa", trilha: "todas" },
      { id: "caponata", nome: "Caponata de berinjela", trilha: "todas" }] },
    { slot: "principal", titulo: "Prato principal", max: 1, opcoes: [
      { id: "carne", nome: "Carne ao molho de vinho", trilha: "padrao" },
      { id: "berinjela", nome: "Berinjela recheada", trilha: "ovolacto" },
      { id: "soja", nome: "Soja refogada com legumes", trilha: "vegano" }] },
  ],
  fonte: { doc_id: "F09", pagina: 2 },
};

test("com Grupo II salvo, 'quanto custa o almoço?' responde R$ 4,50 e diz o grupo", () => {
  const s = memoria();
  perfil.salvar({ grupo: "II" }, s);
  const r = perfil.respostaDePreco(perfil.carregar(s), TABELA, "quanto custa o almoço?");
  assert.match(r.texto, /R\$ 4,50/);
  assert.match(r.texto, /Grupo II/);
  assert.match(r.texto, /\[F04, p\. 1\]/); // continua citando a fonte (RF03)
  assert.equal(r.itens.length, 1);
  assert.doesNotMatch(r.texto, /15,20|2,50/); // não devolve a tabela dos outros grupos
});

test("preço sem refeição na pergunta devolve as três do grupo, só do grupo", () => {
  const r = perfil.respostaDePreco({ grupo: "III" }, TABELA, "qual o preço do RU?");
  assert.equal(r.itens.length, 3);
  assert.match(r.texto, /Café da manhã: R\$ 7,05 · Almoço: R\$ 15,20 · Jantar: R\$ 15,20/);
});

test("Grupo I aparece como gratuito", () => {
  const r = perfil.respostaDePreco({ grupo: "I" }, TABELA, "quanto pago no jantar?");
  assert.match(r.texto, /Jantar: gratuito — valor do Grupo I/);
});

test("sem grupo, ou pergunta que não é de preço, vale a resposta genérica", () => {
  assert.equal(perfil.respostaDePreco({}, TABELA, "quanto custa o almoço?"), null);
  assert.equal(perfil.respostaDePreco({ grupo: "II" }, TABELA, "qual o cardápio de hoje?"), null);
});

test("com trilha vegana, o cardápio destaca a opção vegana e a põe primeiro", () => {
  const c = perfil.ordenarCardapio(CARDAPIO, "vegano");
  const principal = c.compartimentos[1].opcoes;
  assert.equal(principal[0].id, "soja");
  assert.equal(principal[0].destaque, true);
  assert.equal(principal.filter((o) => o.destaque).length, 1);
  assert.ok(c.compartimentos[0].opcoes.every((o) => !o.destaque)); // salada é de todas: nada a destacar
  assert.equal(CARDAPIO.compartimentos[1].opcoes[0].id, "carne"); // não altera o original
});

test("apagar o perfil devolve o comportamento genérico", () => {
  const s = memoria();
  perfil.salvar({ grupo: "II", trilha: "vegano", curso: "Engenharia de Software", semestre: 5 }, s);
  perfil.apagar(s);
  assert.deepEqual(perfil.carregar(s), {});
  assert.equal(perfil.respostaDePreco(perfil.carregar(s), TABELA, "quanto custa o almoço?"), null);
  assert.deepEqual(perfil.ordenarCardapio(CARDAPIO, perfil.carregar(s).trilha), CARDAPIO);
});

test("nada do perfil vai para o servidor", async () => {
  const s = memoria();
  perfil.salvar({ grupo: "II", trilha: "vegano", curso: "Engenharia de Software", semestre: 5 }, s);
  const enviados = [];
  const fetchFalso = async (url, opcoes = {}) => {
    enviados.push(String(url) + " " + (opcoes.body || "") + " " + JSON.stringify(opcoes.headers || {}));
    const corpo = String(url).includes("/precos") ? TABELA : String(url).includes("/cardapio") ? CARDAPIO : { resposta: "ok", fontes: [] };
    return { ok: true, status: 200, json: async () => corpo };
  };
  const api = perfil.criarCliente({ base: "https://rumo.exemplo", fetch: fetchFalso });
  await api.perguntar("quanto custa o almoço?", { data: "2026-11-09" });
  await api.precos();
  await api.cardapio("2026-11-09", "almoco");

  assert.equal(enviados.length, 3);
  const tudo = enviados.join("\n");
  for (const proibido of ["Grupo II", '"II"', "grupo", "vegano", "trilha", "Engenharia de Software", "curso", "semestre"]) {
    assert.ok(!tudo.includes(proibido), `vazou "${proibido}" para o servidor:\n${tudo}`);
  }
  assert.deepEqual(perfil.corpoDaPergunta("x", { data: "2026-11-09" }), { pergunta: "x", contexto: { campus: "gama", data: "2026-11-09" } });
});

test("valores inválidos ou storage corrompido não quebram", () => {
  const s = memoria();
  perfil.salvar({ grupo: "V", trilha: "carnivoro", semestre: 99, curso: "" }, s);
  assert.deepEqual(perfil.carregar(s), {});
  s.setItem(perfil.CHAVE, "{isso não é json");
  assert.deepEqual(perfil.carregar(s), {});
  assert.equal(perfil.validar("grupo", "grupo ii"), "II");
});

test("recusar a oferta faz o Milton não perguntar de novo", () => {
  const s = memoria();
  assert.equal(perfil.deveOferecer(perfil.carregar(s), "grupo"), true);
  perfil.salvar({ recusou: ["grupo"] }, s);
  assert.equal(perfil.deveOferecer(perfil.carregar(s), "grupo"), false);
  perfil.salvar({ grupo: "IV" }, s);
  assert.equal(perfil.deveOferecer(perfil.carregar(s), "grupo"), false);
});

test("detecção de pergunta de preço e de refeição", () => {
  for (const p of ["quanto custa o almoço?", "qual o preço do café?", "valor do jantar", "Quanto é o RU?"]) {
    assert.ok(perfil.ehPerguntaDePreco(p), p);
  }
  assert.ok(!perfil.ehPerguntaDePreco("qual o cardápio de hoje?"));
  assert.equal(perfil.refeicaoDaPergunta("preço do CAFÉ da manhã"), "cafe");
  assert.equal(perfil.refeicaoDaPergunta("e a janta?"), "jantar");
});

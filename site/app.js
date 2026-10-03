"use strict";
/* Painel do acervo das Comissões da CMSP. Dados em dados/serie-<grupo>.json (gerados por
   `python -m painel`): uma lista de datas e, por comissão, uma lista por métrica. */

const COMISSOES = [
  ["TODAS", "Todas as comissões"],
  ["CCJ", "Constituição, Justiça e Legislação Participativa"],
  ["FIN", "Finanças e Orçamento"],
  ["URB", "Política Urbana, Metropolitana e Meio Ambiente"],
  ["ADM", "Administração Pública"],
  ["ECON", "Trânsito, Transporte e Atividade Econômica"],
  ["EDUC", "Educação, Cultura e Esportes"],
  ["SAUDE", "Saúde, Promoção Social, Trabalho e Mulher"],
];
const PERIODOS = [
  ["tudo", "Desde nov/2018"],
  ["legislatura", "Legislatura atual (desde 2025)"],
  ["12m", "Últimos 12 meses"],
  ["90d", "Últimos 90 dias"],
];
const GRUPOS = [
  ["projetos", "Projetos (PL, PDL, PR e PLO)"],
  ["todas", "Todas as matérias"],
];
const LEGISLATURAS = ["2021-01-01", "2025-01-01"];

// Empilhamentos: da base para o topo. As cores são variáveis do CSS (claro e escuro).
const IDADE = [
  { campos: ["idade_mais365"], nome: "Mais de 1 ano", cor: "--idade-5" },
  { campos: ["idade_181a365"], nome: "181 a 365 dias", cor: "--idade-4" },
  { campos: ["idade_91a180"], nome: "91 a 180 dias", cor: "--idade-3" },
  { campos: ["idade_31a90"], nome: "31 a 90 dias", cor: "--idade-2" },
  { campos: ["idade_ate30"], nome: "Até 30 dias", cor: "--idade-1" },
  { campos: ["pendentes"], nome: "Aguardando recebimento", cor: "--cinza-1" },
  { campos: ["idade_desconhecida"], nome: "Idade desconhecida", cor: "--cinza-2" },
];
const PASSO = [
  { campos: ["passo_relator"], nome: "Com o relator", cor: "--s1" },
  { campos: ["passo_secretaria"], nome: "Secretaria", cor: "--s2" },
  { campos: ["passo_procuradoria"], nome: "Procuradoria", cor: "--s3" },
  { campos: ["passo_presidente"], nome: "Presidente da comissão", cor: "--s4" },
  { campos: ["passo_consultoria"], nome: "Consultoria", cor: "--s5" },
  { campos: ["passo_outro", "passo_nenhum", "passo_desconhecido"], nome: "Outros ou sem passo", cor: "--cinza-1" },
];

const DIA = 864e5;
const MARGEM_DIREITA = 56;  // igual em todos os cartões, para os eixos de tempo se alinharem
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const numero = new Intl.NumberFormat("pt-BR");
const fmt = (v) => (v == null ? "—" : numero.format(v));
const dataBR = (d) => `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}/${d.getUTCFullYear()}`;
const dataISO = (d) => d.toISOString().slice(0, 10);
const utc = (iso) => new Date(`${iso}T00:00:00Z`);

const estado = { aba: "evolucao", periodo: "tudo", comissao: "TODAS", grupo: "projetos" };
const cache = {};
let ultimaLargura = 0;

// ----------------------------------------------------------------------------- utilidades
function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto != null) e.textContent = texto;
  return e;
}

function cores() {
  const s = getComputedStyle(document.documentElement);
  const v = (n) => s.getPropertyValue(n).trim();
  return { v, superficie: v("--superficie"), tinta: v("--tinta"), tinta2: v("--tinta-2"),
           tinta3: v("--tinta-3"), grade: v("--grade"), base: v("--base"), s1: v("--s1") };
}

function soma(serie, campos, i) {
  let t = 0;
  for (const c of campos) {
    const v = serie[c][i];
    if (v == null) return null;
    t += v;
  }
  return t;
}

async function carregar(grupo) {
  if (!cache[grupo]) {
    const r = await fetch(`dados/serie-${grupo}.json`);
    if (!r.ok) throw new Error(`não foi possível carregar dados/serie-${grupo}.json (${r.status})`);
    const j = await r.json();
    j.datasObj = j.datas.map(utc);
    cache[grupo] = j;
  }
  return cache[grupo];
}

function intervalo(datas) {
  const ultimo = datas[datas.length - 1];
  let inicio = datas[0];
  if (estado.periodo === "legislatura") inicio = utc("2025-01-01");
  if (estado.periodo === "12m") inicio = new Date(ultimo - 365 * DIA);
  if (estado.periodo === "90d") inicio = new Date(ultimo - 90 * DIA);
  return [Math.max(0, d3.bisectLeft(datas, inicio)), datas.length];
}

// ----------------------------------------------------------------------------- eixos e marcas
function eixoX(datas, largura) {
  const anos = (datas[datas.length - 1] - datas[0]) / (365 * DIA);
  const cabem = Math.max(2, Math.floor(largura / 80));
  if (anos > 2) {
    const passo = Math.ceil(anos / cabem);
    return { ticks: d3.utcYear.every(passo), tickFormat: (d) => String(d.getUTCFullYear()) };
  }
  const meses = Math.max(1, Math.ceil((anos * 12) / cabem));
  return { ticks: d3.utcMonth.every(meses),
           tickFormat: (d) => `${MESES[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}` };
}

function marcos(datas, c, inicioColeta) {
  const [d0, d1] = [datas[0], datas[datas.length - 1]];
  const lista = LEGISLATURAS.map((iso) => ({ d: utc(iso), texto: "nova legislatura" }));
  lista.push({ d: utc(inicioColeta), texto: "início da coleta diária" });
  const visiveis = lista.filter((m) => m.d > d0 && m.d <= d1);
  const perto = (m) => (d1 - m.d) / (d1 - d0) < 0.15;  // texto à esquerda da linha, no fim do eixo
  return [
    Plot.ruleX(visiveis, { x: "d", stroke: c.tinta3, strokeOpacity: 0.7 }),
    Plot.text(visiveis.filter((m) => !perto(m)), { x: "d", text: "texto", frameAnchor: "top",
      textAnchor: "start", dx: 4, dy: -12, fill: c.tinta2, fontSize: 11 }),
    Plot.text(visiveis.filter(perto), { x: "d", text: "texto", frameAnchor: "top",
      textAnchor: "end", dx: -4, dy: -12, fill: c.tinta2, fontSize: 11 }),
  ];
}

function moldura(c, datas, largura, altura, extra) {
  const x = eixoX(datas, largura);
  const opcoes = {
    width: largura, height: altura, marginTop: 22, marginRight: extra.marginRight ?? 16,
    marginBottom: 26, marginLeft: extra.marginLeft ?? 48,
    style: { fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
             fontSize: "12px", background: "transparent", color: c.tinta3, overflow: "visible" },
    x: { type: "utc", domain: [datas[0], datas[datas.length - 1]] },
    y: { domain: extra.yDomain, nice: true, zero: true },
  };
  const eixos = [
    Plot.gridY({ ticks: extra.yTicks ?? 5, stroke: c.grade, strokeOpacity: 1 }),
    Plot.axisY({ ticks: extra.yTicks ?? 5, tickSize: 0, tickPadding: 6, tickFormat: (v) => numero.format(v),
                 fill: c.tinta3, label: null }),
    Plot.axisX({ ticks: x.ticks, tickFormat: x.tickFormat, tickSize: 0, tickPadding: 8,
                 fill: c.tinta3, label: null }),
    Plot.ruleY([0], { stroke: c.base }),
  ];
  return { opcoes, eixos };
}

// ----------------------------------------------------------------------------- cursor e dica
function interagir(alvo, svg, datas, conteudo) {
  alvo.ouvintes?.abort();  // cada redesenho troca os ouvintes do anterior
  alvo.ouvintes = new AbortController();
  const { signal } = alvo.ouvintes;
  const x = svg.scale("x");
  const y = svg.scale("y");
  const cursor = el("div", "cursor");
  const dica = el("div", "dica");
  cursor.hidden = dica.hidden = true;
  alvo.append(cursor, dica);
  const perto = d3.bisector((d) => d).center;
  let atual = null;

  function mostrar(i) {
    atual = i;
    const k = svg.getBoundingClientRect().width / svg.width.baseVal.value;
    const px = x.apply(datas[i]) * k;
    const [yb, yt] = y.range;
    cursor.hidden = false;
    cursor.style.left = `${px}px`;
    cursor.style.top = `${yt * k}px`;
    cursor.style.height = `${(yb - yt) * k}px`;

    const { linhas, total } = conteudo(i);
    dica.replaceChildren(el("p", "data", dataBR(datas[i])));
    for (const l of linhas) {
      const linha = el("div", "linha");
      if (l.cor) {
        const chave = el("span", "chave");
        chave.style.background = l.cor;
        linha.append(chave);
      }
      linha.append(el("strong", null, l.valor), el("span", "nome", l.nome));
      dica.append(linha);
    }
    if (total) {
      const linha = el("div", "linha total");
      linha.append(el("strong", null, total.valor), el("span", "nome", total.nome));
      dica.append(linha);
    }
    dica.hidden = false;
    const largura = alvo.clientWidth;
    const w = dica.offsetWidth;
    dica.style.left = `${px + 12 + w > largura ? Math.max(0, px - 12 - w) : px + 12}px`;
    dica.style.top = `${Math.max(0, yt * k)}px`;
  }
  function esconder() {
    cursor.hidden = dica.hidden = true;
  }

  alvo.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect();
    const k = r.width / svg.width.baseVal.value;
    const px = (ev.clientX - r.left) / k;
    const [x0, x1] = x.range;
    if (px < x0 - 8 || px > x1 + 8) return esconder();
    mostrar(perto(datas, x.invert(px)));
  }, { signal });
  alvo.addEventListener("pointerleave", esconder, { signal });
  alvo.addEventListener("focus", () => mostrar(atual ?? datas.length - 1), { signal });
  alvo.addEventListener("blur", esconder, { signal });
  alvo.addEventListener("keydown", (ev) => {
    const passo = ev.shiftKey ? 30 : 1;
    if (ev.key === "ArrowLeft") mostrar(Math.max(0, (atual ?? datas.length - 1) - passo));
    else if (ev.key === "ArrowRight") mostrar(Math.min(datas.length - 1, (atual ?? 0) + passo));
    else if (ev.key === "Home") mostrar(0);
    else if (ev.key === "End") mostrar(datas.length - 1);
    else return;
    ev.preventDefault();
  }, { signal });
}

function descrever(svg, texto) {
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", texto);
}

// ----------------------------------------------------------------------------- tabela e CSV
function acoes(cartao, datas, colunas, arquivo) {
  const caixa = cartao.querySelector(".acoes");
  if (!caixa) return;
  const grafico = cartao.querySelector(".grafico");
  const aberta = cartao.dataset.tabela === "1";
  const botaoTabela = el("button", "botao", aberta ? "Ver gráfico" : "Ver tabela");
  botaoTabela.type = "button";
  botaoTabela.setAttribute("aria-pressed", String(aberta));
  botaoTabela.addEventListener("click", () => {
    cartao.dataset.tabela = aberta ? "" : "1";
    render();
  });
  const botaoCsv = el("button", "botao", "Baixar CSV");
  botaoCsv.type = "button";
  botaoCsv.addEventListener("click", () => baixarCsv(datas, colunas, arquivo));
  caixa.replaceChildren(botaoTabela, botaoCsv);

  cartao.querySelector(".tabela")?.remove();
  for (const e of cartao.querySelectorAll(".legenda, .grafico")) e.hidden = aberta;
  if (!aberta) return;
  // Um dia por mês (o primeiro do mês dentro do período) e o último dia.
  const indices = [];
  datas.forEach((d, i) => {
    if (i === 0 || d.getUTCMonth() !== datas[i - 1].getUTCMonth()) indices.push(i);
  });
  if (indices[indices.length - 1] !== datas.length - 1) indices.push(datas.length - 1);
  const tabela = el("table");
  const cab = el("tr");
  cab.append(el("th", null, "Data"), ...colunas.map((c) => el("th", null, c.nome)));
  tabela.append(el("thead"), el("tbody"));
  tabela.tHead.append(cab);
  for (const i of indices.reverse()) {
    const tr = el("tr");
    tr.append(el("td", null, dataBR(datas[i])), ...colunas.map((c) => el("td", null, fmt(c.valores[i]))));
    tabela.tBodies[0].append(tr);
  }
  const caixaTabela = el("div", "tabela");
  caixaTabela.append(tabela);
  grafico.after(caixaTabela);
}

function baixarCsv(datas, colunas, arquivo) {
  const aspas = (s) => `"${String(s).replace(/"/g, '""')}"`;
  const linhas = [["data", ...colunas.map((c) => c.nome)].map(aspas).join(",")];
  datas.forEach((d, i) => linhas.push([dataISO(d), ...colunas.map((c) => c.valores[i] ?? "")].join(",")));
  const blob = new Blob([linhas.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
  const a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = arquivo;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// ----------------------------------------------------------------------------- gráficos
function graficoLinha(alvo, datas, valores, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const pontos = datas.map((d, i) => ({ d, v: valores[i] })).filter((p) => p.v != null);
  const ultimo = pontos.slice(-1);
  const m = moldura(c, datas, largura, opcoes.altura, { marginRight: opcoes.marginRight ?? MARGEM_DIREITA,
    marginLeft: opcoes.marginLeft, yTicks: opcoes.yTicks });
  const svg = Plot.plot({
    ...m.opcoes,
    marks: [
      ...m.eixos,
      ...(opcoes.marcos ? marcos(datas, c, opcoes.inicioColeta) : []),
      ...(opcoes.area ? [Plot.areaY(pontos, { x: "d", y: "v", fill: c.s1, fillOpacity: 0.1 })] : []),
      Plot.lineY(pontos, { x: "d", y: "v", stroke: c.s1, strokeWidth: 2, strokeLinejoin: "round", strokeLinecap: "round" }),
      Plot.dot(ultimo, { x: "d", y: "v", r: 4, fill: c.s1, stroke: c.superficie, strokeWidth: 2 }),
      ...(opcoes.rotuloFinal ? [Plot.text(ultimo, { x: "d", y: "v", text: (p) => fmt(p.v), dx: 8,
                                                   textAnchor: "start", fill: c.tinta, fontWeight: 600 })] : []),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, datas, (i) => ({
    linhas: [{ cor: c.s1, valor: opcoes.formato(valores[i]), nome: opcoes.nome }],
  }));
}

function graficoEmpilhado(alvo, datas, camadas, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const nomes = camadas.map((k) => k.nome);
  const longo = [];
  for (const k of camadas) {
    k.valores.forEach((v, i) => { if (v != null) longo.push({ d: datas[i], v, k: k.nome }); });
  }
  const totais = datas.map((_, i) => camadas.reduce((t, k) => t + (k.valores[i] ?? 0), 0));
  const m = moldura(c, datas, largura, opcoes.altura,
                    { yDomain: [0, d3.max(totais) || 1], marginRight: MARGEM_DIREITA });
  const svg = Plot.plot({
    ...m.opcoes,
    color: { domain: nomes, range: camadas.map((k) => c.v(k.cor)) },
    marks: [
      ...m.eixos,
      Plot.areaY(longo, { x: "d", y: "v", fill: "k", z: "k", order: nomes, stroke: c.superficie, strokeWidth: 1 }),
      ...marcos(datas, c, opcoes.inicioColeta),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, datas, (i) => ({
    // Na dica, de cima para baixo, como no gráfico.
    linhas: [...camadas].reverse().map((k) => ({ cor: c.v(k.cor), valor: fmt(k.valores[i]), nome: k.nome })),
    total: { valor: fmt(totais[i]), nome: "no total" },
  }));
}

function legenda(cartao, camadas) {
  const c = cores();
  const ul = cartao.querySelector(".legenda");
  ul.replaceChildren(...camadas.map((k) => {
    const li = el("li");
    const amostra = el("span", "amostra");
    amostra.style.background = c.v(k.cor);
    li.append(amostra, document.createTextNode(k.nome));
    return li;
  }));
}

// ----------------------------------------------------------------------------- painel
function renderKpis(j, serie) {
  const u = j.datas.length - 1;
  const hoje = j.datasObj[u];
  const total = serie.materias[u];
  const iAno = d3.bisectLeft(j.datasObj, new Date(hoje - 365 * DIA));
  const antes = iAno < u ? serie.materias[iAno] : null;
  const recebidas = total - serie.pendentes[u] - (serie.idade_desconhecida[u] ?? 0);
  const velhas = serie.idade_mais365[u];
  const variacao = antes == null ? "" :
    `${total - antes >= 0 ? "+" : "−"}${fmt(Math.abs(total - antes))} em 12 meses (eram ${fmt(antes)})`;
  const itens = [
    { rotulo: `Matérias no acervo em ${dataBR(hoje)}`, valor: fmt(total), nota: variacao, heroi: true },
    { rotulo: "Há mais de 1 ano na comissão", valor: fmt(velhas),
      nota: recebidas ? `${Math.round((100 * velhas) / recebidas)}% das já recebidas` : "" },
    { rotulo: "Idade mediana", valor: serie.mediana_dias[u] == null ? "—" : `${fmt(serie.mediana_dias[u])} dias`,
      nota: "das matérias já recebidas" },
    { rotulo: "Sem relator", valor: fmt(serie.sem_relator[u]), nota: "segundo o retrato do dia" },
    { rotulo: "Aguardando recebimento", valor: fmt(serie.pendentes[u]), nota: "enviadas e ainda não recebidas" },
  ];
  document.getElementById("kpis").replaceChildren(...itens.map((k) => {
    const div = el("div", k.heroi ? "kpi heroi" : "kpi");
    div.append(el("p", "rotulo", k.rotulo), el("p", "valor", k.valor));
    if (k.nota) div.append(el("p", "nota", k.nota));
    return div;
  }));
}

function resumo(nome, datas, valores) {
  const pares = datas.map((d, i) => [d, valores[i]]).filter(([, v]) => v != null);
  if (!pares.length) return nome;
  const [d0, v0] = pares[0];
  const [d1, v1] = pares[pares.length - 1];
  const [dMin, vMin] = pares.reduce((a, b) => (b[1] < a[1] ? b : a));
  const [dMax, vMax] = pares.reduce((a, b) => (b[1] > a[1] ? b : a));
  return `${nome}: ${fmt(v0)} em ${dataBR(d0)} e ${fmt(v1)} em ${dataBR(d1)}; ` +
         `mínimo de ${fmt(vMin)} em ${dataBR(dMin)} e máximo de ${fmt(vMax)} em ${dataBR(dMax)}.`;
}

function renderMultiplos(j, i0, i1) {
  const cartao = document.getElementById("c-comissoes");
  cartao.hidden = estado.comissao !== "TODAS";
  if (cartao.hidden) return;
  const datas = j.datasObj.slice(i0, i1);
  const caixa = cartao.querySelector(".multiplos");
  caixa.replaceChildren();
  for (const [sigla, nome] of COMISSOES.slice(1)) {
    const valores = j.comissoes[sigla].materias.slice(i0, i1);
    const mini = el("div", "mini");
    mini.tabIndex = 0;
    mini.setAttribute("role", "button");
    mini.setAttribute("aria-label", `Ver ${nome} em detalhe`);
    const topo = el("div", "mini-topo");
    const h3 = el("h3", null, `${sigla} `);
    h3.append(el("span", null, nome.split(",")[0]));
    topo.append(h3, el("span", "valor-mini", fmt(valores[valores.length - 1])));
    const grafico = el("div", "grafico");
    mini.append(topo, grafico);
    caixa.append(mini);
    const escolher = () => { estado.comissao = sigla; sincronizar(); render(); window.scrollTo({ top: 0, behavior: "smooth" }); };
    mini.addEventListener("click", escolher);
    mini.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); escolher(); } });
    graficoLinha(grafico, datas, valores, { altura: 120, area: true, yTicks: 3, marginLeft: 40, marginRight: 12,
      nome: "matérias",
      formato: fmt, descricao: resumo(`Acervo da ${sigla}`, datas, valores) });
  }
}

function renderEvolucao(j, serie) {
  const [i0, i1] = intervalo(j.datasObj);
  const datas = j.datasObj.slice(i0, i1);
  const fatia = (campo) => serie[campo].slice(i0, i1);
  const nomeComissao = estado.comissao === "TODAS" ? "das 7 comissões" : `da ${estado.comissao}`;
  const nomeGrupo = estado.grupo === "projetos" ? "Projetos" : "Matérias";
  const arquivo = (tema) => `acervo-${tema}-${estado.comissao.toLowerCase()}-${estado.grupo}.csv`;

  // Tamanho do acervo
  const cAcervo = document.getElementById("c-acervo");
  document.getElementById("sub-acervo").textContent =
    `${nomeGrupo} em análise ${nomeComissao} no fim de cada dia.`;
  const materias = fatia("materias");
  acoes(cAcervo, datas, [{ nome: "matérias", valores: materias }], arquivo("tamanho"));
  if (cAcervo.dataset.tabela !== "1") {
    graficoLinha(cAcervo.querySelector(".grafico"), datas, materias, {
      altura: 300, area: true, marcos: true, rotuloFinal: true, inicioColeta: j.inicio_coleta,
      nome: "matérias", formato: fmt, descricao: resumo(`${nomeGrupo} em análise ${nomeComissao}`, datas, materias) });
  }

  renderMultiplos(j, i0, i1);

  // Idade
  const cIdade = document.getElementById("c-idade");
  const camadasIdade = IDADE.map((k) => ({ ...k, valores: datas.map((_, i) => soma(serie, k.campos, i0 + i)) }))
    .filter((k) => k.valores.some((v) => v));
  legenda(cIdade, camadasIdade);
  acoes(cIdade, datas, camadasIdade, arquivo("idade"));
  if (cIdade.dataset.tabela !== "1") {
    graficoEmpilhado(cIdade.querySelector(".grafico"), datas, camadasIdade, {
      altura: 300, inicioColeta: j.inicio_coleta,
      descricao: `Idade das matérias ${nomeComissao}, empilhada por faixa. ` + resumo("Mais de 1 ano", datas, camadasIdade[0].valores) });
  }

  // Mediana
  const cMediana = document.getElementById("c-mediana");
  const mediana = fatia("mediana_dias");
  acoes(cMediana, datas, [{ nome: "idade mediana (dias)", valores: mediana }], arquivo("mediana"));
  if (cMediana.dataset.tabela !== "1") {
    graficoLinha(cMediana.querySelector(".grafico"), datas, mediana, {
      altura: 220, marcos: true, rotuloFinal: true, inicioColeta: j.inicio_coleta, nome: "dias",
      formato: (v) => (v == null ? "—" : `${fmt(v)}`), descricao: resumo(`Idade mediana, em dias, ${nomeComissao}`, datas, mediana) });
  }

  // Passo interno
  const cPasso = document.getElementById("c-passo");
  const camadasPasso = PASSO.map((k) => ({ ...k, valores: datas.map((_, i) => soma(serie, k.campos, i0 + i)) }));
  legenda(cPasso, camadasPasso);
  acoes(cPasso, datas, camadasPasso, arquivo("passo"));
  if (cPasso.dataset.tabela !== "1") {
    graficoEmpilhado(cPasso.querySelector(".grafico"), datas, camadasPasso, {
      altura: 300, inicioColeta: j.inicio_coleta,
      descricao: `Matérias ${nomeComissao} pela área do passo interno. ` + resumo("Com o relator", datas, camadasPasso[0].valores) });
  }
}

function mostrarErro(texto) {
  let caixa = document.getElementById("erro");
  if (!caixa) {
    caixa = el("p", "erro");
    caixa.id = "erro";
    document.getElementById("conteudo").prepend(caixa);
  }
  caixa.textContent = texto;
  caixa.hidden = !texto;
}

function mostrarAba() {
  const retrato = estado.aba === "retrato";
  document.getElementById("aba-evolucao").setAttribute("aria-selected", String(!retrato));
  document.getElementById("aba-retrato").setAttribute("aria-selected", String(retrato));
  document.getElementById("painel-evolucao").hidden = retrato;
  document.getElementById("painel-retrato").hidden = !retrato;
  document.getElementById("filtro-periodo").hidden = retrato;  // o retrato é sempre do último dia
}

async function render() {
  const conteudo = document.getElementById("conteudo");
  conteudo.classList.add("carregando");
  let j;
  try {
    j = await carregar(estado.grupo);
    if (estado.aba === "retrato") await carregarRetrato();
  } catch (e) {
    conteudo.classList.remove("carregando");
    mostrarErro(`Erro ao carregar os dados: ${e.message}`);
    return;
  }
  mostrarErro("");
  conteudo.classList.remove("carregando");
  ultimaLargura = conteudo.clientWidth;
  const serie = j.comissoes[estado.comissao];

  const coletado = new Date(j.atualizado_em);
  document.getElementById("atualizacao").textContent =
    `Última coleta em ${coletado.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" })} às ` +
    `${coletado.toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" })}`;

  renderKpis(j, serie);
  mostrarAba();
  if (estado.aba === "retrato") renderRetrato();
  else renderEvolucao(j, serie);
}

// ----------------------------------------------------------------------------- retrato do dia
const SPLEGIS = "https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/DetailsMateriaTramitacaoLegislativa/";
// Faixas de tempo, da base da barra para a ponta (as mesmas da evolução).
const FAIXAS_TEMPO = [
  { chave: "mais365", nome: "Mais de 1 ano", cor: "--idade-5", min: 366 },
  { chave: "181a365", nome: "181 a 365 dias", cor: "--idade-4", min: 181 },
  { chave: "91a180", nome: "91 a 180 dias", cor: "--idade-3", min: 91 },
  { chave: "31a90", nome: "31 a 90 dias", cor: "--idade-2", min: 31 },
  { chave: "ate30", nome: "Até 30 dias", cor: "--idade-1", min: 0 },
];
const AGUARDANDO = { chave: "aguardando", nome: "Aguardando recebimento", cor: "--cinza-1" };
const SEM_PASSO = { chave: "sempasso", nome: "Sem passo interno", cor: "--cinza-2" };
const PRIMEIRAS = 15;  // linhas visíveis antes de "Mostrar todos"

const retrato = {
  dados: null,
  recorte: null,  // { dim, chave, nome, faixa, nomeFaixa }
  modos: { "r-relator": "total", "r-passo": "total", "r-autoria": "total" },
  agrupar: "autor",
  busca: "",
  todos: new Set(),
  ordem: { campo: "dc", desc: true },
  limite: 50,
};

// Como cada visão agrupa as matérias e qual tempo usa nas faixas.
const DIMENSOES = {
  relator: {
    chaves: (m) => [m.rel ?? -1],
    nome: (k, d) => (k === -1 ? ["Sem relator", "", true] : [d.pessoas[k][0], d.pessoas[k][1], false]),
    dias: (m) => m.dc, semDado: AGUARDANDO, fixar: -1,
  },
  passo: {
    chaves: (m) => [m.pt || ""],
    nome: (k) => (k === "" ? ["Sem passo interno", "", true] : [k, "", false]),
    dias: (m) => m.dp, semDado: SEM_PASSO,
  },
  autor: {
    chaves: (m) => (m.a.length ? m.a : [-1]),
    nome: (k, d) => {
      if (k === -1) return ["Sem autoria informada", "", true];
      const [nome, grupo] = d.pessoas[k];
      return [nome, grupo === nome || grupo === "Outros" ? "" : grupo, false];
    },
    dias: (m) => m.dc, semDado: AGUARDANDO,
  },
  partido: {
    chaves: (m) => (m.a.length ? [...new Set(m.a.map((a) => retrato.dados.pessoas[a][1]))] : ["—"]),
    nome: (k) => [k, "", k === "Outros" || k === "—"],
    dias: (m) => m.dc, semDado: AGUARDANDO,
  },
};

async function carregarRetrato() {
  if (!retrato.dados) {
    const r = await fetch("dados/retrato.json");
    if (!r.ok) throw new Error(`não foi possível carregar dados/retrato.json (${r.status})`);
    retrato.dados = await r.json();
  }
  return retrato.dados;
}

const semAcento = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function faixaDe(dias, semDado) {
  return dias == null ? semDado.chave : FAIXAS_TEMPO.find((f) => dias >= f.min).chave;
}

function materiasDoFiltro() {
  return retrato.dados.materias.filter((m) => (estado.comissao === "TODAS" || m.c === estado.comissao)
                                               && (estado.grupo === "todas" || m.p));
}

function noRecorte(m, sel) {
  const dim = DIMENSOES[sel.dim];
  if (!dim.chaves(m).includes(sel.chave)) return false;
  return !sel.faixa || faixaDe(dim.dias(m), dim.semDado) === sel.faixa;
}

function agrupar(mats, dimensao) {
  const dim = DIMENSOES[dimensao];
  const linhas = new Map();
  for (const m of mats) {
    const faixa = faixaDe(dim.dias(m), dim.semDado);
    for (const k of dim.chaves(m)) {
      let l = linhas.get(k);
      if (!l) {
        const [nome, grupo, especial] = dim.nome(k, retrato.dados);
        l = { chave: k, nome, grupo, especial, total: 0, faixas: {}, areas: new Map() };
        linhas.set(k, l);
      }
      l.total += 1;
      l.faixas[faixa] = (l.faixas[faixa] || 0) + 1;
      if (dimensao === "passo" && m.pa) l.areas.set(m.pa, (l.areas.get(m.pa) || 0) + 1);
    }
  }
  const lista = [...linhas.values()];
  if (dimensao === "passo") {  // o mesmo passo aparece em áreas diferentes; mostra a mais comum
    for (const l of lista) l.grupo = [...l.areas].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
  }
  lista.sort((a, b) => b.total - a.total || a.nome.localeCompare(b.nome, "pt-BR"));
  const i = lista.findIndex((l) => l.chave === dim.fixar);
  if (i > 0) lista.unshift(...lista.splice(i, 1));
  return lista;
}

function renderBarras(id, dimensao, linhas, porTempo) {
  const cartao = document.getElementById(id);
  const c = cores();
  const faixas = [...FAIXAS_TEMPO, DIMENSOES[dimensao].semDado];
  const presentes = faixas.filter((f) => linhas.some((l) => l.faixas[f.chave]));
  const ul = cartao.querySelector(".legenda");
  ul.hidden = !porTempo;
  if (porTempo) legenda(cartao, presentes);
  const max = d3.max(linhas, (l) => l.total) || 1;
  const todos = retrato.todos.has(id);
  const ol = cartao.querySelector(".barras");
  ol.replaceChildren(...linhas.slice(0, todos ? Infinity : PRIMEIRAS)
    .map((l) => linhaBarra(l, dimensao, presentes, max, porTempo, c)));
  if (!linhas.length) ol.replaceChildren(el("li", "vazio", "Nenhuma matéria neste recorte."));
  const mais = cartao.querySelector(".mais");
  mais.hidden = linhas.length <= PRIMEIRAS;
  mais.textContent = todos ? `Mostrar só os ${PRIMEIRAS} primeiros` : `Mostrar todos (${linhas.length})`;
}

function linhaBarra(l, dimensao, faixas, max, porTempo, c) {
  const sel = retrato.recorte;
  const ativo = !!sel && sel.dim === dimensao && sel.chave === l.chave;
  const botao = el("button", "barra-linha");
  botao.type = "button";
  botao.setAttribute("aria-pressed", String(ativo));
  const completo = l.grupo ? `${l.nome} (${l.grupo})` : l.nome;
  const nome = el("span", l.especial ? "barra-nome especial" : "barra-nome", l.nome);
  if (l.grupo) nome.append(el("span", "grupo", l.grupo));
  nome.title = completo;
  const trilho = el("span", "barra-trilho");
  const partes = porTempo ? faixas.filter((f) => l.faixas[f.chave]).map((f) => ({ f, n: l.faixas[f.chave] }))
                          : [{ f: null, n: l.total }];
  for (const { f, n } of partes) {
    const seg = el("span", "seg");
    seg.style.width = `${(100 * n) / max}%`;
    seg.style.background = f ? c.v(f.cor) : c.s1;
    seg.dataset.n = fmt(n);
    seg.dataset.rotulo = f ? f.nome : "matérias";
    seg.dataset.cor = f ? f.cor : "--s1";
    if (f) {
      seg.dataset.faixa = f.chave;
      if (ativo && sel.faixa === f.chave) seg.classList.add("escolhido");
    }
    trilho.append(seg);
  }
  botao.append(nome, trilho, el("span", "barra-valor", fmt(l.total)));
  const detalhe = porTempo ? ` (${partes.map((p) => `${fmt(p.n)}: ${p.f.nome.toLowerCase()}`).join("; ")})` : "";
  botao.setAttribute("aria-label", `${completo}: ${fmt(l.total)} matérias${detalhe}. Listar as matérias.`);
  botao.addEventListener("click", (ev) => {
    const faixa = ev.target.closest(".seg")?.dataset.faixa ?? null;
    retrato.recorte = { dim: dimensao, chave: l.chave, nome: completo, faixa,
                        nomeFaixa: faixa ? faixas.find((f) => f.chave === faixa).nome : null };
    retrato.limite = 50;
    renderRetrato();
    document.getElementById("r-lista").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  const li = el("li");
  li.append(botao);
  return li;
}

// Lista de matérias
const ORDENS = {
  c: (m) => m.c,
  r: (m) => {
    const [tipo, resto] = m.r.split(" ");
    const [numero, ano] = resto.split("/");
    return `${ano}-${tipo}-${numero.padStart(6, "0")}`;
  },
  aut: (m) => (m.a.length ? semAcento(retrato.dados.pessoas[m.a[0]][0]) : "~"),
  rel: (m) => (m.rel == null ? "~" : semAcento(retrato.dados.pessoas[m.rel][0])),
  dc: (m) => m.dc ?? -1,
  dp: (m) => m.dp ?? -1,
};

function autoria(m, todos = false) {
  const nomes = m.a.map((a) => {
    const [nome, grupo] = retrato.dados.pessoas[a];
    return grupo && grupo !== nome && grupo !== "Outros" ? `${nome} (${grupo})` : nome;
  });
  if (todos || nomes.length <= 3) return nomes.join("; ");
  return `${nomes.slice(0, 2).join("; ")} e mais ${nomes.length - 2}`;
}

function relator(m) {
  if (m.rel == null) return "";
  const [nome, grupo] = retrato.dados.pessoas[m.rel];
  return `${nome} (${grupo})`;
}

function listaFiltrada(mats) {
  const sel = retrato.recorte;
  const lista = sel ? mats.filter((m) => noRecorte(m, sel)) : [...mats];
  const { campo, desc } = retrato.ordem;
  const chave = ORDENS[campo];
  return lista.sort((a, b) => {
    const [x, y] = [chave(a), chave(b)];
    return (x < y ? -1 : x > y ? 1 : 0) * (desc ? -1 : 1) || ORDENS.r(b).localeCompare(ORDENS.r(a));
  });
}

function renderLista(mats) {
  const sel = retrato.recorte;
  const lista = listaFiltrada(mats);
  const onde = estado.comissao === "TODAS" ? "nas 7 comissões" : `na ${estado.comissao}`;
  document.getElementById("lista-titulo").textContent = sel ? `Matérias · ${sel.nome}` : "Matérias";
  document.getElementById("lista-sub").textContent = sel
    ? `${fmt(lista.length)} ${lista.length === 1 ? "matéria" : "matérias"} ${onde}` +
      `${sel.nomeFaixa ? `, faixa "${sel.nomeFaixa.toLowerCase()}"` : ""}.`
    : `Todas as ${fmt(lista.length)} matérias em análise ${onde}. Clique numa barra acima para filtrar.`;
  document.getElementById("lista-limpar").hidden = !sel;

  const colunas = [
    ...(estado.comissao === "TODAS" ? [["c", "Comissão"]] : []),
    ["r", "Matéria"], [null, "Ementa"], ["aut", "Autoria"], ["rel", "Relator"],
    ["dc", "Na comissão"], ["dp", "Passo atual"],
  ];
  const tabela = el("table");
  const cab = el("tr");
  for (const [campo, nome] of colunas) {
    const th = el("th");
    th.scope = "col";
    if (campo) {
      const b = el("button", null, nome);
      b.type = "button";
      b.dataset.campo = campo;
      th.append(b);
      if (retrato.ordem.campo === campo) th.setAttribute("aria-sort", retrato.ordem.desc ? "descending" : "ascending");
    } else {
      th.textContent = nome;
    }
    cab.append(th);
  }
  tabela.append(el("thead"), el("tbody"));
  tabela.tHead.append(cab);
  for (const m of lista.slice(0, retrato.limite)) {
    const tr = el("tr");
    if (estado.comissao === "TODAS") tr.append(el("td", null, m.c));
    const tdMateria = el("td", "materia");
    const link = el("a", null, m.r);
    link.href = SPLEGIS + m.id;
    link.target = "_blank";
    link.rel = "noopener";
    tdMateria.append(link);
    const tdEmenta = el("td", "ementa");
    const ementa = el("span", null, m.e);
    ementa.title = m.e;
    tdEmenta.append(ementa);
    const tdRelator = el("td", null, relator(m) || "—");
    if (m.rel == null) tdRelator.classList.add("muted");
    const tdDias = el("td", "num", m.dc == null ? "aguardando recebimento" : `${fmt(m.dc)} dias`);
    const tdPasso = el("td");
    tdPasso.append(document.createTextNode(m.pt || "—"));
    if (m.dp != null) tdPasso.append(el("span", "muted", ` · há ${fmt(m.dp)} dias`));
    tr.append(tdMateria, tdEmenta, el("td", null, autoria(m)), tdRelator, tdDias, tdPasso);
    tabela.tBodies[0].append(tr);
  }
  const caixa = document.querySelector("#r-lista .lista");
  caixa.replaceChildren(lista.length ? tabela : el("p", "vazio", "Nenhuma matéria neste recorte."));
  const mais = document.getElementById("lista-mais");
  const restantes = lista.length - retrato.limite;
  mais.hidden = restantes <= 0;
  mais.textContent = `Mostrar mais ${fmt(Math.min(50, restantes))} (faltam ${fmt(restantes)})`;
}

function csvLista() {
  const lista = listaFiltrada(materiasDoFiltro());
  const aspas = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
  const cab = ["comissao", "materia", "link", "ementa", "autoria", "relator", "recebida_em",
               "dias_na_comissao", "passo_interno", "area_do_passo", "dias_no_passo"];
  const linhas = [cab.join(",")];
  for (const m of lista) {
    linhas.push([m.c, m.r, SPLEGIS + m.id, m.e, autoria(m, true), relator(m), m.rec, m.dc ?? "",
                 m.pt, m.pa, m.dp ?? ""].map(aspas).join(","));
  }
  const sufixo = retrato.recorte
    ? `-${semAcento(retrato.recorte.nome).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}` : "";
  const blob = new Blob([linhas.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
  const a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = `materias-${estado.comissao.toLowerCase()}-${estado.grupo}${sufixo}.csv`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function sincronizarAlternadores() {
  for (const [id, modo] of Object.entries(retrato.modos)) {
    for (const b of document.querySelectorAll(`#${id} .alternador:not([data-grupo]) button`)) {
      b.setAttribute("aria-pressed", String(b.dataset.modo === modo));
    }
  }
  for (const b of document.querySelectorAll('#r-autoria .alternador[data-grupo="agrupar"] button')) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === retrato.agrupar));
  }
}

function renderRetrato() {
  const d = retrato.dados;
  const mats = materiasDoFiltro();
  const onde = estado.comissao === "TODAS" ? "nas 7 comissões" : `na ${estado.comissao}`;
  const quais = estado.grupo === "projetos" ? "projetos" : "matérias";
  document.getElementById("nota-retrato").textContent =
    `Retrato de ${dataBR(utc(d.data))}: ${fmt(mats.length)} ${quais} em análise ${onde}. ` +
    "As idades contam dias completos até a coleta.";
  sincronizarAlternadores();
  renderBarras("r-relator", "relator", agrupar(mats, "relator"), retrato.modos["r-relator"] === "idade");
  renderBarras("r-passo", "passo", agrupar(mats, "passo"), retrato.modos["r-passo"] === "idade");
  let porAutoria = agrupar(mats, retrato.agrupar);
  if (retrato.busca.trim()) {
    const busca = semAcento(retrato.busca.trim());
    porAutoria = porAutoria.filter((l) => semAcento(`${l.nome} ${l.grupo}`).includes(busca));
  }
  renderBarras("r-autoria", retrato.agrupar, porAutoria, retrato.modos["r-autoria"] === "idade");
  renderLista(mats);
}

function iniciarRetrato() {
  for (const id of Object.keys(retrato.modos)) {
    const cartao = document.getElementById(id);
    cartao.querySelector(".alternador:not([data-grupo])").addEventListener("click", (ev) => {
      const b = ev.target.closest("button");
      if (!b) return;
      retrato.modos[id] = b.dataset.modo;
      renderRetrato();
    });
    cartao.querySelector(".mais").addEventListener("click", () => {
      if (retrato.todos.has(id)) retrato.todos.delete(id);
      else retrato.todos.add(id);
      renderRetrato();
    });
  }
  document.querySelector('#r-autoria .alternador[data-grupo="agrupar"]').addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    retrato.agrupar = b.dataset.modo;
    renderRetrato();
  });
  let espera;
  document.getElementById("busca-autoria").addEventListener("input", (ev) => {
    clearTimeout(espera);
    espera = setTimeout(() => { retrato.busca = ev.target.value; renderRetrato(); }, 150);
  });
  document.getElementById("lista-limpar").addEventListener("click", () => {
    retrato.recorte = null;
    retrato.limite = 50;
    renderRetrato();
  });
  document.getElementById("lista-csv").addEventListener("click", csvLista);
  document.getElementById("lista-mais").addEventListener("click", () => {
    retrato.limite += 50;
    renderLista(materiasDoFiltro());
  });
  document.querySelector("#r-lista .lista").addEventListener("click", (ev) => {
    const b = ev.target.closest("th button");
    if (!b) return;
    const campo = b.dataset.campo;
    const textual = ["c", "r", "aut", "rel"].includes(campo);
    retrato.ordem = { campo, desc: retrato.ordem.campo === campo ? !retrato.ordem.desc : !textual };
    renderLista(materiasDoFiltro());
  });

  // Dica dos trechos das barras: valor primeiro, nome depois.
  const dica = document.getElementById("dica-barras");
  document.addEventListener("pointermove", (ev) => {
    const seg = ev.target.closest?.(".barras .seg");
    if (!seg) { dica.hidden = true; return; }
    const linha = el("div", "linha");
    const chave = el("span", "chave");
    chave.style.background = cores().v(seg.dataset.cor);
    linha.append(chave, el("strong", null, seg.dataset.n), el("span", "nome", seg.dataset.rotulo));
    dica.replaceChildren(el("p", "data", seg.closest(".barra-linha").querySelector(".barra-nome").title), linha);
    dica.hidden = false;
    const w = dica.offsetWidth;
    const h = dica.offsetHeight;
    dica.style.left = `${Math.min(ev.clientX + 14, window.innerWidth - w - 8)}px`;
    dica.style.top = `${ev.clientY + 18 + h > window.innerHeight ? ev.clientY - h - 12 : ev.clientY + 18}px`;
  });
}

// ----------------------------------------------------------------------------- filtros, tema e endereço
function preencher(select, opcoes, valor) {
  select.replaceChildren(...opcoes.map(([v, t]) => {
    const o = el("option", null, t);
    o.value = v;
    return o;
  }));
  select.value = valor;
}

function lerEndereco() {
  const p = new URLSearchParams(location.hash.slice(1));
  const valido = (lista, v) => lista.some(([k]) => k === v);
  if (valido(COMISSOES, p.get("comissao"))) estado.comissao = p.get("comissao");
  if (valido(GRUPOS, p.get("grupo"))) estado.grupo = p.get("grupo");
  if (valido(PERIODOS, p.get("periodo"))) estado.periodo = p.get("periodo");
  if (["evolucao", "retrato"].includes(p.get("aba"))) estado.aba = p.get("aba");
}

function sincronizar() {
  document.getElementById("f-comissao").value = estado.comissao;
  document.getElementById("f-grupo").value = estado.grupo;
  document.getElementById("f-periodo").value = estado.periodo;
  history.replaceState(null, "", `#${new URLSearchParams(estado)}`);
}

const TEMAS = [["", "Tema: automático"], ["light", "Tema: claro"], ["dark", "Tema: escuro"]];

function aplicarTema(tema) {
  if (tema) document.documentElement.dataset.theme = tema;
  else delete document.documentElement.dataset.theme;
  try { tema ? localStorage.setItem("tema", tema) : localStorage.removeItem("tema"); } catch (e) { /* sem armazenamento */ }
  document.getElementById("tema").textContent = TEMAS.find(([t]) => t === tema)[1];
}

function iniciar() {
  lerEndereco();
  preencher(document.getElementById("f-periodo"), PERIODOS, estado.periodo);
  preencher(document.getElementById("f-comissao"),
            COMISSOES.map(([s, n]) => [s, s === "TODAS" ? n : `${s} · ${n}`]), estado.comissao);
  preencher(document.getElementById("f-grupo"), GRUPOS, estado.grupo);
  for (const [id, chave] of [["f-periodo", "periodo"], ["f-comissao", "comissao"], ["f-grupo", "grupo"]]) {
    document.getElementById(id).addEventListener("change", (ev) => {
      estado[chave] = ev.target.value;
      retrato.recorte = null;  // a seleção da lista vale para a comissão e o grupo em que foi feita
      sincronizar();
      render();
    });
  }
  for (const aba of ["evolucao", "retrato"]) {
    document.getElementById(`aba-${aba}`).addEventListener("click", () => {
      estado.aba = aba;
      sincronizar();
      render();
    });
  }
  document.querySelector(".abas").addEventListener("keydown", (ev) => {
    if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
    estado.aba = estado.aba === "evolucao" ? "retrato" : "evolucao";
    sincronizar();
    render();
    document.getElementById(`aba-${estado.aba}`).focus();
  });
  iniciarRetrato();
  aplicarTema(document.documentElement.dataset.theme || "");
  document.getElementById("tema").addEventListener("click", () => {
    const atual = document.documentElement.dataset.theme || "";
    const i = TEMAS.findIndex(([t]) => t === atual);
    aplicarTema(TEMAS[(i + 1) % TEMAS.length][0]);
    render();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  window.addEventListener("hashchange", () => { lerEndereco(); sincronizar(); render(); });
  let espera;
  new ResizeObserver(() => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      if (document.getElementById("conteudo").clientWidth !== ultimaLargura) render();
    }, 150);
  }).observe(document.getElementById("conteudo"));
  sincronizar();
  render();
}

iniciar();

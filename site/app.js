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
  ["livre", "Escolher as datas"],
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
// Cor de cada comissão nos gráficos que as comparam: paleta categórica validada, em ordem fixa
// e a mesma em todos os gráficos. "Todas" é a linha tracejada, na cor do texto.
const COR_COMISSAO = { CCJ: "--s1", FIN: "--s2", URB: "--s3", ADM: "--s4", ECON: "--s5", EDUC: "--s6", SAUDE: "--s7" };
const rotuloComissao = (s) => (s === "TODAS" ? "Todas" : s === "SAUDE" ? "SAÚDE" : s);
// Etapa da tramitação pelo último passo interno, na ordem do processo (reconstrucao/serie.py).
const ETAPA = [
  { campos: ["etapa_sem_relator"], nome: "Sem relator", cor: "--s1" },
  { campos: ["etapa_estudo"], nome: "Em estudo", cor: "--s2" },
  { campos: ["etapa_diligencia"], nome: "Em diligência", cor: "--s3" },
  { campos: ["etapa_pauta"], nome: "Na pauta", cor: "--s4" },
  { campos: ["etapa_votado"], nome: "Votada", cor: "--s5" },
  { campos: ["etapa_outra", "passo_desconhecido"], nome: "Outros ou desconhecido", cor: "--cinza-1" },
];

const DIA = 864e5;
const MARGEM_DIREITA = 56;  // igual em todos os cartões, para os eixos de tempo se alinharem
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const numero = new Intl.NumberFormat("pt-BR");
const fmt = (v) => (v == null ? "—" : numero.format(v));
const dataBR = (d) => `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}/${d.getUTCFullYear()}`;
const dataISO = (d) => d.toISOString().slice(0, 10);
const utc = (iso) => new Date(`${iso}T00:00:00Z`);

const estado = { aba: "retrato", periodo: "tudo", comissao: "TODAS", grupo: "projetos", de: "", ate: "" };
let ultimoDiaDados = null;  // último dia da série, para os períodos relativos (12 meses, 90 dias)
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

// Primeiro e último dia do período escolhido no filtro.
function periodoEscolhido(ultimo = ultimoDiaDados) {
  let inicio = utc("2018-11-01");
  let fim = ultimo;
  if (estado.periodo === "legislatura") inicio = utc("2025-01-01");
  if (estado.periodo === "12m") inicio = new Date(ultimo - 365 * DIA);
  if (estado.periodo === "90d") inicio = new Date(ultimo - 90 * DIA);
  if (estado.periodo === "livre") {
    if (estado.de) inicio = new Date(Math.max(utc(estado.de), inicio));
    if (estado.ate) fim = new Date(Math.min(utc(estado.ate), ultimo));
  }
  if (fim - inicio < 7 * DIA) inicio = new Date(fim - 7 * DIA);  // ao menos uma semana
  return [inicio, fim];
}

function textoPeriodo() {
  if (estado.periodo !== "livre") return PERIODO_TEXTO[estado.periodo];
  const [inicio, fim] = periodoEscolhido();
  return `de ${dataBR(inicio)} a ${dataBR(fim)}`;
}

function intervalo(datas) {
  const [inicio, fim] = periodoEscolhido(datas[datas.length - 1]);
  const i0 = Math.min(Math.max(0, d3.bisectLeft(datas, inicio)), datas.length - 2);
  return [i0, Math.max(i0 + 2, d3.bisectRight(datas, fim))];
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

const MEDIR_MARCO = document.createElement("canvas").getContext("2d");

function marcos(datas, c, inicioColeta, largura) {
  const [d0, d1] = [datas[0], datas[datas.length - 1]];
  const lista = LEGISLATURAS.map((iso) => ({ d: utc(iso), texto: "nova legislatura" }));
  lista.unshift({ d: utc(inicioColeta), texto: "início da coleta diária" });  // o primeiro a ganhar texto
  // Eventos de dados/eventos.csv (como a pandemia), em linha pontilhada e com menos prioridade.
  for (const ev of cache.eventos ?? []) lista.push({ d: utc(ev.data), texto: ev.texto, descricao: ev.descricao, evento: true });
  const visiveis = lista.filter((m) => m.d > d0 && m.d <= d1);
  // O texto vai à direita da linha (à esquerda no fim do eixo) ou, se não couber, do outro lado.
  // Não pode encostar em outro texto nem atravessar outra linha, para não parecer que é dela: em
  // telas estreitas, fica só a linha do marco que não cabe.
  const util = largura - 48 - MARGEM_DIREITA;
  for (const m of visiveis) m.px = ((m.d - d0) / (d1 - d0)) * util;
  MEDIR_MARCO.font = "11px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  const ocupados = [];
  for (const m of visiveis) {
    const w = MEDIR_MARCO.measureText(m.texto).width + 10;
    const fimDoEixo = (d1 - m.d) / (d1 - d0) < 0.15;
    const lados = fimDoEixo ? ["esquerda", "direita"] : ["direita", "esquerda"];
    m.lado = lados.find((lado) => {
      const [a, b] = lado === "esquerda" ? [m.px - w, m.px] : [m.px, m.px + w];
      if (a < -40 || b > util + MARGEM_DIREITA) return false;
      if (ocupados.some(([x0, x1]) => a < x1 && b > x0)) return false;
      if (visiveis.some((o) => o !== m && o.px > a - 2 && o.px < b + 2)) return false;
      ocupados.push([a, b]);
      return true;
    });
  }
  const comTexto = visiveis.filter((m) => m.lado);
  return [
    Plot.ruleX(visiveis.filter((m) => !m.evento), { x: "d", stroke: c.tinta3, strokeOpacity: 0.7 }),
    Plot.ruleX(visiveis.filter((m) => m.evento), { x: "d", stroke: c.tinta3, strokeOpacity: 0.7, strokeDasharray: "2 3",
      title: (m) => `${dataBR(m.d)}: ${m.descricao || m.texto}` }),
    Plot.text(comTexto.filter((m) => m.lado === "direita"), { x: "d", text: "texto", frameAnchor: "top",
      textAnchor: "start", dx: 4, dy: -12, fill: c.tinta2, fontSize: 11 }),
    Plot.text(comTexto.filter((m) => m.lado === "esquerda"), { x: "d", text: "texto", frameAnchor: "top",
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
function interagir(alvo, svg, datas, conteudo) {  // conteudo(i) -> { titulo?, linhas, total? }
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

    const { titulo, linhas, total } = conteudo(i);
    dica.replaceChildren(el("p", "data", titulo ?? dataBR(datas[i])));
    for (const l of linhas) {
      if (l.secao) {
        dica.append(el("p", "secao", l.secao));
        continue;
      }
      const linha = el("div", l.total ? "linha total" : "linha");
      if (l.cor) {
        const chave = el("span", l.quadrado ? "chave quadrado" : "chave");
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
  caixa.replaceChildren(botaoTabela, botaoCsv, ...(aberta ? [] : [botaoImagem(cartao)]));

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

// Imagem PNG do cartão: título, subtítulo, legenda e gráfico, com a fonte no rodapé.
async function baixarImagem(cartao, arquivo) {
  const svg = cartao.querySelector(".grafico svg");
  if (!svg) return;
  const c = cores();
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const w = svg.width.baseVal.value;
  const h = svg.height.baseVal.value;
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" }));
  const img = new Image();
  await new Promise((ok, erro) => { img.onload = ok; img.onerror = erro; img.src = url; });
  URL.revokeObjectURL(url);
  const fonte = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  const largura = w + 48;
  const medir = document.createElement("canvas").getContext("2d");
  const quebrar = (texto, fonteCss, max) => {
    medir.font = fonteCss;
    const linhas = [];
    let atual = "";
    for (const palavra of texto.split(/\s+/)) {
      const teste = atual ? `${atual} ${palavra}` : palavra;
      if (medir.measureText(teste).width > max && atual) { linhas.push(atual); atual = palavra; } else atual = teste;
    }
    if (atual) linhas.push(atual);
    return linhas;
  };
  const titulo = quebrar(cartao.querySelector("h2").textContent, `600 20px ${fonte}`, w);
  const sub = quebrar(cartao.querySelector(".sub")?.textContent ?? "", `14px ${fonte}`, w);
  const itens = [...cartao.querySelectorAll(".legenda li")].map((li) => ({
    texto: li.textContent, cor: li.querySelector(".amostra")?.style.background || li.querySelector(".amostra")?.style.borderColor || c.tinta3 }));
  medir.font = `13px ${fonte}`;
  const linhasLegenda = [];
  let x = 0;
  for (const it of itens) {
    const lw = 18 + medir.measureText(it.texto).width + 16;
    if (x + lw > w && x > 0) { linhasLegenda.push([]); x = 0; }
    if (!linhasLegenda.length) linhasLegenda.push([]);
    linhasLegenda[linhasLegenda.length - 1].push({ ...it, x });
    x += lw;
  }
  const altura = 24 + titulo.length * 26 + sub.length * 20 + 8 + linhasLegenda.length * 22 + 8 + h + 36;
  const escala = 2;
  const canvas = document.createElement("canvas");
  canvas.width = largura * escala;
  canvas.height = altura * escala;
  const ctx = canvas.getContext("2d");
  ctx.scale(escala, escala);
  ctx.fillStyle = c.superficie;
  ctx.fillRect(0, 0, largura, altura);
  let y = 24;
  ctx.textBaseline = "top";
  ctx.fillStyle = c.tinta;
  ctx.font = `600 20px ${fonte}`;
  for (const l of titulo) { ctx.fillText(l, 24, y); y += 26; }
  ctx.fillStyle = c.tinta2;
  ctx.font = `14px ${fonte}`;
  for (const l of sub) { ctx.fillText(l, 24, y); y += 20; }
  y += 8;
  ctx.font = `13px ${fonte}`;
  for (const linha of linhasLegenda) {
    for (const it of linha) {
      ctx.fillStyle = it.cor;
      ctx.fillRect(24 + it.x, y + 2, 12, 12);
      ctx.fillStyle = c.tinta2;
      ctx.fillText(it.texto, 24 + it.x + 18, y);
    }
    y += 22;
  }
  y += 8;
  ctx.drawImage(img, 24, y, w, h);
  y += h + 12;
  ctx.fillStyle = c.tinta3;
  ctx.font = `12px ${fonte}`;
  const filtros = `${estado.comissao === "TODAS" ? "7 comissões" : rotuloComissao(estado.comissao)} · ${GRUPOS.find(([g]) => g === estado.grupo)[1]}`;
  ctx.fillText(`${filtros} · ${textoPeriodo()} · Fonte: SPLEGIS (CMSP) · prototiposlegisla.github.io/comissoes-acervo`, 24, y);
  canvas.toBlob((blob) => {
    const a = el("a");
    a.href = URL.createObjectURL(blob);
    a.download = arquivo;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }, "image/png");
}

function botaoImagem(cartao) {
  const b = el("button", "botao", "Baixar imagem");
  b.type = "button";
  b.addEventListener("click", () => baixarImagem(cartao, `${cartao.id.replace(/^c-/, "")}-${estado.comissao.toLowerCase()}.png`));
  return b;
}

function baixarCsv(datas, colunas, arquivo) {
  baixarTabela(["data", ...colunas.map((c) => c.nome)],
               datas.map((d, i) => [dataISO(d), ...colunas.map((c) => c.valores[i] ?? "")]), arquivo);
}

function baixarTabela(cabecalho, linhas, arquivo) {
  const aspas = (s) => `"${String(s).replace(/"/g, '""')}"`;
  const campo = (v) => (v == null ? "" : typeof v === "number" ? String(v) : aspas(v));
  const texto = [cabecalho.map(aspas).join(","), ...linhas.map((l) => l.map(campo).join(","))];
  const blob = new Blob([texto.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
  const a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = arquivo;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// Como `acoes`, para gráficos cujas linhas não são dias: `linhas` já vêm prontas, em ordem
// cronológica (a tabela mostra a mais recente primeiro, salvo `recentesPrimeiro: false`).
function acoesTabela(cartao, colunas, linhas, arquivo, { recentesPrimeiro = true } = {}) {
  const caixa = cartao.querySelector(".acoes");
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
  botaoCsv.addEventListener("click", () => baixarTabela(colunas.map((c) => c.nome), linhas, arquivo));
  caixa.replaceChildren(botaoTabela, botaoCsv, ...(aberta ? [] : [botaoImagem(cartao)]));

  cartao.querySelector(".tabela")?.remove();
  for (const e of cartao.querySelectorAll(".legenda, .grafico")) e.hidden = aberta;
  if (!aberta) return;
  const tabela = el("table");
  const cab = el("tr");
  cab.append(...colunas.map((c) => el("th", null, c.nome)));
  tabela.append(el("thead"), el("tbody"));
  tabela.tHead.append(cab);
  for (const l of recentesPrimeiro ? [...linhas].reverse() : linhas) {
    const tr = el("tr");
    tr.append(...l.map((v) => el("td", null, typeof v === "number" ? numero.format(v) : v ?? "—")));
    tabela.tBodies[0].append(tr);
  }
  const caixaTabela = el("div", "tabela");
  caixaTabela.append(tabela);
  grafico.after(caixaTabela);
}

// ----------------------------------------------------------------------------- gráficos
function graficoLinha(alvo, datas, valores, opcoes) {
  const c = cores();
  const cor = opcoes.cor ? c.v(opcoes.cor) : c.s1;
  const largura = alvo.clientWidth;
  const pontos = datas.map((d, i) => ({ d, v: valores[i] })).filter((p) => p.v != null);
  const ultimo = pontos.slice(-1);
  const m = moldura(c, datas, largura, opcoes.altura, { marginRight: opcoes.marginRight ?? MARGEM_DIREITA,
    marginLeft: opcoes.marginLeft, yTicks: opcoes.yTicks });
  const svg = Plot.plot({
    ...m.opcoes,
    marks: [
      ...m.eixos,
      ...(opcoes.marcos ? marcos(datas, c, opcoes.inicioColeta, largura) : []),
      ...(opcoes.area ? [Plot.areaY(pontos, { x: "d", y: "v", fill: cor, fillOpacity: 0.1 })] : []),
      Plot.lineY(pontos, { x: "d", y: "v", stroke: cor, strokeWidth: 2, strokeLinejoin: "round", strokeLinecap: "round" }),
      Plot.dot(ultimo, { x: "d", y: "v", r: 4, fill: cor, stroke: c.superficie, strokeWidth: 2 }),
      ...(opcoes.rotuloFinal ? [Plot.text(ultimo, { x: "d", y: "v", text: (p) => fmt(p.v), dx: 8,
                                                   textAnchor: "start", fill: c.tinta, fontWeight: 600 })] : []),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, datas, (i) => ({
    linhas: [{ cor, valor: opcoes.formato(valores[i]), nome: opcoes.detalhe ? `${opcoes.nome} ${opcoes.detalhe(i)}` : opcoes.nome }],
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
      ...marcos(datas, c, opcoes.inicioColeta, largura),
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

// Várias linhas na mesma escala. `pontos` marca cada ponto da série (útil quando ela é curta).
// Opções: marcos (false para tirar as linhas de legislatura e coleta), titulo(i) e formato(v)
// para a dica, detalhe(s, i) para o texto depois do nome e total (série para o percentual).
function graficoLinhas(alvo, datas, series, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const longo = series.flatMap((s) => datas.map((d, i) => ({ d, v: s.valores[i], s: s.nome })).filter((p) => p.v != null));
  const m = moldura(c, datas, largura, opcoes.altura,
                    { yDomain: [0, d3.max(longo, (p) => p.v) || 1], marginRight: MARGEM_DIREITA });
  // Valor no fim de cada linha; rótulos que se encostariam são afastados na vertical.
  const altura = opcoes.altura - 22 - 26;
  const topo = d3.scaleLinear().domain([0, d3.max(longo, (p) => p.v) || 1]).nice().domain()[1];
  const finais = series.map((s) => longo.filter((p) => p.s === s.nome).pop()).filter(Boolean)
    .sort((a, b) => b.v - a.v);
  let anterior = -Infinity;
  for (const p of finais) {
    const y = Math.max((1 - p.v / topo) * altura, anterior + 13);
    p.vRotulo = (1 - y / altura) * topo;
    anterior = y;
  }
  const svg = Plot.plot({
    ...m.opcoes,
    color: { domain: series.map((s) => s.nome), range: series.map((s) => c.v(s.cor)) },
    marks: [
      ...m.eixos,
      ...(opcoes.marcos === false ? [] : marcos(datas, c, opcoes.inicioColeta, largura)),
      Plot.lineY(longo, { x: "d", y: "v", z: "s", stroke: "s", strokeWidth: 2, strokeLinejoin: "round", strokeLinecap: "round" }),
      ...series.filter((s) => s.pontos).map((s) => Plot.dot(longo.filter((p) => p.s === s.nome),
        { x: "d", y: "v", r: 3, fill: c.v(s.cor), stroke: c.superficie, strokeWidth: 1.5 })),
      Plot.text(finais, { x: "d", y: "vRotulo", text: (p) => fmt(p.v), dx: 8, textAnchor: "start", fill: c.tinta, fontWeight: 600 }),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  const formato = opcoes.formato ?? fmt;
  const detalhe = opcoes.detalhe ?? ((s, i) => (opcoes.total?.[i] ? `(${porcentoInteiro(s.valores[i] / opcoes.total[i])} do acervo)` : ""));
  interagir(alvo, svg, datas, (i) => ({
    titulo: opcoes.titulo?.(i),
    linhas: series.filter((s) => s.valores[i] != null).map((s) => ({ cor: c.v(s.cor), valor: formato(s.valores[i]),
      nome: `${s.nome} ${detalhe(s, i)}`.trim() })),
  }));
}

function legenda(cartao, camadas) {
  const c = cores();
  const ul = cartao.querySelector(".legenda");
  ul.replaceChildren(...camadas.map((k) => {
    const li = el("li");
    const amostra = el("span", k.tracejada ? "amostra tracejada" : k.linha ? "amostra linha" : "amostra");
    if (k.tracejada) amostra.style.borderColor = c.v(k.cor);
    else amostra.style.background = c.v(k.cor);
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
  const mais180 = serie.idade_181a365[u] + serie.idade_mais365[u];
  const mais365 = serie.idade_mais365[u];
  const quais = estado.grupo === "projetos" ? "projetos em análise" : "matérias em análise";
  const variacao = antes == null ? quais
    : `${quais}; ${total - antes >= 0 ? "+" : "−"}${fmt(Math.abs(total - antes))} em 12 meses (eram ${fmt(antes)})`;
  const itens = [
    { rotulo: `Acervo ativo em ${dataBR(hoje)}`, valor: fmt(total), nota: variacao, heroi: true },
    { rotulo: "Relatores", valor: fmt(serie.relatores[u]), nota: "com matérias distribuídas" },
    { rotulo: "Sem relator", valor: fmt(serie.sem_relator[u]), nota: `${porcento(serie.sem_relator[u], total)} do acervo` },
    { rotulo: "Mais de 180 dias", valor: fmt(mais180), nota: `${porcento(mais180, total)} do acervo` },
    { rotulo: "Mais de 365 dias", valor: fmt(mais365), nota: `${porcento(mais365, total)} do acervo` },
    { rotulo: "Mediana na comissão", valor: serie.mediana_dias[u] == null ? "—" : `${fmt(serie.mediana_dias[u])} dias`,
      nota: "metade do acervo abaixo" },
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
    const h3 = el("h3", null, `${rotuloComissao(sigla)} `);
    h3.append(el("span", null, nome.split(",")[0]));
    topo.append(h3, el("span", "valor-mini", fmt(valores[valores.length - 1])));
    const grafico = el("div", "grafico");
    mini.append(topo, grafico);
    caixa.append(mini);
    const escolher = () => { estado.comissao = sigla; sincronizar(); render(); window.scrollTo({ top: 0, behavior: "smooth" }); };
    mini.addEventListener("click", escolher);
    mini.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); escolher(); } });
    graficoLinha(grafico, datas, valores, { altura: 120, area: true, yTicks: 3, marginLeft: 40, marginRight: 12,
      nome: "matérias", cor: COR_COMISSAO[sigla],
      formato: fmt, descricao: resumo(`Acervo da ${sigla}`, datas, valores) });
  }
}

function renderEvolucao(j, serie, fluxos, tramitacao, legislativo) {
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
  renderBase100(j, i0, i1);
  if (!(fluxos instanceof Error) && fluxos) renderComposicao(fluxos, j, i0, i1, { comissao: nomeComissao, grupo: nomeGrupo });

  // Idade: desde o recebimento ou desde o último passo interno
  const cIdade = document.getElementById("c-idade");
  const parados = cIdade.dataset.modo === "parado";
  for (const b of cIdade.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === (parados ? "parado" : "idade")));
    b.onclick = () => { cIdade.dataset.modo = b.dataset.modo; render(); };
  }
  cIdade.querySelector("h2").textContent = parados ? "Há quanto tempo estão sem movimentação" : "Há quanto tempo estão na comissão";
  document.getElementById("sub-idade").textContent = parados
    ? "Matérias do acervo pelos dias completos sem nenhum passo interno: desde o último passo ou, se ainda não houve nenhum, desde o recebimento. Mostra o que está parado, mesmo que tenha chegado há pouco."
    : "Matérias do acervo por dias completos desde o recebimento pela comissão.";
  const faixasIdade = parados
    ? IDADE.map((k) => ({ ...k, nome: k.campos[0] === "idade_desconhecida" ? "Sem data conhecida" : k.nome,
                          campos: k.campos.map((cp) => (cp === "idade_desconhecida" ? "parado_desconhecido"
                                                       : cp.replace(/^idade_/, "parado_"))) }))
    : IDADE;
  const camadasIdade = faixasIdade.map((k) => ({ ...k, valores: datas.map((_, i) => soma(serie, k.campos, i0 + i)) }))
    .filter((k) => k.valores.some((v) => v));
  legenda(cIdade, camadasIdade);
  acoes(cIdade, datas, camadasIdade, arquivo(parados ? "sem-movimentacao" : "idade"));
  if (cIdade.dataset.tabela !== "1") {
    graficoEmpilhado(cIdade.querySelector(".grafico"), datas, camadasIdade, {
      altura: 300, inicioColeta: j.inicio_coleta,
      descricao: `${parados ? "Tempo sem movimentação" : "Idade"} das matérias ${nomeComissao}, empilhada por faixa. ` +
        resumo("Mais de 1 ano", datas, camadasIdade[0].valores) });
  }

  // Mediana
  const cMediana = document.getElementById("c-mediana");
  const mediana = fatia("mediana_dias");
  // Base da mediana: só as matérias já recebidas, com idade conhecida.
  const pendentes = fatia("pendentes");
  const recebidas = datas.map((_, i) => soma(serie, ["materias"], i0 + i) - pendentes[i] - serie.idade_desconhecida[i0 + i]);
  acoes(cMediana, datas, [{ nome: "idade mediana (dias)", valores: mediana },
                          { nome: "matérias recebidas (base da mediana)", valores: recebidas },
                          { nome: "aguardando recebimento", valores: pendentes }], arquivo("mediana"));
  if (cMediana.dataset.tabela !== "1") {
    graficoLinha(cMediana.querySelector(".grafico"), datas, mediana, {
      altura: 220, marcos: true, rotuloFinal: true, inicioColeta: j.inicio_coleta, nome: "dias",
      detalhe: (i) => `— mediana de ${fmt(recebidas[i])} ${estado.grupo === "projetos"
        ? (recebidas[i] === 1 ? "projeto recebido" : "projetos recebidos")
        : (recebidas[i] === 1 ? "matéria recebida" : "matérias recebidas")}` +
        (pendentes[i] ? `; ${fmt(pendentes[i])} aguardando recebimento` : ""),
      formato: (v) => (v == null ? "—" : `${fmt(v)}`), descricao: resumo(`Idade mediana, em dias, ${nomeComissao}`, datas, mediana) });
  }

  // Passo interno: pela etapa da tramitação ou pela área
  const cPasso = document.getElementById("c-passo");
  const porEtapa = cPasso.dataset.modo === "etapa";
  for (const b of cPasso.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === (porEtapa ? "etapa" : "area")));
    b.onclick = () => { cPasso.dataset.modo = b.dataset.modo; render(); };
  }
  document.getElementById("sub-passo").textContent = porEtapa
    ? "Etapa de cada matéria na comissão, pelo último passo interno."
    : "Área do último passo interno de cada matéria na comissão.";
  document.getElementById("nota-passo").hidden = !porEtapa;
  const camadasPasso = (porEtapa ? ETAPA : PASSO).map((k) => ({ ...k, valores: datas.map((_, i) => soma(serie, k.campos, i0 + i)) }));
  legenda(cPasso, camadasPasso);
  acoes(cPasso, datas, camadasPasso, arquivo(porEtapa ? "etapa" : "passo"));
  if (cPasso.dataset.tabela !== "1") {
    graficoEmpilhado(cPasso.querySelector(".grafico"), datas, camadasPasso, {
      altura: 300, inicioColeta: j.inicio_coleta,
      descricao: `Matérias ${nomeComissao} pela ${porEtapa ? "etapa da tramitação" : "área do passo interno"}. ` +
        resumo(camadasPasso[0].nome, datas, camadasPasso[0].valores) });
  }

  // Sem relator: estimativa pelo passo interno e, desde a coleta diária, o número do relatório
  const cSemRelator = document.getElementById("c-sem-relator");
  const estimativa = fatia("etapa_sem_relator");
  const seriesSemRelator = [
    { nome: "estimativa pelo passo interno", valores: estimativa, cor: "--s1", linha: true },
    { nome: "relatório do SPLEGIS", valores: fatia("sem_relator"), cor: "--s2", linha: true, pontos: true },
  ];
  legenda(cSemRelator, seriesSemRelator);
  acoes(cSemRelator, datas, seriesSemRelator, arquivo("sem-relator"));
  if (cSemRelator.dataset.tabela !== "1") {
    graficoLinhas(cSemRelator.querySelector(".grafico"), datas, seriesSemRelator, {
      altura: 260, inicioColeta: j.inicio_coleta, total: fatia("materias"),
      descricao: resumo(`${nomeGrupo} sem relator ${nomeComissao} (estimativa)`, datas, estimativa) });
  }

  renderFluxos(fluxos, { comissao: nomeComissao, grupo: nomeGrupo });
  renderResumoSemana(j, serie, fluxos, tramitacao);
  renderSumario();
  renderTramitacao(tramitacao, { comissao: nomeComissao, grupo: nomeGrupo }, j.datasObj[j.datasObj.length - 1]);
  renderLegislativo(legislativo, tramitacao, { comissao: nomeComissao, grupo: nomeGrupo }, j.datasObj[j.datasObj.length - 1]);
}

// ----------------------------------------------------------------------------- composição e base 100
/* Composição do acervo por legislatura de apresentação, tipo ou autoria, dia a dia, a partir
   das passagens (dados/fluxos.json): uma matéria conta enquanto está no acervo. */
function legislaturasDe(f) {
  const ultima = 2001 + 4 * Math.floor((d3.max(f.ano) - 2001) / 4);
  const faixa = (a) => `${a}–${a + 3}`;
  // Da mais antiga (base) para a mais nova (topo); mais antiga = mais escura, como na idade.
  return [
    { nome: `Antes de ${ultima - 12}`, cor: "--idade-5", teste: (ano) => ano < ultima - 12 },
    ...[ultima - 12, ultima - 8, ultima - 4, ultima].map((a, k) => ({
      nome: faixa(a), cor: `--idade-${4 - k}`, teste: (ano) => ano >= a && ano <= a + 3 })),
  ];
}

const COMPOSICAO = {
  legislatura: {
    sub: "Matérias no acervo pela legislatura em que foram apresentadas. As de legislaturas anteriores voltaram às comissões depois de desarquivadas.",
    categorias: (f) => legislaturasDe(f).map((k) => ({ nome: k.nome, cor: k.cor })),
    atributo: (f) => { const ls = legislaturasDe(f); return (i) => ls.findIndex((k) => k.teste(f.ano[i])); },
  },
  tipo: {
    sub: () => "Matérias no acervo pelo tipo: projetos de lei (PL), de decreto legislativo (PDL), de resolução (PR) e de emenda à Lei Orgânica (PLO)" +
      (estado.grupo === "projetos" ? "." : ", documentos recebidos (DOCREC) e outros."),
    categorias: (f) => f.tipos.map((t, k) => ({ nome: t === "Outros" ? "Outros tipos" : t,
                                                 cor: t === "Outros" ? "--cinza-1" : `--s${k + 1}` })),
    atributo: (f) => (i) => f.tipo[i],
  },
  autoria: {
    sub: () => "Matérias no acervo pelo primeiro autor. O Executivo é o prefeito." +
      (estado.grupo === "projetos" ? "" : " Documentos recebidos, requerimentos e outros tipos que não são projetos ficam à parte."),
    categorias: (f) => f.autorias.map((a) => ({ nome: a,
      cor: { Vereadores: "--s1", Executivo: "--s2", "Mesa Diretora": "--s3", "Documentos e outros tipos": "--s4" }[a] ?? "--cinza-1" })),
    atributo: (f) => (i) => f.autoria[i],
  },
};

// Quantas passagens de cada categoria estavam no acervo no fim de cada dia de `datas`.
function composicaoDiaria(f, datas, nCategorias, atributo) {
  const base = dataParaDia(f, datas[0]);
  const n = dataParaDia(f, datas[datas.length - 1]) - base + 1;
  const delta = Array.from({ length: nCategorias }, () => new Int32Array(n + 1));
  for (const i of passagensDoRecorte(f)) {
    const k = atributo(i);
    if (k < 0) continue;
    const de = f.desde[i] == null ? 0 : Math.max(0, f.desde[i] - base);
    const ate = f.ate[i] == null ? n : Math.min(n, f.ate[i] - base);
    if (de >= n || ate <= de) continue;
    delta[k][de] += 1;
    delta[k][ate] -= 1;
  }
  return delta.map((d) => {
    let acc = 0;
    const porDia = Array.from({ length: n }, (_, t) => (acc += d[t]));
    return datas.map((x) => porDia[dataParaDia(f, x) - base]);
  });
}

function renderComposicao(f, j, i0, i1, nomes) {
  const cartao = document.getElementById("c-composicao");
  const modo = COMPOSICAO[cartao.dataset.modo] ? cartao.dataset.modo : "legislatura";
  for (const b of cartao.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === modo));
    b.onclick = () => { cartao.dataset.modo = b.dataset.modo; render(); };
  }
  const def = COMPOSICAO[modo];
  document.getElementById("sub-composicao").textContent = typeof def.sub === "function" ? def.sub() : def.sub;
  const datas = j.datasObj.slice(i0, i1);
  const categorias = def.categorias(f);
  const contagens = composicaoDiaria(f, datas, categorias.length, def.atributo(f));
  const camadas = categorias.map((k, n) => ({ ...k, valores: contagens[n] })).filter((k) => k.valores.some((v) => v));
  legenda(cartao, camadas);
  acoes(cartao, datas, camadas, `composicao-${modo}-${estado.comissao.toLowerCase()}-${estado.grupo}.csv`);
  if (cartao.dataset.tabela === "1") return;
  graficoEmpilhado(cartao.querySelector(".grafico"), datas, camadas, {
    altura: 300, inicioColeta: j.inicio_coleta,
    descricao: `Composição do acervo ${nomes.comissao} por ${modo === "legislatura" ? "legislatura de apresentação" : modo}. ` +
      resumo(camadas[camadas.length - 1]?.nome ?? "", datas, camadas[camadas.length - 1]?.valores ?? []) });
}

// Com uma comissão escolhida, a linha dela engrossa e as das outras se apagam.
function estiloComissao(c, destaque) {
  return (sigla) => {
    if (sigla === "TODAS") return { cor: c.tinta, largura: destaque === "TODAS" ? 2.5 : 1.75, opacidade: 1, traco: "5 3" };
    const escolhida = sigla === destaque;
    return { cor: c.v(COR_COMISSAO[sigla]), largura: escolhida ? 3 : 1.75,
             opacidade: destaque === "TODAS" || escolhida ? 1 : 0.35, traco: null };
  };
}

// Linhas das comissões e de "Todas", com um ponto e o nome no fim de cada uma; nomes que se
// encostariam são afastados na vertical. px e py dão a posição de um ponto {x, y} na tela;
// texto(p), o rótulo do fim da linha (o nome da comissão, se omitido).
function marcasComissoes(c, curvas, destaque, pontosDe, px, py, texto = (p) => rotuloComissao(p.sigla),
                         estilo = estiloComissao(c, destaque)) {
  const peso = (sigla) => (sigla === destaque ? 3 : sigla === "TODAS" ? 2 : destaque === "TODAS" ? 1 : 0);
  const ordem = [...curvas].sort((a, b) => peso(a.sigla) - peso(b.sigla));
  // pontosDe pode trazer pontos com y nulo, que interrompem a linha; o rótulo fica no último com valor.
  const fins = ordem.map((cv) => ({ ...pontosDe(cv).filter((p) => p.y != null).pop(), sigla: cv.sigla })).filter((p) => p.y != null);
  const postos = [];
  for (const r of [...fins].sort((a, b) => py(a) - py(b))) {
    let y = py(r);
    for (const p of postos) if (Math.abs(p.x - px(r)) < 44 && y < p.y + 13) y = p.y + 13;
    postos.push({ x: px(r), y });
    r.dy = y - py(r);
  }
  return [
    ...ordem.map((cv) => {
      const e = estilo(cv.sigla);
      return Plot.line(pontosDe(cv), { x: "x", y: "y", stroke: e.cor, strokeWidth: e.largura, strokeOpacity: e.opacidade,
        ...(e.traco ? { strokeDasharray: e.traco } : {}), strokeLinejoin: "round", strokeLinecap: "round" });
    }),
    ...fins.map((p) => {
      const e = estilo(p.sigla);
      return Plot.dot([p], { x: "x", y: "y", r: 3, fill: e.cor, fillOpacity: e.opacidade, stroke: c.superficie, strokeWidth: 1 });
    }),
    ...fins.map((p) => Plot.text([p], { x: "x", y: "y", dx: 7, dy: p.dy, text: () => texto(p), textAnchor: "start",
      fontSize: 11, fill: p.sigla === destaque ? c.tinta : c.tinta2, fontWeight: p.sigla === destaque ? 600 : 400 })),
  ];
}

// Dica com o valor de cada comissão num ponto: a escolhida primeiro, as outras do maior ao menor.
// detalhe(cv), se dado, vai depois do nome. `estilo` e `nome` servem para curvas que não são comissões.
function linhasDaDica(c, curvas, destaque, valor, formato, detalhe = () => "",
                      { estilo = estiloComissao(c, destaque), nome = (s) => (s === "TODAS" ? "todas as comissões" : rotuloComissao(s)) } = {}) {
  const presentes = curvas.filter((cv) => valor(cv) != null);
  const escolhida = presentes.find((cv) => cv.sigla === destaque);
  const outras = presentes.filter((cv) => cv !== escolhida).sort((a, b) => valor(b) - valor(a));
  return [...(escolhida ? [escolhida] : []), ...outras]
    .map((cv) => ({ cor: estilo(cv.sigla).cor, valor: formato(valor(cv)), nome: `${nome(cv.sigla)} ${detalhe(cv)}`.trim() }));
}

// Curvas por autoria (vereadores, Executivo, Mesa), com as mesmas cores da composição do acervo.
const COR_AUTORIA = { Vereadores: "--s1", Executivo: "--s2", "Mesa Diretora": "--s3" };
const AUTORIAS_CURVAS = ["Vereadores", "Executivo", "Mesa Diretora"];
const TODAS_AUTORIAS = "Todas";
const nomeAutoria = (a) => a;  // "Todas" curto, para caber no fim da linha; a legenda diz "Todas as autorias"
function estiloAutoria(c) {
  return (a) => (a === TODAS_AUTORIAS ? { cor: c.tinta, largura: 2, opacidade: 1, traco: "5 3" }
    : { cor: c.v(COR_AUTORIA[a] ?? "--cinza-1"), largura: 2.25, opacidade: 1, traco: null });
}
function legendaAutorias(cartao) {
  legenda(cartao, [...AUTORIAS_CURVAS.map((a) => ({ nome: a, cor: COR_AUTORIA[a], linha: true })),
                   { nome: "Todas as autorias", cor: "--tinta", tracejada: true }]);
}

function legendaComissoes(cartao) {
  legenda(cartao, [...Object.entries(COR_COMISSAO).map(([sigla, cor]) => ({ nome: rotuloComissao(sigla), cor, linha: true })),
                   { nome: "Todas as comissões", cor: "--tinta", tracejada: true }]);
}

function graficoComparado(alvo, datas, curvas, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const maximo = d3.max(curvas, (cv) => d3.max(cv.valores)) || 1;
  const m = moldura(c, datas, largura, opcoes.altura, { yDomain: [0, maximo], marginRight: MARGEM_DIREITA });
  m.eixos[1] = Plot.axisY({ ticks: 5, tickSize: 0, tickPadding: 6, tickFormat: (v) => `${numero.format(v)}%`,
                            fill: c.tinta3, label: null });
  const topo = d3.scaleLinear().domain([0, maximo]).nice().domain()[1];
  const [d0, d1] = [datas[0], datas[datas.length - 1]];
  const px = (p) => ((p.x - d0) / (d1 - d0)) * (largura - 48 - MARGEM_DIREITA);
  const py = (p) => (1 - p.y / topo) * (opcoes.altura - 22 - 26);
  const pontosDe = (cv) => datas.map((d, i) => ({ x: d, y: cv.valores[i] })).filter((p) => p.y != null);
  const svg = Plot.plot({
    ...m.opcoes,
    marks: [
      ...m.eixos,
      Plot.ruleY([100], { stroke: c.tinta3, strokeDasharray: "3 3", strokeOpacity: 0.8 }),
      ...marcos(datas, c, opcoes.inicioColeta, largura),
      ...marcasComissoes(c, curvas, opcoes.destaque, pontosDe, px, py,
                         (p) => `${rotuloComissao(p.sigla)} ${numero.format(Math.round(p.y))}%`),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, datas, (i) => ({
    linhas: linhasDaDica(c, curvas, opcoes.destaque, (cv) => cv.valores[i], (v) => `${numero.format(Math.round(v))}%`,
                         (cv) => `· ${fmt(cv.brutos[i])} (eram ${fmt(cv.base)})`),
  }));
}

function renderBase100(j, i0, i1) {
  const cartao = document.getElementById("c-base100");
  const datas = j.datasObj.slice(i0, i1);
  const curvas = COMISSOES.map(([sigla]) => {
    const brutos = j.comissoes[sigla].materias.slice(i0, i1);
    const base = brutos.find((x) => x);
    return { sigla, nome: rotuloComissao(sigla), brutos, base,
             valores: brutos.map((x) => (x == null || !base ? null : (100 * x) / base)) };
  });
  // Exemplo com a comissão escolhida (ou as 7 juntas), para dar sentido à porcentagem.
  const ex = curvas.find((cv) => cv.sigla === estado.comissao);
  const final = ex.brutos[ex.brutos.length - 1];
  const r = final / ex.base;
  const comparacao = r >= 3 ? `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(r)} vezes o tamanho daquele dia`
    : r > 2.05 ? "mais que o dobro" : r >= 1.95 ? "o dobro"
    : r > 1.05 ? `${Math.round((r - 1) * 100)}% maior` : r >= 0.95 ? "praticamente o mesmo tamanho"
    : `${Math.round((1 - r) * 100)}% menor`;
  const unidade = estado.grupo === "projetos" ? "projetos" : "matérias";
  const [quem, tinha, tem, esta] = estado.comissao === "TODAS"
    ? ["As 7 comissões juntas", "tinham", "têm", "estão"] : [`A ${ex.nome}`, "tinha", "tem", "está"];
  document.getElementById("sub-base100").textContent =
    "Para comparar comissões de tamanhos muito diferentes, cada linha mostra o acervo de uma comissão como " +
    `porcentagem do tamanho que ela tinha em ${dataBR(datas[0])}, o primeiro dia do período: 100% é o mesmo tamanho; ` +
    `200%, o dobro; 50%, a metade. ${quem} ${tinha} ${fmt(ex.base)} ${unidade} naquele dia e ${tem} ${fmt(final)} ` +
    `em ${dataBR(datas[datas.length - 1])}: ${esta} em ${numero.format(Math.round(100 * r))}%, ${comparacao}.`;
  legendaComissoes(cartao);
  acoes(cartao, datas, curvas.map((cv) => ({ nome: `${cv.nome} (% de ${dataBR(datas[0])})`,
                                             valores: cv.valores.map((v) => (v == null ? null : Math.round(v))) })),
        `crescimento-${estado.grupo}-${estado.periodo}.csv`);
  if (cartao.dataset.tabela === "1") return;
  const ultimo = curvas.map((cv) => `${cv.nome} ${fmt(Math.round(cv.valores[cv.valores.length - 1] ?? 0))}%`).join(", ");
  graficoComparado(cartao.querySelector(".grafico"), datas, curvas, {
    altura: 300, destaque: estado.comissao, inicioColeta: j.inicio_coleta,
    descricao: `Acervo de cada comissão como porcentagem do tamanho em ${dataBR(datas[0])}. No último dia: ${ultimo}.` });
}

// ----------------------------------------------------------------------------- fluxos
/* Passagens das matérias pelas comissões (dados/fluxos.json, gerado por `python -m painel`):
   quando cada matéria entrou no acervo de cada comissão, de onde veio, quando saiu e para
   onde foi. Base dos gráficos de entradas e saídas, de permanência e de rotas. */

// Áreas de origem e de destino, agrupadas. As cores seguem a ordem fixa da paleta.
const AREAS = [
  { chave: "comissao", nome: "Outra comissão", curto: "", cor: "--s1" },
  { chave: "plenario", nome: "Plenário (SGP-21)", curto: "Plenário", cor: "--s2" },
  { chave: "secretaria", nome: "Secretaria das Comissões (SGP-12)", curto: "Sec. Comissões", cor: "--s3" },
  { chave: "controle", nome: "Controle do Processo Legislativo (SGP-22)", curto: "Controle", cor: "--s4" },
  { chave: "sgp", nome: "Outras equipes da SGP", curto: "Outras SGP", cor: "--s5" },
  { chave: "arquivo", nome: "Arquivo", curto: "Arquivo", cor: "--s6" },
  { chave: "procuradoria", nome: "Procuradoria", curto: "Procur.", cor: "--s7" },
  { chave: "outros", nome: "Outras áreas ou desconhecida", curto: "Outras", cor: "--cinza-1" },
];
const PERIODO_TEXTO = { tudo: "desde nov/2018", legislatura: "na legislatura atual (desde 2025)",
                        "12m": "nos últimos 12 meses", "90d": "nos últimos 90 dias" };
const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                      "setembro", "outubro", "novembro", "dezembro"];
const MINIMO_EM_RISCO = 30;  // a curva de permanência para quando restam menos passagens que isso
const MARCOS_DIAS = [[0, "chegada"], [7, "7 dias"], [15, "15 dias"], [30, "30 dias"], [60, "60 dias"],
                     [90, "90 dias"], [180, "180 dias"], [365, "1 ano"], [730, "2 anos"], [1095, "3 anos"]];

function grupoDaArea(area) {
  if (area == null) return "outros";
  if (ORDEM_COMISSOES.includes(area)) return "comissao";
  if (area === "SGP21") return "plenario";
  if (area === "SGP12") return "secretaria";
  if (area === "SGP22") return "controle";
  if (area.startsWith("SGP")) return "sgp";
  if (area === "ARQUIVO" || area === "TRAMITAÇÃO ENCERRADA") return "arquivo";
  if (area === "PROC-CMSP") return "procuradoria";
  return "outros";
}

async function carregarFluxos() {
  if (!cache.fluxos) {
    const r = await fetch("dados/fluxos.json");
    if (!r.ok) throw new Error(`não foi possível carregar dados/fluxos.json (${r.status})`);
    const f = await r.json();
    f.inicioObj = utc(f.inicio);
    f.fimDia = dataParaDia(f, utc(f.fim));
    const area = (i) => (i == null ? null : f.areas[i]);
    f.grupoOrigem = f.origem.map((i) => grupoDaArea(area(i)));
    f.grupoDestino = f.destino.map((i) => grupoDaArea(area(i)));
    f.areaDestino = f.destino.map(area);
    cache.fluxos = f;
  }
  return cache.fluxos;
}

const diaParaData = (f, dia) => new Date(f.inicioObj.getTime() + dia * DIA);
const dataParaDia = (f, data) => Math.round((data - f.inicioObj) / DIA);
const porcentoInteiro = (v) => (v == null ? "—" : v > 0 && v < 0.005 ? "<1%" : `${Math.round(v * 100)}%`);

// Passagens do recorte: grupo de matérias e, se `todas` for falso, a comissão escolhida.
function* passagensDoRecorte(f, todas = false) {
  const so = estado.grupo === "projetos";
  const sel = todas || estado.comissao === "TODAS" ? -1 : f.comissoes.indexOf(estado.comissao);
  for (let i = 0; i < f.comissao.length; i++) {
    if ((so && !f.projeto[i]) || (sel >= 0 && f.comissao[i] !== sel)) continue;
    yield i;
  }
}

function janelaFluxos(f) {
  const [inicio, fim] = periodoEscolhido(diaParaData(f, f.fimDia));
  return [dataParaDia(f, inicio), dataParaDia(f, fim)];
}

// Arquivamento de fim de legislatura (art. 275 do Regimento Interno): não é decisão da
// comissão, então a passagem conta como observada só até ali.
const arquivamentoDeLegislatura = (f, i) => f.fim_legislatura[i] === 1;

// ----------------------------------------------------------------------------- entradas e saídas
function contarFluxos(f, inicio, fim) {
  const semanal = fim - inicio <= 120;
  const passo = semanal ? d3.utcMonday : d3.utcMonth;
  const primeira = passo.floor(diaParaData(f, inicio));
  const faixas = passo.range(primeira, diaParaData(f, fim + 1)).map((a) => {
    const b = passo.offset(a, 1);
    const vazio = () => Object.fromEntries(AREAS.map((k) => [k.chave, 0]));
    return { a, b, meio: new Date((+a + +b) / 2), parcial: dataParaDia(f, b) - 1 > fim,
             entradas: vazio(), saidas: vazio() };
  });
  const limites = faixas.map((x) => dataParaDia(f, x.a));
  const todas = estado.comissao === "TODAS";
  for (const i of passagensDoRecorte(f)) {
    const de = f.desde[i];
    const ate = f.ate[i];
    // Nas 7 comissões juntas, a troca de uma comissão para outra não muda o acervo.
    if (de != null && de >= limites[0] && de <= fim && !(todas && f.grupoOrigem[i] === "comissao")) {
      faixas[d3.bisectRight(limites, de) - 1].entradas[f.grupoOrigem[i]]++;
    }
    if (ate != null && ate >= limites[0] && ate <= fim && !(todas && f.grupoDestino[i] === "comissao")) {
      faixas[d3.bisectRight(limites, ate) - 1].saidas[f.grupoDestino[i]]++;
    }
  }
  for (const x of faixas) {
    x.totalEntradas = d3.sum(AREAS, (k) => x.entradas[k.chave]);
    x.totalSaidas = d3.sum(AREAS, (k) => x.saidas[k.chave]);
    x.saldo = x.totalEntradas - x.totalSaidas;
    x.rotulo = semanal
      ? `semana de ${dataBR(x.a).slice(0, 5)} a ${dataBR(new Date(x.b - DIA))}`
      : `${MESES_LONGOS[x.a.getUTCMonth()]} de ${x.a.getUTCFullYear()}`;
  }
  return { semanal, faixas };
}

function graficoFluxo(alvo, faixas, categorias, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const segmentos = [];
  for (const x of faixas) {
    let acima = 0;
    let abaixo = 0;
    for (const k of categorias) {
      const e = x.entradas[k.chave];
      const s = x.saidas[k.chave];
      if (e) segmentos.push({ x, y1: acima, y2: (acima += e), k: k.nome });
      if (s) segmentos.push({ x, y1: -abaixo, y2: -(abaixo += s), k: k.nome });
    }
  }
  // O vaivém do fim de legislatura (arquivamento em janeiro, desarquivamento nos meses
  // seguintes) chega a dez vezes um mês comum: as barras fora do padrão são cortadas e
  // ganham o valor escrito, para não achatar o resto do gráfico.
  const alturas = faixas.flatMap((x) => [x.totalEntradas, x.totalSaidas]).filter((v) => v > 0).sort(d3.ascending);
  let teto = Infinity;
  const [q1, q3] = [d3.quantileSorted(alturas, 0.25), d3.quantileSorted(alturas, 0.75)];
  if (alturas.length >= 8 && q3 > q1) {
    const normal = d3.max(alturas.filter((v) => v <= q3 + 3 * (q3 - q1)));
    teto = normal * 1.1;
    for (const v of alturas) if (v > teto && v <= teto * 1.15) teto = v * 1.02;  // não corta por pouco
    if (alturas[alturas.length - 1] <= Math.max(teto, 2 * normal)) teto = Infinity;  // só corta o que destoa muito
  }
  let dominio = [-Math.min(teto, d3.max(faixas, (x) => x.totalSaidas) || 1),
                 Math.min(teto, d3.max(faixas, (x) => x.totalEntradas) || 1)];
  if (teto === Infinity) dominio = d3.scaleLinear().domain(dominio).nice(6).domain();
  const [baixo, alto] = dominio;
  // Valor das barras cortadas, junto à borda; vizinhas cortadas descem (ou sobem) um degrau.
  const pixelsPorUnidade = (opcoes.altura - 22 - 26) / (alto - baixo);
  const pixelX = (d) => ((d - faixas[0].a) / (faixas[faixas.length - 1].b - faixas[0].a)) * (largura - 48 - MARGEM_DIREITA);
  const cortes = [];
  for (const [lado, borda, sinal] of [["totalEntradas", alto, -1], ["totalSaidas", baixo, 1]]) {
    let anterior = -Infinity;
    let degrau = 0;
    faixas.forEach((x) => {
      if (x[lado] <= Math.abs(borda)) return;
      degrau = pixelX(x.meio) - anterior < 60 ? degrau + 1 : 0;
      anterior = pixelX(x.meio);
      cortes.push({ x: x.meio, y: borda + (sinal * (10 + 14 * degrau)) / pixelsPorUnidade,
                    texto: `${sinal < 0 ? "▲" : "▼"} ${fmt(x[lado])}` });
    });
  }

  const datas = [faixas[0].a, faixas[faixas.length - 1].b];
  const m = moldura(c, datas, largura, opcoes.altura, { marginRight: MARGEM_DIREITA, yTicks: 6 });
  m.opcoes.y = { domain: dominio, nice: false };
  m.eixos[1] = Plot.axisY({ ticks: 6, tickSize: 0, tickPadding: 6, tickFormat: (v) => numero.format(Math.abs(v)),
                            fill: c.tinta3, label: null });
  const vao = (largura - 48 - MARGEM_DIREITA) / faixas.length > 5 ? 1 : 0;
  const svg = Plot.plot({
    ...m.opcoes,
    color: { domain: categorias.map((k) => k.nome), range: categorias.map((k) => c.v(k.cor)) },
    marks: [
      ...m.eixos,
      Plot.rect(segmentos, { x1: (s) => s.x.a, x2: (s) => s.x.b, y1: "y1", y2: "y2", fill: "k",
        fillOpacity: (s) => (s.x.parcial ? 0.5 : 1), insetLeft: vao, insetRight: vao, clip: true }),
      Plot.ruleY([0], { stroke: c.base }),
      ...marcos(datas, c, opcoes.inicioColeta, largura),
      Plot.text(cortes, { x: "x", y: "y", text: "texto", dx: 6, textAnchor: "start", fill: c.tinta, fontWeight: 600,
        stroke: c.superficie, strokeWidth: 3, paintOrder: "stroke" }),
      Plot.text(["entradas"], { frameAnchor: "left", y: alto / 2, dx: -40, rotate: -90, fill: c.tinta2, fontSize: 11 }),
      Plot.text(["saídas"], { frameAnchor: "left", y: baixo / 2, dx: -40, rotate: -90, fill: c.tinta2, fontSize: 11 }),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, faixas.map((x) => x.meio), (i) => {
    const x = faixas[i];
    const linhas = [{ secao: "Entradas" }];
    for (const k of categorias) if (x.entradas[k.chave]) linhas.push({ cor: c.v(k.cor), quadrado: true, valor: fmt(x.entradas[k.chave]), nome: k.nome });
    linhas.push({ total: true, valor: fmt(x.totalEntradas), nome: "entradas" }, { secao: "Saídas" });
    for (const k of categorias) if (x.saidas[k.chave]) linhas.push({ cor: c.v(k.cor), quadrado: true, valor: fmt(x.saidas[k.chave]), nome: k.nome });
    linhas.push({ total: true, valor: fmt(x.totalSaidas), nome: "saídas" },
                { total: true, valor: `${x.saldo > 0 ? "+" : x.saldo < 0 ? "−" : ""}${fmt(Math.abs(x.saldo))}`, nome: "saldo" });
    return { titulo: x.parcial ? `${x.rotulo} (até ${dataBR(opcoes.ultimoDia)})` : x.rotulo, linhas };
  });
}

function renderFluxo(f, nomes) {
  const cartao = document.getElementById("c-fluxo");
  const todas = estado.comissao === "TODAS";
  const categorias = AREAS.filter((k) => !(todas && k.chave === "comissao"));
  const [inicio, fim] = janelaFluxos(f);
  const { semanal, faixas } = contarFluxos(f, inicio, fim);
  document.getElementById("sub-fluxo").textContent = todas
    ? `${nomes.grupo} que chegaram às 7 comissões e que saíram delas, ${semanal ? "por semana" : "por mês"}, pela área de origem e de destino. As trocas entre comissões não mudam o acervo das 7 juntas e ficam de fora; estão no gráfico de rotas.`
    : `${nomes.grupo} que chegaram ${nomes.comissao.replace(/^da /, "à ")} e que saíram dela, ${semanal ? "por semana" : "por mês"}, pela área de origem e de destino.`;
  legenda(cartao, categorias);
  const colunas = [{ nome: semanal ? "semana" : "mês" },
    ...categorias.map((k) => ({ nome: `entradas: ${k.nome}` })), { nome: "entradas" },
    ...categorias.map((k) => ({ nome: `saídas: ${k.nome}` })), { nome: "saídas" }, { nome: "saldo" }];
  const linhas = faixas.map((x) => [semanal ? dataISO(x.a) : dataISO(x.a).slice(0, 7),
    ...categorias.map((k) => x.entradas[k.chave]), x.totalEntradas,
    ...categorias.map((k) => x.saidas[k.chave]), x.totalSaidas, x.saldo]);
  acoesTabela(cartao, colunas, linhas, `fluxo-${estado.comissao.toLowerCase()}-${estado.grupo}.csv`);
  if (cartao.dataset.tabela === "1") return;
  const maior = faixas.reduce((a, x) => (x.totalSaidas > a.totalSaidas ? x : a), faixas[0]);
  graficoFluxo(cartao.querySelector(".grafico"), faixas, categorias, {
    altura: 320, inicioColeta: f.inicio_coleta, ultimoDia: diaParaData(f, f.fimDia),
    descricao: `Entradas e saídas ${nomes.comissao} ${semanal ? "por semana" : "por mês"}, ${textoPeriodo()}. ` +
      `${fmt(d3.sum(faixas, (x) => x.totalEntradas))} entradas e ${fmt(d3.sum(faixas, (x) => x.totalSaidas))} saídas no período; ` +
      `o maior número de saídas foi em ${maior.rotulo}, com ${fmt(maior.totalSaidas)}.` });
}

// ----------------------------------------------------------------------------- permanência
// Estimador de Kaplan-Meier: fração das passagens que continua na comissão depois de t dias.
// Passagens ainda no acervo e arquivadas no fim da legislatura contam até onde foram vistas.
function permanencia(duracoes, saiu, maxDia) {
  const saidas = new Int32Array(maxDia + 2);
  const fimDaObservacao = new Int32Array(maxDia + 2);
  for (let k = 0; k < duracoes.length; k++) {
    const d = Math.min(Math.max(duracoes[k], 0), maxDia + 1);
    (saiu[k] ? saidas : fimDaObservacao)[d]++;
  }
  const s = new Float64Array(maxDia + 1);
  let emRisco = duracoes.length;
  let fracao = 1;
  let ultimo = -1;
  for (let t = 0; t <= maxDia; t++) {
    if (emRisco < MINIMO_EM_RISCO) break;
    fracao *= 1 - saidas[t] / emRisco;
    s[t] = fracao;
    ultimo = t;
    emRisco -= saidas[t] + fimDaObservacao[t];
  }
  const mediana = ultimo < 0 ? null : s.findIndex((v, t) => t <= ultimo && v <= 0.5);
  return { s, ultimo, mediana: mediana === -1 ? null : mediana };
}

// Uma curva por comissão (e Todas) ou, com `porAutoria`, uma por autoria na comissão escolhida.
function curvasDePermanencia(f, porAutoria = false) {
  const [inicio, fim] = janelaFluxos(f);
  const maxDia = Math.min(3 * 365, fim - inicio);
  const chaves = porAutoria ? [TODAS_AUTORIAS, ...AUTORIAS_CURVAS] : ["TODAS", ...f.comissoes];
  const grupos = new Map(chaves.map((s) => [s, { d: [], e: [] }]));
  for (const i of passagensDoRecorte(f, !porAutoria)) {
    const de = f.desde[i];
    if (de == null || de < inicio || de > fim) continue;
    const ate = f.ate[i];
    const saiu = ate != null && !arquivamentoDeLegislatura(f, i);
    const dur = (ate ?? fim) - de;
    const proprio = porAutoria ? grupos.get(f.autorias[f.autoria[i]]) : grupos.get(f.comissoes[f.comissao[i]]);
    for (const g of [grupos.get(chaves[0]), proprio]) {
      if (!g) continue;
      g.d.push(dur);
      g.e.push(saiu);
    }
  }
  return [...grupos].map(([sigla, g]) => ({ sigla, n: g.d.length, ...permanencia(g.d, g.e, maxDia) }));
}

function rotuloDias(t) {
  if (t === 0) return "na chegada";
  if (t % 365 === 0) return t === 365 ? "1 ano" : `${t / 365} anos`;
  return `${fmt(t)} ${t === 1 ? "dia" : "dias"}`;
}

function graficoPermanencia(alvo, curvas, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const ate = d3.max(curvas, (cv) => cv.ultimo);
  const destaque = curvas.find((cv) => cv.sigla === opcoes.destaque);
  const margens = { marginTop: 16, marginRight: MARGEM_DIREITA, marginBottom: 26, marginLeft: 48 };
  const px = (p) => (p.x * (largura - margens.marginLeft - margens.marginRight)) / ate;
  const py = (p) => (1 - p.y) * (opcoes.altura - margens.marginTop - margens.marginBottom);
  const pontosDe = (cv) => Array.from({ length: cv.ultimo + 1 }, (_, t) => ({ x: t, y: cv.s[t] }));
  const ticks = [];
  for (const [t] of MARCOS_DIAS) if (t <= ate && (!ticks.length || px({ x: t }) - px({ x: ticks[ticks.length - 1] }) >= 64)) ticks.push(t);
  const estilo = opcoes.estilo ?? estiloComissao(c, opcoes.destaque);
  const nome = opcoes.nome ?? rotuloComissao;
  const med = opcoes.semMediana ? null : destaque.mediana;
  const corDestaque = estilo(opcoes.destaque).cor;
  const svg = Plot.plot({
    width: largura, height: opcoes.altura, ...margens,
    style: { fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", fontSize: "12px",
             background: "transparent", color: c.tinta3, overflow: "visible" },
    x: { domain: [0, ate] },
    y: { domain: [0, 1] },
    marks: [
      Plot.gridY({ ticks: [0, 0.25, 0.5, 0.75, 1], stroke: c.grade, strokeOpacity: 1 }),
      Plot.axisY({ ticks: [0, 0.25, 0.5, 0.75, 1], tickSize: 0, tickPadding: 6, tickFormat: (v) => `${v * 100}%`,
                   fill: c.tinta3, label: null }),
      Plot.axisX({ ticks, tickFormat: (t) => MARCOS_DIAS.find(([d]) => d === t)[1], tickSize: 0, tickPadding: 8,
                   fill: c.tinta3, label: null }),
      Plot.ruleY([0], { stroke: c.base }),
      Plot.ruleY([0.5], { stroke: c.tinta3, strokeDasharray: "3 3", strokeOpacity: 0.8 }),
      ...marcasComissoes(c, curvas, opcoes.destaque, pontosDe, px, py, (p) => nome(p.sigla), estilo),
      ...(med != null ? [
        Plot.dot([{ t: med, v: 0.5 }], { x: "t", y: "v", r: 4.5, fill: corDestaque, stroke: c.superficie, strokeWidth: 2 }),
        Plot.text([{ t: med, v: 0.5 }], { x: "t", y: "v", dy: -12, fill: c.tinta, fontWeight: 600,
          // perto do fim do eixo, o texto vai para a esquerda do ponto
          ...(med > ate * 0.6 ? { dx: -8, textAnchor: "end" } : { dx: 8, textAnchor: "start" }),
          text: () => `${nome(opcoes.destaque)}: metade saiu em ${rotuloDias(med)}`,
          stroke: c.superficie, strokeWidth: 3, paintOrder: "stroke" }),
      ] : []),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, d3.range(0, ate + 1), (t) => ({
    titulo: t === 0 ? "Ainda na comissão no dia da chegada" : `Ainda na comissão depois de ${rotuloDias(t)}`,
    linhas: linhasDaDica(c, curvas, opcoes.destaque, (cv) => (t <= cv.ultimo ? cv.s[t] : null), porcentoInteiro,
                         () => "", { estilo, nome: opcoes.nome }),
  }));
}

function renderPermanencia(f, nomes) {
  const cartao = document.getElementById("c-permanencia");
  const porAutoria = cartao.dataset.modo === "autoria";
  for (const b of cartao.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === (porAutoria ? "autoria" : "comissao")));
    b.onclick = () => { cartao.dataset.modo = b.dataset.modo; render(); };
  }
  const curvas = curvasDePermanencia(f, porAutoria).filter((cv) => !porAutoria || cv.ultimo >= 1);
  const chaveDestaque = porAutoria ? TODAS_AUTORIAS : estado.comissao;
  const destaque = curvas.find((cv) => cv.sigla === chaveDestaque);
  const onde = nomes.comissao.replace(/^da /, "na ").replace(/^das /, "nas ");
  const medianas = curvas.filter((cv) => cv.sigla !== TODAS_AUTORIAS)
    .map((cv) => `${cv.mediana != null ? rotuloDias(cv.mediana) : `mais de ${rotuloDias(cv.ultimo)}`} (${cv.sigla})`);
  document.getElementById("sub-permanencia").textContent = porAutoria
    ? `Das passagens que começaram ${textoPeriodo()} ${onde}, quantas ainda estavam lá depois de cada tempo, pelo ` +
      `primeiro autor da matéria. Metade saiu em ${medianas.join(", ").replace(/, ([^,]*)$/, " e $1")}.`
    : `Das passagens que começaram ${textoPeriodo()}, quantas ainda estavam na comissão depois de cada tempo. ` +
      "A linha tracejada marca a metade: onde a curva a cruza está o tempo mediano.";
  if (porAutoria) legendaAutorias(cartao);
  else legendaComissoes(cartao);
  const ate = d3.max(curvas, (cv) => cv.ultimo);
  const dias = MARCOS_DIAS.map(([t]) => t).filter((t) => t > 0 && t <= ate);
  const nome = (s) => (porAutoria ? nomeAutoria(s).toLowerCase() : s === "TODAS" ? "todas" : s === "SAUDE" ? "SAÚDE" : s);
  const colunas = [{ nome: "depois de" }, ...curvas.map((cv) => ({ nome: `${nome(cv.sigla)} (%)` }))];
  const linhas = [
    ...dias.map((t) => [rotuloDias(t), ...curvas.map((cv) => (t <= cv.ultimo ? Math.round(cv.s[t] * 1000) / 10 : null))]),
    ["mediana (dias)", ...curvas.map((cv) => cv.mediana)],
    ["passagens", ...curvas.map((cv) => cv.n)],
  ];
  acoesTabela(cartao, colunas, linhas, `permanencia-${porAutoria ? `autoria-${estado.comissao.toLowerCase()}-` : ""}` +
              `${estado.grupo}-${estado.periodo}.csv`, { recentesPrimeiro: false });
  const grafico = cartao.querySelector(".grafico");
  if (cartao.dataset.tabela === "1") return;
  if (!destaque || destaque.ultimo < 1) {
    grafico.replaceChildren(el("p", "vazio", "Poucas passagens neste recorte para estimar a permanência."));
    return;
  }
  graficoPermanencia(grafico, curvas, {
    altura: 300, destaque: chaveDestaque,
    ...(porAutoria ? { estilo: estiloAutoria(cores()), nome: nomeAutoria, semMediana: true } : {}),
    descricao: `Permanência na comissão ${nomes.comissao}${porAutoria ? ", por autoria" : ""}: ` + (destaque.mediana != null
      ? `metade das passagens saiu em ${rotuloDias(destaque.mediana)}.`
      : `mais da metade ainda estava lá depois de ${rotuloDias(destaque.ultimo)}.`) });
}

// ----------------------------------------------------------------------------- rotas
function renderRotas(f) {
  const cartao = document.getElementById("c-rotas");
  const modo = cartao.dataset.modo || "percentual";
  for (const b of cartao.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === modo));
    b.onclick = () => { cartao.dataset.modo = b.dataset.modo; renderRotas(f); };
  }
  const [inicio, fim] = janelaFluxos(f);
  const colunas = [...ORDEM_COMISSOES.map((s) => ({ chave: s, nome: s === "SAUDE" ? "SAÚDE" : s, titulo: s })),
                   ...AREAS.slice(1).map((k) => ({ chave: k.chave, nome: k.curto, titulo: k.nome }))];
  const contagem = new Map(ORDEM_COMISSOES.map((s) => [s, new Map(colunas.map((col) => [col.chave, 0]))]));
  for (const i of passagensDoRecorte(f, true)) {
    const ate = f.ate[i];
    if (ate == null || ate < inicio || ate > fim) continue;
    const destino = f.grupoDestino[i] === "comissao" ? f.areaDestino[i] : f.grupoDestino[i];
    const linha = contagem.get(f.comissoes[f.comissao[i]]);
    linha.set(destino, linha.get(destino) + 1);
  }
  const totais = new Map([...contagem].map(([s, linha]) => [s, d3.sum(linha.values())]));
  const valor = (s, chave) => (modo === "contagem" ? contagem.get(s).get(chave)
    : totais.get(s) ? contagem.get(s).get(chave) / totais.get(s) : 0);
  const maximo = d3.max(ORDEM_COMISSOES, (s) => d3.max(colunas, (col) => valor(s, col.chave))) || 1;
  const c = cores();
  // Rampa sequencial que parte quase da cor do fundo, para os valores pequenos ficarem discretos.
  const rampa = d3.interpolateRgbBasis([d3.interpolateRgb(c.superficie, c.v("--idade-1"))(0.3),
    ...["--idade-1", "--idade-2", "--idade-3", "--idade-4", "--idade-5"].map(c.v)]);

  document.getElementById("sub-rotas").textContent =
    `Saídas ${textoPeriodo()}, de cada comissão (linhas) para cada destino (colunas)` +
    (modo === "percentual" ? "; cada linha soma 100%." : ".") +
    (estado.grupo === "projetos" ? " Só projetos." : "");
  const tabela = el("table", estado.comissao === "TODAS" ? "matriz" : "matriz com-selecao");
  const cab = el("tr");
  cab.append(el("th", null, "de ↓ · para →"));
  for (const col of colunas) {
    const th = el("th", null, col.nome);
    th.scope = "col";
    th.title = col.titulo;
    cab.append(th);
  }
  const thTotal = el("th", "total", "Saídas");
  thTotal.scope = "col";
  cab.append(thTotal);
  tabela.append(el("thead"), el("tbody"));
  tabela.tHead.append(cab);
  for (const s of ORDEM_COMISSOES) {
    const tr = el("tr", s === estado.comissao ? "selecionada" : null);
    const th = el("th", null, s === "SAUDE" ? "SAÚDE" : s);
    th.scope = "row";
    th.title = COMISSOES.find(([sigla]) => sigla === s)[1];
    tr.append(th);
    for (const col of colunas) {
      const n = contagem.get(s).get(col.chave);
      const v = valor(s, col.chave);
      const diagonal = col.chave === s;
      const td = el("td", n && !diagonal ? null : "vazia", diagonal ? "—" : !n ? "·" : modo === "contagem" ? fmt(n) : porcentoInteiro(v));
      if (n && !diagonal) {
        const fundoCor = d3.color(rampa(Math.min(1, v / maximo)));
        td.style.background = fundoCor.formatHex();
        const { r, g, b } = fundoCor.rgb();
        td.style.color = 0.2126 * r + 0.7152 * g + 0.0722 * b < 140 ? "#fff" : "#0b0b0b";
        td.title = `${s} → ${col.titulo}: ${fmt(n)} de ${fmt(totais.get(s))} saídas (${porcentoInteiro(n / totais.get(s))})`;
      }
      tr.append(td);
    }
    tr.append(el("td", "total", fmt(totais.get(s))));
    tabela.tBodies[0].append(tr);
  }
  const caixa = cartao.querySelector(".matriz-caixa");
  caixa.replaceChildren(tabela);

  const botaoCsv = el("button", "botao", "Baixar CSV");
  botaoCsv.type = "button";
  botaoCsv.addEventListener("click", () => baixarTabela(["de", ...colunas.map((col) => col.titulo), "saídas"],
    ORDEM_COMISSOES.map((s) => [s, ...colunas.map((col) => contagem.get(s).get(col.chave)), totais.get(s)]),
    `rotas-${estado.grupo}-${estado.periodo}.csv`));
  cartao.querySelector(".acoes-csv").replaceChildren(botaoCsv);
}

// ----------------------------------------------------------------------------- votações e tempo das etapas
/* Dados em dados/tramitacao.json (painel/etapas.py): votações por mês e mediana do tempo de
   cada etapa por ano, por grupo × comissão. */
const VOTACOES = [
  { chave: "votadas", nome: "Votada na comissão", cor: "--s1" },
  { chave: "conjunta", nome: "Aprovada em reunião conjunta", cor: "--s2" },
];
const ESTAGIOS = [
  { chave: "relator", nome: "Da chegada ao relator", cor: "--s1" },
  { chave: "estudo", nome: "Do relator à pauta", cor: "--s2" },
  { chave: "pauta", nome: "Da pauta à votação", cor: "--s3" },
];

async function carregarTramitacao() {
  if (!cache.tramitacao) {
    const r = await fetch("dados/tramitacao.json");
    if (!r.ok) throw new Error(`não foi possível carregar dados/tramitacao.json (${r.status})`);
    cache.tramitacao = await r.json();
  }
  return cache.tramitacao;
}

const mesParaData = (mes) => utc(`${mes}-01`);
const rotuloMes = (d) => `${MESES_LONGOS[d.getUTCMonth()]} de ${d.getUTCFullYear()}`;

// Barras empilhadas por mês, com uma linha de média (mesma escala).
function graficoBarrasMes(alvo, faixas, camadas, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const segmentos = [];
  for (const x of faixas) {
    let acima = 0;
    for (const k of camadas) {
      const v = x.valores[k.chave];
      if (v) segmentos.push({ x, y1: acima, y2: (acima += v), k: k.nome });
    }
  }
  const datas = [faixas[0].a, faixas[faixas.length - 1].b];
  // Em `percentual`, cada barra vai a 100%: a altura é a parte de cada camada no total.
  if (opcoes.percentual) {
    for (const sg of segmentos) {
      const t = sg.x.total || 1;
      sg.y1 = (100 * sg.y1) / t;
      sg.y2 = (100 * sg.y2) / t;
    }
  }
  const maximo = opcoes.percentual ? 100 : d3.max(faixas, (x) => Math.max(x.total, x.media ?? 0)) || 1;
  const m = moldura(c, datas, largura, opcoes.altura, { yDomain: [0, maximo], marginRight: MARGEM_DIREITA });
  if (opcoes.percentual) {
    m.eixos[1] = Plot.axisY({ ticks: 5, tickSize: 0, tickPadding: 6, tickFormat: (v) => `${v}%`, fill: c.tinta3, label: null });
  }
  if (opcoes.anual) {  // um rótulo no meio de cada barra, com o ano
    const cabe = (largura - 48 - MARGEM_DIREITA) / faixas.length > 34;
    m.eixos[2] = Plot.axisX({ ticks: faixas.filter((_, i) => cabe || (faixas.length - 1 - i) % 2 === 0)
      .map((x) => x.meio), tickFormat: (d) => String(d.getUTCFullYear()), tickSize: 0, tickPadding: 8, fill: c.tinta3, label: null });
  }
  const vao = (largura - 48 - MARGEM_DIREITA) / faixas.length > 5 ? 1 : 0;
  const comMedia = faixas.filter((x) => x.media != null);
  const svg = Plot.plot({
    ...m.opcoes,
    color: { domain: camadas.map((k) => k.nome), range: camadas.map((k) => c.v(k.cor)) },
    marks: [
      ...m.eixos,
      Plot.rect(segmentos, { x1: (s) => s.x.a, x2: (s) => s.x.b, y1: "y1", y2: "y2", fill: "k",
        fillOpacity: (s) => (s.x.parcial ? 0.5 : 1), insetLeft: vao, insetRight: vao }),
      Plot.ruleY([0], { stroke: c.base }),
      Plot.line(comMedia, { x: "meio", y: "media", stroke: c.tinta, strokeWidth: 1.5, strokeLinejoin: "round" }),
      ...(opcoes.marcos === false ? [] : marcos(datas, c, opcoes.inicioColeta, largura)),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, faixas.map((x) => x.meio), (i) => {
    const x = faixas[i];
    return {
      titulo: opcoes.titulo ? opcoes.titulo(x) : x.parcial ? `${rotuloMes(x.a)} (até ${dataBR(opcoes.ultimoDia)})` : rotuloMes(x.a),
      linhas: [
        ...camadas.filter((k) => !opcoes.soPresentes || x.valores[k.chave]).map((k) => ({
          cor: c.v(k.cor), quadrado: true, valor: fmt(x.valores[k.chave]),
          nome: opcoes.mostrarParte && x.total ? `${k.nome} (${porcentoInteiro(x.valores[k.chave] / x.total)})` : k.nome })),
        { total: true, valor: fmt(x.total), nome: opcoes.rotuloTotal ?? "no mês" },
        ...(x.media != null ? [{ total: true, valor: fmt(Math.round(x.media)), nome: "média dos 12 meses até aqui" }] : []),
      ],
    };
  });
}

function renderProducao(t, nomes, ultimoDia) {
  const cartao = document.getElementById("c-producao");
  const serie = t.producao[estado.grupo][estado.comissao];
  const ultimoMes = t.meses[t.meses.length - 1];
  const parcial = dataISO(ultimoDia) < dataISO(new Date(d3.utcMonth.offset(mesParaData(ultimoMes), 1) - DIA));
  const totais = t.meses.map((_, i) => serie.votadas[i] + serie.conjunta[i]);
  // Média móvel de 12 meses completos (tira o efeito dos recessos de janeiro e julho).
  const completos = parcial ? t.meses.length - 1 : t.meses.length;
  const media = t.meses.map((_, i) => (i >= 11 && i < completos ? d3.mean(totais.slice(i - 11, i + 1)) : null));
  const [i0, i1] = mesesDoPeriodo(t.meses);
  const faixas = t.meses.slice(i0, i1).map((mes, k) => {
    const i = i0 + k;
    const a = mesParaData(mes);
    const b = d3.utcMonth.offset(a, 1);
    return { a, b, meio: new Date((+a + +b) / 2), parcial: parcial && i === t.meses.length - 1, total: totais[i],
             media: media[i], valores: { votadas: serie.votadas[i], conjunta: serie.conjunta[i] } };
  });
  const votados = estado.grupo === "projetos" ? "Projetos votados" : "Matérias votadas";
  const onde = nomes.comissao.replace(/^da /, "na ").replace(/^das /, "nas ");
  document.getElementById("sub-producao").textContent =
    `${votados} ${onde} por mês. ` +
    (estado.comissao === "TODAS" ? "Uma matéria votada em duas comissões conta duas vezes. " : "") +
    "A linha é a média dos 12 meses anteriores, que tira o efeito dos recessos.";
  legenda(cartao, [...VOTACOES, { nome: "Média de 12 meses", cor: "--tinta", linha: true }]);
  acoesTabela(cartao, [{ nome: "mês" }, ...VOTACOES.map((k) => ({ nome: k.nome.toLowerCase() })), { nome: "total" },
                       { nome: "média de 12 meses" }],
              faixas.map((x) => [dataISO(x.a).slice(0, 7), x.valores.votadas, x.valores.conjunta, x.total,
                                  x.media == null ? null : Math.round(x.media)]),
              `votacoes-${estado.comissao.toLowerCase()}-${estado.grupo}.csv`);
  if (cartao.dataset.tabela === "1") return;
  const ultimoAno = faixas.filter((x) => !x.parcial).slice(-12);
  graficoBarrasMes(cartao.querySelector(".grafico"), faixas, VOTACOES, {
    altura: 280, inicioColeta: t.inicio_coleta, ultimoDia,
    descricao: `${votados} ${onde} por mês, ${textoPeriodo()}. ` +
      `Nos últimos 12 meses completos, ${fmt(d3.sum(ultimoAno, (x) => x.total))} votações.` });
}

function renderTempos(t, nomes) {
  const cartao = document.getElementById("c-tempos");
  const serie = t.tempos[estado.grupo][estado.comissao];
  const anoAtual = t.anos[t.anos.length - 1];
  const datas = t.anos.map((a) => utc(`${a}-01-01`));
  const series = ESTAGIOS.map((k) => ({ ...k, valores: serie[k.chave].mediana, linha: true, pontos: true }));
  const onde = nomes.comissao.replace(/^da /, "na ").replace(/^das /, "nas ");
  document.getElementById("sub-tempos").textContent =
    `Mediana, em dias, de cada etapa ${onde}, pelo ano em que ela terminou. ` +
    "Só entram as etapas que terminaram; o filtro de período não se aplica.";
  legenda(cartao, series);
  const colunas = [{ nome: "ano" }];
  for (const k of ESTAGIOS) {
    const nome = k.nome.toLowerCase();
    colunas.push({ nome: `${nome}: mediana (dias)` }, { nome: `${nome}: 1º quartil` },
                 { nome: `${nome}: 3º quartil` }, { nome: `${nome}: etapas` });
  }
  acoesTabela(cartao, colunas, t.anos.map((a, i) => [String(a), ...ESTAGIOS.flatMap((k) =>
    [serie[k.chave].mediana[i], serie[k.chave].p25[i], serie[k.chave].p75[i], serie[k.chave].n[i]])]),
    `etapas-${estado.comissao.toLowerCase()}-${estado.grupo}.csv`);
  if (cartao.dataset.tabela === "1") return;
  const dias = (v) => `${fmt(v)} ${v === 1 ? "dia" : "dias"}`;
  graficoLinhas(cartao.querySelector(".grafico"), datas, series, {
    altura: 260, marcos: false, formato: dias,
    titulo: (i) => (t.anos[i] === anoAtual ? `${anoAtual} (até agora)` : String(t.anos[i])),
    detalhe: (s, i) => {
      const x = serie[s.chave];
      return `— metade entre ${fmt(x.p25[i])} e ${fmt(x.p75[i])}; ${fmt(x.n[i])} etapas`;
    },
    descricao: `Mediana de cada etapa ${onde}, por ano. ` + ESTAGIOS.map((k) =>
      `${k.nome}: ${serie[k.chave].mediana.map((v, i) => `${t.anos[i]} ${v ?? "—"}`).join(", ")}`).join("; ") + "." });
}

// Calendário: votações ou passos internos em cada dia de um ano, como no GitHub.
const DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];
const DIAS_SEMANA_LONGOS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira",
                            "sábado", "domingo"];
const METRICAS_CALENDARIO = { votos: ["votação", "votações"], passos: ["passo interno", "passos internos"] };

function diasDoCalendario(lista, inicio) {
  const valores = new Map();
  let dia = 0;
  for (let k = 0; k < lista.length; k += 2) {
    dia += lista[k];
    valores.set(dataISO(new Date(inicio.getTime() + dia * DIA)), lista[k + 1]);
  }
  return valores;
}

function renderCalendario(t, ultimoDia) {
  const cartao = document.getElementById("c-calendario");
  const metrica = cartao.dataset.metrica === "votos" ? "votos" : "passos";
  for (const b of cartao.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.metrica === metrica));
    b.onclick = () => { cartao.dataset.metrica = b.dataset.metrica; renderCalendario(t, ultimoDia); };
  }
  const inicio = utc(t.calendario.inicio);
  const anos = d3.range(ultimoDia.getUTCFullYear(), inicio.getUTCFullYear() - 1, -1);
  const ano = anos.includes(Number(cartao.dataset.ano)) ? Number(cartao.dataset.ano) : anos[0];
  const seletor = document.getElementById("f-ano-calendario");
  preencher(seletor, anos.map((a) => [String(a), String(a)]), String(ano));
  seletor.onchange = () => { cartao.dataset.ano = seletor.value; renderCalendario(t, ultimoDia); };

  const valores = diasDoCalendario(t.calendario[estado.grupo][estado.comissao][metrica], inicio);
  const [singular, plural] = METRICAS_CALENDARIO[metrica];
  const dias = d3.utcDay.range(utc(`${ano}-01-01`), utc(`${ano + 1}-01-01`))
    .map((d) => ({ d, v: d < inicio || d > ultimoDia ? null : valores.get(dataISO(d)) ?? 0 }));
  const positivos = dias.filter((x) => x.v > 0).map((x) => x.v);
  const classes = d3.scaleQuantile().domain(positivos.length ? positivos : [1]).range([1, 2, 3, 4, 5]);
  const onde = estado.comissao === "TODAS" ? "nas 7 comissões" : `na ${estado.comissao === "SAUDE" ? "SAÚDE" : estado.comissao}`;
  document.getElementById("sub-calendario").textContent =
    `${plural[0].toUpperCase()}${plural.slice(1)} ${onde} em cada dia de ${ano}: ${fmt(d3.sum(positivos))} no ano, ` +
    `em ${fmt(positivos.length)} dias. Os dias de reunião e os recessos aparecem como colunas e faixas.`;

  // Legenda: das faixas de valor, da menor para a maior.
  const faixas = d3.range(1, 6).map((k) => classes.invertExtent(k)).filter(([a, b]) => a != null && b != null);
  const legendaCal = cartao.querySelector(".legenda");
  const itens = [{ nome: "nenhum", cor: null }];
  let anterior = 0;
  faixas.forEach(([, b], k) => {
    const de = anterior + 1;
    const ate = Math.floor(b);
    if (ate >= de) itens.push({ nome: de === ate ? fmt(de) : `${fmt(de)} a ${fmt(ate)}`, cor: `--idade-${k + 1}` });
    anterior = Math.max(anterior, ate);
  });
  legendaCal.replaceChildren(...itens.map((k) => {
    const li = el("li");
    const amostra = el("span", k.cor ? "amostra" : "amostra vazio-cal");
    if (k.cor) amostra.style.background = cores().v(k.cor);
    li.append(amostra, document.createTextNode(k.nome));
    return li;
  }));

  acoesTabela(cartao, [{ nome: "data" }, { nome: plural }],
    dias.filter((x) => x.v != null).map((x) => [dataISO(x.d), x.v]),
    `calendario-${metrica}-${ano}-${estado.comissao.toLowerCase()}-${estado.grupo}.csv`);
  const caixa = cartao.querySelector(".calendario");
  if (cartao.dataset.tabela === "1") return;
  const primeiraSegunda = d3.utcMonday.floor(utc(`${ano}-01-01`));
  const semanas = d3.utcMonday.count(primeiraSegunda, utc(`${ano}-12-31`)) + 1;
  caixa.style.gridTemplateColumns = `28px repeat(${semanas}, minmax(9px, 1fr))`;
  const filhos = [];
  for (let mes = 0; mes < 12; mes++) {
    const d = utc(`${ano}-${String(mes + 1).padStart(2, "0")}-01`);
    const rotulo = el("span", "mes", MESES[mes]);
    rotulo.style.gridColumn = String(2 + Math.floor((d - primeiraSegunda) / (7 * DIA)));
    rotulo.style.gridRow = "1";
    filhos.push(rotulo);
  }
  [0, 2, 4].forEach((k) => {
    const rotulo = el("span", "dia-semana", DIAS_SEMANA[k]);
    rotulo.style.gridRow = String(k + 2);
    rotulo.style.gridColumn = "1";
    filhos.push(rotulo);
  });
  for (const x of dias) {
    const cel = el("span", "dia");
    const semana = Math.floor((x.d - primeiraSegunda) / (7 * DIA));
    const diaSemana = (x.d.getUTCDay() + 6) % 7;
    cel.style.gridColumn = String(semana + 2);
    cel.style.gridRow = String(diaSemana + 2);
    if (x.v == null) {
      cel.classList.add("fora");
    } else {
      const cor = x.v > 0 ? `--idade-${classes(x.v)}` : null;
      if (cor) cel.style.background = cores().v(cor);
      cel.dataset.titulo = `${DIAS_SEMANA_LONGOS[diaSemana]}, ${dataBR(x.d)}`;
      cel.dataset.n = fmt(x.v);
      cel.dataset.rotulo = x.v === 1 ? singular : plural;
      cel.dataset.cor = cor ?? "--grade";
    }
    filhos.push(cel);
  }
  caixa.replaceChildren(...filhos);
  if (ano === anos[0]) caixa.parentElement.scrollLeft = caixa.parentElement.scrollWidth;
}

// ----------------------------------------------------------------------------- pareceres, relatores e desfechos
/* Dados em dados/legislativo.json (painel/legislativo.py), tirados do webservice do SPLEGIS:
   pareceres por mês e conclusão, pareceres por relator e desfecho dos projetos por ano. */
const CONCLUSOES = [
  { chave: "favoravel", nome: "Favorável", cor: "--s1" },
  { chave: "legalidade", nome: "Pela legalidade", cor: "--s2" },
  { chave: "ilegalidade", nome: "Pela ilegalidade", cor: "--s3" },
  { chave: "contrario", nome: "Contrário", cor: "--s4" },
  { chave: "outros", nome: "Outras conclusões", cor: "--cinza-1" },
];
const DESFECHOS = [
  { chave: "lei", nome: "Virou lei", cor: "--s1" },
  { chave: "vetado", nome: "Vetado", cor: "--s2" },
  { chave: "rejeitado", nome: "Rejeitado ou ilegal", cor: "--s3" },
  { chave: "retirado", nome: "Retirado pelo autor", cor: "--s4" },
  { chave: "apensado", nome: "Apensado a outro", cor: "--s5" },
  { chave: "legislatura", nome: "Arquivado no fim da legislatura", cor: "--s6" },
  { chave: "outros", nome: "Outro encerramento", cor: "--cinza-1" },
  { chave: "aberto", nome: "Sem encerramento registrado", cor: "--cinza-2" },
];
const SAIDAS = [
  { chave: "votada", nome: "Votada na comissão", cor: "--s1" },
  { chave: "conjunta", nome: "Aprovada em reunião conjunta", cor: "--s2" },
  { chave: "retirada", nome: "Retirada pelo autor", cor: "--s3" },
  { chave: "apensada", nome: "Apensada a outra", cor: "--s4" },
  { chave: "prazo", nome: "Prazo vencido (art. 363)", cor: "--s5" },
  { chave: "legislatura", nome: "Arquivada no fim da legislatura", cor: "--s6" },
  { chave: "outros", nome: "Outros motivos", cor: "--cinza-1" },
];
const PRIMEIRAS_RELATORES = 15;

async function carregarLegislativo() {
  if (!cache.legislativo) {
    const r = await fetch("dados/legislativo.json");
    if (!r.ok) throw new Error(`não foi possível carregar dados/legislativo.json (${r.status})`);
    cache.legislativo = await r.json();
  }
  return cache.legislativo;
}

// "RICARDO NUNES" -> "Ricardo Nunes"
const nomeProprio = (t) => t.toLowerCase().split(" ").map((p, i) =>
  (i && ["a", "ao", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos", "o", "os", "para", "por"].includes(p) ? p : p.charAt(0).toUpperCase() + p.slice(1))).join(" ");

// O vocabulário de assuntos da Câmara vem em maiúsculas e sem acento: devolve os acentos das
// palavras que aparecem entre os assuntos mais frequentes ("-CAO" vira "-ção", "-AO" vira "-ão").
const ACENTOS = Object.fromEntries(("água alvará área artística assistência auxílio beneficiário calçada cálculo " +
  "calendário cobrança concessionária condomínio convivência coronavírus criança deficiência diagnóstico doença " +
  "doméstica doméstico edifício emergência espaço exigência família física físico gênero história honorífica " +
  "honorífico horário jurídica licença mãe matrícula médica médico móvel munícipe ônibus patrimônio permanência " +
  "praça prêmio presença proprietário psicológica pública público públicos resíduos salário sanitário saúde " +
  "segurança serviços sólidos tecnológica título transferência trânsito transparência único usuário veículos " +
  "violência vítima cão").split(" ").map((p) => [p.normalize("NFD").replace(/[\u0300-\u036f]/g, ""), p]));
const ASSUNTO_PROPRIO = [[/\bsão paulo\b/, "São Paulo"], [/\banchieta\b/, "Anchieta"], [/\bcovid 19\b/, "Covid-19"],
  [/\b(iptu|iss|ong)\b/g, (m) => m.toUpperCase()], [/\blgbtqiapn\b/, "LGBTQIAPN+"]];
function nomeAssunto(termo) {
  let t = termo.toLowerCase().split(" ").map((p) => ACENTOS[p] ??
    (p.length > 3 && p.endsWith("cao") ? p.slice(0, -3) + "ção" : p.length > 2 && p.endsWith("ao") ? p.slice(0, -2) + "ão" : p)).join(" ");
  for (const [rx, troca] of ASSUNTO_PROPRIO) t = t.replace(rx, troca);
  t = t.replace(/\(\s+/g, "(").replace(/\s+\)/g, ")");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// Índices [i0, i1) dos meses de `meses` (AAAA-MM) que entram no período escolhido.
function mesesDoPeriodo(meses) {
  const [inicio, fim] = periodoEscolhido().map((d) => dataISO(d).slice(0, 7));
  const i0 = Math.max(0, meses.findIndex((mes) => mes >= inicio));
  const i1 = meses.findIndex((mes) => mes > fim);
  return [i0, i1 < 0 ? meses.length : Math.max(i1, i0 + 1)];
}

function renderPareceres(l, nomes, ultimoDia) {
  const cartao = document.getElementById("c-pareceres");
  const serie = l.pareceres[estado.comissao];
  const ultimoMes = l.meses[l.meses.length - 1];
  const parcial = dataISO(ultimoDia) < dataISO(new Date(d3.utcMonth.offset(mesParaData(ultimoMes), 1) - DIA));
  const [i0, i1] = mesesDoPeriodo(l.meses);
  const faixas = l.meses.slice(i0, i1).map((mes, k) => {
    const i = i0 + k;
    const a = mesParaData(mes);
    const b = d3.utcMonth.offset(a, 1);
    const valores = Object.fromEntries(CONCLUSOES.map((c) => [c.chave, serie[c.chave][i]]));
    return { a, b, meio: new Date((+a + +b) / 2), parcial: parcial && i === l.meses.length - 1, valores,
             total: d3.sum(CONCLUSOES, (c) => valores[c.chave]), media: null };
  });
  const onde = nomes.comissao.replace(/^da /, "na ").replace(/^das /, "nas ");
  document.getElementById("sub-pareceres").textContent =
    `Pareceres dados pelos relatores ${onde} em cada mês, pela conclusão. Na CCJ o parecer trata da legalidade; ` +
    "nas demais comissões, do mérito." + (estado.grupo === "todas" ? " Só há pareceres de projetos." : "");
  legenda(cartao, CONCLUSOES);
  acoes(cartao, faixas.map((x) => x.a), CONCLUSOES.map((c) => ({ nome: c.nome, valores: faixas.map((x) => x.valores[c.chave]) })),
        `pareceres-${estado.comissao.toLowerCase()}-${estado.periodo}.csv`);
  if (cartao.dataset.tabela === "1") return;
  const soma12 = d3.sum(faixas.filter((x) => !x.parcial).slice(-12), (x) => x.total);
  graficoBarrasMes(cartao.querySelector(".grafico"), faixas, CONCLUSOES, {
    altura: 260, inicioColeta: "2026-10-02", ultimoDia, mostrarParte: true,
    descricao: `Pareceres ${onde} por mês e conclusão, ${textoPeriodo()}. ${fmt(soma12)} nos últimos 12 meses completos.` });
}

// Lista com barras horizontais: itens [{chave, rotulo, extra, n, titulo}], do maior ao menor.
function preencherRanking(cartao, itens, opcoes) {
  const todos = cartao.dataset.todos === "1";
  const mostrar = todos ? itens.slice(0, opcoes.maximoTodos ?? itens.length) : itens.slice(0, PRIMEIRAS_RELATORES);
  const maximo = itens[0]?.n || 1;
  const lista = cartao.querySelector(".ranking");
  lista.replaceChildren(...mostrar.map((it) => {
    const li = el("li");
    const rotulo = el("span", "nome", it.rotulo);
    if (it.extra) rotulo.append(" ", el("small", null, it.extra));
    const trilho = el("span", "trilho");
    const barra = el("span", "barra");
    barra.style.width = `${(100 * it.n) / maximo}%`;
    trilho.append(barra);
    li.append(rotulo, trilho, el("span", "valor", opcoes.valor ? opcoes.valor(it) : fmt(it.n)));
    li.title = it.titulo;
    return li;
  }));
  if (!itens.length) lista.replaceChildren(el("li", "vazio", opcoes.vazio));
  const limite = Math.min(itens.length, opcoes.maximoTodos ?? itens.length);
  const mais = cartao.querySelector(".botao.mais");
  mais.hidden = itens.length <= PRIMEIRAS_RELATORES;
  mais.textContent = todos ? "Mostrar menos" : `Mostrar ${limite < itens.length ? `os ${fmt(limite)} primeiros` : `todos (${fmt(itens.length)})`}`;
  mais.onclick = () => { cartao.dataset.todos = todos ? "" : "1"; opcoes.redesenhar(); };
  const botao = el("button", "botao", "Baixar CSV");
  botao.type = "button";
  botao.addEventListener("click", () => baixarTabela(opcoes.cabecalho, itens.map(opcoes.linhaCsv), opcoes.arquivo));
  cartao.querySelector(".acoes-csv").replaceChildren(botao);
}

function renderRelatores(l) {
  const cartao = document.getElementById("c-relatores");
  const porPartido = cartao.dataset.modo === "partido";
  for (const b of cartao.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === (porPartido ? "partido" : "relator")));
    b.onclick = () => { cartao.dataset.modo = b.dataset.modo; cartao.dataset.todos = ""; renderRelatores(l); };
  }
  const [i0, i1] = mesesDoPeriodo(l.meses);
  const listas = estado.comissao === "TODAS" ? Object.values(l.pareceres_por_relator)
    : [l.pareceres_por_relator[estado.comissao] ?? []];
  const contagem = new Map();
  for (const lista of listas) {
    for (let k = 0; k < lista.length; k += 4) {
      if (lista[k] < i0 || lista[k] >= i1) continue;
      const chave = porPartido ? l.partidos[lista[k + 2]] : lista[k + 1];
      contagem.set(chave, (contagem.get(chave) ?? 0) + lista[k + 3]);
    }
  }
  const total = d3.sum(contagem.values());
  const itens = [...contagem].sort((a, b) => b[1] - a[1]).map(([chave, n]) => {
    const [nome, partido] = porPartido ? [chave, ""] : l.relatores[chave];
    const rotulo = porPartido ? nome : nomeProprio(nome);
    return { chave, rotulo, extra: partido, n, titulo: `${rotulo}: ${fmt(n)} pareceres (${porcento(n, total)})` };
  });
  const onde = estado.comissao === "TODAS" ? "nas 7 comissões" : `na ${rotuloComissao(estado.comissao)}`;
  document.getElementById("sub-relatores").textContent = porPartido
    ? `Pareceres dados ${onde} ${textoPeriodo()}, pelo partido do relator na data do parecer.`
    : `Pareceres dados ${onde} ${textoPeriodo()}, por relator: ${fmt(total)} pareceres de ${fmt(itens.length)} relatores. Ao lado do nome, o partido de hoje.`;
  preencherRanking(cartao, itens, {
    vazio: "Nenhum parecer neste recorte.", redesenhar: () => renderRelatores(l),
    cabecalho: porPartido ? ["partido na data do parecer", "pareceres"] : ["relator", "partido hoje", "pareceres"],
    linhaCsv: (it) => (porPartido ? [it.rotulo, it.n] : [it.rotulo, it.extra, it.n]),
    arquivo: `${porPartido ? "partidos" : "relatores"}-${estado.comissao.toLowerCase()}-${estado.periodo}.csv` });
}

function renderAssuntos(l) {
  const cartao = document.getElementById("c-assuntos");
  const [i0, i1] = mesesDoPeriodo(l.meses);
  const lista = l.assuntos_por_mes[estado.comissao] ?? [];
  const contagem = new Map();
  for (let k = 0; k < lista.length; k += 3) {
    if (lista[k] < i0 || lista[k] >= i1) continue;
    contagem.set(lista[k + 1], (contagem.get(lista[k + 1]) ?? 0) + lista[k + 2]);
  }
  const chegadas = d3.sum((l.chegadas_com_assunto[estado.comissao] ?? []).slice(i0, i1));
  const itens = [...contagem].sort((a, b) => b[1] - a[1]).map(([t, n]) => {
    const rotulo = nomeAssunto(l.assuntos[t]);
    return { chave: t, rotulo, n, titulo: `${rotulo}: ${fmt(n)} projetos (${porcento(n, chegadas)} dos que chegaram)` };
  });
  const onde = estado.comissao === "TODAS" ? "às comissões" : `à ${rotuloComissao(estado.comissao)}`;
  document.getElementById("sub-assuntos").textContent =
    `Assuntos dos ${fmt(chegadas)} projetos que chegaram ${onde} ${textoPeriodo()}, no vocabulário que a Câmara usa ` +
    "para indexar os projetos. Um projeto costuma ter vários assuntos; termos genéricos, como criação ou alteração, ficam de fora.";
  preencherRanking(cartao, itens, {
    vazio: "Nenhum projeto com assunto neste recorte.", redesenhar: () => renderAssuntos(l), maximoTodos: 60,
    valor: (it) => porcento(it.n, chegadas),
    cabecalho: ["assunto", "projetos", "parte dos que chegaram (%)"],
    linhaCsv: (it) => [l.assuntos[it.chave], it.n, Math.round((1000 * it.n) / (chegadas || 1)) / 10],
    arquivo: `assuntos-${estado.comissao.toLowerCase()}-${estado.periodo}.csv` });
}

// Linha do tempo de quem presidiu cada comissão (ou, numa comissão, presidente e vice).
function renderPresidentes(l) {
  const cartao = document.getElementById("c-presidentes");
  const c = cores();
  const [inicio, fim] = periodoEscolhido();
  const uma = estado.comissao !== "TODAS";
  const linhas = uma ? ["Presidente", "Vice-presidente"] : ORDEM_COMISSOES.map(rotuloComissao);
  const barras = [];
  for (const sigla of uma ? [estado.comissao] : ORDEM_COMISSOES) {
    for (const [cargo, vereador, partido, de, ate] of l.presidentes[sigla] ?? []) {
      if (!uma && cargo !== "Presidente") continue;
      const a = new Date(Math.max(utc(de), inicio));
      const b = new Date(Math.min(ate ? +utc(ate) + DIA : +fim + DIA, +fim + DIA));
      if (b <= a) continue;
      barras.push({ linha: uma ? cargo : rotuloComissao(sigla), a, b, nome: nomeProprio(vereador), partido,
                    titulo: `${nomeProprio(vereador)} (${partido || "sem partido"}), ${cargo.toLowerCase()} da ${rotuloComissao(sigla)} ` +
                            `de ${dataBR(utc(de))} ${ate ? `a ${dataBR(utc(ate))}` : "até hoje"}` });
    }
  }
  const onde = uma ? `da ${rotuloComissao(estado.comissao)}` : "de cada comissão";
  document.getElementById("sub-presidentes").textContent =
    `${uma ? "Presidentes e vices" : "Presidentes"} ${onde} ${textoPeriodo()}, pelo cadastro de cargos da Câmara. ` +
    "Os traços curtos são substituições de poucos dias. Passe o mouse para ver o nome, o partido na época e as datas.";
  acoesTabela(cartao, [{ nome: "comissão ou cargo" }, { nome: "vereador" }, { nome: "partido na época" }, { nome: "de" }, { nome: "até" }],
              barras.map((x) => [x.linha, x.nome, x.partido, dataISO(x.a), dataISO(new Date(x.b - DIA))]),
              `presidentes-${estado.comissao.toLowerCase()}.csv`, { recentesPrimeiro: false });
  if (cartao.dataset.tabela === "1") return;
  const alvo = cartao.querySelector(".grafico");
  const largura = alvo.clientWidth;
  const margemEsquerda = uma ? 112 : 60;
  const util = largura - margemEsquerda - 16;
  const porMs = util / (fim - inicio + DIA);
  const datas = [inicio, new Date(+fim + DIA)];
  const x = eixoX(datas, largura);
  const svg = Plot.plot({
    width: largura, height: linhas.length * 38 + 40, marginLeft: margemEsquerda, marginRight: 16, marginTop: 8, marginBottom: 26,
    style: { fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", fontSize: "12px",
             background: "transparent", color: c.tinta3, overflow: "visible" },
    x: { type: "utc", domain: datas },
    y: { domain: linhas, padding: 0.18 },
    marks: [
      Plot.axisX({ ticks: x.ticks, tickFormat: x.tickFormat, tickSize: 0, tickPadding: 8, fill: c.tinta3, label: null }),
      Plot.axisY({ tickSize: 0, tickPadding: 8, fill: c.tinta2, label: null }),
      Plot.barX(barras, { x1: "a", x2: "b", y: "linha", fill: c.s1, insetLeft: 1, insetRight: 1, title: "titulo" }),
      Plot.text(barras.filter((x) => (x.b - x.a) * porMs > x.nome.length * 6.6 + 10),
        { x: (x) => new Date((+x.a + +x.b) / 2), y: "linha", text: "nome", fill: "#fff", fontSize: 11, title: "titulo" }),
    ],
  });
  descrever(svg, `Linha do tempo dos ${uma ? "presidentes e vices" : "presidentes"} ${onde}.`);
  alvo.replaceChildren(svg);
}

// Barras por ano, a partir de séries anuais (uma lista por categoria).
function faixasAnuais(anos, series, categorias) {
  return anos.map((ano, i) => {
    const a = utc(`${ano}-01-01`);
    const b = utc(`${ano + 1}-01-01`);
    const valores = Object.fromEntries(categorias.map((k) => [k.chave, series[k.chave]?.[i] ?? 0]));
    return { ano, a, b, meio: new Date((+a + +b) / 2), parcial: false, valores, media: null,
             total: d3.sum(categorias, (k) => valores[k.chave]) };
  });
}

function renderSaidas(t, nomes) {
  const cartao = document.getElementById("c-saidas");
  const serie = t.saidas[estado.grupo][estado.comissao];
  const [desde, ate] = periodoEscolhido().map((d) => d.getUTCFullYear());
  const anos = t.anos_saidas.filter((a) => a >= desde && a <= ate);
  const sel = t.anos_saidas.map((a) => a >= desde && a <= ate);
  const recorte = Object.fromEntries(SAIDAS.map((k) => [k.chave, serie[k.chave].filter((_, i) => sel[i])]));
  const faixas = faixasAnuais(anos, recorte, SAIDAS);
  const anoAtual = t.anos_saidas[t.anos_saidas.length - 1];
  const onde = nomes.comissao.replace(/^da /, "da ").replace(/^das /, "das ");
  document.getElementById("sub-saidas").textContent =
    `${estado.grupo === "projetos" ? "Projetos" : "Matérias"} que saíram ${onde} em cada ano, pelo motivo da saída. ` +
    "As barras de 2021 e 2025 incluem o arquivamento de fim de legislatura.";
  legenda(cartao, SAIDAS);
  acoesTabela(cartao, [{ nome: "ano" }, ...SAIDAS.map((k) => ({ nome: k.nome.toLowerCase() })), { nome: "total" }],
              faixas.map((x) => [String(x.ano), ...SAIDAS.map((k) => x.valores[k.chave]), x.total]),
              `saidas-${estado.comissao.toLowerCase()}-${estado.grupo}.csv`);
  if (cartao.dataset.tabela === "1") return;
  graficoBarrasMes(cartao.querySelector(".grafico"), faixas, SAIDAS, {
    altura: 280, marcos: false, anual: true, mostrarParte: true, soPresentes: true, rotuloTotal: "no ano",
    titulo: (x) => (x.ano === anoAtual ? `${x.ano} (até agora)` : String(x.ano)),
    descricao: `Saídas ${onde} por ano e motivo. ` + faixas.map((x) => `${x.ano}: ${fmt(x.total)}`).join("; ") + "." });
}

// Gráfico anual com uma linha por comissão (ou por autoria, com `estilo` e `nome`), como o do
// crescimento comparado: a escolhida em destaque e o valor no fim de cada linha.
function graficoAnual(alvo, datas, curvas, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  const estilo = opcoes.estilo ?? estiloComissao(c, opcoes.destaque);
  const nome = opcoes.nome ?? rotuloComissao;
  const maximo = d3.max(curvas, (cv) => d3.max(cv.valores)) || 1;
  const m = moldura(c, datas, largura, opcoes.altura, { yDomain: [0, maximo], marginRight: MARGEM_DIREITA + 24 });
  const topo = d3.scaleLinear().domain([0, maximo]).nice().domain()[1];
  const [d0, d1] = [datas[0], datas[datas.length - 1]];
  const px = (p) => ((p.x - d0) / (d1 - d0)) * (largura - 48 - MARGEM_DIREITA - 24);
  const py = (p) => (1 - p.y / topo) * (opcoes.altura - 22 - 26);
  const pontosDe = (cv) => datas.map((d, i) => ({ x: d, y: cv.valores[i] }));  // y nulo interrompe a linha
  const svg = Plot.plot({
    ...m.opcoes,
    marks: [
      ...m.eixos,
      ...curvas.map((cv) => {
        const e = estilo(cv.sigla);
        return Plot.dot(pontosDe(cv).filter((p) => p.y != null), { x: "x", y: "y", r: 2.5, fill: e.cor, fillOpacity: e.opacidade });
      }),
      ...marcasComissoes(c, curvas, opcoes.destaque, pontosDe, px, py, (p) => `${nome(p.sigla)} ${fmt(p.y)}`, estilo),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
  interagir(alvo, svg, datas, (i) => ({
    titulo: opcoes.titulo?.(i),
    linhas: linhasDaDica(c, curvas, opcoes.destaque, (cv) => cv.valores[i], opcoes.formato ?? fmt,
                         (cv) => opcoes.detalhe?.(cv, i) ?? "", { estilo, nome: (s) => nome(s) }),
  }));
}

const diasTexto = (v) => (v == null ? "—" : `${fmt(v)} ${v === 1 ? "dia" : "dias"}`);

function renderPrazos(l) {
  const cartao = document.getElementById("c-prazos");
  const porAutoria = cartao.dataset.modo === "autoria";
  for (const b of cartao.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === (porAutoria ? "autoria" : "comissao")));
    b.onclick = () => { cartao.dataset.modo = b.dataset.modo; render(); };
  }
  const anoAtual = l.anos[l.anos.length - 1];
  const k0 = l.anos.indexOf(PRIMEIRO_ANO_PRAZOS);
  const anos = l.anos.slice(k0);
  const datas = anos.map((a) => utc(`${a}-01-01`));
  const serie = (s, a) => l.prazos[s]?.[a] ?? { mediana: [], p25: [], p75: [], n: [] };
  const fatia = (x) => anos.map((_, i) => ({ mediana: x.mediana[k0 + i], p25: x.p25[k0 + i], p75: x.p75[k0 + i], n: x.n[k0 + i] }));
  const curvas = porAutoria
    ? [TODAS_AUTORIAS, ...AUTORIAS_CURVAS].map((a) => ({ sigla: a, pontos: fatia(serie(estado.comissao, a)) }))
    : COMISSOES.map(([sigla]) => ({ sigla, pontos: fatia(serie(sigla, TODAS_AUTORIAS)) }));
  for (const cv of curvas) cv.valores = cv.pontos.map((x) => x.mediana);
  const visiveis = curvas.filter((cv) => cv.valores.some((v) => v != null));
  const onde = estado.comissao === "TODAS" ? "nas 7 comissões" : `na ${rotuloComissao(estado.comissao)}`;
  document.getElementById("sub-prazos").textContent = porAutoria
    ? `Mediana, em dias, do tempo até o parecer ${onde}, pelo primeiro autor do projeto e pelo ano do parecer.`
    : "Mediana, em dias, do tempo que cada comissão levou para dar o parecer, pelo ano do parecer.";
  if (porAutoria) legendaAutorias(cartao);
  else legendaComissoes(cartao);
  const nome = porAutoria ? nomeAutoria : rotuloComissao;
  const colunas = [{ nome: "ano" }, ...visiveis.flatMap((cv) => [
    { nome: `${nome(cv.sigla)}: mediana (dias)` }, { nome: `${nome(cv.sigla)}: 1º quartil` },
    { nome: `${nome(cv.sigla)}: 3º quartil` }, { nome: `${nome(cv.sigla)}: pareceres` }])];
  acoesTabela(cartao, colunas, anos.map((a, i) => [String(a), ...visiveis.flatMap((cv) =>
    [cv.pontos[i].mediana, cv.pontos[i].p25, cv.pontos[i].p75, cv.pontos[i].n])]),
    `prazo-do-parecer-${porAutoria ? `autoria-${estado.comissao.toLowerCase()}` : "comissoes"}.csv`);
  if (cartao.dataset.tabela === "1") return;
  const destaque = porAutoria ? TODAS_AUTORIAS : estado.comissao;
  const final = visiveis.find((cv) => cv.sigla === destaque) ?? visiveis[0];
  graficoAnual(cartao.querySelector(".grafico"), datas, visiveis, {
    altura: 300, destaque, formato: diasTexto,
    ...(porAutoria ? { estilo: estiloAutoria(cores()), nome: nomeAutoria } : {}),
    titulo: (i) => (anos[i] === anoAtual ? `Pareceres de ${anoAtual} (até agora)` : `Pareceres de ${anos[i]}`),
    detalhe: (cv, i) => {
      const x = cv.pontos[i];
      return x.mediana == null ? "" : `— metade entre ${fmt(x.p25)} e ${fmt(x.p75)}; ${fmt(x.n)} pareceres`;
    },
    descricao: `Mediana do tempo até o parecer${porAutoria ? ` ${onde}, por autoria` : ", por comissão"}. ` +
      `${nome(final.sigla)}: ${final.valores.map((v, i) => `${anos[i]} ${v ?? "—"}`).join(", ")}.` });
}

// Membros das comissões por partido, mês a mês. As cores ficam com os 7 partidos que mais
// ocuparam cadeiras desde nov/2018 (a ordem vem pronta do painel/legislativo.py).
const PARTIDOS_COM_COR = 7;

function renderMembros(l, ultimoDia) {
  const cartao = document.getElementById("c-membros");
  const mb = l.membros;
  const camadas = [...mb.partidos.slice(0, PARTIDOS_COM_COR).map((p, k) => ({ chave: p, nome: p, cor: `--s${k + 1}` })),
                   { chave: "outros", nome: "Outros partidos", cor: "--cinza-1" }];
  const cadeiras = mb.meses.map(() => ({}));
  const lista = mb.por_comissao[estado.comissao] ?? [];
  for (let k = 0; k < lista.length; k += 3) {
    const p = mb.partidos[lista[k + 1]];
    const chave = lista[k + 1] < PARTIDOS_COM_COR ? p : "outros";
    cadeiras[lista[k]][chave] = (cadeiras[lista[k]][chave] ?? 0) + lista[k + 2];
    if (chave === "outros") (cadeiras[lista[k]].quais ??= []).push(`${p} ${lista[k + 2]}`);
  }
  const ultimoMes = mb.meses[mb.meses.length - 1];
  const parcial = dataISO(ultimoDia) < dataISO(new Date(d3.utcMonth.offset(mesParaData(ultimoMes), 1) - DIA));
  const [i0, i1] = mesesDoPeriodo(mb.meses);
  const faixas = mb.meses.slice(i0, i1).map((mes, k) => {
    const i = i0 + k;
    const a = mesParaData(mes);
    const b = d3.utcMonth.offset(a, 1);
    const valores = Object.fromEntries(camadas.map((x) => [x.chave, cadeiras[i][x.chave] ?? 0]));
    return { a, b, meio: new Date((+a + +b) / 2), parcial: false, valores, media: null, quais: cadeiras[i].quais ?? [],
             total: d3.sum(camadas, (x) => valores[x.chave]) };
  });
  const uma = estado.comissao !== "TODAS";
  document.getElementById("sub-membros").textContent = uma
    ? `Membros da ${rotuloComissao(estado.comissao)} por partido, no dia 15 de cada mês, ${textoPeriodo()}.`
    : `Cadeiras nas 7 comissões por partido, no dia 15 de cada mês, ${textoPeriodo()}. Um vereador em duas comissões ocupa duas cadeiras.`;
  legenda(cartao, camadas);
  acoesTabela(cartao, [{ nome: "mês" }, ...camadas.map((x) => ({ nome: x.nome })), { nome: "total" }, { nome: "outros partidos" }],
              faixas.map((x) => [dataISO(x.a).slice(0, 7), ...camadas.map((k) => x.valores[k.chave]), x.total, x.quais.join("; ")]),
              `membros-${estado.comissao.toLowerCase()}.csv`);
  if (cartao.dataset.tabela === "1") return;
  const ultima = faixas[faixas.length - 1];
  graficoBarrasMes(cartao.querySelector(".grafico"), faixas, camadas, {
    altura: 280, inicioColeta: "2026-10-02", ultimoDia, soPresentes: true, rotuloTotal: uma ? "membros" : "cadeiras",
    titulo: (x) => `${rotuloMes(x.a)}${x === ultima && parcial ? ` (em ${dataBR(ultimoDia)})` : ""}` +
      (x.quais.length ? ` · outros: ${x.quais.join(", ")}` : ""),
    descricao: `${uma ? "Membros" : "Cadeiras"} por partido. No último mês: ` +
      camadas.filter((k) => ultima.valores[k.chave]).map((k) => `${k.nome} ${ultima.valores[k.chave]}`).join(", ") + "." });
}

// Desfecho por grupo (autoria ou partido do primeiro autor): uma barra de 100% por grupo.
function graficoBarrasGrupos(alvo, linhas, camadas, opcoes) {
  const c = cores();
  const largura = alvo.clientWidth;
  MEDIR_MARCO.font = "12px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  const margemEsquerda = Math.ceil(d3.max(linhas, (l) => MEDIR_MARCO.measureText(l.rotulo).width) ?? 60) + 14;
  const segmentos = [];
  for (const l of linhas) {
    let acima = 0;
    for (const k of camadas) {
      const v = l.valores[k.chave] ?? 0;
      if (!v) continue;
      const x1 = (100 * acima) / l.total;
      acima += v;
      segmentos.push({ rotulo: l.rotulo, x1, x2: (100 * acima) / l.total, k: k.nome,
                       titulo: `${l.nome}: ${k.nome.toLowerCase()}, ${fmt(v)} de ${fmt(l.total)} (${porcentoInteiro(v / l.total)})` });
    }
  }
  const svg = Plot.plot({
    width: largura, height: linhas.length * 30 + 34, marginLeft: margemEsquerda, marginRight: 48, marginTop: 4, marginBottom: 26,
    style: { fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", fontSize: "12px",
             background: "transparent", color: c.tinta3, overflow: "visible" },
    x: { domain: [0, 100] },
    y: { domain: linhas.map((l) => l.rotulo), padding: 0.22 },
    color: { domain: camadas.map((k) => k.nome), range: camadas.map((k) => c.v(k.cor)) },
    marks: [
      Plot.axisX({ ticks: [0, 25, 50, 75, 100], tickFormat: (v) => `${v}%`, tickSize: 0, tickPadding: 6, fill: c.tinta3, label: null }),
      Plot.axisY({ tickSize: 0, tickPadding: 8, fill: c.tinta2, label: null }),
      Plot.barX(segmentos, { x1: "x1", x2: "x2", y: "rotulo", fill: "k", stroke: c.superficie, strokeWidth: 1, title: "titulo" }),
      Plot.text(linhas, { x: () => 100, y: "rotulo", text: opcoes.direita, dx: 6, textAnchor: "start", fill: c.tinta, fontWeight: 600 }),
    ],
  });
  descrever(svg, opcoes.descricao);
  alvo.replaceChildren(svg);
}

const PRIMEIRO_ANO_PRAZOS = 2015;
const ANOS_DESFECHO = [
  ["2013-2024", "2013 a 2024 (legislaturas encerradas)", 2013, 2024],
  ["2013-2016", "2013 a 2016", 2013, 2016],
  ["2017-2020", "2017 a 2020", 2017, 2020],
  ["2021-2024", "2021 a 2024", 2021, 2024],
  ["2025-", "2025 em diante", 2025, 9999],
];
const MINIMO_PARTIDO = 30;  // projetos para um partido entrar no gráfico

function renderDesfechosPorGrupo(l, cartao, porPartido) {
  const seletor = document.getElementById("f-anos-desfecho");
  if (!seletor.options.length) {
    for (const [v, t] of ANOS_DESFECHO) seletor.append(new Option(t, v));
    seletor.addEventListener("change", () => render());
  }
  const [, textoAnos, de, ate] = ANOS_DESFECHO.find(([v]) => v === seletor.value) ?? ANOS_DESFECHO[0];
  const indices = l.anos.map((a, i) => (a >= de && a <= ate ? i : -1)).filter((i) => i >= 0);
  const fonte = porPartido ? l.desfechos_partido : l.desfechos_autoria;
  let linhas = Object.entries(fonte).map(([nome, serie]) => {
    const valores = Object.fromEntries(DESFECHOS.map((k) => [k.chave, d3.sum(indices, (i) => serie[k.chave][i])]));
    return { nome, valores, total: d3.sum(DESFECHOS, (k) => valores[k.chave]) };
  }).filter((x) => x.total >= (porPartido ? MINIMO_PARTIDO : 1));
  if (porPartido) linhas.sort((a, b) => b.valores.lei / b.total - a.valores.lei / a.total || b.total - a.total);
  for (const x of linhas) x.rotulo = `${x.nome} · ${fmt(x.total)}`;
  const anos = textoAnos.replace(/ \(.*\)$/, "");
  cartao.querySelector(".sub").textContent = porPartido
    ? `Projetos apresentados por vereadores de ${anos}, pelo partido do primeiro autor na data da leitura e pelo desfecho. ` +
      `Em ordem da parte que virou lei; só partidos com pelo menos ${MINIMO_PARTIDO} projetos.`
    : `Projetos apresentados de ${anos}, pelo primeiro autor e pelo desfecho. O Executivo é o prefeito.`;
  legenda(cartao, DESFECHOS);
  acoesTabela(cartao, [{ nome: porPartido ? "partido" : "autoria" }, { nome: "projetos" }, ...DESFECHOS.map((k) => ({ nome: k.nome.toLowerCase() }))],
              linhas.map((x) => [x.nome, x.total, ...DESFECHOS.map((k) => x.valores[k.chave])]),
              `desfecho-por-${porPartido ? "partido" : "autoria"}-${seletor.value}.csv`, { recentesPrimeiro: false });
  if (cartao.dataset.tabela === "1") return;
  if (!linhas.length) {
    cartao.querySelector(".grafico").replaceChildren(el("p", "vazio", "Nenhum projeto neste recorte."));
    return;
  }
  graficoBarrasGrupos(cartao.querySelector(".grafico"), linhas, DESFECHOS, {
    direita: (x) => porcentoInteiro(x.valores.lei / x.total),
    descricao: `Parte dos projetos de ${anos} que virou lei, ${porPartido ? "por partido do primeiro autor" : "por autoria"}: ` +
      linhas.map((x) => `${x.nome} ${porcentoInteiro(x.valores.lei / x.total)}`).join(", ") + "." });
}

// Funil: até onde chegaram os projetos apresentados nos anos escolhidos (painel/legislativo.py).
const ETAPAS_FUNIL = {
  apresentados: "Apresentados",
  relator: "Ganharam relator em alguma comissão",
  parecer: "Receberam parecer de alguma comissão",
  comissoes: "Passaram por todas as comissões do despacho",
  aprovados: "Aprovados pela Câmara",
  lei: "Viraram lei",
};
const AUTORIAS_FUNIL = [["", "Todas"], ["Vereadores", "Vereadores"], ["Executivo", "Executivo (prefeito)"], ["Mesa Diretora", "Mesa Diretora"]];

function renderFunil(l) {
  const cartao = document.getElementById("c-funil");
  const anosSel = document.getElementById("f-anos-funil");
  const autoriaSel = document.getElementById("f-autoria-funil");
  if (!anosSel.options.length) {
    for (const [v, t] of ANOS_DESFECHO) anosSel.append(new Option(t, v));
    anosSel.value = "2021-2024";  // a última legislatura encerrada
    for (const [v, t] of AUTORIAS_FUNIL) autoriaSel.append(new Option(t, v));
    anosSel.addEventListener("change", () => render());
    autoriaSel.addEventListener("change", () => render());
  }
  const [, textoAnos, de, ate] = ANOS_DESFECHO.find(([v]) => v === anosSel.value) ?? ANOS_DESFECHO[0];
  const anos = textoAnos.replace(/ \(.*\)$/, "");
  const grupos = autoriaSel.value ? [autoriaSel.value] : Object.keys(l.funil.por_autoria);
  const n = l.funil.etapas.map((_, k) => d3.sum(grupos, (a) => d3.sum(l.anos, (ano, i) =>
    (ano >= de && ano <= ate ? l.funil.por_autoria[a][i][k] : 0))));
  const quem = autoriaSel.value === "Executivo" ? "do Executivo" : autoriaSel.value === "Mesa Diretora" ? "da Mesa Diretora"
    : autoriaSel.value === "Vereadores" ? "de vereadores" : "";
  document.getElementById("sub-funil").textContent =
    `Projetos (PL, PDL, PR e PLO) ${quem ? `${quem} ` : ""}apresentados de ${anos} e até onde chegaram. ` +
    `Viraram lei ${porcentoInteiro(n[n.length - 1] / (n[0] || 1))}. Os filtros de comissão, de matérias e de período não se aplicam.`;
  const lista = cartao.querySelector(".funil");
  lista.replaceChildren(...l.funil.etapas.map((etapa, k) => {
    const li = el("li");
    const nome = el("span", "nome", ETAPAS_FUNIL[etapa]);
    if (k > 0) nome.append(" ", el("small", null, `${porcentoInteiro(n[k] / (n[k - 1] || 1))} da etapa anterior`));
    const trilho = el("span", "trilho");
    const barra = el("span", "barra");
    barra.style.width = `${(100 * n[k]) / (n[0] || 1)}%`;
    trilho.append(barra);
    li.append(nome, el("span", "valor", `${fmt(n[k])}${k ? ` · ${porcentoInteiro(n[k] / (n[0] || 1))}` : ""}`), trilho);
    li.title = `${ETAPAS_FUNIL[etapa]}: ${fmt(n[k])} projetos, ${porcentoInteiro(n[k] / (n[0] || 1))} dos apresentados`;
    return li;
  }));
  const botao = el("button", "botao", "Baixar CSV");
  botao.type = "button";
  botao.addEventListener("click", () => baixarTabela(["etapa", "projetos", "% dos apresentados", "% da etapa anterior"],
    l.funil.etapas.map((etapa, k) => [ETAPAS_FUNIL[etapa], n[k], Math.round((1000 * n[k]) / (n[0] || 1)) / 10,
                                      k ? Math.round((1000 * n[k]) / (n[k - 1] || 1)) / 10 : null]),
    `funil-${anosSel.value}-${(autoriaSel.value || "todas").toLowerCase().replace(" ", "-")}.csv`));
  cartao.querySelector(".acoes-csv").replaceChildren(botao);
}

function renderDesfechos(l) {
  const cartao = document.getElementById("c-desfechos");
  const modo = ["ano", "autoria", "partido"].includes(cartao.dataset.modo) ? cartao.dataset.modo : "ano";
  for (const b of cartao.querySelectorAll(".alternador button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === modo));
    b.onclick = () => { cartao.dataset.modo = b.dataset.modo; render(); };
  }
  cartao.querySelector(".anos-desfecho").hidden = modo === "ano";
  cartao.querySelector(".nota-ano").hidden = modo !== "ano";
  cartao.querySelector(".nota-grupo").hidden = modo === "ano";
  if (modo !== "ano") return renderDesfechosPorGrupo(l, cartao, modo === "partido");
  cartao.querySelector(".sub").textContent = "Projetos (PL, PDL, PR e PLO) apresentados em cada ano, pelo desfecho registrado no SPLEGIS. Os filtros de comissão, de matérias e de período não se aplicam.";
  const series = { ...l.desfechos, aberto: l.em_tramitacao };
  const indices = l.anos.map((_, i) => i).filter((i) => l.apresentados[i] != null);
  const anos = indices.map((i) => l.anos[i]);
  const recorte = Object.fromEntries(DESFECHOS.map((k) => [k.chave, indices.map((i) => series[k.chave][i])]));
  const faixas = faixasAnuais(anos, recorte, DESFECHOS);
  legenda(cartao, DESFECHOS);
  acoesTabela(cartao, [{ nome: "ano de apresentação" }, { nome: "apresentados" }, ...DESFECHOS.map((k) => ({ nome: k.nome.toLowerCase() }))],
              faixas.map((x, i) => [String(x.ano), l.apresentados[indices[i]], ...DESFECHOS.map((k) => x.valores[k.chave])]),
              "desfecho-dos-projetos.csv");
  if (cartao.dataset.tabela === "1") return;
  const media = (ini, fim) => {
    const sel = faixas.filter((x) => x.ano >= ini && x.ano <= fim);
    return porcentoInteiro(d3.sum(sel, (x) => x.valores.lei) / (d3.sum(sel, (x) => x.total) || 1));
  };
  graficoBarrasMes(cartao.querySelector(".grafico"), faixas, DESFECHOS, {
    altura: 300, marcos: false, anual: true, percentual: true, mostrarParte: true, rotuloTotal: "projetos apresentados",
    titulo: (x) => `Projetos apresentados em ${x.ano}`,
    descricao: `Desfecho dos projetos por ano de apresentação. Viraram lei ${media(2013, 2016)} dos apresentados de 2013 a 2016 e ` +
      `${media(2017, 2020)} dos de 2017 a 2020.` });
}

function renderLegislativo(l, t, nomes, ultimoDia) {
  const cartoes = ["c-pareceres", "c-relatores", "c-desfechos", "c-presidentes", "c-assuntos", "c-prazos", "c-membros", "c-funil",
                   "c-saidas"]
    .map((id) => document.getElementById(id));
  for (const cartao of cartoes) cartao.querySelector(".erro-fluxos")?.remove();
  if (!(t instanceof Error) && t) renderSaidas(t, nomes);
  if (l instanceof Error || !l) {
    for (const cartao of cartoes.slice(0, -1)) cartao.append(el("p", "vazio erro-fluxos", `Erro ao carregar os dados: ${l?.message ?? ""}`));
    return;
  }
  renderPareceres(l, nomes, ultimoDia);
  renderPrazos(l);
  renderRelatores(l);
  renderPresidentes(l);
  renderMembros(l, ultimoDia);
  renderAssuntos(l);
  renderDesfechos(l);
  renderFunil(l);
}

function renderTramitacao(t, nomes, ultimoDia) {
  const cartoes = ["c-producao", "c-tempos", "c-calendario"].map((id) => document.getElementById(id));
  for (const cartao of cartoes) cartao.querySelector(".erro-fluxos")?.remove();
  if (t instanceof Error) {
    for (const cartao of cartoes) cartao.append(el("p", "vazio erro-fluxos", `Erro ao carregar os dados: ${t.message}`));
    return;
  }
  renderProducao(t, nomes, ultimoDia);
  renderCalendario(t, ultimoDia);
  renderTempos(t, nomes);
}

function renderFluxos(f, nomes) {
  const cartoes = ["c-fluxo", "c-permanencia", "c-rotas", "c-composicao"].map((id) => document.getElementById(id));
  for (const cartao of cartoes) cartao.querySelector(".erro-fluxos")?.remove();
  if (f instanceof Error) {
    for (const cartao of cartoes) cartao.append(el("p", "vazio erro-fluxos", `Erro ao carregar os dados: ${f.message}`));
    return;
  }
  renderFluxo(f, nomes);
  renderPermanencia(f, nomes);
  renderRotas(f);
}


// Últimos 7 dias, comparados com a média semanal do último ano.
function renderResumoSemana(j, serie, f, t) {
  const caixa = document.getElementById("resumo-semana");
  if (!f || f instanceof Error || !t || t instanceof Error) { caixa.hidden = true; return; }
  caixa.hidden = false;
  const fim = f.fimDia;
  const todas = estado.comissao === "TODAS";
  const semana = (de, ate) => {  // entradas e saídas em (de, ate]
    let entradas = 0;
    let saidas = 0;
    for (const i of passagensDoRecorte(f)) {
      const d = f.desde[i];
      const a = f.ate[i];
      if (d != null && d > de && d <= ate && !(todas && f.grupoOrigem[i] === "comissao")) entradas++;
      if (a != null && a > de && a <= ate && !(todas && f.grupoDestino[i] === "comissao")) saidas++;
    }
    return { entradas, saidas };
  };
  const agora = semana(fim - 7, fim);
  const ano = semana(fim - 364, fim);
  const votos = diasDoCalendario(t.calendario[estado.grupo][estado.comissao].votos, utc(t.calendario.inicio));
  let votosSemana = 0;
  let votosAno = 0;
  for (const [iso, n] of votos) {
    const dia = dataParaDia(f, utc(iso));
    if (dia > fim - 7 && dia <= fim) votosSemana += n;
    if (dia > fim - 364 && dia <= fim) votosAno += n;
  }
  const u = j.datas.length - 1;
  const k = d3.bisectLeft(j.datasObj, new Date(j.datasObj[u] - 7 * DIA));
  const variacao = serie.materias[u] - serie.materias[k];
  const media = (n) => `média semanal no último ano: ${fmt(Math.round(n / 52))}`;
  const itens = [
    { rotulo: "Acervo", valor: fmt(serie.materias[u]), nota: `${variacao >= 0 ? "+" : "−"}${fmt(Math.abs(variacao))} na semana` },
    { rotulo: "Entradas", valor: fmt(agora.entradas), nota: media(ano.entradas) },
    { rotulo: "Saídas", valor: fmt(agora.saidas), nota: media(ano.saidas) },
    { rotulo: "Votações", valor: fmt(votosSemana), nota: media(votosAno) },
  ];
  const de = diaParaData(f, fim - 6);
  const onde = estado.comissao === "TODAS" ? "nas 7 comissões" : `na ${rotuloComissao(estado.comissao)}`;
  caixa.replaceChildren(
    el("p", "resumo-titulo", `Últimos 7 dias ${onde}, de ${dataBR(de).slice(0, 5)} a ${dataBR(diaParaData(f, fim))}`),
    ...itens.map((it) => {
      const d = el("div", "kpi");
      d.append(el("p", "rotulo", it.rotulo), el("p", "valor", it.valor), el("p", "nota", it.nota));
      return d;
    }));
}

// Atalhos para os gráficos da aba, na ordem da página (só os visíveis).
function renderSumario() {
  const nav = document.getElementById("sumario-evolucao");
  const linhas = [];
  for (const e of document.querySelectorAll("#painel-evolucao > .secao, #painel-evolucao > .cartao")) {
    if (e.hidden) continue;
    const alvo = e;
    const a = el("a", null, e.classList.contains("secao") ? e.textContent : e.dataset.curto);
    a.href = `#${e.id}`;
    a.addEventListener("click", (ev) => {  // sem mexer no endereço, que guarda os filtros
      ev.preventDefault();
      alvo.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    if (e.classList.contains("secao")) {
      const linha = el("p", "sumario-linha");
      a.className = "sumario-secao";
      linha.append(a);
      linhas.push(linha);
    } else {
      linhas[linhas.length - 1]?.append(a);
    }
  }
  nav.replaceChildren(...linhas);
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
  document.getElementById("periodo-livre").hidden = retrato || estado.periodo !== "livre";
  document.querySelector('.atalhos a[data-aba="retrato"]').hidden = !retrato;  // "Por autor" é do retrato
}

async function render() {
  const conteudo = document.getElementById("conteudo");
  conteudo.classList.add("carregando");
  let j;
  let fluxos = null;
  let tramitacao = null;
  let legislativo = null;
  try {
    j = await carregar(estado.grupo);
    ultimoDiaDados = j.datasObj[j.datasObj.length - 1];
    if (!cache.eventos) cache.eventos = await fetch("dados/eventos.json").then((r) => (r.ok ? r.json() : [])).catch(() => []);
    if (estado.aba === "retrato") await carregarRetrato();
    else {  // sem estes arquivos, os outros gráficos ainda saem
      [fluxos, tramitacao, legislativo] = await Promise.all([carregarFluxos().catch((e) => e),
        carregarTramitacao().catch((e) => e), carregarLegislativo().catch((e) => e)]);
    }
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
  else renderEvolucao(j, serie, fluxos, tramitacao, legislativo);
}

// ----------------------------------------------------------------------------- retrato do dia
const SPLEGIS = "https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/DetailsMateriaTramitacaoLegislativa/";
const RELATORIO = "https://splegisconsulta.saopaulo.sp.leg.br/Relatorio/IndexComissaoProjetoTramitacaoInterna";
// Faixas de tempo, da base da barra para a ponta (as mesmas da evolução).
const FAIXAS_TEMPO = [
  { chave: "mais365", nome: "Mais de 1 ano", cor: "--idade-5", min: 366 },
  { chave: "181a365", nome: "181 a 365 dias", cor: "--idade-4", min: 181 },
  { chave: "91a180", nome: "91 a 180 dias", cor: "--idade-3", min: 91 },
  { chave: "31a90", nome: "31 a 90 dias", cor: "--idade-2", min: 31 },
  { chave: "ate30", nome: "Até 30 dias", cor: "--idade-1", min: 0 },
];
const AGUARDANDO = { chave: "aguardando", nome: "Aguardando recebimento", cor: "--cinza-1" };
const SEM_PASSO = { chave: "sempasso", nome: "Sem estado interno", cor: "--cinza-2" };
const PRIMEIRAS = 15;  // linhas visíveis antes de "Mostrar todos"
const ORDEM_COMISSOES = ["CCJ", "FIN", "URB", "ADM", "ECON", "EDUC", "SAUDE"];
// Grupos que não são partidos, com a descrição mostrada ao lado do nome.
const GRUPOS_ESPECIAIS = {
  Executivo: "prefeitos agregados",
  "Mesa Diretora": "períodos e legislaturas agregados",
  Institucional: "autoria institucional",
  Remetentes: "remetente",
  Outros: "",
};

const retrato = {
  dados: null,
  modos: { "r-relator": "total", "r-passo": "total", "r-autores": "idade", "s-relator": "total", "s-passo": "total" },
  agrupar: "autor",
  todos: new Set(),
  selecao: [],  // [{ tipo: "autor" | "partido", chave }]
  janela: { titulo: "", sub: "", lista: [], limite: 100, ordem: { campo: "dc", desc: true } },
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
    nome: (k) => (k === "" ? ["Sem estado informado", "", true] : [k, "", false]),
    dias: (m) => m.dp, semDado: SEM_PASSO,
  },
  autor: {
    chaves: (m) => (m.a.length ? m.a : [-1]),
    nome: (k, d) => {
      if (k === -1) return ["Sem autoria informada", "", true];
      const [nome, grupo] = d.pessoas[k];
      return [nome, grupo in GRUPOS_ESPECIAIS ? GRUPOS_ESPECIAIS[grupo] : grupo, false];
    },
    dias: (m) => m.dc, semDado: AGUARDANDO,
  },
  partido: {
    chaves: (m) => (m.a.length ? [...new Set(m.a.map((a) => retrato.dados.pessoas[a][1]))] : ["—"]),
    nome: (k) => [k, GRUPOS_ESPECIAIS[k] ?? "", k in GRUPOS_ESPECIAIS || k === "—"],
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
const pct = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const porcento = (parte, todo) => (todo ? `${pct.format((100 * parte) / todo)}%` : "—");

function faixaDe(dias, semDado) {
  return dias == null ? semDado.chave : FAIXAS_TEMPO.find((f) => dias >= f.min).chave;
}

function nomeFaixa(chave) {
  return [...FAIXAS_TEMPO, AGUARDANDO, SEM_PASSO].find((f) => f.chave === chave)?.nome ?? "";
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
  if (dimensao === "passo") {  // o mesmo estado aparece em áreas diferentes; mostra a mais comum
    for (const l of lista) l.grupo = [...l.areas].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
  }
  lista.sort((a, b) => b.total - a.total || a.nome.localeCompare(b.nome, "pt-BR"));
  const i = lista.findIndex((l) => l.chave === dim.fixar);
  if (i > 0) lista.unshift(...lista.splice(i, 1));
  return lista;
}

// ----------------------------------------------------------------------------- barras
// Cada cartão de barras (id) tem modo ("total" ou "idade"), legenda e "Mostrar todos".
function renderBarras(id, dimensao, linhas, aoClicar, marcado) {
  const cartao = document.getElementById(id);
  const porTempo = retrato.modos[id] === "idade";
  const c = cores();
  const faixas = [...FAIXAS_TEMPO, DIMENSOES[dimensao].semDado];
  const presentes = faixas.filter((f) => linhas.some((l) => l.faixas[f.chave]));
  const ul = cartao.querySelector(".legenda");
  ul.hidden = !porTempo;
  if (porTempo) legenda(cartao, presentes);
  for (const b of cartao.querySelectorAll(".alternador:not([data-grupo]) button")) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === retrato.modos[id]));
  }
  const max = d3.max(linhas, (l) => l.total) || 1;
  const todos = retrato.todos.has(id);
  const ol = cartao.querySelector(".barras");
  ol.replaceChildren(...linhas.slice(0, todos ? Infinity : PRIMEIRAS)
    .map((l) => linhaBarra(l, presentes, max, porTempo, c, aoClicar, marcado?.(l))));
  if (!linhas.length) ol.replaceChildren(el("li", "vazio", "Nenhuma matéria neste recorte."));
  const mais = cartao.querySelector(".mais");
  mais.hidden = linhas.length <= PRIMEIRAS;
  mais.textContent = todos ? `Mostrar só os ${PRIMEIRAS} primeiros` : `Mostrar todos (${linhas.length})`;
}

function linhaBarra(l, faixas, max, porTempo, c, aoClicar, marcado) {
  const botao = el("button", "barra-linha");
  botao.type = "button";
  if (marcado != null) botao.setAttribute("aria-pressed", String(marcado));
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
    if (f) seg.dataset.faixa = f.chave;
    trilho.append(seg);
  }
  botao.append(nome, trilho, el("span", "barra-valor", fmt(l.total)));
  const detalhe = porTempo ? ` (${partes.map((p) => `${fmt(p.n)}: ${p.f.nome.toLowerCase()}`).join("; ")})` : "";
  botao.setAttribute("aria-label", `${completo}: ${fmt(l.total)} matérias${detalhe}.`);
  botao.addEventListener("click", (ev) => aoClicar(l, ev.target.closest(".seg")?.dataset.faixa ?? null, completo));
  const li = el("li");
  li.append(botao);
  return li;
}

// ----------------------------------------------------------------------------- lista de matérias
const ORDENS = {
  c: (m) => ORDEM_COMISSOES.indexOf(m.c),
  r: (m) => {
    const [tipo, resto] = m.r.split(" ");
    const [numero, ano] = resto.split("/");
    return `${ano}-${numero.padStart(6, "0")}-${tipo}`;
  },
  aut: (m) => (m.a.length ? semAcento(retrato.dados.pessoas[m.a[0]][0]) : "~"),
  e: (m) => semAcento(m.e),
  rel: (m) => (m.rel == null ? "~" : semAcento(retrato.dados.pessoas[m.rel][0])),
  pa: (m) => semAcento(m.pa || "~"),
  pt: (m) => semAcento(m.pt || "~"),
  dc: (m) => m.dc ?? -1,
  dp: (m) => m.dp ?? -1,
};

function autoria(m, todos = false) {
  const nomes = m.a.map((a) => {
    const [nome, grupo] = retrato.dados.pessoas[a];
    return grupo in GRUPOS_ESPECIAIS ? nome : `${nome} (${grupo})`;
  });
  if (todos || nomes.length <= 3) return nomes.join("; ");
  return `${nomes.slice(0, 2).join("; ")} e mais ${nomes.length - 2}`;
}

function relator(m) {
  if (m.rel == null) return "";
  const [nome, grupo] = retrato.dados.pessoas[m.rel];
  return `${nome} (${grupo})`;
}

function ordenar(lista, { campo, desc }) {
  const chave = ORDENS[campo];
  return [...lista].sort((a, b) => {
    const [x, y] = [chave(a), chave(b)];
    return (x < y ? -1 : x > y ? 1 : 0) * (desc ? -1 : 1) || ORDENS.r(b).localeCompare(ORDENS.r(a));
  });
}

function nomeComissaoAtual() {
  return estado.comissao === "TODAS" ? "Todas as comissões"
    : `${estado.comissao} — ${COMISSOES.find(([s]) => s === estado.comissao)[1]}`;
}

function abrirLista(titulo, materias) {
  const j = retrato.janela;
  j.titulo = titulo;
  j.lista = materias;
  j.limite = 100;
  const quais = estado.grupo === "projetos" ? "projeto(s)" : "matéria(s)";
  j.sub = `${nomeComissaoAtual()} · ${fmt(materias.length)} ${quais} no recorte · Clique nos títulos das colunas para ordenar.`;
  renderJanela();
  const dialogo = document.getElementById("janela-lista");
  if (!dialogo.open) dialogo.showModal();
}

const COLUNAS_JANELA = [
  ["c", "Comissão"], ["r", "Matéria"], ["aut", "Autor(es)"], ["e", "Ementa"], ["rel", "Relator"],
  ["pa", "Local atual"], ["pt", "Estado atual"], ["dc", "Dias na comissão"], ["dp", "Dias no estado"],
];

function renderJanela() {
  const j = retrato.janela;
  document.getElementById("janela-titulo").textContent = j.titulo;
  document.getElementById("janela-sub").textContent = j.sub;
  const lista = ordenar(j.lista, j.ordem);
  const colunas = COLUNAS_JANELA.filter(([c]) => c !== "c" || estado.comissao === "TODAS");
  const tabela = el("table");
  const cab = el("tr");
  for (const [campo, nome] of colunas) {
    const th = el("th");
    th.scope = "col";
    const b = el("button", null, nome);
    b.type = "button";
    b.dataset.campo = campo;
    th.append(b);
    if (j.ordem.campo === campo) th.setAttribute("aria-sort", j.ordem.desc ? "descending" : "ascending");
    cab.append(th);
  }
  tabela.append(el("thead"), el("tbody"));
  tabela.tHead.append(cab);
  for (const m of lista.slice(0, j.limite)) {
    const tr = el("tr");
    if (estado.comissao === "TODAS") tr.append(el("td", null, m.c));
    const tdMateria = el("td", "materia");
    const link = el("a", null, `${m.r} ↗`);
    link.href = SPLEGIS + m.id;
    link.target = "_blank";
    link.rel = "noopener";
    tdMateria.append(link);
    const tdEmenta = el("td", "ementa");
    const ementa = el("span", null, m.e);
    ementa.title = m.e;
    tdEmenta.append(ementa);
    const tdRelator = el("td", null, relator(m) || "Sem relator");
    if (m.rel == null) tdRelator.classList.add("muted");
    tr.append(tdMateria, el("td", "autores", autoria(m)), tdEmenta, tdRelator, el("td", null, m.pa || "—"),
              el("td", null, m.pt || "—"),
              el("td", "num", m.dc == null ? "aguardando" : fmt(m.dc)), el("td", "num", fmt(m.dp)));
    tabela.tBodies[0].append(tr);
  }
  const caixa = document.getElementById("janela-tabela");
  caixa.replaceChildren(lista.length ? tabela : el("p", "vazio", "Nenhuma matéria neste recorte."));
  const mais = document.getElementById("janela-mais");
  const restantes = lista.length - j.limite;
  mais.hidden = restantes <= 0;
  mais.textContent = `Mostrar mais ${fmt(Math.min(100, restantes))} (faltam ${fmt(restantes)})`;
}

// ----------------------------------------------------------------------------- exportações
const COLUNAS_EXPORTACAO = [
  { nome: "Processo", largura: 15 }, { nome: "Tipo", largura: 8 }, { nome: "Número", largura: 9 },
  { nome: "Ano", largura: 8 }, { nome: "Comissão", largura: 10 }, { nome: "Ementa", largura: 60 },
  { nome: "Autor", largura: 30 }, { nome: "Relator", largura: 30 }, { nome: "Data da tramitação", largura: 20 },
  { nome: "Local da tramitação", largura: 18 }, { nome: "Motivo da tramitação", largura: 28 },
  { nome: "Data da tramitação interna", largura: 22 }, { nome: "Local da tramitação interna", largura: 26 },
  { nome: "Estado atual", largura: 36 }, { nome: "Dias na comissão", largura: 10 },
  { nome: "Faixa — dias na comissão", largura: 22 }, { nome: "Dias no estado atual", largura: 10 },
  { nome: "Faixa — dias no estado atual", largura: 24 }, { nome: "Relatório detalhado", largura: 16 },
];

const dataHora = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)} ${iso.slice(11, 19)}`.trim() : "");

function linhaExportacao(m, xlsx) {
  const [tipo, resto] = m.r.split(" ");
  const [numero, ano] = resto.split("/");
  const recebida = !!m.rec;
  return [
    m.r, tipo, Number(numero), Number(ano), m.c, m.e, autoria(m, true), relator(m) || "Sem relator",
    dataHora(recebida ? m.rec : m.envd), m.c,
    m.env ? `${recebida ? "Recebido de" : "Pendente recebimento de"} ${m.env}` : "",
    dataHora(m.pd), m.pa, m.pt || "Sem estado informado",
    m.dc ?? "", nomeFaixa(faixaDe(m.dc, AGUARDANDO)), m.dp ?? "", nomeFaixa(faixaDe(m.dp, SEM_PASSO)),
    xlsx ? { link: SPLEGIS + m.id, texto: "Abrir no SPLEGIS" } : SPLEGIS + m.id,
  ];
}

function baixar(blob, arquivo) {
  const a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = arquivo;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function nomeArquivo(base, extensao) {
  const coleta = retrato.dados.coletado_em.slice(0, 16).replace("T", "_").replace(":", "");
  const limpo = semAcento(base).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
  return `acervo-comissoes-cmsp_${coleta}_${limpo}.${extensao}`;
}

async function exportar(formato, titulo, materias) {
  const lista = ordenar(materias, retrato.janela.ordem);
  if (formato === "csv") {
    const aspas = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
    const linhas = [COLUNAS_EXPORTACAO.map((c) => aspas(c.nome)).join(",")];
    for (const m of lista) linhas.push(linhaExportacao(m, false).map(aspas).join(","));
    // BOM para o Excel reconhecer o UTF-8 e os acentos
    baixar(new Blob(["﻿" + linhas.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" }),
           nomeArquivo(titulo, "csv"));
  } else if (formato === "xlsx") {
    const blob = await PlanilhaXlsx.gerar([{
      nome: "Matérias", titulo: `${titulo} · ${nomeComissaoAtual()}`,
      informacoes: [["Última atualização", dataHora(retrato.dados.coletado_em)], ["Fonte", RELATORIO],
                    ["Matérias", lista.length]],
      colunas: COLUNAS_EXPORTACAO, linhas: lista.map((m) => linhaExportacao(m, true)),
    }]);
    baixar(blob, nomeArquivo(titulo, "xlsx"));
  } else {
    imprimir(titulo, lista);
  }
}

function imprimir(titulo, lista) {
  const caixa = document.getElementById("impressao");
  const tabela = el("table");
  const cab = el("tr");
  for (const nome of ["Matéria", "Autor(es)", "Ementa", "Relator", "Estado atual", "Dias na comissão"]) {
    cab.append(el("th", null, nome));
  }
  tabela.append(el("thead"), el("tbody"));
  tabela.tHead.append(cab);
  for (const m of lista) {
    const tr = el("tr");
    tr.append(el("td", null, `${estado.comissao === "TODAS" ? `${m.c} · ` : ""}${m.r}`), el("td", null, autoria(m, true)),
              el("td", null, m.e), el("td", null, relator(m) || "Sem relator"), el("td", null, m.pt || "—"),
              el("td", null, m.dc == null ? "aguardando" : fmt(m.dc)));
    tabela.tBodies[0].append(tr);
  }
  caixa.replaceChildren(el("h1", null, titulo),
                        el("p", null, `${nomeComissaoAtual()} · ${fmt(lista.length)} matéria(s) · ` +
                                      `retrato de ${dataHora(retrato.dados.coletado_em)} · fonte: SPLEGIS`),
                        tabela);
  document.body.classList.add("imprimindo");
  const terminar = () => {
    document.body.classList.remove("imprimindo");
    caixa.replaceChildren();
    window.removeEventListener("afterprint", terminar);
  };
  window.addEventListener("afterprint", terminar);
  window.print();
}

async function relatorioConsolidado() {
  const botao = document.getElementById("baixar-relatorio");
  botao.disabled = true;
  try {
    const d = await carregarRetrato();
    const quais = estado.grupo === "projetos" ? "projetos" : "matérias";
    const abas = ORDEM_COMISSOES.map((sigla) => {
      const mats = d.materias.filter((m) => m.c === sigla && (estado.grupo === "todas" || m.p));
      return {
        nome: sigla, titulo: `Acervo de ${quais} em análise — ${sigla === "SAUDE" ? "SAÚDE" : sigla}`,
        informacoes: [["Última atualização", dataHora(d.coletado_em)], ["Fonte", RELATORIO]],
        colunas: COLUNAS_EXPORTACAO,
        linhas: ordenar(mats, { campo: "r", desc: true }).map((m) => linhaExportacao(m, true)),
      };
    });
    const coleta = d.coletado_em.slice(0, 16).replace("T", "_").replace(":", "");
    baixar(await PlanilhaXlsx.gerar(abas), `acervo-comissoes-cmsp_${coleta}_${estado.grupo}.xlsx`);
  } catch (e) {
    mostrarErro(`Não foi possível gerar o relatório: ${e.message}`);
  } finally {
    botao.disabled = false;
  }
}

// ----------------------------------------------------------------------------- pesquisa por autor
function noSelecao(m) {
  const pessoas = retrato.dados.pessoas;
  return retrato.selecao.some((s) => (s.tipo === "autor" ? m.a.includes(s.chave)
                                                         : m.a.some((a) => pessoas[a][1] === s.chave)));
}

function nomeSelecao(s) {
  if (s.tipo === "partido") return `Partido: ${s.chave}`;
  const [nome, grupo] = retrato.dados.pessoas[s.chave];
  return grupo in GRUPOS_ESPECIAIS ? nome : `${nome} (${grupo})`;
}

function alternarSelecao(item) {
  const i = retrato.selecao.findIndex((s) => s.tipo === item.tipo && s.chave === item.chave);
  if (i >= 0) retrato.selecao.splice(i, 1);
  else retrato.selecao.push(item);
  renderRetrato();
}

function opcoesAutoria(mats) {
  const autores = agrupar(mats, "autor").filter((l) => l.chave !== -1);
  const partidos = agrupar(mats, "partido").filter((l) => !(l.chave in GRUPOS_ESPECIAIS) && l.chave !== "—");
  return { autores, partidos };
}

function renderSugestoes(mats, abrirTudo = false) {
  const entrada = document.getElementById("busca-autor");
  const ul = document.getElementById("sugestoes-autor");
  const termo = semAcento(entrada.value.trim());
  if (!termo && !abrirTudo) {
    ul.hidden = true;
    entrada.setAttribute("aria-expanded", "false");
    return;
  }
  const { autores, partidos } = opcoesAutoria(mats);
  const opcoes = [
    ...partidos.map((l) => ({ tipo: "partido", chave: l.chave, texto: `Todos do ${l.chave}`, info: `partido · ${fmt(l.total)}` })),
    ...autores.map((l) => ({ tipo: "autor", chave: l.chave, texto: l.nome, info: `${l.grupo || "autor"} · ${fmt(l.total)}` })),
  ].filter((o) => !termo || semAcento(`${o.texto} ${o.info}`).includes(termo))
   .filter((o) => !retrato.selecao.some((s) => s.tipo === o.tipo && s.chave === o.chave));
  ul.replaceChildren(...opcoes.slice(0, 50).map((o, i) => {
    const li = el("li");
    li.id = `sugestao-${i}`;
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", "false");
    li.append(el("span", null, o.texto), el("span", "tipo", o.info));
    li.addEventListener("mousedown", (ev) => { ev.preventDefault(); escolherSugestao(o); });
    li.opcao = o;
    return li;
  }));
  if (!opcoes.length) ul.replaceChildren(el("li", "vazio", "Nenhum autor ou partido encontrado."));
  ul.hidden = false;
  entrada.setAttribute("aria-expanded", "true");
}

function escolherSugestao(o) {
  const entrada = document.getElementById("busca-autor");
  entrada.value = "";
  document.getElementById("sugestoes-autor").hidden = true;
  entrada.setAttribute("aria-expanded", "false");
  entrada.removeAttribute("aria-activedescendant");
  alternarSelecao({ tipo: o.tipo, chave: o.chave });
}

function renderAutoria(mats) {
  const { autores, partidos } = opcoesAutoria(mats);
  document.getElementById("autor-contagem").textContent =
    `${fmt(autores.length)} autores ou órgãos identificados nesta seleção de comissão.`;

  // Seleção rápida por partido
  const chips = document.getElementById("chips-partidos");
  chips.replaceChildren(...[...partidos].sort((a, b) => a.chave.localeCompare(b.chave, "pt-BR")).map((l) => {
    const b = el("button", null, l.chave);
    b.type = "button";
    const ativo = retrato.selecao.some((s) => s.tipo === "partido" && s.chave === l.chave);
    b.setAttribute("aria-pressed", String(ativo));
    b.title = `${fmt(l.total)} matérias de autores do ${l.chave}`;
    b.addEventListener("click", () => alternarSelecao({ tipo: "partido", chave: l.chave }));
    return b;
  }));

  // Seleção atual
  const ul = document.getElementById("chips-selecao");
  ul.replaceChildren(...retrato.selecao.map((s) => {
    const li = el("li", "chip", nomeSelecao(s));
    const x = el("button", null, "×");
    x.type = "button";
    x.setAttribute("aria-label", `Remover ${nomeSelecao(s)}`);
    x.addEventListener("click", () => alternarSelecao(s));
    li.append(x);
    return li;
  }));
  document.getElementById("selecao-vazia").hidden = retrato.selecao.length > 0;
  document.getElementById("limpar-selecao").hidden = !retrato.selecao.length;

  // Lista nominal (clicar inclui na seleção)
  const linhas = retrato.agrupar === "autor" ? autores : agrupar(mats, "partido");
  for (const b of document.querySelectorAll('#r-autores .alternador[data-grupo="agrupar"] button')) {
    b.setAttribute("aria-pressed", String(b.dataset.modo === retrato.agrupar));
  }
  const tipo = retrato.agrupar;
  renderBarras("r-autores", tipo, linhas,
               (l) => { if (l.chave !== "—") alternarSelecao({ tipo, chave: l.chave }); },
               (l) => retrato.selecao.some((s) => s.tipo === tipo && s.chave === l.chave));

  renderResultado(mats);
}

function renderResultado(mats) {
  const caixa = document.getElementById("resultado-autor");
  caixa.hidden = !retrato.selecao.length;
  if (caixa.hidden) return;
  const selecionadas = mats.filter(noSelecao);
  const recebidas = selecionadas.filter((m) => m.dc != null).map((m) => m.dc).sort((a, b) => a - b);
  const meio = Math.floor(recebidas.length / 2);
  const mediana = !recebidas.length ? null
    : recebidas.length % 2 ? recebidas[meio] : Math.floor((recebidas[meio - 1] + recebidas[meio]) / 2);
  const semRelator = selecionadas.filter((m) => m.rel == null).length;
  const mais180 = selecionadas.filter((m) => m.dc != null && m.dc > 180).length;
  const quais = estado.grupo === "projetos" ? "projeto(s) encontrado(s)" : "matéria(s) encontrada(s)";
  const kpis = [
    { rotulo: "Na seleção", valor: fmt(selecionadas.length), nota: quais },
    { rotulo: "Sem relator", valor: fmt(semRelator), nota: `${porcento(semRelator, selecionadas.length)} da seleção` },
    { rotulo: "Mais de 180 dias", valor: fmt(mais180), nota: `${porcento(mais180, selecionadas.length)} da seleção` },
    { rotulo: "Idade mediana", valor: mediana == null ? "—" : `${fmt(mediana)} dias`, nota: "metade da seleção abaixo" },
  ];
  document.getElementById("kpis-selecao").replaceChildren(...kpis.map((k) => {
    const div = el("div", "kpi");
    div.append(el("p", "rotulo", k.rotulo), el("p", "valor", k.valor), el("p", "nota", k.nota));
    return div;
  }));

  const c = cores();
  const contagem = {};
  for (const m of selecionadas) {
    const f = faixaDe(m.dc, AGUARDANDO);
    contagem[f] = (contagem[f] || 0) + 1;
  }
  const faixas = [...FAIXAS_TEMPO].reverse().concat(AGUARDANDO).filter((f) => f !== AGUARDANDO || contagem[f.chave]);
  document.getElementById("faixas-selecao").replaceChildren(...faixas.map((f) => {
    const li = el("li");
    li.style.borderLeftColor = c.v(f.cor);
    li.append(el("strong", null, fmt(contagem[f.chave] || 0)), el("span", null, f.nome));
    return li;
  }));

  renderBarras("s-relator", "relator", agrupar(selecionadas, "relator"),
               (l, faixa, nome) => abrirLista(rotuloRecorte(`Relator: ${nome}`, faixa),
                                              selecionadas.filter((m) => noRecorte(m, { dim: "relator", chave: l.chave, faixa }))));
  renderBarras("s-passo", "passo", agrupar(selecionadas, "passo"),
               (l, faixa, nome) => abrirLista(rotuloRecorte(`Estado: ${nome}`, faixa),
                                              selecionadas.filter((m) => noRecorte(m, { dim: "passo", chave: l.chave, faixa }))));
}

function rotuloRecorte(base, faixa) {
  return faixa ? `${base} · ${nomeFaixa(faixa)}` : base;
}

// ----------------------------------------------------------------------------- retrato
function renderRetrato() {
  const d = retrato.dados;
  const mats = materiasDoFiltro();
  const quais = estado.grupo === "projetos" ? "projetos" : "matérias";
  document.getElementById("nota-retrato").textContent =
    `Retrato de ${dataBR(utc(d.data))}, com ${fmt(mats.length)} ${quais}. Gráficos interativos: clique ou toque ` +
    "em qualquer barra ou trecho colorido para abrir a lista completa das matérias daquele recorte, acessar os " +
    "projetos no SPLEGIS e exportar a seleção.";
  renderBarras("r-relator", "relator", agrupar(mats, "relator"),
               (l, faixa, nome) => abrirLista(rotuloRecorte(`Relator: ${nome}`, faixa),
                                              mats.filter((m) => noRecorte(m, { dim: "relator", chave: l.chave, faixa }))));
  renderBarras("r-passo", "passo", agrupar(mats, "passo"),
               (l, faixa, nome) => abrirLista(rotuloRecorte(`Estado: ${nome}`, faixa),
                                              mats.filter((m) => noRecorte(m, { dim: "passo", chave: l.chave, faixa }))));
  renderAutoria(mats);
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
  document.querySelector('#r-autores .alternador[data-grupo="agrupar"]').addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    retrato.agrupar = b.dataset.modo;
    renderRetrato();
  });
  document.getElementById("ver-todas").addEventListener("click", () =>
    abrirLista(estado.grupo === "projetos" ? "Todos os projetos" : "Todas as matérias", materiasDoFiltro()));
  document.getElementById("limpar-selecao").addEventListener("click", () => {
    retrato.selecao = [];
    renderRetrato();
  });
  document.getElementById("selecao-lista").addEventListener("click", () =>
    abrirLista("Autores: seleção completa", materiasDoFiltro().filter(noSelecao)));
  for (const b of document.querySelectorAll("[data-exportar-selecao]")) {
    b.addEventListener("click", () => exportar(b.dataset.exportarSelecao, "Autores: seleção completa",
                                              materiasDoFiltro().filter(noSelecao)));
  }

  // Combobox de autores e partidos
  const entrada = document.getElementById("busca-autor");
  const ul = document.getElementById("sugestoes-autor");
  let ativo = -1;
  const marcar = (i) => {
    const itens = [...ul.querySelectorAll("li[role=option]")];
    if (!itens.length) return;
    ativo = (i + itens.length) % itens.length;
    itens.forEach((li, k) => li.setAttribute("aria-selected", String(k === ativo)));
    entrada.setAttribute("aria-activedescendant", itens[ativo].id);
    itens[ativo].scrollIntoView({ block: "nearest" });
  };
  entrada.addEventListener("input", () => { ativo = -1; renderSugestoes(materiasDoFiltro()); });
  entrada.addEventListener("focus", () => { if (entrada.value) renderSugestoes(materiasDoFiltro()); });
  entrada.addEventListener("blur", () => setTimeout(() => { ul.hidden = true; entrada.setAttribute("aria-expanded", "false"); }, 120));
  entrada.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") { if (ul.hidden) renderSugestoes(materiasDoFiltro(), true); marcar(ativo + 1); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { marcar(ativo - 1); ev.preventDefault(); }
    else if (ev.key === "Enter") {
      const itens = [...ul.querySelectorAll("li[role=option]")];
      const li = itens[ativo] || itens[0];
      if (li && !ul.hidden) { escolherSugestao(li.opcao); ev.preventDefault(); }
    } else if (ev.key === "Escape") { ul.hidden = true; entrada.setAttribute("aria-expanded", "false"); }
  });
  document.getElementById("abrir-sugestoes").addEventListener("mousedown", (ev) => {
    ev.preventDefault();
    if (ul.hidden) { entrada.focus(); renderSugestoes(materiasDoFiltro(), true); }
    else ul.hidden = true;
  });

  // Janela da lista
  const dialogo = document.getElementById("janela-lista");
  document.getElementById("janela-fechar").addEventListener("click", () => dialogo.close());
  dialogo.addEventListener("click", (ev) => { if (ev.target === dialogo) dialogo.close(); });  // clique fora
  document.getElementById("janela-mais").addEventListener("click", () => {
    retrato.janela.limite += 100;
    renderJanela();
  });
  document.getElementById("janela-tabela").addEventListener("click", (ev) => {
    const b = ev.target.closest("th button");
    if (!b) return;
    const campo = b.dataset.campo;
    const textual = !["dc", "dp"].includes(campo);
    const atual = retrato.janela.ordem;
    retrato.janela.ordem = { campo, desc: atual.campo === campo ? !atual.desc : !textual };
    renderJanela();
  });
  for (const b of dialogo.querySelectorAll("[data-exportar]")) {
    b.addEventListener("click", () => exportar(b.dataset.exportar, retrato.janela.titulo, retrato.janela.lista));
  }
  document.getElementById("baixar-relatorio").addEventListener("click", relatorioConsolidado);

  // Dica dos trechos das barras: valor primeiro, nome depois.
  const dica = document.getElementById("dica-barras");
  document.addEventListener("pointermove", (ev) => {
    const seg = ev.target.closest?.(".barras .seg, .calendario .dia[data-n]");
    if (!seg) { dica.hidden = true; return; }
    const linha = el("div", "linha");
    const chave = el("span", "chave quadrado");
    chave.style.background = cores().v(seg.dataset.cor);
    linha.append(chave, el("strong", null, seg.dataset.n), el("span", "nome", seg.dataset.rotulo));
    const titulo = seg.dataset.titulo ?? seg.closest(".barra-linha").querySelector(".barra-nome").title;
    dica.replaceChildren(el("p", "data", titulo), linha);
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
  for (const chave of ["de", "ate"]) estado[chave] = /^\d{4}-\d{2}-\d{2}$/.test(p.get(chave) ?? "") ? p.get(chave) : "";
  if (["evolucao", "retrato"].includes(p.get("aba"))) estado.aba = p.get("aba");
}

function sincronizar() {
  for (const b of document.querySelectorAll("#f-comissao button")) {
    b.setAttribute("aria-pressed", String(b.dataset.comissao === estado.comissao));
  }
  document.getElementById("nome-comissao").textContent = estado.comissao === "TODAS"
    ? "Todas as comissões permanentes" : `${estado.comissao} · ${COMISSOES.find(([s]) => s === estado.comissao)[1]}`;
  document.getElementById("f-grupo").value = estado.grupo;
  document.getElementById("f-periodo").value = estado.periodo;
  document.getElementById("f-de").value = estado.de;
  document.getElementById("f-ate").value = estado.ate;
  document.getElementById("periodo-livre").hidden = estado.aba === "retrato" || estado.periodo !== "livre";
  history.replaceState(null, "", `#${new URLSearchParams(Object.entries(estado).filter(([, v]) => v))}`);
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
  preencher(document.getElementById("f-grupo"), GRUPOS, estado.grupo);
  document.getElementById("f-comissao").replaceChildren(...COMISSOES.map(([sigla, nome]) => {
    const b = el("button", null, sigla === "TODAS" ? "Todas" : sigla === "SAUDE" ? "SAÚDE" : sigla);
    b.type = "button";
    b.dataset.comissao = sigla;
    b.title = nome;
    b.addEventListener("click", () => {
      estado.comissao = sigla;
      sincronizar();
      render();
    });
    return b;
  }));
  for (const [id, chave] of [["f-periodo", "periodo"], ["f-grupo", "grupo"], ["f-de", "de"], ["f-ate", "ate"]]) {
    document.getElementById(id).addEventListener("change", (ev) => {
      estado[chave] = ev.target.value;
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
  // Atalhos do topo: "Por autor" fica na aba do retrato; os demais, no fim da página.
  for (const a of document.querySelectorAll(".atalhos a")) {
    a.addEventListener("click", async (ev) => {
      ev.preventDefault();
      if (a.dataset.aba && estado.aba !== a.dataset.aba) {
        estado.aba = a.dataset.aba;
        sincronizar();
        await render();
      }
      document.querySelector(a.getAttribute("href")).scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
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

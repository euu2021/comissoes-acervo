"use strict";
/* Gerador mínimo de planilhas .xlsx no navegador, sem bibliotecas: monta o XML do
   SpreadsheetML e o compacta num .zip (deflate via CompressionStream, quando há). */

const PlanilhaXlsx = (() => {
  const enc = new TextEncoder();

  // ------------------------------------------------------------------------- zip
  const TABELA_CRC = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = TABELA_CRC[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  async function compactar(bytes) {
    if (typeof CompressionStream === "undefined") return null;
    try {
      const fluxo = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate-raw"));
      return new Uint8Array(await new Response(fluxo).arrayBuffer());
    } catch (e) {
      return null;  // navegador sem deflate-raw: grava sem compressão
    }
  }

  async function zip(arquivos) {
    const agora = new Date();
    const hora = (agora.getHours() << 11) | (agora.getMinutes() << 5) | (agora.getSeconds() >> 1);
    const data = ((agora.getFullYear() - 1980) << 9) | ((agora.getMonth() + 1) << 5) | agora.getDate();
    const partes = [];
    const central = [];
    let deslocamento = 0;
    for (const { nome, conteudo } of arquivos) {
      const bruto = enc.encode(conteudo);
      const compacto = await compactar(bruto);
      const metodo = compacto ? 8 : 0;
      const dados = compacto || bruto;
      const nomeBytes = enc.encode(nome);
      const crc = crc32(bruto);

      const local = new DataView(new ArrayBuffer(30));
      local.setUint32(0, 0x04034b50, true);
      local.setUint16(4, 20, true);
      local.setUint16(6, 0x0800, true);  // nomes em UTF-8
      local.setUint16(8, metodo, true);
      local.setUint16(10, hora, true);
      local.setUint16(12, data, true);
      local.setUint32(14, crc, true);
      local.setUint32(18, dados.length, true);
      local.setUint32(22, bruto.length, true);
      local.setUint16(26, nomeBytes.length, true);
      partes.push(new Uint8Array(local.buffer), nomeBytes, dados);

      const cd = new DataView(new ArrayBuffer(46));
      cd.setUint32(0, 0x02014b50, true);
      cd.setUint16(4, 20, true);
      cd.setUint16(6, 20, true);
      cd.setUint16(8, 0x0800, true);
      cd.setUint16(10, metodo, true);
      cd.setUint16(12, hora, true);
      cd.setUint16(14, data, true);
      cd.setUint32(16, crc, true);
      cd.setUint32(20, dados.length, true);
      cd.setUint32(24, bruto.length, true);
      cd.setUint16(28, nomeBytes.length, true);
      cd.setUint32(42, deslocamento, true);
      central.push(new Uint8Array(cd.buffer), nomeBytes);
      deslocamento += 30 + nomeBytes.length + dados.length;
    }
    const tamanhoCentral = central.reduce((t, p) => t + p.length, 0);
    const fim = new DataView(new ArrayBuffer(22));
    fim.setUint32(0, 0x06054b50, true);
    fim.setUint16(8, arquivos.length, true);
    fim.setUint16(10, arquivos.length, true);
    fim.setUint32(12, tamanhoCentral, true);
    fim.setUint32(16, deslocamento, true);
    return new Blob([...partes, ...central, new Uint8Array(fim.buffer)],
                    { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  }

  // ------------------------------------------------------------------------- planilha
  const esc = (v) => String(v)
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function coluna(i) {
    let s = "";
    for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
    return s;
  }

  // Estilos: 0 padrão, 1 título, 2 cabeçalho, 3 link, 4 rótulo das informações
  const ESTILOS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="4"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="14"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font><font><u/><sz val="11"/><color rgb="FF2A78D6"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE1E0D9"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;

  function celula(ref, valor, estilo = 0) {
    const s = estilo ? ` s="${estilo}"` : "";
    if (valor == null || valor === "") return "";
    if (typeof valor === "number" && Number.isFinite(valor)) return `<c r="${ref}"${s}><v>${valor}</v></c>`;
    if (typeof valor === "object" && valor.link) {  // fórmula HYPERLINK: dispensa as relações do pacote
      const url = esc(valor.link.replace(/"/g, '""'));
      const texto = esc((valor.texto || valor.link).replace(/"/g, '""'));
      return `<c r="${ref}" s="3" t="str"><f>HYPERLINK("${url}","${texto}")</f><v>${esc(valor.texto || valor.link)}</v></c>`;
    }
    return `<c r="${ref}"${s} t="inlineStr"><is><t xml:space="preserve">${esc(valor)}</t></is></c>`;
  }

  function aba(a, indice) {
    // a: { nome, titulo, informacoes: [[rótulo, valor]], colunas: [{ nome, largura }], linhas: [[...]] }
    const linhas = [];
    let r = 1;
    const ultimaCol = coluna(a.colunas.length - 1);
    if (a.titulo) linhas.push(`<row r="${r}">${celula(`A${r++}`, a.titulo, 1)}</row>`);
    for (const [rotulo, valor] of a.informacoes || []) {
      linhas.push(`<row r="${r}">${celula(`A${r}`, rotulo, 4)}${celula(`B${r}`, valor)}</row>`);
      r++;
    }
    const cabecalho = r;
    linhas.push(`<row r="${r}">${a.colunas.map((c, i) => celula(`${coluna(i)}${r}`, c.nome, 2)).join("")}</row>`);
    r++;
    for (const valores of a.linhas) {
      linhas.push(`<row r="${r}">${valores.map((v, i) => celula(`${coluna(i)}${r}`, v)).join("")}</row>`);
      r++;
    }
    const fimDados = Math.max(cabecalho, r - 1);
    const cols = a.colunas.map((c, i) => `<col min="${i + 1}" max="${i + 1}" width="${c.largura || 14}" customWidth="1"/>`).join("");
    const xml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetViews><sheetView workbookViewId="0"${indice === 0 ? ' tabSelected="1"' : ""}><pane ySplit="${cabecalho}" topLeftCell="A${cabecalho + 1}" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<cols>${cols}</cols>
<sheetData>${linhas.join("")}</sheetData>
<autoFilter ref="A${cabecalho}:${ultimaCol}${fimDados}"/>
${a.titulo && a.colunas.length > 1 ? `<mergeCells count="1"><mergeCell ref="A1:${ultimaCol}1"/></mergeCells>` : ""}
</worksheet>`;
    return { xml, filtro: `'${a.nome.replace(/'/g, "''")}'!$A$${cabecalho}:$${ultimaCol}$${fimDados}` };
  }

  async function gerar(abas) {
    const feitas = abas.map(aba);
    const nomes = abas.map((a) => esc(a.nome.slice(0, 31)));
    const arquivos = [
      { nome: "[Content_Types].xml", conteudo: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${abas.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("")}</Types>` },
      { nome: "_rels/.rels", conteudo: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>` },
      { nome: "xl/workbook.xml", conteudo: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${nomes.map((n, i) => `<sheet name="${n}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("")}</sheets><definedNames>${feitas.map((f, i) => `<definedName name="_xlnm._FilterDatabase" localSheetId="${i}" hidden="1">${esc(f.filtro)}</definedName>`).join("")}</definedNames></workbook>` },
      { nome: "xl/_rels/workbook.xml.rels", conteudo: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${abas.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("")}<Relationship Id="rId${abas.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>` },
      { nome: "xl/styles.xml", conteudo: ESTILOS },
      ...feitas.map((f, i) => ({ nome: `xl/worksheets/sheet${i + 1}.xml`, conteudo: f.xml })),
    ];
    return zip(arquivos);
  }

  return { gerar };
})();

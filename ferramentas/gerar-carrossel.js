#!/usr/bin/env node
// Gera as imagens de um carrossel do Instagram (1080x1350) a partir de um arquivo JSON.
// Uso: node ferramentas/gerar-carrossel.js posts/2026-11-24-carrossel-tema.json
//
// Formato do JSON:
// {
//   "assinatura": "@suabarbearia",
//   "slides": [
//     { "tipo": "capa", "titulo": "...", "subtitulo": "..." },
//     { "tipo": "conteudo", "numero": "1", "titulo": "...", "texto": "..." },
//     { "tipo": "final", "titulo": "...", "texto": "..." }
//   ]
// }
// As cores são lidas de marca/perfil.md (seção "Identidade visual"), se existirem.

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RAIZ = path.resolve(__dirname, '..');

function lerCores() {
  const padrao = { fundo: '#111111', destaque: '#C9A227', texto: '#F5F5F5' };
  const arquivo = path.join(RAIZ, 'marca', 'perfil.md');
  if (!fs.existsSync(arquivo)) return padrao;
  const md = fs.readFileSync(arquivo, 'utf8');
  const pegar = (rotulo) => {
    const m = md.match(new RegExp(rotulo + '[^#\\n]*?(#[0-9a-fA-F]{6})'));
    return m ? m[1] : null;
  };
  return {
    fundo: pegar('Cor principal') || padrao.fundo,
    destaque: pegar('Cor de destaque') || padrao.destaque,
    texto: pegar('Cor do texto') || padrao.texto,
  };
}

const esc = (s = '') =>
  String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function html(slide, idx, total, assinatura, c) {
  const tipo = slide.tipo || (idx === 0 ? 'capa' : idx === total - 1 ? 'final' : 'conteudo');
  let corpo;
  if (tipo === 'capa') {
    corpo = `
      <div class="selo">💈</div>
      <h1 class="capa">${esc(slide.titulo)}</h1>
      ${slide.subtitulo ? `<p class="sub">${esc(slide.subtitulo)}</p>` : ''}
      <p class="arraste">arrasta pro lado →</p>`;
  } else if (tipo === 'final') {
    corpo = `
      <h1 class="final">${esc(slide.titulo)}</h1>
      ${slide.texto ? `<p class="texto">${esc(slide.texto)}</p>` : ''}
      <p class="arroba">${esc(assinatura)}</p>`;
  } else {
    corpo = `
      ${slide.numero ? `<div class="numero">${esc(slide.numero)}</div>` : ''}
      <h2>${esc(slide.titulo)}</h2>
      ${slide.texto ? `<p class="texto">${esc(slide.texto)}</p>` : ''}`;
  }
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { width:1080px; height:1350px; background:${c.fundo}; color:${c.texto};
      font-family: 'Helvetica Neue', Arial, sans-serif; position:relative; overflow:hidden; }
    .moldura { position:absolute; inset:48px; border:3px solid ${c.destaque}; border-radius:8px; }
    .conteudo { position:absolute; inset:120px 110px 170px; display:flex; flex-direction:column; justify-content:center; }
    .selo { font-size:90px; margin-bottom:40px; }
    h1 { font-size:104px; line-height:1.05; font-weight:900; text-transform:uppercase; letter-spacing:-1px; }
    h1.final { font-size:84px; }
    h1 .d, h2 .d { color:${c.destaque}; }
    h2 { font-size:76px; line-height:1.1; font-weight:800; margin-bottom:44px; }
    .sub { font-size:44px; margin-top:44px; color:${c.destaque}; font-weight:600; }
    .texto { font-size:46px; line-height:1.4; opacity:.92; }
    h1.final + .texto { margin-top:44px; }
    .numero { font-size:150px; font-weight:900; color:${c.destaque}; line-height:1; margin-bottom:24px; }
    .arraste { position:absolute; bottom:-40px; right:0; font-size:34px; opacity:.7; }
    .arroba { margin-top:70px; font-size:52px; font-weight:800; color:${c.destaque}; }
    .rodape { position:absolute; left:110px; right:110px; bottom:90px; display:flex; justify-content:space-between;
      font-size:30px; opacity:.6; }
    .barra { position:absolute; left:0; bottom:0; height:14px; background:${c.destaque};
      width:${Math.round(((idx + 1) / total) * 100)}%; }
  </style></head><body>
    <div class="moldura"></div>
    <div class="conteudo">${corpo}</div>
    <div class="rodape"><span>${esc(assinatura)}</span><span>${idx + 1}/${total}</span></div>
    <div class="barra"></div>
  </body></html>`;
}

// Permite destacar palavras com *asteriscos* nos títulos.
function destacar(htmlStr) {
  return htmlStr.replace(/\*([^*<]+)\*/g, '<span class="d">$1</span>');
}

async function main() {
  const entrada = process.argv[2];
  if (!entrada) {
    console.error('Uso: node ferramentas/gerar-carrossel.js caminho/do/carrossel.json');
    process.exit(1);
  }
  const dados = JSON.parse(fs.readFileSync(entrada, 'utf8'));
  const slides = dados.slides || [];
  if (!slides.length) throw new Error('O JSON não tem slides.');
  const assinatura = dados.assinatura || '@suabarbearia';
  const cores = { ...lerCores(), ...(dados.cores || {}) };

  const pasta = entrada.replace(/\.json$/i, '');
  fs.mkdirSync(pasta, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
  for (let i = 0; i < slides.length; i++) {
    await page.setContent(destacar(html(slides[i], i, slides.length, assinatura, cores)));
    const arq = path.join(pasta, `slide-${String(i + 1).padStart(2, '0')}.png`);
    await page.screenshot({ path: arq });
    console.log('✔', arq);
  }
  await browser.close();
}

main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});

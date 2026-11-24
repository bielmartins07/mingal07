# 💈 Agente de Instagram da Barbearia

Um agente do Claude Code que cria os posts do Instagram da barbearia: indicação, reflexão,
carrossel (com as imagens prontas), dica para barbeiro, dica para cliente, roteiro de reels,
stories e calendário da semana.

## Primeiro passo (só uma vez)

Abra `marca/perfil.md` e preencha: nome da barbearia, @, cidade, serviços, produtos que você vende,
cores e hashtags. Tudo o que o agente escrever vai sair com essas informações.

## Como pedir

No Claude Code, digite `/instagram-barbearia` seguido do que você quer, ou só peça em português:

- `/instagram-barbearia carrossel pra barbeiro sobre como fidelizar cliente`
- `/instagram-barbearia indicação do óleo de barba`
- `/instagram-barbearia reflexão sobre constância`
- `/instagram-barbearia carrossel pro cliente: como escolher corte pelo formato do rosto`
- `/instagram-barbearia monta os posts da semana`
- `/instagram-barbearia roteiro de reels de antes e depois`

Os posts ficam salvos em `posts/`. Carrosséis geram também as imagens (1080x1350, tamanho do feed)
numa pasta com o mesmo nome.

## Gerar as imagens de um carrossel na mão

```bash
node ferramentas/gerar-carrossel.js posts/exemplos/carrossel-cliente-barba.json
```

Precisa de Node.js e Playwright (`npm i playwright && npx playwright install chromium`).

## O que tem aqui

| Pasta | O que é |
|---|---|
| `.claude/skills/instagram-barbearia/` | O agente: regras, formatos de post e banco de temas |
| `marca/perfil.md` | Dados da sua barbearia (preencha!) |
| `ferramentas/gerar-carrossel.js` | Transforma o carrossel em imagens |
| `posts/exemplos/` | 4 posts de exemplo (2 carrosséis com imagens, 1 indicação, 1 reflexão) |

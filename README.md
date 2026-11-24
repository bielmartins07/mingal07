# 💈 Agente de Instagram da Barbearia

Um agente do Claude Code que transforma suas fotos (cortes, você na barbearia, momentos da vida)
em posts prontos para o Instagram, falando com **todo mundo**: clientes, amigos, família, gente do bairro.
Reflexão, história pessoal, dica pro cliente, indicação, carrossel com suas fotos, reels, stories
e calendário da semana.

## Primeiro passo (só uma vez)

Abra `marca/perfil.md` e preencha: nome da barbearia, @, cidade, a seção **Sobre mim**
(sua história), serviços, produtos que você vende, cores e hashtags. Tudo o que o agente escrever vai sair com essas informações.

## Como pedir

No Claude Code, digite `/instagram-barbearia` seguido do que você quer, ou só peça em português:

- Manda as fotos e escreve: `/instagram-barbearia faz os posts dessas fotos`
- `/instagram-barbearia reflexão com essa foto minha na cadeira`
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
| `fotos/` | Suas fotos, organizadas por data |
| `posts/exemplos/` | Posts de exemplo (carrossel com imagens, indicação, reflexão) |

# Layout mapping — HTR Genealogia

Documento de referência visual do aplicativo. Novos componentes devem reutilizar estes tokens antes de criar valores isolados.

## Princípios

- Interface clara, utilitária e orientada à revisão de documentos.
- Fundo neutro para não competir com a imagem histórica.
- Azul para navegação e ações principais; amarelo para seleção/atenção; verde para revisão concluída.
- O canvas usa cinza escuro para preservar contraste com páginas claras.

## Cores

| Token | Valor | Uso |
|---|---|---|
| `--color-page` | `#f5f5f5` | Fundo geral |
| `--color-surface` | `#ffffff` | Cards, painéis e controles |
| `--color-surface-muted` | `#eeeeee` | Menu lateral |
| `--color-header` | `#222222` | Barra superior |
| `--color-text` | `#333333` | Texto principal |
| `--color-text-muted` | `#666666` | Texto auxiliar |
| `--color-border` | `#cccccc` | Divisórias e bordas |
| `--color-primary` | `#245ea8` | Ações e links |
| `--color-primary-soft` | `#cfe3ff` | Estado ativo |
| `--color-warning` | `#d99000` | Palavra pendente |
| `--color-success` | `#2a7d32` | Palavra revisada |
| `--color-canvas` | `#444444` | Área da imagem |

## Tipografia

- Família principal: `system-ui, "Segoe UI", Roboto, sans-serif`.
- Família técnica: `ui-monospace, Consolas, monospace`.
- Corpo: `16px`.
- Texto auxiliar: `12px`.
- Título de página: `32px`.
- Line-height recomendado para texto: `1.5` a `1.6`.

## Espaçamento e dimensões

| Token | Valor |
|---|---:|
| `--space-1` | `4px` |
| `--space-2` | `8px` |
| `--space-3` | `12px` |
| `--space-4` | `16px` |
| `--space-5` | `24px` |
| `--radius-sm` | `4px` |
| `--radius-md` | `6px` |

- Barra superior: aproximadamente `48px`.
- Menu lateral: `230px` no desktop.
- Botões: padding vertical de `9px`.
- Cards: padding de `12px` a `24px`.

## Estados do editor

- Registro: contorno azul.
- Linha selecionada: contorno laranja e nós visíveis.
- Palavra pendente: amarelo/laranja.
- Palavra selecionada: amarelo claro.
- Palavra revisada: verde.

## Implementação

Os tokens vivem em [app/frontend/src/styles/tokens.css](../../app/frontend/src/styles/tokens.css). O front-end usa Vite, React e TypeScript; a interface Flask existente permanece ativa durante a migração incremental.

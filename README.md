# HTR Genealogia

Ferramenta para marcar palavras manuscritas numa imagem, reconhecê-las (HTR) e treinar o modelo com as suas confirmações.

## Estrutura

```
meu-htr/
├── dataset/
│   ├── originals/           ← coleções de imagens das páginas
│   ├── processed/           ← recortes confirmados (PNG)
│   ├── annotations/         ← labels, léxico, registros e layout
│   └── splits/              ← train.csv / val.csv
├── models/
│   ├── segmentation/
│   └── recognition/
│       ├── base/            download do modelo pré-treinado (cache)
│       ├── run-AAAAMMDD-HHMM/   histórico de cada treino
│       └── current/         modelo que o servidor usa
├── src/
│   ├── preprocessing/ · segmentation/ · recognition/
│   ├── alignment/ · geometry/ · database/
│       └── recognition/htr/ código Python e treinamento
├── app/
│   ├── backend/              API Node
│   └── frontend/             Vite, React e TypeScript
├── experiments/
├── tests/
├── requirements.txt
└── README.md
```

## Instalação (VS Code)

No Windows, o instalador abaixo prepara todos os componentes locais: ambiente
Python, dependências de IA/Kraken, dependências do Node, build do front-end,
pastas de dados e configuração local do eScriptorium. Ele é idempotente:
execuções seguintes preservam o ambiente virtual, o `variables.env` e os dados
já existentes.

Pré-requisitos: Python 3.10+, Node.js 20+ e Docker Desktop iniciado (o Docker
pode ser ignorado durante a instalação com `-SkipDocker`).

O instalador mantém o ambiente virtual, caches de pacotes e cache de modelos
em `F:\hcr_genealogy` (na pasta `.cache`), evitando consumir espaço no disco
do sistema.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
```

Para também construir e iniciar o eScriptorium:

```powershell
.\scripts\install.ps1 -StartEscriptorium
```

Se o Docker ainda não estiver instalado, prepare o restante primeiro:

```powershell
.\scripts\install.ps1 -SkipDocker
```

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  |  source .venv/bin/activate (Linux/Mac)
pip install -r requirements.txt # com GPU NVIDIA, instale o torch antes: https://pytorch.org
pip install -e .
pytest                          # valida o ambiente instalado
```

### Kraken e eScriptorium

O Kraken está instalado como motor de segmentação e reconhecimento histórico:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\kraken.exe --version
```

O módulo [src/segmentation/kraken.py](src/segmentation/kraken.py) executa o
pipeline com segmentação por baselines, reconhecimento e saída PageXML. Os
modelos devem ser fornecidos separadamente, pois a qualidade depende do
acervo e do idioma:

```powershell
& .\.venv\Scripts\kraken.exe list
& .\.venv\Scripts\kraken.exe get <DOI-DO-MODELO>
```

O eScriptorium será usado inicialmente para anotação e treinamento. Ele é uma
aplicação web separada, executada aqui pelo Docker Desktop. O código oficial foi
baixado em `app/escriptorium/` e, com o Docker Desktop iniciado, pode ser
subido assim:

```powershell
cd app/escriptorium
docker info
docker compose up -d --build
docker compose ps
```

Abra `http://localhost:8080`. O usuário inicial local é `admin` e a senha é
gerada pelo instalador em `app/escriptorium/variables.env`; altere-a antes de
expor o serviço fora da máquina. Para parar os serviços:

```powershell
docker compose down
```

O serviço `mail` fica desativado por padrão porque não é necessário para o
trabalho local e depende de `registry.gitlab.com/scripta/escriptorium/mail`.
Para ativá-lo explicitamente, depois que o restante estiver funcionando, use
`docker compose --profile optional-mail up -d mail`. Se `docker info` falhar,
abra o Docker Desktop, aguarde o engine Linux ficar pronto e execute os
comandos novamente.

Exporte as anotações do eScriptorium em PageXML e coloque-as em
`dataset/annotations/`. Converta-as para os registros editáveis do projeto:

```powershell
& ..\.venv\Scripts\python.exe -m database.pagexml `
  dataset\annotations\pagina.xml dataset\annotations\pagina.records.json `
  --image-name pagina.jpg
```

O conversor preserva regiões, linhas, baselines, palavras, polígonos e
transcrições humanas. Assim, o PageXML do eScriptorium vira entrada para a
interface própria e não fica preso ao fornecedor da anotação.

O fluxo planejado é: página original → pré-processamento → regiões/registros
→ linhas/baselines → HTR de linhas → alinhamento e palavras → revisão humana
→ PageXML/JSON com polígonos, transcrições e metadados. O reconhecimento de
linha não será tratado como prova de que cada polígono de palavra está correto:
essa etapa permanecerá editável e poderá ser corrigida manualmente.

### Front-end moderno

O novo front-end fica em `app/frontend/` e usa Node.js, Vite, React e TypeScript.
O front-end antigo em Flask continua disponível durante a migração incremental.
O Node agora é a API pública; o Flask/Python fica temporariamente interno para
OpenCV, reconhecimento TrOCR e treinamento.

Terminal 1 — serviço Python de IA:

```powershell
& ".\.venv\Scripts\python.exe" -m recognition.htr.server --no-model
```

Terminal 2 — API Node pública:

```powershell
cd app/frontend
npm install
npm run server
```

Terminal 3 — front-end Vite:

```powershell
cd app/frontend
npm run dev
```

Abra `http://127.0.0.1:5173`. O Vite encaminha `/api`, `/recognize` e
`/detect-layout` para o Node em `http://127.0.0.1:5100`.

#### Migração Flask → Node

O arquivo `app/frontend/server/index.ts` é o gateway público. Todas as rotas
existentes em `/api` continuam compatíveis e são encaminhadas ao serviço
Python durante a migração. Os serviços de IA possuem contratos explícitos:

- `POST /recognize` — candidatos de transcrição;
- `POST /detect-layout` — linhas e regiões detectadas;
- `GET /api/images` e `GET /api/image/...` — imagens;
- `/api/records/*` — registros, salvamento, layout e resegmentação.

Quando a persistência for migrada para Node, apenas o encaminhamento das rotas
de registros será substituído; o contrato usado pelo React permanecerá igual.

Para validar a compilação:

```powershell
npm run build
```

O proxy do Vite encaminha `/api`, `/recognize` e `/detect-layout` para a API
Node em `http://127.0.0.1:5100`; a API Node encaminha as operações ao serviço
Python em `http://127.0.0.1:5000`.
Os padrões visuais estão documentados em `docs/layout-mapping.md`.

### Reconhecimento em português

O modelo padrão agora é
`mazafard/trocr-finetuned_20250422_125947`, um checkpoint comunitário
fine-tuned para texto em português. O TrOCR não possui uma opção que troque o
idioma durante a execução. Esse checkpoint foi treinado principalmente para
texto impresso; para manuscritos históricos, o fine-tuning com seus próprios
recortes continua sendo necessário. Para usar outro checkpoint compatível,
defina-o antes de iniciar o servidor:

```powershell
$env:HTR_BASE_MODEL = "id-do-checkpoint-portugues"
python -m recognition.htr.server
```

Se `models/recognition/finetuned/current` foi criado anteriormente usando o modelo inglês,
ele continuará tendo precedência. Remova apenas essa pasta ou treine novamente
com `--from-base` para usar o novo checkpoint português:

```powershell
Remove-Item -Recurse -Force .\models\finetuned\current
python -m recognition.htr.training.prepare_dataset
python -m recognition.htr.training.train --from-base
```

Depois, reinicie o servidor. Se `models/recognition/finetuned/current` existir, ele terá
precedência sobre `HTR_BASE_MODEL`; use `--from-base` para treinar novamente a
partir do checkpoint configurado.

## Fluxo de trabalho

1. Crie uma subpasta para cada coleção dentro de `dataset/originals/`, por exemplo:
   `dataset/originals/colecao-01/`.
2. Copie as aproximadamente 15 páginas dessa coleção para essa subpasta.
   O menu **Coleções** exibirá a subpasta e suas imagens automaticamente.
3. Use **Novo registro** para marcar os registros; as correções das linhas e
   palavras serão usadas posteriormente na preparação do treinamento.
2. **Rotular**: execute *"1. Servidor"* (ou `python -m recognition.htr.server`) e abra http://127.0.0.1:5000.
   Arraste um retângulo aproximado sobre uma palavra → o sistema encosta o retângulo na tinta → mostra candidatos com %
   → corrija se preciso → **Enter** para confirmar.
   Sem modelo ainda (ou sem torch)? Use `--no-model` e digite as transcrições.
3. **Preparar**: `python -m recognition.htr.training.prepare_dataset`
4. **Treinar**: `python -m recognition.htr.training.train` (continua do `current`; use `--from-base` para recomeçar)
5. **Avaliar**: `python -m recognition.htr.training.evaluate` → CER e % de palavras exatas
6. Reinicie o servidor. Repita: cada ciclo rotula mais rápido, porque o modelo acerta mais.

## Revisão por registro

Use **Novo registro** para desenhar o retângulo de um registro de batismo.
O detector automático tenta encontrar linhas e palavras, executa o
reconhecimento palavra por palavra e mostra uma tabela com confiança e estado.
Em **Editar linhas e palavras**, arraste caixas existentes ou desenhe caixas
adicionais. As linhas detectadas aparecem como polígonos azuis com nós:
arraste os nós para acompanhar linhas inclinadas ou tortas e clique em
**Reidentificar palavras pelas linhas** para executar novamente a segmentação.
Depois, selecione cada palavra, corrija a transcrição e use **Salvar e próxima**.
As correções são guardadas em `dataset/annotations/records.json` e também alimentam
o dataset individual de palavras.

O registro analisado fica como rascunho no navegador até clicar em
**Salvar registro**. A edição e a exclusão de palavras não são persistidas
automaticamente; se o rascunho não for salvo, essas alterações são perdidas.
Registros de páginas diferentes podem ser ligados preenchendo o mesmo campo
**Grupo do registro** antes de salvar. Os registros salvos anteriormente não
são apagados ao clicar em **Novo registro**.

As linhas detectadas usam quatro nós e priorizam uma geometria horizontal
simples. O lápis ao lado da linha permite selecionar e mover seus nós. Ao
salvar, essas linhas corrigidas são registradas em
`dataset/annotations/layout_training.jsonl` para o futuro treinamento do detector
de layout. Use **Reidentificar palavras pelas linhas** depois de corrigir uma
linha.

O download do modelo pode funcionar sem autenticação, mas o Hugging Face exibe
um aviso e aplica limites menores. Para usar limites maiores, defina seu token
apenas no ambiente local antes de iniciar:

```powershell
$env:HF_TOKEN = "seu-token-do-hugging-face"
python -m recognition.htr.server
```

## Como funciona

- **Ajuste à tinta**: dentro do retângulo desenhado, binariza (Otsu), remove ruído de papel e usa o *bounding box* da tinta.
  Se o traço de outra linha entrar no retângulo, ele também será incluído: desenhe sem cortar nem invadir a palavra vizinha.
- **Confiança**: média geométrica da probabilidade dos tokens de cada hipótese (beam search, 5 candidatos).
  É uma estimativa, **não calibrada**: "96%" ainda não significa que acerta 96 de 100. Compare com `was_correct` em `labels.csv` para calibrar.
- **Aprendizado imediato**: palavras confirmadas vão para `lexicon.json` e sobem no ranking dos candidatos seguintes (marcadas com ✓).
  Isto ajusta o ranking, não os pesos do modelo; o aprendizado real acontece no passo 4.
- **Correções valem mais que acertos**: quando o modelo erra e você corrige, o par (imagem, texto certo) entra no treino.

## Pontos de atenção

- **Grafia antiga**: transcreva *como está escrito* ("Joze", "freguezia", "mez"), não modernize. Defina uma convenção para abreviaturas (ex.: `Fr.co`) e mantenha-a.
- **Quantidade**: com poucas centenas de palavras o ganho é pequeno; espere resultados úteis a partir de alguns milhares, de várias páginas e mãos diferentes.
- **Formato do TrOCR**: redimensiona cada recorte para 384×384, o que achata palavras muito longas. Se o CER estagnar nelas, é o primeiro suspeito.
- **Trocar de motor** (Kraken, CRNN+CTC próprio): só `recognizer.py` e `training/` mudam; interface e armazenamento continuam iguais.
- `dataset/` e `models/` estão no `.gitignore` (dados pessoais, arquivos pesados).

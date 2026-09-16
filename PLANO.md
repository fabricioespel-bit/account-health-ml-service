# Plano de Arquitetura — ML Clássico + Kubernetes (Azure/AKS)

`account-health-ml-service` — projeto de portfólio para fechar os gaps técnicos de ML
clássico/Deep Learning, Kubernetes e Azure/Microsoft.

Fabricio Espel · v4, 08/set/2026 — revisão de `Plano_ML_Classico_Kubernetes_Fabricio.pdf` (v2)
após discussão de riscos, ajustes de escopo e troca de fonte de dados (dataset público real + data lake
simplificado, em vez de dataset 100% sintético).

## 0. Modo de trabalho (requisito do projeto)

Registrado em 08/set/2026, a pedido explícito do Fabricio: neste projeto, o Claude **não deve executar
comandos nem desenvolver scripts por conta própria**. O papel do Claude é orientar — explicar o quê e o
porquê, sugerir o comando ou o código — e o Fabricio é quem executa os comandos e escreve/roda os scripts,
com a orientação do Claude. Isso vale para todas as fases do plano (setup Azure, download do Kaggle,
scripts de ingestão, treino de modelo, manifests K8s, etc.), não só para operações destrutivas ou que
mexem em infra real.

Motivo: o objetivo do projeto é fechar gaps técnicos reais (ML clássico, Kubernetes, Azure) — a
aprendizagem exige que o Fabricio execute e desenvolva na prática, não que o Claude faça por ele.

## 1. Contexto e objetivo

Decisão de investir tomada em 01/set/2026, a partir do padrão de requisitos observado em mais de 35 vagas
analisadas até então: ML clássico (supervisionado/não supervisionado, fine-tuning/PEFT/LoRA) e
Kubernetes apareceram como bloqueio ou diferencial recorrente em vagas de bom fit técnico (Radix, Loft,
Quality Digital, Banco BV, FCamara, Motiva, Hospital Care, SAUTER) — frequência suficiente para justificar
investimento ativo.

Mudança de infraestrutura (08/set/2026): o plano original usava GKE Autopilot (GCP). A decisão agora é
construir em Azure/AKS em vez de GCP, por dois motivos que se reforçam: (1) a API do Kubernetes é
padrão entre provedores — construir em AKS ensina exatamente os mesmos primitivos (Deployment,
Service, HPA, probes) que uma vaga pedindo "Kubernetes" quer ver, sem perder nada do gap-closing
original; (2) soma experiência real e verificável em Azure, que apareceu como bloqueio ou diferencial
explícito em pelo menos 5 vagas já analisadas (WTW — Copilot Studio/Azure AI Foundry; Hospital Care —
Azure AI Foundry como plataforma central; L3 — Azure OpenAI/Azure AI Search/Microsoft Fabric; Grupo AG
Capital — Azure/OCI nomeados; Keyrus — multi-cloud/híbrido como diferencial). GCP já está coberto por
experiência real de produção (Hagens, data-lake-engineering-decisions, RAG) — este projeto é a
oportunidade natural de diversificar sem abrir mão de nenhum gap técnico já planejado.

Objetivo triplo, então: (1) prova de trabalho real em ML clássico — modelo treinado, avaliado com rigor e
servido em produção; (2) experiência hands-on real com Kubernetes; (3) experiência hands-on real em Azure
— três gaps fechados por um projeto só.

**Correção de referência (08/set/2026):** o repositório `data-lake-engineering-decisions` (localmente
`marketing-data-lake`) citado no plano original **é um projeto fictício/ilustrativo** — documenta metodologia
e decisões de um projeto real do autor sem expor dados reais, não é uma fonte de dados nem um pipeline
a replicar. O desenho de `gld_account_activity_daily` (colunas: date, account_id, plan_tier, mrr_brl,
active_users, product_events, support_tickets_opened, support_tickets_resolved) segue como referência de
formato de feature, mas deixa de ser o gerador do dataset — ver decisão de fonte de dados abaixo.

**Mudança de fonte de dados (08/set/2026):** em vez de gerar um dataset 100% sintético, este projeto passa
a consumir um **dataset público real** (uso + billing/transações) combinado com uma camada sintética de
suporte, ingeridos por um **data lake simplificado dentro da Azure** — fecha um quarto gap técnico (ADLS
Gen2 + Synapse Serverless SQL) além dos três já planejados, sem inflar demais o escopo (ver seção 2 e 3).

**Prazo (revisado, 08/set/2026):** o critério até 15/09/2026 (saída da Hagens) não é mais um limitador rígido.
Prioridade é fazer as etapas com rigor e extrair o aprendizado real, não fechar dentro do prazo original a
qualquer custo. Estimativas da seção 6 seguem como referência, não como deadline.

## 2. Escopo e domínio

- **Problema de negócio:** prever churn (cancelamento) de conta a partir de sinais de uso de produto,
billing/transações e suporte — o domínio deixa de ser estritamente "B2B SaaS" e passa a espelhar o do
dataset público escolhido (assinatura de streaming/consumo digital), reaproveitando a mesma lógica de
negócio (uso cai + suporte sobe → risco de churn sobe) **como hipótese de trabalho a validar, não como
premissa garantida** — ver achado da EDA na "Status da Fase 0" abaixo: o rótulo de churn do KKBox é
puramente de billing/renovação (confirmado no script oficial `WSDMChurnLabeller.scala`), e a EDA na
amostra não mostrou uma tendência de queda de uso claramente mais forte em churners do que em
não-churners no curto prazo — a relação uso↓→churn↑ pode ser mais fraca ou mais indireta (via billing) do
que o desenho original assumia. Sinais de billing (auto-renovação, sensibilidade a preço) entram como
hipótese concorrente a testar na Fase 1.
- **Dataset (revisado, 08/set/2026):**
  - **Fonte real — uso e billing:** [KKBox's Churn Prediction Challenge](https://www.kaggle.com/c/kkbox-churn-prediction-challenge/data)
    (WSDM Cup 2018, Kaggle) — dados reais de uma assinatura de streaming: `transactions` (billing/renovação,
    ~21,5M linhas), `user_logs` (uso diário, ~30M linhas), `members` (cadastro, ~6,7M linhas) e rótulo de
    churn já validado pela competição (~1M contas rotuladas).
  - **Amostragem obrigatória (decidido, 10/set/2026):** o dataset completo é grande demais pro orçamento
    deste projeto — usar um subconjunto de **25.000 contas (`msno`)**, sorteadas aleatoriamente e
    estratificadas por status de churn, preservando a taxa real observada em `train_v2.csv`
    (970.960 contas rotuladas, **9,0% de churn** — 87.330 churners). A amostra estratificada resulta em
    ~2.250 churners e ~22.750 não-churners, com seed fixa (42) para reprodutibilidade.
    - **Justificativa do tamanho (regra EPV — events per variable):** para modelos como regressão
      logística, a prática recomendada ("one in ten rule") é ter pelo menos ~10 eventos da classe
      minoritária (aqui, churners) por variável preditora (feature) no modelo, evitando overfitting e
      coeficientes instáveis. Com ~2.250 churners na amostra, a regra suporta até ~225 features
      (`2.250 / 10`) — bem acima do conjunto de features previsto para este projeto (uso, billing,
      cadastro e suporte agregados por conta, provavelmente 10-25 no total), deixando folga confortável
      sem exigir uma amostra maior.
    - Tamanhos menores (5.000 e 10.000 contas) foram considerados e descartados: 5.000 geraria só ~450
      churners, arriscado para um split robusto em treino/validação/teste; 10.000 (~900 churners) já
      atenderia a regra EPV, mas 25.000 foi escolhido para ficar mais próximo de um volume realista de
      produção, ainda representando só ~2,6% da população total (baixo custo de armazenamento/consulta
      no Synapse Serverless).
  - **Camada sintética — suporte:** datasets públicos reais de uso/billing e de tickets de suporte não
    compartilham `account_id` entre si (são de empresas diferentes) — decisão tomada: gerar uma camada
    sintética de tickets de suporte, correlacionada de propósito com queda de uso das mesmas contas reais
    amostradas (mesma causalidade do plano original: uso↓ → tickets↑ → churn↑), documentada
    explicitamente no README como lacuna de dado público real disponível, não como dado real disfarçado.
  - **Ingestão via data lake simplificado na Azure** (ADLS Gen2 bronze/silver/gold) em vez de carregar
    direto em Azure SQL Database — decisão revisada: o objetivo inclui aprender ingestão multi-fonte de
    verdade, então a simplificação deixada de lado no plano v2/v3 (ADLS Gen2) volta ao escopo.
    **Revisão (11/set/2026):** a transformação bronze→silver→gold, originalmente planejada via **Azure
    Synapse Serverless SQL**, foi **abandonada** — a assinatura ficou bloqueada por uma restrição real de
    capacidade regional da Microsoft para novos SQL Servers em East US (não é temporária: pedido formal de
    "Region access" foi **negado** por alta demanda, sem prazo — ver detalhe na "Status da Fase 0").
    Transformação segue **local, em Python/Polars**, escrevendo Parquet direto nos containers `silver`/
    `gold` do ADLS Gen2; a camada `gold` final é lida pelo serviço FastAPI (Fase 2) via SDK
    `azure-storage-file-datalake`, sem depender de nenhum banco relacional — evita reintroduzir a mesma
    dependência de `Microsoft.Sql`/SQL Server que causou o bloqueio. Mantém o gap de "data lake real na
    Azure" (ADLS Gen2 + AKS), sacrificando especificamente a experiência de SQL serverless sobre o lake
    (ver seção 4 para a decisão completa).
- **Variável-alvo:** usar a **definição nativa de churn do KKBox** (não-renovação em até 30 dias após o fim
  do período pago), documentada e comparada explicitamente com a janela de 60 dias do plano original —
  decisão registrada: manter a definição validada pela competição em vez de forçar uma redefinição
  artificial de 60 dias sobre um dado real que já tem um rótulo estabelecido (mais simples e mais honesto
  ao dado do que reinterpretar a fonte).
- **Split treino/validação/teste — revisado 14/set/2026:** o plano original pedia split temporal (não
  aleatório) para evitar vazamento de informação futura — premissa válida para um dataset sintético com
  histórico contínuo por conta, mas **não se aplica ao KKBox**: o rótulo de churn é avaliado numa única
  janela fixa (expiração em fev/2017, checada via transações fev-mar/2017) igual para as 25.000 contas —
  não existe "passado" e "futuro" natural entre contas para particionar temporalmente. **Decisão: split
  aleatório estratificado por `is_churn`, 70/15/15** (treino/validação/teste), mantendo a proporção de 9%
  de churn em cada parte. Documentar essa mudança de premissa explicitamente no README (é uma correção
  honesta sobre a fonte de dado real, não um descuido).

## 3. Fases do projeto

### Fase -1 — Validações e dependências pré-projeto (NOVA, 08/set/2026)

Adicionada após revisão: antes de comprometer a estimativa de esforço da Fase 3 com uma premissa não
verificada, validar as dependências externas que podem mudar o caminho do projeto.

- Confirmar assinatura Azure ativa e créditos/free tier disponíveis.
- Instalar/atualizar Azure CLI (`az`).
- **Verificar disponibilidade de AKS Automatic** na região/subscription pretendida — feature relativamente
  nova, não necessariamente GA em toda região. Se disponível, seguir com AKS Automatic. Se não, decidir
  conscientemente pelo fallback (AKS padrão + cluster autoscaler) *antes* de estimar a Fase 3, não durante.
- Levantar custo real esperado do node pool do AKS (não escala a zero como Cloud Run/GKE Autopilot —
  os nodes cobram desde o minuto 1, diferente do control plane que é gratuito). Definir mecanismo de
  desligamento automatizado do cluster entre sessões (ver nota de custo abaixo), não depender de lembrar
  manualmente.
- Criar Resource Group dedicado (ex.: `rg-account-health-ml`).
- Criar o repositório `account-health-ml-service` (público, github.com/fabricioespel-bit).
- **(Novo, 08/set/2026)** Confirmar conta Kaggle ativa + token de API (`kaggle.json`), necessário para baixar
  o dataset KKBox — aceitar as regras da competição no site é pré-requisito para o download funcionar.
- **(Novo, 08/set/2026)** Provisionar a conta de armazenamento ADLS Gen2 (containers `bronze`, `silver`,
  `gold`) dentro do Resource Group do projeto. ~~e o workspace do Azure Synapse (modo Serverless)~~ —
  **abandonado em 11/set/2026**, ver "Status da Fase 0" e seção 4 (decisão de arquitetura).
- Critério de saída da Fase -1: por escrito, (a) confirmação AKS Automatic disponível ou fallback assumido,
  (b) estimativa de custo/hora do node pool e mecanismo de desligamento definido, (c) ambiente Azure
  pronto (assinatura, CLI, resource group, ADLS Gen2), (d) acesso ao Kaggle confirmado.

**Status da Fase -1 (atualizado em 09/set/2026):**

- ✅ Assinatura Azure ativa — **Pay-As-You-Go** (não foi possível ativar a avaliação gratuita de US$ 200;
  a conta exigiu assinatura paga diretamente), conta pessoal limpa (`fabricioespel80@outlook.com`, tenant
  "Default Directory", sem nenhum vínculo com a Hagens — ver nota abaixo sobre o problema de tenant
  encontrado durante o setup). **Sem crédito gratuito de margem — todo gasto é cobrança real no cartão.**
- ✅ Budget configurado no Azure Cost Management: **US$ 10**, com alertas em 50%, 80% e 100%
  (US$ 5 / US$ 8 / US$ 10) — rede de segurança contra gasto inesperado, complementar ao `az aks stop`/
  `az aks start` que será adotado como rotina de desligamento entre sessões na Fase 3. Valor baixo de
  propósito (ainda sem dado real de custo/hora do node pool); ajustar depois de observar o gasto real.
- ✅ Repositório `account-health-ml-service` criado e publicado em
  `github.com/fabricioespel-bit/account-health-ml-service`.
- ✅ Acesso ao Kaggle confirmado — API Token (formato novo, não legacy) gerado e validado via
  `uv run kaggle competitions list`; regras da competição KKBox Churn Prediction aceitas no site.
- ✅ **AKS Automatic confirmado disponível** para a assinatura ("Azure subscription 1") na região **East US** —
  validado pelo Portal (Centro do Kubernetes → Criar → "Cluster automático do Kubernetes"), formulário abriu
  sem nenhum aviso de indisponibilidade com a assinatura e a região pré-selecionadas. **Decisão: seguir com
  AKS Automatic em East US na Fase 3**, sem necessidade do fallback (AKS padrão + cluster autoscaler).
- ✅ Azure CLI (`az` 2.90.0) instalado via `uv tool install azure-cli` — login confirmado
  (`fabricioespel80@outlook.com`, assinatura "Azure subscription 1", subscription id
  `91d5b811-3464-4f6a-91d9-2846c8488a84`, tenant "Default Directory"). **Nota:** a tentativa inicial via
  `brew install azure-cli` ficou presa compilando dependências (`llvm@22` levou 6h26min do código-fonte,
  `rust` em seguida) — o macOS 12 desta máquina é velho o suficiente para não ter os binários pré-compilados
  ("bottles") do Homebrew para essas formulas, forçando build local gigante. `uv tool install` resolveu em
  minutos, baixando wheels pré-compiladas. Lição: nesta máquina, preferir `uv tool install`/`pip install`
  a `brew install` para ferramentas Python com dependências nativas pesadas.
- ✅ Custo do node pool do AKS — sem estimativa prévia exata (Portal não mostra custo inline pro AKS
  Automatic), mitigado com Budget + alertas (ver acima) em vez de número fixo antecipado; mecanismo de
  desligamento definido (`az aks stop`/`start` manual entre sessões, a implementar na Fase 3).
- ✅ Resource Group `rg-account-health-ml` criado em `eastus` (via `az group create`).
- ✅ ADLS Gen2 (`sahealthml2026fe`, containers `bronze`/`silver`/`gold`) provisionado em 10/set — detalhe
  completo na "Status da Fase 0". Workspace Synapse Serverless **abandonado** em 11/set (ver Fase 0 e
  seção 4) — não faz mais parte do critério de saída desta fase.
- ✅ **Fase -1 encerrada** (11/set/2026): todos os itens do critério de saída atendidos, com o Synapse
  removido do escopo.

**Nota sobre o setup da conta Azure (09/set/2026):** a primeira tentativa de criar a conta Azure com o
e-mail pessoal (`fabricioespel@gmail.com`) resultou no tenant caindo dentro do Microsoft Entra ID da
Hagens ("HAGENS MARKETING LTDA"), porque esse e-mail já era convidado (guest) nesse diretório — sem
nenhuma assinatura própria nele, e sem permissão de guest para criar um novo tenant a partir daquele
contexto (serviço de criação de locatário não aparecia disponível na busca do Portal). Resolvido criando
uma conta Microsoft nova (`fabricioespel80@outlook.com`, sem vínculo prévio com nenhum tenant
corporativo) e refazendo o cadastro da assinatura a partir dela — gerou um "Default Directory" pessoal
automaticamente, limpo. Lição registrada: ao usar um e-mail pessoal que já teve qualquer relação de
convidado com um tenant corporativo (Teams, SharePoint, M365 etc.), o cadastro do Azure pode herdar esse
contexto em vez de criar um diretório novo — vale verificar o diretório ativo (canto superior direito do
Portal) logo após criar a conta.

### Fase 0 — Data lake simplificado, dados e definição de sucesso (revisada, 08/set/2026)

- **Ingestão (bronze):** baixar a amostra de contas do KKBox (transactions, user_logs, members — ver seção
  2 para critério de amostragem) via API do Kaggle e subir para o container `bronze` do ADLS Gen2, um
  prefixo por fonte, sem transformação. Gerar a camada sintética de tickets de suporte (correlacionada com
  queda de uso das mesmas contas amostradas) e subir também como fonte própria em `bronze`, claramente
  identificada como sintética (ex. prefixo `bronze/support_tickets_synthetic/`).
- **Transformação (silver) — revisado 11/set/2026:** scripts Python/Polars locais lendo os arquivos do
  `bronze` — tipagem, deduplicação, padronização de datas — escrevendo Parquet no container `silver` via
  upload (`azure-storage-file-datalake`). Um modelo por fonte, mesma disciplina do padrão bronze/silver/
  gold já usado no projeto de referência (fictício) citado na seção 1. (Originalmente planejado via views/
  CTAS no Synapse Serverless SQL — abandonado por bloqueio de capacidade regional, ver seção 4.)
- **Consolidação (gold) — revisado 11/set/2026:** tabela única `gold_account_activity` juntando uso +
  billing reais (por `msno`) com a camada sintética de suporte, no formato inspirado em
  `gld_account_activity_daily` (ver seção 1), escrita como Parquet em `gold` no ADLS Gen2. O serviço
  FastAPI (Fase 2) lê essa tabela direto do ADLS Gen2 (pequena, cabe em memória) no startup, sem depender
  de um banco relacional — evita reintroduzir a dependência de `Microsoft.Sql` que causou o bloqueio do
  Synapse. (Originalmente planejado como carga em Azure SQL Database.)

  **Schema silver/gold (desenhado 14/set/2026):**

  *Silver — um modelo por fonte, tipado/deduplicado, sem agregação:*
  - `silver/churn_labels`: `msno` (str), `is_churn` (bool) — passthrough tipado.
  - `silver/members`: `registration_init_time` (Date); `bd` limpo — valores ≤0 ou >100 viram `null` +
    flag `bd_invalido` (bool), preservando o dado bruto de forma auditável; `gender`/`registered_via`
    mantidos com nulls (tratamento fica pro gold).
  - `silver/transactions`: `transaction_date`/`membership_expire_date` (Date); `is_auto_renew`/`is_cancel`
    → bool; dedup de linhas exatamente duplicadas; ordenado por `msno`, `transaction_date`.
  - `silver/user_logs`: `date` (Date); sanity check em `total_secs` — fora de `[0, 86400]` (mais que um
    dia inteiro é fisicamente impossível) vira `null` + flag `total_secs_invalido`; dedup de `(msno, date)`.
  - `silver/support_tickets`: `opened_at`/`resolved_at` (Date); passthrough do resto.

  *Gold — `gold_account_activity`, 1 linha por conta:*
  - **Cadastro:** `tem_cadastro` (bool), `faixa_etaria` (categoria, `bd_invalido`/null → "desconhecido"),
    `gender` (categoria, null → "desconhecido"), `registered_via` (categoria, null → "desconhecido"),
    `tenure_cadastro_dias` (até 28/fev/2017, mesma janela do rótulo de churn).
  - **Billing:** `n_transacoes`, `auto_renew_ultima` (bool — sinal mais forte da EDA: 92,6% vs. 47,8%),
    `desligou_auto_renovacao` (bool — transição 1→0, 8,6x mais comum em churn), `ja_cancelou` (bool),
    `desconto_medio`, `plano_dias_ultimo`, `dias_desde_ultima_transacao`.
  - **Uso:** `tem_uso_registrado` (bool), `total_secs_ultimo_mes`, `variacao_uso_mes` (log-ratio, sinal
    fraco mas mantido), `tendencia_uso_3m` (log-ratio, últimos 3 meses), `meses_ativos`.
  - **Suporte:** `n_tickets_total`, `n_tickets_ultimos_30d`.
  - **Alvo:** `is_churn`.

- Definir por escrito, antes de treinar qualquer modelo: métrica principal (recall a uma precisão mínima
  aceitável, calibrada depois de ver a distribuição real de churn da amostra), baseline mínimo, critério
  objetivo de "modelo pronto para produção", e o critério de amostragem (tamanho da amostra, estratégia de
  estratificação por churn).

**Status da Fase 0 (atualizado em 10/set/2026):**

- ✅ **Ingestão (bronze) concluída.** Amostra de 25.000 contas (ver critério EPV na seção 2) baixada via
  Kaggle API, filtrada localmente com Polars (lazy/streaming para os arquivos grandes) e subida para o
  container `bronze` do ADLS Gen2, um prefixo por fonte:
  - `bronze/churn_labels/sample_accounts.csv` — 25.000 contas rotuladas (1,2MB).
  - `bronze/members/members_sampled.csv` — 22.196 contas com cadastro completo (88,8% de match; 92,6%
    entre churners vs. 88,4% entre não-churners — diferença pequena, não indica viés relevante) (1,6MB).
  - `bronze/transactions/transactions_sampled.csv` — 390.735 transações, 24.949 contas únicas (99,8% de
    match) (31,4MB).
  - `bronze/user_logs/user_logs_sampled.csv` — 6.154.364 linhas de uso diário, 21.949 contas únicas
    (87,8% de match) (471,8MB).
  - `bronze/support_tickets_synthetic/support_tickets_synthetic.csv` — 128.800 tickets sintéticos gerados
    com taxa de Poisson variável por conta-mês (base 0,05/mês, +1,2 em meses com queda de uso ≥30%),
    correlação auditável: 90% dos tickets caem em mês de queda de uso, 18.973 contas (76% da amostra) têm
    pelo menos 1 ticket. **Nota para a fase de EDA/feature engineering:** o limiar de -30% pode estar
    capturando volatilidade normal de uso mês a mês além do sinal de risco real — revisitar se as features
    derivadas parecerem ruidosas demais.
  - Nota de qualidade de dado: ~11-12% das contas amostradas não têm registro em `members` e/ou em
    `user_logs` — meio esperado para este dataset, mas precisa de tratamento explícito (feature de
    "sem cadastro"/"sem uso registrado" ou imputação) no desenho da camada `gold`.
- ❌ **Synapse Serverless — abandonado (11/set/2026).** Histórico completo do bloqueio:
  `SqlServerRegionDoesNotAllowProvisioning` ao tentar criar o workspace, testado em `eastus` e `eastus2`,
  via CLI e UI, identicamente. Pesquisa na documentação oficial da Microsoft
  ([capacity-errors-troubleshoot](https://learn.microsoft.com/en-us/azure/azure-sql/capacity-errors-troubleshoot?view=azuresql))
  revelou que essa mensagem exige um pedido explícito de **"Region access"** (cota de SQL Database), não
  espera passiva — chamado nº **2609110040003068** foi aberto gratuitamente (rota de cota é self-service,
  diferente do suporte técnico geral que pediu plano pago) pedindo acesso em East US. **Resposta da
  Microsoft (11/set/2026, via e-mail do suporte):** pedido **negado** — "due to high demand for Azure SQL
  DB in east US region", sem prazo de resolução (oferecia só: atualizações bimensais, aviso quando
  liberar, ou arquivar o pedido). **Decisão: abandonar o Synapse Serverless SQL** em vez de pedir acesso a
  outra região — ver racional completo na seção 4 ("Decisões de arquitetura"). Os dados brutos já prontos
  em `bronze` não são afetados; a transformação segue local (Python/Polars), sem depender de nenhum
  recurso `Microsoft.Sql`. Chamado de suporte deixado para arquivamento (não é mais necessário).
- ✅ **EDA inicial feito** (`scripts/06_eda.py`), rodado sobre os arquivos do bronze localmente (independe
  do Synapse). Achados principais:
  - **Qualidade de dado em `members`:** `bd` (idade) tem 48,7% de valores inválidos (≤0 ou >100, mediana
    real é 0, máximo absurdo de 1035) — campo não usável como numérico direto, exige categorização
    ("faixa etária" ou "não informado"). `gender` tem 59,7% de nulos — mesmo tratamento.
  - **Transações:** 92,2% de taxa de auto-renovação, só 1,7% de cancelamento explícito — consistente com
    a definição de churn do KKBox ser sobre não-renovação silenciosa, não cancelamento ativo.
  - **Hipótese uso↓→churn↑ testada e não confirmada no curto prazo:** variação de uso mês a mês (métrica
    robusta via log-ratio, mediana) ficou parecida entre churners e não-churners; comparação de recência/
    volume de meses ativos também não mostrou diferença (ambos os grupos com o mesmo teto de dado,
    fev/2017, e média de ~15-16 meses ativos). Investigado com o script oficial de rotulagem
    (`WSDMChurnLabeller.scala`, baixado e lido): confirma que o rótulo de churn do KKBox é 100%
    baseado em renovação de billing (expiração em fev/2017 + checagem de renovação em até 30 dias via
    transações fev-mar/2017), **não em uso** — o que explica por que a correlação simples com uso não
    apareceu forte. Ver ajuste da hipótese na seção 2. Ação: testar features de billing (mudança em
    auto-renovação, sensibilidade a preço) como preditores concorrentes/complementares na Fase 1, em vez
    de assumir uso como sinal dominante.
  - **Features de billing testadas (`scripts/07_eda_billing.py`) — sinais fortes confirmados:**
    auto-renovação ativa na última transação (92,6% não-churn vs. 47,8% churn — diferença enorme);
    já desligou auto-renovação alguma vez no histórico (0,6% vs. 5,0% — raro, mas ~8,6x mais comum em
    churners); nº de transações históricas/tenure de billing (mediana 17 vs. 10 — churners com bem menos
    histórico). Sinais fracos/nulos: histórico de cancelamento explícito (21,1% vs. 25,8%, diferença
    pequena), desconto médio e duração do plano (sem diferença, mediana igual nos dois grupos).
    **Ressalva importante:** a feature de auto-renovação é forte a ponto de ser quase mecânica (não é
    vazamento de rótulo — o script de rotulagem não usa essa flag diretamente — mas é uma proxy quase
    direta de "vai gerar transação de renovação automaticamente"). Um modelo apoiado só nela vira trivial;
    o desafio de ML real está em combinar isso com tenure, uso e suporte para nuance, não em só achar essa
    variável. Reportar métricas do modelo final também sem essa feature, como comparação, na Fase 1.
- ✅ **Transformação (silver) e Consolidação (gold) concluídas (14/set/2026)**, localmente via Python/
  Polars (substituindo o Synapse abandonado — ver acima e seção 4), seguindo o schema desenhado nesta
  mesma data:
  - `scripts/09_transform_silver.py`: gerou as 5 tabelas silver (`churn_labels`, `members`, `transactions`
    — dedup removeu 69 linhas duplicadas exatas, `user_logs`, `support_tickets`), subidas em Parquet
    (`compression="zstd"`) pro container `silver` do ADLS Gen2.
  - `scripts/10_build_gold.py`: consolidou `gold_account_activity` (25.000 linhas, 21 colunas), subida
    pro container `gold`. Nulos por coluna bateram exatamente com as taxas de match já conhecidas da EDA
    (11,2% sem cadastro, 0,2% sem transação, 12,2% sem uso, 16,1% sem variação de uso mês-a-mês — esse
    último maior porque exige pelo menos 2 meses de histórico, não só 1) — confirma que o pipeline está
    correto, sem inconsistência nova introduzida na consolidação.
  - **Fase 0 está 100% completa.**
- ✅ **Definição de sucesso por escrito (decidido, 11/set/2026):**
  - **Métrica de comparação entre modelos:** PR-AUC (Average Precision) — mais robusta que ROC-AUC dado
    o desbalanceamento (9% de churn).
  - **Métrica de decisão ("modelo é melhor que o outro"):** F2-score (recall pesa 2x mais que precisão),
    justificado pela assimetria de custo do negócio: perder um churner (FN) custa receita recorrente
    perdida; alertar uma conta que não ia sair (FP) custa só um contato de retenção de baixo custo.
  - **Baseline mínimo (calculado, `scripts/08_baseline_billing.py`):** regra de uma linha "flagar como
    risco se auto-renovação estiver desligada na última transação" — **Precisão 40,7%, Recall 52,2%,
    F2 = 0,494** (TP=1160, FP=1691, FN=1061, TN=21037, sobre as 24.949 contas com transação). Esse é o
    número que qualquer modelo de ML precisa superar pra justificar a complexidade extra sobre uma regra
    simples.
  - **Critério de "modelo pronto para produção":** **F2 ≥ 0,65** no conjunto de teste (split temporal,
    não aleatório — ver seção 2), ~30% de melhoria relativa sobre o baseline. Escolhido como meta
    moderada: ambiciosa o suficiente pra justificar ML de verdade combinando billing + cadastro + suporte
    sintético, mas realista dado que a fonte de uso (`user_logs`) já mostrou sinal fraco na EDA e o sinal
    mais forte isolado (auto-renovação) já está "gasto" no próprio baseline.
  - **Ressalva de robustez (ligada ao achado da EDA de billing):** reportar F2 também **sem** a feature de
    auto-renovação, pra confirmar que o modelo não depende trivialmente dela — um modelo que só repete o
    baseline com outra roupagem não conta como sucesso real.

### Fase 1 — Baseline e modelagem clássica

- Baseline heurístico simples (ex.: "sinalizar conta se uso caiu mais de 30% nos últimos 14 dias") — ponto de
comparação real.
- Modelo 1: Logistic Regression — interpretável, base estatística de comparação.
- Modelo 2: Gradient Boosting (XGBoost ou LightGBM) — modelo de produção real para dados tabulares.
- Modelo 3 (stretch, só se sobrar tempo): rede neural simples em PyTorch, com justificativa explícita de quando
ela se justifica (ou não) para dados tabulares desse porte.
- Treino local ou em notebook simples — Azure Machine Learning workspace fica como stretch opcional
(equivalente ao Vertex AI do lado GCP), não obrigatório para o escopo v1, para não estourar o orçamento de
tempo.
- Avaliação: precision/recall/F1, ROC-AUC, curva de calibração, SHAP values para explicar decisões do modelo a
um público de negócio.
  - **Ressalva registrada (08/set/2026):** por ora, SHAP fica limitado a um plot estático no README — não
    virar notebook interativo ou dashboard de negócio nesta fase. Quando chegarmos neste ponto,
    **retomar essa decisão explicitamente** e avaliar se vale a pena evoluir para notebook dedicado ou
    dashboard, considerando o tempo disponível naquele momento.
  - **Revisado, 14/set/2026:** SHAP não pôde ser instalado — a versão resolvida (0.52.0) trava numa
    dependência exata de `llvmlite==0.36.0`, que só suporta Python até 3.9 (o projeto usa 3.12/3.13).
    Substituído por **importância de feature nativa do XGBoost** (`feature_importances_`) — cobre a mesma
    necessidade de explicabilidade básica do plano original sem a dependência quebrada.

**Status da Fase 1 (atualizado em 14/set/2026):**

- ✅ **Notebook estruturado** criado em `notebooks/01_fase1_modelagem.ipynb` (célula por célula, kernel do
  `.venv` do projeto). Novas dependências: `scikit-learn`, `xgboost`, `pandas`, `matplotlib`,
  `ipykernel`/`jupyter` (dev). `shap` descartado pelo motivo acima.
- ✅ **Split 70/15/15 estratificado** confirmado: 17.499/3.751/3.750 contas, 9,0% de churn mantido nos três
  conjuntos.
- ✅ **Bug real encontrado e corrigido na origem** (`scripts/10_build_gold.py`): `desconto_medio` virava
  `infinity` quando `plan_list_price = 0` (transações promocionais/trial) — afetava 29,6% das contas.
  Corrigido pra `null` quando não há preço de tabela pra calcular a razão; gold reprocessado e reenviado
  ao ADLS Gen2.
- ✅ **Modelos treinados e avaliados** (métricas: PR-AUC pra comparação, F2-score pra decisão — ver
  definição de sucesso na Fase 0):

  | Modelo | F2 (validação) | F2 (teste) |
  |---|---|---|
  | Baseline (regra de billing, Fase 0) | — | 0,494 |
  | Logistic Regression | 0,572 | — |
  | XGBoost (hiperparâmetro padrão) | 0,614 | — |
  | XGBoost (`RandomizedSearchCV`, 30 iter × 3 folds, `scoring=average_precision`) | 0,626 | — |
  | XGBoost (busca ampliada, 50 iter, +`scale_pos_weight`/regularização) | 0,629 | **0,601 (oficial)** |
  | XGBoost, sem `auto_renew_ultima` (checagem de robustez) | — | 0,568 |

  **Meta de produção (F2≥0,65) não foi atingida** — resultado final honesto: F2=0,601 no teste, ~22% de
  melhoria relativa sobre o baseline. A busca de hiperparâmetro **saturou** (duas rodadas de
  `RandomizedSearchCV` convergiram pro mesmo PR-AUC de validação cruzada, 0,605, inclusive escolhendo
  `scale_pos_weight=1` — ou seja, rebalancear não ajudou) — sinal de que o teto está no conjunto de
  features atual, não em ajuste fino. **Decisão: aceitar o resultado e documentar honestamente**, em vez
  de insistir em mais tuning com retorno decrescente comprovado (ver seção 4 para a decisão registrada).
- ✅ **Checagem de robustez confirmada:** removendo `auto_renew_ultima` (a feature "forte demais" que já
  havíamos sinalizado como quase mecânica), o F2 no teste cai só **5,4%** (0,601 → 0,568), continuando
  acima do baseline (+15%). Confirma que o modelo combina sinais de verdade (tenure, recência, uso,
  suporte), não depende trivialmente de uma única variável.
- ✅ **Importância de features (XGBoost nativo) — achado novo:** `auto_renew_ultima` (39,1%) e
  **`dias_desde_ultima_transacao`** (22,8%) somam **62% de toda a importância** — a recência da última
  transação é um sinal forte que a EDA de billing anterior não tinha testado explicitamente. Uso
  (`user_logs`) confirma sinal fraco (todas as features de uso abaixo de 2% cada, consistente com o achado
  da EDA). **Os tickets de suporte sintéticos também saem irrelevantes** (~1% cada) — cadeia de
  causalidade honesta: como o uso real é fraco, o sinal de suporte "montado propositalmente em cima da
  queda de uso" (Fase 0) também acaba fraco no modelo final, não é um problema de implementação.
- ⬜ Rede neural (Modelo 3, stretch) — não feita, dado que XGBoost já é o modelo mais forte e a diferença
  pro baseline já está clara; avaliar se vale a pena mais adiante.

### Fase 2 — Empacotamento do modelo como serviço

- FastAPI com endpoints `/predict` e `/health`.
- Modelo serializado (joblib ou ONNX) em Azure Blob Storage, carregado no startup do container — decisão
documentada: cold start vs. tamanho de imagem/reprodutibilidade.
- Testes automatizados do serviço de inferência: contrato de entrada/saída e casos de borda.

**Status da Fase 2 (atualizado em 14/set/2026):**

- ✅ **Modelo e metadados serializados** a partir do notebook (`joblib.dump` do XGBoost final +
  `metadata.json` com listas de features/threshold/métricas) e enviados a um container novo, **`models`**,
  no ADLS Gen2 — decisão de container dedicado em vez de misturar artefato de modelo com dado em `gold`.
- ✅ **Serviço FastAPI implementado** em `src/account_health/` — `data/loader.py` (baixa `gold_account_activity.parquet`
  via `azure-storage-file-datalake`), `models/loader.py` (baixa modelo + metadata do container `models`),
  `service/main.py` (app FastAPI). Endpoint final: **`GET /predict/{msno}`** (parâmetro de caminho, não
  query) — busca a conta na tabela `gold` carregada em memória no `lifespan` de startup, roda o modelo,
  retorna `{msno, churn_probability, is_at_risk, threshold}`; `404` se a conta não existir na tabela.
  `GET /health` simples pra liveness/readiness. Sem depender de banco relacional (consistente com o
  abandono do Azure SQL Database na Fase 0).
- ✅ **Testes automatizados** (`tests/test_service.py`, 3 casos: health, predict de conta existente,
  predict de conta inexistente) usando `TestClient` do FastAPI com **mock** dos dois loaders
  (`monkeypatch`) — testes não dependem de rede/credenciais Azure nem do modelo/dado reais, rodam
  determinísticos e rápidos (~4s). `uv run pytest tests/ -v` — 3 passed.
- **Bugs reais encontrados e corrigidos ao longo da implementação** (vale registrar, não é "código feio",
  é o tipo de fricção real de colocar um serviço no ar):
  - O pacote `account_health` foi instalado como editable **quando `src/account_health/` ainda estava
    vazio** — o `uv` cacheou uma build sem nenhum módulo dentro, e adicionar arquivos depois não invalidou
    esse cache sozinho (`uv sync` normal não percebeu). Fix: `uv sync --reinstall-package account-health-ml-service`.
  - Variáveis em `~/.config/account-health-ml/secrets.env` escritas sem `export` — funcionavam com `az`
    (que faz substituição de variável no próprio shell antes de rodar), mas não eram repassadas pro
    processo filho do `uv run uvicorn`. Fix: adicionar `export` nas linhas do secrets.env.
  - **Ordem de features trocada** entre o treino (`categóricas + booleanas + numéricas`, do notebook) e o
    serviço (`categóricas + numéricas + booleanas`, erro de digitação) — XGBoost é estrito quanto a isso e
    recusa rodar (`ValueError: feature_names mismatch`) em vez de silenciosamente dar resultado errado, o
    que é uma proteção boa de se conhecer.
  - Endpoint definido como `/predict/{msno}` (caminho) em vez do `/predict?msno=...` (query) inicialmente
    proposto — precisa de URL-encoding manual dos caracteres especiais do `msno` (`+`→`%2B`, `=`→`%3D`) ao
    testar via `curl`, já que `msno` são hashes base64.
- ⬜ Deploy real do container (Dockerfile, ACR) — fica pra Fase 3, junto do AKS.

### Validação pré-Fase 3 (NOVA, 08/set/2026)

Antes de prosseguir para o deploy em Kubernetes, aplicar um gate de qualidade equivalente ao da Fase 0 —
por escrito, checar:

- Serviço FastAPI responde `/health` e `/predict` localmente (ou em container local) sem erros, com os
  testes de contrato da Fase 2 passando.
- Critério de "modelo pronto para produção" definido na Fase 0 foi de fato atingido pelo modelo escolhido.
- Imagem de container builda localmente e roda sem depender de credenciais/paths que só existirão no
  cluster (nenhum caminho hardcoded incompatível com AKS).
- Decisões de secrets (o que vai para Key Vault) já mapeadas antes de escrever manifests do K8s.

Só avançar para a Fase 3 depois desse checklist fechado — mesma disciplina da Fase 0, para não empurrar
problema de empacotamento para dentro da complexidade adicional do Kubernetes.

**Status da validação pré-Fase 3 (atualizado em 15/set/2026):**

- ✅ `/health` e `/predict` respondendo — agora confirmado rodando de verdade num **container Linux no
  Azure** (não só local), com resultado idêntico ao teste local (`churn_probability: 0.043` pra mesma
  conta de teste).
- ⚠️ Critério de F2≥0,65 — **não atingido** (F2=0,601 no teste), aceito conscientemente na Fase 1. Não
  bloqueia a Fase 3 por decisão já registrada.
- ✅ Imagem builda e roda sem depender de credencial/path só-local — confirmado.
- ⬜ Secrets no Key Vault — ainda pendente (ver nota abaixo, ficou ainda mais claro que isso não é
  "nice to have").

**Saga real de colocar o serviço num container — vale documentar como aprendizado de portfólio:**

1. **Docker Desktop incompatível com o macOS 12** desta máquina (exige macOS 14+). Tentativa de
   alternativa via **Colima** (runtime leve baseado em Lima/QEMU) esbarrou num beco sem saída: o QEMU
   11.1.1 exige Clang v10+/Xcode 15+ pra compilar, indisponível nesse macOS. **Decisão: abandonar Docker
   local por completo** e buildar direto na nuvem via `az acr build` — mais realista (times de verdade
   buildam em CI/nuvem) e contorna o problema de vez.
2. **Bugs reais no Dockerfile, um de cada vez:**
   - Faltava `README.md` no contexto de build — `hatchling` exige esse arquivo pra validar metadados do
     pacote, e ele não tinha sido copiado (só `pyproject.toml`/`uv.lock`/`src/`).
   - Faltava `libgomp1` (equivalente Linux do `libomp` que já tínhamos instalado via Homebrew no macOS pro
     XGBoost) — adicionado ao `apt-get install`.
   - Adicionado `ca-certificates` e `ENV PYTHONUNBUFFERED=1` como precaução/boa prática (não eram a causa
     raiz do problema seguinte, mas ficam corretos no Dockerfile de qualquer forma).
3. **Teste do container sem Docker local:** usado **Azure Container Instances (ACI)** como ambiente de
   smoke-test descartável (`az container create`/`delete`) — sobe, testa via `curl`, apaga. Custo
   irrisório por poucos minutos de uso.
4. **`CrashLoopBackOff` com `ExitCode 3` e logs sempre vazios** (`az container logs` retornando `None`)
   — o maior desafio de diagnóstico da sessão:
   - `az container exec` interativo (`/bin/bash`) bateu num **bug real do Azure CLI**
     (`RuntimeError: release unlocked lock`) quando rodado sem uma sessão de terminal totalmente
     interativa — não é bug nosso, é limitação do ambiente de execução usado.
   - Contornado com comandos de "tiro único" (`--exec-command "timeout 8 <comando>"`, sem pipes/redirects/
     aspas aninhadas, que quebravam o parser do `az container exec`) — finalmente revelou o traceback
     real: `azure.core.exceptions.ClientAuthenticationError` — assinatura MAC não bate ao baixar o
     `gold_account_activity.parquet`.
   - Descartadas por ordem: falta de memória (testado 1GB→2GB, mesmo erro), relógio do container
     dessincronizado (`date -u` confirmou hora certa), chave de storage errada/desatualizada (testado com
     chave nova recém-buscada, mesmo erro).
   - **Causa raiz real:** `$AZURE_STORAGE_KEY` **não persiste entre comandos separados** nesta sessão de
     terminal (mesmo padrão de "esqueceu de `source`" já visto várias vezes no projeto, mas dessa vez
     mascarado porque o comando de criação do container "parecia" certo — só falhava silenciosamente ao
     montar a variável). Confirmado definitivamente testando com `--environment-variables` não-secure
     (não-criptografada) e inspecionando o JSON de retorno: primeira tentativa mostrou o valor **vazio**;
     ao encadear busca da chave + delete + create **num único comando** (`VAR=$(...) && az container
     delete ... && az container create ...`), o valor apareceu correto e o serviço subiu.
   - **Lição pra qualquer sessão futura:** nunca depender de uma variável `export`ada num comando anterior
     sobreviver pro próximo — sempre buscar/exportar e usar no mesmo bloco de comando encadeado com `&&`.
5. **Limpeza de segurança:** como o diagnóstico final usou variável não-secure (expondo a chave em texto
   plano na configuração do recurso), a chave da storage account foi **rotacionada**
   (`az storage account keys renew`) logo depois, e o `secrets.env` local atualizado.
6. **Container de teste (ACI) deletado** ao final, seguindo o princípio de não deixar recurso pago
   rodando à toa entre sessões.
7. Imagem final publicada em `acrhealthml2026fe.azurecr.io/account-health-ml-service:v1`, validada e
   pronta pra ser referenciada nos manifests do AKS na Fase 3.

**Conclusão prática:** esse debug reforça — não é só "nice to have" — a necessidade real do Key Vault +
Workload Identity planejados pra Fase 3: variável de ambiente simples já se provou frágil mesmo num teste
manual isolado; num cluster de produção de verdade, essa fragilidade seria inaceitável.

### Fase 3 — Deploy em Kubernetes no Azure (o gap-closing real)

- Azure Kubernetes Service (AKS), preferencialmente em modo AKS Automatic (equivalente ao GKE
Autopilot: menos operação de cluster, ainda expõe primitivos reais de K8s) — decisão já validada na Fase -1;
se caiu no fallback (AKS padrão + cluster autoscaler), seguir com esse caminho documentado como decisão
consciente, não improviso de última hora.
- Primitivos reais de K8s de qualquer forma: Deployment, Service, HorizontalPodAutoscaler, resource
requests/limits, readiness/liveness probes — o que realmente importa pra uma vaga que pede "Kubernetes".
- Secrets via Azure Key Vault + Azure AD Workload Identity (federated identity para pods no AKS) —
equivalente direto ao par Secret Manager + Workload Identity do GCP, mesmo padrão de segurança já usado
no amigurumi-agent.
- Imagem de container publicada no Azure Container Registry (ACR).
- Documentar por que AKS em vez de Azure Container Apps (o análogo mais próximo do Cloud Run no Azure) —
decisão deliberada, porque o gap é Kubernetes de verdade, não só "rodar container gerenciado sem ver a API
do K8s".
- **Trade-off de custo (reforçado, 08/set/2026):** node pool do AKS não escala a zero como um serviço
  serverless — os nodes cobram desde o minuto 1, independente de o control plane do AKS ser gratuito.
  Automatizar o desligamento do cluster inteiro entre sessões de demonstração (ex.: `az aks stop` /
  `az aks start`, não só reduzir o node pool manualmente) — decisão definida já na Fase -1, aplicada aqui.

**Status da Fase 3 (atualizado em 15/set/2026):**

- ✅ **AKS Automatic não foi viável nessa assinatura** — decisão revisada em relação à Fase -1. Na época,
  só validamos que o formulário do Portal abria sem aviso de indisponibilidade; a criação de verdade
  esbarrou em duas camadas de restrição real: (1) quota de vCPU "Total Regional" limitada a 10 (padrão de
  assinatura nova) — resolvida via cota self-service (sem chamado, ao contrário do caso do SQL Server);
  (2) as famílias de VM com suporte a 3 zonas de disponibilidade que o AKS Automatic exige por design
  (Dv5, DDv5, etc.) estavam **indisponíveis nessa assinatura/região** (não só cota zero — "Unavailable in
  this region"), sem alternativa self-service. **Ativado o fallback já documentado desde a Fase -1: AKS
  padrão + cluster autoscaler**, usando `Standard_D4s_v7` (família com cota confirmada e presente na
  lista de VMs permitidas pelo AKS nessa assinatura — descoberta via o próprio erro do `az aks create`,
  que lista as VMs válidas). Cluster `aks-account-health`, `sku: Base, tier: Free`, autoscaler 1-2 nós.
- ✅ **Imagem publicada no ACR** (`acrhealthml2026fe.azurecr.io/account-health-ml-service:v1`, validada
  na Fase 2) — cluster já criado com `--attach-acr` pra permissão de pull automática, sem role assignment
  manual.
- ✅ **Key Vault + Azure AD Workload Identity implementado de ponta a ponta** (não ficou só documentado —
  funcionou de primeira na primeira tentativa real de deploy):
  - Key Vault `kv-healthml2026fe` (RBAC habilitado) guardando a chave da storage account como secret
    (`storage-account-key`).
  - OIDC Issuer + Workload Identity habilitados no cluster existente (`az aks update
    --enable-oidc-issuer --enable-workload-identity`) e o addon do driver CSI do Key Vault
    (`azure-keyvault-secrets-provider`).
  - Identidade gerenciada dedicada (`id-account-health`) com role `Key Vault Secrets User` sobre o vault,
    federada com um `ServiceAccount` do Kubernetes (`account-health-sa`) via credencial federada
    (`az identity federated-credential create`, ligando o OIDC Issuer do cluster ao subject
    `system:serviceaccount:default:account-health-sa`).
  - `SecretProviderClass` com `secretObjects` sincronizando o secret do Key Vault pra um Secret nativo do
    Kubernetes (`storage-key-secret`) — decisão de design: o app **não precisou de nenhuma mudança de
    código**, continua lendo `AZURE_STORAGE_KEY` via `os.environ` normalmente, só que agora a origem do
    valor é o Key Vault via `secretKeyRef`, não mais uma variável de ambiente solta.
- ✅ **Manifests do Kubernetes** em `infra/k8s/` (`deployment.yaml`, `service.yaml`, `hpa.yaml`):
  Deployment com `azure.workload.identity/use: "true"`, resource requests/limits (512Mi/250m request,
  1Gi/500m limit — calibrado pelo teste de memória do ACI na Fase 2), readiness/liveness probes em
  `/health`; Service tipo `LoadBalancer` (IP público via Azure Load Balancer); HPA 1-3 réplicas por CPU
  (70% de utilização).
- ✅ **Deploy validado end-to-end**: pod `Ready` na primeira tentativa, `/health` e `/predict` respondendo
  via o IP público do Service, com resultado **idêntico** ao teste local e ao teste no ACI da Fase 2
  (`churn_probability: 0,043` pra mesma conta de teste) — confirma que a cadeia completa (AKS → Workload
  Identity → Key Vault → ADLS Gen2) funciona de ponta a ponta sem nenhuma cópia de credencial em texto
  plano em lugar nenhum do cluster.
- ⬜ Ainda pendente: aplicar o mecanismo de desligamento de custo (`az aks stop` entre sessões), e
  documentar por que AKS em vez de Container Apps (item já no plano original, ainda não escrito no
  README).

### Fase 4 — Monitoramento e detecção de drift

- **Revisado 11/set/2026:** logging estruturado de predições em **Azure Table Storage** (mesma storage
  account do data lake, sem depender de `Microsoft.Sql`/SQL Server — ver decisão de abandonar Azure SQL
  Database na seção 4) em vez de Azure SQL Database, reaproveitando o padrão de "monitoramento contínuo"
  já estabelecido no nível 4 do rag-quality-assurance.
- Logs de aplicação/infraestrutura via Azure Monitor / Log Analytics — equivalente ao Cloud Logging do lado
GCP.
- Checagem simples de drift de dados (distribuição de features ao longo do tempo, lendo os Parquets do
  `gold` com Polars em vez de query SQL), com critério documentado de quando um alerta dispararia.
- **(Decidido, 16/set/2026) Escopo da checagem de drift — data drift via PSI, não concept drift:**
  existem três tipos de drift relevantes em produção — *data drift* (distribuição das features de entrada
  muda), *concept drift* (a relação entre feature e rótulo muda) e *prediction drift* (a distribuição das
  saídas do modelo muda). Concept drift é o sinal mais direto de degradação real, mas exige rótulo
  verdadeiro (aqui, saber se a conta de fato renovou ou não) — no KKBox isso equivaleria a esperar o
  fechamento de um novo ciclo de cobrança, o que não existe neste dataset histórico estático. Decisão:
  implementar apenas **data drift** nesta fase, via **PSI (Population Stability Index)** por feature,
  comparando duas cohortes reais de tempo dentro do próprio KKBox (não duas amostras idênticas nem dado
  sintético perturbado) — ver metodologia abaixo. Cortes de PSI usados (padrão de mercado, não arbitrário):
  <0,1 sem mudança significativa; 0,1–0,25 mudança moderada; >0,25 alerta.
  **Nota para produção real (não implementada aqui, só documentada por rigor):** o desenho maduro seria em
  camadas — prediction drift e data drift rodando com frequência alta como sinais antecipados (não exigem
  rótulo), e concept drift rodando sempre que o rótulo real ficasse disponível (aqui, mensalmente, no
  fechamento de cada ciclo de cobrança) como confirmação definitiva dos alertas antecipados. A escolha de
  quanto pesar cada camada depende da latência do rótulo e do custo do erro do negócio, não é uma regra fixa
  de ML — este projeto usa a camada mais simples (data drift) por ser a única viável sem simular rótulo
  futuro de forma artificial.
- **(Decidido, 16/set/2026) Metodologia da checagem — Opção A (cohortes reais), não simulação sintética:**
  em vez de perturbar artificialmente uma cópia da `gold` pra forçar um drift fake, a checagem compara duas
  cohortes reais de contas dentro do próprio KKBox (ex.: contas por período real de última transação/
  atividade) — o resultado, se houver drift, é um achado genuíno do dado, não um exercício vazio contra o
  próprio dado espelhado nem um drift fabricado. Mesmo princípio já aplicado no projeto (preferir dado real
  mesmo quando mais trabalhoso, reservar sintético só para lacunas sem alternativa — ver decisão dos tickets
  de suporte).
- **(Implementado, 16/set/2026) Método final e resultado da checagem de drift:** em vez de dividir uma
  única foto da `gold` por recência de conta (a ideia genérica do item anterior), o método escolhido foi
  **parametrizar o `REF_DATE`** de `scripts/10_build_gold.py` (antes fixo em código) e rodar o pipeline
  duas vezes — uma na data de produção (2017-02-28) e outra 3 meses antes (2016-11-30) — gerando duas fotos
  reais do mesmo pipeline em momentos diferentes. Isso reproduz de forma mais fiel o que aconteceria numa
  checagem de produção de verdade (mesmo código, dias diferentes) do que uma simples divisão de cohortes
  dentro de uma foto só.
  - **Bug real encontrado e corrigido durante a implementação:** a primeira versão do script parametrizado
    usava `REF_DATE` só para calcular diferenças de dias (`dias_desde_ultima_transacao`, janela de tickets),
    mas nunca filtrava as tabelas de origem (`transactions`, `user_logs`, `support_tickets`) para excluir
    registros posteriores ao `REF_DATE` — ou seja, a "foto" de nov/2016 enxergava transações e uso de
    dez/2016 a fev/2017, um vazamento real de dado do futuro. Sintoma que expôs o bug: as duas fotos geraram
    contagens de nulo **idênticas**, o que não deveria acontecer entre dois momentos diferentes. Corrigido
    filtrando cada tabela pelo seu campo de data (`<= REF_DATE`) antes de agregar.
  - **Resultado do PSI, após o fix:** das 11 features numéricas do modelo, 10 ficaram dentro do normal
    (PSI < 0,1). Uma, `meses_ativos`, deu PSI = 0,660 (zona de alerta) — mas investigação mostrou ser
    **falso positivo estrutural**, não drift de comportamento: `meses_ativos` é uma contagem cumulativa
    desde jan/2015, então seu teto cresce mecanicamente conforme o `REF_DATE` avança (máximo de 23 meses em
    nov/2016 vs. 26 em fev/2017) — qualquer comparação de PSI entre janelas de calendário de tamanhos
    diferentes vai acusar "drift" nessa feature mesmo sem nenhuma mudança real de comportamento. Lição
    documentada: features de contagem cumulativa/lifetime não são boas candidatas a checagem de PSI entre
    janelas de referência diferentes, a menos que normalizadas (ex.: meses ativos ÷ meses desde o cadastro).
- **(Implementado e validado, 16/set/2026) Azure Monitor / Log Analytics no AKS:** addon de monitoramento
  habilitado no cluster existente (`az aks enable-addons --addon monitoring`), criando/conectando um Log
  Analytics Workspace automaticamente. Validado com uma consulta KQL real via
  `az monitor log-analytics query`, retornando as linhas de log reais do `uvicorn` do pod (incluindo a
  chamada de `/predict` de teste e as chamadas periódicas de `/health` do `readinessProbe`).
  - **Obstáculo real encontrado durante a validação:** ao reativar o cluster (`az aks start`, parado desde
    o fim da Fase 3), o pod da aplicação estava em `ImagePullBackOff` — o ACR (`acrhealthml2026fe`) tinha
    sido **deletado** de propósito ao fim da sessão anterior (princípio de recurso efêmero), então a imagem
    referenciada pelo `deployment.yaml` não existia mais. Corrigido recriando o ACR do zero (mesmo nome,
    pra não editar manifest), rebuildando a imagem (`az acr build`) e reconectando a permissão de pull ao
    cluster já existente via `az aks update --attach-acr` (diferente do `--attach-acr` usado na criação
    original do cluster — aqui é o comando pra um cluster já existente). Depois de `kubectl delete pod`
    (pra forçar nova tentativa), o pod subiu normalmente. Lição prática: o ciclo de "recurso efêmero" da
    Fase 3 (aks stop + ACR deletado) precisa desse procedimento de reconstrução do ACR sempre que o
    cluster for reativado — não é só dar `aks start`.

### Fase 5 (stretch, só se sobrar tempo) — CI/CD

- GitHub Actions: build da imagem, push para o ACR, deploy no AKS.
- Reforça rigor de engenharia, mas não é bloqueante para considerar o projeto "pronto".
- **(Implementado e validado, 16/set/2026):** workflow em `.github/workflows/deploy.yml`, disparado em push
  na `main` (filtrado por `paths` que afetam a imagem, pra não disparar deploy em commits só de
  documentação). Autenticação via **federação OIDC** com uma **Managed Identity dedicada**
  (`id-github-actions-cicd`, separada da identidade de runtime do pod — princípio de menor privilégio).
  Cada build usa o **hash do commit** como tag da imagem (`${{ github.sha }}`), em vez de uma tag fixa —
  necessário pro Kubernetes de fato perceber que há imagem nova a cada deploy.
  - **Bug real #1 — formato do `subject` do OIDC:** a primeira tentativa falhou com
    `AADSTS700213: No matching federated identity record found`. O `subject` configurado na Azure seguia o
    formato "padrão" da documentação (`repo:usuario/repo:ref:refs/heads/main`), mas o token real emitido
    pelo GitHub usava `repo:usuario@<id-numerico>/repo@<id-numerico>:ref:refs/heads/main` — a conta tem
    habilitada a customização do GitHub que usa o **ID imutável** do usuário/repositório em vez do nome
    (proteção contra federação quebrar se a conta/repo for renomeado). Corrigido com
    `az identity federated-credential update`, usando o `subject` exato do erro retornado.
  - **Bug real #2 — `AcrPush` insuficiente pro `az acr build`:** com a federação já funcionando, o passo de
    build falhou com "recurso não encontrado" pro ACR — mensagem enganosa, já que o recurso existia. Causa
    real: `AcrPush` cobre só o plano de dados (pull/push de imagem), mas `az acr build` aciona uma **tarefa
    de build no ACR** (`scheduleRun`), uma operação de plano de controle que a role não cobre. Corrigido
    concedendo `Contributor` **escopado só a esse ACR específico** (não ao grupo de recursos inteiro).
  - **Resultado:** pipeline validado de ponta a ponta — push → build → publish no ACR → `kubectl set image`
    → rollout no AKS, confirmado com `kubectl get deployment` mostrando a tag = hash do commit exato que
    disparou o run, e o serviço respondendo normalmente depois do rollout.

## 4. Decisões de arquitetura a documentar

Mesmo padrão dos outros repositórios do portfólio: o README existe para registrar a decisão e o trade-off,
não só descrever a infraestrutura.

- Por que Azure em vez de GCP para este projeto especificamente — diversificação deliberada de portfólio
multi-cloud, não indecisão.
- Por que classificação binária de churn, e não regressão de health score.
- Por que XGBoost/LightGBM antes de rede neural, para dados tabulares desse tamanho.
- Por que AKS (Automatic, se disponível) em vez de Azure Container Apps — o gap intencional é Kubernetes
de verdade.
- Por que Key Vault + Workload Identity, não secrets estáticos.
- **(Revisado, 11/set/2026)** Por que abandonar Azure Synapse Serverless SQL e Azure SQL Database
  inteiramente, em favor de transformação local (Python/Polars) + Parquet no ADLS Gen2 servido direto pelo
  FastAPI + Azure Table Storage para logging de predições: a assinatura recebeu uma **negativa formal e
  sem prazo** da Microsoft ("high demand for Azure SQL DB in east US region") para um pedido de "Region
  access" — não era um bloqueio temporário de propagação (como os providers da Fase -1), era uma restrição
  real de capacidade. Continuar dependente de `Microsoft.Sql` (seja via Synapse, seja via uma Azure SQL
  Database separada para servir a camada `gold` ou logar predições na Fase 4) arriscava bater na mesma
  parede de novo mais adiante. Opções consideradas: (a) pedir "Region access" para outra região — mais
  simples de aprovar (a negativa foi específica de East US), mas ainda mantém uma dependência de recurso
  que já provou ser frágil nesta assinatura; (b) trocar o projeto inteiro para AWS — descartado, mesmo
  racional de mercado (35+ vagas) que justificou escolher Azure originalmente, e jogaria fora toda a infra
  já validada (storage, containers, AKS confirmado); **(c) escolhida:** remover a dependência de SQL
  Server do projeto por completo, migrando as duas únicas funções que a usavam (servir features da `gold`
  e logar predições) para serviços da própria storage account já provisionada (Blob/ADLS Gen2 e Table
  Storage). Mantém os três gaps originais (ML clássico, Kubernetes, Azure — ver seção 1) intactos; o único
  gap sacrificado é a experiência específica de SQL serverless sobre data lake, substituída por experiência
  real com Azure Table Storage (NoSQL) e leitura de Parquet direto do ADLS Gen2 por um serviço em produção
  — ainda genuinamente "Azure", só não a peça específica do Synapse.
- Trade-off de custo: gestão do node pool do AKS entre sessões de uso (reduzir/desligar quando não estiver
ativamente demonstrando o projeto) — mecanismo automatizado, não dependência de lembrar manualmente.
- **(Revisado, 15/set/2026)** Resultado da validação de AKS Automatic feita na Fase -1: aparecia
  **disponível** no formulário do Portal em 09/set/2026, mas a criação real (Fase 3) revelou duas
  restrições que o formulário não expunha: quota de vCPU regional em 10 (resolvida via cota self-service)
  e as famílias de VM com suporte a 3 zonas de disponibilidade **indisponíveis** para essa assinatura
  nessa região (não contornável por cota). **Decisão final: usar o fallback já previsto desde a Fase -1**
  — AKS padrão + cluster autoscaler, com `Standard_D4s_v7`. Lição: validar disponibilidade de um recurso
  Azure pelo formulário do Portal não garante que a criação de fato funcione — só a tentativa real revela
  restrições de quota/disponibilidade específicas da assinatura. Detalhe completo na seção 3 (Fase 3,
  status).
- **(Novo, 08/set/2026)** Por que KKBox (dado real de uso+billing) combinado com suporte sintético
  correlacionado, em vez de 100% sintético ou tentar forçar dois datasets reais sem `account_id` em comum
  — lacuna real de dado público disponível, documentada explicitamente, não escondida.
- **(Novo, 08/set/2026)** Por que Azure Synapse Serverless SQL para bronze→silver→gold, em vez de scripts
  Python simples (menos realista para o gap de "data lake na Azure") ou um Spark Pool dedicado (custo e
  complexidade fora do orçamento deste projeto).
- **(Decidido, 10/set/2026)** Critério de amostragem do KKBox — 25.000 contas estratificadas por churn
  (taxa real 9,0%), justificado pela regra EPV (events per variable) além do argumento de custo/orçamento.
  Ver detalhe completo na seção 2.
- **(Novo, 08/set/2026)** Por que manter a definição nativa de churn do KKBox (30 dias pós-expiração) em vez
  da janela de 60 dias do plano original.
- **(Decidido, 14/set/2026)** Por que aceitar F2=0,601 (teste) em vez de continuar tentando bater a meta de
  0,65: duas rodadas de `RandomizedSearchCV` (30 e 50 iterações, incluindo `scale_pos_weight` e
  regularização na segunda) convergiram pro mesmo PR-AUC de validação cruzada (0,605) — sinal claro de
  saturação, não de busca insuficiente. A segunda busca inclusive escolheu `scale_pos_weight=1` como ótimo,
  confirmando que rebalancear a classe minoritária não ajuda mais. Alternativas consideradas: (a) engenharia
  de features adicional (ex.: recência de suporte, tendência de valor pago) — descartada por ora, retorno
  incerto e a meta de 0,65 já era declaradamente uma "aspiração moderada" desde a Fase 0, não uma garantia;
  (b) forçar um threshold ou métrica que maquiasse o número — rejeitado por ir contra o princípio de rigor
  do projeto. Resultado real: F2=0,601 supera o baseline em ~22%, e a checagem de robustez (sem
  `auto_renew_ultima`) confirma que o modelo não é trivial (queda de só 5,4%). Documentar essa distância da
  meta explicitamente no README como resultado honesto, não escondê-la.

## 5. Critério de conclusão

- Modelo supera o baseline heurístico em recall, à precisão mínima definida na Fase 0.
- Serviço de inferência deployado e respondendo em produção real no AKS — não só localmente.
- README documenta as decisões da seção 4, incluindo explicitamente por que Azure foi escolhido para este
projeto.
- (Opcional, desejável) Post de LinkedIn no formato dos posts 3–5, com achado técnico real — por exemplo,
comparando na prática AKS Automatic vs. GKE Autopilot, ou o trade-off de custo real do node pool.

## 6. Estimativa de esforço (referência, não deadline)

- Fase -1 (validações pré-projeto, agora incluindo ADLS Gen2/Synapse/Kaggle): ~1 dia.
- Fase 0 (revisada — ingestão real + camada sintética + bronze/silver/gold no Synapse Serverless +
  definição de sucesso): ~2–3 dias, maior que a estimativa original (~1 dia) por causa do data lake.
- Fase 1–2 (modelo + empacotamento): ~2–3 dias — sem grande diferença por causa do Azure, já que é
majoritariamente Python/SQL.
- Fase 3 (AKS): ~3–4 dias, podendo variar conforme o resultado da validação de AKS Automatic na Fase -1.
- Fase 4 (monitoramento): ~1 dia.
- Fase 5 (CI/CD, stretch): ~1 dia, opcional.

**Total:** ~2 a 2,5 semanas de trabalho focado — maior que a versão anterior por causa do data lake
simplificado (gap técnico a mais, de propósito). O prazo de 15/09/2026 (saída da Hagens) não é mais um
limitador — prioridade é o aprendizado e a qualidade de cada etapa.

## 7. Próximos passos imediatos (atualizado, 11/set/2026)

- ✅ Fase -1 completa (Azure, Kaggle, AKS Automatic validado, ADLS Gen2 — Synapse removido do escopo).
- ✅ Fase 0 quase completa: ingestão bronze, EDA de uso e billing, definição de sucesso — tudo feito.
- **Pendente na Fase 0:** escrever os scripts locais de transformação silver (tipagem/dedup dos arquivos
  do `bronze`) e consolidação gold (`gold_account_activity`), e subir os Parquets resultantes pro ADLS
  Gen2 — substitui o que seria feito via Synapse Serverless (abandonado, ver seção 4).
- Depois disso: Fase 1 (baseline heurístico já calculado — F2=0,494 — mais os modelos de ML clássico:
  Logistic Regression, XGBoost/LightGBM, avaliação com PR-AUC/F2 contra a meta de F2≥0,65).

**Ideia para depois (fora de escopo agora):** se este projeto validar bem a experiência em Azure, um
segundo projeto natural seria replicar parte do RAG/agentes do amigurumi-agent usando Azure OpenAI +
Azure AI Search — endereçaria diretamente o gap técnico específico que apareceu na vaga da L3. Não
incluído neste plano para não estourar escopo.

---

## Changelog de revisão (08/set/2026)

Ajustes feitos após discussão dos riscos levantados na leitura do plano v2 original (PDF):

1. Adicionada **Fase -1** (validações e dependências pré-projeto), incluindo checagem explícita de
   disponibilidade do AKS Automatic antes de comprometer a estimativa da Fase 3.
2. Reforçado o trade-off de custo do node pool do AKS: recomendação de desligamento automatizado
   (`az aks stop`/`start`) em vez de depender de lembrar manualmente — registrada nas seções 3 (Fase 3) e 4.
3. Escopo do SHAP limitado a plot estático no README por ora, com ressalva explícita para retomar a
   decisão (notebook/dashboard) quando a Fase 1 for executada.
4. Adicionado gate de **validação pré-Fase 3**, equivalente em rigor ao gate da Fase 0, antes do deploy em
   Kubernetes.
5. Prazo de 15/09/2026 deixou de ser um limitador rígido — prioridade redefinida para qualidade e
   aprendizado em cada etapa, não para fechar dentro do cronograma original.

## Changelog de revisão (08/set/2026, parte 2 — troca de fonte de dados)

Após a revisão acima, o usuário apontou que `data-lake-engineering-decisions` (marketing-data-lake) é um
projeto fictício/ilustrativo, não uma fonte de dados real, e pediu para usar um dataset público real com um
data lake simplificado na Azure. Ajustes:

1. Dataset trocado de sintético puro para o real KKBox Churn Prediction (Kaggle/WSDM Cup 2018) — uso e
   billing/transações reais, amostrado por conta.
2. Camada de tickets de suporte gerada sinteticamente e correlacionada com os dados reais amostrados,
   por não existir dataset público de suporte com `account_id` em comum com o KKBox — decisão explícita,
   documentada, não escondida.
3. Reintroduzido um data lake simplificado na Azure (ADLS Gen2 bronze/silver/gold) com Azure Synapse
   Serverless SQL como camada de transformação — decisão que tinha sido deliberadamente cortada nas
   revisões anteriores (v2/v3) volta ao escopo, agora como um quarto gap técnico intencional.
4. Variável-alvo trocada da janela de 60 dias (arbitrária) para a definição nativa de churn do KKBox
   (30 dias pós-expiração), já validada pela competição.
5. Estimativa de esforço da Fase 0 aumentada (~2–3 dias em vez de ~1 dia) para refletir a ingestão real
   multi-fonte; total do projeto revisado para ~2 a 2,5 semanas.

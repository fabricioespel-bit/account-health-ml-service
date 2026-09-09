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
negócio (uso cai + suporte sobe → risco de churn sobe).
- **Dataset (revisado, 08/set/2026):**
  - **Fonte real — uso e billing:** [KKBox's Churn Prediction Challenge](https://www.kaggle.com/c/kkbox-churn-prediction-challenge/data)
    (WSDM Cup 2018, Kaggle) — dados reais de uma assinatura de streaming: `transactions` (billing/renovação,
    ~21,5M linhas), `user_logs` (uso diário, ~30M linhas), `members` (cadastro, ~6,7M linhas) e rótulo de
    churn já validado pela competição (~1M contas rotuladas).
  - **Amostragem obrigatória:** o dataset completo é grande demais pro orçamento deste projeto — usar um
    subconjunto de contas (ex.: N mil `msno` sorteados, a definir na Fase 0 junto da definição de sucesso),
    documentando o critério de amostragem (aleatório estratificado por status de churn, para não distorcer
    a proporção de classes).
  - **Camada sintética — suporte:** datasets públicos reais de uso/billing e de tickets de suporte não
    compartilham `account_id` entre si (são de empresas diferentes) — decisão tomada: gerar uma camada
    sintética de tickets de suporte, correlacionada de propósito com queda de uso das mesmas contas reais
    amostradas (mesma causalidade do plano original: uso↓ → tickets↑ → churn↑), documentada
    explicitamente no README como lacuna de dado público real disponível, não como dado real disfarçado.
  - **Ingestão via data lake simplificado na Azure** (ADLS Gen2 bronze/silver/gold + Azure Synapse
    Serverless SQL para as transformações) em vez de carregar direto em Azure SQL Database — decisão
    revisada: o objetivo agora inclui aprender ingestão multi-fonte de verdade, então a simplificação deixada
    de lado no plano v2/v3 (ADLS Gen2 + Synapse) volta ao escopo, mas usando **Synapse Serverless** (sem
    cluster/pool dedicado pra gerenciar) em vez de uma arquitetura completa com Spark/pools dedicados —
    ainda um corte deliberado de complexidade (ver seção 4).
- **Variável-alvo:** usar a **definição nativa de churn do KKBox** (não-renovação em até 30 dias após o fim
  do período pago), documentada e comparada explicitamente com a janela de 60 dias do plano original —
  decisão registrada: manter a definição validada pela competição em vez de forçar uma redefinição
  artificial de 60 dias sobre um dado real que já tem um rótulo estabelecido (mais simples e mais honesto
  ao dado do que reinterpretar a fonte).
- **Split temporal, não aleatório** — evita vazamento de informação futura. Documentar essa decisão
explicitamente.

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
  `gold`) e o workspace do Azure Synapse (modo Serverless) dentro do Resource Group do projeto.
- Critério de saída da Fase -1: por escrito, (a) confirmação AKS Automatic disponível ou fallback assumido,
  (b) estimativa de custo/hora do node pool e mecanismo de desligamento definido, (c) ambiente Azure
  pronto (assinatura, CLI, resource group, ADLS Gen2, Synapse Serverless), (d) acesso ao Kaggle confirmado.

### Fase 0 — Data lake simplificado, dados e definição de sucesso (revisada, 08/set/2026)

- **Ingestão (bronze):** baixar a amostra de contas do KKBox (transactions, user_logs, members — ver seção
  2 para critério de amostragem) via API do Kaggle e subir para o container `bronze` do ADLS Gen2, um
  prefixo por fonte, sem transformação. Gerar a camada sintética de tickets de suporte (correlacionada com
  queda de uso das mesmas contas amostradas) e subir também como fonte própria em `bronze`, claramente
  identificada como sintética (ex. prefixo `bronze/support_tickets_synthetic/`).
- **Transformação (silver):** views/CTAS no Synapse Serverless SQL sobre os arquivos do `bronze` — tipagem,
  deduplicação, padronização de datas, escritas em Parquet no container `silver`. Um modelo por fonte,
  mesma disciplina do padrão bronze/silver/gold já usado no projeto de referência (fictício) citado na seção 1.
- **Consolidação (gold):** tabela única `gold_account_activity` juntando uso + billing reais (por `msno`) com a
  camada sintética de suporte, no formato inspirado em `gld_account_activity_daily` (ver seção 1), escrita em
  `gold` no ADLS Gen2 — e só essa tabela final, já pequena, carregada em Azure SQL Database para servir de
  camada de features de treino/inferência (mantém a Fase 2 simples, sem o serviço FastAPI depender do lake).
- Definir por escrito, antes de treinar qualquer modelo: métrica principal (recall a uma precisão mínima
  aceitável, calibrada depois de ver a distribuição real de churn da amostra), baseline mínimo, critério
  objetivo de "modelo pronto para produção", e o critério de amostragem (tamanho da amostra, estratégia de
  estratificação por churn).

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

### Fase 2 — Empacotamento do modelo como serviço

- FastAPI com endpoints `/predict` e `/health`.
- Modelo serializado (joblib ou ONNX) em Azure Blob Storage, carregado no startup do container — decisão
documentada: cold start vs. tamanho de imagem/reprodutibilidade.
- Testes automatizados do serviço de inferência: contrato de entrada/saída e casos de borda.

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

### Fase 4 — Monitoramento e detecção de drift

- Logging estruturado de predições de volta no Azure SQL Database (tabela de predictions), reaproveitando o
padrão de "monitoramento contínuo" já estabelecido no nível 4 do rag-quality-assurance.
- Logs de aplicação/infraestrutura via Azure Monitor / Log Analytics — equivalente ao Cloud Logging do lado
GCP.
- Checagem simples de drift de dados (distribuição de features ao longo do tempo, via query SQL), com critério
documentado de quando um alerta dispararia.

### Fase 5 (stretch, só se sobrar tempo) — CI/CD

- GitHub Actions: build da imagem, push para o ACR, deploy no AKS.
- Reforça rigor de engenharia, mas não é bloqueante para considerar o projeto "pronto".

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
- Por que Azure SQL Database só para a tabela `gold` final (camada de features), com o restante do lake em
ADLS Gen2 — não a arquitetura completa de um data warehouse, mas também não mais "tudo em SQL direto".
- Trade-off de custo: gestão do node pool do AKS entre sessões de uso (reduzir/desligar quando não estiver
ativamente demonstrando o projeto) — mecanismo automatizado, não dependência de lembrar manualmente.
- **(Novo)** Resultado da validação de AKS Automatic feita na Fase -1: disponível ou fallback, e por quê.
- **(Novo, 08/set/2026)** Por que KKBox (dado real de uso+billing) combinado com suporte sintético
  correlacionado, em vez de 100% sintético ou tentar forçar dois datasets reais sem `account_id` em comum
  — lacuna real de dado público disponível, documentada explicitamente, não escondida.
- **(Novo, 08/set/2026)** Por que Azure Synapse Serverless SQL para bronze→silver→gold, em vez de scripts
  Python simples (menos realista para o gap de "data lake na Azure") ou um Spark Pool dedicado (custo e
  complexidade fora do orçamento deste projeto).
- **(Novo, 08/set/2026)** Critério de amostragem do KKBox (tamanho da amostra e estratificação por churn) —
  por que um subconjunto e não o dataset completo (~21,5M/30M linhas).
- **(Novo, 08/set/2026)** Por que manter a definição nativa de churn do KKBox (30 dias pós-expiração) em vez
  da janela de 60 dias do plano original.

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

## 7. Próximos passos imediatos

- Fase -1: validar disponibilidade de AKS Automatic, confirmar assinatura/créditos Azure, instalar `az`,
  criar Resource Group, provisionar ADLS Gen2 + Synapse Serverless, confirmar acesso ao Kaggle, e definir
  mecanismo de desligamento de custo do cluster.
- Criar o repositório `account-health-ml-service` (público, github.com/fabricioespel-bit).
- Fase 0: baixar a amostra do KKBox, ingerir em `bronze`, gerar a camada sintética de suporte, transformar
  até `gold` via Synapse Serverless, carregar a tabela final em Azure SQL Database, e escrever por escrito a
  definição de sucesso (métrica principal, baseline, critério de "pronto", critério de amostragem) antes de
  qualquer linha de modelo.

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

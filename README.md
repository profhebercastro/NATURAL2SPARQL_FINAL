# Natural2SPARQL 💬 ➡️ SPARQL

[![Java](https://img.shields.io/badge/Java-17-blue.svg?style=for-the-badge&logo=openjdk)](https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html)
[![Spring](https://img.shields.io/badge/Spring_Boot-3.2-green.svg?style=for-the-badge&logo=spring)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.9-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/downloads/release/python-390/)
[![Flask](https://img.shields.io/badge/Flask-black.svg?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Apache Jena](https://img.shields.io/badge/Apache-Jena-orange.svg?style=for-the-badge&logo=apache)](https://jena.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-gray.svg?style=for-the-badge&logo=docker)](https://www.docker.com/)

Um sistema que traduz perguntas em linguagem natural (Português) em consultas **SPARQL**, executando-as contra uma base de conhecimento RDF para obter respostas precisas. O framework utiliza uma arquitetura flexível baseada em templates, Processamento de Linguagem Natural e uma ontologia de domínio para realizar buscas diretas e cálculos dinâmicos.

---

### ✨ **[Acesse a Demonstração Online](https://natural2sparql-v5.onrender.com/)** ✨

*(Nota: A primeira requisição do dia pode demorar um pouco para "acordar" o servidor gratuito da plataforma Render.)*

---

## 📜 Índice

*   [Funcionalidades Principais](#-funcionalidades-principais)
*   [Tecnologias Utilizadas](#-tecnologias-utilizadas)
*   [Arquitetura e Fluxo de Dados](#-arquitetura-e-fluxo-de-dados)
*   [Como Executar o Projeto](#-como-executar-o-projeto)
*   [Como Usar a Aplicação](#-como-usar-a-aplicação)
*   [Estrutura de Arquivos Essenciais](#-estrutura-de-arquivos-essenciais)
*   [Como Adaptar para um Novo Domínio](#-como-adaptar-para-um-novo-domínio)

## ✨ Funcionalidades Principais

*   **🗣️ Interface em Linguagem Natural**: Permite que usuários façam perguntas simples ou complexas sobre um domínio de conhecimento sem precisar conhecer a sintaxe SPARQL.
*   **⚙️ Arquitetura de Microserviços**: Combina a robustez do **Java/Spring Boot** para o backend principal e gerenciamento da ontologia com um microserviço **Python/Flask** dedicado ao Processamento de Linguagem Natural (NLP).
*   **🧠 Motor de NLP Baseado em Similaridade**: Utiliza um modelo de **similaridade de texto (TF-IDF)** para comparar a pergunta do usuário com um conjunto curado de **perguntas de referência**, selecionando o template de consulta mais adequado de forma robusta e escalável.
*   **쿼 Consultas Complexas e Dinâmicas**: Capaz de gerar consultas SPARQL que realizam **cálculos em tempo real** (ex: variação percentual), aplicam **filtros dinâmicos** (por nome, setor, tipo de ação) e executam **consultas aninhadas (subqueries)** para responder perguntas analíticas de múltiplas etapas.
*   **🧩 Motor de Templates Genéricos**: Emprega um sistema de substituição em duas fases. Os templates SPARQL contêm placeholders estruturais (`P1`, `S1`), que são mapeados para termos RDF específicos de um domínio através de um arquivo de propriedades, permitindo que a lógica de consulta seja facilmente reutilizada.
*   **☁️ Pronto para a Nuvem**: Containerizado com **Docker** e configurado para deploy em plataformas como a **Render**, com um script de inicialização que gerencia múltiplos processos.

## ⚙️ Tecnologias Utilizadas

| Categoria                      | Tecnologia                                                                                             | Propósito                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Backend & Orquestração**     | `Java 17`, `Spring Boot 3.2`, `Apache Jena`                                                            | Servidor principal, manipulação da ontologia, geração de consultas, execução de queries |
| **Processamento de Linguagem** | `Python 3.9`, `Flask`, `Gunicorn`, `scikit-learn`                                                      | Microserviço de NLP, classificação de intenção, extração de entidades, normalização de texto |
| **Frontend**                   | `HTML5`, `CSS3`, `JavaScript` (vanilla com API `fetch`)                                                | Interface de usuário interativa para gerar e executar consultas                    |
| **Base de Dados & Config.**    | `RDF/TTL` (ontologia), `.properties` (mapeamento), `.json` (dicionários), `.txt` (templates)           | Armazenamento do conhecimento e das configurações do framework     |
| **DevOps & Build**             | `Docker` (build multi-stage), `Maven`, `start.sh`                                                      | Containerização, gerenciamento de dependências e orquestração dos serviços         |

## 🏗️ Arquitetura e Fluxo de Dados

O sistema opera com uma arquitetura desacoplada onde o serviço Java orquestra o fluxo, consultando o serviço Python para obter inteligência de NLP e, em seguida, construindo a consulta final.

1.  **Interface do Usuário**: O usuário digita uma pergunta na interface web.
2.  **Requisição ao Backend Java**: O Frontend envia a pergunta via `POST` para o endpoint `/api/processar`.
3.  **Chamada ao Serviço de NLP**: O `SPARQLProcessor` (Java) faz uma chamada HTTP para o microserviço Python/Flask.
4.  **Processamento em Python (`nlp_controller.py`)**:
    *   **Seleção de Template por Similaridade**: A pergunta do usuário é vetorizada e comparada com todas as perguntas no arquivo `Reference_questions.txt` usando similaridade de cosseno. O `templateId` da pergunta de referência mais similar é selecionado.
    *   **Extração de Entidades**: Funções baseadas em dicionários e expressões regulares extraem todas as informações relevantes da pergunta: nome da empresa, ticker, setor (incluindo índices como IMAT), data, métricas, tipo de ação (ordinária/preferencial) e parâmetros de ranking.
    *   **Resposta JSON**: Devolve um objeto JSON para o Java, contendo o `templateId` selecionado e um dicionário com todas as `entidades` extraídas.
5.  **Geração da Consulta SPARQL (Java)**:
    *   **Lógica de Montagem Unificada**: O `SPARQLProcessor` carrega o conteúdo do template (`.txt`) correspondente ao `templateId`.
    *   **Substituição de Filtros**: Insere os blocos de filtro (`#FILTER_BLOCK_...#`, `#REGEX_FILTER#`) no template, se as entidades correspondentes foram extraídas pelo NLP.
    *   **Resolução de Placeholders Genéricos**: Chama o `PlaceholderService` para traduzir todos os placeholders estruturais (`P1`, `S1`, etc.) para seus valores RDF.
    *   **Resolução de Placeholders de Valor**: Substitui os placeholders de valor (`#DATA#`, `#CALCULO#`, `#VALOR_DESEJADO#`, etc.) usando os dados restantes do JSON do NLP.
    *   **Retorno**: A consulta SPARQL final e montada é retornada para o Frontend.
6.  **Execução da Consulta**: O usuário pode clicar em **Executar** para enviar a consulta gerada ao backend, que a executa no grafo Apache Jena em memória e retorna o resultado.

## 🚀 Como Executar o Projeto

### Pré-requisitos

*   `Java JDK 17+` & `Apache Maven 3.6+`
*   `Docker`

---

<details>
<summary><strong>Opção Recomendada: Execução com Docker</strong></summary>

A maneira mais fácil e que melhor simula o ambiente de produção é usar o `Dockerfile` e o `start.sh` que já estão no projeto.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/hebercastrorp1979/NATURAL2SPARQL.git
    cd NATURAL2SPARQL
    ```

2.  **Construa a imagem Docker:**
    O `Dockerfile` multi-stage cuida do build do Java, da configuração do Python e da instalação de todas as dependências.
    ```bash
    docker build -t natural2sparql .
    ```

3.  **Execute o container:**
    O script `start.sh` orquestra a inicialização dos dois processos (Java e Python) dentro do container.
    ```bash
    docker run -p 8080:8080 -it natural2sparql
    ```

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

## 🕹️ Como Usar a Aplicação

1.  Acesse a interface web: [**Demo Online**](https://natural2sparql-v5.onrender.com) ou `http://localhost:8080`.
2.  Digite sua pergunta no campo de texto.
    > **Exemplos de Perguntas que o Sistema Entende:**
    >
    > **Buscas Diretas:**
    > *   `Qual foi o preço de fechamento da ação da CSN em 08/05/2023?`
    > *   `Qual foi o preço de abertura da CBAV3 em 08/05/2023?`
    > *   `Qual o código de negociação da empresa Vale?`
    > *   `Qual foi o preço mínimo da ação preferencial do Itau em 05/05/2023?`
    >
    > **Buscas com Cálculo e Ranking:**
    > *   `Qual foi a variação intradiária absoluta da ação da CSN no pregão de 08/05/2023?`
    > *   `Qual ação do setor de mineração que teve a maior alta percentual no pregão do dia 08/05/2023?`
    > *   `Quais as cinco ações de maior percentual de baixa no pregão de 08/05/2023?`
    >
    > **Buscas Complexas (com Subquery):**
    > *   `Qual foi a variação intradiária absoluta da ação com maior alta percentual?`
    > *   `Qual foi o intervalo intradiário percentual da ação com maior baixa entre as ações do IMAT?`
3.  Clique em **GERAR CONSULTA**. A consulta SPARQL correspondente aparecerá.
4.  Clique em **Executar** para ver o resultado.

## 🗂️ Estrutura de Arquivos Essenciais

*   `nlp/`: Pasta dedicada que contém o microserviço Python (`nlp_controller.py`) e seus arquivos de configuração (`requirements.txt`, dicionários `.json`, `Reference_questions.txt`).
*   `src/main/resources/`: Contém os recursos do backend Java.
    *   `static/`: Contém o frontend (`index.html`, CSS, etc.).
    *   `ontology_stock_market_B3.ttl`: O arquivo da ontologia RDF.
    *   `Templates/`: Contém os arquivos de template SPARQL (`.txt`).
    *   `placeholders.properties`: Arquivo crucial que mapeia os placeholders genéricos para os termos RDF.
    *   `application.properties`: Define a porta do servidor e outras configurações do Spring.
*   `Dockerfile`: Define como a aplicação poliglota é empacotada em um container para deploy.
*   `start.sh`: Script que orquestra a inicialização dos serviços Java e Python dentro do container.

## 🔄 Como Adaptar para um Novo Domínio

A arquitetura do framework permite sua adaptação para um novo domínio (ex: filmes, produtos, etc.) através da substituição dos artefatos de conhecimento:

1.  **Criar/Atualizar a Ontologia**: Modifique o arquivo `.ttl` com o esquema e os dados do novo domínio.
2.  **Atualizar Dicionários de NLP**: Altere os arquivos `.json` na pasta `nlp/` para refletir as novas entidades (nomes de produtos, categorias, etc.).
3.  **Criar Perguntas de Referência**: O passo mais importante. Adapte o `Reference_questions.txt` com perguntas de exemplo bem definidas para cada tipo de consulta que você deseja suportar no novo domínio.
4.  **Definir Novos Templates SPARQL**: Crie arquivos `.txt` em `Templates/` com as consultas SPARQL parametrizadas necessárias para o novo domínio.
5.  **Mapear Placeholders**: Edite o `placeholders.properties` para mapear os placeholders genéricos (`P1`, `S1`...) para os novos predicados e classes da sua ontologia.
6.  **Reconstruir a Imagem Docker** (`docker build ...`) para aplicar as mudanças.
# Natural2SPARQL: Geração de Consultas SPARQL a partir de Linguagem Natural

[![Java](https://img.shields.io/badge/Java-17-blue.svg?style=for-the-badge&logo=openjdk)](https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html)
[![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.2-green.svg?style=for-the-badge&logo=spring)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-black.svg?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Apache Jena](https://img.shields.io/badge/Apache-Jena-orange.svg?style=for-the-badge&logo=apache)](https://jena.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-gray.svg?style=for-the-badge&logo=docker)](https://www.docker.com/)

Este framework é o artefato principal da dissertação de Mestrado em Computação Aplicada, apresentada na Faculdade de Filosofia, Ciências e Letras de Ribeirão Preto (FFCLRP) da Universidade de São Paulo (USP), sob o título: *Geração de consultas SPARQL a partir de linguagem natural*.

O sistema traduz perguntas em português para consultas **[SPARQL](https://www.w3.org/TR/sparql11-overview/)**, executando-as contra uma base de conhecimento RDF para obter respostas precisas sobre o mercado de ações brasileiro (B3). O principal objetivo do projeto é democratizar o acesso a dados semânticos, permitindo que usuários sem conhecimento técnico em SPARQL ou ontologias possam realizar consultas complexas de forma intuitiva.

---

### ✨ **[Acesse a Demonstração Online](http://calisto.ffclrp.usp.br:4000)** ✨

---

## 📜 Índice

*   [Funcionalidades Principais](#-funcionalidades-principais)
*   [Tecnologias Utilizadas](#-tecnologias-utilizadas)
*   [Arquitetura e Fluxo de Dados](#-arquitetura-e-fluxo-de-dados)
*   [Como Executar o Projeto](#-como-executar-o-projeto)
*   [Exemplos de Perguntas Suportadas](#-exemplos-de-perguntas-suportadas)
*   [Artefatos de Conhecimento](#-artefatos-de-conhecimento)
*   [Como Adaptar para um Novo Domínio](#-como-adaptar-para-um-novo-domínio)

## ✨ Funcionalidades Principais

*   **🗣️ Interface em Linguagem Natural**: Permite que usuários façam perguntas em português sobre o mercado de ações da B3, abstraindo a complexidade da sintaxe SPARQL.
*   **⚙️ Arquitetura de Microserviços**: Combina a robustez do **Java/Spring Boot** para orquestração e manipulação do grafo RDF com a agilidade de um microserviço **Python/Flask** dedicado ao Processamento de Linguagem Natural (PLN).
*   **🧠 Motor de PLN Híbrido**: Utiliza uma abordagem de duas etapas para máxima precisão:
    1.  **Seleção por Regras Heurísticas**: Identifica padrões em perguntas complexas (ex: "a ação do setor X com a maior métrica Y") para selecionar diretamente templates com subconsultas.
    2.  **Seleção por Similaridade Semântica**: Para casos gerais, emprega um modelo `TF-IDF` para calcular a similaridade de cosseno entre a pergunta do usuário e um conjunto de **perguntas de referência**, selecionando o template mais adequado.
*   **🎯 Extração de Entidades Robusta**: O serviço de PLN utiliza uma pipeline de extração baseada em dicionários com ordem de prioridade para identificar datas, métricas, tickers, nomes de empresas, setores e índices, minimizando ambiguidades.
*   **쿼 Consultas Analíticas Complexas**: O framework vai além de simples buscas, gerando consultas SPARQL que realizam **cálculos em tempo de execução** (`BIND`), aplicam **filtros dinâmicos** (`FILTER`) e executam **consultas aninhadas (subqueries)** para responder a perguntas analíticas avançadas.
*   **☁️ Pronto para a Nuvem**: Containerizado com **Docker** (usando build multi-stage para otimização) e configurado para deploy em qualquer ambiente que suporte contêineres, com um script de inicialização que gerencia os dois serviços (Java e Python).

## ⚙️ Tecnologias Utilizadas

| Categoria                      | Tecnologia                                                                                             | Propósito                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Backend & Orquestração**     | `Java 17`, `Spring Boot 3.2`, `Apache Jena`                                                            | Servidor principal da API REST, manipulação da ontologia, construção e execução de queries SPARQL. |
| **Processamento de Linguagem** | `Python 3.9+`, `Flask`, `scikit-learn`                                                      | Microserviço de PLN: classificação de intenção, extração de entidades, normalização de texto. |
| **Frontend**                   | `HTML5`, `CSS3`, `JavaScript` (vanilla com API `fetch`)                                                | Interface de usuário interativa para submeter perguntas e visualizar os resultados.   |
| **Base de Conhecimento**       | `RDF/Turtle (.ttl)`, `.properties`, `.json`, `.txt`                                                     | Ontologia, mapeamentos, dicionários e templates que formam a base de conhecimento. |
| **Build & Deploy**             | `Docker` (multi-stage), `Maven`, `start.sh`                                                            | Containerização, gerenciamento de dependências e orquestração dos serviços.        |

## 🏗️ Arquitetura e Fluxo de Dados

O sistema opera com uma arquitetura desacoplada onde o serviço Java orquestra o fluxo, consultando o serviço Python para obter inteligência de NLP e, em seguida, construindo a consulta final.

1.  **Interface do Usuário**: O usuário digita uma pergunta na interface web.
2.  **Requisição ao Backend Java**: O Frontend envia a pergunta via `POST` para o endpoint `/api/processar`.
3.  **Chamada ao Serviço de NLP**: O `SPARQLProcessor` (Java) faz uma chamada HTTP para o microserviço Python/Flask (`http://localhost:5000/process_question`).
4.  **Processamento em Python (`nlp_controller.py`)**:
    *   **Extração de Entidades**: A pergunta é processada por uma pipeline de regras que extrai entidades como datas, tickers, nomes de empresas, setores, índices e métricas.
    *   **Seleção de Template Híbrida**: O sistema primeiro aplica regras heurísticas para identificar perguntas complexas e selecionar o template apropriado. Se nenhuma regra se aplica, ele recorre à similaridade de texto com as `Reference_questions.txt`.
    *   **Resposta JSON**: Devolve um objeto JSON para o Java, contendo o `templateId` selecionado e um dicionário com todas as `entidades` extraídas.
5.  **Geração da Consulta SPARQL (Java)**:
    *   O `SPARQLProcessor` carrega o conteúdo do template (`.txt`).
    *   Ele realiza uma **substituição em duas fases**: primeiro preenche os placeholders de valor (`#DATA#`, `#ENTIDADE_NOME#`), e depois, com auxílio do `PlaceholderService`, traduz os placeholders estruturais (`P1`, `S1`, etc.) para seus URIs da ontologia, definidos em `placeholders.properties`.
    *   A consulta final é montada e retornada ao Frontend.
6.  **Execução e Formatação**: O Frontend envia a consulta gerada para o endpoint `/api/executar`. O backend executa a query e formata os resultados numéricos para uma exibição amigável.

## 🚀 Como Executar o Projeto

### Pré-requisitos

*   `Java JDK 17+` & `Apache Maven 3.6+`
*   `Python 3.9+` & `pip`
*   `Docker` (recomendado para simular o ambiente de produção)

---

<details>
<summary><strong>Opção 1 (Recomendada): Execução com Docker</strong></summary>

A maneira mais fácil e robusta de executar o projeto, simulando um ambiente de produção.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/profhebercastro/NATURAL2SPARQL_FINAL.git
    cd NATURAL2SPARQL_FINAL
    ```

2.  **Construa a imagem Docker:**
    O `Dockerfile` multi-stage cuida da compilação do Java, da configuração do Python e da instalação de todas as dependências.
    ```bash
    docker build -t natural2sparql:latest .
    ```

3.  **Execute o contêiner:**
    O script `start.sh` orquestra a inicialização dos dois processos (Java e Python).
    ```bash
    docker run -d --restart always -p 4000:8080 --name natural2sparql-container natural2sparql:latest
    ```
    Análise do comando:
    - `-d`: Roda o contêiner em segundo plano (detached).
    - `--restart always`: Garante que o contêiner reinicie automaticamente com o servidor.
    - `-p 4000:8080`: Mapeia a porta 4000 do seu computador (host) para a porta 8080 do contêiner (onde o Spring Boot roda).
    - `--name natural2sparql-container`: Dá um nome fácil de gerenciar ao contêiner.

4.  Acesse a aplicação em [**http://localhost:4000**](http://localhost:4000).

</details>

<details>
<summary><strong>Opção 2: Execução Local (para Desenvolvimento)</strong></summary>

Ideal para desenvolvimento e depuração, executando cada serviço separadamente.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/profhebercastro/NATURAL2SPARQL_FINAL.git
    cd NATURAL2SPARQL_FINAL
    ```

2.  **Execute o Serviço de NLP (Python):**
    *   Abra um terminal na raiz do projeto.
    *   Crie e ative um ambiente virtual:
        ```bash
        python3 -m venv venv
        source venv/bin/activate  # macOS/Linux
        # venv\Scripts\activate    # Windows
        ```
    *   Instale as dependências:
        ```bash
        pip install -r requirements.txt
        ```
    *   Inicie o servidor Flask:
        ```bash
        python3 src/main/resources/nlp/nlp_controller.py
        ```
    *   O servidor Python estará rodando em `http://localhost:5000`. **Deixe este terminal aberto.**

3.  **Execute o Serviço Principal (Java):**
    *   Abra um **novo** terminal na raiz do projeto.
    *   Compile e execute a aplicação Spring Boot com Maven:
        ```bash
        mvn spring-boot:run
        ```
    *   O servidor Java estará rodando em `http://localhost:8080`.

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

## 🕹️ Exemplos de Perguntas Suportadas

> **Buscas Diretas:**
> *   `Qual foi o preço de fechamento da ação da CSN em 18/06/2025?`
> *   `Qual o código de negociação da empresa Gerdau?`
> *   `Quais são as empresas do setor de energia elétrica?`
>
> **Buscas com Agregação e Filtros:**
> *   `Qual foi o volume total negociado nas ações de bancos em 13/06/2025?`
> *   `Qual foi o preço mínimo da ação preferencial do Itau em 17/06/2025?`
>
> **Buscas com Cálculo e Ranking:**
> *   `Qual foi a variação intradiária absoluta da ação da CSN no pregão de 30/06/2025?`
> *   `Qual ação do setor de mineração que teve a maior alta percentual no pregão do dia 18/06/2025?`
> *   `Quais as cinco ações de maior percentual de baixa no pregão de 10/06/2025?`
>
> **Buscas Complexas (com Subquery):**
> *   `Qual foi o volume financeiro da ação com o maior percentual de alta no pregão de 30/06/2025?`
> *   `Qual foi o intervalo intradiário percentual da ação com maior baixa entre as ações do IMAT no pregão de 30/06/2025?`

## 🗂️ Artefatos de Conhecimento

A flexibilidade do framework vem da separação entre o código e os artefatos de conhecimento, localizados em `src/main/resources/`.

*   `nlp/`: Contém os dicionários e arquivos de referência para o microserviço Python.
    *   `Reference_questions.txt`: O conjunto de perguntas de referência para o cálculo de similaridade.
    *   `Named_entity_dictionary.json`: Mapeia nomes informais de empresas para seus nomes canônicos.
    *   `sector_map.json`: Mapeia sinônimos de setores para os nomes canônicos.
    *   `index_map.json`: Mapeia siglas de índices (IBOV, IFNC) para suas listas de tickers.
*   `Templates/`: Contém os arquivos de template SPARQL (`.txt`). Cada arquivo representa um tipo de consulta parametrizada.
*   `ontology_inferred_final.ttl`: A base de conhecimento RDF, pré-processada, contendo toda a ontologia e os dados do mercado de ações.
*   `placeholders.properties`: Arquivo crucial que desacopla os templates da ontologia, mapeando placeholders estruturais genéricos (ex: `P1`, `S1`) para os URIs e variáveis SPARQL específicos.

## 🔄 Como Adaptar para um Novo Domínio

A arquitetura modular permite a adaptação do framework para um novo domínio (ex: filmes, produtos biológicos, etc.) através da substituição dos artefatos de conhecimento, sem a necessidade de alterar o código-fonte Java ou Python.

1.  **Criar/Atualizar a Ontologia**: Modele o novo domínio em um arquivo `.ttl` (ou outro formato RDF) e coloque-o na pasta `resources`.
2.  **Atualizar Dicionários de NLP**: Adapte os arquivos `.json` na pasta `nlp/` para refletir as novas entidades, categorias e sinônimos do seu domínio.
3.  **Criar Perguntas de Referência**: O passo mais importante. Adapte o `Reference_questions.txt` com exemplos de perguntas para cada tipo de consulta que você deseja suportar.
4.  **Definir Novos Templates SPARQL**: Crie novos arquivos `.txt` em `Templates/` com as consultas SPARQL parametrizadas necessárias para o novo domínio.
5.  **Mapear Placeholders**: Edite o `placeholders.properties` para mapear os placeholders estruturais (`P1`, `S1`...) para os novos predicados e classes da sua ontologia.
6.  **Reconstruir a Imagem Docker** (`docker build ...`) para aplicar as mudanças.
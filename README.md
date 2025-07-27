# Natural2SPARQL 💬 ➡️ SPARQL

[![Java](https://img.shields.io/badge/Java-17-blue.svg?style=for-the-badge&logo=openjdk)](https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html)
[![Spring](https://img.shields.io/badge/Spring_Boot-3.2-green.svg?style=for-the-badge&logo=spring)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-black.svg?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Apache Jena](https://img.shields.io/badge/Apache-Jena-orange.svg?style=for-the-badge&logo=apache)](https://jena.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-gray.svg?style=for-the-badge&logo=docker)](https://www.docker.com/)

Um sistema que traduz perguntas em linguagem natural (Português) em consultas **[SPARQL](https://www.w3.org/TR/sparql11-overview/)**, executando-as contra uma base de conhecimento RDF para obter respostas precisas. O framework utiliza uma arquitetura flexível baseada em templates, Processamento de Linguagem Natural e uma ontologia de domínio para realizar buscas diretas e cálculos dinâmicos.

---

### ✨ **[Acesse a Demonstração Online](https://natural2sparql-final.onrender.com/)** ✨

*(Nota: A primeira requisição do dia pode demorar cerca de 30 segundos para "acordar" o servidor da plataforma Render.)*

---

## 📜 Índice

*   [Funcionalidades Principais](#-funcionalidades-principais)
*   [Tecnologias Utilizadas](#-tecnologias-utilizadas)
*   [Arquitetura e Fluxo de Dados](#-arquitetura-e-fluxo-de-dados)
*   [Como Executar o Projeto](#-como-executar-o-projeto)
*   [Exemplos de Perguntas](#-exemplos-de-perguntas)
*   [Estrutura de Arquivos Essenciais](#-estrutura-de-arquivos-essenciais)
*   [Como Adaptar para um Novo Domínio](#-como-adaptar-para-um-novo-domínio)

## ✨ Funcionalidades Principais

*   **🗣️ Interface em Linguagem Natural**: Permite que usuários façam perguntas simples ou complexas sobre um domínio de conhecimento sem precisar conhecer a sintaxe SPARQL.
*   **⚙️ Arquitetura de Microserviços**: Combina a robustez do **Java/Spring Boot** para o backend principal com um microserviço **Python/Flask** dedicado ao Processamento de Linguagem Natural (NLP).
*   **🧠 Motor de NLP Híbrido**:
    *   **Seleção de Template por Regras**: Utiliza um sistema de regras explícitas para selecionar o template de consulta mais adequado para perguntas que envolvem setores (ex: `Template_4C` para agregações), garantindo precisão.
    *   **Seleção por Similaridade**: Para outros casos, emprega um modelo de **similaridade de texto (TF-IDF)** para comparar a pergunta do usuário com um conjunto de **perguntas de referência**, selecionando o template mais provável de forma robusta.
*   **🎯 Extração de Entidades Robusta**: O serviço de NLP segue uma pipeline hierárquica para extrair entidades, priorizando termos inequívocos (como tickers e datas) e usando dicionários para identificar setores e nomes de empresas, evitando conflitos com palavras-chave.
*   **쿼 Consultas Complexas e Dinâmicas**: Capaz de gerar consultas SPARQL que realizam **cálculos em tempo real** (ex: variação percentual), aplicam **filtros dinâmicos** (por nome, setor, tipo de ação) e executam **consultas aninhadas (subqueries)** para responder perguntas analíticas.
*   **☁️ Pronto para a Nuvem**: Containerizado com **Docker** (build multi-stage) e configurado para deploy em plataformas como a **Render**, com um script de inicialização que gerencia múltiplos processos.

## ⚙️ Tecnologias Utilizadas

| Categoria                      | Tecnologia                                                                                             | Propósito                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Backend & Orquestração**     | `Java 17`, `Spring Boot 3.2`, `Apache Jena`                                                            | Servidor principal, manipulação da ontologia, geração de consultas, execução de queries |
| **Processamento de Linguagem** | `Python 3.9+`, `Flask`, `scikit-learn`                                                                 | Microserviço de NLP, classificação de intenção, extração de entidades, normalização de texto |
| **Frontend**                   | `HTML5`, `CSS3`, `JavaScript` (vanilla com API `fetch`)                                                | Interface de usuário interativa para gerar e executar consultas                    |
| **Base de Dados & Config.**    | `RDF/TTL` (ontologia pré-calculada), `.properties` (mapeamento), `.json` (dicionários), `.txt` (templates) | Armazenamento do conhecimento e das configurações do framework     |
| **DevOps & Build**             | `Docker` (build multi-stage), `Maven`, `start.sh`                                                      | Containerização, gerenciamento de dependências e orquestração dos serviços         |

## 🏗️ Arquitetura e Fluxo de Dados

O sistema opera com uma arquitetura desacoplada onde o serviço Java orquestra o fluxo, consultando o serviço Python para obter inteligência de NLP e, em seguida, construindo a consulta final.

1.  **Interface do Usuário**: O usuário digita uma pergunta na interface web.
2.  **Requisição ao Backend Java**: O Frontend envia a pergunta via `POST` para o endpoint `/api/processar`.
3.  **Chamada ao Serviço de NLP**: O `SPARQLProcessor` (Java) faz uma chamada HTTP para o microserviço Python/Flask.
4.  **Processamento em Python (`nlp_controller.py`)**:
    *   **Extração de Entidades em Pipeline**: Uma função única e robusta (`extrair_todas_entidades`) processa a pergunta em etapas, extraindo e "consumindo" entidades em uma ordem de prioridade (Data -> Métricas -> Setor -> Ticker/Nome da Empresa) para evitar ambiguidades.
    *   **Seleção de Template Híbrida**: O sistema primeiro verifica se as entidades extraídas correspondem a uma regra de negócio explícita para escolher um template de consulta complexa (`Template_8A/B`, `Template_7A/B`). Se nenhuma regra for acionada, ele recorre à similaridade de texto (TF-IDF) com o `Reference_questions.txt` para encontrar o template mais adequado.
    *   **Resposta JSON**: Devolve um objeto JSON para o Java, contendo o `templateId` selecionado e um dicionário com todas as `entidades` extraídas.
5.  **Geração da Consulta SPARQL (Java)**:
    *   O `SPARQLProcessor` carrega o conteúdo do template (`.txt`) correspondente.
    *   Ele preenche os placeholders (`#DATA#`, `#CALCULO#`, etc.) usando os dados do JSON do NLP.
    *   Uma lógica inteligente diferencia entre nomes de empresa e tickers para gerar o bloco de filtro (`#FILTER_BLOCK_ENTIDADE#`) correto.
    *   O `PlaceholderService` traduz todos os placeholders estruturais (`P1`, `S1`, etc.) para seus valores RDF.
    *   Os prefixos são adicionados, e a consulta final é retornada ao Frontend.
6.  **Execução e Formatação**: O Frontend envia a consulta gerada e o tipo de métrica para o endpoint `/api/executar`. O backend executa a query no grafo Apache Jena e formata os resultados numéricos (moeda, percentual, números grandes) antes de devolver a resposta final para exibição.

## 🚀 Como Executar o Projeto

### Pré-requisitos

*   `Java JDK 17+` & `Apache Maven 3.6+`
*   `Python 3.9+` & `pip`
*   `Docker` (recomendado para simular o ambiente de produção)

---

<details>
<summary><strong>Opção Recomendada: Execução com Docker</strong></summary>

A maneira mais fácil e que melhor simula o ambiente de produção é usar o `Dockerfile` que já está no projeto.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/profhebercastro/NATURAL2SPARQL_FINAL.git
    cd NATURAL2SPARQL_FINAL
    ```

2.  **Construa a imagem Docker:**
    O `Dockerfile` multi-stage cuida do build do Java, da configuração do Python e da instalação de todas as dependências.
    ```bash
    docker build -t natural2sparql .
    ```

3.  **Execute o container:**
    O script `start.sh` orquestra a inicialização dos dois processos (Java e Python) dentro do container.
    ```bash
    docker run -p 8080:10000 -it natural2sparql
    ```
    *Nota: Mapeamos a porta 8080 do seu computador para a porta 10000 do container, que é a porta padrão do Render.*

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

<details>
<summary><strong>Opção 2: Execução Local (para Desenvolvimento)</strong></summary>

Esta abordagem permite executar cada serviço separadamente, o que é ideal para desenvolvimento e depuração.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/profhebercastro/NATURAL2SPARQL_FINAL.git
    cd NATURAL2SPARQL_FINAL
    ```

2.  **Execute o Serviço de NLP (Python):**
    *   Abra um terminal na raiz do projeto.
    *   Crie e ative um ambiente virtual:
        ```bash
        python -m venv venv
        # Windows:
        venv\Scripts\activate
        # macOS/Linux:
        source venv/bin/activate
        ```
    *   Instale as dependências:
        ```bash
        pip install -r requirements.txt
        ```
    *   Navegue até a pasta do script e inicie o servidor:
        ```bash
        cd src/main/resources
        python nlp_controller.py
        ```
    *   O servidor Python estará rodando em `http://localhost:5000`. **Deixe este terminal aberto.**

3.  **Execute o Serviço Principal (Java):**
    *   Abra um **novo** terminal na raiz do projeto.
    *   Compile e execute a aplicação Spring Boot com Maven:
        ```bash
        mvn spring-boot:run
        ```
    *   O servidor Java estará rodando em `http://localhost:8080` (ou na porta configurada).

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

## 🕹️ Exemplos de Perguntas

> **Buscas Diretas:**
> *   `Qual foi o preço de fechamento da ação da CSN em 18/06/2025?`
> *   `Qual foi o preço de abertura da CBAV3 em 10/06/2025?`
> *   `Qual o código de negociação da empresa Gerdau?`
> *   `Qual foi o preço mínimo da ação preferencial do Itau em 17/06/2025?`
> *   `Quais são as ações do setor de energia elétrica?`
>
> **Buscas com Agregação:**
> *   `Qual foi o volume total negociado nas ações de bancos em 13/06/2025?`
> *   `Some a quantidade de ações do Itau negociadas no pregão de 23/06/2025.`
>
> **Buscas com Cálculo e Ranking:**
> *   `Qual foi a variação intradiária absoluta da ação da CSN no pregão de 30/06/2025?`
> *   `Qual ação do setor de mineração que teve a maior alta percentual no pregão do dia 18/06/2025?`
> *   `Quais as cinco ações de maior percentual de baixa no pregão de 10/06/2025?`
>
> **Buscas Complexas (com Subquery):**
> *   `Qual foi a variação intradiária absoluta da ação com o maior percentual de alta no pregão de 30/06/2025?`
> *   `Qual foi o intervalo intradiário percentual da ação com maior baixa entre as ações do IMAT no pregão de 30/06/2025?`

## 🗂️ Estrutura de Arquivos Essenciais

*   `src/main/resources/`: Contém os recursos do backend Java e o microserviço Python.
    *   `nlp_controller.py`: O microserviço Python/Flask.
    *   `static/index.html`: O frontend da aplicação.
    *   `ontology_inferred_final.ttl`: O arquivo pré-processado da ontologia RDF.
    *   `Templates/`: Contém os arquivos de template SPARQL (`.txt`).
    *   `placeholders.properties`: Arquivo crucial que mapeia os placeholders genéricos para os termos RDF.
    *   Dicionários de NLP (`Named_entity_dictionary.json`, `setor_map.json`, etc.).
*   `Dockerfile`: Define como a aplicação poliglota é empacotada em um container para deploy.
*   `start.sh`: Script que orquestra a inicialização dos serviços Java e Python dentro do container.
*   `requirements.txt`: Lista as dependências do serviço Python.

## 🔄 Como Adaptar para um Novo Domínio

A arquitetura do framework permite sua adaptação para um novo domínio (ex: filmes, produtos, etc.) através da substituição dos artefatos de conhecimento:

1.  **Criar/Atualizar a Ontologia**: Gere um novo arquivo `.ttl` com o esquema e os dados do novo domínio.
2.  **Atualizar Dicionários de NLP**: Altere os arquivos `.json` para refletir as novas entidades (nomes de produtos, categorias, sinônimos, etc.).
3.  **Criar Perguntas de Referência**: O passo mais importante. Adapte o `Reference_questions.txt` com perguntas de exemplo bem definidas para cada tipo de consulta que você deseja suportar no novo domínio.
4.  **Definir Novos Templates SPARQL**: Crie arquivos `.txt` em `Templates/` com as consultas SPARQL parametrizadas necessárias para o novo domínio.
5.  **Mapear Placeholders**: Edite o `placeholders.properties` para mapear os placeholders genéricos (`P1`, `S1`...) para os novos predicados e classes da sua ontologia.
6.  **Reconstruir a Imagem Docker** (`docker build ...`) para aplicar as mudanças.
# Natural2SPARQL_2025 💬 ➡️ SPARQL

[![Java](https://img.shields.io/badge/Java-17-blue.svg?style=for-the-badge&logo=openjdk)](https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html)
[![Spring](https://img.shields.io/badge/Spring_Boot-3-green.svg?style=for-the-badge&logo=spring)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.9-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/downloads/release/python-390/)
[![Flask](https://img.shields.io/badge/Flask-black.svg?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Apache Jena](https://img.shields.io/badge/Apache-Jena-orange.svg?style=for-the-badge&logo=apache)](https://jena.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-gray.svg?style=for-the-badge&logo=docker)](https://www.docker.com/)

Um sistema poliglota que traduz perguntas em linguagem natural (Português) em consultas **SPARQL**, executando-as contra uma base de conhecimento RDF para obter respostas precisas.

---

### ✨ **[Acesse a Demonstração Online](https://natural2sparql-2025.onrender.com)** ✨

*(Nota: A primeira requisição do dia pode demorar um pouco para "acordar" o servidor gratuito do Render.)*

---

## 📜 Índice

*   [Funcionalidades Principais](#-funcionalidades-principais)
*   [Tecnologias Utilizadas](#-tecnologias-utilizadas)
*   [Arquitetura e Fluxo de Dados](#-arquitetura-e-fluxo-de-dados)
*   [Como Executar o Projeto](#-como-executar-o-projeto)
*   [Como Usar a Aplicação](#-como-usar-a-aplicação)
*   [Estrutura de Arquivos Essenciais](#-estrutura-de-arquivos-essenciais)
*   [Atualizando os Dados](#-atualizando-os-dados)

## ✨ Funcionalidades Principais

*   **🗣️ Interface em Linguagem Natural**: Permite que usuários façam perguntas sobre o mercado de ações sem precisar conhecer a sintaxe SPARQL.
*   **⚙️ Arquitetura de Microserviços**: Combina a robustez do **Java/Spring Boot** para o backend principal e gerenciamento da ontologia com um microserviço **Python/Flask** dedicado ao Processamento de Linguagem Natural (NLP).
*   **🧠 Povoamento da Base de Conhecimento**: Na inicialização, o sistema lê dados de planilhas `.xlsx` e popula dinamicamente uma ontologia RDF em memória usando Apache Jena.
*   **🧩 Motor Baseado em Templates**: Utiliza um sistema flexível de templates SPARQL. Para suportar novos tipos de perguntas, basta adicionar um novo arquivo de template e uma nova "pergunta de interesse", minimizando a necessidade de alterações no código-fonte.
*   **☁️ Pronto para a Nuvem**: Containerizado com **Docker** usando um build multi-stage eficiente e configurado para deploy contínuo na plataforma **Render**.

## ⚙️ Tecnologias Utilizadas

| Categoria                      | Tecnologia                                                                                             | Propósito                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Backend & Orquestração**     | `Java 17`, `Spring Boot 3`, `Apache Jena`, `Apache POI`, `OkHttp`                                        | Servidor principal, manipulação da ontologia, leitura de Excel, comunicação HTTP   |
| **Processamento de Linguagem** | `Python 3.9`, `Flask`, `sentence-transformers`, `scikit-learn`                                         | Microserviço de NLP, similaridade semântica, extração de entidades                 |
| **Frontend**                   | `HTML5`, `CSS3`, `JavaScript` (vanilla com API `fetch`)                                                | Interface de usuário simples e reativa                                             |
| **Base de Dados**              | `RDF/TTL` (esquema da ontologia), `.xlsx` (fonte de dados)                                             | Armazenamento do conhecimento e dos dados brutos                                   |
| **DevOps & Build**             | `Docker` (build multi-stage), `Maven`                                                                  | Containerização, gerenciamento de dependências e build do projeto Java             |

## 🏗️ Arquitetura e Fluxo de Dados

O sistema opera com uma arquitetura desacoplada onde o serviço Java orquestra o fluxo, consultando o serviço Python para obter inteligência de NLP.

1.  **Interface do Usuário**: O usuário digita "Qual foi o preço de fechamento da ação da CSN em 08/05/2023?" e clica em `Processar`.
2.  **Requisição ao Backend Java**: O Frontend envia a pergunta via `POST` para o endpoint `/process-question` no servidor Spring Boot.
3.  **Chamada ao Serviço de NLP**: O `SPARQLProcessor` (Java) faz uma chamada HTTP para o microserviço Python/Flask (`http://localhost:5000/nlp`), enviando a pergunta do usuário.
4.  **Processamento em Python (`nlp_controller.py`)**:
    *   **Identificação do Template**: Usa o modelo de embeddings `sentence-transformers` para calcular a similaridade semântica entre a pergunta do usuário e a lista em `perguntas_de_interesse.txt`. O match com maior pontuação define o `template_id` (ex: `Template_1A`).
    *   **Extração de Entidades**: Usa expressões regulares e o `Thesaurus.json` para extrair e normalizar entidades como `data`, `empresa` e `valor_desejado`.
    *   **Resposta JSON**: Devolve um objeto JSON para o Java, contendo o `template_id` e as `entidades` extraídas. Ex: `{"template_id": "Template_1A", "entities": {...}}`.
5.  **Geração da Consulta SPARQL (Java)**:
    *   O `SPARQLProcessor` recebe o JSON.
    *   Lê o arquivo de template correspondente (ex: `Template_1A.txt`).
    *   Usa o `Thesaurus.json` para mapear os termos extraídos (ex: "preço de fechamento" -> `b3:precoFechamento`) e substitui os placeholders (`#ENTIDADE_NOME#`, `#DATA#`, etc.) no template.
6.  **Execução da Consulta**: O `Ontology.java` recebe a consulta SPARQL completa e a executa contra o modelo RDF em memória usando o motor de consulta do **Apache Jena**.
7.  **Resposta Final**: O resultado da consulta é formatado e retornado ao Frontend, que o exibe para o usuário.

## 🚀 Como Executar o Projeto

### Pré-requisitos

*   `Java JDK 17+` & `Apache Maven 3.6+`
*   `Python 3.9+` & `pip`
*   `Docker` (para execução em container)

---

<details>
<summary><strong>Opção 1: Execução Local (Recomendado para desenvolvimento)</strong></summary>

Como o projeto consiste em dois serviços separados, você precisará de **dois terminais**.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/hebercastro79/Natural2SPARQL_2025.git
    cd Natural2SPARQL_2025
    ```

2.  **Terminal 1: Inicie o Serviço de NLP (Python)**
    *   Instale as dependências:
        ```bash
        pip install -r requirements.txt
        ```
    *   Execute o servidor Flask. O modelo de linguagem será baixado na primeira vez.
        ```bash
        flask --app src/main/resources/nlp_controller run
        ```
    *   O serviço estará rodando em `http://localhost:5000`.

3.  **Terminal 2: Inicie o Serviço Principal (Java)**
    *   Execute a aplicação com Maven:
        ```bash
        ./mvnw spring-boot:run
        ```
    *   Na primeira execução, o sistema irá popular a base de conhecimento a partir dos arquivos Excel.

4.  Acesse a aplicação completa em [**http://localhost:8080**](http://localhost:8080).

</details>

<details>
<summary><strong>Opção 2: Execução com Docker (Simula o ambiente de produção)</strong></summary>

O `Dockerfile` foi projetado para construir e executar ambos os serviços em um único container.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/hebercastro79/Natural2SPARQL_2025.git
    cd Natural2SPARQL_2025
    ```

2.  **Construa a imagem Docker:**
    O `Dockerfile` multi-stage cuida do build do Java, da configuração do Python e da instalação de todas as dependências.
    ```bash
    docker build -t natural2sparql .
    ```

3.  **Execute o container:**
    Um script `start.sh` (executado pelo Dockerfile) se encarrega de iniciar os dois processos (Java e Python) dentro do container.
    ```bash
    docker run -p 8080:8080 -it natural2sparql
    ```

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

## 🕹️ Como Usar a Aplicação

1.  Acesse a interface web: [**Demo Online**](https://natural2sparql-2025.onrender.com) ou `http://localhost:8080`.
2.  Digite sua pergunta no campo de texto.
    > **Exemplos de perguntas que o sistema entende:**
    > *   `Qual foi o preço de fechamento da ação da CSN em 08/05/2023?`
    > *   `Qual foi o preço de abertura da CBAV3 em 08/05/2023?`
    > *   `Qual o código de negociação da ação da Gerdau?`
    > *   `Quais são as ações do setor eletrico?`
    > *   `Qual foi o volume negociado nas ações do setor bancário em 05/05/2023?`
3.  Clique em **Processar**. O resultado da consulta aparecerá diretamente na área de resposta.

## 🗂️ Estrutura de Arquivos Essenciais

*   `src/main/resources/ontologiaB3_com_inferencia.ttl`: O esqueleto da nossa ontologia, definindo as classes e propriedades.
*   `src/main/resources/Datasets/`: Contém as planilhas com dados brutos de negociações.
*   `src/main/resources/Templates/`: Contém os arquivos de template SPARQL.
*   `src/main/resources/Thesaurus.json`: Dicionário crucial que mapeia termos da linguagem natural (ex: "csn", "preço de abertura") para seus identificadores formais na ontologia (ex: "CSN MINERACAO S.A.", "b3:precoAbertura").
*   `src/main/resources/perguntas_de_interesse.txt`: Lista de perguntas-exemplo, usada pelo serviço de NLP para determinar a intenção do usuário.
*   `src/main/resources/nlp_controller.py`: O microserviço Python/Flask que lida com todo o NLP.
*   `Dockerfile`: Define como a aplicação poliglota é empacotada em um container.
*   `start.sh`: Script que orquestra a inicialização dos serviços Java e Python dentro do container.

## 🔄 Atualizando os Dados

Para atualizar o sistema com dados de novos pregões ou empresas:

1.  **Adicione/Substitua Planilhas**: Coloque os novos arquivos `.xlsx` na pasta `src/main/resources/Datasets/`. Certifique-se de que eles seguem o mesmo formato das planilhas existentes.
2.  **Atualize o Thesaurus**: Se novas empresas ou tickers foram adicionados, atualize o `Thesaurus.json` para que o sistema possa reconhecê-los.
3.  **Reinicie a Aplicação**: Simplesmente pare e reinicie a aplicação (seja via `mvnw spring-boot:run` ou reconstruindo e executando o container Docker). A aplicação não armazena um cache em disco; ela reconstrói a base de conhecimento em memória a cada inicialização, garantindo que os dados mais recentes sejam carregados.
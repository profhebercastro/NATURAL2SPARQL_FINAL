# Natural2SPARQL V4 💬 ➡️ SPARQL

[![Java](https://img.shields.io/badge/Java-17-blue.svg?style=for-the-badge&logo=openjdk)](https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html)
[![Spring](https://img.shields.io/badge/Spring_Boot-3.2-green.svg?style=for-the-badge&logo=spring)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.9-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/downloads/release/python-390/)
[![Flask](https://img.shields.io/badge/Flask-black.svg?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Apache Jena](https://img.shields.io/badge/Apache-Jena-orange.svg?style=for-the-badge&logo=apache)](https://jena.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-gray.svg?style=for-the-badge&logo=docker)](https://www.docker.com/)

Um sistema poliglota que traduz perguntas em linguagem natural (Português) em consultas **SPARQL**, executando-as contra uma base de conhecimento RDF para obter respostas precisas. O framework utiliza uma arquitetura flexível baseada em templates e placeholders genéricos para permitir fácil adaptação a diferentes domínios.

---

### ✨ **[Acesse a Demonstração Online](https://natural2sparql-v4.onrender.com)** ✨

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

*   **🗣️ Interface em Linguagem Natural**: Permite que usuários façam perguntas sobre um dominio de conhecimento sem precisar conhecer a sintaxe SPARQL.
*   **⚙️ Arquitetura de Microserviços**: Combina a robustez do **Java/Spring Boot** para o backend principal e gerenciamento da ontologia com um microserviço **Python/Flask** dedicado ao Processamento de Linguagem Natural (NLP).
*   **🧠 Povoamento da Base de Conhecimento**: Na inicialização, o sistema lê dados de planilhas `.xlsx` e popula dinamicamente uma ontologia RDF em memória usando Apache Jena.
*   **🧩 Motor Baseado em Templates Genéricos**: Utiliza um sistema de substituição em duas fases. Os templates SPARQL contêm placeholders abstratos (`P1`, `S1`), que são mapeados para termos RDF específicos de um domínio através de um arquivo de propriedades. Isso permite que a lógica de consulta seja reutilizada em diferentes ontologias.
*   **☁️ Pronto para a Nuvem**: Containerizado com **Docker** usando um build multi-stage eficiente e configurado para deploy contínuo na plataforma **Render**.

## ⚙️ Tecnologias Utilizadas

| Categoria                      | Tecnologia                                                                                             | Propósito                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Backend & Orquestração**     | `Java 17`, `Spring Boot 3.2`, `Apache Jena`, `Apache POI`                                              | Servidor principal, manipulação da ontologia, leitura de Excel, comunicação HTTP   |
| **Processamento de Linguagem** | `Python 3.9`, `Flask`, `Gunicorn`, `scikit-learn`                                                      | Microserviço de NLP, similaridade semântica (TF-IDF), extração de entidades        |
| **Frontend**                   | `HTML5`, `CSS3`, `JavaScript` (vanilla com API `fetch`)                                                | Interface de usuário com fluxo de dois botões (Gerar/Executar)                     |
| **Base de Dados & Config.**    | `RDF/TTL` (esquema), `.xlsx` (dados), `.properties` (mapeamento), `.json` (dicionários)                | Armazenamento do conhecimento, dos dados e das configurações do framework          |
| **DevOps & Build**             | `Docker` (build multi-stage), `Maven`                                                                  | Containerização, gerenciamento de dependências e build do projeto Java             |

## 🏗️ Arquitetura e Fluxo de Dados

O sistema opera com uma arquitetura desacoplada onde o serviço Java orquestra o fluxo, consultando o serviço Python para obter inteligência de NLP e, em seguida, construindo a consulta final.

1.  **Interface do Usuário**: O usuário digita uma pergunta e clica em `GERAR CONSULTA`.
2.  **Requisição ao Backend Java**: O Frontend envia a pergunta via `POST` para o endpoint `/gerar_consulta`.
3.  **Chamada ao Serviço de NLP**: O `SPARQLProcessor` (Java) faz uma chamada HTTP para o microserviço Python/Flask, enviando a pergunta.
4.  **Processamento em Python (`nlp_controller.py`)**:
    *   **Seleção do Template**: Usa **TF-IDF** e **Similaridade de Cosseno** para comparar a pergunta do usuário com a lista em `Reference_questions.txt` e determinar o `templateId`.
    *   **Extração de Entidades**: Usa `empresa_nome_map.json` e `setor_map.json` para extrair entidades como nome, ticker ou setor.
    *   **Identificação da Métrica**: Usa `Thesaurus.json` para identificar a métrica pedida (ex: "preço de fechamento") e retorna sua chave (ex: `metrica.preco_fechamento`).
    *   **Resposta JSON**: Devolve um objeto JSON contendo o `templateId` e as `entidades` (incluindo a chave da métrica).
5.  **Geração da Consulta SPARQL (Java)**:
    *   **Fase 1 (Substituição de Entidades)**: O `SPARQLProcessor` recebe o JSON, carrega o template e substitui os placeholders de entidade (`#ENTIDADE_NOME#`, `#DATA#`) e o de métrica (`#VALOR_DESEJADO#`).
    *   **Fase 2 (Substituição de Placeholders RDF)**: O `PlaceholderService` recebe a query semi-pronta e, usando o `placeholders.properties`, substitui os placeholders genéricos (`P1`, `S1`, etc.) pelos termos RDF correspondentes.
    *   **Retorno**: A consulta SPARQL final é retornada para o Frontend.
6.  **Execução da Consulta**: O usuário clica em `Executar`. O Frontend envia a query para o endpoint `/executar_query`. O `Ontology.java` a executa no grafo em memória e retorna o resultado.
7.  **Resposta Final**: O resultado é formatado e exibido para o usuário.

## 🚀 Como Executar o Projeto

### Pré-requisitos

*   `Java JDK 17+` & `Apache Maven 3.6+`
*   `Docker` & `Docker Compose`

---

<details>
<summary><strong>Opção Recomendada: Execução com Docker Compose</strong></summary>

A maneira mais fácil e que melhor simula o ambiente de produção é usar o `Dockerfile` que já está no projeto.

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/hebercastro79/Natural2SPARQL_V4.git
    cd Natural2SPARQL_V4
    ```

2.  **Construa a imagem Docker:**
    O `Dockerfile` multi-stage cuida do build do Java, da configuração do Python e da instalação de todas as dependências.
    ```bash
    docker build -t natural2sparql-v4 .
    ```

3.  **Execute o container:**
    Um script `start.sh` (executado pelo Dockerfile) se encarrega de iniciar os dois processos (Java e Python) dentro do container.
    ```bash
    docker run -p 8080:8080 -it natural2sparql-v4
    ```

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

## 🕹️ Como Usar a Aplicação

1.  Acesse a interface web: [**Demo Online**](https://natural2sparql-v4.onrender.com) ou `http://localhost:8080`.
2.  Digite sua pergunta no campo de texto.
    > **Exemplos de perguntas que o sistema entende:**
    > *   `Qual foi o preço de fechamento da ação da CSN em 08/05/2023?`
    > *   `Qual foi o preço de abertura da CBAV3 em 08/05/2023?`
    > *   `Qual o código de negociação da ação da Gerdau?`
    > *   `Quais são as ações do setor eletrico?`
    > *   `Qual foi o volume negociado nas ações do setor bancário em 05/05/2023?`
3.  Clique em **GERAR CONSULTA**. A consulta SPARQL aparecerá.
4.  Clique em **Executar** para ver o resultado.

## 🗂️ Estrutura de Arquivos Essenciais

*   `nlp/`: Pasta dedicada que contém o microserviço Python e todos os seus arquivos de configuração (`nlp_controller.py`, `Thesaurus.json`, etc.).
*   `src/main/resources/`: Contém os recursos do backend Java.
    *   `ontologiaB3_com_inferencia.ttl`: O esqueleto da ontologia.
    *   `Datasets/`: Contém as planilhas com dados brutos.
    *   `Templates/`: Contém os arquivos de template SPARQL com placeholders genéricos.
    *   `placeholders.properties`: Arquivo crucial que mapeia os placeholders genéricos para os termos RDF específicos do domínio.
*   `Dockerfile`: Define como a aplicação poliglota é empacotada em um container.
*   `start.sh`: Script que orquestra a inicialização dos serviços Java e Python dentro do container.

## 🔄 Atualizando os Dados

1.  **Adicione/Substitua Planilhas**: Coloque os novos arquivos `.xlsx` na pasta `src/main/resources/Datasets/`.
2.  **Atualize os Mapas de Entidades**: Se novas empresas ou setores foram adicionados, atualize `nlp/empresa_nome_map.json` e `nlp/setor_map.json`.
3.  **Reinicie a Aplicação**: O `Dockerfile` está configurado para forçar a reconstrução do cache da ontologia a cada novo deploy, garantindo que os dados mais recentes sejam sempre carregados.
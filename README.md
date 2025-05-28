# Natural2SPARQL

Natural2SPARQL é um sistema que traduz perguntas em linguagem natural (português) sobre o mercado de ações da B3 em consultas SPARQL. Essas consultas são executadas contra uma base de conhecimento em RDF para fornecer respostas aos usuários através de uma interface web.

## Funcionalidades Principais

*   **Tradução de Linguagem Natural para SPARQL**: Converte perguntas como "Qual o preço de fechamento da PETR4 em 10/05/2023?" em consultas SPARQL formais.
*   **Processamento de Linguagem Natural (PLN)**: Utiliza spaCy e FuzzyWuzzy para identificar a intenção do usuário, extrair entidades relevantes (empresas, códigos de ação, datas, setores) e normalizá-las.
*   **Base de Conhecimento Ontológica**: Utiliza uma ontologia (RDF/TTL) populada com dados da B3 (informações de empresas, setores, dados históricos de pregões).
*   **Consultas Baseadas em Templates**: Emprega um sistema de templates SPARQL que são preenchidos dinamicamente com as entidades extraídas.
*   **Interface Web**: Fornece uma interface de usuário simples baseada em Flask para interação.
*   **Deploy em Nuvem**: Configurado para deploy na plataforma Render usando Docker.

## Tecnologias Utilizadas

*   **Backend**:
    *   Java 17
    *   Apache Jena (para manipulação da ontologia e execução de SPARQL)
    *   Spring Boot (para empacotamento da aplicação Java)
*   **Processamento de Linguagem Natural**:
    *   Python 3.9
    *   spaCy (tokenização, NER, modelos de linguagem)
    *   FuzzyWuzzy (correspondência de strings por similaridade)
*   **Frontend/Gateway**:
    *   Python 3.9
    *   Flask (framework web)
*   **Base de Dados**:
    *   RDF/TTL (para a base de conhecimento)
    *   Arquivos Excel (`.xlsx`) como fonte primária dos dados.
*   **DevOps**:
    *   Docker
    *   Render (para deploy)
*   **Outros**:
    *   Pandas (para manipulação de dados em scripts Python)

## Arquitetura do Sistema

O sistema opera com os seguintes componentes principais:

1.  **Interface do Usuário (Web App - Flask)**: Recebe a pergunta do usuário.
2.  **Orquestrador Java (Spring Boot App)**:
    *   Recebe a pergunta do Web App.
    *   Invoca o **Processador de PLN Python**.
3.  **Processador de PLN (Script Python)**:
    *   Analisa a pergunta usando spaCy e `perguntas_de_interesse.txt`.
    *   Identifica o template SPARQL e extrai entidades (empresas, datas, etc.).
    *   Normaliza entidades usando `empresa_nome_map.json`.
    *   Retorna o ID do template e as entidades para o Orquestrador Java.
4.  **Construtor de Consultas (Java - parte do Orquestrador)**:
    *   Seleciona o template SPARQL correspondente.
    *   Preenche o template com as entidades extraídas.
5.  **Motor de Consulta (Java - Apache Jena)**:
    *   Executa a consulta SPARQL contra a ontologia (`ontologiaB3_com_inferencia.ttl`).
6.  **Ontologia (RDF/TTL)**: Base de conhecimento com dados da B3.
7.  O resultado é retornado pela cadeia até a Interface do Usuário.

*(Veja o Diagrama de Arquitetura abaixo para uma representação visual)*

## Configuração e Instalação

### Pré-requisitos

*   Java JDK 17 ou superior
*   Apache Maven (para construir o projeto Java)
*   Python 3.9 ou superior
*   `pip` (gerenciador de pacotes Python)
*   Docker (opcional, para rodar em container ou para deploy)

### Passos de Instalação Local

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/hebercastro79/Natural2SPARQL_2025.git
    cd Natural2SPARQL_2025
    ```

2.  **Prepare os dados e mapeamentos (se necessário):**
    *   O arquivo `empresa_nome_map.json` é crucial e é gerado a partir de `src/main/resources/Templates/Informacoes_Empresas.xlsx`. Se este Excel for atualizado, regenere o mapa:
        ```bash
        python src/main/resources/generate_map.py
        ```
    *   **Importante**: Os arquivos de ontologia (`.ttl`) são populados a partir dos arquivos Excel em `src/main/resources/Datasets/` e `src/main/resources/Templates/Informacoes_Empresas.xlsx`. **Este projeto não inclui os scripts para converter Excel em TTL.** Se os dados nos Excels mudarem, os arquivos TTL precisam ser regenerados manualmente ou com ferramentas externas (não fornecidas aqui) e substituídos na pasta `src/main/resources/`.

3.  **Construa a aplicação Java:**
    ```bash
    ./mvnw clean package
    # ou mvn clean package se você tem Maven instalado globalmente
    ```
    Isso gerará o arquivo `target/Natural2SPARQL-0.0.1-SNAPSHOT.jar`.

4.  **Instale as dependências Python e baixe o modelo spaCy:**
    ```bash
    pip install -r requirements.txt
    python -m spacy download pt_core_news_lg
    ```

5.  **Execute a aplicação web:**
    ```bash
    python web_app.py
    ```
    A aplicação estará acessível em `http://127.0.0.1:8080`.

### Executando com Docker

1.  **Construa a imagem Docker:**
    (Certifique-se que o passo 2 e 3 da instalação local foram executados para ter o `.jar` e `empresa_nome_map.json` atualizados antes de construir a imagem, ou adapte o Dockerfile para incluir esses passos).
    ```bash
    docker build -t natural2sparql .
    ```

2.  **Execute o container Docker:**
    ```bash
    docker run -p 8080:8080 natural2sparql
    ```
    A aplicação estará acessível em `http://127.0.0.1:8080`.

## Como Usar

1.  Acesse a interface web (localmente em `http://127.0.0.1:8080` ou no link de deploy do Render: [https://natural2sparql-master-1.onrender.com](https://natural2sparql-master-1.onrender.com)).
2.  Digite sua pergunta no campo de texto. O sistema suporta perguntas como:
    *   Preço de fechamento de uma empresa em uma data:
        *   `Qual foi o preço de fechamento da ação da CSN em 08/05/2023?`
    *   Preço de abertura de um código de ação em uma data:
        *   `Qual foi o preço de abertura da CBAV3 em 08/05/2023?`
    *   Código de negociação de uma empresa:
        *   `Qual o código de negociação da ação da Gerdau?`
    *   Ações de um setor específico:
        *   `Quais são as ações do setor eletrico?`
3.  Clique em "Perguntar".
4.  A resposta será exibida abaixo do campo de pergunta.

## Manutenção de Dados

*   **Mapeamento Empresa-Nome (`empresa_nome_map.json`)**: Se `src/main/resources/Templates/Informacoes_Empresas.xlsx` for modificado, execute `python src/main/resources/generate_map.py` para atualizar `empresa_nome_map.json`.
*   **Ontologia (`.ttl`)**: Se os dados em `src/main/resources/Datasets/dados_novos_*.xlsx` ou `src/main/resources/Templates/Informacoes_Empresas.xlsx` forem atualizados, os arquivos `.ttl` (especialmente `ontologiaB3.ttl` e, por consequência, `ontologiaB3_com_inferencia.ttl`) **DEVEM** ser regenerados. O processo para esta conversão Excel-para-RDF não está incluído neste repositório e deve ser realizado externamente. Após a regeneração, substitua os arquivos antigos em `src/main/resources/`. Se estiver usando Docker, reconstrua a imagem.
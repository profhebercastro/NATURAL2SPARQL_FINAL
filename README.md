# Natural2SPARQL_2025 💬 ➡️  SPARQL

[![Java](https://img.shields.io/badge/Java-17-blue.svg?style=for-the-badge&logo=openjdk)](https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html)
[![Python](https://img.shields.io/badge/Python-3.9-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/downloads/release/python-390/)
[![Spring](https://img.shields.io/badge/Spring_Boot-3-green.svg?style=for-the-badge&logo=spring)](https://spring.io/projects/spring-boot)
[![Apache Jena](https://img.shields.io/badge/Apache-Jena-orange.svg?style=for-the-badge&logo=apache)](https://jena.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-gray.svg?style=for-the-badge&logo=docker)](https://www.docker.com/)

Um sistema que traduz perguntas em linguagem natural (Português) sobre o mercado de ações em consultas **SPARQL**, executando-as contra uma base de conhecimento RDF para obter respostas precisas.

---

### ✨ **[Acesse a Demonstração Online](https://natural2sparql-2025.onrender.com)** ✨



---

## 📜 Índice

*   [Funcionalidades Principais](#-funcionalidades-principais)
*   [Tecnologias Utilizadas](#-tecnologias-utilizadas)
*   [Arquitetura e Fluxo de Dados](#-arquitetura-e-fluxo-de-dados)
*   [Como Executar o Projeto](#-como-executar-o-projeto)
*   [Como Usar a Aplicação](#-como-usar-a-aplicação)
*   [Atualizando os Dados](#-atualizando-os-dados)

## ✨ Funcionalidades Principais

*   **🗣️ Interface em Linguagem Natural**: Permite que usuários façam perguntas complexas sobre uma determinada ontologia de domínio sem saber SPARQL.
*   **⚙️ Orquestração Híbrida**: Combina o poder do **Java/Spring** para robustez e gerenciamento de ontologias com a simplicidade do **Python** para processamento de linguagem.
*   **🏗️ Construção Automática da Ontologia**: Na primeira inicialização, o sistema lê arquivos `.xlsx` e constrói a base de conhecimento RDF, incluindo um cache com inferências para startups futuras ultrarrápidas.
*   **🧩 Motor Baseado em Templates**: Arquitetura extensível que permite adicionar suporte a novos tipos de perguntas apenas criando um novo arquivo de template, sem alterar o código Java principal.
*   **☁️ Pronto para a Nuvem**: Containerizado com **Docker** e configurado para deploy contínuo na plataforma **Render**.

## ⚙️ Tecnologias Utilizadas

| Categoria                      | Tecnologia                                                                                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ |
| **Backend & Orquestração**     | `Java 17`, `Spring Boot 3`, `Apache Jena`, `Apache POI`                                                  |
| **Processamento de Linguagem** | `Python 3.9` (com bibliotecas padrão `difflib`, `re`, `json`)                                          |
| **Frontend**                   | `HTML5`, `CSS3`, `JavaScript` (vanilla)                                                                |
| **Base de Dados**              | `RDF/TTL` (para a ontologia), `.xlsx` (como fonte de dados primária)                                     |
| **DevOps & Build**             | `Docker` (build multi-stage), `Maven`                                                                  |

## 🏗️ Arquitetura e Fluxo de Dados

<details>
<summary><strong>Clique para expandir e ver o fluxo detalhado de uma requisição</strong></summary>

1.  **Frontend**: O usuário digita "Qual o preço de fechamento da CSN em 08/05/2023?" e clica em `GERAR CONSULTA`.
2.  **API Call 1 (`/gerar_consulta`)**: A pergunta é enviada para o backend Java.
3.  **Java (`QuestionProcessor`)**: Invoca o script `pln_processor.py`.
4.  **Python (`pln_processor.py`)**:
    *   **Classifica a Intenção**: Compara a pergunta com os padrões em `perguntas_de_interesse.txt` e seleciona `Template_1A`.
    *   **Extrai Entidades**: Identifica "preço de fechamento", "CSN" e "08/05/2023".
    *   **Normaliza Dados**: Usa `empresa_nome_map.json` para converter "CSN" no nome canônico "CSN MINERAÇÃO S.A.".
    *   **Retorna JSON**: Devolve `{"template_nome": "Template_1A", "mapeamentos": {...}}` para o Java.
5.  **Java (`QuestionProcessor`)**:
    *   Lê o conteúdo de `Template_1A.txt`.
    *   Substitui os placeholders (`#ENTIDADE_NOME#`, `#DATA#`, etc.) com os valores recebidos, montando a consulta SPARQL.
    *   Envia a consulta gerada de volta ao Frontend.
6.  **Frontend**: Exibe a consulta SPARQL e habilita o botão `Executar`.
7.  **API Call 2 (`/executar_query`)**: O usuário clica em `Executar`, e a consulta SPARQL é enviada para o backend.
8.  **Java (`Ontology`)**: O componente de ontologia executa a consulta SPARQL contra o modelo RDF em memória usando **Apache Jena**.
9.  **Resposta Final**: O resultado é formatado de forma amigável e enviado ao Frontend para exibição.

</details>

## 🚀 Como Executar o Projeto

### Pré-requisitos

*   `Java JDK 17+`
*   `Apache Maven 3.6+`
*   `Python 3.9+`
*   `Docker` (opcional, para execução em container)

---

<details>
<summary><strong>Opção 1: Execução Local (Recomendado para desenvolvimento)</strong></summary>

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/hebercastro79/Natural2SPARQL_2025.git
    cd Natural2SPARQL_2025
    ```

2.  **Instale as dependências Python:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Execute a aplicação com Maven:**
    ```bash
    ./mvnw spring-boot:run
    ```
    > **Nota:** Na primeira execução, o sistema irá construir a base de conhecimento a partir dos arquivos Excel, o que pode levar alguns segundos. As inicializações seguintes serão quase instantâneas.

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

<details>
<summary><strong>Opção 2: Execução com Docker</strong></summary>

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/hebercastro79/Natural2SPARQL_2025.git
    cd Natural2SPARQL_2025
    ```

2.  **Construa a imagem Docker:**
    O `Dockerfile` multi-stage cuida de todo o processo de build do Java e da configuração do Python.
    ```bash
    docker build -t natural2sparql .
    ```

3.  **Execute o container:**
    ```bash
    docker run -e PORT=8080 -p 8080:8080 -it natural2sparql
    ```

4.  Acesse a aplicação em [**http://localhost:8080**](http://localhost:8080).

</details>

## 🕹️ Como Usar a Aplicação

1.  Acesse a interface web: [**Demo Online**](https://natural2sparql-2025.onrender.com) ou `http://localhost:8080`.
2.  Digite sua pergunta no campo de texto.

    > **Exemplos de perguntas que você pode fazer:**
    > *   `Qual foi o preço de fechamento da ação da CSN em 08/05/2023?`
    > *   `Qual o código de negociação da ação da Gerdau?`
    > *   `Quais são as ações do setor eletrico?`
    > *   `Qual foi o volume negociado nas ações do setor bancário em 05/05/2023?`

3.  Clique em **GERAR CONSULTA**. A consulta SPARQL correspondente aparecerá.
4.  Clique em **Executar** para ver o resultado final.

## 🔄 Atualizando os Dados

O sistema é projetado para ser facilmente atualizável com novos dados.

1.  **Adicione/Substitua Planilhas**: Coloque os novos arquivos `.xlsx` nas pastas `src/main/resources/Datasets/` (dados de pregões) ou `src/main/resources/Templates/` (informações de empresas).
2.  **Limpe o Cache Antigo**: A forma mais segura de forçar a reconstrução da base de conhecimento é executar o comando `clean` do Maven, que apaga a pasta `target/`.
    ```bash
    ./mvnw clean
    ```
3.  **Reinicie a Aplicação**: Execute o projeto novamente (com `mvn spring-boot:run` ou reconstruindo a imagem Docker). O sistema detectará a ausência do cache e irá gerar um novo a partir dos dados atualizados.
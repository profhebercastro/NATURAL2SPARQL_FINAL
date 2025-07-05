package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.example.Programa_heber.service.SPARQLProcessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@SpringBootApplication
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    private final SPARQLProcessor sparqlProcessor;
    private final Ontology ontology;

    @Autowired
    public Main(SPARQLProcessor sparqlProcessor, Ontology ontology) {
        this.sparqlProcessor = sparqlProcessor;
        this.ontology = ontology;
    }

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }
    
    @PostMapping("/gerar_consulta")
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        // Esta parte já está correta e não precisa de alterações.
        String pergunta = request.getPergunta();
        ProcessamentoDetalhadoResposta resposta = new ProcessamentoDetalhadoResposta();

        if (pergunta == null || pergunta.trim().isEmpty()) {
            resposta.setErro("A pergunta não pode estar vazia.");
            return ResponseEntity.badRequest().body(resposta);
        }

        logger.info("Recebida requisição para GERAR consulta para: '{}'", pergunta);
        try {
            resposta = sparqlProcessor.generateSparqlQuery(pergunta);
            if (resposta.getErro() != null) {
                return ResponseEntity.internalServerError().body(resposta);
            }
            return ResponseEntity.ok(resposta);
        } catch (Exception e) {
            logger.error("Erro no endpoint /gerar_consulta: {}", e.getMessage(), e);
            resposta.setErro("Erro interno ao gerar a consulta: " + e.getMessage());
            return ResponseEntity.internalServerError().body(resposta);
        }
    }

    /**
     * Endpoint para EXECUTAR uma consulta SPARQL.
     * AGORA COM LÓGICA DE FORMATAÇÃO ROBUSTA.
     */
    @PostMapping("/executar_query")
    public ResponseEntity<Map<String, String>> executarQuery(@RequestBody ExecuteQueryRequest request) {
        String sparqlQuery = request.getSparqlQuery();
        
        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("erro", "A consulta SPARQL não pode estar vazia."));
        }

        logger.info("Recebida requisição para EXECUTAR a consulta.");
        try {
            // A classe Ontology já retorna uma lista de mapas, que é uma ótima estrutura.
            List<Map<String, String>> resultList = ontology.executeQuery(sparqlQuery);

            // Chamamos nosso novo método auxiliar para formatar essa lista em uma string
            String formattedResult = formatResultSet(resultList);
            
            // Retornamos a string formatada no campo "resultado" do JSON
            return ResponseEntity.ok(Map.of("resultado", formattedResult));

        } catch (Exception e) {
            logger.error("Erro no endpoint /executar_query: {}", e.getMessage(), e);
            return ResponseEntity.internalServerError().body(Map.of("erro", "Erro interno ao executar a consulta."));
        }
    }

    /**
     * NOVO MÉTODO AUXILIAR: Formata uma lista de resultados SPARQL em uma string de texto legível.
     * Consegue lidar com resultados vazios, uma linha/uma coluna, ou múltiplas linhas/colunas.
     * @param resultList A lista de resultados vinda da classe Ontology.
     * @return Uma string formatada para ser exibida na <textarea> do frontend.
     */
    private String formatResultSet(List<Map<String, String>> resultList) {
        if (resultList == null || resultList.isEmpty()) {
            return "A consulta foi executada com sucesso, mas não retornou resultados.";
        }

        // Caso especial: uma única linha e uma única coluna (ex: "Qual o preço...")
        // Extrai apenas o valor para uma resposta mais limpa.
        if (resultList.size() == 1 && resultList.get(0).size() == 1) {
            String singleValue = resultList.get(0).values().iterator().next();
            logger.info("Resultado de valor único extraído da consulta: {}", singleValue);
            return singleValue;
        }

        // Caso geral: múltiplas linhas ou colunas. Formata como uma tabela de texto.
        StringBuilder sb = new StringBuilder();
        
        // Constrói o cabeçalho da tabela com os nomes das variáveis
        String header = String.join("\t | \t", resultList.get(0).keySet());
        sb.append(header).append("\n");
        sb.append("=".repeat(header.length() + (resultList.get(0).size() * 5))).append("\n");

        // Constrói as linhas de dados
        for (Map<String, String> row : resultList) {
            String line = row.values().stream().collect(Collectors.joining("\t | \t"));
            sb.append(line).append("\n");
        }
        
        return sb.toString();
    }
}
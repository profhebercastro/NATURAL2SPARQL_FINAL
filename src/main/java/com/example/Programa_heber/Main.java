package com.example.Programa_heber;

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

import java.util.HashMap;
import java.util.List;
import java.util.Map;

// Removi a exclusão do DataSource, pois geralmente não é necessária
// a menos que você tenha dependências de banco de dados que não quer configurar.
@SpringBootApplication
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    // Injeção de dependências via construtor (melhor prática)
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
    
    // CORREÇÃO: Removendo modelos de requisição customizados para simplicidade
    // e para corresponder ao que a interface (JavaScript) provavelmente envia.

    /**
     * Endpoint para gerar a consulta SPARQL a partir de uma pergunta em linguagem natural.
     * Recebe: {"pergunta": "Qual o preço..."}
     * Retorna: {"sparqlQuery": "SELECT..."}
     */
    @PostMapping("/api/generate-query")
    public ResponseEntity<Map<String, String>> gerarConsulta(@RequestBody Map<String, String> request) {
        String pergunta = request.get("pergunta");
        if (pergunta == null || pergunta.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "A pergunta não pode estar vazia."));
        }

        logger.info("Recebida requisição para GERAR consulta para: '{}'", pergunta);
        try {
            // Chama o novo método do SPARQLProcessor que retorna a string da query
            String generatedQuery = sparqlProcessor.generateSparqlQuery(pergunta);
            
            // Verifica se o processador retornou um erro
            if (generatedQuery.startsWith("Erro")) {
                 return ResponseEntity.internalServerError().body(Map.of("error", generatedQuery));
            }

            // Cria um mapa para a resposta JSON
            Map<String, String> response = new HashMap<>();
            response.put("sparqlQuery", generatedQuery);

            return ResponseEntity.ok(response);
        } catch (Exception e) {
            logger.error("Erro no endpoint /api/generate-query: {}", e.getMessage(), e);
            return ResponseEntity.internalServerError().body(Map.of("error", "Erro interno ao gerar a consulta."));
        }
    }

    /**
     * Endpoint para executar uma consulta SPARQL.
     * Recebe: {"sparqlQuery": "SELECT..."}
     * Retorna: {"resultado": [{...}, {...}]}
     */
    @PostMapping("/api/execute-query")
    public ResponseEntity<Map<String, Object>> executarQuery(@RequestBody Map<String, String> request) {
        String sparqlQuery = request.get("sparqlQuery");
        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "A consulta SPARQL não pode estar vazia."));
        }

        logger.info("Recebida requisição para EXECUTAR a consulta:\n{}", sparqlQuery);
        try {
            // Chama o método de execução que está na classe Ontology
            List<Map<String, String>> result = ontology.executeQuery(sparqlQuery);

            // Monta uma resposta JSON estruturada
            Map<String, Object> response = new HashMap<>();
            response.put("resultado", result);

            return ResponseEntity.ok(response);
        } catch (Exception e) {
            logger.error("Erro no endpoint /api/execute-query: {}", e.getMessage(), e);
            return ResponseEntity.internalServerError().body(Map.of("error", "Erro interno ao executar a consulta."));
        }
    }
}
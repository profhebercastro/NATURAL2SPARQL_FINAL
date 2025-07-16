package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.example.Programa_heber.service.SPARQLProcessor;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// --- INÍCIO DAS IMPORTAÇÕES CORRIGIDAS ---
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.ArrayList; 
// --- FIM DAS IMPORTAÇÕES CORRIGIDAS ---


@SpringBootApplication
@RestController
@RequestMapping("/api")
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    @Autowired
    private SPARQLProcessor sparqlProcessor;
    
    @Autowired
    private Ontology ontology;

    @Autowired
    private ObjectMapper objectMapper;

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }
    
    @PostMapping("/processar")
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        String pergunta = request.getPergunta();
        
        if (pergunta == null || pergunta.trim().isEmpty()) {
            ProcessamentoDetalhadoResposta erro = new ProcessamentoDetalhadoResposta();
            erro.setErro("A pergunta não pode estar vazia.");
            return ResponseEntity.badRequest().body(erro);
        }

        logger.info("Recebida requisição para GERAR consulta para: '{}'", pergunta);
        try {
            ProcessamentoDetalhadoResposta resposta = sparqlProcessor.generateSparqlQuery(pergunta);
            if (resposta.getErro() != null) {
                return ResponseEntity.status(500).body(resposta);
            }
            return ResponseEntity.ok(resposta);
        } catch (Exception e) {
            logger.error("Erro no endpoint /processar: {}", e.getMessage(), e);
            ProcessamentoDetalhadoResposta erro = new ProcessamentoDetalhadoResposta();
            erro.setErro("Erro interno ao gerar a consulta: " + e.getMessage());
            return ResponseEntity.status(500).body(erro);
        }
    }

    @PostMapping("/executar")
    public ResponseEntity<String> executarQuery(@RequestBody ExecuteQueryRequest request) {
        String sparqlQuery = request.getQuery();
        
        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body("{\"error\": \"A consulta SPARQL não pode estar vazia.\"}");
        }

        logger.info("Recebida requisição para EXECUTAR a consulta.");
        try {
            List<Map<String, String>> bindings = ontology.executeQuery(sparqlQuery);

            Map<String, Object> head = new HashMap<>();
            List<String> vars = bindings.isEmpty() ? Collections.emptyList() : new ArrayList<>(bindings.get(0).keySet());
            head.put("vars", vars);

            Map<String, Object> results = new HashMap<>();
            
            List<Map<String, Object>> formattedBindings = new ArrayList<>();
            for(Map<String, String> row : bindings) {
                Map<String, Object> newRow = new HashMap<>();
                for(Map.Entry<String, String> entry : row.entrySet()) {
                    Map<String, String> valueMap = new HashMap<>();
                    valueMap.put("type", "literal");
                    valueMap.put("value", entry.getValue());
                    newRow.put(entry.getKey(), valueMap);
                }
                formattedBindings.add(newRow);
            }
            results.put("bindings", formattedBindings);

            Map<String, Object> finalJsonResponse = new HashMap<>();
            finalJsonResponse.put("head", head);
            finalJsonResponse.put("results", results);

            String resultadoJson = objectMapper.writeValueAsString(finalJsonResponse);
            
            return ResponseEntity.ok(resultadoJson);

        } catch (JsonProcessingException e) {
             logger.error("Erro ao serializar resultado para JSON: {}", e.getMessage(), e);
            return ResponseEntity.status(500).body("{\"error\": \"Erro ao formatar o resultado da consulta.\"}");
        } 
        catch (Exception e) {
            logger.error("Erro no endpoint /executar: {}", e.getMessage(), e);
            return ResponseEntity.status(500).body("{\"error\": \"Erro interno ao executar a consulta: " + e.getMessage() + "\"}");
        }
    }
}```

### **O Que Foi Corrigido**

Adicionei as seguintes linhas no topo do arquivo `Main.java`, logo após a declaração `package`:

```java
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.ArrayList; 
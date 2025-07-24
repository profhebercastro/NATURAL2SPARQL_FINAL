package com.example.Program;

import com.example.Program.model.ExecuteQueryRequest;
import com.example.Program.model.PerguntaRequest;
import com.example.Program.model.ProcessamentoDetalhadoResposta;
import com.example.Program.ontology.Ontology;
import com.example.Program.service.SPARQLProcessor;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.jena.rdf.model.Model;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.io.StringWriter;
import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.text.NumberFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

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
        String tipoMetrica = request.getTipoMetrica(); // Pega o tipo de métrica da requisição

        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body("{\"error\": \"A consulta SPARQL não pode estar vazia.\"}");
        }
        logger.info("Executando query. Tipo de métrica recebido: {}", tipoMetrica);
        try {
            List<Map<String, String>> bindings = ontology.executeQuery(sparqlQuery);
            Map<String, Object> head = new HashMap<>();
            List<String> vars = bindings.isEmpty() ? Collections.emptyList() : new ArrayList<>(bindings.get(0).keySet());
            head.put("vars", vars);

            Map<String, Object> results = new HashMap<>();
            
            // --- Listas para formatação ---
            List<String> priceVarNames = List.of("precoMaximo", "precoMinimo", "precoAbertura", "precoFechamento", "precoMedio");
            List<String> largeNumberVarNames = List.of("volume", "volumeIndividual", "quantidade", "totalNegocios");
            
            // --- Formatadores ---
            NumberFormat currencyFormatter = DecimalFormat.getCurrencyInstance(new Locale("pt", "BR"));
            NumberFormat integerFormatter = DecimalFormat.getIntegerInstance(new Locale("pt", "BR"));
            DecimalFormat percentageFormatter = new DecimalFormat("#,##0.00'%'", new DecimalFormatSymbols(new Locale("pt", "BR")));
            DecimalFormatSymbols symbols = new DecimalFormatSymbols();
            symbols.setGroupingSeparator('.');
            DecimalFormat volumeFormatter = new DecimalFormat("'R$ ' #,##0", symbols);

            List<Map<String, Object>> formattedBindings = new ArrayList<>();
            for(Map<String, String> row : bindings) {
                Map<String, Object> newRow = new HashMap<>();
                for(Map.Entry<String, String> entry : row.entrySet()) {
                    Map<String, String> valueMap = new HashMap<>();
                    valueMap.put("type", "literal");

                    String currentValue = entry.getValue();
                    String varName = entry.getKey();
                    String formattedValue = currentValue; 

                    try {
                        double numericValue = Double.parseDouble(currentValue);

                        // Lógica de formatação baseada no contexto (tipoMetrica) e no nome da variável
                        if (varName.equals("resultadoCalculado") && tipoMetrica != null) {
                            if (tipoMetrica.contains("perc")) { // Ex: "variacao_perc", "intervalo_perc"
                                formattedValue = percentageFormatter.format(numericValue);
                            } else { // Assume que outros cálculos são valores monetários (variacao_abs, etc)
                                formattedValue = currencyFormatter.format(numericValue);
                            }
                        } else if (priceVarNames.contains(varName)) {
                            formattedValue = currencyFormatter.format(numericValue);
                        } else if (largeNumberVarNames.contains(varName)) {
                            if (varName.toLowerCase().contains("volume")) {
                                formattedValue = volumeFormatter.format(numericValue);
                            } else {
                                formattedValue = integerFormatter.format(numericValue);
                            }
                        }
                    } catch (NumberFormatException e) {
                        // Mantém o valor original se não for número (ex: um ticker)
                    }
                    
                    valueMap.put("value", formattedValue);
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
        } catch (Exception e) {
            logger.error("Erro no endpoint /executar: {}", e.getMessage(), e);
            return ResponseEntity.status(500).body("{\"error\": \"Erro interno ao executar a consulta: " + e.getMessage() + "\"}");
        }
    }

    @GetMapping("/debug/get-inferred-ontology")
    public ResponseEntity<String> getInferredOntology() {
        logger.info("Recebida requisição de DEBUG para obter a ontologia inferida.");
        Model inferredModel = ontology.getInferredModel();
        if (inferredModel == null) {
            logger.warn("Tentativa de acessar modelo inferido, mas ele é nulo.");
            return ResponseEntity.status(500).body("Erro: O modelo inferido ainda não foi gerado ou está nulo.");
        }
        StringWriter out = new StringWriter();
        inferredModel.write(out, "TURTLE");
        String ontologyAsString = out.toString();
        HttpHeaders headers = new HttpHeaders();
        headers.add(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=ontology_inferred_from_render.ttl");
        headers.add(HttpHeaders.CONTENT_TYPE, MediaType.TEXT_PLAIN_VALUE);
        logger.info("Enviando ontologia inferida como anexo para download.");
        return ResponseEntity.ok()
                .headers(headers)
                .body(ontologyAsString);
    }
}

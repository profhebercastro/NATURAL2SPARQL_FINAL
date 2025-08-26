package com.example.Program.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

@Component
public class Ontology {

    private static final Logger logger = LoggerFactory.getLogger(Ontology.class);
    private Model model;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();
    private static final String PRECOMPUTED_ONTOLOGY_FILE = "ontology_inferred_final.ttl";

    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização do Componente Ontology...");
        lock.writeLock().lock();
        try {
            this.model = ModelFactory.createDefaultModel();
            ClassPathResource resource = new ClassPathResource(PRECOMPUTED_ONTOLOGY_FILE);
            try (InputStream in = resource.getInputStream()) {
                if (in == null) {
                    throw new IllegalStateException("Arquivo de ontologia '" + PRECOMPUTED_ONTOLOGY_FILE + "' não encontrado no classpath.");
                }
                RDFDataMgr.read(this.model, in, Lang.TURTLE);
            }
            if (this.model.isEmpty()) {
                throw new IllegalStateException("FALHA CRÍTICA: O modelo pré-calculado está vazio.");
            }
            logger.info("<<< SUCESSO! Ontology inicializada. Total de triplas: {} >>>", this.model.size());
        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
            throw new RuntimeException("Falha crítica ao carregar a ontologia.", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Executa uma consulta SPARQL do tipo SELECT.
     * @param sparqlQuery A consulta a ser executada.
     * @return Uma lista de mapas representando as linhas de resultado.
     */
    public List<Map<String, String>> executeSelectQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            List<Map<String, String>> resultsList = new ArrayList<>();
            Query query = QueryFactory.create(sparqlQuery);
            try (QueryExecution qexec = QueryExecutionFactory.create(query, this.model)) {
                ResultSet rs = qexec.execSelect();
                List<String> resultVars = rs.getResultVars();
                while (rs.hasNext()) {
                    QuerySolution soln = rs.nextSolution();
                    Map<String, String> rowMap = new LinkedHashMap<>();
                    for (String varName : resultVars) {
                        RDFNode node = soln.get(varName);
                        String value = (node == null) ? "N/A" : (node.isLiteral() ? node.asLiteral().getLexicalForm() : node.toString());
                        rowMap.put(varName, value);
                    }
                    resultsList.add(rowMap);
                }
            }
            return resultsList;
        } finally {
            lock.readLock().unlock();
        }
    }

    /**
     * Executa uma consulta SPARQL do tipo ASK.
     * @param sparqlQuery A consulta ASK a ser executada.
     * @return true se o padrão da consulta for encontrado, false caso contrário.
     */
    public boolean executeAskQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            Query query = QueryFactory.create(sparqlQuery);
            try (QueryExecution qexec = QueryExecutionFactory.create(query, this.model)) {
                return qexec.execAsk();
            }
        } finally {
            lock.readLock().unlock();
        }
    }

    public Model getInferredModel() {
        return this.model;
    }
}
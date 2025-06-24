package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.shared.JenaException;
import org.apache.jena.vocabulary.OWL;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.text.Normalizer;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.regex.Pattern;

@Component
public class Ontology {

    private static final Logger logger = LoggerFactory.getLogger(Ontology.class);

    private Model baseModel;
    private InfModel infModel;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    private static final String ONT_PREFIX = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";

    // --- CORREÇÃO PRINCIPAL: REMOÇÃO DAS BARRAS INICIAIS ---
    // O ClassLoader irá procurar a partir da raiz de 'resources'.
    private static final String[] PREGAO_FILES = {
            "datasets/dados_novos_anterior.xlsx",
            "datasets/dados_novos_atual.xlsx"
    };
    private static final String SCHEMA_FILE = "stock_market.owl";
    private static final String BASE_DATA_FILE = "ontologiaB3.ttl";
    private static final String INFO_EMPRESAS_FILE = "Templates/Informacoes_Empresas.xlsx";
    // -----------------------------------------------------------
    
    private static final String INFERENCE_OUTPUT_FILE = "ontologiaB3_com_inferencia.ttl";

    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização Ontology (@PostConstruct)...");
        lock.writeLock().lock();
        try {
            baseModel = ModelFactory.createDefaultModel();
            baseModel.setNsPrefix("stock", ONT_PREFIX);
            baseModel.setNsPrefix("rdf", RDF.uri);
            baseModel.setNsPrefix("rdfs", RDFS.uri);
            baseModel.setNsPrefix("owl", OWL.NS);
            baseModel.setNsPrefix("xsd", XSDDatatype.XSD + "#");
            logger.info("   Modelo base criado e prefixos definidos.");

            loadRdfData(SCHEMA_FILE, Lang.RDFXML, "Schema OWL");
            loadRdfData(BASE_DATA_FILE, Lang.TURTLE, "Dados base TTL");

            logger.info("--- Iniciando carregamento Informações das Empresas ---");
            loadInformacoesEmpresas(INFO_EMPRESAS_FILE);
            logger.info("--- Carregamento Informações das Empresas concluído ---");

            logger.info("--- Iniciando carregamento planilhas de pregão ---");
            for (String filePath : PREGAO_FILES) {
                loadDadosPregaoExcel(filePath);
            }
            logger.info("--- Carregamento planilhas pregão concluído ---");

            long baseSizeBeforeInfer = baseModel.size();
            logger.info("Total triplas BASE (pós-load): {}", baseSizeBeforeInfer);
            validateBaseModelLoad(baseSizeBeforeInfer);

            logger.info("--- Configurando Reasoner ---");
            Reasoner reasoner = getReasoner();
            logger.info("--- Criando modelo inferência ---");
            infModel = ModelFactory.createInfModel(reasoner, baseModel);
            long infSize = infModel.size();
            long inferredCount = infSize - baseSizeBeforeInfer;
            logger.info("--- Modelo inferência criado. Base:{}, Inferidas:{}, Total:{} ---",
                    baseSizeBeforeInfer, Math.max(0, inferredCount), infSize);

            saveInferredModel();
            logger.info("<<< Ontology INICIALIZADA COM SUCESSO >>>");

        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
            baseModel = null; infModel = null;
        } finally {
            lock.writeLock().unlock();
        }
    }

    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            if (infModel == null) {
                logger.error("ERRO CRÍTICO: Modelo de inferência não inicializado.");
                return null;
            }
            logger.debug("Executando consulta SPARQL:\n---\n{}\n---", sparqlQuery);
            List<Map<String, String>> resultsList = new ArrayList<>();
            Query query;
            try {
                query = QueryFactory.create(sparqlQuery);
            } catch (QueryParseException e) {
                logger.error("ERRO DE SINTAXE na query SPARQL: {}", e.getMessage());
                logger.error("Query com erro:\n---\n{}\n---", sparqlQuery);
                return null;
            }
            try (QueryExecution qexec = QueryExecutionFactory.create(query, infModel)) {
                ResultSet rs = qexec.execSelect();
                List<String> resultVars = rs.getResultVars();
                while (rs.hasNext()) {
                    QuerySolution soln = rs.nextSolution();
                    Map<String, String> rowMap = new HashMap<>();
                    for (String varName : resultVars) {
                        RDFNode node = soln.get(varName);
                        String value = "N/A";
                        if (node != null) {
                            if (node.isLiteral()) value = node.asLiteral().getLexicalForm();
                            else if (node.isResource()) value = node.asResource().getURI();
                            else value = node.toString();
                        }
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

    // A lógica de cleanPath aqui agora é redundante, mas não prejudica.
    private void loadRdfData(String resourcePath, Lang language, String description) {
        String cleanPath = resourcePath.startsWith("/") ? resourcePath.substring(1) : resourcePath;
        logger.info("   Tentando carregar {} de classpath: {}", description, cleanPath);
        try (InputStream in = Ontology.class.getClassLoader().getResourceAsStream(cleanPath)) {
            if (in == null) {
                logger.error("   !!!!!!!! ARQUIVO ESSENCIAL '{}' ({}) NÃO ENCONTRADO no classpath !!!!!!!!!", cleanPath, description);
                throw new FileNotFoundException("Arquivo RDF essencial não encontrado: " + cleanPath);
            }
            try (InputStream bis = new BufferedInputStream(in)) {
                RDFDataMgr.read(baseModel, bis, language);
            }
            logger.info("   {} '{}' carregado com sucesso.", description, cleanPath);
        } catch (Exception e) {
             throw new RuntimeException("Falha ao carregar RDF essencial: " + cleanPath, e);
        }
    }

    private void loadInformacoesEmpresas(String resourcePath) {
        String cleanPath = resourcePath.startsWith("/") ? resourcePath.substring(1) : resourcePath;
        logger.info(">> Iniciando carregamento Informações Empresas de: {}", cleanPath);
        int rowsProcessed = 0; int errors = 0;

        try (InputStream excelFile = Ontology.class.getClassLoader().getResourceAsStream(cleanPath)) {
            if (excelFile == null) {
                logger.error("   Arquivo Excel de Informações de Empresas '{}' não encontrado. Pulando.", cleanPath);
                return;
            }
            // O resto do seu método permanece igual...
        } catch (IOException e) {
            logger.error("   Erro de I/O ao ABRIR Informacoes_Empresas {}: {}", cleanPath, e.getMessage(), e);
        }
    }

    private void loadDadosPregaoExcel(String resourcePath) {
        String cleanPath = resourcePath.startsWith("/") ? resourcePath.substring(1) : resourcePath;
        logger.info(">> Iniciando carregamento Pregão de: {}", cleanPath);
        int rowsProcessed = 0; int errors = 0; int skippedTickerFormat = 0;
        try (InputStream excelFile = Ontology.class.getClassLoader().getResourceAsStream(cleanPath)) {
            if (excelFile == null) {
                logger.error("   Arquivo Excel de Pregão '{}' não encontrado. Pulando.", cleanPath); return;
            }
            // O resto do seu método permanece igual...
        } catch (IOException e) {
            logger.error("   Erro de I/O ao ABRIR Excel de Pregão {}", cleanPath, e);
        }
    }

    // TODOS OS OUTROS MÉTODOS AUXILIARES PERMANECEM EXATAMENTE IGUAIS
    // ... findOrCreateEmpresaResource, normalizarTextoJava, etc. ...

}
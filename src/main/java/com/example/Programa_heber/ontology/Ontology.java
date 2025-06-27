package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
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

@Component
public class Ontology {

    private static final Logger logger = LoggerFactory.getLogger(Ontology.class);
    private InfModel infModel;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    private static final String ONT_PREFIX = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";
    private static final String[] PREGAO_FILES = { "datasets/dados_novos_anterior.xlsx", "datasets/dados_novos_atual.xlsx" };
    private static final String INFO_EMPRESAS_FILE = "Templates/Informacoes_Empresas.xlsx";
    private static final String INFERENCE_OUTPUT_FILENAME = "ontologiaB3_com_inferencia.ttl";

    @PostConstruct
    public void init() {
        lock.writeLock().lock();
        try { this.infModel = loadOrCreateInferredModel(); }
        catch (Exception e) { throw new RuntimeException("FALHA CRÍTICA AO CARREGAR/CRIAR ONTOLOGIA", e); }
        finally { lock.writeLock().unlock(); }
    }

    private InfModel loadOrCreateInferredModel() throws IOException {
        ClassPathResource inferredResource = new ClassPathResource(INFERENCE_OUTPUT_FILENAME);
        if (inferredResource.exists() && inferredResource.contentLength() > 0) {
            logger.info("--- Modelo inferido pré-calculado '{}' encontrado. Carregando... ---", INFERENCE_OUTPUT_FILENAME);
            Model dataModel = ModelFactory.createDefaultModel();
            try (InputStream in = inferredResource.getInputStream()) { RDFDataMgr.read(dataModel, in, Lang.TURTLE); }
            return ModelFactory.createRDFSModel(dataModel);
        } else {
            logger.warn("--- Modelo inferido '{}' não encontrado. Construindo do zero... ---", INFERENCE_OUTPUT_FILENAME);
            Model baseModel = buildBaseModelFromSources();
            InfModel constructedInfModel = ModelFactory.createRDFSModel(baseModel);
            saveInferredModelToFileSystem(constructedInfModel);
            return constructedInfModel;
        }
    }

    private Model buildBaseModelFromSources() throws IOException {
        Model model = ModelFactory.createDefaultModel();
        model.setNsPrefix("b3", ONT_PREFIX);
        model.setNsPrefix("rdfs", RDFS.uri);

        // A ordem de carregamento é crucial
        loadInformacoesEmpresas(model, INFO_EMPRESAS_FILE);
        for (String filePath : PREGAO_FILES) {
            loadDadosPregaoExcel(model, filePath);
        }
        return model;
    }

    private void loadInformacoesEmpresas(Model model, String resourcePath) throws IOException {
        logger.info(">> Carregando Cadastro de Empresas...");
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream(); Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String nomeEmpresa = getStringCellValue(row.getCell(0));
                String ticker = getStringCellValue(row.getCell(1));
                if (nomeEmpresa == null || ticker == null) continue;

                // Cria ou obtém o Recurso para o Valor Mobiliário (entidade central)
                Resource vmRes = model.createResource(ONT_PREFIX + ticker.trim());
                addStatement(model, vmRes, RDF.type, model.createResource(ONT_PREFIX + "Valor_Mobiliario"));
                addStatement(model, vmRes, model.createProperty(ONT_PREFIX, "ticker"), ticker.trim());
                
                // Cria ou obtém o Recurso para a Empresa
                Resource empresaRes = model.createResource(ONT_PREFIX + normalizarParaURI(nomeEmpresa.trim()));
                addStatement(model, empresaRes, RDF.type, model.createResource(ONT_PREFIX + "Empresa"));
                addStatement(model, empresaRes, RDFS.label, nomeEmpresa.trim(), "pt");

                // CRIA A LIGAÇÃO CORRETA E ÚNICA
                addStatement(model, empresaRes, model.createProperty(ONT_PREFIX, "temValorMobiliarioNegociado"), vmRes);
            }
        }
    }

    private void loadDadosPregaoExcel(Model model, String resourcePath) throws IOException {
        logger.info(">> Carregando Dados de Pregão de: {}", resourcePath);
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream(); Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            SimpleDateFormat rdfDateFormat = new SimpleDateFormat("yyyy-MM-dd");
            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String ticker = getStringCellValue(row.getCell(3));
                Date dataPregao = getDateCellValue(row.getCell(1));
                if (ticker == null || dataPregao == null) continue;

                // Encontra o nó Valor Mobiliário que JÁ DEVE EXISTIR
                Resource valorMobiliario = model.getResource(ONT_PREFIX + ticker.trim());

                // Cria a instância de Negociação
                String dataFmt = rdfDateFormat.format(dataPregao);
                Resource negociadoRes = model.createResource(ONT_PREFIX + "Negociado_" + ticker.trim() + "_" + dataFmt);
                addStatement(model, negociadoRes, RDF.type, model.createResource(ONT_PREFIX + "Negociado_Em_Pregao"));

                // CRIA A LIGAÇÃO DIRETA E CORRETA (o ponto da falha)
                addStatement(model, valorMobiliario, model.createProperty(ONT_PREFIX, "negociado"), negociadoRes);
                
                // Cria o Pregão e o liga à Negociação
                Resource pregaoRes = model.createResource(ONT_PREFIX + "Pregao_" + dataFmt);
                addStatement(model, pregaoRes, model.createProperty(ONT_PREFIX, "ocorreEmData"), model.createTypedLiteral(dataFmt, XSDDatatype.XSDdate));
                addStatement(model, negociadoRes, model.createProperty(ONT_PREFIX, "negociadoDurante"), pregaoRes);
                
                // Adiciona os dados
                addNumericProperty(model, negociadoRes, model.createProperty(ONT_PREFIX, "precoFechamento"), getNumericCellValue(row.getCell(11)));
                // Adicione os outros aqui...
            }
        }
    }
    
    // --- O RESTO DA CLASSE (Helpers) ---
    public List<Map<String, String>> executeQuery(String sparqlQuery) { /* ... */ }
    private String getStringCellValue(Cell cell) { /* ... */ }
    private Date getDateCellValue(Cell cell) { /* ... */ }
    private double getNumericCellValue(Cell cell) { /* ... */ }
    private String normalizarParaURI(String texto) { /* ... */ }
    private void saveInferredModelToFileSystem(InfModel modelToSave) { /* ... */ }
    private void addStatement(Model model, Resource s, Property p, RDFNode o) { if (s != null && p != null && o != null) model.add(s, p, o); }
    private void addStatement(Model model, Resource s, Property p, String o) { if (s != null && p != null && o != null && !o.isEmpty()) model.add(s, p, o); }
    private void addStatement(Model model, Resource s, Property p, String o, String lang) { if (s != null && p != null && o != null && !o.isEmpty()) model.add(s, p, o, lang); }
    private void addNumericProperty(Model model, Resource s, Property p, double value) { if (!Double.isNaN(value)) addStatement(model, s, p, model.createTypedLiteral(value)); }
    private void validateBaseModelLoad(long size) { if (size < 1000) logger.warn("MODELO BASE SUSPEITOSAMENTE PEQUENO ({}) APÓS CARREGAMENTO!", size); }
}
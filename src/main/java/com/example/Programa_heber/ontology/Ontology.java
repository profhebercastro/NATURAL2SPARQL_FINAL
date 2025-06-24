package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.vocabulary.OWL;
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
    private static final String SCHEMA_FILE = "stock_market.owl";
    private static final String BASE_DATA_FILE = "ontologiaB3.ttl";
    
    /************************************************************/
    /* --- AQUI ESTÁ A CORREÇÃO ---                             */
    /* O nome da pasta no seu projeto é "Templates" com 'T'     */
    /* maiúsculo. O caminho precisa ser exatamente igual.       */
    /************************************************************/
    private static final String INFO_EMPRESAS_FILE = "Templates/Informacoes_Empresas.xlsx"; // <-- CORRIGIDO
    
    private static final String INFERENCE_OUTPUT_FILENAME = "ontologiaB3_com_inferencia.ttl";

    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização do Componente Ontology (@PostConstruct)...");
        lock.writeLock().lock();
        try {
            this.infModel = loadOrCreateInferredModel();
            if (this.infModel == null || this.infModel.isEmpty()) {
                throw new IllegalStateException("FALHA CRÍTICA: O modelo de inferência RDF não pôde ser carregado ou criado.");
            }
            logger.info("<<< Ontology INICIALIZADA COM SUCESSO. Total de triplas no modelo: {} >>>", this.infModel.size());
        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE E IRRECUPERÁVEL NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
            throw new RuntimeException("Falha crítica ao inicializar a camada de ontologia.", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    private InfModel loadOrCreateInferredModel() throws IOException {
        ClassPathResource inferredResource = new ClassPathResource(INFERENCE_OUTPUT_FILENAME);
        if (inferredResource.exists()) {
            logger.info("--- Modelo inferido pré-calculado '{}' encontrado. Carregando diretamente... ---", INFERENCE_OUTPUT_FILENAME);
            Model dataModel = ModelFactory.createDefaultModel();
            try (InputStream in = inferredResource.getInputStream()) {
                RDFDataMgr.read(dataModel, in, Lang.TURTLE);
            }
            return ModelFactory.createRDFSModel(dataModel);
        } else {
            logger.warn("--- Modelo inferido '{}' não encontrado. Construindo do zero (processo lento)... ---", INFERENCE_OUTPUT_FILENAME);
            Model baseModel = buildBaseModelFromSources();
            validateBaseModelLoad(baseModel.size());
            Reasoner reasoner = ReasonerRegistry.getRDFSReasoner();
            InfModel constructedInfModel = ModelFactory.createInfModel(reasoner, baseModel);
            long inferredCount = constructedInfModel.size() - baseModel.size();
            logger.info("--- Modelo de inferência criado. Base:{}, Inferidas:{}, Total:{} ---", baseModel.size(), Math.max(0, inferredCount), constructedInfModel.size());
            saveInferredModelToFileSystem(constructedInfModel);
            return constructedInfModel;
        }
    }

    private Model buildBaseModelFromSources() throws IOException {
        Model model = ModelFactory.createDefaultModel();
        model.setNsPrefix("b3", ONT_PREFIX);
        model.setNsPrefix("rdf", RDF.uri);
        model.setNsPrefix("rdfs", RDFS.uri);
        model.setNsPrefix("owl", OWL.NS);
        model.setNsPrefix("xsd", XSDDatatype.XSD + "#");
        
        loadRdfData(model, SCHEMA_FILE, Lang.RDFXML, "Schema OWL");
        loadRdfData(model, BASE_DATA_FILE, Lang.TURTLE, "Dados base TTL");
        loadInformacoesEmpresas(model, INFO_EMPRESAS_FILE);
        
        for (String filePath : PREGAO_FILES) {
            loadDadosPregaoExcel(model, filePath);
        }
        return model;
    }

    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            if (infModel == null) return Collections.emptyList();
            List<Map<String, String>> resultsList = new ArrayList<>();
            Query query = QueryFactory.create(sparqlQuery);
            try (QueryExecution qexec = QueryExecutionFactory.create(query, infModel)) {
                ResultSet rs = qexec.execSelect();
                List<String> resultVars = rs.getResultVars();
                while (rs.hasNext()) {
                    QuerySolution soln = rs.nextSolution();
                    Map<String, String> rowMap = new LinkedHashMap<>();
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
        } catch (Exception e) {
            logger.error("Erro durante a execução da consulta SPARQL.", e);
            return Collections.emptyList();
        } finally {
            lock.readLock().unlock();
        }
    }

    private void loadRdfData(Model model, String resourcePath, Lang language, String description) throws IOException {
        try (InputStream in = new ClassPathResource(resourcePath).getInputStream()) {
            RDFDataMgr.read(model, in, language);
        } catch (IOException e) {
            logger.error("ERRO FATAL ao ler o recurso RDF '{}'", resourcePath, e);
            throw e;
        }
    }

    private void loadInformacoesEmpresas(Model model, String resourcePath) throws IOException {
        logger.info(">> Carregando Informações de Empresas de: {}", resourcePath);
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream();
             Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String nomeEmpresa = getStringCellValue(row.getCell(0));
                String ticker = getStringCellValue(row.getCell(1));
                String setor = getStringCellValue(row.getCell(5));
                if (nomeEmpresa == null || ticker == null || setor == null) continue;

                Resource empresaResource = createResource(model, ONT_PREFIX + normalizarTexto(nomeEmpresa));
                addStatement(model, empresaResource, RDF.type, createResource(model, ONT_PREFIX + "Empresa_Capital_Aberto"));
                addStatement(model, empresaResource, RDFS.label, model.createLiteral(nomeEmpresa.trim(), "pt"));
                
                Resource setorResource = createResource(model, ONT_PREFIX + "Setor_" + normalizarTexto(setor));
                addStatement(model, setorResource, RDF.type, createResource(model, ONT_PREFIX + "Setor_Atuacao"));
                addStatement(model, setorResource, RDFS.label, model.createLiteral(setor.trim(), "pt"));
                addStatement(model, empresaResource, createProperty(model, "atuaEm"), setorResource);
                
                Resource vmResource = createResource(model, ONT_PREFIX + ticker.trim());
                addStatement(model, vmResource, RDF.type, createResource(model, "Valor_Mobiliario"));
                addStatement(model, vmResource, RDFS.label, model.createLiteral(ticker.trim()));
                addStatement(model, empresaResource, createProperty(model, "temValorMobiliarioNegociado"), vmResource);
                
                Resource codigoResource = createResource(model, ONT_PREFIX + ticker.trim() + "_Codigo");
                addStatement(model, codigoResource, RDF.type, createResource(model, "Codigo_Negociacao"));
                addStatement(model, codigoResource, createProperty(model, "ticker"), model.createLiteral(ticker.trim()));
                addStatement(model, vmResource, createProperty(model, "representadoPor"), codigoResource);
            }
        }
    }

    private void loadDadosPregaoExcel(Model model, String resourcePath) throws IOException {
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream();
             Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            SimpleDateFormat rdfDateFormat = new SimpleDateFormat("yyyy-MM-dd");
            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String ticker = getStringCellValue(row.getCell(3));
                Date dataPregao = getDateCellValue(row.getCell(1));
                if (ticker == null || !ticker.matches("^[A-Z]{4}\\d{1,2}$") || dataPregao == null) continue;

                String dataFmt = rdfDateFormat.format(dataPregao);
                Resource valorMobiliario = createResource(model, ONT_PREFIX + ticker.trim());
                String negociadoUri = ONT_PREFIX + "Negociado_" + ticker.trim() + "_" + dataFmt;
                Resource negociadoResource = createResource(model, negociadoUri);
                addStatement(model, negociadoResource, RDF.type, createResource(model, "Negociado_Em_Pregao"));
                addStatement(model, valorMobiliario, createProperty(model, "negociado"), negociadoResource);
                
                Resource pregaoResource = createResource(model, ONT_PREFIX + "Pregao_" + dataFmt);
                addStatement(model, pregaoResource, RDF.type, createResource(model, "Pregao"));
                addStatement(model, pregaoResource, createProperty(model, "ocorreEmData"), model.createTypedLiteral(dataFmt, XSDDatatype.XSDdate));
                addStatement(model, negociadoResource, createProperty(model, "negociadoDurante"), pregaoResource);
                
                addNumericProperty(model, negociadoResource, createProperty(model, "precoAbertura"), getNumericCellValue(row.getCell(7)));
                addNumericProperty(model, negociadoResource, createProperty(model, "precoMaximo"), getNumericCellValue(row.getCell(8)));
                addNumericProperty(model, negociadoResource, createProperty(model, "precoMinimo"), getNumericCellValue(row.getCell(9)));
                addNumericProperty(model, negociadoResource, createProperty(model, "precoFechamento"), getNumericCellValue(row.getCell(11)));
                addNumericProperty(model, negociadoResource, createProperty(model, "volumeNegociacao"), getNumericCellValue(row.getCell(15)));
            }
        }
    }
    
    // --- Funções Utilitárias ---
    private String getStringCellValue(Cell cell) {
        if (cell == null) return null;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        switch (type) {
            case STRING: return cell.getStringCellValue().trim();
            case NUMERIC: return String.valueOf(cell.getNumericCellValue());
            default: return null;
        }
    }

    private Date getDateCellValue(Cell cell) {
        if (cell == null) return null;
        if (cell.getCellType() == CellType.NUMERIC && DateUtil.isCellDateFormatted(cell)) return cell.getDateCellValue();
        if (cell.getCellType() == CellType.STRING) {
            for (String format : new String[]{"yyyy-MM-dd", "dd/MM/yyyy"}) {
                try { return new SimpleDateFormat(format).parse(cell.getStringCellValue().trim()); } catch (ParseException ignored) {}
            }
        }
        return null;
    }

    private double getNumericCellValue(Cell cell) {
        if (cell == null) return Double.NaN;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        if (type == CellType.NUMERIC) return cell.getNumericCellValue();
        if (type == CellType.STRING) {
            try { return Double.parseDouble(cell.getStringCellValue().trim().replace(",", ".")); } catch (NumberFormatException e) { return Double.NaN; }
        }
        return Double.NaN;
    }

    private String normalizarTexto(String texto) {
        if (texto == null) return "";
        return Normalizer.normalize(texto.trim(), Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}+", "")
                .replaceAll("[^a-zA-Z0-9_]", "_");
    }
    
    private void saveInferredModelToFileSystem(InfModel modelToSave) {
        Path outputPath = Paths.get(INFERENCE_OUTPUT_FILENAME);
        try (OutputStream out = new BufferedOutputStream(Files.newOutputStream(outputPath))) {
            RDFDataMgr.write(out, modelToSave, Lang.TURTLE);
        } catch (IOException e) {
            logger.warn("Não foi possível salvar o modelo inferido em disco.", e);
        }
    }
    
    private Resource createResource(Model model, String uri) { return model.createResource(uri); }
    private Property createProperty(Model model, String localName) { return model.createProperty(ONT_PREFIX + localName); }
    private void addStatement(Model model, Resource s, Property p, RDFNode o) { if (s != null && p != null && o != null) model.add(s, p, o); }
    private void addNumericProperty(Model model, Resource s, Property p, double value) { if (!Double.isNaN(value)) addStatement(model, s, p, model.createTypedLiteral(value)); }
    private void validateBaseModelLoad(long size) { if (size < 100) logger.warn("MODELO BASE SUSPEITOSAMENTE PEQUENO ({}) APÓS CARREGAMENTO!", size); }
}
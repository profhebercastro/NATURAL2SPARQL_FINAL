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
    
    // --- CORREÇÃO DE CAMINHOS: SEM A BARRA INICIAL ---
    private static final String[] PREGAO_FILES = {
            "datasets/dados_novos_anterior.xlsx",
            "datasets/dados_novos_atual.xlsx"
    };
    private static final String SCHEMA_FILE = "stock_market.owl";
    private static final String BASE_DATA_FILE = "ontologiaB3.ttl";
    private static final String INFO_EMPRESAS_FILE = "Templates/Informacoes_Empresas.xlsx";
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
            loadInformacoesEmpresas(INFO_EMPRESAS_FILE);

            for (String filePath : PREGAO_FILES) {
                loadDadosPregaoExcel(filePath);
            }
            logger.info("--- Carregamento planilhas pregão concluído ---");

            long baseSizeBeforeInfer = baseModel.size();
            validateBaseModelLoad(baseSizeBeforeInfer);

            Reasoner reasoner = getReasoner();
            infModel = ModelFactory.createInfModel(reasoner, baseModel);
            long infSize = infModel.size();
            long inferredCount = infSize - baseSizeBeforeInfer;
            logger.info("--- Modelo inferência criado. Base:{}, Inferidas:{}, Total:{} ---",
                    baseSizeBeforeInfer, Math.max(0, inferredCount), infSize);

            saveInferredModel();
            logger.info("<<< Ontology INICIALIZADA COM SUCESSO >>>");

        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
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
            List<Map<String, String>> resultsList = new ArrayList<>();
            Query query = QueryFactory.create(sparqlQuery);
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
        } catch(Exception e) {
            logger.error("Erro ao executar consulta SPARQL.", e);
            return null;
        }
        finally {
            lock.readLock().unlock();
        }
    }

    private void loadRdfData(String resourcePath, Lang language, String description) {
        logger.info("   Tentando carregar {} de classpath: {}", description, resourcePath);
        try (InputStream in = Ontology.class.getClassLoader().getResourceAsStream(resourcePath)) {
            if (in == null) {
                throw new FileNotFoundException("Arquivo RDF essencial não encontrado: " + resourcePath);
            }
            RDFDataMgr.read(baseModel, in, language);
            logger.info("   {} '{}' carregado com sucesso.", description, resourcePath);
        } catch (Exception e) {
             throw new RuntimeException("Falha ao carregar RDF: " + resourcePath, e);
        }
    }

    private void loadInformacoesEmpresas(String resourcePath) {
        logger.info(">> Iniciando carregamento Informações Empresas de: {}", resourcePath);
        try (InputStream excelFile = Ontology.class.getClassLoader().getResourceAsStream(resourcePath)) {
            if (excelFile == null) {
                logger.error("   Arquivo Excel de Informações de Empresas '{}' não encontrado. Pulando.", resourcePath);
                return;
            }
            try (Workbook workbook = new XSSFWorkbook(excelFile)) {
                Sheet sheet = workbook.getSheetAt(0);
                final int nomeEmpresaColIdx = 0, codigoNegociacaoColIdx = 1, setorAtuacao3PrincipalColIdx = 5;
                for (int i = 1; i <= sheet.getLastRowNum(); i++) {
                    Row row = sheet.getRow(i);
                    if (row == null) continue;
                    String nomeEmpresaPlanilha = getStringCellValue(row.getCell(nomeEmpresaColIdx), "NomeEmpresa", i + 1);
                    String tickerPlanilha = getStringCellValue(row.getCell(codigoNegociacaoColIdx), "CodigoNegociacao", i + 1);
                    String setorPrincipalPlanilha = getStringCellValue(row.getCell(setorAtuacao3PrincipalColIdx), "SetorAtuacao3Principal", i + 1);
                    if (nomeEmpresaPlanilha == null || tickerPlanilha == null || setorPrincipalPlanilha == null) continue;
                    
                    Resource empresaResource = findOrCreateEmpresaResource(nomeEmpresaPlanilha.trim(), tickerPlanilha.trim().toUpperCase());
                    addPropertyIfNotExist(empresaResource, RDF.type, getResource("Empresa_Capital_Aberto"));
                    addPropertyIfNotExist(empresaResource, RDFS.label, baseModel.createLiteral(nomeEmpresaPlanilha.trim(), "pt"));
                    String setorUriNome = ONT_PREFIX + "Setor_" + normalizarTextoJava(setorPrincipalPlanilha.trim());
                    Resource setorUriResource = baseModel.createResource(setorUriNome);
                    addPropertyIfNotExist(setorUriResource, RDF.type, getResource("Setor_Atuacao"));
                    addPropertyIfNotExist(setorUriResource, RDFS.label, baseModel.createLiteral(setorPrincipalPlanilha.trim(), "pt"));
                    addPropertyIfNotExist(empresaResource, getProperty("atuaEm"), setorUriResource);
                    Resource vmResource = findOrCreateValorMobiliarioResource(tickerPlanilha.trim().toUpperCase());
                    addPropertyIfNotExist(empresaResource, getProperty("temValorMobiliarioNegociado"), vmResource);
                }
            }
        } catch (IOException e) {
            logger.error("   Erro de I/O ao ABRIR Informacoes_Empresas {}: {}", resourcePath, e.getMessage(), e);
        }
    }

    private void loadDadosPregaoExcel(String resourcePath) {
        logger.info(">> Iniciando carregamento Pregão de: {}", resourcePath);
        try (InputStream excelFile = Ontology.class.getClassLoader().getResourceAsStream(resourcePath)) {
            if (excelFile == null) {
                logger.error("   Arquivo Excel de Pregão '{}' não encontrado. Pulando.", resourcePath); return;
            }
            try (Workbook workbook = new XSSFWorkbook(excelFile)) {
                Sheet sheet = workbook.getSheetAt(0);
                SimpleDateFormat rdfDateFormat = new SimpleDateFormat("yyyy-MM-dd");
                for (int i = 1; i <= sheet.getLastRowNum(); i++) {
                    Row row = sheet.getRow(i);
                    if (row == null) continue;
                    final int tickerColIdx = 3, dataColIdx = 1, openPriceColIdx = 7, highPriceColIdx = 8,
                            lowPriceColIdx = 9, closePriceColIdx = 11, totalNegociosColIdx = 13, volumeColIdx = 15;
                    String ticker = getStringCellValue(row.getCell(tickerColIdx), "Ticker", i + 1);
                    Date dataPregaoDate = getDateCellValue(row.getCell(dataColIdx), "Data", i + 1, ticker);
                    if (ticker == null || !ticker.matches("^[A-Z]{4}\\d{1,2}$") || dataPregaoDate == null) continue;
                    
                    double pUlt = getNumericCellValue(row.getCell(closePriceColIdx), "PrecoFechamento", i + 1, ticker);
                    if (Double.isNaN(pUlt)) continue;

                    String dataFmt = rdfDateFormat.format(dataPregaoDate);
                    Resource valorMobiliarioResource = findOrCreateValorMobiliarioResource(ticker.trim().toUpperCase());
                    String negociadoURI = ONT_PREFIX + "Negociado_" + ticker.trim().toUpperCase() + "_" + dataFmt.replace("-", "");
                    Resource negociadoResource = baseModel.createResource(negociadoURI, getResource("Negociado_Em_Pregao"));
                    Resource pregaoResource = baseModel.createResource(ONT_PREFIX + "Pregao_" + dataFmt.replace("-", ""), getResource("Pregao"));

                    addPropertyIfNotExist(pregaoResource, getProperty("ocorreEmData"), ResourceFactory.createTypedLiteral(dataFmt, XSDDatatype.XSDdate));
                    addPropertyIfNotExist(valorMobiliarioResource, getProperty("negociado"), negociadoResource);
                    addPropertyIfNotExist(negociadoResource, getProperty("negociadoDurante"), pregaoResource);
                    
                    addNumericPropertyIfValid(negociadoResource, getProperty("precoAbertura"), getNumericCellValue(row.getCell(openPriceColIdx), "PrecoAbertura", i+1, ticker));
                    addNumericPropertyIfValid(negociadoResource, getProperty("precoMaximo"), getNumericCellValue(row.getCell(highPriceColIdx), "PrecoMaximo", i+1, ticker));
                    addNumericPropertyIfValid(negociadoResource, getProperty("precoMinimo"), getNumericCellValue(row.getCell(lowPriceColIdx), "PrecoMinimo", i+1, ticker));
                    addNumericPropertyIfValid(negociadoResource, getProperty("precoFechamento"), pUlt);
                    addNumericPropertyIfValid(negociadoResource, getProperty("totalNegocios"), getNumericCellValue(row.getCell(totalNegociosColIdx), "TotalNegocios", i+1, ticker));
                    addNumericPropertyIfValid(negociadoResource, getProperty("volumeNegociacao"), getNumericCellValue(row.getCell(volumeColIdx), "Volume", i+1, ticker));
                }
            }
        } catch (IOException e) {
            logger.error("   Erro de I/O ao ABRIR Excel de Pregão {}", resourcePath, e);
        }
    }

    private Resource findOrCreateEmpresaResource(String nomeEmpresa, String ticker) {
        StmtIterator iter = baseModel.listStatements(null, RDFS.label, baseModel.createLiteral(nomeEmpresa, "pt"));
        if (iter.hasNext()) {
            return iter.nextStatement().getSubject();
        }
        return baseModel.createResource(ONT_PREFIX + ticker.replaceAll("[^A-Za-z0-9]", "") + "_EmpresaEntidade");
    }

    private String normalizarTextoJava(String textoInput) {
        if (textoInput == null) return "";
        String nfd = Normalizer.normalize(textoInput.toLowerCase(Locale.ROOT), Normalizer.Form.NFD);
        Pattern pattern = Pattern.compile("\\p{InCombiningDiacriticalMarks}+");
        return pattern.matcher(nfd).replaceAll("").replaceAll("[^a-z0-9\\s]", "").trim().replaceAll("\\s+", "_");
    }

    private Resource findOrCreateValorMobiliarioResource(String ticker) {
        String vmUriStr = ONT_PREFIX + ticker;
        Resource vmResource = baseModel.getResource(vmUriStr);
        if (!baseModel.contains(vmResource, RDF.type, getResource("Valor_Mobiliario"))) {
            vmResource = baseModel.createResource(vmUriStr);
            addPropertyIfNotExist(vmResource, RDF.type, getResource("Valor_Mobiliario"));
            Resource codigoResource = baseModel.createResource(ONT_PREFIX + ticker + "_Codigo", getResource("Codigo_Negociacao"));
            addPropertyIfNotExist(codigoResource, getProperty("ticker"), baseModel.createLiteral(ticker));
            addPropertyIfNotExist(vmResource, getProperty("representadoPor"), codigoResource);
        }
        return vmResource;
    }

    private void validateBaseModelLoad(long size) {
        logger.info("   Validação: Modelo base tem {} triplas.", size);
        if (size == 0) logger.error("MODELO BASE VAZIO APÓS CARREGAMENTO!");
    }

    private Reasoner getReasoner() {
        return ReasonerRegistry.getRDFSReasoner();
    }

    private void saveInferredModel() {
        try {
            Path outputPath = Paths.get(INFERENCE_OUTPUT_FILE);
            if (infModel != null && infModel.size() > 0) {
                try (OutputStream out = new BufferedOutputStream(Files.newOutputStream(outputPath))) {
                    RDFDataMgr.write(out, infModel, Lang.TURTLE);
                    logger.info("   Modelo RDF inferido salvo em: {}", outputPath.toAbsolutePath());
                }
            }
        } catch (Exception e) {
            logger.error("   Falha ao salvar modelo inferido.", e);
        }
    }

    private String getStringCellValue(Cell cell, String colName, int rowNum) {
        if (cell == null) return null;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        switch (type) {
            case STRING: return cell.getStringCellValue().trim();
            case NUMERIC: return String.valueOf(cell.getNumericCellValue());
            default: return null;
        }
    }

    private Date getDateCellValue(Cell cell, String colName, int rowNum, String tickerContext) {
        if (cell == null) return null;
        if (cell.getCellType() == CellType.NUMERIC && DateUtil.isCellDateFormatted(cell)) {
            return cell.getDateCellValue();
        } else if (cell.getCellType() == CellType.STRING) {
            return parseDateFromString(cell.getStringCellValue().trim(), colName, rowNum, tickerContext);
        }
        return null;
    }

    private Date parseDateFromString(String dateStr, String colName, int rowNum, String tickerContext) {
        SimpleDateFormat[] formats = { new SimpleDateFormat("yyyy-MM-dd"), new SimpleDateFormat("dd/MM/yyyy"), new SimpleDateFormat("yyyyMMdd") };
        for (SimpleDateFormat fmt : formats) {
            try { return fmt.parse(dateStr); } catch (ParseException ignored) {}
        }
        return null;
    }

    private double getNumericCellValue(Cell cell, String colName, int rowNum, String tickerContext) {
        if (cell == null) return Double.NaN;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        if (type == CellType.NUMERIC) return cell.getNumericCellValue();
        if (type == CellType.STRING) {
            try { return Double.parseDouble(cell.getStringCellValue().trim().replace(",", ".")); } catch (NumberFormatException e) { return Double.NaN; }
        }
        return Double.NaN;
    }

    private Property getProperty(String localName) {
        return ResourceFactory.createProperty(ONT_PREFIX + localName);
    }

    private Resource getResource(String localName) {
        return ResourceFactory.createResource(ONT_PREFIX + localName);
    }

    private void addPropertyIfNotExist(Resource subject, Property predicate, RDFNode object) {
        if (subject != null && predicate != null && object != null && !baseModel.contains(subject, predicate, object)) {
            baseModel.add(subject, predicate, object);
        }
    }

    private void addNumericPropertyIfValid(Resource subject, Property predicate, double value) {
        if (subject != null && predicate != null && !Double.isNaN(value)) {
            baseModel.add(subject, predicate, baseModel.createTypedLiteral(value));
        }
    }
}
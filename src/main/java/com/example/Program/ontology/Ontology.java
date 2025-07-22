package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.tdb2.TDB2Factory; 
import org.apache.jena.util.iterator.ExtendedIterator; 
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
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

  
    private Dataset dataset; 
    private Model model;     
    private final ReadWriteLock lock = new ReentrantReadWriteLock();
    
    
    private static final String TDB_DATABASE_LOCATION = "/var/data/tdb2_database"; 

   
    private static final String ONT_PREFIX = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";
    private static final String PREGAO_FILE_CONSOLIDADO = "datasets/stock_market_june 2025.xlsx";
    private static final String INFO_EMPRESAS_FILE = "Templates/Company_Information.xlsx";

    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização do Componente Ontology (@PostConstruct)...");
        
        
        try {
            Files.createDirectories(Paths.get(TDB_DATABASE_LOCATION));
        } catch (IOException e) {
            logger.error("FALHA CRÍTICA: Não foi possível criar o diretório do banco de dados TDB em '{}'.", TDB_DATABASE_LOCATION, e);
            throw new RuntimeException("Falha ao criar diretório do TDB.", e);
        }

       
        this.dataset = TDB2Factory.connectDataset(TDB_DATABASE_LOCATION);
        this.model = dataset.getDefaultModel(); 
        logger.info("Conectado ao banco de dados TDB2 em '{}'", TDB_DATABASE_LOCATION);

       
        dataset.begin(ReadWrite.READ);
        boolean isEmpty = model.isEmpty();
        dataset.end();

        if (isEmpty) {
            logger.warn("!!! Banco de dados TDB2 está vazio. Iniciando processo de populamento único...");
            populateDatabaseFromScratch();
        } else {
            logger.info("<<< Banco de dados TDB2 já populado. Total de triplas: {} >>>", model.size());
        }
    }

    private void populateDatabaseFromScratch() {
        lock.writeLock().lock(); 
        try {
            
            logger.info("--- (1/3) Construindo modelo base em memória a partir dos arquivos Excel...");
            Model baseModelInMemory = buildBaseModelFromSources();
            logger.info("--- Modelo base em memória construído com {} triplas.", baseModelInMemory.size());
            
            validateBaseModelLoad(baseModelInMemory.size());

           
            logger.info("--- (2/3) Aplicando RDFS Reasoner para criar o modelo de inferência...");
            Reasoner reasoner = ReasonerRegistry.getRDFSReasoner();
            InfModel infModelInMemory = ModelFactory.createInfModel(reasoner, baseModelInMemory);
            long inferredCount = infModelInMemory.size() - baseModelInMemory.size();
            logger.info("--- Modelo de inferência criado. Base:{}, Inferidas:{}, Total:{} triplas.",
                    baseModelInMemory.size(), Math.max(0, inferredCount), infModelInMemory.size());

           
            logger.info("--- (3/3) Gravando o modelo inferido completo no banco de dados TDB2 em disco...");
            dataset.begin(ReadWrite.WRITE); 
            try {
                model.add(infModelInMemory); 
                dataset.commit(); 
                logger.info("--- SUCESSO! Banco de dados TDB2 populado com {} triplas. ---", model.size());
            } catch (Exception e) {
                logger.error("!!!!!!!! FALHA GRAVE DURANTE A TRANSAÇÃO DE ESCRITA NO TDB2 !!!!!!!!", e);
                dataset.abort(); 
            } finally {
                dataset.end(); 
            }

        } catch (IOException e) {
            logger.error("!!!!!!!! FALHA IRRECUPERÁVEL AO CONSTRUIR O MODELO BASE !!!!!!!!", e);
            throw new RuntimeException("Falha crítica ao ler fontes de dados para o TDB2.", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    
    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        lock.readLock().lock();
        List<Map<String, String>> resultsList = new ArrayList<>();
        
        dataset.begin(ReadWrite.READ); 
        try {
            if (this.model == null) { 
                logger.error("Tentativa de executar consulta em um modelo nulo."); 
                return Collections.emptyList(); 
            }
            Query query = QueryFactory.create(sparqlQuery);
            try (QueryExecution qexec = QueryExecutionFactory.create(query, this.model)) {
                ResultSet rs = qexec.execSelect();
                List<String> resultVars = rs.getResultVars();
                while (rs.hasNext()) {
                    QuerySolution soln = rs.nextSolution();
                    Map<String, String> rowMap = new LinkedHashMap<>();
                    for (String varName : resultVars) {
                        RDFNode node = soln.get(varName);
                        String value = "N/A";
                        if (node != null) {
                            if (node.isLiteral()) { value = node.asLiteral().getLexicalForm(); } 
                            else { value = node.toString(); }
                        }
                        rowMap.put(varName, value);
                    }
                    resultsList.add(rowMap);
                }
            }
            logger.info("Consulta retornou {} resultados.", resultsList.size());
            return resultsList;
        } catch (Exception e) {
            logger.error("Erro durante a execução da consulta SPARQL.", e);
            return Collections.emptyList();
        } finally {
            dataset.end(); 
            lock.readLock().unlock();
        }
    }
    
   
    @PreDestroy
    public void closeDatabase() {
        if (dataset != null) {
            logger.info("<<< Fechando a conexão com o banco de dados TDB2... >>>");
            dataset.close();
        }
    }

    

    private Model buildBaseModelFromSources() throws IOException {
        Model inMemoryModel = ModelFactory.createDefaultModel();
        inMemoryModel.setNsPrefix("b3", ONT_PREFIX);
        inMemoryModel.setNsPrefix("rdfs", RDFS.uri);
        inMemoryModel.setNsPrefix("rdf", RDF.uri);
        inMemoryModel.setNsPrefix("xsd", XSDDatatype.XSD + "#");

        loadInformacoesEmpresas(inMemoryModel, INFO_EMPRESAS_FILE);
        loadDadosPregaoExcel(inMemoryModel, PREGAO_FILE_CONSOLIDADO);
        
        return inMemoryModel;
    }

    private void loadInformacoesEmpresas(Model model, String resourcePath) throws IOException {
        
        logger.info(">> Carregando Cadastro de Empresas de: {}", resourcePath);
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream(); Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String nomeEmpresa = getStringCellValue(row.getCell(0));
                String ticker = getStringCellValue(row.getCell(1));
                if (nomeEmpresa == null || ticker == null || nomeEmpresa.isBlank() || ticker.isBlank()) continue;

                String tickerClean = ticker.trim();
                String nomeEmpresaClean = nomeEmpresa.trim();

                Resource vmRes = model.createResource(ONT_PREFIX + tickerClean);
                addStatement(model, vmRes, RDF.type, model.createResource(ONT_PREFIX + "Valor_Mobiliario"));
                addStatement(model, vmRes, RDFS.label, model.createLiteral(tickerClean));
                addStatement(model, vmRes, model.createProperty(ONT_PREFIX, "ticker"), model.createLiteral(tickerClean));

                Resource empresaRes = model.createResource(ONT_PREFIX + normalizarParaURI(nomeEmpresaClean));
                addStatement(model, empresaRes, RDF.type, model.createResource(ONT_PREFIX + "Empresa_Capital_Aberto"));
                addStatement(model, empresaRes, RDFS.label, nomeEmpresaClean, "pt");

                addStatement(model, empresaRes, model.createProperty(ONT_PREFIX + "temValorMobiliarioNegociado"), vmRes);
                
                for (int i = 3; i <= 5; i++) {
                    String setor = getStringCellValue(row.getCell(i));
                    if (setor != null && !setor.isBlank()) {
                        Resource setorRes = model.createResource(ONT_PREFIX + normalizarParaURI(setor.trim()));
                        addStatement(model, setorRes, RDF.type, model.createResource(ONT_PREFIX + "Setor_Atuacao"));
                        addStatement(model, setorRes, RDFS.label, setor.trim(), "pt");
                        addStatement(model, empresaRes, model.createProperty(ONT_PREFIX, "atuaEm"), setorRes);
                    }
                }
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

                Date dataPregao = getDateCellValue(row.getCell(2));
                String ticker = getStringCellValue(row.getCell(4));
                
                if (ticker == null || !ticker.matches("^[A-Z]{4}\\d{1,2}$") || dataPregao == null) continue;
                
                String tickerTrim = ticker.trim();
                
                Resource valorMobiliario = model.createResource(ONT_PREFIX + tickerTrim);
                addStatement(model, valorMobiliario, RDF.type, model.createResource(ONT_PREFIX + "Valor_Mobiliario"));
                addStatement(model, valorMobiliario, RDFS.label, model.createLiteral(tickerTrim));

                String dataFmt = rdfDateFormat.format(dataPregao);
                Resource negociadoResource = model.createResource(ONT_PREFIX + tickerTrim + "_Negociado_" + dataFmt.replace("-", ""));
                addStatement(model, negociadoResource, RDF.type, model.createResource(ONT_PREFIX + "Negociado_Em_Pregao"));
                addStatement(model, valorMobiliario, model.createProperty(ONT_PREFIX + "negociado"), negociadoResource);

                Resource pregaoResource = model.createResource(ONT_PREFIX + "Pregao_" + dataFmt.replace("-", ""));
                addStatement(model, pregaoResource, RDF.type, model.createResource(ONT_PREFIX + "Pregao"));
                addStatement(model, pregaoResource, model.createProperty(ONT_PREFIX + "ocorreEmData"), model.createTypedLiteral(dataFmt, XSDDatatype.XSDdate));
                addStatement(model, negociadoResource, model.createProperty(ONT_PREFIX + "negociadoDurante"), pregaoResource);
                
                addNumericProperty(model, negociadoResource, model.createProperty(ONT_PREFIX, "precoAbertura"), getNumericCellValue(row.getCell(8)));
                addNumericProperty(model, negociadoResource, model.createProperty(ONT_PREFIX, "precoMaximo"), getNumericCellValue(row.getCell(9)));
                addNumericProperty(model, negociadoResource, model.createProperty(ONT_PREFIX, "precoMinimo"), getNumericCellValue(row.getCell(10)));
                addNumericProperty(model, negociadoResource, model.createProperty(ONT_PREFIX, "precoMedio"), getNumericCellValue(row.getCell(11)));
                addNumericProperty(model, negociadoResource, model.createProperty(ONT_PREFIX, "precoFechamento"), getNumericCellValue(row.getCell(12)));
                addNumericProperty(model, negociadoResource, model.createProperty(ONT_PREFIX, "totalNegocios"), getNumericCellValue(row.getCell(14)));
                addNumericProperty(model, negociadoResource, model.createProperty(ONT_PREFIX, "volumeNegociacao"), getNumericCellValue(row.getCell(15)));
            }
        }
    }

    
    public Model getInferredModel() {
        return this.model;
    }
    
   
    private String getStringCellValue(Cell cell) {
        if (cell == null) return null;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        switch (type) {
            case STRING: return cell.getStringCellValue().trim();
            case NUMERIC: 
                if (DateUtil.isCellDateFormatted(cell)) { return null; }
                double numericValue = cell.getNumericCellValue();
                if (numericValue == Math.floor(numericValue)) { return String.valueOf((long) numericValue); }
                return String.valueOf(numericValue);
            default: return null;
        }
    }
    private Date getDateCellValue(Cell cell) {
        if (cell == null) return null;
        if (cell.getCellType() == CellType.NUMERIC && DateUtil.isCellDateFormatted(cell)) return cell.getDateCellValue();
        if (cell.getCellType() == CellType.STRING) {
            for (String format : new String[]{"yyyy-MM-dd", "dd/MM/yyyy", "yyyyMMdd"}) {
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
    private String normalizarParaURI(String texto) {
        if (texto == null) return "";
        return Normalizer.normalize(texto.trim(), Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}+", "")
                .replaceAll("[^a-zA-Z0-9_ -]", "")
                .replaceAll("\\s+", "_")
                .replaceAll("/", "_");
    }
    private void addStatement(Model model, Resource s, Property p, RDFNode o) {
        if (s != null && p != null && o != null) { model.add(s, p, o); }
    }
    private void addStatement(Model model, Resource s, Property p, String o, String lang) {
        if (s != null && p != null && o != null && !o.isBlank()) { model.add(s, p, model.createLiteral(o, lang)); }
    }
    private void addNumericProperty(Model model, Resource s, Property p, double value) {
        if (!Double.isNaN(value)) { model.add(s, p, model.createTypedLiteral(value)); }
    }
    private void validateBaseModelLoad(long size) { if (size < 1000) logger.warn("MODELO BASE SUSPEITOSAMENTE PEQUENO ({}) APÓS CARREGAMENTO!", size); }

}
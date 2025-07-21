package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

@Component
public class Ontology {

    private static final Logger logger = LoggerFactory.getLogger(Ontology.class);
    private Model model;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    private static final String ONT_PREFIX = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";
    private static final String PREGAO_FILE = "datasets/stock_market_june 2025.xlsx";
    private static final String INFO_EMPRESAS_FILE = "Templates/Company_Information.xlsx";

    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização do Componente Ontology (@PostConstruct)...");
        lock.writeLock().lock();
        try {
            Model dataModel = ModelFactory.createDefaultModel();
            dataModel.setNsPrefix("b3", ONT_PREFIX);
            dataModel.setNsPrefix("rdfs", RDFS.uri);
            dataModel.setNsPrefix("xsd", XSDDatatype.XSD + "#");

            loadData(dataModel);

            // IMPORTANTE: Usamos o modelo de dados PURO, SEM INFERÊNCIA.
            this.model = dataModel;

            if (this.model.isEmpty()) {
                throw new IllegalStateException("FALHA CRÍTICA: O modelo RDF foi criado vazio.");
            }
            logger.info("<<< Ontology INICIALIZADA COM SUCESSO. Total de triplas no modelo: {} >>>", this.model.size());
        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE E IRRECUPERÁVEL NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
            throw new RuntimeException("Falha crítica ao inicializar a camada de ontologia.", e);
        } finally {
            lock.writeLock().unlock();
        }
    }
    
    private void loadData(Model model) throws IOException {
        // Passo A: Mapeia Ticker -> Setores e Ticker -> Nome Canônico da Empresa
        Map<String, Set<String>> tickerToSectorMap = new HashMap<>();
        Map<String, String> tickerToCompanyNameMap = new HashMap<>();
        logger.info(">> Carregando metadados de Empresas de: {}", INFO_EMPRESAS_FILE);
        try (InputStream excelFile = new ClassPathResource(INFO_EMPRESAS_FILE).getInputStream(); Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String nomeEmpresa = getStringCellValue(row.getCell(0));
                String ticker = getStringCellValue(row.getCell(1));
                if (ticker != null && !ticker.isBlank() && nomeEmpresa != null && !nomeEmpresa.isBlank()) {
                    tickerToCompanyNameMap.put(ticker.trim(), nomeEmpresa.trim());
                    Set<String> setores = new HashSet<>();
                    for (int i = 3; i <= 5; i++) {
                        String setor = getStringCellValue(row.getCell(i));
                        if (setor != null && !setor.isBlank()) {
                            setores.add(setor.trim());
                        }
                    }
                    tickerToSectorMap.put(ticker.trim(), setores);
                }
            }
        }
        
        // Passo B: Processa a planilha de pregão e cria um grafo simples e limpo
        logger.info(">> Carregando Dados de Pregão de: {}", PREGAO_FILE);
        try (InputStream excelFile = new ClassPathResource(PREGAO_FILE).getInputStream(); Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            SimpleDateFormat rdfDateFormat = new SimpleDateFormat("yyyy-MM-dd");

            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;

                Date dataPregao = getDateCellValue(row.getCell(2)); // Coluna C
                String ticker = getStringCellValue(row.getCell(4)); // Coluna E
                
                if (ticker == null || !ticker.matches("^[A-Z]{4}\\d{1,2}$") || dataPregao == null) continue;
                
                String tickerTrim = ticker.trim();
                String dataFmt = rdfDateFormat.format(dataPregao);
                
                // Cria um ÚNICO nó para cada linha do pregão. A estrutura é plana e simples.
                Resource pregaoNode = model.createResource(ONT_PREFIX + tickerTrim + "_" + dataFmt);
                
                pregaoNode.addProperty(RDF.type, model.createResource(ONT_PREFIX + "RegistroDePregao"));
                pregaoNode.addProperty(model.createProperty(ONT_PREFIX, "ticker"), tickerTrim);
                pregaoNode.addProperty(model.createProperty(ONT_PREFIX, "ocorreEmData"), model.createTypedLiteral(dataFmt, XSDDatatype.XSDdate));
                
                // Usa o mapa para adicionar o nome canônico da empresa
                String nomeEmpresa = tickerToCompanyNameMap.getOrDefault(tickerTrim, getStringCellValue(row.getCell(6)));
                if (nomeEmpresa != null) {
                    pregaoNode.addProperty(model.createProperty(ONT_PREFIX, "nomeEmpresa"), nomeEmpresa);
                }
                
                // Usa o mapa para adicionar os setores
                if (tickerToSectorMap.containsKey(tickerTrim)) {
                    for (String setor : tickerToSectorMap.get(tickerTrim)) {
                        pregaoNode.addProperty(model.createProperty(ONT_PREFIX, "atuaEmSetor"), setor);
                    }
                }
                
                // Adiciona todas as métricas de preço diretamente ao nó
                addNumericProperty(pregaoNode, model.createProperty(ONT_PREFIX, "precoAbertura"), getNumericCellValue(row.getCell(8)));
                addNumericProperty(pregaoNode, model.createProperty(ONT_PREFIX, "precoMaximo"), getNumericCellValue(row.getCell(9)));
                addNumericProperty(pregaoNode, model.createProperty(ONT_PREFIX, "precoMinimo"), getNumericCellValue(row.getCell(10)));
                addNumericProperty(pregaoNode, model.createProperty(ONT_PREFIX, "precoMedio"), getNumericCellValue(row.getCell(11)));
                addNumericProperty(pregaoNode, model.createProperty(ONT_PREFIX, "precoFechamento"), getNumericCellValue(row.getCell(12)));
                addNumericProperty(pregaoNode, model.createProperty(ONT_PREFIX, "quantidade"), getNumericCellValue(row.getCell(14)));
                addNumericProperty(pregaoNode, model.createProperty(ONT_PREFIX, "volume"), getNumericCellValue(row.getCell(15)));
            }
        }
    }
    
    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            if (this.model == null) { logger.error("Tentativa de executar consulta em um modelo nulo."); return Collections.emptyList(); }
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
            lock.readLock().unlock();
        }
    }

    // Métodos auxiliares
    private String getStringCellValue(Cell cell) {
        if (cell == null) return null;
        if (cell.getCellType() == CellType.STRING) return cell.getStringCellValue().trim();
        if (cell.getCellType() == CellType.NUMERIC) {
            if (DateUtil.isCellDateFormatted(cell)) return null;
            return String.valueOf(cell.getNumericCellValue());
        }
        return null;
    }
    private Date getDateCellValue(Cell cell) {
        if (cell == null) return null;
        if (cell.getCellType() == CellType.NUMERIC && DateUtil.isCellDateFormatted(cell)) return cell.getDateCellValue();
        if (cell.getCellType() == CellType.STRING) {
            try { return new SimpleDateFormat("yyyy-MM-dd").parse(cell.getStringCellValue().trim()); } catch (ParseException ignored) {}
            try { return new SimpleDateFormat("dd/MM/yyyy").parse(cell.getStringCellValue().trim()); } catch (ParseException ignored) {}
        }
        return null;
    }
    private double getNumericCellValue(Cell cell) {
        if (cell == null) return Double.NaN;
        if (cell.getCellType() == CellType.NUMERIC) return cell.getNumericCellValue();
        if (cell.getCellType() == CellType.STRING) {
            try { return Double.parseDouble(cell.getStringCellValue().trim().replace(",", ".")); } catch (NumberFormatException e) { return Double.NaN; }
        }
        return Double.NaN;
    }
    private void addNumericProperty(Resource res, Property p, double value) {
        if (res != null && p != null && !Double.isNaN(value)) {
            res.addProperty(p, model.createTypedLiteral(value));
        }
    }

    public Model getInferredModel() { return this.model; }
}
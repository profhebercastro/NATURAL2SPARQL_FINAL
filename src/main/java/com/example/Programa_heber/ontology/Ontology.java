// -----------------------------------------------------------------
// ARQUIVO: Ontology.java (VERSÃO FINAL E COMPLETA, CORRIGIDA v3)
// -----------------------------------------------------------------
package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
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

    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização do Componente Ontology (@PostConstruct)...");
        lock.writeLock().lock();
        try {
            logger.warn("--- Construindo modelo RDF em memória a partir das fontes de dados (Excel)... ---");
            Model baseModel = buildBaseModelFromSources();
            validateBaseModelLoad(baseModel.size());

            logger.info("Aplicando RDFS reasoner para inferência...");
            Reasoner reasoner = ReasonerRegistry.getRDFSReasoner();
            this.infModel = ModelFactory.createInfModel(reasoner, baseModel);
            
            long inferredCount = this.infModel.size() - baseModel.size();
            logger.info("--- Modelo de inferência criado. Triplas Base: {}, Inferidas: {}, Total: {} ---", baseModel.size(), Math.max(0, inferredCount), this.infModel.size());
            
            if (this.infModel == null || this.infModel.isEmpty()) {
                throw new IllegalStateException("FALHA CRÍTICA: O modelo de inferência RDF não pôde ser criado ou está vazio.");
            }
            logger.info("<<< Ontology INICIALIZADA COM SUCESSO. >>>");
        
        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE E IRRECUPERÁVEL NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
            throw new RuntimeException("Falha crítica ao inicializar a camada de ontologia.", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    private Model buildBaseModelFromSources() throws IOException {
        Model model = ModelFactory.createDefaultModel();
        model.setNsPrefix("b3", ONT_PREFIX);
        model.setNsPrefix("rdfs", RDFS.uri);
        model.setNsPrefix("xsd", XSDDatatype.XSD + "#");

        loadInformacoesEmpresas(model, INFO_EMPRESAS_FILE);
        for (String filePath : PREGAO_FILES) {
            loadDadosPregaoExcel(model, filePath);
        }
        return model;
    }
    
    private void loadInformacoesEmpresas(Model model, String resourcePath) throws IOException {
        logger.info(">> Carregando Cadastro de Empresas de: {}", resourcePath);
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream(); Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String nomeEmpresa = getStringCellValue(row.getCell(0));
                String ticker = getStringCellValue(row.getCell(1));
                String setor = getStringCellValue(row.getCell(2));
                
                if (nomeEmpresa == null || nomeEmpresa.trim().isEmpty() || ticker == null || ticker.trim().isEmpty()) continue;

                Resource empresaRes = model.createResource(ONT_PREFIX + normalizarParaURI(nomeEmpresa.trim()));
                addStatement(model, empresaRes, RDF.type, model.createResource(ONT_PREFIX + "Empresa"));
                addStatement(model, empresaRes, RDFS.label, nomeEmpresa.trim(), "pt");

                Resource vmRes = model.createResource(ONT_PREFIX + ticker.trim());
                addStatement(model, vmRes, RDF.type, model.createResource(ONT_PREFIX + "Valor_Mobiliario"));
                addStatement(model, vmRes, model.createProperty(ONT_PREFIX, "ticker"), ticker.trim()); // Esta linha é o foco do erro

                addStatement(model, empresaRes, model.createProperty(ONT_PREFIX, "temValorMobiliarioNegociado"), vmRes);

                if (setor != null && !setor.trim().isEmpty()){
                    Resource setorRes = model.createResource(ONT_PREFIX + normalizarParaURI(setor.trim()));
                    addStatement(model, setorRes, RDF.type, model.createResource(ONT_PREFIX + "Setor_Atuacao"));
                    addStatement(model, setorRes, RDFS.label, setor.trim(), "pt");
                    addStatement(model, empresaRes, model.createProperty(ONT_PREFIX, "atuaEm"), setorRes);
                }
            }
        }
        logger.info(">> Cadastro de Empresas carregado. Triplas atuais: {}", model.size());
    }

    private void loadDadosPregaoExcel(Model model, String resourcePath) throws IOException {
        logger.info(">> Carregando Dados de Pregão de: {}", resourcePath);
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream(); Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            SimpleDateFormat rdfDateFormat = new SimpleDateFormat("yyyy-MM-dd");
            
            Map<Integer, Property> propertyMap = Map.of(
                5, model.createProperty(ONT_PREFIX, "precoAbertura"),
                11, model.createProperty(ONT_PREFIX, "precoFechamento"),
                6, model.createProperty(ONT_PREFIX, "precoMaximo"),
                7, model.createProperty(ONT_PREFIX, "precoMinimo"),
                8, model.createProperty(ONT_PREFIX, "precoMedio"),
                14, model.createProperty(ONT_PREFIX, "volumeNegociacao")
            );

            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;
                String ticker = getStringCellValue(row.getCell(3));
                Date dataPregao = getDateCellValue(row.getCell(1));
                
                if (ticker == null || !ticker.matches("^[A-Z]{4}\\d{1,2}$") || dataPregao == null) continue;

                Resource valorMobiliario = model.getResource(ONT_PREFIX + ticker.trim());
                if(!model.contains(valorMobiliario, RDF.type)) continue;

                String dataFmt = rdfDateFormat.format(dataPregao);
                Resource negociadoRes = model.createResource(ONT_PREFIX + "Negociado_" + ticker.trim() + "_" + dataFmt);
                addStatement(model, negociadoRes, RDF.type, model.createResource(ONT_PREFIX + "Negociado_Em_Pregao"));

                addStatement(model, valorMobiliario, model.createProperty(ONT_PREFIX, "negociado"), negociadoRes);

                Resource pregaoRes = model.createResource(ONT_PREFIX + "Pregao_" + dataFmt);
                addStatement(model, pregaoRes, RDF.type, model.createResource(ONT_PREFIX + "Pregao"));
                addStatement(model, pregaoRes, model.createProperty(ONT_PREFIX, "ocorreEmData"), model.createTypedLiteral(dataFmt, XSDDatatype.XSDdate));
                addStatement(model, negociadoRes, model.createProperty(ONT_PREFIX, "negociadoDurante"), pregaoRes);

                for(Map.Entry<Integer, Property> entry : propertyMap.entrySet()){
                    double numericValue = getNumericCellValue(row.getCell(entry.getKey()));
                    if (!Double.isNaN(numericValue)){
                        addStatement(model, negociadoRes, entry.getValue(), model.createTypedLiteral(numericValue));
                    }
                }
            }
        }
         logger.info(">> Dados de Pregão de '{}' carregados. Total de triplas agora: {}", resourcePath, model.size());
    }

    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            if (infModel == null) {
                 logger.warn("Tentativa de executar query com modelo nulo!");
                 return Collections.emptyList();
            }
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
            logger.error("Erro durante a execução da consulta SPARQL: {}", sparqlQuery, e);
            return Collections.emptyList();
        } finally {
            lock.readLock().unlock();
        }
    }

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
        if (cell.getCellType() == CellType.FORMULA) {
            try {
                return cell.getNumericCellValue();
            } catch (IllegalStateException e){
                try {
                    return Double.parseDouble(cell.getStringCellValue().trim().replace(",", "."));
                } catch(NumberFormatException nfe){
                    return Double.NaN;
                }
            }
        }
        if (cell.getCellType() == CellType.NUMERIC) return cell.getNumericCellValue();
        if (cell.getCellType() == CellType.STRING) {
            try { return Double.parseDouble(cell.getStringCellValue().trim().replace(",", ".")); } catch (NumberFormatException e) { return Double.NaN; }
        }
        return Double.NaN;
    }

    private String normalizarParaURI(String texto) {
        if (texto == null) return "";
        return Normalizer.normalize(texto.trim(), Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}+", "")
                .replaceAll("[^a-zA-Z0-9_\\s-]", "")
                .replaceAll("[\\s-]+", "_");
    }

    // --- MÉTODOS HELPER CORRIGIDOS ---
    private void addStatement(Model model, Resource s, Property p, RDFNode o) { if (s != null && p != null && o != null) model.add(s, p, o); }
    private void addStatement(Model model, Resource s, Property p, String o, String lang) { if (s != null && p != null && o != null && !o.isEmpty()) model.add(s, p, o, lang); }
    
    // --- NOVO MÉTODO ADICIONADO PARA CORRIGIR O ERRO ---
    private void addStatement(Model model, Resource s, Property p, String o) { 
        if (s != null && p != null && o != null && !o.isEmpty()) {
            model.add(s, p, o);
        }
    }
    
    private void validateBaseModelLoad(long size) { if (size < 1000) logger.warn("MODELO BASE SUSPEITOSAMENTE PEQUENO ({}) APÓS CARREGAMENTO!", size); }

}
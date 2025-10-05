# STJ Scraper

STJ Scraper é um sistema de extração de decisões jurídicas do Superior Tribunal de Justiça (STJ) através do sistema SCON. O projeto segue exatamente a mesma arquitetura do STF Scraper, mas adaptado para funcionar com o STJ.

## Características Principais

- **Arquitetura Espelhada**: Replica exatamente a estrutura do STF Scraper
- **3 Workers Paralelos**: Processamento concorrente com isolamento de contextos
- **Extração de Textarea**: Captura texto integral do elemento `<textarea id="textSemformatacao1">`
- **Sistema SCON**: Otimizado para o sistema de consulta do STJ
- **Saída Padronizada**: Mesmo formato JSON do STF com fonte diferenciada

## Instalação

### Dependências

Este projeto requer as mesmas dependências do STF Scraper:

```bash
# Instalar dependências do projeto principal
cd /path/to/RAG-TCC
pip install -r requirements.txt

# Ou usar poetry (recomendado)
poetry install
```

### Dependências Principais
- Python 3.8+
- Scrapy
- scrapy-playwright
- Playwright (com navegador Chromium)

## Estrutura do Projeto

```
stj_scraper/
├── scrapy.cfg                 # Configuração do Scrapy
├── manage.py                  # Gerenciador de filas (3 workers)
├── stj_queue_manager.py       # Sistema de filas thread-safe
├── data/
│   └── simple_query_spider/
│       └── query_links.json   # Consultas de entrada (mesmo formato STF)
├── logs/
│   └── scrapy.log            # Logs de execução
├── stj_scraper/
│   ├── __init__.py
│   ├── items.py              # Definições de itens (adaptado STJ)
│   ├── middlewares.py        # Middlewares
│   ├── pipelines.py          # Pipelines (validação, JSON, stats)
│   ├── settings.py           # Configurações (3 workers habilitados)
│   ├── spiders/
│   │   ├── __init__.py
│   │   └── stj_jurisprudencia.py  # Spider principal
│   └── utils/
│       ├── stj_selectors.py  # Seletores XPath/CSS para STJ
│       └── stj_parsers.py    # Regex e parsers para metadados
└── temp_queue/               # Arquivos temporários (auto-limpeza)
```

## Uso

### Execução com 3 Workers (Recomendado)

```bash
cd stj_scraper

# Execução com 3 workers paralelos
python manage.py concurrent --workers 3

# Com browser visível (debug)
python manage.py concurrent --workers 3 --show-browser

# Com número personalizado de workers
python manage.py concurrent --workers 5
```

### Execução Sequencial

```bash
# Execução sequencial (1 worker)
python manage.py sequential

# Com browser visível
python manage.py sequential --show-browser
```

### Monitoramento

```bash
# Ver status da fila
python manage.py status

# Limpar arquivos de fila
python manage.py cleanup
```

### Execução Direta do Spider

```bash
# Execução direta (sem sistema de filas)
scrapy crawl stj_jurisprudencia

# Com arquivo de consultas personalizado
scrapy crawl stj_jurisprudencia -a query_file=/path/to/custom_queries.json

# Modo desenvolvimento (limitado a 5 itens)
scrapy crawl stj_jurisprudencia -s ENV=development
```

## Formato de Entrada

O sistema usa o mesmo formato JSON do STF Scraper. Exemplo:

```json
[
  {
    "query": "peculato culposo artigo 312",
    "artigo": "312", 
    "url": "https://scon.stj.jus.br/SCON/pesquisar.jsp?b=DTXT&numDocsPagina=50&i=1&livre=peculato+culposo+artigo+312&..."
  }
]
```

## Formato de Saída

Mesmo esquema do STF, diferenciado pela fonte:

```json
{
  "source": "stj_scraper",
  "tribunal": "STJ", 
  "cluster_name": "art_312",
  "cluster_description": "peculato culposo artigo 312 (art. 312 do Código Penal)",
  "article_reference": "CP art. 312",
  "title": "STJ Decision 1 - Article 312",
  "case_number": "ARESP 1234567",
  "classe_processual_unificada": "AGRAVO EM RECURSO ESPECIAL",
  "content": "SUPERIOR TRIBUNAL DE JUSTIÇA...",
  "raw_text": "Texto extraído do textarea #textSemformatacao1...",
  "url": "https://scon.stj.jus.br/SCON/verDecisao.asp?...",
  "tribunal": "STJ",
  "legal_area": "Penal",
  "relator": "MINISTRO JOÃO DA SILVA",
  "publication_date": "15/03/2023",
  "decision_date": "10/03/2023", 
  "partes": "RECORRENTE: JOÃO; RECORRIDO: ESTADO",
  "captured_at_utc": "2023-03-20T10:30:45Z",
  "success": true,
  "errors": null,
  "input_url": "https://scon.stj.jus.br/SCON/pesquisar.jsp?...",
  "decision_url": "https://scon.stj.jus.br/SCON/verDecisao.asp?...",
  "content_quality": 95
}
```

## Arquivos de Saída

Os dados são organizados por artigo:

```
data/
└── stj_jurisprudencia/
    ├── art_312/
    │   └── art_312_stj_jurisprudencia_20250320_143025.jsonl
    ├── art_323/
    │   └── art_323_stj_jurisprudencia_20250320_143026.jsonl
    └── scraping_stats.json
```

## Configurações de Concorrência

### 3 Workers (Padrão)
- `CONCURRENT_REQUESTS = 3`
- `CONCURRENT_REQUESTS_PER_DOMAIN = 3` 
- `PLAYWRIGHT_MAX_CONTEXTS = 3`
- `AUTOTHROTTLE_TARGET_CONCURRENCY = 3.0`

### Delays e Politeness
- `DOWNLOAD_DELAY = 3` segundos
- `RANDOMIZE_DOWNLOAD_DELAY = 0.5`
- `RETRY_TIMES = 3`
- Backoff exponencial para HTTP 429

## Diferenças em Relação ao STF

| Aspecto | STF | STJ |
|---------|-----|-----|
| **Domínio** | jurisprudencia.stf.jus.br | scon.stj.jus.br |
| **Sistema** | Portal STF | SCON |
| **Extração** | Clipboard API | Textarea #textSemformatacao1 |
| **Fonte** | stf_scraper | stj_scraper |
| **Tribunal** | STF | STJ |
| **Workers** | 1 (sequencial) | 3 (paralelo) |
| **Classes** | HC, ARE, RE, RHC, MC | ARESP, RESP, RHC, HC, MS, MC |

## Logs e Debug

```bash
# Ver logs em tempo real
tail -f logs/scrapy.log

# Verificar estatísticas
cat data/scraping_stats.json | jq .

# Debug com browser visível
python manage.py concurrent --workers 1 --show-browser
```

## Critérios de Qualidade

O pipeline de validação avalia:
- **URL**: Deve conter scon.stj.jus.br (25 pts)
- **Relator**: Nome de ministro válido (25 pts)  
- **Título**: Contém siglas STJ (ARESP, RESP, etc.) (25 pts)
- **Conteúdo**: Texto > 500 chars com indicadores STJ (25 pts)

Itens com qualidade < 30 são descartados.

## Troubleshooting

### Textarea Não Encontrado
Se o seletor `#textSemformatacao1` não funcionar:
1. Verificar se a página tem o elemento
2. Tentar seletores alternativos em `stj_selectors.py`
3. Usar fallback para qualquer `<textarea>`

### Workers Não Inicializam  
```bash
# Limpar estado de fila
python manage.py cleanup

# Verificar dependências
python -c "import scrapy_playwright; print('OK')"
```

### Rate Limiting
Se receber HTTP 429:
- Aumentar `DOWNLOAD_DELAY`
- Reduzir `CONCURRENT_REQUESTS`
- Ativar `AUTOTHROTTLE_DEBUG = True`

## Exemplo de Teste de Fumaça

```bash
# Teste rápido (1 query, 1 decisão)
python manage.py concurrent --workers 1
echo "Verificando saída..."
find data/ -name "*.jsonl" | head -1 | xargs head -1 | jq '.raw_text | length'
# Deve retornar > 0 se extraiu texto
```

## Contribuição

Mantenha a paridade com o STF Scraper:
1. Mesma estrutura de arquivos
2. Mesmo padrão de nomenclatura
3. Mesmo formato de saída (apenas mude source/tribunal)
4. Mesma qualidade de logs e documentação
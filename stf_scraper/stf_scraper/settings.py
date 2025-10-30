# Scrapy settings for stf_scraper project
# ---------------------------------------
# Este arquivo centraliza todas as configurações do projeto.
# Ele foi ajustado para funcionar tanto com spiders normais (STF)
# quanto com spiders que usam Playwright (SEEU).

BOT_NAME = "stf_scraper"

SPIDER_MODULES = ["stf_scraper.spiders"]
NEWSPIDER_MODULE = "stf_scraper.spiders"

# -------------------------------------------------------------
# ⚙️ Configurações gerais
# -------------------------------------------------------------
ROBOTSTXT_OBEY = False
DOWNLOAD_DELAY = 1.0  # Evita sobrecarregar os servidores
CONCURRENT_REQUESTS = 8
LOG_LEVEL = "INFO"

# -------------------------------------------------------------
# 🧠 Pipelines e processamento de itens
# -------------------------------------------------------------
ITEM_PIPELINES = {
    # Exemplo: 'stf_scraper.pipelines.JsonWriterPipeline': 300,
}

# -------------------------------------------------------------
# 🌐 scrapy-playwright: Integração com navegador real
# -------------------------------------------------------------
# Essas configurações habilitam o uso do Playwright
# apenas quando o spider usa meta={"playwright": True}

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Permite execução assíncrona (obrigatório para Playwright)
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Define o tipo de navegador (pode ser "chromium", "firefox" ou "webkit")
PLAYWRIGHT_BROWSER_TYPE = "chromium"

# Timeout padrão de 30 segundos
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000

# Não fecha o navegador a cada requisição (melhor desempenho)
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,  # Mude para False se quiser ver o navegador abrindo
}

# -------------------------------------------------------------
# 🧱 Armazenamento de dados
# -------------------------------------------------------------
# Pasta onde os spiders salvam os arquivos coletados (JSON, etc)
FEEDS = {
    "data/%(name)s/%(time)s.json": {
        "format": "json",
        "encoding": "utf8",
        "store_empty": False,
        "indent": 4,
    },
}

# -------------------------------------------------------------
# 🧩 Extras úteis
# -------------------------------------------------------------
# Evita bloqueios e melhora compatibilidade com sites modernos
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}

ITEM_PIPELINES = {
    "stf_scraper.pipelines.JsonWriterPipeline": 300,  # novo pipeline
}


# -------------------------------------------------------------
# ✅ Observação final
# -------------------------------------------------------------
# - O spider do STF (scrapy puro) continuará funcionando normalmente.
# - O spider do SEEU usará automaticamente o Playwright para renderizar as páginas.
# - Tudo foi configurado para rodar dentro do mesmo projeto sem conflito.

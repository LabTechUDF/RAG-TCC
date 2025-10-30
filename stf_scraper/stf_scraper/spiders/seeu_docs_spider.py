import scrapy
from scrapy_playwright.page import PageMethod


class SeeuDocsSpider(scrapy.Spider):
    name = "seeu_docs"
    allowed_domains = ["docs.seeu.pje.jus.br"]
    start_urls = ["https://docs.seeu.pje.jus.br/docs/intro/"]

    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "FEEDS": {
            "data/seeu_docs.json": {
                "format": "json",
                "encoding": "utf8",
                "overwrite": True,
            }
        },
    }

    async def parse(self, response):
        """Captura todos os links de documentos e segue para cada um."""
        self.logger.info("Página inicial carregada: %s", response.url)

        # Seleciona todos os links internos que apontam para páginas de docs
        links = response.css("a::attr(href)").getall()
        for link in links:
            if link and link.startswith("/docs/"):
                url = response.urljoin(link)
                yield scrapy.Request(
                    url,
                    callback=self.parse_doc,
                    meta=dict(
                        playwright=True,
                        playwright_page_methods=[
                            PageMethod("wait_for_selector", "main"),
                            PageMethod("wait_for_timeout", 2000),
                        ],
                    ),
                )

    async def parse_doc(self, response):
        """Extrai título e conteúdo principal de cada documento."""
        title = response.css("h1::text").get()
        paragraphs = response.css("main p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p.strip())

        yield {
            "url": response.url,
            "title": title or "Sem título",
            "content": content or "Sem conteúdo",
        }

        self.logger.info(f"✅ Documento salvo: {title or response.url}")

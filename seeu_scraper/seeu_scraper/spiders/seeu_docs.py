import scrapy

class SeeuDocsSpider(scrapy.Spider):
    name = "seeu_docs"
    start_urls = ["https://docs.seeu.pje.jus.br/docs/category/guias-de-uso-para-o-seeu/"]

    # 👉 Define a ordem dos campos no JSON exportado
    custom_settings = {
        'FEED_EXPORT_FIELDS': ['cluster_name', 'title', 'content', 'url']
    }

    def parse(self, response):
        # Extrai os links das categorias e subpáginas
        for link in response.css("a::attr(href)").getall():
            if link.startswith("/docs/"):
                yield response.follow(link, callback=self.parse_page)

    def parse_page(self, response):
        # Garante o formato e a ordem que você quer
        yield {
            "cluster_name": "Documentos de suporte SEEU",
            "title": response.css("h1::text").get(),
            "content": " ".join(response.css("p::text").getall()).strip(),
            "url": response.url
        }

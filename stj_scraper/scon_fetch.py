#!/usr/bin/env python3
"""
Baixa o inteiro teor de acórdãos do STJ pelo SCON com uma pessoa no circuito.

O SCON fica atrás de um desafio do Cloudflare ("Confirme que é humano"). Este script NÃO tenta
contorná-lo: abre um Chromium visível na tela do usuário, espera a pessoa marcar a verificação
e só então busca cada processo, baixa o PDF do inteiro teor pela mesma sessão (com intervalo entre
requisições) e extrai o texto com pdftotext.

Uso:
    DISPLAY=:0 python3 scon_fetch.py --processo "REsp 1365279" --processo "REsp 2104116" \
        --out /home/tupan/rag-tcc-exports/juridico/stj_scon
    python3 scon_fetch.py --file processos.txt   # um processo por linha
Saída: <out>/pdf/<registro>.pdf, <out>/txt/<registro>.txt e <out>/scon_inteiro_teor.jsonl (com sha256).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin

from playwright.sync_api import sync_playwright

BASE = "https://scon.stj.jus.br"
PROFILE_DIR = Path(__file__).parent / "data" / "scon" / "profile"


def results_url(livre: str) -> str:
    return (f"{BASE}/SCON/pesquisar.jsp?preConsultaPP=&acao=pesquisar&novaConsulta=true&i=1&b=ACOR&livre={quote(livre)}"
            "&filtroPorOrgao=&filtroPorMinistro=&filtroPorNota=&data=&tipo_visualizacao=&tp=T&processo=&classe=&uf="
            "&relator=&dtpb=&dtpb1=&dtpb2=&dtde=&dtde1=&dtde2=&orgao=&ementa=&nota=&ref=")


def norm_processo(text: str) -> str:
    """'REsp 1.365.279/SP' -> 'RESP 1365279'."""
    text = re.sub(r"/\s*[A-Z]{2}\b", "", text.upper())
    m = re.match(r"^\s*(.+?)\s+([\d.]+)\s*$", text.strip())
    return f"{re.sub(r'\\s+', '', m.group(1))} {m.group(2).replace('.', '')}" if m else text.strip()


def field(doc, title: str) -> str:
    loc = doc.locator(f".paragrafoBRS:has(> .docTitulo:text-is('{title}')) .docTexto")
    return re.sub(r"\s+", " ", loc.first.inner_text()).strip() if loc.count() else ""


def parse_documents(page):
    docs = []
    for doc in page.locator(".listadocumentos .documento").all():
        ita = doc.locator("a[href*='GetInteiroTeorDoAcordao']")
        href = ita.first.get_attribute("href") if ita.count() else ""
        m = re.search(r"inteiro_teor\('([^']+)'\)", href or "")
        ementa = doc.locator("textarea.textareaSemformatacao")
        docs.append({
            "identificacao": doc.locator(".clsIdentificacaoDocumento").first.inner_text().strip(),
            "processo": field(doc, "Processo"),
            "relator": field(doc, "Relator") or field(doc, "Relatora"),
            "orgao_julgador": field(doc, "Órgão Julgador"),
            "data_julgamento": field(doc, "Data do Julgamento"),
            "publicacao": field(doc, "Data da Publicação/Fonte"),
            "ementa": ementa.first.input_value().strip() if ementa.count() else "",
            "acordao": field(doc, "Acórdão"),
            "referencia_legislativa": field(doc, "Referência Legislativa"),
            "jurisprudencia_citada": field(doc, "Jurisprudência Citada"),
            "inteiro_teor_path": m.group(1).replace("&amp;", "&") if m else None,
        })
    return docs


def wait_for_results(page, timeout_s: int) -> str:
    """'docs' quando há resultados, 'empty' quando a busca não achou nada, '' se esgotou o tempo."""
    for _ in range(max(1, timeout_s // 2)):
        if page.locator(".listadocumentos .documento").count():
            return "docs"
        body = page.content()
        if "Nenhum documento encontrado" in body or re.search(r"numDocs\">\s*0\b", body):
            return "empty"
        time.sleep(2)
    return ""


def fetch_pdf(context, page, ita_path: str) -> tuple:
    """Baixa o inteiro teor pela sessão do navegador; se vier uma página HTML, segue o link/iframe do PDF."""
    url = urljoin(BASE, ita_path)
    resp = context.request.get(url, timeout=120000)
    body = resp.body()
    if body[:4] == b"%PDF":
        return body, resp.url
    html = body.decode("utf-8", errors="replace")
    for candidate in re.findall(r'(?:src|href)="([^"]+)"', html):
        if re.search(r"\.pdf|mediado|documento|ITA", candidate, flags=re.I):
            inner = context.request.get(urljoin(resp.url, candidate.replace("&amp;", "&")), timeout=120000)
            if inner.body()[:4] == b"%PDF":
                return inner.body(), inner.url
    # último recurso: abrir na aba e capturar o download/PDF
    with page.expect_download(timeout=60000) as dl:
        page.goto(url)
    path = dl.value.path()
    data = Path(path).read_bytes()
    return (data if data[:4] == b"%PDF" else b""), url


def pdf_to_text(pdf: Path, txt: Path) -> str:
    subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), str(txt)], check=True)
    return txt.read_text(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description="Inteiro teor do STJ via SCON (verificação humana)")
    ap.add_argument("--processo", action="append", default=[], help='Ex.: "REsp 1365279" (repetível)')
    ap.add_argument("--file", help="Arquivo com um processo por linha")
    ap.add_argument("--out", required=True, help="Pasta de saída")
    ap.add_argument("--human-timeout", type=int, default=600, help="Segundos para a pessoa concluir a verificação")
    ap.add_argument("--delay", type=float, default=5.0, help="Segundos entre processos")
    args = ap.parse_args()

    processos = list(args.processo)
    if args.file:
        processos += [l.strip() for l in Path(args.file).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    if not processos:
        sys.exit("informe --processo ou --file")

    out = Path(args.out)
    (out / "pdf").mkdir(parents=True, exist_ok=True)
    (out / "txt").mkdir(parents=True, exist_ok=True)
    manifest_path = out / "scon_inteiro_teor.jsonl"
    done = set()
    if manifest_path.exists():
        # só conta como feito o que foi baixado; timeouts e falhas são tentados de novo
        done = {r["requested"] for r in (json.loads(l) for l in manifest_path.read_text(encoding="utf-8").splitlines() if l.strip())
                if r.get("status") == "ok"}
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False, locale="pt-BR",
                                                        viewport={"width": 1280, "height": 900}, accept_downloads=True)
        page = context.pages[0] if context.pages else context.new_page()
        first = True
        for requested in processos:
            if requested in done:
                print(f"⏭️  {requested}: já baixado", flush=True)
                continue
            target = norm_processo(requested)
            number = target.split(" ")[-1]
            page.goto(results_url(number), wait_until="domcontentloaded", timeout=120000)
            if first:
                page.bring_to_front()
                shot = out / "scon_waiting_verification.png"
                page.screenshot(path=str(shot))
                print(f">>> Janela do Chromium aberta: marque 'Confirme que é humano'. Tela atual salva em {shot}", flush=True)
            state = ""
            waited = 0
            limit_s = args.human_timeout if first else 90
            while waited < limit_s and not state:
                state = wait_for_results(page, min(60, limit_s - waited))
                waited += 60
                if not state and first:
                    print(f"... aguardando a verificação humana ({waited}s de {limit_s}s)", flush=True)
            if first and state == "":
                print("❌ verificação não concluída — nada foi registrado; rode de novo quando alguém puder marcar a caixa", flush=True)
                context.close()
                sys.exit(2)
            first = False
            record = {"requested": requested, "target": target, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if state != "docs":
                record["status"] = "no_results" if state == "empty" else "verification_timeout"
                print(f"❌ {requested}: {record['status']}", flush=True)
            else:
                docs = parse_documents(page)
                match = next((d for d in docs if norm_processo(d["identificacao"]) == target), None)
                if not match or not match["inteiro_teor_path"]:
                    record["status"] = "not_found_in_results"
                    record["results_seen"] = [d["identificacao"] for d in docs]
                    print(f"❌ {requested}: não está nos resultados ({record['results_seen'][:5]})", flush=True)
                else:
                    registro = re.search(r"num_registro=(\d+)", match["inteiro_teor_path"]).group(1)
                    pdf_bytes, source_url = fetch_pdf(context, page, match["inteiro_teor_path"])
                    record.update({k: v for k, v in match.items() if k != "inteiro_teor_path"})
                    record.update({"num_registro": registro, "inteiro_teor_url": urljoin(BASE, match["inteiro_teor_path"])})
                    if not pdf_bytes:
                        record["status"] = "pdf_not_obtained"
                        print(f"❌ {requested}: PDF não obtido", flush=True)
                    else:
                        pdf = out / "pdf" / f"{registro}.pdf"
                        pdf.write_bytes(pdf_bytes)
                        text = pdf_to_text(pdf, out / "txt" / f"{registro}.txt")
                        record.update({"status": "ok", "pdf_file": str(pdf), "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                                       "text_file": str(out / "txt" / f"{registro}.txt"), "text_chars": len(text),
                                       "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "source_url": source_url})
                        print(f"✅ {requested}: {len(pdf_bytes)} bytes PDF, {len(text)} caracteres", flush=True)
            with open(manifest_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            time.sleep(args.delay)
        context.close()


if __name__ == "__main__":
    main()

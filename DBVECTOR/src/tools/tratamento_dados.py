#!/usr/bin/env python3
"""
Utilitário de tratamento e consolidação de dados para RAG Jurídico.

Varre recursivamente diretórios, lê arquivos .json e .jsonl, filtra registros
com cluster_name == "unknown" e escreve saída em JSONL pronto para indexação.
"""

import argparse
import json
import logging
import sys
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Tuple


# Configuração de logging
logger = logging.getLogger("rag.tratamento_dados")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class DataProcessor:
    """Processador de dados para consolidação e limpeza."""

    def __init__(
        self,
        input_dir: Path,
        output_file: Path,
        dedupe_by: str = "id",
        ignore_hidden: bool = True,
        extensions: List[str] = None,
        quiet: bool = False,
    ):
        self.input_dir = input_dir
        self.output_file = output_file
        self.dedupe_by = dedupe_by
        self.ignore_hidden = ignore_hidden
        self.extensions = extensions or [".json", ".jsonl"]
        self.quiet = quiet

        # Regex para limpeza de tokens ruins / HTML
        # Remove HTML tags, common HTML entities (&nbsp;), and standalone 'br' tokens
        self._re_html = re.compile(r"<[^>]+>", flags=re.IGNORECASE)
        self._re_html_entities = re.compile(r"&(nbsp|amp|lt|gt);", flags=re.IGNORECASE)
        # standalone 'br' token (word boundary) appears frequently as separator in scraped text
        self._re_bad_br = re.compile(r"\bbr\b", flags=re.IGNORECASE)
        # collapse multiple whitespace into single space/newline
        self._re_multi_space = re.compile(r"[\t\u00A0\s]+")

        # Estatísticas
        self.stats = {
            "files_scanned": 0,
            "files_processed": 0,
            "records_read": 0,
            "records_written": 0,
            "filtered_unknown": 0,
            "duplicates_removed": 0,
            "invalid_records": 0,
        }

        # Set para deduplicação
        self.seen_keys: Set[str] = set()

        if quiet:
            logger.setLevel(logging.WARNING)

    def normalize_cluster_value(self, value: Any) -> str:
        """Normaliza valor do cluster para comparação."""
        if value is None:
            return ""
        return str(value).strip().lower()

    def is_unknown_cluster(self, record: Dict[str, Any]) -> bool:
        """
        Verifica se o registro possui cluster_name == "unknown" (case-insensitive).
        Também verifica variantes: cluster, clusterName, cluster_nome.
        """
        cluster_fields = ["cluster_name", "cluster", "clusterName", "cluster_nome"]

        for field in cluster_fields:
            if field in record:
                normalized = self.normalize_cluster_value(record[field])
                if normalized == "unknown":
                    return True

        return False

    def should_deduplicate(self, record: Dict[str, Any]) -> bool:
        """
        Verifica se o registro deve ser removido por duplicação.
        Retorna True se for duplicado (já visto), False caso contrário.
        """
        if self.dedupe_by == "none":
            return False

        key_field = self.dedupe_by
        key_value = record.get(key_field)

        if not key_value:
            # Se não tem o campo de deduplicação, não deduplica esse item
            logger.debug(f"Record without {key_field} field, skipping deduplication")
            return False

        # Normalizar chave para string
        if isinstance(key_value, (dict, list)):
            # Para objetos complexos, usar hash do JSON
            key_str = hashlib.md5(
                json.dumps(key_value, sort_keys=True).encode()
            ).hexdigest()
        else:
            key_str = str(key_value)

        # Normalização especial para case_number: remove "despacho" e mantém só números
        if key_field == "case_number":
            # Remove "despacho" (case-insensitive)
            key_str = re.sub(r'\bdespacho\b', '', key_str, flags=re.IGNORECASE)
            # Mantém apenas dígitos
            key_str = re.sub(r'[^\d]', '', key_str)
            if not key_str:
                # Se não sobrou nenhum número, não deduplica
                logger.debug(f"case_number without digits after normalization, skipping deduplication")
                return False

        if key_str in self.seen_keys:
            return True

        self.seen_keys.add(key_str)
        return False

    def process_json_file(self, file_path: Path) -> int:
        """
        Processa arquivo .json.
        Retorna número de registros escritos.
        """
        written = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Se for lista, iterar elementos
            if isinstance(data, list):
                for item in data:
                    if self.process_record(item):
                        written += 1
            # Se for dict, tratar como único registro
            elif isinstance(data, dict):
                if self.process_record(data):
                    written += 1
            else:
                logger.warning(
                    f"File {file_path} contains neither list nor object, skipping"
                )

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")

        return written

    def process_jsonl_file(self, file_path: Path) -> int:
        """
        Processa arquivo .jsonl linha a linha.
        Retorna número de registros escritos.
        """
        written = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        if self.process_record(record):
                            written += 1
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Invalid JSON at {file_path}:{line_num}: {e}"
                        )
                        self.stats["invalid_records"] += 1

        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")

        return written

    def process_record(self, record: Any) -> bool:
        """
        Processa um único registro: valida, filtra e escreve.
        Retorna True se foi escrito, False caso contrário.
        """
        self.stats["records_read"] += 1

        # Validação: registro deve ser objeto
        if not isinstance(record, dict):
            logger.warning(f"Record is not an object, skipping: {type(record)}")
            self.stats["invalid_records"] += 1
            return False

        # Filtro: cluster_name == "unknown"
        if self.is_unknown_cluster(record):
            self.stats["filtered_unknown"] += 1
            return False

        # Deduplicação
        if self.should_deduplicate(record):
            self.stats["duplicates_removed"] += 1
            return False

        # Limpeza de campos textuais antes de escrever
        self.clean_text_fields(record)

        # Escrever registro
        self.write_record(record)
        self.stats["records_written"] += 1
        return True

    def clean_text_fields(self, record: Dict[str, Any]) -> None:
        """Limpa campos textuais comuns no registro removendo tokens ruins.

        - Remove tags HTML
        - Remove entidades HTML básicas (&nbsp;, &amp;, etc.)
        - Remove tokens isolados 'br' (usados como quebras) e os substitui por espaço
        - Normaliza espaços em branco
        - Limpa case_number removendo "despacho" e mantendo apenas números
        A função modifica o dicionário in-place.
        """
        text_fields = [
            "content",
            "text",
            "body",
            "conteudo",
            "resumo",
            "summary",
            "title",
        ]

        for field in text_fields:
            if field in record and isinstance(record[field], str):
                text = record[field]

                # remover tags HTML
                text = self._re_html.sub(" ", text)

                # remover entidades HTML simples
                text = self._re_html_entities.sub(" ", text)

                # remover token 'br' isolado (muitas fontes usam 'br' como separador)
                text = self._re_bad_br.sub(" ", text)

                # colapsar espaços e normalizar
                text = self._re_multi_space.sub(" ", text).strip()

                # atualizar campo
                record[field] = text

        # Limpar case_number: remover "despacho" e manter apenas números
        if "case_number" in record and isinstance(record["case_number"], str):
            case_num = record["case_number"]
            # Remove "despacho" (case-insensitive) e mantém apenas dígitos
            case_num = re.sub(r'\bdespacho\b', '', case_num, flags=re.IGNORECASE)
            # Extrai apenas números
            case_num = re.sub(r'[^\d]', '', case_num)
            if case_num:
                record["case_number"] = case_num

    def write_record(self, record: Dict[str, Any]) -> None:
        """Escreve um registro no arquivo de saída (JSONL)."""
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def should_process_path(self, path: Path) -> bool:
        """Verifica se o caminho deve ser processado (respeita ignore_hidden)."""
        if not self.ignore_hidden:
            return True

        # Verificar se alguma parte do caminho começa com '.'
        for part in path.parts:
            if part.startswith("."):
                return False

        return True

    def find_eligible_files(self) -> List[Path]:
        """Encontra todos os arquivos elegíveis para processamento."""
        eligible = []

        for ext in self.extensions:
            pattern = f"**/*{ext}"
            for file_path in self.input_dir.rglob(pattern):
                if file_path.is_file() and self.should_process_path(file_path):
                    eligible.append(file_path)
                    self.stats["files_scanned"] += 1

        return sorted(eligible)

    def process(self) -> int:
        """
        Executa o processamento completo.
        Retorna exit code (0 = sucesso, 1 = erro).
        """
        import time

        start_time = time.time()

        logger.info(f"Starting data processing...")
        logger.info(f"Input directory: {self.input_dir}")
        logger.info(f"Output file: {self.output_file}")
        logger.info(f"Deduplication: {self.dedupe_by}")

        # Validar diretório de entrada
        if not self.input_dir.exists():
            logger.error(f"Input directory does not exist: {self.input_dir}")
            return 1

        if not self.input_dir.is_dir():
            logger.error(f"Input path is not a directory: {self.input_dir}")
            return 1

        # Criar diretório de saída se necessário
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Limpar arquivo de saída se existir
        if self.output_file.exists():
            self.output_file.unlink()

        # Encontrar arquivos elegíveis
        eligible_files = self.find_eligible_files()

        if not eligible_files:
            logger.error(
                f"No eligible files found in {self.input_dir} "
                f"with extensions {self.extensions}"
            )
            return 1

        logger.info(f"Found {len(eligible_files)} eligible files")

        # Processar cada arquivo
        for file_path in eligible_files:
            logger.debug(f"Processing {file_path}")

            if file_path.suffix == ".jsonl":
                written = self.process_jsonl_file(file_path)
            elif file_path.suffix == ".json":
                written = self.process_json_file(file_path)
            else:
                continue

            if written > 0:
                self.stats["files_processed"] += 1
                logger.debug(f"  → {written} records written")

        # Estatísticas finais
        elapsed = time.time() - start_time

        logger.info("=" * 60)
        logger.info("Processing completed successfully")
        logger.info(f"Time elapsed: {elapsed:.2f}s")
        logger.info(f"Files scanned: {self.stats['files_scanned']}")
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Records read: {self.stats['records_read']}")
        logger.info(f"Records written: {self.stats['records_written']}")
        logger.info(f"Filtered (unknown cluster): {self.stats['filtered_unknown']}")
        logger.info(f"Duplicates removed: {self.stats['duplicates_removed']}")
        logger.info(f"Invalid records: {self.stats['invalid_records']}")
        logger.info("=" * 60)

        return 0


def main() -> int:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Consolida e limpa dados JSON/JSONL para indexação",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s --input data --output data/merged_clean.jsonl
  %(prog)s -i data -o output.jsonl --dedupe-by id --quiet
  %(prog)s --input data --dedupe-by hash --ignore-hidden
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="data",
        help="Diretório raiz para varredura (default: data)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="data/merged_clean.jsonl",
        help="Arquivo de saída JSONL (default: data/merged_clean.jsonl)",
    )

    parser.add_argument(
        "--dedupe-by",
        type=str,
        default="id",
        help="Campo para deduplicação: 'id', 'hash', 'none', ou qualquer nome de campo (ex: case_number) (default: id)",
    )

    parser.add_argument(
        "--ignore-hidden",
        action="store_true",
        default=True,
        help="Ignorar arquivos e pastas iniciados por '.' (default: True)",
    )

    parser.add_argument(
        "--no-ignore-hidden",
        dest="ignore_hidden",
        action="store_false",
        help="Não ignorar arquivos e pastas ocultos",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduzir verbosidade (apenas avisos e erros)",
    )

    parser.add_argument(
        "--extensions",
        type=str,
        default=".json,.jsonl",
        help="Extensões de arquivo separadas por vírgula (default: .json,.jsonl)",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Imprimir estatísticas finais em JSON",
    )

    args = parser.parse_args()

    # Processar extensões
    extensions = [ext.strip() for ext in args.extensions.split(",")]
    extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

    # Criar processador
    processor = DataProcessor(
        input_dir=Path(args.input),
        output_file=Path(args.output),
        dedupe_by=args.dedupe_by,
        ignore_hidden=args.ignore_hidden,
        extensions=extensions,
        quiet=args.quiet,
    )

    # Executar processamento
    exit_code = processor.process()

    # Imprimir stats em JSON se solicitado
    if args.stats:
        print(json.dumps(processor.stats, indent=2))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

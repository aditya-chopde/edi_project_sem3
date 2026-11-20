from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
import logging
from pathlib import Path
from time import perf_counter
from typing import Callable

import cv2
import fitz
import numpy as np
import pytesseract
from docx import Document as WordDocument
from ebooklib import ITEM_DOCUMENT, epub
from PIL import Image

from app import config

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int], None]
_ocr_executor = ThreadPoolExecutor(
    max_workers=config.OCR_WORKERS,
    thread_name_prefix="itihasa-ocr",
)


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def _preprocess_for_ocr(image: Image.Image) -> Image.Image:
    image_array = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    _, thresholded = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return Image.fromarray(thresholded)


def _ocr(image: Image.Image) -> str:
    started_at = perf_counter()
    text = pytesseract.image_to_string(
        _preprocess_for_ocr(image),
        lang=config.OCR_LANGS,
    ).strip()
    logger.info("OCR page completed (elapsed_seconds=%.3f)", perf_counter() - started_at)
    return text


def _ocr_pdf_page(path: str, page_index: int) -> str:
    with fitz.open(path) as pdf:
        page = pdf.load_page(page_index)
        pixmap = page.get_pixmap(
            dpi=config.OCR_DPI, colorspace=fitz.csRGB, alpha=False
        )
        image = Image.frombytes(
            "RGB", (pixmap.width, pixmap.height), pixmap.samples
        )
        return _ocr(image)


def extract_document(
    path: Path,
    file_type: str,
    progress_callback: ProgressCallback | None = None,
) -> list[PageText]:
    suffix = file_type.lower()
    logger.info("Extracting text from file type %s", suffix)
    if suffix == ".pdf":
        started_at = perf_counter()
        pages: list[PageText | None] = []
        ocr_page_indices: list[int] = []
        ocr_pages: dict[int, str] = {}
        completed_pages = 0
        with fitz.open(path) as pdf:
            total_pages = len(pdf)
            pages = [None] * total_pages
            for page_index, page in enumerate(pdf):
                page_number = page_index + 1
                text = page.get_text("text").strip()
                extraction_method = "text"
                if len(text) < 50:
                    extraction_method = "OCR"
                    ocr_page_indices.append(page_index)
                else:
                    pages[page_index] = PageText(page=page_number, text=text)
                    completed_pages += 1
                    if progress_callback:
                        progress_callback(completed_pages, total_pages)
                logger.debug(
                    "Extracted PDF page (page=%d, method=%s, characters=%d)",
                    page_number,
                    extraction_method,
                    len(text),
                )
        if len(ocr_page_indices) == 1:
            page_index = ocr_page_indices[0]
            ocr_pages[page_index] = _ocr_pdf_page(str(path), page_index)
            completed_pages += 1
            if progress_callback:
                progress_callback(completed_pages, total_pages)
        elif ocr_page_indices:
            futures = {
                _ocr_executor.submit(_ocr_pdf_page, str(path), page_index): page_index
                for page_index in ocr_page_indices
            }
            for future in as_completed(futures):
                page_index = futures[future]
                ocr_pages[page_index] = future.result()
                completed_pages += 1
                if progress_callback:
                    progress_callback(completed_pages, total_pages)

        for page_index, text in ocr_pages.items():
            pages[page_index] = PageText(page=page_index + 1, text=text)
            logger.debug(
                "OCR extracted PDF page (page=%d, characters=%d)",
                page_index + 1,
                len(text),
            )
        logger.info(
            "PDF extraction complete (pages=%d, ocr_pages=%d, elapsed_seconds=%.3f)",
            total_pages,
            len(ocr_pages),
            perf_counter() - started_at,
        )
        return [page for page in pages if page is not None]

    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}:
        started_at = perf_counter()
        with Image.open(path) as image:
            text = _ocr_executor.submit(_ocr, image.copy()).result()
            logger.debug(
                "OCR extracted image (page=1, characters=%d)", len(text)
            )
            if progress_callback:
                progress_callback(1, 1)
            logger.info(
                "Image extraction complete (elapsed_seconds=%.3f)",
                perf_counter() - started_at,
            )
            return [PageText(page=1, text=text)]

    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig")
        logger.debug(
            "Read text document (page=1, characters=%d)", len(text)
        )
        if progress_callback:
            progress_callback(1, 1)
        return [PageText(page=1, text=text)]

    if suffix == ".docx":
        word_document = WordDocument(path)
        text = "\n".join(
            paragraph.text for paragraph in word_document.paragraphs if paragraph.text
        )
        logger.debug("Extracted DOCX text (page=1, characters=%d)", len(text))
        if progress_callback:
            progress_callback(1, 1)
        return [PageText(page=1, text=text)]

    if suffix == ".epub":
        book = epub.read_epub(str(path))
        pages = []
        items = list(book.get_items_of_type(ITEM_DOCUMENT))
        for page_number, item in enumerate(items, start=1):
            parser = _TextExtractor()
            parser.feed(item.get_content().decode("utf-8", errors="replace"))
            text = "\n".join(parser.parts)
            logger.debug(
                "Extracted EPUB section (page=%d, characters=%d)",
                page_number,
                len(text),
            )
            pages.append(PageText(page=page_number, text=text))
            if progress_callback:
                progress_callback(page_number, len(items))
        return pages

    raise ValueError(f"Unsupported file type: {suffix}")

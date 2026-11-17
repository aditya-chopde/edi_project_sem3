from dataclasses import dataclass
from html.parser import HTMLParser
import logging
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytesseract
from docx import Document as WordDocument
from ebooklib import ITEM_DOCUMENT, epub
from PIL import Image

from app import config

logger = logging.getLogger(__name__)


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
    return pytesseract.image_to_string(
        _preprocess_for_ocr(image),
        lang=config.OCR_LANGS,
    ).strip()


def extract_document(path: Path, file_type: str) -> list[PageText]:
    suffix = file_type.lower()
    logger.info("Extracting text from file type %s", suffix)
    if suffix == ".pdf":
        pages: list[PageText] = []
        with fitz.open(path) as pdf:
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                extraction_method = "text"
                if len(text) < 50:
                    extraction_method = "OCR"
                    pixmap = page.get_pixmap(
                        dpi=config.OCR_DPI, colorspace=fitz.csRGB, alpha=False
                    )
                    image = Image.frombytes(
                        "RGB", (pixmap.width, pixmap.height), pixmap.samples
                    )
                    text = _ocr(image)
                logger.debug(
                    "Extracted PDF page (page=%d, method=%s, characters=%d)",
                    page_number,
                    extraction_method,
                    len(text),
                )
                pages.append(PageText(page=page_number, text=text))
        return pages

    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}:
        with Image.open(path) as image:
            text = _ocr(image.copy())
            logger.debug(
                "OCR extracted image (page=1, characters=%d)", len(text)
            )
            return [PageText(page=1, text=text)]

    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig")
        logger.debug(
            "Read text document (page=1, characters=%d)", len(text)
        )
        return [PageText(page=1, text=text)]

    if suffix == ".docx":
        word_document = WordDocument(path)
        text = "\n".join(
            paragraph.text for paragraph in word_document.paragraphs if paragraph.text
        )
        logger.debug("Extracted DOCX text (page=1, characters=%d)", len(text))
        return [PageText(page=1, text=text)]

    if suffix == ".epub":
        book = epub.read_epub(str(path))
        pages = []
        for page_number, item in enumerate(
            book.get_items_of_type(ITEM_DOCUMENT), start=1
        ):
            parser = _TextExtractor()
            parser.feed(item.get_content().decode("utf-8", errors="replace"))
            text = "\n".join(parser.parts)
            logger.debug(
                "Extracted EPUB section (page=%d, characters=%d)",
                page_number,
                len(text),
            )
            pages.append(PageText(page=page_number, text=text))
        return pages

    raise ValueError(f"Unsupported file type: {suffix}")

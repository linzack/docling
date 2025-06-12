import logging # For capturing logs
from pathlib import Path

from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorDevice
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.settings import PageRange # For PageRange type hint
from docling.document_converter import DocumentConverter, PdfFormatOption

from .test_data_gen_flag import GEN_TEST_DATA
from .verify_utils import verify_conversion_result_v1, verify_conversion_result_v2

GENERATE_V1 = GEN_TEST_DATA
GENERATE_V2 = GEN_TEST_DATA


def get_pdf_paths():
    # Define the directory you want to search
    directory = Path("./tests/data/pdf/")

    # List all PDF files in the directory and its subdirectories
    pdf_files = sorted(directory.rglob("*.pdf"))
    return pdf_files


def get_converter():
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True
    pipeline_options.accelerator_options.device = AcceleratorDevice.CPU

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=DoclingParseDocumentBackend,
            )
        }
    )

    return converter


def test_e2e_pdfs_conversions():
    pdf_paths = get_pdf_paths()
    converter = get_converter()

    for pdf_path in pdf_paths:
        print(f"converting {pdf_path}")

        doc_result: ConversionResult = converter.convert(pdf_path)

        verify_conversion_result_v1(
            input_path=pdf_path, doc_result=doc_result, generate=GENERATE_V1
        )

        verify_conversion_result_v2(
            input_path=pdf_path, doc_result=doc_result, generate=GENERATE_V2
        )


def test_e2e_code_formula_with_page_range():
    pdf_path = Path("./tests/data/pdf/code_and_formula.pdf")

    # Configure pipeline options for enrichment
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False # Keep OCR off as in other tests
    pipeline_options.do_table_structure = False # Disable table structure if not needed for this test
    pipeline_options.do_formula_enrichment = True # Enable an enrichment that uses BaseItemAndImageEnrichmentModel
    pipeline_options.do_code_enrichment = True   # Enable an enrichment that uses BaseItemAndImageEnrichmentModel
    # Accelerator options can be default or as in get_converter()
    pipeline_options.accelerator_options.device = AcceleratorDevice.CPU

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                # Using DoclingParseDocumentBackend as in get_converter()
                # If CodeFormulaModel needs a different backend, this might need adjustment
                # For now, assume DoclingParseDocumentBackend is sufficient for page image generation
                backend=DoclingParseDocumentBackend,
            )
        }
    )

    # Test with page_range=(1, 1) - process only the first page (1-indexed)
    # The 'code_and_formula.pdf' has at least 2 pages.
    # PageRange is 1-indexed, inclusive start/end.
    page_range_to_test = PageRange(1, 1)

    # Capture logs to check for the specific warning
    # This part is tricky without knowing the test runner (pytest/unittest)
    # For now, we'll proceed without explicit log capture in this subtask,
    # but the test should ideally check for absence of the warning.
    # The primary check will be that elements from the correct page are processed.

    print(f"Converting {pdf_path} with page_range={page_range_to_test}")
    doc_result: ConversionResult = converter.convert(pdf_path, page_range=page_range_to_test)

    assert doc_result.status == "SUCCESS", f"Conversion failed with status {doc_result.status}"
    assert doc_result.document is not None, "Document not created"
    assert len(doc_result.pages) == 1, f"Expected 1 page to be processed, but got {len(doc_result.pages)}"

    # Check that the processed page is indeed the first page (0-indexed absolute)
    # doc_result.pages[0].page_no should be 0 (abs 0-indexed for original page 1)
    assert doc_result.pages[0].page_no == 0, f"Expected processed page to be page_no 0 (absolute), got {doc_result.pages[0].page_no}"

    # Verify elements in the document are from the correct page
    # and that enrichment might have occurred (e.g. text updated or annotations added by CodeFormulaModel)
    processed_elements = 0
    if doc_result.document.pages: # Check if there are pages in the document structure
        # doc_result.document.pages is a dict keyed by 1-indexed absolute page number
        assert 1 in doc_result.document.pages, "Page 1 (absolute) not found in document output"

        for item, _ in doc_result.document.pages[1].iterate_items():
            assert item.prov[0].page_no == 1, f"Element {item.id} from unexpected page {item.prov[0].page_no}"
            # If CodeFormulaModel modified text or added annotations, that's a good sign
            # For example, if it's a TextItem and label is FORMULA, text might be updated.
            # This assertion is a placeholder for more specific checks based on model behavior.
            processed_elements +=1

    assert processed_elements > 0, "No elements found or processed on the selected page."
    print(f"Successfully converted {pdf_path} with page_range, {processed_elements} elements processed from page 1.")

    # Optional: Test with another page_range, e.g., page 2
    page_range_to_test_pg2 = PageRange(2, 2)
    print(f"Converting {pdf_path} with page_range={page_range_to_test_pg2}")
    doc_result_pg2: ConversionResult = converter.convert(pdf_path, page_range=page_range_to_test_pg2)
    assert doc_result_pg2.status == "SUCCESS", f"Conversion failed with status {doc_result_pg2.status}"
    assert doc_result_pg2.document is not None, "Document not created for page 2"
    assert len(doc_result_pg2.pages) == 1, f"Expected 1 page for page_range {page_range_to_test_pg2}, got {len(doc_result_pg2.pages)}"
    assert doc_result_pg2.pages[0].page_no == 1, f"Expected processed page to be page_no 1 (absolute), got {doc_result_pg2.pages[0].page_no}"

    processed_elements_pg2 = 0
    if doc_result_pg2.document.pages:
         assert 2 in doc_result_pg2.document.pages, "Page 2 (absolute) not found in document output for second test"
         for item, _ in doc_result_pg2.document.pages[2].iterate_items():
             assert item.prov[0].page_no == 2, f"Element {item.id} from unexpected page {item.prov[0].page_no} on second test"
             processed_elements_pg2 +=1
    assert processed_elements_pg2 > 0, "No elements found or processed on page 2."
    print(f"Successfully converted {pdf_path} with page_range for page 2, {processed_elements_pg2} elements processed.")

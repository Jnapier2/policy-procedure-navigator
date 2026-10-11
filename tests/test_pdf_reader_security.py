from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.ingest import extract_text, make_document_record


def test_pdf_policy_text_still_enters_the_governed_document_pipeline() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): font}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 10 150 Td (Purchases require manager approval.) Tj ET')
    page[NameObject('/Contents')] = stream
    output = io.BytesIO()
    writer.write(output)

    assert 'Purchases require manager approval.' in extract_text(output.getvalue(), 'policy.pdf')
    document, chunks, _ = make_document_record(
        output.getvalue(), 'policy.pdf', {'allowed_roles': 'employee,admin'},
    )
    assert document['allowed_roles'] == ['employee', 'admin']
    assert any('manager approval' in chunk['content'] for chunk in chunks)


def test_default_pdf_reader_bounds_an_unterminated_indirect_object_header() -> None:
    valid = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(valid)
    reader = PdfReader(io.BytesIO(valid.getvalue()))
    oversized = io.BytesIO(b'1' * 10000 + b' 0 obj\n')

    # Exercise the upstream reader boundary with the application's default
    # non-strict mode. No huge allocation, timing assumption or hostile file.
    try:
        reader.read_object_header(oversized)
    except (ValueError, OverflowError):
        pass
    assert oversized.tell() < 200, 'the reader consumed an oversized object-number token'

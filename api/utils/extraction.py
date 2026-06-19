import fitz  # PyMuPDF
from docx import Document
import io

def extract_pdf(file_bytes: bytes) -> str:
    """Extracts text from a PDF, inserting [PAGE X] markers."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    extracted_text = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        extracted_text.append(f"[PAGE {page_num + 1}]\n{text}")
        
    return "\n\n".join(extracted_text)

def extract_docx(file_bytes: bytes) -> str:
    """Extracts text from a Word document paragraph by paragraph."""
    doc = Document(io.BytesIO(file_bytes))
    extracted_text = [para.text for para in doc.paragraphs if para.text.strip()]
    
    return "\n".join(extracted_text)

def concatenate_files(files: list[dict]) -> str:
    """
    Joins multiple files into one large text blob.
    'files' should be a list of dicts: [{"filename": "contract.pdf", "text": "..."}]
    """
    if not files:
        return ""
        
    if len(files) == 1:
        # If there's only one file, we don't need FILE markers
        return files[0]["text"]
        
    combined = []
    for f in files:
        combined.append(f"[FILE: {f['filename']}]\n{f['text']}")
        
    return "\n\n---\n\n".join(combined)

"""
PDF Splitter Utility
====================
Automatically splits large PDF files into smaller chunks for processing.
"""

import os
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

# Maximum chunk size: 95MB (leaving buffer below 100MB limit)
MAX_CHUNK_SIZE = 95 * 1024 * 1024


def split_pdf_by_size(
    file_path: Union[str, Path],
    output_dir: Union[str, Path],
    max_chunk_size: int = MAX_CHUNK_SIZE,
) -> List[Tuple[Path, int]]:
    """
    Split a large PDF into smaller chunks based on file size.
    
    Args:
        file_path: Path to the source PDF
        output_dir: Directory to save chunk files
        max_chunk_size: Maximum size per chunk in bytes (default: 95MB)
    
    Returns:
        List of tuples (chunk_path, page_count) for each chunk
    """
    import fitz  # PyMuPDF
    
    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    original_size = file_path.stat().st_size
    if original_size <= max_chunk_size:
        # No splitting needed, return original file
        return [(file_path, fitz.open(file_path).page_count)]
    
    logger.info(f"Splitting PDF {file_path.name} ({original_size / 1024 / 1024:.1f}MB) into chunks...")
    
    doc = fitz.open(file_path)
    total_pages = doc.page_count
    doc.close()
    
    # Estimate pages per chunk based on file size ratio
    # Add 20% buffer to be safe
    avg_page_size = original_size / total_pages
    pages_per_chunk = int((max_chunk_size / avg_page_size) * 0.8)
    pages_per_chunk = max(pages_per_chunk, 1)  # At least 1 page per chunk
    
    chunks = []
    base_name = file_path.stem
    
    # Open document once and split
    doc = fitz.open(file_path)
    
    for i in range(0, total_pages, pages_per_chunk):
        end_page = min(i + pages_per_chunk, total_pages)
        chunk_pages = end_page - i
        
        # Create new PDF for this chunk
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=i, to_page=end_page - 1)
        
        chunk_name = f"{base_name}_part{i // pages_per_chunk + 1}.pdf"
        chunk_path = output_dir / chunk_name
        
        chunk_doc.save(chunk_path, garbage=4, deflate=True)
        chunk_doc.close()
        
        chunk_size = chunk_path.stat().st_size
        logger.info(f"  Created chunk {i // pages_per_chunk + 1}: {chunk_name} ({chunk_pages} pages, {chunk_size / 1024 / 1024:.1f}MB)")
        chunks.append((chunk_path, chunk_pages))
    
    doc.close()
    
    logger.info(f"Split into {len(chunks)} chunks")
    return chunks


def split_pdf_by_page_groups(
    file_path: Union[str, Path],
    output_dir: Union[str, Path],
    pages_per_chunk: int = 50,
) -> List[Tuple[Path, int]]:
    """
    Split a PDF into chunks with a fixed number of pages.
    
    Args:
        file_path: Path to the source PDF
        output_dir: Directory to save chunk files
        pages_per_chunk: Number of pages per chunk
    
    Returns:
        List of tuples (chunk_path, page_count) for each chunk
    """
    import fitz  # PyMuPDF
    
    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(file_path)
    total_pages = doc.page_count
    doc.close()
    
    chunks = []
    base_name = file_path.stem
    
    doc = fitz.open(file_path)
    chunk_num = 1
    
    for i in range(0, total_pages, pages_per_chunk):
        end_page = min(i + pages_per_chunk, total_pages)
        chunk_pages = end_page - i
        
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=i, to_page=end_page - 1)
        
        chunk_name = f"{base_name}_part{chunk_num}.pdf"
        chunk_path = output_dir / chunk_name
        
        chunk_doc.save(chunk_path, garbage=4, deflate=True)
        chunk_doc.close()
        
        chunks.append((chunk_path, chunk_pages))
        chunk_num += 1
    
    doc.close()
    
    logger.info(f"Split PDF into {len(chunks)} chunks ({pages_per_chunk} pages each)")
    return chunks


from typing import Union

"""
File chunking functionality for creating text segments
Supports various file formats via file_parser
Supports both character-based and token-based chunking
Supports GCS storage backend for cloud-native file operations
"""

import hashlib
import os
import unicodedata
from typing import List, Optional, TYPE_CHECKING

from gemini.file_parser import parse_file

if TYPE_CHECKING:
    from gemini.storage import StorageBackend

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("Warning: tiktoken not available. Install with: pip install tiktoken")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to use only ASCII characters

    Args:
        filename: Original filename (may contain non-ASCII characters)

    Returns:
        ASCII-safe filename
    """
    # Try to transliterate Unicode characters to ASCII
    try:
        # Normalize unicode characters
        normalized = unicodedata.normalize("NFKD", filename)
        # Encode to ASCII, ignoring characters that can't be converted
        ascii_name = normalized.encode("ascii", "ignore").decode("ascii")

        # If we lost too many characters, use a hash instead
        if len(ascii_name) < len(filename) * 0.3:  # Lost more than 70%
            # Create a hash of the original filename
            file_hash = hashlib.md5(filename.encode("utf-8")).hexdigest()[:8]
            return f"file_{file_hash}"

        # Remove any remaining problematic characters
        safe_name = "".join(c if c.isalnum() or c in "_- " else "_" for c in ascii_name)
        # Clean up multiple underscores and spaces
        safe_name = " ".join(safe_name.split())
        safe_name = "_".join(safe_name.split("_"))

        return (
            safe_name
            if safe_name
            else f"file_{hashlib.md5(filename.encode('utf-8')).hexdigest()[:8]}"
        )

    except Exception:
        # Fallback to hash if anything goes wrong
        file_hash = hashlib.md5(filename.encode("utf-8")).hexdigest()[:8]
        return f"file_{file_hash}"


def chunk_text_file(
    file_path: str,
    file_id: str,
    chunk_size: int = 1000,
    output_dir: str = "chunks",
    storage_backend: Optional["StorageBackend"] = None,
) -> List[str]:
    """
    Parse and split a file into chunks, save as separate text files

    Supports: .txt, .md, .docx, .pdf

    Args:
        file_path: Path to the input file
        file_id: Identifier for the file (used in chunk filenames)
        chunk_size: Number of characters per chunk
        output_dir: Directory to save chunk files (or GCS blob prefix)
        storage_backend: Optional storage backend (GCS or local). If None, uses local filesystem.

    Returns:
        List of file paths/blob paths for created chunks
    """
    # Sanitize file_id to ensure ASCII-safe filenames
    safe_file_id = sanitize_filename(file_id)

    # Parse the file to extract text
    print(f"      Parsing file: {os.path.basename(file_path)}")
    try:
        content = parse_file(file_path)
        print(f"      Extracted {len(content)} characters")
    except ValueError as e:
        print(f"   Warning: {e}")
        return []

    if not content.strip():
        print(f"   Warning: No text content extracted from {file_path}")
        return []

    # Create output directory (only for local filesystem)
    if storage_backend is None:
        print(f"      Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)

    # Split into chunks
    chunks = []
    current_pos = 0
    chunk_num = 0

    while current_pos < len(content):
        # Get chunk of text
        chunk_text = content[current_pos : current_pos + chunk_size]

        # Try to break at sentence/paragraph boundary if possible
        if current_pos + chunk_size < len(content):
            # Look for paragraph break
            last_newline = chunk_text.rfind("\n\n")
            if last_newline > chunk_size * 0.5:  # At least 50% through chunk
                chunk_text = chunk_text[:last_newline]
            else:
                # Look for sentence break
                last_period = max(
                    chunk_text.rfind(". "),
                    chunk_text.rfind(".\n"),
                    chunk_text.rfind("! "),
                    chunk_text.rfind("? "),
                )
                if last_period > chunk_size * 0.5:
                    chunk_text = chunk_text[: last_period + 1]

        # Save chunk to file or GCS
        chunk_num += 1
        chunk_filename = f"{safe_file_id}_chunk_{chunk_num:03d}.txt"

        # Prepare chunk content
        chunk_content = (
            f"--- {file_id}: Chunk {chunk_num} ---\n"
            f"Source: {os.path.basename(file_path)}\n\n"
            f"{chunk_text}"
        )

        if storage_backend:
            # Use storage backend (GCS or cached GCS)
            # For GCS, output_dir is a blob prefix like "chunks/area/site"
            chunk_path = f"{output_dir}/{chunk_filename}" if output_dir else chunk_filename
            storage_backend.write_file(chunk_path, chunk_content)
            chunks.append(chunk_path)
        else:
            # Use local filesystem
            chunk_filepath = os.path.join(output_dir, chunk_filename)
            with open(chunk_filepath, "w", encoding="utf-8") as f:
                f.write(chunk_content)
            chunks.append(chunk_filepath)

        # Move position forward by actual chunk size
        actual_chunk_size = len(chunk_text)
        current_pos += actual_chunk_size

        # Skip whitespace at the beginning of next chunk
        while current_pos < len(content) and content[current_pos].isspace():
            current_pos += 1

    return chunks


def chunk_text_smart(
    text: str,
    file_id: str,
    chunk_size: int = 1000,
    overlap: int = 100,
    output_dir: str = "chunks",
) -> List[str]:
    """
    Split text into overlapping chunks with smart boundary detection

    Args:
        text: Text content to chunk
        file_id: Identifier for the content
        chunk_size: Target size of each chunk in characters
        overlap: Number of characters to overlap between chunks
        output_dir: Directory to save chunk files

    Returns:
        List of file paths for created chunks
    """
    # Sanitize file_id to ensure ASCII-safe filenames
    safe_file_id = sanitize_filename(file_id)

    os.makedirs(output_dir, exist_ok=True)

    chunks = []
    current_pos = 0
    chunk_num = 0

    while current_pos < len(text):
        # Calculate end position
        end_pos = min(current_pos + chunk_size, len(text))

        # Extract chunk
        chunk_text = text[current_pos:end_pos]

        # Find good break point (if not at end)
        if end_pos < len(text):
            # Try to break at paragraph
            last_para = chunk_text.rfind("\n\n")
            if last_para > chunk_size * 0.6:
                chunk_text = chunk_text[:last_para]
                end_pos = current_pos + last_para
            else:
                # Try to break at sentence
                for delimiter in [". ", ".\n", "! ", "? "]:
                    last_sent = chunk_text.rfind(delimiter)
                    if last_sent > chunk_size * 0.6:
                        chunk_text = chunk_text[: last_sent + len(delimiter)]
                        end_pos = current_pos + last_sent + len(delimiter)
                        break

        # Save chunk
        chunk_num += 1
        chunk_filename = f"{safe_file_id}_chunk_{chunk_num:03d}.txt"
        chunk_filepath = os.path.join(output_dir, chunk_filename)

        with open(chunk_filepath, "w", encoding="utf-8") as f:
            f.write(f"--- {file_id}: Chunk {chunk_num} ---\n\n")
            f.write(chunk_text.strip())

        chunks.append(chunk_filepath)

        # Move to next chunk with overlap
        current_pos = end_pos - overlap
        if current_pos >= len(text):
            break

    return chunks


def chunk_text_tokens(
    text: str,
    file_id: str,
    chunk_tokens: int = 400,
    overlap_percent: float = 0.15,
    output_dir: str = "chunks",
    storage_backend: Optional["StorageBackend"] = None,
    encoding_name: str = "cl100k_base",
) -> List[str]:
    """
    Split text into overlapping chunks based on token count

    Args:
        text: Text content to chunk
        file_id: Identifier for the content
        chunk_tokens: Target number of tokens per chunk (default: 400 tokens)
        overlap_percent: Percentage of overlap between chunks (default: 0.15 for 15%)
        output_dir: Directory to save chunk files (or GCS blob prefix)
        storage_backend: Optional storage backend (GCS or local). If None, uses local filesystem.
        encoding_name: Tiktoken encoding to use (cl100k_base for GPT-4/Gemini)

    Returns:
        List of file paths/blob paths for created chunks
    """
    if not TIKTOKEN_AVAILABLE:
        print(
            "Warning: tiktoken not available. Falling back to character-based chunking."
        )
        # Approximate: 1 token ≈ 4 characters
        char_size = chunk_tokens * 4
        char_overlap = int(char_size * overlap_percent)
        return chunk_text_smart(text, file_id, char_size, char_overlap, output_dir)

    # Sanitize file_id
    safe_file_id = sanitize_filename(file_id)

    # Create output directory (only for local filesystem)
    if storage_backend is None:
        os.makedirs(output_dir, exist_ok=True)

    # Load tokenizer
    try:
        encoding = tiktoken.get_encoding(encoding_name)
    except Exception as e:
        print(f"Warning: Could not load encoding '{encoding_name}': {e}")
        print("Falling back to character-based chunking")
        char_size = chunk_tokens * 4
        char_overlap = int(char_size * overlap_percent)
        return chunk_text_smart(text, file_id, char_size, char_overlap, output_dir)

    # Token overlap in tokens
    overlap_tokens = int(chunk_tokens * overlap_percent)

    # Tokenize the entire text
    print(f"        Tokenizing text...")
    tokens = encoding.encode(text)
    total_tokens = len(tokens)
    print(
        f"        Text has {total_tokens} tokens, will create ~{(total_tokens // chunk_tokens) + 1} chunks"
    )

    chunks = []
    chunk_num = 0
    start_idx = 0

    while start_idx < total_tokens:
        if chunk_num % 10 == 0 and chunk_num > 0:
            print(f"        Created {chunk_num} chunks so far...")
        # Calculate end index
        end_idx = min(start_idx + chunk_tokens, total_tokens)

        # Extract chunk tokens
        chunk_tokens_list = tokens[start_idx:end_idx]

        # Decode back to text
        chunk_text = encoding.decode(chunk_tokens_list)

        # Try to find natural break points if not at the end
        if end_idx < total_tokens:
            # Look for paragraph break (try to keep last 10% for boundary search)
            boundary_search = chunk_text[int(len(chunk_text) * 0.9) :]
            para_break = boundary_search.rfind("\n\n")

            if para_break > 0:
                # Found paragraph break, adjust chunk
                adjusted_chunk = chunk_text[: int(len(chunk_text) * 0.9) + para_break]
                # Re-encode to get actual token count
                adjusted_tokens = encoding.encode(adjusted_chunk)
                chunk_text = adjusted_chunk
                end_idx = start_idx + len(adjusted_tokens)
            else:
                # Try sentence break
                for delimiter in [". ", ".\n", "! ", "? "]:
                    sent_break = boundary_search.rfind(delimiter)
                    if sent_break > 0:
                        adjusted_chunk = chunk_text[
                            : int(len(chunk_text) * 0.9) + sent_break + len(delimiter)
                        ]
                        adjusted_tokens = encoding.encode(adjusted_chunk)
                        chunk_text = adjusted_chunk
                        end_idx = start_idx + len(adjusted_tokens)
                        break

        # Save chunk
        chunk_num += 1
        chunk_filename = f"{safe_file_id}_chunk_{chunk_num:03d}.txt"
        actual_tokens = len(encoding.encode(chunk_text))

        # Prepare chunk content
        chunk_content = (
            f"--- {file_id}: Chunk {chunk_num} ({actual_tokens} tokens) ---\n\n"
            f"{chunk_text.strip()}"
        )

        if storage_backend:
            # Use storage backend (GCS or cached GCS)
            chunk_path = f"{output_dir}/{chunk_filename}" if output_dir else chunk_filename
            storage_backend.write_file(chunk_path, chunk_content)
            chunks.append(chunk_path)
        else:
            # Use local filesystem
            chunk_filepath = os.path.join(output_dir, chunk_filename)
            with open(chunk_filepath, "w", encoding="utf-8") as f:
                f.write(chunk_content)
            chunks.append(chunk_filepath)

        # If we just processed the last chunk, we're done
        if end_idx >= total_tokens:
            break

        # Move to next chunk with overlap
        new_start_idx = end_idx - overlap_tokens

        # Prevent infinite loop - ensure we're making progress
        # If overlap would keep us in same position, just move forward
        if new_start_idx <= start_idx:
            # This happens when end_idx - overlap_tokens <= start_idx
            # Just break here as we've reached the end
            break

        start_idx = new_start_idx

    print(f"        Finished creating {len(chunks)} chunks")
    return chunks


def chunk_file_tokens(
    file_path: str,
    file_id: str,
    chunk_tokens: int = 400,
    overlap_percent: float = 0.15,
    output_dir: str = "chunks",
    storage_backend: Optional["StorageBackend"] = None,
) -> List[str]:
    """
    Parse file and split into token-based chunks with overlap

    Args:
        file_path: Path to input file
        file_id: Identifier for the file
        chunk_tokens: Target tokens per chunk (300-500 recommended)
        overlap_percent: Overlap percentage (0.10-0.20 recommended for 10-20%)
        output_dir: Output directory for chunks (or GCS blob prefix)
        storage_backend: Optional storage backend (GCS or local). If None, uses local filesystem.

    Returns:
        List of chunk file paths/blob paths
    """
    # Sanitize file_id
    safe_file_id = sanitize_filename(file_id)

    # Parse file
    print(f"      Parsing file: {os.path.basename(file_path)}")
    try:
        content = parse_file(file_path)
        print(f"      Extracted {len(content)} characters")
    except ValueError as e:
        print(f"   Warning: {e}")
        return []

    if not content.strip():
        print(f"   Warning: No text content extracted from {file_path}")
        return []

    print(
        f"      Creating chunks ({chunk_tokens} tokens, {int(overlap_percent*100)}% overlap)..."
    )
    result = chunk_text_tokens(
        content, file_id, chunk_tokens, overlap_percent, output_dir, storage_backend
    )
    print(f"      Created {len(result)} chunks")
    return result

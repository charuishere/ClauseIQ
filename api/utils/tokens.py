import tiktoken
import hashlib

def count_tokens(text: str) -> int:
    """
    Counts the number of tokens in a given text using the standard cl100k_base encoding.
    This gives us a highly accurate estimate of LLM context size.
    """
    if not text:
        return 0
    # cl100k_base is widely used and provides a safe upper bound estimate
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def compute_hash(text: str) -> str:
    """
    Computes a SHA-256 hash of the text to serve as a unique fingerprint.
    Done so that if user uploads the same file, we can reject it.
    """
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

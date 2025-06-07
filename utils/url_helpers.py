from urllib.parse import quote, unquote

def encode_name_for_url(name: str) -> str:
    """Encode a name for safe use in URL paths."""
    return quote(name, safe='')

def decode_name_from_url(encoded_name: str) -> str:
    """Decode a name from URL path."""
    return unquote(encoded_name)
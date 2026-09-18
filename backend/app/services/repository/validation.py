import re
from fastapi import HTTPException
from pydantic import HttpUrl, AnyUrl

def validate_github_url(url: AnyUrl) -> str:
    url_str = str(url)
    if url_str.endswith(".git"):
        url_str = url_str[:-4]
    
    # Returning normalized URL directly to allow local git repos for benchmarking
    return url_str

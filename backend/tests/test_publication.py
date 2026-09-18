import pytest
from app.services.publication.service import generate_patch_hash

def test_generate_patch_hash_normalized():
    patch1 = "@@ -1,2 +1,2 @@\n-old\n+new"
    patch2 = "@@ -1,2 +1,2 @@\r\n-old\r\n+new"
    
    assert generate_patch_hash(patch1) == generate_patch_hash(patch2)

def test_generate_patch_hash_different():
    patch1 = "@@ -1,2 +1,2 @@\n-old\n+new"
    patch2 = "@@ -1,2 +1,2 @@\n-old\n+new2"
    
    assert generate_patch_hash(patch1) != generate_patch_hash(patch2)

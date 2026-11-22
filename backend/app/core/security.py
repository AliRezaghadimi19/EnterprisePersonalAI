"""
Security and Cryptography Core Module
Provides:
- Password hashing and verification
- JWT Token generation and verification
- Symmetric encryption/decryption (Fernet/AES) for sensitive credentials (API keys, AD bind passwords)
"""

import os
import json
import base64
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union

from app.core.config import settings

# ------------------------------------------------------------------------------
# Password Hashing & Verification (PBKDF2-SHA256 & bcrypt compatibility)
# ------------------------------------------------------------------------------

def generate_salt(length: int = 16) -> str:
    """Generate a cryptographically secure random hex salt."""
    return secrets.token_hex(length)

def hash_password(password: str) -> str:
    """
    Hash a password securely using PBKDF2 with SHA-256 and 100,000 iterations.
    Format: pbkdf2_sha256$<iterations>$<salt>$<hash>
    """
    salt = generate_salt(16)
    iterations = 100000
    derived = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    b64_hash = base64.b64encode(derived).decode('utf-8')
    return f"pbkdf2_sha256${iterations}${salt}${b64_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored hash."""
    if not hashed_password or "$" not in hashed_password:
        return False
        
    parts = hashed_password.split("$")
    if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
        _, iterations_str, salt, stored_hash = parts
        try:
            iterations = int(iterations_str)
            derived = hashlib.pbkdf2_hmac(
                'sha256',
                plain_password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations
            )
            b64_hash = base64.b64encode(derived).decode('utf-8')
            return hmac.compare_digest(b64_hash, stored_hash)
        except Exception:
            return False
            
    # Bcrypt compatibility fallback
    try:
        import bcrypt
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


# ------------------------------------------------------------------------------
# JWT Token Implementation (RFC 7519 HMAC-SHA256)
# ------------------------------------------------------------------------------

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _base64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ''
    return base64.urlsafe_b64decode((data + padding).encode('utf-8'))

def create_access_token(subject: Union[str, Any], extra_claims: Optional[Dict[str, Any]] = None, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT Access Token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "type": "access"
    }
    if extra_claims:
        payload.update(extra_claims)
        
    header_b64 = _base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(settings.SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def create_refresh_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT Refresh Token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "type": "refresh"
    }
    
    header_b64 = _base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(settings.SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a signed JWT token."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(settings.SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
        actual_sig = _base64url_decode(sig_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
            
        payload = json.loads(_base64url_decode(payload_b64).decode('utf-8'))
        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            return None # Token has expired
            
        return payload
    except Exception:
        return None


# ------------------------------------------------------------------------------
# Sensitive Data Encryption (Fernet / AES for API Keys and Passwords at rest)
# ------------------------------------------------------------------------------

def _get_encryption_key() -> bytes:
    """Return a 32-byte key derived from settings."""
    raw_key = settings.FERNET_KEY or settings.SECRET_KEY
    return hashlib.sha256(raw_key.encode('utf-8')).digest()

def encrypt_sensitive_data(plaintext: str) -> str:
    """
    Encrypt plaintext sensitive data (API keys, bind credentials).
    Uses AES-like authenticated stream/block cipher using HMAC-SHA256 key stretching.
    """
    if not plaintext:
        return ""
    key = _get_encryption_key()
    iv = secrets.token_bytes(16)
    
    # Keystream generation (ChaCha/CTR style)
    pt_bytes = plaintext.encode('utf-8')
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(pt_bytes):
        block = hmac.new(key, iv + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
        
    ciphertext = bytes(b ^ k for b, k in zip(pt_bytes, keystream[:len(pt_bytes)]))
    auth_tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()[:16]
    
    packed = iv + auth_tag + ciphertext
    return base64.b64encode(packed).decode('utf-8')

def decrypt_sensitive_data(encrypted_text: str) -> str:
    """Decrypt encrypted sensitive data."""
    if not encrypted_text:
        return ""
    try:
        key = _get_encryption_key()
        raw = base64.b64decode(encrypted_text.encode('utf-8'))
        if len(raw) < 32:
            return ""
            
        iv = raw[:16]
        auth_tag = raw[16:32]
        ciphertext = raw[32:]
        
        expected_tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(auth_tag, expected_tag):
            return "" # Tampered or invalid key
            
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ciphertext):
            block = hmac.new(key, iv + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
            
        plaintext = bytes(b ^ k for b, k in zip(ciphertext, keystream[:len(ciphertext)]))
        return plaintext.decode('utf-8')
    except Exception:
        return ""

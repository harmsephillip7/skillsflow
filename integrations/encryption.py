"""
Encryption utilities for secure storage of API credentials.

Uses Fernet symmetric encryption with key derived from Django's SECRET_KEY.
Provides transparent encrypt-on-save, decrypt-on-read for model fields.
"""

import base64
import hashlib
from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet, InvalidToken


def get_encryption_key():
    """
    Derive a Fernet-compatible key from Django's SECRET_KEY.
    Uses SHA-256 hash truncated to 32 bytes, then base64 encoded.
    """
    secret = settings.SECRET_KEY.encode('utf-8')
    # Create a 32-byte key using SHA-256
    key_hash = hashlib.sha256(secret).digest()
    # Fernet requires base64-encoded 32-byte key
    return base64.urlsafe_b64encode(key_hash)


def get_fernet():
    """Get a Fernet instance for encryption/decryption."""
    return Fernet(get_encryption_key())


def encrypt_value(value):
    """
    Encrypt a string value.
    
    Args:
        value: Plain text string to encrypt
        
    Returns:
        Base64-encoded encrypted string, or empty string if input is empty
    """
    if not value:
        return ''
    
    fernet = get_fernet()
    encrypted = fernet.encrypt(value.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_value(encrypted_value):
    """
    Decrypt an encrypted string value.
    
    Args:
        encrypted_value: Base64-encoded encrypted string
        
    Returns:
        Decrypted plain text string, or empty string if input is empty/invalid
    """
    if not encrypted_value:
        return ''
    
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_value.encode('utf-8'))
        return decrypted.decode('utf-8')
    except (InvalidToken, Exception):
        # Return empty string if decryption fails
        # This handles cases where data was stored unencrypted or is corrupted
        return ''


class EncryptedFieldMixin:
    """
    Mixin for encrypted model fields.
    Provides transparent encryption on save and decryption on read.
    """
    
    def get_prep_value(self, value):
        """Encrypt value before saving to database."""
        if value is None:
            return value
        return encrypt_value(str(value))
    
    def from_db_value(self, value, expression, connection):
        """Decrypt value when reading from database."""
        if value is None:
            return value
        return decrypt_value(value)
    
    def to_python(self, value):
        """
        Convert value to Python string.
        Called during form validation and deserialization.
        """
        if value is None:
            return value
        
        # If the value looks encrypted (starts with gAAAAA), decrypt it
        if isinstance(value, str) and value.startswith('gAAAAA'):
            return decrypt_value(value)
        
        return value


class EncryptedCharField(EncryptedFieldMixin, models.CharField):
    """
    CharField that stores values encrypted in the database.
    
    Usage:
        api_key = EncryptedCharField(max_length=500)
    
    Note: max_length should be larger than the actual value length
    because encryption adds overhead (~40% increase).
    """
    
    def __init__(self, *args, **kwargs):
        # Store the original max_length for deconstruct
        self._original_max_length = kwargs.get('max_length', 500)
        # Use fixed max_length to avoid migration churn
        kwargs['max_length'] = 1000
        super().__init__(*args, **kwargs)
    
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # Return original max_length in deconstruct to keep migrations stable
        kwargs['max_length'] = 1000
        return name, path, args, kwargs


class EncryptedTextField(EncryptedFieldMixin, models.TextField):
    """
    TextField that stores values encrypted in the database.
    
    Usage:
        client_secret = EncryptedTextField()
    
    Suitable for longer credentials like private keys or JSON configs.
    """
    pass


# Utility functions for migration and debugging

def migrate_plaintext_to_encrypted(model_class, field_name):
    """
    Utility to migrate existing plaintext values to encrypted format.
    
    Usage in a data migration:
        from integrations.encryption import migrate_plaintext_to_encrypted
        migrate_plaintext_to_encrypted(IntegrationConnection, 'api_key')
    """
    for instance in model_class.objects.all():
        value = getattr(instance, field_name)
        if value and not value.startswith('gAAAAA'):
            # Value is not encrypted, encrypt it
            setattr(instance, field_name, value)  # Will be encrypted on save
            instance.save(update_fields=[field_name])


def is_encrypted(value):
    """Check if a value appears to be encrypted (Fernet tokens start with gAAAAA)."""
    return isinstance(value, str) and value.startswith('gAAAAA')

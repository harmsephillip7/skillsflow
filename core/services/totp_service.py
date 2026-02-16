"""
TOTP (Time-based One-Time Password) Service
Handles Google Authenticator integration for two-factor authentication
"""
import pyotp
import qrcode
from io import BytesIO
import base64
import secrets
from typing import Tuple, List, Dict
from django.utils import timezone


class TOTPService:
    """Service for managing TOTP-based 2FA"""
    
    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret
        Returns: Base32-encoded secret string
        """
        return pyotp.random_base32()
    
    @staticmethod
    def get_totp_provisioning_uri(secret: str, email: str, issuer: str = "SkillsFlow ERP") -> str:
        """
        Generate the provisioning URI for QR code
        This URI is scanned by Google Authenticator or similar apps
        
        Args:
            secret: Base32-encoded TOTP secret
            email: User's email address (used as account name)
            issuer: Name of the service/issuer
            
        Returns: Provisioning URI string
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=email,
            issuer_name=issuer
        )
    
    @staticmethod
    def generate_qr_code(provisioning_uri: str) -> str:
        """
        Generate QR code from provisioning URI
        
        Args:
            provisioning_uri: The provisioning URI for TOTP
            
        Returns: Base64-encoded PNG image as data URL
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        img_bytes = img_io.getvalue()
        
        # Return as data URL
        img_base64 = base64.b64encode(img_bytes).decode()
        return f"data:image/png;base64,{img_base64}"
    
    @staticmethod
    def verify_token(secret: str, token: str, window: int = 1) -> bool:
        """
        Verify a TOTP token against the secret
        
        Args:
            secret: Base32-encoded TOTP secret
            token: The 6-digit code from Google Authenticator
            window: Number of time windows to check (for clock skew tolerance)
            
        Returns: True if token is valid, False otherwise
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=window)
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """
        Generate backup codes for account recovery if device is lost
        
        Args:
            count: Number of codes to generate
            
        Returns: List of backup codes
        """
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric codes
            code = secrets.token_hex(4).upper()  # 8 characters
            codes.append(code)
        return codes
    
    @staticmethod
    def format_backup_codes(codes: List[str]) -> str:
        """
        Format backup codes for storage
        
        Args:
            codes: List of backup codes
            
        Returns: Comma-separated string of codes
        """
        return ",".join(codes)
    
    @staticmethod
    def parse_backup_codes(backup_codes_str: str) -> List[str]:
        """
        Parse backup codes from storage format
        
        Args:
            backup_codes_str: Comma-separated string of backup codes
            
        Returns: List of backup codes
        """
        if not backup_codes_str:
            return []
        return backup_codes_str.split(",")
    
    @staticmethod
    def verify_backup_code(secret: str, code: str) -> bool:
        """
        Verify if a code is a valid backup code
        Note: This does NOT consume the code. Must be handled separately.
        
        Args:
            secret: The backup codes string
            code: The code to verify
            
        Returns: True if code exists, False otherwise
        """
        codes = TOTPService.parse_backup_codes(secret)
        return code.upper() in [c.upper() for c in codes]
    
    @staticmethod
    def consume_backup_code(backup_codes_str: str, code: str) -> Tuple[bool, str]:
        """
        Verify and remove a backup code from the list
        
        Args:
            backup_codes_str: Comma-separated string of backup codes
            code: The code to consume
            
        Returns: Tuple of (success, remaining_codes_str)
        """
        codes = TOTPService.parse_backup_codes(backup_codes_str)
        
        for i, stored_code in enumerate(codes):
            if stored_code.upper() == code.upper():
                codes.pop(i)
                return True, TOTPService.format_backup_codes(codes)
        
        return False, backup_codes_str
    
    @staticmethod
    def get_totp_setup_info(user_email: str, issuer: str = "SkillsFlow ERP") -> Dict:
        """
        Generate complete setup information for user to enable 2FA
        
        Args:
            user_email: User's email address
            issuer: Service name
            
        Returns: Dictionary with secret, QR code, and backup codes
        """
        secret = TOTPService.generate_secret()
        provisioning_uri = TOTPService.get_totp_provisioning_uri(secret, user_email, issuer)
        qr_code = TOTPService.generate_qr_code(provisioning_uri)
        backup_codes = TOTPService.generate_backup_codes()
        
        return {
            "secret": secret,
            "qr_code": qr_code,
            "provisioning_uri": provisioning_uri,
            "backup_codes": backup_codes,
            "backup_codes_formatted": TOTPService.format_backup_codes(backup_codes),
        }

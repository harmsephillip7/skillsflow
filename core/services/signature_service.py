"""
Digital Signature Capture Service
Handles signature capture, processing, storage, and validation.

Features:
- Base64 canvas data processing to PNG with transparent background
- Image standardization to 400x150px
- SHA-256 hash generation for integrity verification
- POPIA-compliant consent capture with audit trail
- Lock mechanism with admin unlock capability
"""
import base64
import hashlib
import io
import logging
from datetime import datetime
from typing import Optional, Tuple, Union

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from core.models import User, SignatureCapture, FacilitatorProfile, WorkplaceOfficerProfile
from corporate.models import HostMentor
from learners.models import Learner

logger = logging.getLogger(__name__)

# Standard signature dimensions (width x height in pixels)
SIGNATURE_WIDTH = 400
SIGNATURE_HEIGHT = 150


class SignatureService:
    """
    Service for capturing and managing digital signatures.
    
    Usage:
        service = SignatureService()
        
        # Capture for a learner
        success, message = service.capture_signature_for_learner(
            learner=learner,
            base64_data='data:image/png;base64,...',
            request=request,
            consent_given=True
        )
        
        # Admin unlock
        success = service.unlock_signature(
            profile=learner,
            admin_user=admin,
            reason='Learner requested re-signing due to name change'
        )
    """
    
    POPIA_CONSENT_TEXT = (
        "I consent to SkillsFlow storing and using my digital signature for the purpose of "
        "generating compliance documents, agreements, and certificates on my behalf. "
        "I understand that my signature will be securely stored in accordance with the "
        "Protection of Personal Information Act (POPIA) and will only be used for official "
        "training-related documentation. I confirm that I am the person whose signature is "
        "being captured and that this digital signature has the same legal effect as my "
        "handwritten signature."
    )
    
    def process_base64_signature(self, base64_data: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Process base64 canvas data into a standardized PNG image.
        
        Args:
            base64_data: Base64-encoded PNG data (with or without data URI prefix)
            
        Returns:
            Tuple of (image_bytes, error_message)
        """
        try:
            # Remove data URI prefix if present
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
            
            # Decode base64 data
            image_data = base64.b64decode(base64_data)
            
            # Open image with Pillow
            image = Image.open(io.BytesIO(image_data))
            
            # Ensure RGBA mode for transparency support
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Create a new transparent image with standard dimensions
            standardized = Image.new('RGBA', (SIGNATURE_WIDTH, SIGNATURE_HEIGHT), (0, 0, 0, 0))
            
            # Calculate scaling to fit within standard dimensions while maintaining aspect ratio
            width_ratio = SIGNATURE_WIDTH / image.width
            height_ratio = SIGNATURE_HEIGHT / image.height
            scale_ratio = min(width_ratio, height_ratio, 1.0)  # Don't upscale
            
            new_width = int(image.width * scale_ratio)
            new_height = int(image.height * scale_ratio)
            
            # Resize if necessary
            if scale_ratio < 1.0:
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Center the signature on the standardized canvas
            x_offset = (SIGNATURE_WIDTH - new_width) // 2
            y_offset = (SIGNATURE_HEIGHT - new_height) // 2
            
            standardized.paste(image, (x_offset, y_offset), image)
            
            # Save to bytes
            output = io.BytesIO()
            standardized.save(output, format='PNG', optimize=True)
            output.seek(0)
            
            return output.getvalue(), None
            
        except Exception as e:
            logger.error(f"Error processing signature image: {e}")
            return None, f"Failed to process signature image: {str(e)}"
    
    def compute_hash(self, image_bytes: bytes) -> str:
        """Compute SHA-256 hash of image bytes for integrity verification."""
        return hashlib.sha256(image_bytes).hexdigest()
    
    def get_client_info(self, request) -> Tuple[Optional[str], str]:
        """Extract client IP address and user agent from request."""
        # Get IP address (handle proxy headers)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        return ip_address, user_agent
    
    def capture_signature_for_learner(
        self,
        learner: Learner,
        base64_data: str,
        request,
        consent_given: bool = True
    ) -> Tuple[bool, str]:
        """
        Capture digital signature for a learner.
        
        Args:
            learner: Learner instance
            base64_data: Base64-encoded signature image
            request: HTTP request object
            consent_given: POPIA consent confirmation
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Check if already locked
        if learner.signature_locked:
            return False, "Signature is locked and cannot be modified. Contact admin for assistance."
        
        # Require consent
        if not consent_given:
            return False, "POPIA consent is required to capture signature."
        
        # Process the image
        image_bytes, error = self.process_base64_signature(base64_data)
        if error:
            return False, error
        
        # Compute hash
        signature_hash = self.compute_hash(image_bytes)
        
        # Get client info
        ip_address, user_agent = self.get_client_info(request)
        
        # Generate filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"learner_{learner.id}_{timestamp}.png"
        
        # Save to learner
        learner.signature.save(filename, ContentFile(image_bytes), save=False)
        learner.signature_hash = signature_hash
        learner.signature_captured_at = timezone.now()
        learner.signature_locked = True  # Lock after capture
        learner.save(update_fields=['signature', 'signature_hash', 'signature_captured_at', 'signature_locked'])
        
        # Also create SignatureCapture record for audit trail if user exists
        if learner.user:
            SignatureCapture.objects.update_or_create(
                user=learner.user,
                defaults={
                    'signature_image': learner.signature,
                    'signature_hash': signature_hash,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'popia_consent_text': self.POPIA_CONSENT_TEXT,
                    'popia_consent_given': consent_given,
                    'is_locked': True,
                }
            )
        
        logger.info(f"Signature captured for Learner {learner.id} from IP {ip_address}")
        return True, "Signature captured successfully."
    
    def capture_signature_for_facilitator(
        self,
        facilitator: FacilitatorProfile,
        base64_data: str,
        request,
        consent_given: bool = True
    ) -> Tuple[bool, str]:
        """Capture digital signature for a facilitator."""
        if facilitator.signature_locked:
            return False, "Signature is locked and cannot be modified. Contact admin for assistance."
        
        if not consent_given:
            return False, "POPIA consent is required to capture signature."
        
        image_bytes, error = self.process_base64_signature(base64_data)
        if error:
            return False, error
        
        signature_hash = self.compute_hash(image_bytes)
        ip_address, user_agent = self.get_client_info(request)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"facilitator_{facilitator.id}_{timestamp}.png"
        
        facilitator.signature.save(filename, ContentFile(image_bytes), save=False)
        facilitator.signature_hash = signature_hash
        facilitator.signature_captured_at = timezone.now()
        facilitator.signature_locked = True
        facilitator.save(update_fields=['signature', 'signature_hash', 'signature_captured_at', 'signature_locked'])
        
        # Create SignatureCapture audit record
        SignatureCapture.objects.update_or_create(
            user=facilitator.user,
            defaults={
                'signature_image': facilitator.signature,
                'signature_hash': signature_hash,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'popia_consent_text': self.POPIA_CONSENT_TEXT,
                'popia_consent_given': consent_given,
                'is_locked': True,
            }
        )
        
        logger.info(f"Signature captured for Facilitator {facilitator.id} from IP {ip_address}")
        return True, "Signature captured successfully."
    
    def capture_signature_for_mentor(
        self,
        mentor: HostMentor,
        base64_data: str,
        request,
        consent_given: bool = True
    ) -> Tuple[bool, str]:
        """Capture digital signature for a mentor."""
        if mentor.signature_locked:
            return False, "Signature is locked and cannot be modified. Contact admin for assistance."
        
        if not consent_given:
            return False, "POPIA consent is required to capture signature."
        
        image_bytes, error = self.process_base64_signature(base64_data)
        if error:
            return False, error
        
        signature_hash = self.compute_hash(image_bytes)
        ip_address, user_agent = self.get_client_info(request)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"mentor_{mentor.id}_{timestamp}.png"
        
        mentor.signature.save(filename, ContentFile(image_bytes), save=False)
        mentor.signature_hash = signature_hash
        mentor.signature_captured_at = timezone.now()
        mentor.signature_locked = True
        mentor.save(update_fields=['signature', 'signature_hash', 'signature_captured_at', 'signature_locked'])
        
        # Create SignatureCapture audit record if user exists
        if mentor.user:
            SignatureCapture.objects.update_or_create(
                user=mentor.user,
                defaults={
                    'signature_image': mentor.signature,
                    'signature_hash': signature_hash,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'popia_consent_text': self.POPIA_CONSENT_TEXT,
                    'popia_consent_given': consent_given,
                    'is_locked': True,
                }
            )
        
        logger.info(f"Signature captured for Mentor {mentor.id} from IP {ip_address}")
        return True, "Signature captured successfully."
    
    def capture_signature_for_officer(
        self,
        officer: WorkplaceOfficerProfile,
        base64_data: str,
        request,
        consent_given: bool = True
    ) -> Tuple[bool, str]:
        """Capture digital signature for a workplace officer."""
        if officer.signature_locked:
            return False, "Signature is locked and cannot be modified. Contact admin for assistance."
        
        if not consent_given:
            return False, "POPIA consent is required to capture signature."
        
        image_bytes, error = self.process_base64_signature(base64_data)
        if error:
            return False, error
        
        signature_hash = self.compute_hash(image_bytes)
        ip_address, user_agent = self.get_client_info(request)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"officer_{officer.id}_{timestamp}.png"
        
        officer.signature.save(filename, ContentFile(image_bytes), save=False)
        officer.signature_hash = signature_hash
        officer.signature_captured_at = timezone.now()
        officer.signature_locked = True
        officer.save(update_fields=['signature', 'signature_hash', 'signature_captured_at', 'signature_locked'])
        
        # Create SignatureCapture audit record
        SignatureCapture.objects.update_or_create(
            user=officer.user,
            defaults={
                'signature_image': officer.signature,
                'signature_hash': signature_hash,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'popia_consent_text': self.POPIA_CONSENT_TEXT,
                'popia_consent_given': consent_given,
                'is_locked': True,
            }
        )
        
        logger.info(f"Signature captured for Officer {officer.id} from IP {ip_address}")
        return True, "Signature captured successfully."
    
    def unlock_signature(
        self,
        profile: Union[Learner, FacilitatorProfile, HostMentor, WorkplaceOfficerProfile],
        admin_user: User,
        reason: str
    ) -> Tuple[bool, str]:
        """
        Unlock a signature for re-capture (admin only).
        
        Args:
            profile: Profile instance with signature fields
            admin_user: Admin user performing the unlock
            reason: Reason for unlocking (required for audit)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not reason.strip():
            return False, "Unlock reason is required for audit trail."
        
        if not admin_user.is_staff:
            return False, "Only staff members can unlock signatures."
        
        profile.signature_locked = False
        profile.save(update_fields=['signature_locked'])
        
        # Update SignatureCapture audit record if user exists
        user = getattr(profile, 'user', None)
        if user:
            try:
                signature_capture = SignatureCapture.objects.get(user=user)
                signature_capture.unlock(admin_user, reason)
            except SignatureCapture.DoesNotExist:
                pass
        
        profile_type = profile.__class__.__name__
        profile_id = profile.id
        logger.info(
            f"Signature unlocked for {profile_type} {profile_id} by {admin_user.email}. "
            f"Reason: {reason}"
        )
        
        return True, f"Signature unlocked. {profile_type} can now provide a new signature."
    
    def verify_signature_integrity(
        self,
        profile: Union[Learner, FacilitatorProfile, HostMentor, WorkplaceOfficerProfile]
    ) -> Tuple[bool, str]:
        """
        Verify that a signature has not been tampered with.
        
        Args:
            profile: Profile instance with signature fields
            
        Returns:
            Tuple of (valid: bool, message: str)
        """
        if not profile.signature:
            return False, "No signature on file."
        
        if not profile.signature_hash:
            return False, "No signature hash stored for verification."
        
        try:
            profile.signature.seek(0)
            computed_hash = hashlib.sha256(profile.signature.read()).hexdigest()
            
            if computed_hash == profile.signature_hash:
                return True, "Signature integrity verified."
            else:
                return False, "Signature integrity check failed - file may have been modified."
        except Exception as e:
            return False, f"Error verifying signature: {str(e)}"
    
    def get_signature_for_document(
        self,
        profile: Union[Learner, FacilitatorProfile, HostMentor, WorkplaceOfficerProfile]
    ) -> Optional[bytes]:
        """
        Get signature image bytes for embedding in documents.
        
        Args:
            profile: Profile instance with signature fields
            
        Returns:
            Image bytes or None if no signature
        """
        if not profile.signature:
            return None
        
        try:
            profile.signature.seek(0)
            return profile.signature.read()
        except Exception as e:
            logger.error(f"Error reading signature for document: {e}")
            return None

"""
Card Scanner Service using OpenAI Vision API
Extracts contact information from photos of learner "Contact Me" cards
"""
import base64
import json
import logging
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from django.conf import settings

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContact:
    """Structured contact data extracted from a card"""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    phone_secondary: str = ""
    whatsapp_number: str = ""
    
    # School leaver info
    school_name: str = ""
    grade: str = ""
    expected_matric_year: Optional[int] = None
    
    # Parent/Guardian
    parent_name: str = ""
    parent_phone: str = ""
    parent_email: str = ""
    parent_relationship: str = ""
    
    # Interest
    qualification_interest: str = ""
    
    # Additional
    employer_name: str = ""
    notes: str = ""
    
    # Confidence
    confidence_score: float = 0.0
    raw_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def has_minimum_data(self) -> bool:
        """Check if we have at least a name and one contact method"""
        has_name = bool(self.first_name or self.last_name)
        has_contact = bool(self.email or self.phone or self.whatsapp_number)
        return has_name and has_contact


class CardScannerService:
    """
    Service for scanning contact cards using AI vision
    """
    
    EXTRACTION_PROMPT = """You are an expert at extracting contact information from photos of "Contact Me" cards, 
business cards, or registration forms used at education exhibitions and events in South Africa.

Analyze this image and extract all contact information you can find. The card may be handwritten or printed.

Return a JSON object with these fields (use empty string "" for missing data, not null):
{
    "first_name": "Person's first name",
    "last_name": "Person's surname/last name",
    "email": "Email address",
    "phone": "Primary phone number (format: 0XX XXX XXXX or +27...)",
    "phone_secondary": "Secondary phone if present",
    "whatsapp_number": "WhatsApp number if different from phone",
    "school_name": "School name if this is a student",
    "grade": "Grade/Year level (e.g., 'Grade 11', 'Grade 12', 'Matric')",
    "expected_matric_year": null or year number (e.g., 2026),
    "parent_name": "Parent/Guardian name if listed",
    "parent_phone": "Parent/Guardian phone",
    "parent_email": "Parent/Guardian email",
    "parent_relationship": "Relationship (Mother, Father, Guardian)",
    "qualification_interest": "What course/qualification they're interested in",
    "employer_name": "Company name if they work",
    "notes": "Any other relevant info (job title, special requests, etc.)",
    "confidence_score": 0.0 to 1.0 based on how confident you are in the extraction,
    "raw_text": "All readable text from the card"
}

Important South African context:
- Phone numbers typically start with 0 (mobile: 06x, 07x, 08x) or landline (0XX)
- Grades are Grade 8-12, with Grade 12 also called Matric
- Common qualifications include: N1-N6 certificates, trade tests, apprenticeships, learnerships
- Look for school logos or names

Return ONLY the JSON object, no other text."""

    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not self.api_key:
            import os
            self.api_key = os.environ.get('OPENAI_API_KEY')
        
        if OpenAI and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OpenAI client not available - card scanning disabled")
    
    def is_available(self) -> bool:
        """Check if the service is available"""
        return self.client is not None
    
    def _encode_image(self, image_data: bytes) -> str:
        """Encode image bytes to base64"""
        return base64.b64encode(image_data).decode('utf-8')
    
    def _detect_image_type(self, image_data: bytes) -> str:
        """Detect image MIME type from bytes"""
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image/png'
        elif image_data[:2] == b'\xff\xd8':
            return 'image/jpeg'
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return 'image/webp'
        elif image_data[:3] == b'GIF':
            return 'image/gif'
        return 'image/jpeg'  # Default
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize South African phone numbers"""
        if not phone:
            return ""
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Handle +27 format
        if cleaned.startswith('+27'):
            cleaned = '0' + cleaned[3:]
        elif cleaned.startswith('27') and len(cleaned) == 11:
            cleaned = '0' + cleaned[2:]
        
        # Format as 0XX XXX XXXX if 10 digits
        if len(cleaned) == 10 and cleaned.startswith('0'):
            return f"{cleaned[:3]} {cleaned[3:6]} {cleaned[6:]}"
        
        return cleaned
    
    def _parse_response(self, response_text: str) -> ExtractedContact:
        """Parse the AI response into ExtractedContact"""
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response_text)
            
            # Normalize phone numbers
            data['phone'] = self._normalize_phone(data.get('phone', ''))
            data['phone_secondary'] = self._normalize_phone(data.get('phone_secondary', ''))
            data['whatsapp_number'] = self._normalize_phone(data.get('whatsapp_number', ''))
            data['parent_phone'] = self._normalize_phone(data.get('parent_phone', ''))
            
            # Handle expected_matric_year
            matric_year = data.get('expected_matric_year')
            if matric_year and isinstance(matric_year, str):
                try:
                    data['expected_matric_year'] = int(matric_year)
                except ValueError:
                    data['expected_matric_year'] = None
            
            # Clean empty values
            for key in data:
                if data[key] is None:
                    data[key] = "" if key != 'expected_matric_year' and key != 'confidence_score' else data[key]
            
            return ExtractedContact(**{k: v for k, v in data.items() if k in ExtractedContact.__dataclass_fields__})
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return ExtractedContact(
                notes=f"Failed to parse response: {response_text[:500]}",
                confidence_score=0.0
            )
    
    def scan_card(self, image_data: bytes) -> ExtractedContact:
        """
        Scan a single card image and extract contact information
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            ExtractedContact with extracted data
        """
        if not self.is_available():
            raise RuntimeError("Card scanner service not available - OpenAI API key not configured")
        
        try:
            # Encode image
            base64_image = self._encode_image(image_data)
            image_type = self._detect_image_type(image_data)
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model="gpt-4o",  # GPT-4o has best vision capabilities
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.EXTRACTION_PROMPT
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{base64_image}",
                                    "detail": "high"  # Use high detail for better text extraction
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1  # Low temperature for more consistent extraction
            )
            
            # Parse the response
            response_text = response.choices[0].message.content
            logger.info(f"OpenAI Vision response: {response_text[:200]}...")
            
            return self._parse_response(response_text)
            
        except Exception as e:
            logger.exception(f"Error scanning card: {e}")
            raise RuntimeError(f"Failed to scan card: {str(e)}")
    
    def scan_cards_batch(self, images: List[bytes]) -> List[ExtractedContact]:
        """
        Scan multiple card images
        
        Args:
            images: List of raw image bytes
            
        Returns:
            List of ExtractedContact objects
        """
        results = []
        for image_data in images:
            try:
                result = self.scan_card(image_data)
                results.append(result)
            except Exception as e:
                logger.error(f"Error scanning card in batch: {e}")
                results.append(ExtractedContact(
                    notes=f"Scan failed: {str(e)}",
                    confidence_score=0.0
                ))
        return results


# Singleton instance
_scanner_instance: Optional[CardScannerService] = None


def get_card_scanner() -> CardScannerService:
    """Get or create the card scanner service singleton"""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = CardScannerService()
    return _scanner_instance

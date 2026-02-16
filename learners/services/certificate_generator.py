"""
Financial Literacy Certificate Generator
Generates PDF certificates with QR codes and blockchain anchoring
"""
import hashlib
import io
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
import qrcode


class FinancialLiteracyCertificateGenerator:
    """Generate branded PDF certificates for financial literacy completion"""
    
    def __init__(self):
        self.page_width, self.page_height = landscape(A4)
        
    def generate_certificate(self, progress):
        """
        Generate certificate PDF for a FinancialLiteracyProgress record
        
        Args:
            progress: FinancialLiteracyProgress instance
            
        Returns:
            tuple: (pdf_content, certificate_hash)
        """
        # Store progress for use in footer signature embedding
        self._current_progress = progress
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        
        # Draw certificate border
        self._draw_border(c)
        
        # Add watermark
        self._add_watermark(c)
        
        # Certificate title
        c.setFont("Helvetica-Bold", 36)
        c.setFillColor(colors.HexColor('#1e40af'))  # Primary blue
        c.drawCentredString(self.page_width / 2, self.page_height - 1.5*inch, 
                           "Certificate of Completion")
        
        # Subtitle
        c.setFont("Helvetica", 16)
        c.setFillColor(colors.HexColor('#374151'))  # Gray
        c.drawCentredString(self.page_width / 2, self.page_height - 2*inch,
                           "Financial Literacy Program")
        
        # Learner name
        c.setFont("Helvetica", 14)
        c.drawCentredString(self.page_width / 2, self.page_height - 2.8*inch,
                           "This certifies that")
        
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(colors.HexColor('#1e40af'))
        learner_name = progress.learner.get_full_name()
        c.drawCentredString(self.page_width / 2, self.page_height - 3.4*inch,
                           learner_name)
        
        # Module title
        c.setFont("Helvetica", 14)
        c.setFillColor(colors.HexColor('#374151'))
        c.drawCentredString(self.page_width / 2, self.page_height - 4*inch,
                           "has successfully completed the module")
        
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(colors.HexColor('#059669'))  # Green
        c.drawCentredString(self.page_width / 2, self.page_height - 4.5*inch,
                           progress.module.title)
        
        # Completion details
        completion_date = progress.completed_at or datetime.now()
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.HexColor('#6b7280'))
        
        details_y = self.page_height - 5.2*inch
        c.drawCentredString(self.page_width / 2, details_y,
                           f"Completed on {completion_date.strftime('%d %B %Y')}")
        
        if progress.score:
            c.drawCentredString(self.page_width / 2, details_y - 0.3*inch,
                              f"Score: {progress.score}%")
        
        # Duration
        c.drawCentredString(self.page_width / 2, details_y - 0.6*inch,
                           f"Duration: {progress.module.duration_minutes} minutes")
        
        # Verification code and QR code
        self._add_verification_section(c, progress)
        
        # Footer
        self._add_footer(c)
        
        # Finalize PDF
        c.showPage()
        c.save()
        
        # Get PDF content and compute hash
        pdf_content = buffer.getvalue()
        certificate_hash = hashlib.sha256(pdf_content).hexdigest()
        
        buffer.close()
        
        return pdf_content, certificate_hash
    
    def _draw_border(self, c):
        """Draw decorative border around certificate"""
        c.setStrokeColor(colors.HexColor('#1e40af'))
        c.setLineWidth(4)
        margin = 0.5 * inch
        c.rect(margin, margin, 
               self.page_width - 2*margin, 
               self.page_height - 2*margin)
        
        # Inner border
        c.setStrokeColor(colors.HexColor('#3b82f6'))
        c.setLineWidth(1)
        inner_margin = 0.6 * inch
        c.rect(inner_margin, inner_margin,
               self.page_width - 2*inner_margin,
               self.page_height - 2*inner_margin)
    
    def _add_watermark(self, c):
        """Add semi-transparent watermark"""
        c.saveState()
        c.setFillColor(colors.HexColor('#e0e7ff'), alpha=0.1)
        c.setFont("Helvetica-Bold", 72)
        c.translate(self.page_width / 2, self.page_height / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, "SKILLSFLOW")
        c.restoreState()
    
    def _add_verification_section(self, c, progress):
        """Add QR code and verification information"""
        # Generate QR code
        verification_url = f"{getattr(settings, 'SITE_URL', 'https://skillsflow.co.za')}/verify-certificate/{progress.certificate_code}/"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(verification_url)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR to buffer
        qr_buffer = io.BytesIO()
        qr_image.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        # Draw QR code
        qr_size = 1.2 * inch
        qr_x = self.page_width - 2.5*inch
        qr_y = 0.8*inch
        c.drawImage(io.BytesIO(qr_buffer.getvalue()), 
                   qr_x, qr_y, 
                   width=qr_size, height=qr_size)
        
        # Verification text
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor('#6b7280'))
        c.drawString(qr_x, qr_y - 0.15*inch, "Scan to verify")
        
        # Verification code
        c.setFont("Helvetica-Bold", 9)
        c.drawString(1*inch, 1.2*inch, "Verification Code:")
        c.setFont("Courier", 8)
        c.drawString(1*inch, 1*inch, str(progress.certificate_code))
    
    def _add_footer(self, c):
        """Add certificate footer with signatures"""
        y_position = 1.5 * inch
        
        # Signature lines
        c.setStrokeColor(colors.HexColor('#9ca3af'))
        c.setLineWidth(1)
        
        # Left signature (Administrator)
        left_x = 2 * inch
        
        # Right signature (Institution)
        right_x = self.page_width - 4*inch
        
        # Try to add actual signatures from profiles
        learner = getattr(self, '_current_progress', None)
        if learner:
            learner = learner.learner
        
        # Draw signature images if available, otherwise draw placeholder lines
        admin_signature_drawn = False
        learner_signature_drawn = False
        
        # Try to get learner signature
        if learner and hasattr(learner, 'signature') and learner.signature:
            try:
                sig_img = self._get_signature_image(learner.signature)
                if sig_img:
                    # Draw learner signature (left side)
                    sig_width = 2 * inch
                    sig_height = 0.75 * inch
                    c.drawImage(sig_img, 
                               left_x, y_position - 0.2*inch, 
                               width=sig_width, height=sig_height,
                               mask='auto')
                    learner_signature_drawn = True
            except Exception:
                pass
        
        # Draw placeholder line if no signature
        if not learner_signature_drawn:
            c.line(left_x, y_position, left_x + 2*inch, y_position)
        
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor('#374151'))
        c.drawCentredString(left_x + 1*inch, y_position - 0.3*inch, 
                           "Program Administrator")
        
        # Right side - institution signature (placeholder for now)
        c.line(right_x, y_position, right_x + 2*inch, y_position)
        c.drawCentredString(right_x + 1*inch, y_position - 0.3*inch,
                           "SkillsFlow Training Institute")
        
        # Date issued
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor('#6b7280'))
        c.drawCentredString(self.page_width / 2, 0.7*inch,
                           f"Issued: {datetime.now().strftime('%d %B %Y')}")
    
    def _get_signature_image(self, signature_field):
        """
        Get signature image from model field for embedding in PDF.
        
        Args:
            signature_field: ImageField containing signature PNG
            
        Returns:
            ImageReader or None
        """
        from reportlab.lib.utils import ImageReader
        
        try:
            if signature_field:
                signature_field.seek(0)
                img_data = io.BytesIO(signature_field.read())
                return ImageReader(img_data)
        except Exception:
            pass
        return None
    
    def save_certificate(self, progress):
        """
        Generate and save certificate, update progress record
        
        Args:
            progress: FinancialLiteracyProgress instance
            
        Returns:
            FinancialLiteracyProgress: Updated progress instance
        """
        from django.utils import timezone
        
        # Generate certificate
        pdf_content, certificate_hash = self.generate_certificate(progress)
        
        # Update progress record
        progress.certificate_hash = certificate_hash
        progress.certificate_issued_at = timezone.now()
        progress.save()
        
        return progress

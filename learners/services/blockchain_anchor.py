"""
Blockchain Anchoring Service
Anchors certificate hashes to blockchain for verification
"""
import hashlib
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class BlockchainAnchorService:
    """
    Service for anchoring certificate hashes to blockchain
    
    Supports multiple blockchain options:
    - Ethereum/Polygon for production
    - Local testing mode for development
    - Future: Integration with Blockcerts or other certificate platforms
    """
    
    def __init__(self):
        self.enabled = getattr(settings, 'BLOCKCHAIN_ANCHORING_ENABLED', False)
        self.provider = getattr(settings, 'BLOCKCHAIN_PROVIDER', 'TEST')
        self.contract_address = getattr(settings, 'BLOCKCHAIN_CONTRACT_ADDRESS', None)
        
    def anchor_certificate(self, certificate_hash, metadata=None):
        """
        Anchor a certificate hash to blockchain
        
        Args:
            certificate_hash: SHA-256 hash of certificate
            metadata: Optional dict with additional data
            
        Returns:
            dict: {
                'success': bool,
                'transaction_id': str or None,
                'block_number': int or None,
                'timestamp': datetime or None,
                'error': str or None
            }
        """
        if not self.enabled:
            logger.info(f"Blockchain anchoring disabled. Hash: {certificate_hash}")
            return {
                'success': False,
                'transaction_id': None,
                'error': 'Blockchain anchoring not enabled'
            }
        
        try:
            if self.provider == 'ETHEREUM':
                return self._anchor_to_ethereum(certificate_hash, metadata)
            elif self.provider == 'POLYGON':
                return self._anchor_to_polygon(certificate_hash, metadata)
            elif self.provider == 'TEST':
                return self._anchor_test_mode(certificate_hash, metadata)
            else:
                logger.error(f"Unknown blockchain provider: {self.provider}")
                return {
                    'success': False,
                    'error': f'Unknown provider: {self.provider}'
                }
        except Exception as e:
            logger.exception(f"Error anchoring certificate: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_certificate(self, certificate_hash, transaction_id):
        """
        Verify a certificate against blockchain record
        
        Args:
            certificate_hash: SHA-256 hash to verify
            transaction_id: Blockchain transaction ID
            
        Returns:
            dict: {
                'verified': bool,
                'timestamp': datetime or None,
                'error': str or None
            }
        """
        if not self.enabled or self.provider == 'TEST':
            # In test mode, assume all certificates are valid
            return {'verified': True, 'timestamp': None}
        
        try:
            if self.provider == 'ETHEREUM':
                return self._verify_on_ethereum(certificate_hash, transaction_id)
            elif self.provider == 'POLYGON':
                return self._verify_on_polygon(certificate_hash, transaction_id)
            else:
                return {'verified': False, 'error': 'Unknown provider'}
        except Exception as e:
            logger.exception(f"Error verifying certificate: {e}")
            return {'verified': False, 'error': str(e)}
    
    def _anchor_to_ethereum(self, certificate_hash, metadata):
        """Anchor to Ethereum mainnet or testnet"""
        # TODO: Implement Web3.py integration
        # from web3 import Web3
        # w3 = Web3(Web3.HTTPProvider(settings.ETHEREUM_RPC_URL))
        # ... contract interaction ...
        
        logger.warning("Ethereum anchoring not yet implemented")
        return {
            'success': False,
            'error': 'Ethereum anchoring not implemented'
        }
    
    def _anchor_to_polygon(self, certificate_hash, metadata):
        """Anchor to Polygon (low-cost alternative to Ethereum)"""
        # TODO: Implement Polygon integration
        # Similar to Ethereum but with Polygon RPC endpoints
        
        logger.warning("Polygon anchoring not yet implemented")
        return {
            'success': False,
            'error': 'Polygon anchoring not implemented'
        }
    
    def _anchor_test_mode(self, certificate_hash, metadata):
        """Test mode - simulate blockchain anchoring"""
        import uuid
        from datetime import datetime
        
        # Generate fake transaction ID
        tx_id = f"TEST-{uuid.uuid4().hex[:16]}"
        
        logger.info(f"TEST MODE: Anchored {certificate_hash} -> {tx_id}")
        
        return {
            'success': True,
            'transaction_id': tx_id,
            'block_number': 999999,
            'timestamp': datetime.now(),
            'error': None
        }
    
    def _verify_on_ethereum(self, certificate_hash, transaction_id):
        """Verify certificate on Ethereum"""
        # TODO: Implement verification
        return {'verified': False, 'error': 'Not implemented'}
    
    def _verify_on_polygon(self, certificate_hash, transaction_id):
        """Verify certificate on Polygon"""
        # TODO: Implement verification
        return {'verified': False, 'error': 'Not implemented'}


class BlockcertsIntegration:
    """
    Integration with Blockcerts open standard
    https://www.blockcerts.org/
    
    For production use with standardized certificate verification
    """
    
    def __init__(self):
        self.enabled = getattr(settings, 'BLOCKCERTS_ENABLED', False)
        
    def issue_certificate(self, progress):
        """
        Issue certificate following Blockcerts standard
        
        Args:
            progress: FinancialLiteracyProgress instance
            
        Returns:
            dict: Blockcerts JSON-LD certificate
        """
        if not self.enabled:
            return None
        
        # Generate Blockcerts-compliant JSON
        certificate = {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://w3id.org/blockcerts/v3"
            ],
            "type": ["VerifiableCredential", "BlockcertsCredential"],
            "id": f"urn:uuid:{progress.certificate_code}",
            "issuer": {
                "id": "https://skillsflow.co.za",
                "name": "SkillsFlow Training Institute",
                "email": "certificates@skillsflow.co.za"
            },
            "issuanceDate": progress.certificate_issued_at.isoformat() if progress.certificate_issued_at else None,
            "credentialSubject": {
                "id": f"learner:{progress.learner.learner_number}",
                "name": progress.learner.get_full_name(),
                "achievement": {
                    "name": progress.module.title,
                    "description": f"Financial Literacy Module - {progress.module.title}",
                    "criteria": f"Minimum score: {progress.module.passing_score}%",
                    "score": progress.score
                }
            }
        }
        
        return certificate


def anchor_certificate_async(progress_id):
    """
    Async task to anchor certificate to blockchain
    Can be called from Celery or other task queue
    
    Args:
        progress_id: FinancialLiteracyProgress ID
    """
    from learners.models import FinancialLiteracyProgress
    
    try:
        progress = FinancialLiteracyProgress.objects.get(id=progress_id)
        
        if not progress.certificate_hash:
            logger.error(f"No certificate hash for progress {progress_id}")
            return
        
        service = BlockchainAnchorService()
        result = service.anchor_certificate(progress.certificate_hash, metadata={
            'learner_id': progress.learner.id,
            'module_id': progress.module.id,
            'score': progress.score,
            'completed_at': progress.completed_at.isoformat() if progress.completed_at else None
        })
        
        if result['success']:
            progress.blockchain_tx_id = result['transaction_id']
            progress.save()
            logger.info(f"Successfully anchored certificate for progress {progress_id}")
        else:
            logger.error(f"Failed to anchor certificate: {result.get('error')}")
            
    except FinancialLiteracyProgress.DoesNotExist:
        logger.error(f"FinancialLiteracyProgress {progress_id} not found")
    except Exception as e:
        logger.exception(f"Error in anchor_certificate_async: {e}")

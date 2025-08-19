"""
Healthcare Application Guardrails System

This module implements comprehensive input and output guardrails using Guardrails AI
and Rebuff to prevent misuse, jailbreaks, and ensure safe healthcare interactions.

Key Features:
1. Input validation and sanitization
2. Output filtering for medical safety
3. Jailbreak detection and prevention
4. Healthcare-specific content validation
5. PII/PHI protection
6. Medical disclaimer enforcement
"""

import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from enum import Enum
import warnings

# Suppress pkg_resources deprecation warning from guardrails package
warnings.filterwarnings(
    "ignore", 
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module="guardrails.hub.install"
)

import guardrails as gd

from app.core.config import settings
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction

logger = logging.getLogger(__name__)

class GuardrailViolationType(Enum):
    """Types of guardrail violations"""
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    TOXIC_CONTENT = "toxic_content"
    PII_DETECTED = "pii_detected"
    MEDICAL_MISINFORMATION = "medical_misinformation"
    INAPPROPRIATE_MEDICAL_ADVICE = "inappropriate_medical_advice"
    PROFANITY = "profanity"
    OFF_TOPIC = "off_topic"
    EXCESSIVE_LENGTH = "excessive_length"
    INVALID_FORMAT = "invalid_format"
    COMPETITOR_MENTION = "competitor_mention"
    UNSAFE_MEDICAL_CONTENT = "unsafe_medical_content"
    MISSING_DISCLAIMER = "missing_disclaimer"
    DANGEROUS_ADVICE = "dangerous_advice"

class GuardrailResult:
    """Result of guardrail validation"""
    
    def __init__(
        self,
        is_safe: bool,
        filtered_content: str,
        violations: List[Dict[str, Any]] = None,
        confidence_score: float = 1.0,
        metadata: Dict[str, Any] = None
    ):
        self.is_safe = is_safe
        self.filtered_content = filtered_content
        self.violations = violations or []
        self.confidence_score = confidence_score
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization"""
        return {
            "is_safe": self.is_safe,
            "filtered_content": self.filtered_content,
            "violations": self.violations,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }

# Custom Guard class to replace Rebuff
class Guard:
    """Simple jailbreak detection guard"""
    
    def __init__(self):
        # Initialize with comprehensive jailbreak patterns
        self.jailbreak_patterns = [
            # Basic instruction override patterns
            r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions",
            r"forget\s+(?:all\s+)?(?:previous\s+)?instructions",
            r"disregard\s+(?:all\s+)?(?:previous\s+)?instructions",
            r"override\s+(?:all\s+)?(?:previous\s+)?instructions",
            r"bypass\s+(?:all\s+)?(?:safety\s+)?(?:measures|restrictions|guidelines)",
            
            # Role-playing and persona attacks
            r"act\s+as\s+(?:if\s+)?(?:you\s+)?(?:are\s+)?(?:not\s+)?(?:an?\s+)?(?:ai|assistant|chatbot)",
            r"pretend\s+(?:to\s+be|you\s+are)",
            r"roleplay\s+as",
            r"simulate\s+(?:being\s+)?(?:an?\s+)?",
            
            # Direct jailbreak terms
            r"jailbreak",
            r"do\s+anything\s+now",
            r"developer\s+mode",
            r"unrestricted\s+mode",
            r"god\s+mode",
            r"admin\s+mode",
            r"root\s+access",
            r"sudo\s+mode",
            
            # System manipulation
            r"break\s+(?:out\s+of\s+)?(?:your\s+)?(?:programming|constraints|limitations)",
            r"ignore\s+(?:your\s+)?(?:programming|constraints|limitations|guidelines)",
            r"override\s+(?:your\s+)?(?:safety|security|ethical)\s+(?:protocols|guidelines|measures)",
            
            # Malicious instruction patterns
            r"tell\s+me\s+how\s+to\s+(?:hack|break|exploit|attack)",
            r"step\s+by\s+step\s+(?:guide|instructions)\s+(?:to|for)\s+(?:hack|break|exploit)",
            r"provide\s+(?:dangerous|harmful|illegal)\s+(?:advice|information|instructions)",
            
            # Safety bypass patterns
            r"without\s+(?:safety|ethical|moral)\s+(?:considerations|restrictions|guidelines)",
            r"ignore\s+(?:safety|ethical|moral)\s+(?:considerations|restrictions|guidelines)",
            r"bypass\s+(?:safety|ethical|moral)\s+(?:considerations|restrictions|guidelines)",
        ]
        
        # Suspicious word combinations
        self.suspicious_combinations = [
            (['ignore', 'bypass', 'override', 'disable'], ['safety', 'security', 'restriction', 'guideline', 'rule']),
            (['hack', 'exploit', 'break', 'attack'], ['system', 'security', 'protection', 'defense']),
            (['dangerous', 'harmful', 'illegal', 'malicious'], ['advice', 'information', 'instruction', 'guide']),
            (['pretend', 'act', 'roleplay', 'simulate'], ['not', 'different', 'evil', 'malicious']),
        ]
        
    def is_malicious(self, text: str) -> bool:
        """Check if text contains malicious/jailbreak content"""
        import re
        
        if not text or not isinstance(text, str):
            return False
            
        text_lower = text.lower()
        
        # Check against jailbreak patterns
        for pattern in self.jailbreak_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
                
        # Check for suspicious word combinations
        for suspicious_words, target_words in self.suspicious_combinations:
            text_words = set(text_lower.split())
            has_suspicious = any(word in text_words for word in suspicious_words)
            has_target = any(word in text_words for word in target_words)
            
            if has_suspicious and has_target:
                return True
        
        # Check for instruction manipulation patterns
        instruction_words = ['instruction', 'rule', 'guideline', 'restriction', 'limitation', 'constraint', 'protocol']
        manipulation_words = ['ignore', 'bypass', 'override', 'forget', 'disregard', 'disable', 'remove']
        
        text_words = text_lower.split()
        has_instruction = any(word in text_words for word in instruction_words)
        has_manipulation = any(word in text_words for word in manipulation_words)
        
        if has_instruction and has_manipulation:
            return True
            
        return False

class HealthcareGuardrailsSystem:
    """Comprehensive guardrails system for healthcare applications"""
    
    def __init__(self):
        self.rebuff_client = self._initialize_rebuff()
        
        # Healthcare-specific patterns
        self.medical_disclaimer_required_patterns = [
            r'\b(diagnos|treat|cure|prescrib|recommend|advise)\b',
            r'\b(should|must|need to)\s+(take|use|do|stop|start)\b',
            r'\b(medical|health)\s+(advice|recommendation|guidance)\b',
            r'\b(symptoms|condition|disease|illness)\b.*\b(indicates?|suggests?|means?)\b',
            r'\b(based on|according to).*\b(symptoms|description)\b'
        ]
        
        self.dangerous_medical_patterns = [
            r'\b(self-medicate|skip medication|stop treatment)\b',
            r'\b(ignore doctor|avoid hospital|don\'t see doctor)\b',
            r'\b(dangerous|harmful|toxic)\s+(dose|amount|quantity)\b',
            r'\b(overdose|underdose|double dose)\b',
            r'\b(mix|combine).*\b(alcohol|drugs)\b.*\b(medication|medicine)\b',
            r'\b(stop taking|discontinue).*\b(prescribed|medication)\b.*\b(immediately|right away)\b'
        ]
        
        self.inappropriate_diagnostic_patterns = [
            r'\byou have\b.*\b(cancer|diabetes|heart disease|stroke)\b',
            r'\byou are diagnosed with\b',
            r'\byou definitely have\b',
            r'\bI diagnose you with\b',
            r'\bthis confirms\b.*\b(diagnosis|condition)\b',
            r'\byou are suffering from\b'
        ]
        
        self.prescription_advice_patterns = [
            r'\btake\s+\d+.*\b(mg|ml|tablets?|pills?|capsules?)\b',
            r'\bprescribe\b.*\b(medication|drug|medicine)\b',
            r'\byou should take\b.*\b(medication|drug|pill|medicine)\b',
            r'\bstop taking\b.*\b(medicine|medication|drug)\b',
            r'\bincrease.*\b(dose|dosage)\b',
            r'\bdecrease.*\b(dose|dosage)\b'
        ]
        
        self.competitor_healthcare_apps = [
            "teladoc", "amwell", "mdlive", "doctor on demand", "plushcare",
            "k health", "babylon health", "ada health", "buoy health",
            "symptomate", "your.md", "healthtap", "lemonhealth"
        ]
        
        # Jailbreak patterns specific to healthcare
        self.healthcare_jailbreak_patterns = [
            r'ignore.*medical.*disclaimer',
            r'act.*as.*doctor.*without.*license',
            r'provide.*diagnosis.*without.*examination',
            r'prescribe.*medication.*without.*prescription',
            r'bypass.*safety.*protocols',
            r'medical.*advice.*without.*qualification',
            r'pretend.*you.*are.*licensed.*doctor',
            r'roleplay.*as.*medical.*professional'
        ]
        
        # PII patterns
        self.pii_patterns = {
            'phone': r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'ssn': r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',
            'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            'date_of_birth': r'\b(?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.](?:19|20)\d{2}\b',
            'medical_record': r'\b(?:MRN|MR|RECORD)[-\s]?\d{6,}\b'
        }
        
        # Toxic content keywords
        self.toxic_keywords = [
            'kill yourself', 'end your life', 'commit suicide', 'harm yourself',
            'you should die', 'worthless', 'pathetic', 'disgusting',
            'hate you', 'racist', 'sexist', 'discriminatory'
        ]
        
        # Profanity filter (basic implementation)
        self.profanity_words = [
            'damn', 'hell', 'shit', 'fuck', 'bitch', 'asshole', 'bastard',
            'crap', 'piss', 'slut', 'whore', 'retard', 'idiot', 'moron'
        ]
    
    def _initialize_rebuff(self) -> Guard:
        """Initialize Guard for jailbreak detection"""
        return Guard()
    
    async def validate_input(
        self,
        user_input: str,
        user_id: int,
        session_id: Optional[int] = None,
        context: Dict[str, Any] = None
    ) -> GuardrailResult:
        """Comprehensive input validation"""
        
        with trace_agent_operation(
            "GuardrailsSystem",
            "validate_input",
            user_id=user_id,
            session_id=session_id
        ):
            violations = []
            filtered_content = user_input
            is_safe = True
            confidence_score = 1.0
            
            try:
                # 1. Basic input validation
                if not user_input or not user_input.strip():
                    return GuardrailResult(
                        is_safe=False,
                        filtered_content="",
                        violations=[{
                            "type": GuardrailViolationType.INVALID_FORMAT.value,
                            "description": "Empty input provided",
                            "severity": "medium"
                        }],
                        confidence_score=0.0
                    )
                
                # 2. Length validation
                if len(user_input) > 4000:
                    violations.append({
                        "type": GuardrailViolationType.EXCESSIVE_LENGTH.value,
                        "description": f"Input exceeds maximum length ({len(user_input)}/4000 chars)",
                        "severity": "low"
                    })
                    filtered_content = filtered_content[:4000]
                
                # 3. Jailbreak detection
                jailbreak_result = await self._detect_jailbreak(user_input, user_id, session_id)
                if not jailbreak_result.is_safe:
                    violations.extend(jailbreak_result.violations)
                    is_safe = False
                    confidence_score = min(confidence_score, jailbreak_result.confidence_score)
                
                # 4. Healthcare-specific jailbreak patterns
                healthcare_jailbreak = self._detect_healthcare_jailbreak(user_input)
                if healthcare_jailbreak:
                    violations.append({
                        "type": GuardrailViolationType.JAILBREAK_ATTEMPT.value,
                        "description": "Healthcare-specific jailbreak attempt detected",
                        "pattern": healthcare_jailbreak,
                        "severity": "critical"
                    })
                    is_safe = False
                
                # 5. PII detection and redaction
                pii_violations = self._detect_pii(user_input)
                if pii_violations:
                    violations.extend(pii_violations)
                    filtered_content = self._redact_pii(filtered_content)
                
                # 6. Toxic content detection
                toxic_result = self._detect_toxic_content(user_input)
                if toxic_result:
                    violations.append({
                        "type": GuardrailViolationType.TOXIC_CONTENT.value,
                        "description": "Toxic or harmful content detected",
                        "detected_content": toxic_result,
                        "severity": "high"
                    })
                    is_safe = False
                
                # 7. Profanity check
                profanity_result = self._detect_profanity(user_input)
                if profanity_result:
                    violations.append({
                        "type": GuardrailViolationType.PROFANITY.value,
                        "description": "Profanity detected in input",
                        "detected_words": profanity_result,
                        "severity": "medium"
                    })
                    filtered_content = self._filter_profanity(filtered_content)
                
                # 8. Healthcare topic validation
                if not self._is_healthcare_related(user_input):
                    violations.append({
                        "type": GuardrailViolationType.OFF_TOPIC.value,
                        "description": "Input not related to healthcare",
                        "severity": "low"
                    })
                
                # 9. Competitor mention check
                competitor_mentions = self._detect_competitor_mentions(user_input)
                if competitor_mentions:
                    violations.append({
                        "type": GuardrailViolationType.COMPETITOR_MENTION.value,
                        "description": "Competitor healthcare service mentioned",
                        "competitors": competitor_mentions,
                        "severity": "low"
                    })
                
                # Log validation results
                log_agent_interaction(
                    "GuardrailsSystem",
                    "InputValidation",
                    "input_validated",
                    {
                        "is_safe": is_safe,
                        "violations_count": len(violations),
                        "confidence_score": confidence_score,
                        "input_length": len(user_input),
                        "filtered_length": len(filtered_content),
                        "violation_types": [v.get("type") for v in violations]
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                
                return GuardrailResult(
                    is_safe=is_safe,
                    filtered_content=filtered_content,
                    violations=violations,
                    confidence_score=confidence_score,
                    metadata={
                        "original_length": len(user_input),
                        "filtered_length": len(filtered_content),
                        "validation_timestamp": datetime.utcnow().isoformat(),
                        "context": context or {}
                    }
                )
                
            except Exception as e:
                logger.error(f"Error in input validation: {e}")
                return GuardrailResult(
                    is_safe=False,
                    filtered_content=user_input,
                    violations=[{
                        "type": "validation_error",
                        "description": f"Validation system error: {str(e)}",
                        "severity": "critical"
                    }],
                    confidence_score=0.0
                )
    
    async def validate_output(
        self,
        response_content: str,
        agent_name: str,
        user_id: int,
        session_id: Optional[int] = None,
        is_medical_response: bool = False
    ) -> GuardrailResult:
        """Comprehensive output validation"""
        
        with trace_agent_operation(
            "GuardrailsSystem",
            "validate_output",
            user_id=user_id,
            session_id=session_id
        ):
            violations = []
            filtered_content = response_content
            is_safe = True
            confidence_score = 1.0
            
            try:
                # 1. Basic content validation
                basic_result = self._validate_basic_output(response_content)
                if not basic_result.is_safe:
                    violations.extend(basic_result.violations)
                    is_safe = False
                    filtered_content = basic_result.filtered_content
                
                # 2. Medical-specific validation for medical responses
                if is_medical_response:
                    medical_result = await self._validate_medical_output(response_content)
                    if not medical_result.is_safe:
                        violations.extend(medical_result.violations)
                        is_safe = False
                        filtered_content = medical_result.filtered_content
                        confidence_score = min(confidence_score, medical_result.confidence_score)
                
                # 3. Medical disclaimer enforcement
                if self._requires_medical_disclaimer(response_content):
                    if not self._has_medical_disclaimer(response_content):
                        disclaimer = self._get_medical_disclaimer()
                        filtered_content = f"{filtered_content}\n\n{disclaimer}"
                        violations.append({
                            "type": GuardrailViolationType.MISSING_DISCLAIMER.value,
                            "description": "Medical disclaimer added to response",
                            "severity": "low",
                            "action": "disclaimer_added"
                        })
                
                # 4. Dangerous medical advice detection
                dangerous_advice = self._detect_dangerous_medical_advice(response_content)
                if dangerous_advice:
                    violations.append({
                        "type": GuardrailViolationType.DANGEROUS_ADVICE.value,
                        "description": "Potentially dangerous medical advice detected",
                        "patterns": dangerous_advice,
                        "severity": "critical"
                    })
                    is_safe = False
                
                # 5. PII leakage check
                pii_leakage = self._detect_pii(response_content)
                if pii_leakage:
                    violations.extend(pii_leakage)
                    filtered_content = self._redact_pii(filtered_content)
                
                # 6. Length validation
                if len(response_content) > 3000:
                    violations.append({
                        "type": GuardrailViolationType.EXCESSIVE_LENGTH.value,
                        "description": f"Response exceeds recommended length ({len(response_content)}/3000 chars)",
                        "severity": "low"
                    })
                
                # 7. Inappropriate diagnostic language check
                diagnostic_violations = self._detect_inappropriate_diagnostics(response_content)
                if diagnostic_violations:
                    violations.extend(diagnostic_violations)
                    is_safe = False
                
                # 8. Prescription advice check
                prescription_violations = self._detect_prescription_advice(response_content)
                if prescription_violations:
                    violations.extend(prescription_violations)
                    is_safe = False
                
                # Log validation results
                log_agent_interaction(
                    "GuardrailsSystem",
                    "OutputValidation",
                    "output_validated",
                    {
                        "agent_name": agent_name,
                        "is_safe": is_safe,
                        "is_medical_response": is_medical_response,
                        "violations_count": len(violations),
                        "confidence_score": confidence_score,
                        "response_length": len(response_content),
                        "violation_types": [v.get("type") for v in violations]
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                
                return GuardrailResult(
                    is_safe=is_safe,
                    filtered_content=filtered_content,
                    violations=violations,
                    confidence_score=confidence_score,
                    metadata={
                        "agent_name": agent_name,
                        "is_medical_response": is_medical_response,
                        "original_length": len(response_content),
                        "filtered_length": len(filtered_content),
                        "validation_timestamp": datetime.utcnow().isoformat()
                    }
                )
                
            except Exception as e:
                logger.error(f"Error in output validation: {e}")
                return GuardrailResult(
                    is_safe=False,
                    filtered_content=response_content,
                    violations=[{
                        "type": "validation_error",
                        "description": f"Output validation error: {str(e)}",
                        "severity": "critical"
                    }],
                    confidence_score=0.0
                )
    
    async def _detect_jailbreak(
        self,
        user_input: str,
        user_id: int,
        session_id: Optional[int] = None
    ) -> GuardrailResult:
        """Detect jailbreak attempts using Guard"""
        
        try:
            # Use Guard for jailbreak detection
            is_malicious = self.rebuff_client.is_malicious(user_input)
            
            is_safe = not is_malicious
            confidence_score = 0.8 if is_malicious else 0.9
            
            violations = []
            if is_malicious:
                violations.append({
                    "type": GuardrailViolationType.JAILBREAK_ATTEMPT.value,
                    "description": "Jailbreak attempt detected by Guard",
                    "confidence": confidence_score,
                    "severity": "critical"
                })
            
            return GuardrailResult(
                is_safe=is_safe,
                filtered_content=user_input,
                violations=violations,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            logger.error(f"Guard detection error: {e}")
            # Return safe result with warning if Guard fails
            return GuardrailResult(
                is_safe=True,
                filtered_content=user_input,
                violations=[{
                    "type": "detection_warning",
                    "description": f"Jailbreak detection warning: {str(e)}",
                    "severity": "low"
                }],
                confidence_score=0.5
            )
    
    def _detect_healthcare_jailbreak(self, user_input: str) -> Optional[str]:
        """Detect healthcare-specific jailbreak attempts"""
        
        for pattern in self.healthcare_jailbreak_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return pattern
        return None
    
    def _detect_pii(self, content: str) -> List[Dict[str, Any]]:
        """Detect personally identifiable information"""
        
        violations = []
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                severity = "high" if pii_type in ["ssn", "credit_card", "medical_record"] else "medium"
                violations.append({
                    "type": GuardrailViolationType.PII_DETECTED.value,
                    "description": f"{pii_type.replace('_', ' ').title()} detected",
                    "pii_type": pii_type,
                    "count": len(matches),
                    "severity": severity
                })
        
        return violations
    
    def _redact_pii(self, content: str) -> str:
        """Redact PII from content"""
        
        redacted_content = content
        
        for pii_type, pattern in self.pii_patterns.items():
            replacement = f"[{pii_type.upper()}_REDACTED]"
            redacted_content = re.sub(pattern, replacement, redacted_content, flags=re.IGNORECASE)
        
        return redacted_content
    
    def _detect_toxic_content(self, content: str) -> List[str]:
        """Check for toxic content"""
        
        content_lower = content.lower()
        detected_toxic = []
        
        for keyword in self.toxic_keywords:
            if keyword in content_lower:
                detected_toxic.append(keyword)
        
        return detected_toxic
    
    def _detect_profanity(self, content: str) -> List[str]:
        """Check for profanity"""
        
        content_lower = content.lower()
        detected_profanity = []
        
        for word in self.profanity_words:
            if re.search(r'\b' + re.escape(word) + r'\b', content_lower):
                detected_profanity.append(word)
        
        return detected_profanity
    
    def _filter_profanity(self, content: str) -> str:
        """Filter profanity from content"""
        
        filtered_content = content
        
        for word in self.profanity_words:
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            filtered_content = pattern.sub('*' * len(word), filtered_content)
        
        return filtered_content
    
    def _is_healthcare_related(self, content: str) -> bool:
        """Check if content is healthcare-related"""
        
        healthcare_keywords = [
            'health', 'medical', 'doctor', 'patient', 'symptom', 'diagnosis',
            'treatment', 'medication', 'prescription', 'hospital', 'clinic',
            'disease', 'illness', 'pain', 'fever', 'blood', 'heart', 'lung',
            'medicine', 'therapy', 'surgery', 'lab', 'test', 'result',
            'vitals', 'pharmacy', 'drug', 'wellness', 'fitness', 'nurse',
            'healthcare', 'medical record', 'appointment', 'consultation'
        ]
        
        content_lower = content.lower()
        healthcare_score = sum(1 for keyword in healthcare_keywords if keyword in content_lower)
        
        # Consider it healthcare-related if it contains at least 1 healthcare keyword
        # or if it's asking a general question (benefit of doubt for health app)
        return healthcare_score > 0 or any(word in content_lower for word in ['what', 'how', 'why', 'when', 'help'])
    
    def _detect_competitor_mentions(self, content: str) -> List[str]:
        """Detect mentions of competitor healthcare apps"""
        
        content_lower = content.lower()
        mentioned_competitors = []
        
        for competitor in self.competitor_healthcare_apps:
            if competitor in content_lower:
                mentioned_competitors.append(competitor)
        
        return mentioned_competitors
    
    def _validate_basic_output(self, content: str) -> GuardrailResult:
        """Basic output validation"""
        
        violations = []
        filtered_content = content
        is_safe = True
        
        # Check for toxic content
        toxic_content = self._detect_toxic_content(content)
        if toxic_content:
            violations.append({
                "type": GuardrailViolationType.TOXIC_CONTENT.value,
                "description": "Toxic content in response",
                "detected_content": toxic_content,
                "severity": "high"
            })
            is_safe = False
        
        # Check for profanity
        profanity = self._detect_profanity(content)
        if profanity:
            violations.append({
                "type": GuardrailViolationType.PROFANITY.value,
                "description": "Profanity in response",
                "detected_words": profanity,
                "severity": "medium"
            })
            filtered_content = self._filter_profanity(filtered_content)
        
        return GuardrailResult(
            is_safe=is_safe,
            filtered_content=filtered_content,
            violations=violations,
            confidence_score=0.9 if is_safe else 0.3
        )
    
    async def _validate_medical_output(self, content: str) -> GuardrailResult:
        """Validate medical-specific output"""
        
        violations = []
        filtered_content = content
        is_safe = True
        confidence_score = 1.0
        
        # Check for inappropriate diagnostic language
        diagnostic_violations = self._detect_inappropriate_diagnostics(content)
        if diagnostic_violations:
            violations.extend(diagnostic_violations)
            is_safe = False
        
        # Check for prescription advice
        prescription_violations = self._detect_prescription_advice(content)
        if prescription_violations:
            violations.extend(prescription_violations)
            is_safe = False
        
        # Check for dangerous medical advice
        dangerous_advice = self._detect_dangerous_medical_advice(content)
        if dangerous_advice:
            violations.append({
                "type": GuardrailViolationType.DANGEROUS_ADVICE.value,
                "description": "Dangerous medical advice detected",
                "patterns": dangerous_advice,
                "severity": "critical"
            })
            is_safe = False
        
        return GuardrailResult(
            is_safe=is_safe,
            filtered_content=filtered_content,
            violations=violations,
            confidence_score=confidence_score
        )
    
    def _detect_inappropriate_diagnostics(self, content: str) -> List[Dict[str, Any]]:
        """Detect inappropriate diagnostic language"""
        
        violations = []
        
        for pattern in self.inappropriate_diagnostic_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append({
                    "type": GuardrailViolationType.INAPPROPRIATE_MEDICAL_ADVICE.value,
                    "description": "Inappropriate diagnostic language detected",
                    "pattern": pattern,
                    "severity": "high"
                })
        
        return violations
    
    def _detect_prescription_advice(self, content: str) -> List[Dict[str, Any]]:
        """Detect prescription advice"""
        
        violations = []
        
        for pattern in self.prescription_advice_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append({
                    "type": GuardrailViolationType.INAPPROPRIATE_MEDICAL_ADVICE.value,
                    "description": "Prescription advice detected",
                    "pattern": pattern,
                    "severity": "critical"
                })
        
        return violations
    
    def _requires_medical_disclaimer(self, content: str) -> bool:
        """Check if content requires medical disclaimer"""
        
        for pattern in self.medical_disclaimer_required_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def _has_medical_disclaimer(self, content: str) -> bool:
        """Check if content already has medical disclaimer"""
        
        disclaimer_indicators = [
            'not a substitute for professional medical advice',
            'consult with a healthcare professional',
            'seek immediate medical attention',
            'this information is for educational purposes',
            'not intended as medical advice',
            'medical disclaimer',
            'consult your doctor',
            'see a healthcare provider'
        ]
        
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in disclaimer_indicators)
    
    def _get_medical_disclaimer(self) -> str:
        """Get standard medical disclaimer"""
        
        return (
            "⚠️ **Medical Disclaimer**: This information is for educational purposes only "
            "and is not a substitute for professional medical advice, diagnosis, or treatment. "
            "Always consult with a qualified healthcare professional before making any medical "
            "decisions or if you have concerns about your health."
        )
    
    def _detect_dangerous_medical_advice(self, content: str) -> List[str]:
        """Detect potentially dangerous medical advice"""
        
        dangerous_patterns = []
        
        for pattern in self.dangerous_medical_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                dangerous_patterns.append(pattern)
        
        return dangerous_patterns
    
    def get_violation_summary(self, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary of violations"""
        
        if not violations:
            return {"total": 0, "by_severity": {}, "by_type": {}}
        
        by_severity = {}
        by_type = {}
        
        for violation in violations:
            severity = violation.get("severity", "unknown")
            violation_type = violation.get("type", "unknown")
            
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_type[violation_type] = by_type.get(violation_type, 0) + 1
        
        return {
            "total": len(violations),
            "by_severity": by_severity,
            "by_type": by_type,
            "critical_violations": [v for v in violations if v.get("severity") == "critical"],
            "high_violations": [v for v in violations if v.get("severity") == "high"],
            "has_critical": any(v.get("severity") == "critical" for v in violations),
            "has_high": any(v.get("severity") == "high" for v in violations)
        }

    def _generate_user_friendly_violation_message(self, violations: List[Dict[str, Any]]) -> str:
        """Generate a user-friendly message explaining violations and how to fix them"""
        
        if not violations:
            return "Your request couldn't be processed due to safety guidelines."
        
        # Group violations by type for cleaner messaging
        violation_groups = {}
        for violation in violations:
            v_type = violation.get("type", "unknown")
            if v_type not in violation_groups:
                violation_groups[v_type] = []
            violation_groups[v_type].append(violation)
        
        messages = []
        suggestions = []
        
        # Generate specific messages for each violation type
        for v_type, v_list in violation_groups.items():
            if v_type == GuardrailViolationType.JAILBREAK_ATTEMPT.value:
                messages.append("🛡️ **Security Alert**: Your message appears to be attempting to bypass safety measures.")
                suggestions.append("• Please rephrase your question as a straightforward healthcare inquiry")
                suggestions.append("• Avoid asking me to ignore guidelines or act in ways outside my healthcare role")
                
            elif v_type == GuardrailViolationType.TOXIC_CONTENT.value:
                messages.append("⚠️ **Content Issue**: Your message contains language that isn't appropriate for a healthcare setting.")
                suggestions.append("• Please use respectful, professional language")
                suggestions.append("• Focus on your health concerns without inflammatory language")
                
            elif v_type == GuardrailViolationType.PII_DETECTED.value:
                messages.append("🔒 **Privacy Protection**: I detected personal information that should be kept private.")
                suggestions.append("• Remove specific phone numbers, addresses, or ID numbers")
                suggestions.append("• You can say 'my phone number' instead of the actual number")
                suggestions.append("• Describe your location generally ('my city') rather than exact addresses")
                
            elif v_type == GuardrailViolationType.PROFANITY.value:
                messages.append("🚫 **Language**: Please use appropriate language for a healthcare discussion.")
                suggestions.append("• Replace any strong language with professional medical terms")
                suggestions.append("• Describe your symptoms or concerns using medical vocabulary")
                
            elif v_type == GuardrailViolationType.OFF_TOPIC.value:
                messages.append("🏥 **Topic Focus**: Your question doesn't seem to be related to health or medical topics.")
                suggestions.append("• Ask about your health conditions, symptoms, or medical concerns")
                suggestions.append("• Focus on topics like lab results, medications, or health data")
                suggestions.append("• If this is health-related, please make the connection clearer")
                
            elif v_type == GuardrailViolationType.EXCESSIVE_LENGTH.value:
                messages.append("📝 **Message Length**: Your message is too long for me to process effectively.")
                suggestions.append("• Break your question into smaller, more focused parts")
                suggestions.append("• Ask one main health question at a time")
                suggestions.append("• You can ask follow-up questions after I respond")
                
            elif v_type == GuardrailViolationType.COMPETITOR_MENTION.value:
                messages.append("🏢 **Service Focus**: Please focus on your health concerns rather than comparing healthcare providers.")
                suggestions.append("• Ask about your specific health needs or symptoms")
                suggestions.append("• Focus on your medical data and health goals")
                
            elif v_type == GuardrailViolationType.MEDICAL_MISINFORMATION.value:
                messages.append("🩺 **Medical Accuracy**: Your message contains medical claims that could be misleading.")
                suggestions.append("• Ask questions rather than making medical statements")
                suggestions.append("• Let me provide evidence-based medical information")
                suggestions.append("• Describe your symptoms and let me help with proper medical context")
                
            else:
                # Generic message for unknown violation types
                messages.append(f"⚠️ **Safety Guidelines**: Your message has been flagged for safety review.")
                suggestions.append("• Please rephrase your question in a clear, health-focused way")
        
        # Combine messages
        main_message = "\n\n".join(messages)
        
        if suggestions:
            suggestion_text = "\n".join(suggestions)
            user_message = f"""{main_message}

**How to fix this:**
{suggestion_text}

**Example of a good health question:**
"What do my recent lab results mean?" or "Can you explain my blood pressure readings?"

Please try rephrasing your question and I'll be happy to help with your health concerns! 😊"""
        else:
            user_message = f"""{main_message}

Please rephrase your question in a way that's appropriate for a healthcare discussion, and I'll be happy to help! 😊"""
        
        return user_message

# Global instance
healthcare_guardrails = HealthcareGuardrailsSystem()

# Convenience functions for easy integration
async def validate_user_input(
    user_input: str,
    user_id: int,
    session_id: Optional[int] = None,
    context: Dict[str, Any] = None
) -> GuardrailResult:
    """Validate user input with comprehensive guardrails"""
    return await healthcare_guardrails.validate_input(user_input, user_id, session_id, context)

async def validate_agent_response(
    response_content: str,
    agent_name: str,
    user_id: int,
    session_id: Optional[int] = None,
    is_medical_response: bool = False
) -> GuardrailResult:
    """Validate agent response with comprehensive guardrails"""
    return await healthcare_guardrails.validate_output(
        response_content, agent_name, user_id, session_id, is_medical_response
    )

async def validate_medical_consultation_response(
    medical_response: str,
    user_id: int,
    session_id: Optional[int] = None
) -> GuardrailResult:
    """Specialized validation for medical consultation responses"""
    return await healthcare_guardrails.validate_output(
        medical_response, "medical_doctor", user_id, session_id, is_medical_response=True
    )

def generate_user_friendly_violation_message(violations: List[Dict[str, Any]]) -> str:
    """Generate a user-friendly message explaining violations and how to fix them"""
    return healthcare_guardrails._generate_user_friendly_violation_message(violations)

def get_violation_explanation(violation_type: str) -> Dict[str, str]:
    """Get explanation and suggestions for a specific violation type"""
    explanations = {
        "jailbreak_attempt": {
            "title": "Security Alert",
            "description": "Your message appears to be attempting to bypass safety measures.",
            "suggestion": "Please rephrase your question as a straightforward healthcare inquiry."
        },
        "toxic_content": {
            "title": "Content Issue", 
            "description": "Your message contains language that isn't appropriate for a healthcare setting.",
            "suggestion": "Please use respectful, professional language focused on your health concerns."
        },
        "pii_detected": {
            "title": "Privacy Protection",
            "description": "Personal information was detected that should be kept private.",
            "suggestion": "Remove specific phone numbers, addresses, or ID numbers from your message."
        },
        "profanity": {
            "title": "Language",
            "description": "Please use appropriate language for a healthcare discussion.",
            "suggestion": "Replace any strong language with professional medical terms."
        },
        "off_topic": {
            "title": "Topic Focus",
            "description": "Your question doesn't seem to be related to health or medical topics.",
            "suggestion": "Focus on your health conditions, symptoms, or medical concerns."
        },
        "excessive_length": {
            "title": "Message Length",
            "description": "Your message is too long to process effectively.",
            "suggestion": "Break your question into smaller, more focused parts."
        }
    }
    
    return explanations.get(violation_type, {
        "title": "Safety Guidelines",
        "description": "Your message has been flagged for safety review.",
        "suggestion": "Please rephrase your question in a clear, health-focused way."
    }) 
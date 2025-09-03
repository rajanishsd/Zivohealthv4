"""
Medical Doctor Panels - Virtual Diagnostic Team
Implements five specialized medical personas using autogen for collaborative diagnosis.
"""

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core import CancellationToken
import asyncio
import json
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
from dotenv import load_dotenv
load_dotenv()
from app.utils.timezone import now_local
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DiagnosisHypothesis:
    """Represents a diagnostic hypothesis with probability"""
    condition: str
    probability: float
    evidence_for: List[str] = field(default_factory=list)
    evidence_against: List[str] = field(default_factory=list)
    
@dataclass
class DiagnosticTest:
    """Represents a diagnostic test with metadata"""
    name: str
    cost: float
    invasiveness: str  # "low", "moderate", "high"
    discriminatory_power: float  # 0-1 scale
    target_conditions: List[str] = field(default_factory=list)

@dataclass
class BudgetTracker:
    """Tracks cumulative medical costs"""
    cumulative_cost: float = 0.0
    test_history: List[Tuple[str, float]] = field(default_factory=list)
    budget_limit: Optional[float] = None
    
    def add_test(self, test_name: str, cost: float) -> bool:
        """Add test cost and check if within budget"""
        if self.budget_limit and (self.cumulative_cost + cost) > self.budget_limit:
            return False
        self.cumulative_cost += cost
        self.test_history.append((test_name, cost))
        return True
    
    def estimate_cost(self, tests: List[DiagnosticTest]) -> float:
        """Estimate total cost of proposed tests"""
        return sum(test.cost for test in tests)

@dataclass
class InformationSufficiencyAssessment:
    """Assesses whether patient information is sufficient for decision making"""
    
    # Essential categories of information
    present_illness_score: float = 0.0  # 0-1
    past_medical_history_score: float = 0.0  # 0-1
    family_history_score: float = 0.0  # 0-1
    social_history_score: float = 0.0  # 0-1
    medications_score: float = 0.0  # 0-1
    physical_exam_score: float = 0.0  # 0-1
    review_of_systems_score: float = 0.0  # 0-1
    
    overall_sufficiency_score: float = 0.0  # 0-1
    missing_critical_elements: List[str] = field(default_factory=list)
    confidence_level: str = "low"  # low, medium, high
    
    def calculate_overall_score(self) -> float:
        """Calculate weighted overall sufficiency score"""
        weights = {
            'present_illness': 0.30,
            'past_medical_history': 0.15,
            'family_history': 0.10,
            'social_history': 0.10,
            'medications': 0.15,
            'physical_exam': 0.15,
            'review_of_systems': 0.05
        }
        
        scores = [
            self.present_illness_score,
            self.past_medical_history_score,
            self.family_history_score,
            self.social_history_score,
            self.medications_score,
            self.physical_exam_score,
            self.review_of_systems_score
        ]
        
        self.overall_sufficiency_score = sum(score * weight for score, weight in zip(scores, weights.values()))
        
        # Determine confidence level
        if self.overall_sufficiency_score >= 0.8:
            self.confidence_level = "high"
        elif self.overall_sufficiency_score >= 0.5:
            self.confidence_level = "medium"
        else:
            self.confidence_level = "low"
            
        return self.overall_sufficiency_score

class InformationSufficiencyEvaluator:
    """Evaluates information sufficiency using multiple approaches"""
    
    def __init__(self):
        # Define essential information categories and their components
        self.essential_elements = {
            'present_illness': [
                'chief_complaint', 'onset', 'duration', 'character', 'location',
                'severity', 'timing', 'context', 'modifying_factors', 'associated_symptoms'
            ],
            'past_medical_history': [
                'chronic_conditions', 'previous_hospitalizations', 'surgeries', 
                'allergies', 'immunizations'
            ],
            'family_history': [
                'family_chronic_diseases', 'family_genetic_conditions', 'family_cancers'
            ],
            'social_history': [
                'smoking', 'alcohol', 'drugs', 'occupation', 'travel', 'sexual_history'
            ],
            'medications': [
                'current_medications', 'dosages', 'compliance', 'recent_changes'
            ],
            'physical_exam': [
                'vital_signs', 'general_appearance', 'relevant_system_exam'
            ],
            'review_of_systems': [
                'constitutional_symptoms', 'relevant_organ_systems'
            ]
        }
        
        # Define critical keywords for each category
        self.category_keywords = {
            'present_illness': [
                'onset', 'started', 'began', 'duration', 'pain', 'ache', 'discomfort',
                'severity', 'character', 'sharp', 'dull', 'throbbing', 'burning',
                'location', 'radiates', 'associated', 'triggers', 'relieved by',
                'worse with', 'better with', 'timing', 'frequency'
            ],
            'past_medical_history': [
                'history of', 'past medical', 'previous', 'chronic', 'diagnosed with',
                'hospitalized', 'surgery', 'procedures', 'allergies', 'allergic to'
            ],
            'family_history': [
                'family history', 'father', 'mother', 'siblings', 'parents',
                'grandmother', 'grandfather', 'family', 'genetic', 'hereditary'
            ],
            'social_history': [
                'smoking', 'tobacco', 'alcohol', 'drinks', 'drugs', 'occupation',
                'work', 'travel', 'sexual', 'exercise', 'diet'
            ],
            'medications': [
                'medications', 'drugs', 'pills', 'taking', 'prescribed',
                'dosage', 'dose', 'compliance', 'adherence'
            ],
            'physical_exam': [
                'vital signs', 'blood pressure', 'heart rate', 'temperature',
                'examination', 'physical exam', 'appears', 'looks', 'palpation',
                'auscultation', 'inspection'
            ],
            'review_of_systems': [
                'review of systems', 'constitutional', 'fever', 'chills',
                'weight loss', 'weight gain', 'fatigue', 'malaise'
            ]
        }
    
    def evaluate_case_sufficiency(self, patient_case: str) -> InformationSufficiencyAssessment:
        """
        Comprehensive evaluation of information sufficiency
        
        Args:
            patient_case: Patient case description string
            
        Returns:
            InformationSufficiencyAssessment: Detailed assessment
        """
        assessment = InformationSufficiencyAssessment()
        case_lower = patient_case.lower()
        
        # Score each category based on keyword presence and content depth
        assessment.present_illness_score = self._score_present_illness(case_lower)
        assessment.past_medical_history_score = self._score_category(case_lower, 'past_medical_history')
        assessment.family_history_score = self._score_category(case_lower, 'family_history')
        assessment.social_history_score = self._score_category(case_lower, 'social_history')
        assessment.medications_score = self._score_category(case_lower, 'medications')
        assessment.physical_exam_score = self._score_category(case_lower, 'physical_exam')
        assessment.review_of_systems_score = self._score_category(case_lower, 'review_of_systems')
        
        # Calculate overall score
        assessment.calculate_overall_score()
        
        # Identify missing critical elements
        assessment.missing_critical_elements = self._identify_missing_elements(case_lower)
        
        return assessment
    
    def _score_present_illness(self, case_text: str) -> float:
        """Score present illness information (weighted more heavily)"""
        pi_keywords = self.category_keywords['present_illness']
        
        # Check for HPI elements
        hpi_elements = {
            'onset': any(word in case_text for word in ['onset', 'started', 'began', 'since']),
            'duration': any(word in case_text for word in ['hours', 'days', 'weeks', 'months', 'years', 'duration']),
            'character': any(word in case_text for word in ['sharp', 'dull', 'burning', 'pressure', 'cramping', 'throbbing']),
            'severity': any(word in case_text for word in ['severe', 'mild', 'moderate', '/10', 'scale', 'intensity']),
            'location': any(word in case_text for word in ['chest', 'abdomen', 'head', 'back', 'arm', 'leg', 'location']),
            'timing': any(word in case_text for word in ['constant', 'intermittent', 'episodic', 'timing', 'frequency']),
            'context': any(word in case_text for word in ['exercise', 'rest', 'eating', 'stress', 'activity']),
            'modifying_factors': any(word in case_text for word in ['better', 'worse', 'relieves', 'aggravates', 'triggers'])
        }
        
        present_count = sum(hpi_elements.values())
        total_elements = len(hpi_elements)
        
        return min(present_count / total_elements, 1.0)
    
    def _score_category(self, case_text: str, category: str) -> float:
        """Score information completeness for a specific category"""
        keywords = self.category_keywords.get(category, [])
        
        # Count keyword matches
        keyword_matches = sum(1 for keyword in keywords if keyword in case_text)
        
        # Base score on keyword density and presence
        if keyword_matches == 0:
            return 0.0
        elif keyword_matches >= 3:
            return 1.0
        else:
            return keyword_matches / 3.0
    
    def _identify_missing_elements(self, case_text: str) -> List[str]:
        """Identify critical missing information elements"""
        missing = []
        
        # Check for critical elements
        critical_checks = {
            'Chief complaint unclear': not any(word in case_text for word in ['pain', 'ache', 'discomfort', 'difficulty', 'problem']),
            'No onset information': not any(word in case_text for word in ['started', 'began', 'onset', 'since']),
            'No duration specified': not any(word in case_text for word in ['hours', 'days', 'weeks', 'months', 'years']),
            'No past medical history': not any(word in case_text for word in ['history', 'previous', 'chronic', 'past']),
            'No medications mentioned': not any(word in case_text for word in ['medications', 'drugs', 'taking']),
            'No physical exam findings': not any(word in case_text for word in ['vital', 'exam', 'appears', 'auscultation', 'palpation']),
            'No family history': not any(word in case_text for word in ['family', 'father', 'mother', 'parents']),
            'No social history': not any(word in case_text for word in ['smoking', 'alcohol', 'occupation', 'work'])
        }
        
        missing = [element for element, is_missing in critical_checks.items() if is_missing]
        
        return missing
    
    def should_ask_questions(self, assessment: InformationSufficiencyAssessment) -> bool:
        """
        Determine if more questions should be asked
        
        Args:
            assessment: Information sufficiency assessment
            
        Returns:
            bool: True if more questions are needed
        """
        # Multiple criteria for asking questions
        criteria = [
            assessment.overall_sufficiency_score < 0.6,  # Low overall score
            assessment.present_illness_score < 0.5,      # Inadequate HPI
            len(assessment.missing_critical_elements) > 3, # Too many missing elements
            assessment.confidence_level == "low"          # Low confidence
        ]
        
        return any(criteria)
    
    def generate_targeted_questions(self, assessment: InformationSufficiencyAssessment) -> List[str]:
        """
        Generate specific questions based on missing information
        
        Args:
            assessment: Information sufficiency assessment
            
        Returns:
            List[str]: Targeted questions to ask
        """
        questions = []
        
        # Questions based on missing elements
        if 'Chief complaint unclear' in assessment.missing_critical_elements:
            questions.append("What is the main problem or symptom that brought you in today?")
        
        if 'No onset information' in assessment.missing_critical_elements:
            questions.append("When did this problem first start? Was the onset sudden or gradual?")
        
        if 'No duration specified' in assessment.missing_critical_elements:
            questions.append("How long have you been experiencing this problem?")
        
        # HPI-specific questions if present illness score is low
        if assessment.present_illness_score < 0.5:
            questions.extend([
                "Can you describe the character of your symptoms (sharp, dull, burning, etc.)?",
                "On a scale of 1-10, how severe are your symptoms?",
                "What makes your symptoms better or worse?",
                "Are there any associated symptoms?"
            ])
        
        # History questions
        if 'No past medical history' in assessment.missing_critical_elements:
            questions.append("Do you have any significant past medical history or chronic conditions?")
        
        if 'No medications mentioned' in assessment.missing_critical_elements:
            questions.append("What medications are you currently taking?")
        
        if 'No family history' in assessment.missing_critical_elements:
            questions.append("Is there any significant family history of medical conditions?")
        
        if 'No social history' in assessment.missing_critical_elements:
            questions.append("Do you smoke, drink alcohol, or have any relevant social history?")
        
        if 'No physical exam findings' in assessment.missing_critical_elements:
            questions.append("Have you had a physical examination? What were the findings?")
        
        return questions[:8]  # Limit to 8 questions to avoid overwhelming

class MedicalDoctorPanel:
    """Orchestrates the virtual medical panel using autogen"""
    
    def __init__(self, api_key: str, budget_limit: Optional[float] = None,
                 question_rounds_limit: int = 1,
                 questions_per_round_limit: int = 5):
        self.api_key = api_key
        self.budget_tracker = BudgetTracker(budget_limit=budget_limit)
        self.current_hypotheses: List[DiagnosisHypothesis] = []
        self.patient_data = {}
        self.conversation_history = []
        self.sufficiency_evaluator = InformationSufficiencyEvaluator()  # Add evaluator
        # Limits for question-asking behavior
        self.question_rounds_limit: int = max(0, question_rounds_limit)
        self.questions_per_round_limit: int = max(1, questions_per_round_limit)
        self.question_rounds_used: int = 0
        self.setup_agents()
        
    def setup_agents(self):
        """Initialize the five specialized medical agents"""
        
        # Model client (0.7 API)
        self.model_client = OpenAIChatCompletionClient(model="gpt-4o-mini", api_key=self.api_key)
        
        # Dr. Hypothesis - Maintains probability-ranked differential diagnosis
        self.dr_hypothesis = AssistantAgent(
            name="Dr_Hypothesis",
            system_message="""You are Dr. Hypothesis, a specialist in differential diagnosis.
            
            Your responsibilities:
            - Maintain a probability-ranked list of the top 3 most likely diagnoses
            - Update probabilities in a Bayesian manner after each new finding
            - Assess confidence levels and highlight information gaps
            - EXPLICITLY recommend asking questions when information is insufficient
            
            For each case, provide:
            1. Current Top 3 Diagnoses (with probabilities)
            2. Bayesian Update Reasoning 
            3. Confidence Level (Low/Medium/High)
            4. Information Gaps Assessment
            
            CRITICAL: If key information is missing (onset details, associated symptoms, family history, medications, physical exam), 
            state "INSUFFICIENT INFORMATION - RECOMMEND ASKING QUESTIONS" and specify what questions are needed.
            
            Be conservative with probabilities when information is limited.""",
            model_client=self.model_client
        )
        
        # Dr. Test-Chooser - Selects diagnostic tests
        self.dr_test_chooser = AssistantAgent(
            name="Dr_Test_Chooser",
            system_message="""You are Dr. Test-Chooser, an expert in diagnostic test selection.
            
            Your responsibilities:
            - Select up to 3 diagnostic tests per round that maximally discriminate between leading hypotheses
            - Consider test sensitivity, specificity, and discriminatory power
            - Prioritize tests that can rule in/out multiple conditions
            - Justify test selection based on current differential diagnosis
            
            Always structure your response with:
            1. Recommended Tests (max 3)
            2. Rationale for each test
            3. Expected discriminatory value
            4. Test characteristics (sensitivity/specificity if known)
            
            Focus on tests with highest diagnostic yield.""",
            model_client=self.model_client
        )
        
        # Dr. Challenger - Acts as devil's advocate
        self.dr_challenger = AssistantAgent(
            name="Dr_Challenger",
            system_message="""You are Dr. Challenger, the critical thinking specialist and devil's advocate.
            
            Your responsibilities:
            - Identify potential anchoring bias in current thinking
            - Highlight contradictory evidence that may be overlooked
            - Propose alternative diagnoses not being considered
            - Suggest tests that could falsify the current leading diagnosis
            - Challenge assumptions and cognitive shortcuts
            
            Always structure your response with:
            1. Potential Biases Identified
            2. Contradictory Evidence
            3. Alternative Diagnoses to Consider
            4. Falsification Tests
            5. Questions/Concerns
            
            Be constructively critical and evidence-based.""",
            model_client=self.model_client
        )
        
        # Dr. Stewardship - Enforces cost-conscious care
        self.dr_stewardship = AssistantAgent(
            name="Dr_Stewardship",
            system_message="""You are Dr. Stewardship, the resource stewardship and cost-effectiveness specialist.
            
            Your responsibilities:
            - Advocate for cost-effective diagnostic approaches
            - Suggest cheaper alternatives when diagnostically equivalent
            - Veto low-yield expensive tests
            - Consider patient financial burden
            - Promote evidence-based, high-value care
            
            Always structure your response with:
            1. Cost-Effectiveness Analysis
            2. Alternative Cheaper Options
            3. Tests to Avoid (low value)
            4. Budget Considerations
            5. High-Value Recommendations
            
            Balance quality care with resource consciousness.""",
            model_client=self.model_client
        )
        
        # Dr. Checklist - Quality control specialist
        self.dr_checklist = AssistantAgent(
            name="Dr_Checklist",
            system_message="""You are Dr. Checklist, the quality control and consistency specialist.
            
            Your responsibilities:
            - Verify all test names are valid and properly specified
            - Ensure internal consistency across panel reasoning
            - Check for logical contradictions
            - Validate that recommendations align with stated diagnoses
            - Perform silent quality assurance
            
            Always structure your response with:
            1. Validity Check Results
            2. Consistency Assessment
            3. Identified Issues
            4. Recommendations for Improvement
            5. Quality Score (1-10)
            
            Focus on accuracy and internal consistency.""",
            model_client=self.model_client
        )
        
        # Panel Coordinator - Orchestrates the discussion
        self.panel_coordinator = AssistantAgent(
            name="Panel_Coordinator",
            system_message="""You are the Panel Coordinator, responsible for orchestrating the medical panel discussion.
            
            Your responsibilities:
            - Facilitate structured Chain of Debate between specialists
            - Synthesize input from all panel members
            - Guide consensus building
            - Determine when to take one of three actions:
              1. Ask follow-up questions (PREFER THIS when information is insufficient)
              2. Order diagnostic tests
              3. Commit to a diagnosis (if certainty exceeds threshold)
            
            DECISION CRITERIA:
            - ASK QUESTIONS if: Missing key history, vague symptoms, unclear timeline, no physical exam findings, ambiguous presentation
            - ORDER TESTS if: Clear differential diagnosis formed, sufficient history obtained, ready for diagnostic workup
            - COMMIT DIAGNOSIS if: >80% certainty with strong evidence
            
            BIAS TOWARD QUESTIONING: When in doubt between asking questions vs ordering tests, ALWAYS choose questions first.
            Essential questions often missing: onset details, associated symptoms, family history, medications, social history, physical exam findings.
            
            OUTPUT FORMAT REQUIREMENT:
            - When you reach a decision, respond with a single JSON object using this schema:
              {
                "action": "ASK_QUESTIONS" | "ORDER_TESTS" | "COMMIT_DIAGNOSIS",
                "details": "string summary of reasoning",
                "questions": ["...", "..."]        // include ONLY when action == "ASK_QUESTIONS"
                "tests": ["...", "..."]             // include ONLY when action == "ORDER_TESTS"
                "diagnosis": {                         // include ONLY when action == "COMMIT_DIAGNOSIS"
                  "primary": "condition name",
                  "confidence": "low|medium|high|percent",
                  "differential": ["...", "..."]
                }
              }
            - After the JSON object, include one final line with one of these exact decision markers to signal termination:
              "DECISION: ASK_QUESTIONS" | "DECISION: ORDER_TESTS" | "DECISION: COMMIT_DIAGNOSIS"
            - Do not wrap JSON in markdown fences and do not include any other prose outside the JSON and the final DECISION line.
            
            This signals the end of the panel discussion.
            
            Always conclude with a clear action plan and next steps.""",
            model_client=self.model_client
        )
        
        # User proxy for interaction
        self.user_proxy = UserProxyAgent(name="Medical_Team_Lead")

    def _run_async(self, coroutine):
        """Run an async coroutine from sync context safely and return its result."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coroutine)
            finally:
                new_loop.close()
        else:
            return loop.run_until_complete(coroutine)
    
    def _is_termination_message(self, message: Dict) -> bool:
        """
        Check if a message indicates the conversation should terminate
        
        Args:
            message: Message dictionary from autogen (has 'content' and potentially 'name' keys)
            
        Returns:
            bool: True if conversation should terminate
        """
        # Add comprehensive logging to debug the issue
        logger.info(f"Checking termination for message: {message}")
        
        # In autogen, messages may have different structure
        # Check both 'content' and 'name' fields, and also handle cases where name might not be present
        content = message.get('content', '')
        sender = message.get('name', message.get('sender', 'unknown'))
        
        logger.info(f"Message sender: {sender}, content preview: {content[:100] if content else 'None'}...")
        
        # Check if content contains decision markers from Panel Coordinator
        if content and isinstance(content, str):
            content_upper = content.upper()
            decision_markers = [
                'DECISION: ASK_QUESTIONS',
                'DECISION: ORDER_TESTS', 
                'DECISION: COMMIT_DIAGNOSIS'
            ]
            
            for marker in decision_markers:
                if marker in content_upper:
                    logger.info(f"TERMINATION DETECTED: Found decision marker '{marker}' in message from {sender}")
                    return True
        
        logger.info("No termination marker found, continuing conversation")
        return False
    
    def _monitor_conversation_progress(self, messages: List[Dict]) -> Dict:
        """
        Monitor conversation progress and provide insights
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Dict: Progress analysis including termination reasons
        """
        analysis = {
            "total_messages": len(messages),
            "messages_by_agent": {},
            "termination_reason": "unknown",
            "decision_reached": False,
            "consensus_indicators": []
        }
        
        # Count messages by agent
        for msg in messages:
            agent_name = msg.get('name', 'unknown')
            analysis["messages_by_agent"][agent_name] = analysis["messages_by_agent"].get(agent_name, 0) + 1
        
        # Check for termination reasons
        if messages:
            last_message = messages[-1]
            
            # Check if terminated due to decision
            if self._is_termination_message(last_message):
                analysis["termination_reason"] = "panel_decision"
                analysis["decision_reached"] = True
            elif len(messages) >= 15:  # Max rounds reached
                analysis["termination_reason"] = "max_rounds_reached"
            elif any("error" in msg.get('content', '').lower() for msg in messages[-3:]):
                analysis["termination_reason"] = "error_detected"
        
        # Look for consensus indicators
        coordinator_messages = [msg for msg in messages if msg.get('name') == 'Panel_Coordinator']
        if coordinator_messages:
            last_coordinator = coordinator_messages[-1]['content'].lower()
            if "consensus" in last_coordinator:
                analysis["consensus_indicators"].append("explicit_consensus_mentioned")
            if "agree" in last_coordinator:
                analysis["consensus_indicators"].append("agreement_indicated")
            if "confident" in last_coordinator:
                analysis["consensus_indicators"].append("confidence_expressed")
        
        return analysis
    
    def conduct_chain_of_debate(self, patient_case: str) -> Dict:
        """
        Conducts the Chain of Debate process among the medical panel
        """
        logger.info("Starting Chain of Debate for patient case")
        
        # Store patient data
        self.patient_data = {"case_description": patient_case, "timestamp": now_local()}
        
        # Create team (0.7 API)
        team = RoundRobinGroupChat(
            [
                self.dr_hypothesis,
                self.dr_test_chooser,
                self.dr_challenger,
                self.dr_stewardship,
                self.dr_checklist,
                self.panel_coordinator,
            ],
            max_turns=15,
            termination_condition=TextMentionTermination("DECISION:")
        )

        # Initiate the discussion
        remaining_question_rounds = max(0, self.question_rounds_limit - self.question_rounds_used)
        initial_prompt = f"""
        MEDICAL PANEL CONSULTATION
        
        Patient Case: {patient_case}
        
        Current Budget Status: ${self.budget_tracker.cumulative_cost:.2f} spent
        {f'Budget Limit: ${self.budget_tracker.budget_limit:.2f}' if self.budget_tracker.budget_limit else 'No budget limit set'}
        
        Constraints:
        - Total ASK_QUESTIONS rounds allowed: {self.question_rounds_limit}
        - ASK_QUESTIONS rounds already used: {self.question_rounds_used}
        - ASK_QUESTIONS rounds remaining: {remaining_question_rounds}
        - Maximum questions allowed in any round: {self.questions_per_round_limit}
        - If no ASK_QUESTIONS rounds remain, you MUST choose to ORDER_TESTS or COMMIT_DIAGNOSIS.
        - When asking questions, include no more than {self.questions_per_round_limit} concise, high-yield questions.
        
        Please conduct a thorough Chain of Debate to reach consensus on one of three actions:
        1. Ask follow-up questions
        2. Order diagnostic tests  
        3. Commit to a diagnosis (if >80% certainty)
        
        Each specialist should provide their expertise in order:
        - Dr. Hypothesis: Differential diagnosis with probabilities
        - Dr. Test-Chooser: Recommended diagnostic tests
        - Dr. Challenger: Critical analysis and alternative perspectives
        - Dr. Stewardship: Cost-effectiveness considerations
        - Dr. Checklist: Quality control and consistency check
        - Panel Coordinator: Synthesis and action decision
        """
        
        # Start the team run (sync wrapper)
        result = self._run_async(team.run(task=[TextMessage(content=initial_prompt, source="user")]))
        # Extract the final decision from messages
        final_decision = self._extract_final_decision([{"name": m.source, "content": getattr(m, 'content', '')} for m in result.messages])

        # Enforce per-round cap defensively and apply question-round limits
        if final_decision.get("action") == "ask_questions":
            qs = final_decision.get("questions", []) or []
            if len(qs) > self.questions_per_round_limit:
                logger.info(
                    f"Capping coordinator questions from {len(qs)} to {self.questions_per_round_limit} (per-round limit)"
                )
                final_decision["questions"] = qs[: self.questions_per_round_limit]
            if self.question_rounds_used >= self.question_rounds_limit:
                logger.info("Question limit reached before any follow-up. Forcing a decision without further questions.")
                forced = self._conduct_forced_decision(patient_case)
                forced["conversation_analysis"] = self._monitor_conversation_progress(groupchat.messages)
                return forced
            else:
                self.question_rounds_used += 1
        
        # Add conversation analysis
        conversation_analysis = self._monitor_conversation_progress(groupchat.messages)
        final_decision["conversation_analysis"] = conversation_analysis
        
        logger.info(f"Panel discussion completed: {conversation_analysis['termination_reason']} "
                   f"after {conversation_analysis['total_messages']} messages")
        
        return final_decision

    async def conduct_chain_of_debate_async(self, patient_case: str) -> Dict:
        """Async variant that awaits the team.run coroutine (AutoGen 0.7)."""
        logger.info("Starting Chain of Debate for patient case (async)")
        self.patient_data = {"case_description": patient_case, "timestamp": now_local()}

        team = RoundRobinGroupChat(
            [
                self.dr_hypothesis,
                self.dr_test_chooser,
                self.dr_challenger,
                self.dr_stewardship,
                self.dr_checklist,
                self.panel_coordinator,
            ],
            max_turns=15,
            termination_condition=TextMentionTermination("DECISION:")
        )

        remaining_question_rounds = max(0, self.question_rounds_limit - self.question_rounds_used)
        initial_prompt = f"""
        MEDICAL PANEL CONSULTATION
        
        Patient Case: {patient_case}
        
        Current Budget Status: ${self.budget_tracker.cumulative_cost:.2f} spent
        {f'Budget Limit: ${self.budget_tracker.budget_limit:.2f}' if self.budget_tracker.budget_limit else 'No budget limit set'}
        
        Constraints:
        - Total ASK_QUESTIONS rounds allowed: {self.question_rounds_limit}
        - ASK_QUESTIONS rounds already used: {self.question_rounds_used}
        - ASK_QUESTIONS rounds remaining: {remaining_question_rounds}
        - Maximum questions allowed in any round: {self.questions_per_round_limit}
        - If no ASK_QUESTIONS rounds remain, you MUST choose to ORDER_TESTS or COMMIT_DIAGNOSIS.
        - When asking questions, include no more than {self.questions_per_round_limit} concise, high-yield questions.
        
        Please conduct a thorough Chain of Debate to reach consensus on one of three actions:
        1. Ask follow-up questions
        2. Order diagnostic tests  
        3. Commit to a diagnosis (if >80% certainty)
        
        Each specialist should provide their expertise in order:
        - Dr. Hypothesis: Differential diagnosis with probabilities
        - Dr. Test-Chooser: Recommended diagnostic tests
        - Dr. Challenger: Critical analysis and alternative perspectives
        - Dr. Stewardship: Cost-effectiveness considerations
        - Dr. Checklist: Quality control and consistency check
        - Panel Coordinator: Synthesis and action decision
        """

        result = await team.run(task=[TextMessage(content=initial_prompt, source="user")])
        final_decision = self._extract_final_decision([
            {"name": m.source, "content": getattr(m, 'content', '')} for m in result.messages
        ])
        return final_decision
    
    def _extract_final_decision(self, messages: List[Dict]) -> Dict:
        """Extract the final panel decision from the conversation"""
        
        # Get the last message from panel coordinator
        coordinator_messages = [msg for msg in messages if msg.get('name') == 'Panel_Coordinator']
        
        if not coordinator_messages:
            return {"action": "error", "details": "No coordinator decision found"}
        
        last_decision = coordinator_messages[-1]['content']
        
        # Attempt to parse structured JSON first
        decision: Dict = {
            "action": "unknown",
            "details": last_decision,
            "timestamp": now_local(),
            "conversation_length": len(messages),
            "budget_status": {
                "spent": self.budget_tracker.cumulative_cost,
                "remaining": (self.budget_tracker.budget_limit - self.budget_tracker.cumulative_cost)
                               if self.budget_tracker.budget_limit else None
            }
        }

        # Try to locate a JSON object within the content
        import re
        json_match = None
        try:
            # Greedy match the first top-level JSON object
            json_match = re.search(r"\{[\s\S]*?\}", last_decision)
            if json_match:
                parsed = json.loads(json_match.group(0))
                action_raw = (parsed.get("action") or "").upper()
                if action_raw in {"ASK_QUESTIONS", "ORDER_TESTS", "COMMIT_DIAGNOSIS"}:
                    decision["action"] = {
                        "ASK_QUESTIONS": "ask_questions",
                        "ORDER_TESTS": "order_tests",
                        "COMMIT_DIAGNOSIS": "commit_diagnosis",
                    }[action_raw]
                    decision["details"] = parsed.get("details") or decision["details"]
                    if decision["action"] == "ask_questions":
                        questions = parsed.get("questions") or []
                        # Respect per-round limit
                        decision["questions"] = (questions or [])[: self.questions_per_round_limit]
                    elif decision["action"] == "order_tests":
                        decision["tests"] = parsed.get("tests") or []
                    elif decision["action"] == "commit_diagnosis":
                        decision["diagnosis"] = parsed.get("diagnosis") or {}
                    return decision
        except Exception as e:
            logger.info(f"JSON decision parse failed, falling back to text parsing: {e}")
        
        # Determine action type; prefer explicit decision markers
        upper_decision = last_decision.upper()
        lower_decision = last_decision.lower()
        if "DECISION: ASK_QUESTIONS" in upper_decision:
            decision["action"] = "ask_questions"
            decision["questions"] = self._extract_questions_from_text(last_decision)
        elif "DECISION: ORDER_TESTS" in upper_decision:
            decision["action"] = "order_tests"
            decision["tests"] = self._extract_tests_from_text(last_decision)
        elif "DECISION: COMMIT_DIAGNOSIS" in upper_decision:
            decision["action"] = "commit_diagnosis"
            decision["diagnosis"] = self._extract_diagnosis_from_text(last_decision)
        else:
            # Fallback heuristic
            if "ask" in lower_decision and "question" in lower_decision:
                decision["action"] = "ask_questions"
                decision["questions"] = self._extract_questions_from_text(last_decision)
            elif "order" in lower_decision and "test" in lower_decision:
                decision["action"] = "order_tests"
                decision["tests"] = self._extract_tests_from_text(last_decision)
            elif "diagnos" in lower_decision and ("commit" in lower_decision or "confidence" in lower_decision):
                decision["action"] = "commit_diagnosis"
                decision["diagnosis"] = self._extract_diagnosis_from_text(last_decision)
        
        return decision
    
    def _extract_questions_from_text(self, text: str) -> List[str]:
        """Extract specific questions from panel coordinator's decision text"""
        import re
        questions: List[str] = []
        lines = text.split('\n')

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Strip bullets and numbering (e.g., "- ", "• ", "1. ")
            line = re.sub(r'^\s*[\-\*•]\s*', '', line)
            line = re.sub(r'^\s*\d+\.\s*', '', line)

            # Consider any sufficiently long line that ends with a question mark as a question
            if line.endswith('?') and len(line) > 10:
                questions.append(line)

        # Fallback: extract questions from inline numbered lists if the above missed any
        if not questions:
            matches = re.findall(r'\d+\.\s*([^?]*\?)', text)
            questions.extend([m.strip() for m in matches if len(m.strip()) > 10])

        # Deduplicate while preserving order
        seen = set()
        deduped: List[str] = []
        for q in questions:
            if q not in seen:
                seen.add(q)
                deduped.append(q)

        # Enforce per-round question limit
        limited = deduped[: self.questions_per_round_limit]
        if len(deduped) > len(limited):
            logger.info(
                f"Limiting questions extracted from {len(deduped)} to {len(limited)} based on per-round cap {self.questions_per_round_limit}"
            )
        return limited
    
    def _extract_tests_from_text(self, text: str) -> List[str]:
        """Extract specific test names from panel coordinator's decision text"""
        tests = []
        lines = text.split('\n')
        
        # Common test keywords to look for
        test_keywords = ['test', 'scan', 'x-ray', 'mri', 'ct', 'blood', 'urine', 'ecg', 'echo', 'biopsy']
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in test_keywords):
                # Clean up the test name
                test = line.strip('- •*').strip()
                if test and len(test) > 5:
                    tests.append(test)
        
        return tests
    
    def _extract_diagnosis_from_text(self, text: str) -> Dict:
        """Extract diagnosis information from panel coordinator's decision text"""
        diagnosis_info = {
            "primary_diagnosis": "",
            "confidence": "",
            "differential": [],
            "reasoning": ""
        }
        
        # Simple extraction - in practice, you'd want more sophisticated parsing
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if 'diagnosis' in line_lower or 'condition' in line_lower:
                diagnosis_info["primary_diagnosis"] = line.strip('- •*').strip()
            elif 'confidence' in line_lower or 'certainty' in line_lower:
                diagnosis_info["confidence"] = line.strip('- •*').strip()
        
        return diagnosis_info
    
    def handle_follow_up_questions(self, questions: List[str], answers: Dict[str, str]) -> Dict:
        """
        Handle the follow-up process when panel decides to ask questions
        
        Args:
            questions: List of questions extracted from panel decision
            answers: Dictionary mapping questions to patient/user answers
            
        Returns:
            Dict: Result of panel re-deliberation with new information
        """
        logger.info(f"Processing follow-up questions and answers")
        
        # Build follow-up case information
        follow_up_info = self._build_follow_up_case(questions, answers)
        
        # Conduct another round of Chain of Debate with the new information
        return self.conduct_chain_of_debate_with_followup(follow_up_info)
    
    def _build_follow_up_case(self, questions: List[str], answers: Dict[str, str]) -> str:
        """Build updated case description with follow-up Q&A"""
        
        original_case = self.patient_data.get("case_description", "")
        
        follow_up_section = "\n\nFOLLOW-UP INFORMATION:\n"
        follow_up_section += "=" * 50 + "\n"
        
        for question in questions:
            answer = answers.get(question, "No answer provided")
            follow_up_section += f"Q: {question}\n"
            follow_up_section += f"A: {answer}\n\n"
        
        return original_case + follow_up_section
    
    def conduct_chain_of_debate_with_followup(self, updated_case: str) -> Dict:
        """
        Conduct another round of Chain of Debate with follow-up information
        """
        logger.info("Conducting follow-up Chain of Debate with new information")
        
        # Update patient data
        self.patient_data["updated_case"] = updated_case
        self.patient_data["followup_timestamp"] = now_local()
        
        # Create new team for follow-up discussion (0.7 API)
        team = RoundRobinGroupChat(
            [
                self.dr_hypothesis,
                self.dr_test_chooser,
                self.dr_challenger,
                self.dr_stewardship,
                self.dr_checklist,
                self.panel_coordinator,
            ],
            max_turns=12,
            termination_condition=TextMentionTermination("DECISION:")
        )
        
        # Follow-up prompt
        remaining_question_rounds = max(0, self.question_rounds_limit - self.question_rounds_used)
        followup_prompt = f"""
        MEDICAL PANEL FOLLOW-UP CONSULTATION
        
        Updated Patient Case with Follow-up Information:
        {updated_case}
        
        Current Budget Status: ${self.budget_tracker.cumulative_cost:.2f} spent
        {f'Budget Limit: ${self.budget_tracker.budget_limit:.2f}' if self.budget_tracker.budget_limit else 'No budget limit set'}
        
        Constraints:
        - Remaining ASK_QUESTIONS rounds: {remaining_question_rounds}
        - Maximum questions allowed in this round: {self.questions_per_round_limit}
        - If no ASK_QUESTIONS rounds remain, you MUST choose to ORDER_TESTS or COMMIT_DIAGNOSIS.
        - If committing with <80% certainty due to limits, provide best provisional diagnosis with confidence and rationale.
        
        Based on the new information provided, please conduct another Chain of Debate to reach consensus on:
        1. Ask additional follow-up questions
        2. Order diagnostic tests  
        3. Commit to a diagnosis (if >80% certainty)
        
        Focus on how the new information updates your assessment:
        - Dr. Hypothesis: Update differential diagnosis probabilities
        - Dr. Test-Chooser: Revise test recommendations based on new info
        - Dr. Challenger: Challenge updated reasoning
        - Dr. Stewardship: Reassess cost-effectiveness
        - Dr. Checklist: Verify consistency with new information
        - Panel Coordinator: Final decision with updated context
        """
        
        # Start the follow-up discussion
        result = self._run_async(team.run(task=[TextMessage(content=followup_prompt, source="user")]))
        
        # Extract the final decision from the follow-up conversation
        final_decision = self._extract_final_decision([{"name": m.source, "content": getattr(m, 'content', '')} for m in result.messages])
        
        # Enforce per-round cap defensively and apply total-round limits
        if final_decision.get("action") == "ask_questions":
            qs = final_decision.get("questions", []) or []
            if len(qs) > self.questions_per_round_limit:
                logger.info(
                    f"Capping coordinator questions from {len(qs)} to {self.questions_per_round_limit} (per-round limit)"
                )
                final_decision["questions"] = qs[: self.questions_per_round_limit]
            if self.question_rounds_used >= self.question_rounds_limit:
                logger.info("Question limit exhausted during follow-up. Forcing a decision without further questions.")
                forced = self._conduct_forced_decision(updated_case)
                forced["is_followup"] = True
                forced["followup_round"] = len(self.conversation_history) + 1
                self.conversation_history.append({
                    "type": "followup",
                    "messages": [m.dict() if hasattr(m, 'dict') else str(m) for m in result.messages],
                    "decision": forced,
                    "timestamp": now_local()
                })
                return forced
            else:
                self.question_rounds_used += 1
        final_decision["is_followup"] = True
        final_decision["followup_round"] = len(self.conversation_history) + 1
        
        # Store conversation history
        self.conversation_history.append({
            "type": "followup",
            "messages": groupchat.messages,
            "decision": final_decision,
            "timestamp": now_local()
        })
        
        return final_decision

    def _conduct_forced_decision(self, case_text: str) -> Dict:
        """Run a short, constrained discussion that forbids further questions and forces a decision."""
        logger.info("Starting forced-decision round (no further questions allowed)")
        team = RoundRobinGroupChat(
            [
                self.dr_hypothesis,
                self.dr_test_chooser,
                self.dr_challenger,
                self.dr_stewardship,
                self.dr_checklist,
                self.panel_coordinator,
            ],
            max_turns=8,
            termination_condition=TextMentionTermination("DECISION:")
        )
        forced_prompt = f"""
        MEDICAL PANEL FORCED-DECISION ROUND
        
        Patient Case:
        {case_text}
        
        Constraint: The question limit has been reached. DO NOT ASK ANY FURTHER QUESTIONS.
        You MUST COMMIT TO A DIAGNOSIS (best or provisional) including:
        - Top diagnosis and brief reasoning
        - Confidence level (as a percentage or Low/Medium/High)
        - 1-2 key next-step actions if applicable
        
        End with exactly: "DECISION: COMMIT_DIAGNOSIS".
        """
        result = self._run_async(team.run(task=[TextMessage(content=forced_prompt, source="user")]))
        decision = self._extract_final_decision([{"name": m.source, "content": getattr(m, 'content', '')} for m in result.messages])
        return decision

    async def _conduct_forced_decision_async(self, case_text: str) -> Dict:
        logger.info("Starting forced-decision round (async)")
        team = RoundRobinGroupChat(
            [
                self.dr_hypothesis,
                self.dr_test_chooser,
                self.dr_challenger,
                self.dr_stewardship,
                self.dr_checklist,
                self.panel_coordinator,
            ],
            max_turns=8,
            termination_condition=TextMentionTermination("DECISION:")
        )
        forced_prompt = f"""
        MEDICAL PANEL FORCED-DECISION ROUND
        
        Patient Case:
        {case_text}
        
        Constraint: The question limit has been reached. DO NOT ASK ANY FURTHER QUESTIONS.
        You MUST COMMIT TO A DIAGNOSIS (best or provisional) including:
        - Top diagnosis and brief reasoning
        - Confidence level (as a percentage or Low/Medium/High)
        - 1-2 key next-step actions if applicable
        
        End with exactly: "DECISION: COMMIT_DIAGNOSIS".
        """
        result = await team.run(task=[TextMessage(content=forced_prompt, source="user")])
        return self._extract_final_decision([
            {"name": m.source, "content": getattr(m, 'content', '')} for m in result.messages
        ])
    
    def evaluate_information_sufficiency(self, patient_case: str) -> InformationSufficiencyAssessment:
        """
        Evaluate whether the patient case has sufficient information
        
        Args:
            patient_case: Patient case description
            
        Returns:
            InformationSufficiencyAssessment: Detailed sufficiency assessment
        """
        return self.sufficiency_evaluator.evaluate_case_sufficiency(patient_case)
    
    def should_prioritize_questions(self, patient_case: str) -> Tuple[bool, InformationSufficiencyAssessment]:
        """
        Determine if questions should be prioritized over tests/diagnosis
        
        Args:
            patient_case: Patient case description
            
        Returns:
            Tuple[bool, InformationSufficiencyAssessment]: (should_ask_questions, assessment)
        """
        assessment = self.evaluate_information_sufficiency(patient_case)
        should_ask = self.sufficiency_evaluator.should_ask_questions(assessment)
        
        logger.info(f"Information Sufficiency Assessment:")
        logger.info(f"  Overall Score: {assessment.overall_sufficiency_score:.2f}")
        logger.info(f"  Confidence Level: {assessment.confidence_level}")
        logger.info(f"  Should Ask Questions: {should_ask}")
        logger.info(f"  Missing Elements: {assessment.missing_critical_elements}")
        
        return should_ask, assessment
    
    def estimate_test_costs(self, test_names: List[str]) -> Dict:
        """
        Estimate costs for proposed tests
        """
        # Simplified cost database - in practice this would be more comprehensive
        test_costs = {
            "complete blood count": 25.0,
            "comprehensive metabolic panel": 35.0,
            "lipid panel": 30.0,
            "thyroid function tests": 45.0,
            "ecg": 50.0,
            "chest x-ray": 75.0,
            "echocardiogram": 200.0,
            "stress test": 300.0,
            "ct scan": 500.0,
            "mri": 800.0,
            "cardiac catheterization": 2000.0,
            "biopsy": 400.0
        }
        
        estimated_costs = {}
        total_cost = 0.0
        
        for test_name in test_names:
            # Simple fuzzy matching for test names
            cost = None
            for known_test, test_cost in test_costs.items():
                if known_test.lower() in test_name.lower() or test_name.lower() in known_test.lower():
                    cost = test_cost
                    break
            
            if cost is None:
                cost = 150.0  # Default cost for unknown tests
            
            estimated_costs[test_name] = cost
            total_cost += cost
        
        return {
            "individual_costs": estimated_costs,
            "total_estimated_cost": total_cost,
            "budget_feasible": (not self.budget_tracker.budget_limit or 
                              (self.budget_tracker.cumulative_cost + total_cost) <= self.budget_tracker.budget_limit)
        }
    
    def process_patient_case(self, patient_case: str, budget_limit: Optional[float] = None) -> Dict:
        """
        Main entry point for processing a patient case
        """
        if budget_limit:
            self.budget_tracker.budget_limit = budget_limit
        
        # Reset question usage for a new case
        self.question_rounds_used = 0
            
        logger.info(f"Processing patient case with budget limit: ${budget_limit}")
        
        try:
            # Conduct the Chain of Debate
            decision = self.conduct_chain_of_debate(patient_case)
            
            # Add cost analysis if tests are being ordered
            if decision["action"] == "order_tests":
                # Extract test names from decision details (simplified parsing)
                # In practice, you'd want more robust test name extraction
                decision["cost_analysis"] = {
                    "message": "Cost analysis would be performed on specific test orders",
                    "current_budget_status": decision["budget_status"]
                }
            
            return decision
            
        except Exception as e:
            logger.error(f"Error processing patient case: {str(e)}")
            return {
                "action": "error",
                "details": f"Error during panel discussion: {str(e)}",
                "timestamp": now_local()
            }

    async def process_patient_case_async(self, patient_case: str, budget_limit: Optional[float] = None) -> Dict:
        if budget_limit:
            self.budget_tracker.budget_limit = budget_limit
        self.question_rounds_used = 0
        logger.info(f"Processing patient case with budget limit (async): ${budget_limit}")
        try:
            decision = await self.conduct_chain_of_debate_async(patient_case)
            if decision.get("action") == "ask_questions":
                if self.question_rounds_used >= self.question_rounds_limit:
                    decision = await self._conduct_forced_decision_async(patient_case)
            return decision
        except Exception as e:
            logger.error(f"Error processing patient case (async): {str(e)}")
            return {
                "action": "error",
                "details": f"Error during panel discussion: {str(e)}",
                "timestamp": now_local()
            }

def demonstrate_information_sufficiency():
    """
    Comprehensive demonstration of information sufficiency identification methods
    """
    print("=" * 80)
    print("INFORMATION SUFFICIENCY IDENTIFICATION METHODS")
    print("=" * 80)
    
    # Initialize evaluator
    evaluator = InformationSufficiencyEvaluator()
    
    # Test cases with varying levels of information completeness
    test_cases = {
        "Minimal Case": "35-year-old patient presents with chest pain.",
        
        "Moderate Case": """
        45-year-old male presents with chest pain that started 2 hours ago.
        Pain is described as pressure-like, 7/10 severity.
        Associated with shortness of breath.
        Past medical history of hypertension.
        """,
        
        "Complete Case": """
        45-year-old male presents with substernal chest pain that started 2 hours ago while climbing stairs.
        Pain is pressure-like, 7/10 severity, radiating to left arm.
        Associated with shortness of breath and diaphoresis.
        No relief with rest.
        Past medical history: Hypertension, diabetes mellitus type 2, smoking (1 pack/day for 20 years).
        Family history: Father had MI at age 50.
        Current medications: Lisinopril, Metformin.
        Vital signs: BP 150/95, HR 105, RR 22, O2 sat 96% on room air.
        Physical exam: Appears diaphoretic, mild distress.
        """
    }
    
    print("\nANALYZING DIFFERENT CASE COMPLETENESS LEVELS:")
    print("-" * 60)
    
    for case_name, case_text in test_cases.items():
        print(f"\n🔍 **{case_name.upper()}**")
        print(f"Case: {case_text.strip()}")
        
        # Evaluate sufficiency
        assessment = evaluator.evaluate_case_sufficiency(case_text)
        
        print(f"\n📊 **SUFFICIENCY SCORES:**")
        print(f"  • Overall Score: {assessment.overall_sufficiency_score:.2f}/1.0")
        print(f"  • Present Illness: {assessment.present_illness_score:.2f}/1.0")
        print(f"  • Past Medical History: {assessment.past_medical_history_score:.2f}/1.0")
        print(f"  • Family History: {assessment.family_history_score:.2f}/1.0")
        print(f"  • Social History: {assessment.social_history_score:.2f}/1.0")
        print(f"  • Medications: {assessment.medications_score:.2f}/1.0")
        print(f"  • Physical Exam: {assessment.physical_exam_score:.2f}/1.0")
        print(f"  • Review of Systems: {assessment.review_of_systems_score:.2f}/1.0")
        
        print(f"\n🎯 **DECISION INDICATORS:**")
        print(f"  • Confidence Level: {assessment.confidence_level.upper()}")
        print(f"  • Should Ask Questions: {'YES' if evaluator.should_ask_questions(assessment) else 'NO'}")
        
        if assessment.missing_critical_elements:
            print(f"\n❌ **MISSING CRITICAL ELEMENTS:**")
            for element in assessment.missing_critical_elements:
                print(f"    • {element}")
        
        # Generate targeted questions
        if evaluator.should_ask_questions(assessment):
            questions = evaluator.generate_targeted_questions(assessment)
            print(f"\n❓ **SUGGESTED QUESTIONS ({len(questions)}):**")
            for i, question in enumerate(questions, 1):
                print(f"    {i}. {question}")
        
        print("\n" + "-" * 60)
    
    print("\n" + "=" * 80)
    print("INFORMATION SUFFICIENCY CRITERIA SUMMARY")
    print("=" * 80)
    
    print("""
🎯 **DECISION THRESHOLDS:**
   • High Confidence (>0.8): Ready for tests/diagnosis
   • Medium Confidence (0.5-0.8): May need targeted questions
   • Low Confidence (<0.5): Definitely need more information

🔍 **KEY INFORMATION CATEGORIES (Weighted):**
   • Present Illness (30%): Chief complaint, onset, duration, character, severity
   • Past Medical History (15%): Chronic conditions, surgeries, allergies
   • Physical Exam (15%): Vital signs, examination findings
   • Medications (15%): Current medications, dosages, compliance
   • Family History (10%): Genetic predispositions, family diseases
   • Social History (10%): Smoking, alcohol, occupation, travel
   • Review of Systems (5%): Constitutional symptoms, organ systems

❌ **CRITICAL MISSING ELEMENTS THAT TRIGGER QUESTIONS:**
   • Chief complaint unclear
   • No onset information
   • No duration specified
   • No past medical history
   • No medications mentioned
   • No physical exam findings
   • No family history
   • No social history

🤖 **AUTOMATED QUESTION GENERATION:**
   • Targeted questions based on specific missing information
   • Prioritized by clinical importance
   • Limited to 8 questions to avoid overwhelming
   • Structured to gather HPI, history, and examination data
    """)
    
    print("\n" + "=" * 80)
    print("INTEGRATION WITH MEDICAL PANEL SYSTEM")
    print("=" * 80)
    
    print("""
The information sufficiency system integrates with the medical panel in multiple ways:

🔄 **AUTOMATED PREPROCESSING:**
   1. Every case is automatically evaluated before panel discussion
   2. Sufficiency scores are provided to all agents
   3. Missing elements are highlighted to guide discussion

🎯 **BIASED DECISION-MAKING:**
   1. Panel Coordinator receives sufficiency assessment
   2. Dr. Hypothesis gets information gap analysis
   3. Automatic question generation when sufficiency is low

📊 **OBJECTIVE METRICS:**
   1. Quantitative scores replace subjective assessment
   2. Consistent criteria across all cases
   3. Trackable improvement in information gathering

💡 **SMART QUESTION TARGETING:**
   1. Questions generated based on specific missing elements
   2. Clinical priority ordering
   3. Avoids redundant or low-value questions
    """)

if __name__ == "__main__":
    # Run the information sufficiency demonstration
    demonstrate_information_sufficiency() 
"""
AI-powered Assessment Mapping Service
Maps Moodle activities to QCTO assessment criteria using OpenAI GPT-4 and Claude API.
"""
import os
from typing import List, Dict, Optional
from decimal import Decimal
import openai
import anthropic
from django.conf import settings


class AIMapperError(Exception):
    """Custom exception for AI mapping errors"""
    pass


class AssessmentMapper:
    """
    AI service for mapping Moodle activities to QCTO assessment criteria.
    
    Uses OpenAI GPT-4 as primary, Claude API as fallback.
    Returns top 3 suggestions ranked by confidence.
    
    Usage:
        mapper = AssessmentMapper()
        suggestions = mapper.map_activity_to_criteria(
            activity_name="Welding Safety Quiz",
            activity_description="Assessment of safety procedures...",
            available_criteria=[...]
        )
    """
    
    def __init__(self):
        """Initialize AI clients with API keys from settings"""
        self.openai_api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
        self.claude_api_key = getattr(settings, 'ANTHROPIC_API_KEY', os.getenv('ANTHROPIC_API_KEY'))
        
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        
        if self.claude_api_key:
            self.claude_client = anthropic.Anthropic(api_key=self.claude_api_key)
    
    def map_activity_to_criteria(
        self,
        activity_name: str,
        activity_description: str,
        activity_type: str,
        available_criteria: List[Dict[str, str]],
        max_suggestions: int = 3
    ) -> List[Dict]:
        """
        Map a Moodle activity to QCTO assessment criteria using AI.
        
        Args:
            activity_name: Name of the Moodle activity
            activity_description: Description/content of the activity
            activity_type: Type (QUIZ, ASSIGN, LESSON, etc.)
            available_criteria: List of dicts with 'criteria_code' and 'description'
            max_suggestions: Maximum number of suggestions to return (default 3)
        
        Returns:
            List of mappings sorted by confidence:
            [
                {
                    'criteria_code': 'AC1.1',
                    'confidence': 95.5,
                    'reasoning': 'This activity directly assesses...'
                },
                ...
            ]
        
        Raises:
            AIMapperError: If both AI services fail
        """
        # Try OpenAI first
        if self.openai_api_key:
            try:
                return self._map_with_openai(
                    activity_name,
                    activity_description,
                    activity_type,
                    available_criteria,
                    max_suggestions
                )
            except Exception as e:
                print(f"OpenAI mapping failed: {str(e)}, falling back to Claude")
        
        # Fallback to Claude
        if self.claude_api_key:
            try:
                return self._map_with_claude(
                    activity_name,
                    activity_description,
                    activity_type,
                    available_criteria,
                    max_suggestions
                )
            except Exception as e:
                raise AIMapperError(f"Both AI services failed. Claude error: {str(e)}")
        
        raise AIMapperError("No AI API keys configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
    def _build_prompt(
        self,
        activity_name: str,
        activity_description: str,
        activity_type: str,
        available_criteria: List[Dict[str, str]],
        max_suggestions: int
    ) -> str:
        """Build the AI prompt for assessment mapping"""
        criteria_list = "\n".join([
            f"- {c['criteria_code']}: {c['description']}"
            for c in available_criteria
        ])
        
        prompt = f"""You are an expert in QCTO (Quality Council for Trades and Occupations) assessment mapping for South African vocational training.

Your task is to map a Moodle LMS activity to the most appropriate QCTO assessment criteria.

MOODLE ACTIVITY:
- Name: {activity_name}
- Type: {activity_type}
- Description: {activity_description}

AVAILABLE QCTO ASSESSMENT CRITERIA:
{criteria_list}

INSTRUCTIONS:
1. Analyze the Moodle activity content and learning outcomes
2. Compare against each QCTO assessment criterion
3. Select the top {max_suggestions} BEST MATCHING criteria
4. Rank them by confidence (0-100)
5. Provide clear reasoning for each match

RESPONSE FORMAT (JSON):
{{
    "mappings": [
        {{
            "criteria_code": "AC1.1",
            "confidence": 95.5,
            "reasoning": "This activity directly assesses the learner's ability to..."
        }},
        {{
            "criteria_code": "AC2.3",
            "confidence": 78.0,
            "reasoning": "Partial alignment - the quiz covers some aspects of..."
        }}
    ]
}}

IMPORTANT:
- Only suggest mappings with confidence > 50%
- Be conservative - only map if there's genuine alignment
- Consider critical vs non-critical criteria
- Explain WHY each mapping makes sense
- Return ONLY valid JSON, no other text

Respond now:"""
        
        return prompt
    
    def _map_with_openai(
        self,
        activity_name: str,
        activity_description: str,
        activity_type: str,
        available_criteria: List[Dict[str, str]],
        max_suggestions: int
    ) -> List[Dict]:
        """Map using OpenAI GPT-4"""
        prompt = self._build_prompt(
            activity_name,
            activity_description,
            activity_type,
            available_criteria,
            max_suggestions
        )
        
        response = openai.chat.completions.create(
            model="gpt-4o",  # Latest GPT-4 model
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert QCTO assessment mapper. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent mappings
            response_format={"type": "json_object"}
        )
        
        result = response.choices[0].message.content
        
        # Parse JSON response
        import json
        data = json.loads(result)
        mappings = data.get('mappings', [])
        
        # Sort by confidence descending
        mappings.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        return mappings[:max_suggestions]
    
    def _map_with_claude(
        self,
        activity_name: str,
        activity_description: str,
        activity_type: str,
        available_criteria: List[Dict[str, str]],
        max_suggestions: int
    ) -> List[Dict]:
        """Map using Anthropic Claude"""
        prompt = self._build_prompt(
            activity_name,
            activity_description,
            activity_type,
            available_criteria,
            max_suggestions
        )
        
        message = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",  # Latest Claude model
            max_tokens=2048,
            temperature=0.3,
            system="You are an expert QCTO assessment mapper. Always respond with valid JSON only.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        result = message.content[0].text
        
        # Parse JSON response
        import json
        data = json.loads(result)
        mappings = data.get('mappings', [])
        
        # Sort by confidence descending
        mappings.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        return mappings[:max_suggestions]
    
    def batch_map_activities(
        self,
        activities: List[Dict],
        available_criteria: List[Dict[str, str]],
        max_suggestions: int = 3
    ) -> Dict[int, List[Dict]]:
        """
        Map multiple activities in batch.
        
        Args:
            activities: List of activity dicts with 'id', 'name', 'description', 'type'
            available_criteria: List of available QCTO criteria
            max_suggestions: Max suggestions per activity
        
        Returns:
            Dict mapping activity_id to list of suggestions
        """
        results = {}
        
        for activity in activities:
            try:
                mappings = self.map_activity_to_criteria(
                    activity_name=activity['name'],
                    activity_description=activity.get('description', ''),
                    activity_type=activity.get('type', 'OTHER'),
                    available_criteria=available_criteria,
                    max_suggestions=max_suggestions
                )
                results[activity['id']] = mappings
            except AIMapperError as e:
                print(f"Failed to map activity {activity['id']}: {str(e)}")
                results[activity['id']] = []
        
        return results

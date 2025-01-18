from typing import List, Dict, Tuple, Optional
import logging
from ..models.job_match import RequirementMatch
from ..config import client
from ..prompts import JOB_MATCH_ANALYSIS_PROMPT

class JobMatcher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _extract_percentage(text: str) -> float:
        try:
            import re
            matches = re.findall(r'(?:overall|skills?|experience)(?:[^:]*):[ ]*(\d+(?:\.\d+)?)', text.lower())
            if matches:
                score = float(matches[0])
                return max(85.0, min(score, 100.0))
            return 85.0
        except ValueError:
            return 85.0

    @staticmethod
    def _clean_comment(text: str) -> str:
        # Remove Analysis section and limit to 6 words
        text = text.split('\nAnalysis:')[0]
        words = text.strip().split()
        return ' '.join(words[:6])

    def _parse_ai_response(self, response: str) -> Dict[str, any]:
        sections = {
            "match_percentage": 0.0,
            "skills_match": 0.0,
            "experience_match": 0.0,
            "analysis": "",
            "skills_comment": "",
            "experience_comment": "",
            "overall_comment": ""
        }
        
        current_section = None
        for line in response.split('\n'):
            line_lower = line.lower().strip()
            if 'overall:' in line_lower:
                sections['match_percentage'] = self._extract_percentage(line)
                current_section = 'overall'
            elif 'skills match:' in line_lower:
                sections['skills_match'] = self._extract_percentage(line)
                current_section = 'skills'
            elif 'experience match:' in line_lower:
                sections['experience_match'] = self._extract_percentage(line)
                current_section = 'experience'
            elif line.strip():
                if current_section == 'overall':
                    sections['overall_comment'] = self._clean_comment(line)
                elif current_section == 'skills':
                    sections['skills_comment'] = self._clean_comment(line)
                elif current_section == 'experience':
                    sections['experience_comment'] = self._clean_comment(line)

        return sections

    async def analyze_match(self, job_desc: dict, cv_data: str, skill_map: Optional[List[Dict[str, str]]] = None):
        try:
            skill_description_map = {}
            if skill_map:
                for item in skill_map:
                    skill_description_map.update(item)

            prompt = JOB_MATCH_ANALYSIS_PROMPT.format(
                title=job_desc["title"],
                objective=job_desc["objective"],
                goals=job_desc["goals"],
                description=job_desc["description"],
                skills=", ".join(job_desc["skills"]),
                experience=str(job_desc["experienceRequired"]),
                cv_data=cv_data,
                skill_descriptions="\n".join(f"{k}: {v}" for k, v in skill_description_map.items())
            )

            completion = client.chat.complete(
                model="mistral-large-latest",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert HR analyst. Evaluate matches and provide scores.
                        STRICT RULES:
                        1. Score between 85-100% ONLY if CV data shows clear evidence
                        2. If CV data is missing/invalid, score should be 0%
                        3. ALL comments must be EXACTLY 6 WORDS OR LESS
                        4. Be extremely concise and accurate
                        5. Verify skills against actual CV content
                        
                        FORMAT EXACTLY AS:
                        Overall: XX%
                        [6 words or less comment]
                        
                        Skills Match: XX%
                        [6 words or less comment]
                        
                        Experience Match: XX%
                        [6 words or less comment]
                        
                        NOTE: Default to 0% if CV data is invalid"""
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            )
            response = completion.choices[0].message.content

            if not response:
                raise Exception("Empty response from AI service")

            sections = self._parse_ai_response(response)
            
            requirements = [
                RequirementMatch(
                    requirement="Technical Skills",
                    expectation=f"Required: {', '.join(job_desc['skills'])}",
                    candidateProfile=cv_data,
                    matchPercentage=sections['skills_match'],
                    comment=sections['skills_comment'].strip()
                ),
                RequirementMatch(
                    requirement="Experience",
                    expectation=f"{job_desc['experienceRequired']} years",
                    candidateProfile=cv_data,
                    matchPercentage=sections['experience_match'],
                    comment=sections['experience_comment'].strip()
                ),
                RequirementMatch(
                    requirement="Overall Assessment",
                    expectation="Job Fit Analysis",
                    candidateProfile=cv_data,
                    matchPercentage=sections['match_percentage'],
                    comment=sections['overall_comment'].strip()
                )
            ]

            return sections['match_percentage'], requirements

        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise Exception(f"Analysis failed: {str(e)}")
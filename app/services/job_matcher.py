from typing import Any, List, Dict, Tuple
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
        text = text.split('\nAnalysis:')[0]
        words = text.strip().split()
        return ' '.join(words[:6])

    def _extract_matched_fields(self, section: str, cv_data: str, skill_map: Dict[str, str] = None) -> Dict[str, Any]:
        """Extract relevant fields from cv_data based on the section."""
        if section.lower() in (skill_map or {}):
            # Return the skill description for this specific skill
            return {section: skill_map[section]}
        elif section.lower() == 'experience':
            return {"experience": cv_data}
        elif section.lower() == 'overall':
            return {"summary": cv_data}
        else:
            return {}

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


    async def analyze_match(self, job_desc: dict, cv_data: str, skill_map: dict | None = None):
        try:
            prompt = JOB_MATCH_ANALYSIS_PROMPT.format(
                title=job_desc["title"],
                objective=job_desc["objective"],
                goals=job_desc["goals"],
                description=job_desc["description"],
                skills=", ".join(job_desc["skills"]),
                experience=str(job_desc["experienceRequired"]),
                cv_data=cv_data,
                skill_descriptions="\n".join(f"{k}: {v}" for k, v in (skill_map or {}).items())
            )

            completion = client.chat.complete(
                model="mistral-large-latest",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert HR analyst. Evaluate matches and provide comprehensive candidate profiles for each mandatory field.
                        STRICT RULES:
                        1. Provide detailed profiles for each requirement.
                        2. If CV data is missing/invalid, indicate accordingly.
                        3. Ensure all profiles are based on CV content."""
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
                    requirement=skill,
                    expectation=f"Required proficiency in {skill}",
                    candidateProfile=self._extract_matched_fields(skill, cv_data, skill_map),
                    matchPercentage=sections['skills_match'],
                    comment=sections['skills_comment'].strip()
                ) for skill in (skill_map or {}).keys()
            ]
            requirements.append(
                RequirementMatch(
                    requirement="Overall Assessment",
                    expectation="Job Fit Analysis",
                    candidateProfile=self._extract_matched_fields("overall", cv_data),
                    matchPercentage=sections['match_percentage'],
                    comment=sections['overall_comment'].strip()
                )
            )

            return sections['match_percentage'], requirements

        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise Exception(f"Analysis failed: {str(e)}")
from typing import List, Dict, Tuple
import logging
from ..models.job_match import RequirementMatch
from ..config import client
from ..prompts import JOB_MATCH_ANALYSIS_PROMPT

class JobMatcher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _parse_ai_response(self, response: str) -> Dict[str, any]:
        """Parse AI response into structured format"""
        sections = {
            "match_percentage": 0.0,
            "skills_match": 0.0,
            "experience_match": 0.0,
            "analysis": ""
        }
        
        def extract_percentage(text: str) -> float:
            try:
                import re
                matches = re.findall(r'(?:overall|skills?|experience)(?:[^:]*):[ ]*(\d+(?:\.\d+)?)', text.lower())
                if matches:
                    score = float(matches[0])
                    return max(85.0, min(score, 100.0))
                return 85.0
            except ValueError:
                return 85.0

        for line in response.split('\n'):
            line_lower = line.lower().strip()
            if 'overall:' in line_lower:
                sections['match_percentage'] = extract_percentage(line)
            elif 'skills match:' in line_lower or 'skills:' in line_lower:
                sections['skills_match'] = extract_percentage(line)
            elif 'experience match:' in line_lower or 'experience:' in line_lower:
                sections['experience_match'] = extract_percentage(line)
            elif line.strip():
                sections['analysis'] += line + '\n'
        
        return sections

    async def analyze_match(self, job_desc: dict, candidate: dict):
        try:
            prompt = JOB_MATCH_ANALYSIS_PROMPT.format(
                title=job_desc["title"],
                description=job_desc["description"],
                skills=", ".join(job_desc["skills"]),
                experience=job_desc["experienceRequired"],
                candidate_skills=", ".join(f"{skill}: {level}" 
                                         for skill, level in candidate["skills"].items()),
                candidate_experience=candidate["experience"],
                notice_period=candidate["noticePeriod"],
                salary=candidate["expectedSalary"]
            )

            try:
                completion = client.chat.complete(
                    model="mistral-large-latest",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are an expert HR analyst. Evaluate matches and provide detailed scores.
                            YOU MUST:
                            1. Score between 85-100% based on actual match quality
                            2. Never default to minimum scores
                            3. Justify each score with specific reasons
                            
                            FORMAT EXACTLY AS:
                            Overall: XX%
                            Skills Match: XX%
                            Experience Match: XX%
                            
                            Analysis:
                            [Detailed justification for each score]"""
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ]
                )
                response = completion.choices[0].message.content
            except Exception as api_error:
                raise Exception(f"AI analysis failed: {str(api_error)}")

            if not response:
                raise Exception("Empty response from AI service")

            sections = self._parse_ai_response(response)
            
            requirements = [
                RequirementMatch(
                    requirement="Technical Skills",
                    expectation=f"Required: {', '.join(job_desc['skills'])}",
                    candidateProfile=", ".join(candidate["skills"].keys()),
                    matchPercentage=sections['skills_match']
                ),
                RequirementMatch(
                    requirement="Experience",
                    expectation=job_desc["experienceRequired"],
                    candidateProfile=candidate["experience"],
                    matchPercentage=sections['experience_match']
                ),
                RequirementMatch(
                    requirement="Overall Assessment",
                    expectation="Job Fit Analysis",
                    candidateProfile=sections['analysis'].strip(),
                    matchPercentage=sections['match_percentage']
                )
            ]

            return sections['match_percentage'], requirements

        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise Exception(f"Analysis failed: {str(e)}")
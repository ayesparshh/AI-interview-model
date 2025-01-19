from typing import Any, List, Dict, Tuple
import logging
import re
from ..models.job_match import RequirementMatch
from ..config import client
from ..prompts import JOB_MATCH_ANALYSIS_PROMPT

class JobMatcher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _extract_percentage(text: str) -> float:
        try:
            matches = re.findall(r'(?:overall|skills?|experience)(?:[^:]*):[ ]*(\d+(?:\.\d+)?)', text.lower())
            if matches:
                score = float(matches[0])
                return min(score, 100.0)  
            return 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def _clean_comment(text: str) -> str:
        text = text.split('\nAnalysis:')[0]
        if text.startswith("**Overall Comment:**"):
            text = text.replace("**Overall Comment:**", "").strip()
        if text.startswith("**Skills Comment:**"):
            text = text.replace("**Skills Comment:**", "").strip()

        words = text.split()
        return ' '.join(words[:6]).strip()

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
        analysis_text = []
        
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
            elif 'analysis:' in line_lower:
                current_section = 'analysis'
            elif line.strip():
                if current_section == 'analysis':
                    analysis_text.append(line.strip())
                elif current_section == 'overall':
                    sections['overall_comment'] = self._clean_comment(line)
                elif current_section == 'skills':
                    sections['skills_comment'] = self._clean_comment(line)
                elif current_section == 'experience':
                    sections['experience_comment'] = self._clean_comment(line)

        sections['analysis'] = ' '.join(analysis_text)
        return sections

    async def analyze_match(self, job_desc: dict, cv_data: str, skill_map: List[Dict[str, str]] | None = None):
        try:
            parsed_skill_map = {}
            if skill_map:
                for skill_info in skill_map:
                    for skill_name, description in skill_info.items():
                        parsed_skill_map[skill_name.lower()] = {
                            'original': skill_name,
                            'description': description
                        }

            # Modify prompt to always include skill assessments
            prompt = f"""
            {JOB_MATCH_ANALYSIS_PROMPT.format(
                title=job_desc["title"],
                objective=job_desc["objective"],
                goals=job_desc["goals"],
                description=job_desc.get("jobDescription", job_desc.get("description", "")),
                skills=", ".join(job_desc["skills"]),
                experience=str(job_desc["experienceRequired"]),
                cv_data=cv_data,
                skill_descriptions="\n".join(f"{info['original']}: {info['description']}" 
                                        for info in parsed_skill_map.values())
            )}

            IMPORTANT: YOU MUST include an Assessment for EACH skill listed above.
            For any skill not found in CV, provide assessment: "No evidence found in CV data"
            """

            # Single API request
            completion = client.chat.complete(
                model="mistral-large-latest",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert HR analyst. Analyze each skill with specific scoring criteria justification."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            )
            
            response = completion.choices[0].message.content
            sections = self._parse_ai_response(response)
            
            requirements = []
            for skill in job_desc["skills"]:
                skill_info = parsed_skill_map.get(skill.lower()) or parsed_skill_map.get(
                    next((k for k in parsed_skill_map if k in skill.lower() or skill.lower() in k), '')
                )
                skill_description = skill_info['description'] if skill_info else "No description provided"
                
                pattern = f"Skill: {skill}.*?Assessment: (.*?)(?=Skill:|$)"
                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                skill_analysis = match.group(1).strip() if match else "No assessment available"
                
                skill_pattern = f"Skill: {skill}.*?Match Percentage: (\d+)"
                skill_match = re.search(skill_pattern, response, re.DOTALL | re.IGNORECASE)
                skill_percentage = float(skill_match.group(1)) if skill_match else sections['skills_match']
                
                requirements.append(
                    RequirementMatch(
                        requirement=skill,
                        expectation=f"Required proficiency in {skill}",
                        candidateProfile=skill_description,
                        matchPercentage=skill_percentage,
                        comment=skill_analysis
                    )
                )

            # Add overall assessment
            requirements.append(
                RequirementMatch(
                    requirement="Overall Assessment",
                    expectation="Job Fit Analysis",
                    candidateProfile="Overall profile analysis", 
                    matchPercentage=sections['match_percentage'],
                    comment=sections['analysis'] if sections['analysis'] else sections['overall_comment']
                )
            )

            return sections['match_percentage'], requirements

        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise Exception(f"Analysis failed: {str(e)}")
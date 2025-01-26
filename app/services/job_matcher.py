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
        # Remove any markdown formatting and newlines
        text = re.sub(r'\*\*.*?\*\*:', '', text)
        text = text.replace('\n', ' ').strip()
        
        # Remove any analysis prefixes
        text = text.split('Analysis:')[-1].strip()
        
        # Limit to meaningful first sentence
        sentences = text.split('.')
        return sentences[0].strip() if sentences else text.strip()

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
                    clean_line = line.strip()
                    if clean_line and not clean_line.lower().startswith(('overall:', 'skills:', 'experience:')):
                        analysis_text.append(clean_line)
                elif current_section in ['overall', 'skills', 'experience']:
                    sections[f'{current_section}_comment'] = self._clean_comment(line)

        sections['analysis'] = ' '.join(analysis_text).strip()
        return sections

    def _extract_skill_info(self, response: str, skill: str) -> Tuple[float, str]:
        skill_pattern = fr"Skill:\s*{re.escape(skill)}.*?Match Percentage:\s*(\d+)"
        analysis_pattern = fr"Skill:\s*{re.escape(skill)}.*?Assessment:\s*(.*?)(?=(?:Skill:|$))"
        
        skill_match = re.search(skill_pattern, response, re.DOTALL | re.IGNORECASE)
        analysis_match = re.search(analysis_pattern, response, re.DOTALL | re.IGNORECASE)
        
        percentage = float(skill_match.group(1)) if skill_match else 0.0
        analysis = ' '.join(analysis_match.group(1).strip().split()[:6]) if analysis_match else "No specific assessment available"
        
        return percentage, analysis

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
            """

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
                ],
                temperature=0.1
            )
            
            response = completion.choices[0].message.content
            sections = self._parse_ai_response(response)
            
            requirements = []
            for skill in job_desc["skills"]:
                skill_info = parsed_skill_map.get(skill.lower()) or parsed_skill_map.get(
                    next((k for k in parsed_skill_map if k in skill.lower() or skill.lower() in k), '')
                )
                skill_description = skill_info['description'] if skill_info else "No description provided"
                skill_percentage, skill_analysis = self._extract_skill_info(response, skill)

                
                requirements.append(
                    RequirementMatch(
                        requirement=skill,
                        expectation=f"Required proficiency in {skill}",
                        candidateProfile=skill_description,
                        matchPercentage=skill_percentage or sections['skills_match'],
                        comment=skill_analysis

                    )
                )

            return (
                sections['match_percentage'], 
                requirements,
                sections['analysis'] if sections['analysis'] else sections['overall_comment']

            )

        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            raise Exception(f"Analysis failed: {str(e)}")
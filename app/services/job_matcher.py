from typing import List, Dict, Tuple
import logging
from ..models.job_match import RequirementMatch
from ..config import client
from ..prompts import JOB_MATCH_ANALYSIS_PROMPT

class JobMatcher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _parse_percentage(self, value: str) -> float:
        """Parse percentage value from string"""
        try:
            clean_value = value.replace('%', '').strip()
            return float(clean_value)
        except ValueError:
            return 0.0

    def _calculate_skill_weights(self, job_skills: List[str], candidate_skills: Dict[str, any]) -> Dict[str, float]:
        """Calculate weighted scores for skills based on importance and transferable skills"""
        weights = {}
        for skill in job_skills:
            skill_lower = skill.lower()
            # Direct matches
            direct_matches = [
                cs for cs in candidate_skills.keys()
                if skill_lower == cs.lower()
            ]
            # Related/transferable skills
            related_matches = [
                cs for cs in candidate_skills.keys()
                if (skill_lower in cs.lower() or cs.lower() in skill_lower) and cs not in direct_matches
            ]
            
            if direct_matches:
                weights[skill] = 100.0
            elif related_matches:
                weights[skill] = 90.0
            else:
                weights[skill] = 85.0
        return weights

    def _analyze_experience_match(self, required_exp: str, candidate_exp: str) -> Tuple[float, str]:
        """Analyze experience match considering various formats"""
        try:
            req_years = float(''.join(filter(str.isdigit, required_exp)))
            cand_years = float(''.join(filter(str.isdigit, candidate_exp)))
            
            match_percentage = min((cand_years / req_years * 100), 100) if req_years > 0 else 0
            analysis = f"Required: {required_exp} years | Candidate: {candidate_exp} years"
            
            return match_percentage, analysis
        except:
            # Fallback to AI analysis if parsing fails
            return 0.0, "Experience format needs manual analysis"

    def _parse_ai_response(self, response: str) -> Dict[str, any]:
        sections = {
            "match_percentage": 85.0,  # Default baseline
            "skills_analysis": "",
            "skills_match": 0.0,
            "experience_analysis": "",
            "experience_match": 0.0,
            "overall_assessment": ""
        }
        
        def extract_percentage(text: str) -> float:
            try:
                import re
                matches = re.findall(r'(?:percentage|match|score|rating):\s*(\d+(?:\.\d+)?)\s*%?', 
                                   text.lower())
                if matches:
                    return min(float(matches[0]), 100.0)  # Cap at 100%
            except ValueError:
                pass
            return 85.0  # Default to baseline if parsing fails
        
        # Rest of the parsing logic remains the same
        for section in response.split('\n\n'):
            section_lower = section.lower().strip()
            if 'overall_match_percentage:' in section_lower:
                sections['match_percentage'] = extract_percentage(section)
            elif 'skills_match_percentage:' in section_lower:
                sections['skills_match'] = extract_percentage(section)
                sections['skills_analysis'] = section
            elif 'experience_match_percentage:' in section_lower:
                sections['experience_match'] = extract_percentage(section)
                sections['experience_analysis'] = section
        
        # Use the maximum of calculated or extracted percentages
        if sections['match_percentage'] < 85.0:
            sections['match_percentage'] = max(
                85.0,
                (sections['skills_match'] * 0.6 + sections['experience_match'] * 0.4)
            )
        
        return sections

    async def analyze_match(self, job_desc: dict, candidate: dict) -> Tuple[float, List[RequirementMatch]]:
        try:
            # Calculate skill weights before AI analysis
            skill_weights = self._calculate_skill_weights(
                job_desc["skills"],
                candidate["skills"]
            )
            
            # Calculate initial experience match
            exp_match, exp_analysis = self._analyze_experience_match(
                job_desc["experienceRequired"],
                candidate["experience"]
            )

            # Enhance prompt with weighted analysis
            prompt = JOB_MATCH_ANALYSIS_PROMPT.format(
                title=job_desc["title"],
                description=job_desc["description"],
                skills=", ".join(f"{skill} (Match: {weight:.1f}%)" 
                               for skill, weight in skill_weights.items()),
                experience=job_desc["experienceRequired"],
                candidate_skills=", ".join(f"{skill} (Level: {level})" 
                                         for skill, level in candidate["skills"].items()),
                candidate_experience=candidate["experience"],
                notice_period=candidate["noticePeriod"],
                salary=candidate["expectedSalary"]
            ) + "\n\nPlease provide detailed percentage matches for skills and experience separately. Be critical and precise in your evaluation. Percentages should reflect actual match quality, not just presence of keywords."
            
            self.logger.debug(f"Formatted prompt: {prompt}")

            # Get AI analysis
            try:
                completion = client.chat.completions.create(
                    model="grok-beta",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are an expert HR analyst specialized in tech recruitment.
                            IMPORTANT SCORING RULES:
                            1. Start at 85% minimum for experience matches
                            2. Value transferable skills highly (Python → any backend)
                            3. Consider cloud/DevOps skills as transferable
                            4. Weight technical fundamentals over specific tools
                            5. Never score below 70% if years of experience match
                            Always justify scores through transferable skills."""
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    temperature=0.2,  # Even lower for consistency
                    max_tokens=1000,
                    presence_penalty=0.0,
                    frequency_penalty=0.0
                )
                response = completion.choices[0].message.content
                self.logger.debug(f"API Response: {response}")
            except Exception as api_error:
                self.logger.error(f"API Error: {str(api_error)}")
                raise Exception(f"API call failed: {str(api_error)}")

            if not response:
                self.logger.error("Empty response from AI service")
                raise Exception("Empty response from AI service")

            # Parse AI response
            sections = self._parse_ai_response(response)
            
            # Adjust skills match based on weights
            if sections['skills_match'] == 0.0:
                sections['skills_match'] = sum(skill_weights.values()) / len(skill_weights) if skill_weights else 0.0
            
            # Adjust experience match if AI didn't provide one
            if sections['experience_match'] == 0.0:
                sections['experience_match'] = exp_match
            
            requirements = [
                RequirementMatch(
                    requirement="Technical Skills",
                    expectation=f"Required: {', '.join(job_desc['skills'])}",
                    candidateProfile=", ".join([skill for skill, level in candidate["skills"].items()]),
                    matchPercentage=sections.get("skills_match", 0.0)
                ),
                RequirementMatch(
                    requirement="Experience",
                    expectation=job_desc["experienceRequired"],
                    candidateProfile=f"Years: {candidate['experience']} | Domains: {', '.join(candidate['skills'].keys())}",
                    matchPercentage=sections.get("experience_match", 0.0)
                ),
                RequirementMatch(
                    requirement="Overall Assessment",
                    expectation="Job Fit Analysis",
                    candidateProfile=f"Match quality based on skill overlap and experience",
                    matchPercentage=sections.get("match_percentage", 0.0)
                )
            ]

            return float(sections.get("match_percentage", 0.0)), requirements

        except Exception as e:
            self.logger.error(f"AI analysis failed: {str(e)}")
            raise Exception(f"AI analysis failed: {str(e)}")
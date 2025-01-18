from fastapi import APIRouter, HTTPException
from ..models.job_match import JobMatchRequest, JobMatchResponse
from ..services.job_matcher import JobMatcher

router = APIRouter()
matcher = JobMatcher()

@router.post("/analyze-match", response_model=JobMatchResponse)
async def analyze_job_match(request: JobMatchRequest):
    try:
        skill_map = {}
        if request.skill_description_map:
            for skill_dict in request.skill_description_map:
                skill_map.update(skill_dict)
        
        overall_match, requirements = await matcher.analyze_match(
            request.job.dict(),
            request.cv_data,
            skill_map
        )
        
        return JobMatchResponse(
            overallMatch=overall_match,
            requirements=requirements
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
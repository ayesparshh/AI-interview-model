CV_ANALYSIS_PROMPT = """
You are a CV analyzer. Analyze this CV against the job requirements and provide a STRICT response in this format:

MATCH_PERCENTAGE: [ONLY a number 0-100, no text]

Example correct format:
MATCH_PERCENTAGE: 75

SKILLS_ANALYSIS:
| Requirement | Expectation | Match Status |
|------------|-------------|--------------|
{requirements_table}

APPLICATION DETAILS:
| Category | Details |
|----------|---------|
| Mandatory Skills | Skill 1: {application_data[mandatory_skill_1]}
| | Skill 2: {application_data[mandatory_skill_2]}
| | Skill 3: {application_data[mandatory_skill_3]}
| | Skill 4: {application_data[mandatory_skill_4]}
| | Skill 5: {application_data[mandatory_skill_5]}
| Preferred Skills | {application_data[preferred_skills]}
| Current Address | {application_data[current_address]}
| Expected Salary | {application_data[expected_salary]}
| Notice Period | {application_data[notice_period]} months

KEY_FINDINGS:
| Category | Status | Details |
|----------|--------|---------|
| Experience Level | [Match/Partial/No Match] | [Details] |
| Language Skills | [Match/Partial/No Match] | [Level Found] |
| Location Compatibility | [Match/Partial/No Match] | [Distance & Travel Time] |
| Work Model | [Match/Partial/No Match] | [Remote/Hybrid/Onsite] |

SUMMARY:
- [Top 3 strengths]
- [Top 3 gaps]
- [Final recommendation]

CV: {cv_text}
Job Description: {job_description}
"""

MULTIPLE_JOBS_ANALYSIS_PROMPT = """
Provide a structured match analysis in following format:

MATCH_PERCENTAGE: [percentage]

| Category | Match Status |
|----------|-------------|
| Required Skills | [percentage] |
| Experience Level | [percentage] |
| Location Fit | [percentage] |
| Overall Fit | [percentage] |

Job Title: {job_title}
CV: {cv_text}
Job Description: {job_description}
"""

QUESTION_GENERATION_PROMPT = """
Based on the CV and job description, generate exactly {n} UNIQUE and DIVERSE technical interview questions.
Each question must focus on a DIFFERENT aspect of the candidate's experience or skills.
Each question must have an independently calculated estimated answer time between 2-6 minutes.

IMPORTANT RULES:
1. Generate exactly {n} questions
2. NEVER REPEAT similar questions or topics
3. Each question must cover a DIFFERENT technical area:
   - System Design & Architecture
   - Coding & Implementation
   - Problem Solving & Algorithms
   - Technical Leadership & Project Management
   - Tools & Technologies
   - Database & Data Modeling
   - Security & Performance
   - DevOps & Deployment

4. Each time estimate must be calculated based on the question's complexity:
   - Complex system design questions: 5-6 minutes
   - Technical implementation questions: 4-5 minutes
   - Experience-based questions: 3-4 minutes
   - Tool/technology specific questions: 2-3 minutes

5. Use this exact format:

Example format:
QUESTION: Describe a challenging scalability issue you encountered and how you resolved it.
TIME: 5

QUESTION: Explain your approach to implementing secure authentication in your projects.
TIME: 4

Previous Questions: {previous_questions}

CV: {cv_text}
Job Description: {job_description}
"""

ANSWER_SCORING_PROMPT = """
Evaluate the following question-answer pair and provide a score out of 10.
Format your response EXACTLY as follows:

SCORE: [number between 0-10]
FEEDBACK: [brief explanation of the score]

Question: {question}
Candidate Answer: {answer}
Job Description: {job_description}

Scoring criteria:
- Completeness (0-3 points)
- Technical accuracy (0-3 points)
- Communication clarity (0-2 points)
- Practical application (0-2 points)
"""

MULTIPLE_CANDIDATES_ANALYSIS_PROMPT = """
You are an AI CV analyzer. Based on the following CV and job description, calculate the match percentage.

CV Text:
{cv_text}

Job Description:
{job_description}

You MUST respond EXACTLY in this format:
MATCH_PERCENTAGE: [number]

For example:
MATCH_PERCENTAGE: 75

Rules:
1. Provide ONLY a number between 0 and 100
2. Do NOT include any % symbol
3. Do NOT include any additional text or explanation
4. The number should reflect the overall match between CV and job requirements
"""
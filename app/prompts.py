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

JOB_MATCH_ANALYSIS_PROMPT = """
Analyze this match and provide specific percentage scores.
IMPORTANT: Scores must be between 85-100% based on actual match quality.

Job Requirements:
Title: {title}
Description: {description}
Required Skills: {skills}
Required Experience: {experience}

Candidate Details:
Technical Skills: {candidate_skills}
Experience Level: {candidate_experience}
Notice Period: {notice_period}
Expected Salary: {salary}

YOU MUST RESPOND EXACTLY IN THIS FORMAT:
Overall: XX%
Skills Match: XX%
Experience Match: XX%

Analysis:
[Detailed justification for each score]

DO NOT default to minimum scores. Evaluate actual match quality.
"""

FOLLOW_UP_QUESTION_PROMPT = """
Based on this previous question and answer, generate a significantly more challenging follow-up question.

Original Question: {original_question}
Candidate's Answer: {provided_answer}
Topic Area: {topic_area}
Current Difficulty: {difficulty_level}

REQUIREMENTS:
1. Question MUST be technically more complex and build upon mentioned concepts
2. For caching-related questions, specifically explore:
   - Distributed caching architectures and patterns
   - Cache coherency and consistency challenges
   - Advanced cache invalidation strategies
   - Cache failure scenarios and recovery mechanisms
   - Cache warming and pre-population strategies
   - Memory optimization and eviction policies
   - Multi-level caching architectures
3. Focus on edge cases and system design implications
4. Challenge architectural decisions with scale considerations

Return in this JSON format:
{
    "question": "Your detailed follow-up question",
    "time_minutes": number between 3-6,
    "difficulty_increase": "significant",
    "related_concepts": ["concept1", "concept2", "concept3"]
}
"""
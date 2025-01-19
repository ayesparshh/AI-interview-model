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
Ensure your response strictly follows the format below.

Format:
SCORE: [number between 0-10]
COMMENT: [brief judging comment, max 6 words]

Scoring Criteria:
1. Completeness (0-4 points): Does the answer fully address all parts of the question?
2. Technical Accuracy (0-3 points): Is the technical content correct and well-explained?
3. Communication Clarity (0-2 points): Is the answer clearly and effectively communicated?
4. Practical Application (0-1 points): Does the answer include practical examples or applications?

Additional Requirements:
- Reference specific aspects of the candidate's answer in the comment.
- Avoid adding any information not present in the candidate's answer.
- Maintain objectivity and constructiveness in feedback.

Question: {question}
Candidate Answer: {answer}
"""

JOB_MATCH_ANALYSIS_PROMPT = """
Analyze the following job description and candidate CV data. Provide specific percentage scores along with detailed scoring justification for each skill.

Job Requirements:
Title: {title}
Objective: {objective}
Goals: {goals}
Description: {description}
Required Skills: {skills}
Required Experience: {experience}

Candidate Details:
CV Data: {cv_data}
Skill Descriptions: {skill_descriptions}

For each skill, provide:
1. A detailed assessment of proficiency level
2. Evidence from CV or provided skill descriptions
3. Justification for the scoring based on experience and projects

SCORING CRITERIA:

Skills Match (0-100%):
- 0-20%: Almost no required skills present
- 21-40%: Some basic skills present but major gaps
- 41-60%: Has core skills but lacks several requirements
- 61-80%: Most required skills present with minor gaps
- 81-100%: All or nearly all required skills present with depth

Experience Match (0-100%):
- 0-20%: No relevant experience
- 21-40%: Some related but not direct experience
- 41-60%: Has relevant experience but less than required
- 61-80%: Meets experience requirements
- 81-100%: Exceeds experience requirements

Overall Match (Weighted Average):
- Skills Match: 60% weight
- Experience Match: 40% weight
- Final score must reflect actual qualification gaps

STRICT VALIDATION RULES:
1. If CV Data is missing/invalid, all scores MUST be 0%
2. Required skills must be EXPLICITLY found in CV with evidence
3. Years of experience must be clearly verifiable
4. Perfect scores (95-100%) should be extremely rare
5. Use the full scoring range (0-100%)
6. Each score requires specific evidence from CV

YOU MUST RESPOND EXACTLY IN THIS FORMAT:
Overall: XX%
Overall Comment: [EXACTLY 6 WORDS]

Skills Match: XX%
Skills Comment: [EXACTLY 6 WORDS]

For each skill:
Skill: [skill_name]
Match Percentage: XX%
Assessment: [EXACTLY 6 WORDS describing key finding]

Experience Match: XX%
Experience Comment: [EXACTLY 6 WORDS]

Analysis: [EXACTLY 6 WORDS]
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
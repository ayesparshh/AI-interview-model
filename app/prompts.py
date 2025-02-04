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
Analyze the following job requirements and CV data:

Job Title: {title}
Objective: {objective}
Goals: {goals}
Description: {description}
Required Skills: {skills}
Required Experience: {experience}

CV Data:
{cv_data}

Skill Descriptions:
{skill_descriptions}

Please provide:
1. Overall Match Score (0-100)
2. Skills Match Score (0-100)
3. Experience Match Score (0-100)

For each skill, provide:
- Match percentage (0-100)
- One clear, concise sentence assessment

Guidelines:
- Keep all comments brief and specific
- Avoid using newlines in comments
- Focus on key points only
- Use simple, direct language

Format your response as:
Overall: [score]
[One sentence overall assessment]

Skills Match: [score]
[One sentence skills summary]

Experience Match: [score]
[One sentence experience assessment]

Analysis:
[Brief overall analysis]

For each skill:
Skill: [skill name]
Match Percentage: [score]
Assessment: [one clear sentence]
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
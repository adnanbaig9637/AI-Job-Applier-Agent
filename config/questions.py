'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''


###################################################### APPLICATION INPUTS ######################################################


# >>>>>>>>>>> Easy Apply Questions & Inputs <<<<<<<<<<<

# Give an relative path of your default resume to be uploaded. If file in not found, will continue using your previously uploaded resume in LinkedIn.
default_resume_path = "resumes/ADNAN_BAIG_Resume.pdf"      # (In Development)

# What do you want to answer for questions that ask about years of experience you have, this is different from current_experience? 
years_of_experience = "2"          # A number in quotes Eg: "0","1","2","3","4", etc.

# Do you need visa sponsorship now or in future?
require_visa = "No"               # "Yes" or "No"

# What is the link to your portfolio website, leave it empty as "", if you want to leave this question unanswered
website = "https://github.com/adnanbaig9637"                        # "www.example.bio" or "" and so on....

# Please provide the link to your LinkedIn profile.
linkedIn = "https://linkedin.com/in/adnanbaig2002/"       # "https://www.linkedin.com/in/example" or "" and so on...

# What is the status of your citizenship? # If left empty as "", tool will not answer the question. However, note that some companies make it compulsory to be answered
# Valid options are: "U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer", "Non-citizen allowed to work for current employer", "Non-citizen seeking work authorization", "Canadian Citizen/Permanent Resident" or "Other"
us_citizenship = "Non-citizen allowed to work for any employer"



## SOME ANNOYING QUESTIONS BY COMPANIES 🫠 ##

# What to enter in your desired salary question (American and European), What is your expected CTC (South Asian and others)?, only enter in numbers as some companies only allow numbers,
desired_salary = 1200000          # 80000, 90000, 100000 or 120000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your expected CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
And if asked in months, then it will divide by 12 and answer. Examples:
* 2400000 will be answered as "200000"
* 850000 will be answered as "70833"
'''

# What is your current CTC? Some companies make it compulsory to be answered in numbers...
current_ctc = 730000            # 800000, 900000, 1000000 or 1200000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your current CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
# And if asked in months, then it will divide by 12 and answer. Examples:
# * 2400000 will be answered as "200000"
# * 850000 will be answered as "70833"
'''

# (In Development) # Currency of salaries you mentioned. Companies that allow string inputs will add this tag to the end of numbers. Eg: 
currency = "INR"                 # "USD", "INR", "EUR", etc.

# What is your notice period in days?
notice_period = 30                   # Any number >= 0 without quotes. Eg: 0, 7, 15, 30, 45, etc.
'''
Note: If question has 'month' or 'week' in it (Example: What is your notice period in months), 
then it will divide by 30 or 7 and answer respectively. Examples:
* For notice_period = 66:
  - "66" OR "2" if asked in months OR "9" if asked in weeks
* For notice_period = 15:"
  - "15" OR "0" if asked in months OR "2" if asked in weeks
* For notice_period = 0:
  - "0" OR "0" if asked in months OR "0" if asked in weeks
'''

# Your LinkedIn headline in quotes Eg: "Software Engineer @ Google, Masters in Computer Science", "Recent Grad Student @ MIT, Computer Science"
linkedin_headline = "Software Engineer @ Zyrix.AI | Engineering the Future with Generative & Agentic AI" # "Headline" or "" to leave this question unanswered

# Your summary in quotes, use \n to add line breaks if using single quotes "Summary".You can skip \n if using triple quotes """Summary"""
linkedin_summary = """
Software Engineer specializing in Artificial Intelligence and Machine Learning, with deep expertise in Generative AI and Agentic AI systems. Proven experience designing and developing intelligent AI agents, conversational interfaces, and scalable backend services. Adept at building production-grade AI solutions, optimizing system performance, and delivering high-impact outcomes in dynamic environments. Strong collaborator with a track record of driving end-to-end execution from concept to deployment.

Technical Proficiencies:
Programming & Core Technologies: Python, SQL, Async Programming.
AI/ML & Data Science: Machine Learning, Deep Learning, NLP, Generative AI, LLMs, Model Fine-tuning, Embeddings, Semantic Search.
Backend & API Development: RESTful APIs (FastAPI), Microservices Architecture, Event-Driven Systems, Asynchronous Processing (Celery), Messaging (RabbitMQ), Redis Caching, Scalable Backend Systems.
Agentic AI & Frameworks: LangGraph, LangChain, FastAgent, Google ADK.
Data & Vector Databases: ChromaDB, FAISS, Pinecone, PostgreSQL.
Libraries & Tools: Pandas, NumPy, PySpark, Scikit-learn, TensorFlow, Keras, Transformers, OpenCV, Matplotlib, Seaborn, Playwright, Crawl4AI, Logfire, LLM Instructor.
LLM Ecosystem: OpenAI GPT, Gemini, Anthropic, NVIDIA AI, Hugging Face, Ollama.
Deployment: Docker, CI/CD basics, Monitoring & Logging, API Serving.

Projects:
1. TAP Agents / Test Auto Pilot (Kitap Platform): Architected a scalable Agentic AI-driven multi-agent platform for end-to-end autonomous testing of web applications, reducing manual testing effort by ~80% and human intervention by ~85%.
2. Data Quality Gateway & Data Analytics AI Agents: Built an NLP-powered data analysis agent for natural language querying across relational databases and requirements documents, plus Apache Spark-based large-scale data comparison across Snowflake, MySQL, PostgreSQL, Databricks, and Azure SQL.
3. AI-Powered Face Recognition & PPE/Accident Detection System: Built real-time face recognition, PPE compliance detection, and accident detection with WhatsApp alerting using computer vision and deep learning.

Explore my work on GitHub: github.com/adnanbaig9637
"""

'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Your cover letter in quotes, use \n to add line breaks if using single quotes "Cover Letter".You can skip \n if using triple quotes """Cover Letter""" (This question makes sense though)
cover_letter = """
Cover Letter
"""
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------

# Your user_information_all letter in quotes, use \n to add line breaks if using single quotes "user_information_all".You can skip \n if using triple quotes """user_information_all""" (This question makes sense though)
# We use this to pass to AI to generate answer from information , Assuing Information contians eg: resume  all the information like name, experience, skills, Country, any illness etc. 
user_information_all ="""
Name: Adnan Baig
Title: Associate Software Engineer (AI/ML)
Location: Achalpur, Maharashtra, India (currently based in Hyderabad, India)
Email: adnanbaig2002@gmail.com
Phone: +91 9637641856
LinkedIn: https://linkedin.com/in/adnanbaig2002/
GitHub: https://github.com/adnanbaig9637

Education:
- Bachelor of Engineering (B.E.), PRMITR, Badnera, Amravati, Maharashtra (2020-2023), 82.55%
- Diploma in Engineering, Government College of Polytechnic, Achalpur, Maharashtra (2017-2020), 82.26%
- No Master's degree.

Experience:
- Associate Software Engineer (AI/ML) at Kairos Technologies, Hyderabad, India (08/2024 - Present, ~1 year 10 months). Working on TAP Agents (Kitap Platform) - an AI-powered test automation system using Generative AI and Agentic AI multi-agent architectures, and Data Quality Gateway - data profiling, cleansing, and large-scale row comparison using Apache Spark with multi-database support.
- Data Science Intern at Innomatics Research Labs, Hyderabad, India (01/2024 - 04/2024). Worked on ML models, Generative AI solutions, NLP techniques (sentiment analysis), data preprocessing, EDA, model training and deployment.

Total professional experience: 1 year 10 months (excluding internship).

Skills: Python, SQL, Async Programming, Machine Learning, Deep Learning, NLP, Generative AI, LLMs, Model Fine-tuning, Embeddings, Semantic Search, FastAPI, Microservices, Celery, RabbitMQ, Redis, LangGraph, LangChain, FastAgent, Google ADK, ChromaDB, FAISS, Pinecone, PostgreSQL, Pandas, NumPy, PySpark, Scikit-learn, TensorFlow, Keras, Transformers, OpenCV, Matplotlib, Seaborn, Playwright, Crawl4AI, OpenAI GPT, Gemini, Anthropic, NVIDIA AI, Hugging Face, Ollama, Docker, CI/CD, Git, GitHub.

Certifications: Data Science Professional Certificate (Innomatics Research Labs), Advance ML and Generative AI Internship Program (Innomatics Research Labs), Machine Learning with Python powered by IBM (Innomatics Research Labs), Advance Data Analysis Internship Program (Innomatics Research Labs).

Languages: English, Hindi, Urdu, Marathi.

Work authorization: Indian citizen, does not require visa sponsorship to work in India. Would require sponsorship for roles outside India.

Notice period: 30 days.
Current CTC: 7.3 LPA (INR 730000 per annum).
Expected CTC: 12 LPA (INR 1200000 per annum).
"""


##<
'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Name of your most recent employer
recent_employer = "Zyrix AI" # "", "Lala Company", "Google", "Snowflake", "Databricks"

# Example question: "On a scale of 1-10 how much experience do you have building web or mobile applications? 1 being very little or only in school, 10 being that you have built and launched applications to real users"
confidence_level = "8"             # Any number between "1" to "10" including 1 and 10, put it in quotes ""
##


##> ------ Screening questions (used by Naukri's chatbot, which asks these as plain text) ------

# Your education. Naukri recruiters ask for these constantly.
highest_qualification = "B.E. Computer Science"   # "B.Tech", "B.E.", "MCA", "M.Tech", "B.Sc", etc.
graduation_year = "2023"            # Year you passed out, in quotes Eg: "2023"
graduation_percentage = "82.55"     # Your degree percentage or CGPA, in quotes Eg: "82.55", "8.2"

# Your current employment.
current_company = "Kairos Technologies"          # "" if you are not working right now
current_designation = "Associate Software Engineer (AI/ML)"

# Are you open to moving for a job? Answers "willing to relocate" screeners.
willing_to_relocate = "Yes"         # "Yes" or "No"

# Answer used for yes/no screeners the bot has no specific rule for.
# Most Naukri screeners are "are you willing / are you able / are you comfortable",
# where "Yes" is the answer that keeps your application alive.
default_yes_no_answer = "Yes"       # "Yes" or "No"

# Teach the bot answers for questions it keeps getting wrong.
# Each key is a lowercase phrase to look for in the question, each value is the answer to give.
# The bot checks these FIRST, before all of its built-in rules, and uses the
# LONGEST matching key, so you can override anything here.
# Whenever the log says a question was "unanswerable", add a line here and it is handled forever.
custom_question_answers = {
    # "notice period":                "30 days",
    # "in-person interview":          "Yes",
    # "reason for job change":        "Looking for stronger AI/ML ownership",
    # "how did you hear about us":    "Naukri",
}

# What should the bot do when it truly cannot answer a question?
#   True  = skip the job and record the question in the failed-applications CSV,
#           so you can add it to `custom_question_answers` above. Nothing wrong is submitted.
#   False = submit the application with the question left blank.
# Never guess: guessing is what made every unknown question get answered "2".
skip_job_on_unanswerable_question = True   # True or False, Note: True or False are case-sensitive

# Ask you in the terminal when a question cannot be answered?
# Unlike `pause_at_failed_question` this needs no pop-up window, so it still
# works on machines where Tk / pyautogui dialogs are broken.
ask_in_terminal_on_failed_question = True  # True or False, Note: True or False are case-sensitive
##<



# >>>>>>>>>>> RELATED SETTINGS <<<<<<<<<<<

## Allow Manual Inputs
# Should the tool pause before every submit application during easy apply to let you check the information?
pause_before_submit = False        # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''

# Should the tool pause if it needs help in answering questions during easy apply?
# Note: If set as False will answer randomly...
pause_at_failed_question = True    # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
##

# Do you want to overwrite previous answers?
overwrite_previous_answers = False # True or False, Note: True or False are case-sensitive







############################################################################################################
'''
THANK YOU for using my tool 😊! Wishing you the best in your job hunt 🙌🏻!

Sharing is caring! If you found this tool helpful, please share it with your peers 🥺. Your support keeps this project alive.

Support my work on <PATREON_LINK>. Together, we can help more job seekers.

As an independent developer, I pour my heart and soul into creating tools like this, driven by the genuine desire to make a positive impact.

Your support, whether through donations big or small or simply spreading the word, means the world to me and helps keep this project alive and thriving.

Gratefully yours 🙏🏻,
Sai Vignesh Golla
'''
############################################################################################################
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


###################################################### LINKEDIN SEARCH PREFERENCES ######################################################

# These Sentences are Searched in LinkedIn
# Enter your search terms inside '[ ]' with quotes ' "searching title" ' for each search followed by comma ', ' Eg: ["Software Engineer", "Software Developer", "Selenium Developer"]
search_terms = ["AI/ML Engineer", "Python Developer", "AI Engineer", "Agentic AI Developer", "AI Developer", "AI Backend Developer", "Gen AI Developer", "Gen AI Engineer", "Agentic AI Engineer"]

# Search location, this will be filled in "City, state, or zip code" search box. If left empty as "", tool will not fill it.
search_location = "India"               # Some valid examples: "", "United States", "India", "Chicago, Illinois, United States", "90001, Los Angeles, California, United States", "Bengaluru, Karnataka, India", etc.

# After how many number of applications in current search should the bot switch to next search? 
switch_number = 30                 # Only numbers greater than 0... Don't put in quotes

# Do you want to randomize the search order for search_terms?
randomize_search_order = False     # True of False, Note: True or False are case-sensitive


# >>>>>>>>>>> Job Search Filters <<<<<<<<<<<
''' 
You could set your preferences or leave them as empty to not select options except for 'True or False' options. Below are some valid examples for leaving them empty:
This is below format: QUESTION = VALID_ANSWER

## Examples of how to leave them empty. Note that True or False options cannot be left empty! 
* question_1 = ""                    # answer1, answer2, answer3, etc.
* question_2 = []                    # (multiple select)
* question_3 = []                    # (dynamic multiple select)

## Some valid examples of how to answer questions:
* question_1 = "answer1"                  # "answer1", "answer2", "answer3" or ("" to not select). Answers are case sensitive.
* question_2 = ["answer1", "answer2"]     # (multiple select) "answer1", "answer2", "answer3" or ([] to not select). Note that answers must be in [] and are case sensitive.
* question_3 = ["answer1", "Random AnswER"]     # (dynamic multiple select) "answer1", "answer2", "answer3" or ([] to not select). Note that answers must be in [] and need not match the available options.

'''

sort_by = "Most recent"                       # "Most recent", "Most relevant" or ("" to not select) 
date_posted = "Past week"         # "Any time", "Past month", "Past week", "Past 24 hours" or ("" to not select)
salary = ""                              # "$40,000+", "$60,000+", "$80,000+", "$100,000+", "$120,000+", "$140,000+", "$160,000+", "$180,000+", "$200,000+"

easy_apply_only = True             # True or False, Note: True or False are case-sensitive

experience_level = ["Entry level", "Associate", "Mid-Senior level"]              # (multiple select) "Internship", "Entry level", "Associate", "Mid-Senior level", "Director", "Executive"
job_type = ["Full-time"]                      # (multiple select) "Full-time", "Part-time", "Contract", "Temporary", "Volunteer", "Internship", "Other"
on_site = ["Remote", "Hybrid"]                       # (multiple select) "On-site", "Remote", "Hybrid"

companies = []                     # (dynamic multiple select) make sure the name you type in list exactly matches with the company name you're looking for, including capitals. 
                                   # Eg: "7-eleven", "Google","X, the moonshot factory","YouTube","CapitalG","Adometry (acquired by Google)","Meta","Apple","Byte Dance","Netflix", "Snowflake","Mineral.ai","Microsoft","JP Morgan","Barclays","Visa","American Express", "Snap Inc", "JPMorgan Chase & Co.", "Tata Consultancy Services", "Recruiting from Scratch", "Epic", and so on...
location = []                      # (dynamic multiple select)
industry = []                      # (dynamic multiple select)
job_function = []                  # (dynamic multiple select)
job_titles = []                    # (dynamic multiple select)
benefits = []                      # (dynamic multiple select)
commitments = []                   # (dynamic multiple select)

under_10_applicants = False        # True or False, Note: True or False are case-sensitive
in_your_network = False            # True or False, Note: True or False are case-sensitive
fair_chance_employer = False       # True or False, Note: True or False are case-sensitive


## >>>>>>>>>>> RELATED SETTING <<<<<<<<<<<

# Pause after applying filters to let you modify the search results and filters?
pause_after_filters = True         # True or False, Note: True or False are case-sensitive

##




## >>>>>>>>>>> SKIP IRRELEVANT JOBS <<<<<<<<<<<
 
# Avoid applying to these companies, and companies with these bad words in their 'About Company' section...
about_company_bad_words = ["Crossover"]       # (dynamic multiple search) or leave empty as []. Ex: ["Staffing", "Recruiting", "Name of Company you don't want to apply to"]

# Skip checking for `about_company_bad_words` for these companies if they have these good words in their 'About Company' section... [Exceptions, For example, I want to apply to "Robert Half" although it's a staffing company]
about_company_good_words = []      # (dynamic multiple search) or leave empty as []. Ex: ["Robert Half", "Dice"]

# Avoid applying to these companies if they have these bad words in their 'Job Description' section...  (In development)
bad_words = ["US Citizen","USA Citizen","No C2C", "No Corp2Corp", ".NET", "Embedded Programming", "PHP", "Ruby", "CNC"]                     # (dynamic multiple search) or leave empty as []. Case Insensitive. Ex: ["word_1", "phrase 1", "word word", "polygraph", "US Citizenship", "Security Clearance"]

# Do you have an active Security Clearance? (True for Yes and False for No)
security_clearance = False         # True or False, Note: True or False are case-sensitive

# Do you have a Masters degree? (True for Yes and False for No). If True, the tool will apply to jobs containing the word 'master' in their job description and if it's experience required <= current_experience + 2 and current_experience is not set as -1. 
did_masters = False                 # True or False, Note: True or False are case-sensitive

# Avoid applying to jobs if their required experience is above your current_experience. (Set value as -1 if you want to apply to all ignoring their required experience...)
current_experience = 2             # Integers > -2 (Ex: -1, 0, 1, 2, 3, 4...)
##




## >>>>>>>>>>> NAUKRI JOB RELEVANCE FILTER <<<<<<<<<<<
"""
Naukri's keyword search is much looser than LinkedIn's -- searching "AI Engineer"
genuinely returns .NET, QA and support roles. These settings add a POSITIVE gate
on top of the negative `bad_words` screening above: a job must look like a role
you actually want before the bot applies to it.

Only `runNaukriBot.py` reads these. LinkedIn (`runAiBot.py`) is unaffected.
Leave any list empty as [] to switch that rule off.

Matching is whole-term and case-insensitive, so "AI" matches "AI/ML Engineer"
and "AI-driven" but NOT "chair" or "maintain".
"""

# The job TITLE must contain at least one of these, or the job is skipped.
# This is the main fix for "it applies to any job".
naukri_required_title_words = [
    "AI", "A.I.", "ML", "AI/ML", "Machine Learning", "Artificial Intelligence",
    "Deep Learning", "Generative AI", "GenAI", "Gen AI", "LLM", "Agentic",
    "NLP", "Natural Language", "Computer Vision", "MLOps",
    "Data Scientist", "Data Science",
    "Python", "Backend Engineer", "Backend Developer",
]

# Reject the job if its TITLE contains any of these, even if it matched above.
naukri_excluded_title_words = [
    ".NET", "Dot Net", "DotNet", "C#", "Java", "J2EE", "Spring Boot",
    "PHP", "Ruby", "Golang", "Scala", "Perl", "COBOL", "Mainframe",
    "Tester", "Testing", "QA", "Quality Assurance", "SDET", "Manual Test",
    "Automation Test", "Test Engineer", "Test Analyst",
    "Frontend", "Front End", "React", "Angular", "Vue", "UI/UX", "UX", "Designer",
    "Android", "iOS", "Flutter", "React Native", "Mobile",
    "DevOps", "SRE", "Network", "System Admin", "Sysadmin", "Desktop Support",
    "Salesforce", "SAP", "ServiceNow", "Sharepoint", "Oracle", "Workday",
    "Business Analyst", "Sales", "Marketing", "Recruiter", "HR", "Accountant",
    "Support Engineer", "Technical Support", "Customer Support", "BPO",
    "Intern", "Internship", "Fresher", "Trainee", "Teacher", "Trainer", "Faculty",
    "Data Entry", "Content Writer", "Embedded", "Firmware", "VLSI", "CNC",
]

# The job must mention at least `naukri_min_skill_matches` of these skills in its
# title or description. This catches roles with a plausible title but unrelated content.
naukri_required_skills = [
    "Python", "Machine Learning", "Deep Learning", "NLP", "Generative AI", "GenAI",
    "LLM", "LLMs", "Large Language Model", "Agentic", "AI Agent", "LangChain",
    "LangGraph", "RAG", "Retrieval Augmented", "Embedding", "Embeddings",
    "Vector Database", "ChromaDB", "FAISS", "Pinecone", "Transformers",
    "Hugging Face", "OpenAI", "GPT", "Gemini", "Anthropic", "Ollama",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy", "PySpark",
    "Computer Vision", "OpenCV", "FastAPI", "Prompt Engineering", "Fine-tuning",
    "Artificial Intelligence", "Data Science", "MLOps", "Model Deployment",
]

# How many of the skills above must appear. Raise it to be stricter, set 0 to disable.
naukri_min_skill_matches = 1       # Only non-negative numbers... Don't put in quotes
"""
Why 1 and not 2: the title gate above is already strict, so this rule is a
safety net rather than the main filter. At 2, a genuine "Python Developer" role
whose description happens to name only Python (and no second listed skill) gets
rejected. Raise it to 2 or 3 if you want strictly AI-specific roles, and accept
that some plain Python roles will be filtered out.
"""
##






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
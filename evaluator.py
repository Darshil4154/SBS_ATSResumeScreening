import json
import os
import re
import time
import concurrent.futures
from openai import OpenAI

CRITERIA_ORDER = [
    'project_management', 'software_testing_erp', 'reports_sql',
    'sis_business_processes_ar', 'process_improvement', 'reconciling_accounts',
    'gaap_financial_mgmt', 'federal_state_compliance', 'budget_financial_analysis',
    'communication_executive_presence', 'sop_documentation',
    'vendor_stakeholder_coordination', 'education_match', 'experience_match',
]

CRITERIA_LABELS = {
    'project_management': 'Project Management',
    'software_testing_erp': 'Software Testing/ERP Implementation',
    'reports_sql': 'Creating Reports/SQL',
    'sis_business_processes_ar': 'SIS Business Processes in AR',
    'process_improvement': 'Process Improvement',
    'reconciling_accounts': 'Reconciling Accounts',
    'gaap_financial_mgmt': 'GAAP & Financial Mgmt',
    'federal_state_compliance': 'Federal/State Compliance',
    'budget_financial_analysis': 'Budget & Financial Analysis',
    'communication_executive_presence': 'Communication & Exec Presence',
    'sop_documentation': 'SOP & Documentation',
    'vendor_stakeholder_coordination': 'Vendor & Stakeholder Coord',
    'education_match': 'Education Match',
    'experience_match': 'Experience Match',
}


def _get_client():
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"]
    )


def build_prompt(jd_text, resume_text):
    return f"""You are a generous but fair HR professional at Texas A&M University evaluating resumes for the FBS Senior Analyst position. Your goal is to FIND REASONS TO GIVE POINTS, not find reasons to take them away. You want to identify the best candidates from a pool — so score generously where evidence exists.

=== JOB DESCRIPTION ===
{jd_text}

=== RESUME ===
{resume_text}

=== SCORING PHILOSOPHY ===
Think like a real HR person doing a resume screen — NOT like a keyword-matching robot.

USE SEMANTIC MATCHING — these are the same thing:
- "Financial reporting" = "Creating Reports" = "Management reports" = "Data analysis" → all count for Reports/SQL
- "Month-end close" = "Account reconciliation" = "GL reconciliation" = "Balance sheet review" → all count for Reconciling Accounts
- "Coordinated with teams" = "Managed stakeholders" = "Liaised between departments" → counts for Vendor & Stakeholder
- "Developed procedures" = "Created documentation" = "Wrote guidelines" = "Training materials" → counts for SOP & Documentation
- "Ensured compliance" = "Regulatory adherence" = "Policy interpretation" = "Audit support" → counts for Federal/State Compliance
- "Led initiatives" = "Drove improvements" = "Streamlined processes" = "Increased efficiency" → counts for Process Improvement
- "Managed budgets" = "Financial planning" = "Forecast" = "Variance analysis" = "Cost management" → counts for Budget & Financial Analysis
- Anyone who worked as an Accountant, Financial Analyst, or Business Analyst for years IMPLICITLY has GAAP knowledge, financial management skills, communication skills, and reconciliation experience — score 5-7 minimum for those even without explicit mention.

SCORING SCALE — BE GENEROUS WHERE FAIR:
- 0-2: Truly nothing related anywhere in the resume
- 3-4: Weak but some tangential connection exists
- 5-6: Moderate — relevant experience exists, not perfectly aligned but clearly capable
- 7-8: Strong — clear direct experience, multiple touch points
- 9-10: Exceptional — deep, extensive, perfectly matching

RULES:
- The AVERAGE candidate in this pool should score around 60-80 out of 140. If your scores are lower, you are being too strict.
- A Financial Analyst with 5+ years experience should score at LEAST 5/10 on most financial criteria.
- Read EVERY section: summary, all jobs, skills, education, certifications. Don't skip older roles.
- University/higher-ed experience = +1 bonus on relevant criteria.
- Give partial credit generously. If someone has "some" experience, that's a 5-6, not a 2-3.

JUSTIFICATION FORMAT — MUST follow this exact structure for EVERY criterion:
"FOUND: [list what you found in the resume relevant to this criterion — quote specific bullet points, job titles, companies].
POINTS GIVEN: +X for [reason], +X for [reason], +X for [reason].
POINTS REDUCED: -X because [what's missing or weak], -X because [another gap].
FINAL: [score]/10."
Example: "FOUND: Candidate worked as Financial Analyst at CitiusTech where they 'prepared monthly variance reports' and 'managed budget forecasts.' Also lists SQL and Excel under skills. POINTS GIVEN: +3 for financial reporting at CitiusTech, +2 for SQL skill listed, +2 for Excel/data analysis. POINTS REDUCED: -2 no mention of student information system queries, -1 no database application experience mentioned. FINAL: 7/10."

RED FLAGS INSTRUCTIONS (do NOT copy these instructions into the output — write actual findings):
- Check if candidate has less than 6 years relevant experience. If so, write something like "Only 3 years of relevant experience (requires 6)."
- Check if degree is unrelated. If so, write "Degree in [field] — not directly in accounting/business/finance."
- Check for employment gaps over 6 months. If found, write "Employment gap from [date] to [date]."
- Check if they lack required KSAs. Write which specific ones are missing.
- Check if no higher-ed/university work experience. Write "No university/higher education work experience."
- If nothing concerning, return an empty list [].

Return ONLY valid JSON — no markdown backticks, no extra text:
{{
  "candidate_name": "full name from resume",
  "candidate_email": "email from resume or null",
  "scores": {{
    "project_management": {{
      "score": 0,
      "justification": "detailed evidence-based justification with point breakdown",
      "keywords_found": ["project management terms found in resume"],
      "keywords_missing": ["terms searched for but not found"]
    }},
    "software_testing_erp": {{
      "score": 0,
      "justification": "Look for: ERP systems (Banner, PeopleSoft, Workday, SAP, Oracle), software testing, UAT, system implementations, software coordination",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "reports_sql": {{
      "score": 0,
      "justification": "Look for: SQL, reporting, data analysis, queries, Excel reporting, database, data extraction, financial reports, management reports",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "sis_business_processes_ar": {{
      "score": 0,
      "justification": "Look for: student information systems, accounts receivable, student accounts, tuition, billing, cashiering, collections, bursar",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "process_improvement": {{
      "score": 0,
      "justification": "Look for: process improvement, workflow optimization, efficiency, automation, streamlining, lean, six sigma, redesign",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "reconciling_accounts": {{
      "score": 0,
      "justification": "Look for: reconciliation, account reconciliation, auditing transactions, ledger balancing, month-end close, bank reconciliation, GL",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "gaap_financial_mgmt": {{
      "score": 0,
      "justification": "Look for: GAAP, accounting principles, financial management, financial statements, general ledger, journal entries, accruals. Anyone with accounting job titles likely has this.",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "federal_state_compliance": {{
      "score": 0,
      "justification": "Look for: compliance, regulations, federal reporting, state reporting, audit, regulatory, policies, tax compliance, SOX",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "budget_financial_analysis": {{
      "score": 0,
      "justification": "Look for: budget, financial analysis, forecasting, variance analysis, financial planning, cost analysis, budget preparation",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "communication_executive_presence": {{
      "score": 0,
      "justification": "Look for: communication skills, presentations, executive reporting, stakeholder communication, cross-functional teams, customer service, training others",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "sop_documentation": {{
      "score": 0,
      "justification": "Look for: SOPs, documentation, procedures, process documentation, training materials, policy writing, job aids, manuals",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "vendor_stakeholder_coordination": {{
      "score": 0,
      "justification": "Look for: vendor management, stakeholder coordination, liaison, cross-department, external relationships, vendor relations, contract management",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "education_match": {{
      "score": 0,
      "justification": "State exact degree, field, school, year. Score: 10=Accounting/Finance degree, 8-9=Business/Economics/MIS, 7=other related, 5-6=unrelated bachelor's with strong experience, 3-4=some college, 0-2=no degree info. Master's/MBA = +1 bonus.",
      "keywords_found": [],
      "keywords_missing": []
    }},
    "experience_match": {{
      "score": 0,
      "justification": "List EVERY relevant role with years. Sum total. Score: 10=8+ years relevant, 8-9=6-8 years, 6-7=4-6 years, 4-5=2-4 years, 2-3=1-2 years, 0-1=none. Count financial analyst, accountant, business analyst, budget roles as relevant.",
      "keywords_found": [],
      "keywords_missing": []
    }}
  }},
  "application_score": 0,
  "recommendation": "STRONG HIRE or RECOMMEND INTERVIEW or MAYBE or PASS",
  "overall_summary": "5-6 sentence hiring manager assessment covering fit, strengths, gaps, and interview recommendation.",
  "red_flags": ["Example: Less than 6 years relevant experience (has only 3 years)", "Example: No higher education experience", "Example: Degree in unrelated field (Biology)"],
  "top_strengths": ["Strength with specific evidence from resume", "Second strength with evidence", "Third strength with evidence"]
}}"""


def parse_response(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    attempts = [text]
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        attempts.append(match.group(0))
    for raw in list(attempts):
        attempts.append(re.sub(r'\\(?!["\\/bfnrtu])', '', raw))

    for a in attempts:
        try:
            data = json.loads(a)
            total = sum(int(data.get('scores', {}).get(k, {}).get('score', 0)) for k in CRITERIA_ORDER)
            data['application_score'] = total
            return data
        except Exception:
            continue
    raise ValueError("JSON parse failed")


def evaluate_resume(jd_text, resume_text):
    client = _get_client()
    prompt = build_prompt(jd_text, resume_text)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=5000
            )
            result = parse_response(response.choices[0].message.content)
            print(f"  -> {result.get('candidate_name','?')}: {result['application_score']}/140", flush=True)
            return result
        except ValueError:
            if attempt < 2:
                time.sleep(1)
                continue
            raise
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise
    raise Exception("Failed after 3 attempts")


def chat_answer(question, all_candidates_data):
    client = _get_client()

    context = "You are an AI assistant for a hiring manager at Texas A&M University Student Business Services reviewing candidates for the FBS Senior Analyst position. You have full evaluation data for all candidates. Give specific, detailed answers with scores, evidence, and clear comparisons when asked.\n\nCANDIDATE DATA:\n\n"
    for c in all_candidates_data:
        scores = c.get('scores', {})
        context += f"\n--- {c['candidate_name']} (Total: {c['application_score']}/140, Email: {c.get('candidate_email', 'N/A')}) ---\n"
        context += f"Summary: {c.get('overall_summary', 'N/A')}\n"
        context += f"Strengths: {', '.join(c.get('top_strengths', []))}\n"
        flags = c.get('red_flags', [])
        context += f"Red Flags: {', '.join(flags) if flags else 'None'}\n"
        for key in CRITERIA_ORDER:
            s = scores.get(key, {})
            context += f"  {CRITERIA_LABELS[key]}: {s.get('score', 0)}/10 — {s.get('justification', 'N/A')}\n"

    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": question}
        ],
        temperature=0.2,
        max_tokens=3000
    )
    return response.choices[0].message.content

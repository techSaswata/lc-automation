#!/usr/bin/env python3
"""
LeetCode Daily Auto Solver - Local Mac Version
Runs when Mac opens, retries until success for the day
"""

import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Configuration - Load from environment or keys.md
SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / ".daily_success.json"

# Load credentials (you can set these as environment variables)
LEETCODE_SESSION = os.environ.get("LEETCODE_SESSION", "")
LEETCODE_CSRF = os.environ.get("LEETCODE_CSRF", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = os.environ.get("SMTP_PORT", "587")


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "Origin": "https://leetcode.com",
}

cookies = {
    "LEETCODE_SESSION": LEETCODE_SESSION,
    "csrftoken": LEETCODE_CSRF
}

if LEETCODE_CSRF:
    headers["X-CSRFToken"] = LEETCODE_CSRF


# ---------------------------
# State Management
# ---------------------------
def load_state():
    """Load success state from file"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_state(date_str, success=False):
    """Save success state for today"""
    state = {
        "date": date_str,
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def should_run_today():
    """Check if we need to run today"""
    today = datetime.now().strftime("%Y-%m-%d")
    state = load_state()
    
    # If no state, or different date, or not successful yet - run
    if not state:
        return True
    if state.get("date") != today:
        return True
    if not state.get("success"):
        return True
    
    return False


# ---------------------------
# 1. Fetch Daily Problem
# ---------------------------
def get_daily_challenge():
    url = "https://leetcode.com/graphql"
    query = {
        "query": """
        query questionOfToday {
          activeDailyCodingChallengeQuestion {
            date
            question {
              title
              titleSlug
              content
              codeSnippets {
                lang
                code
              }
            }
          }
        }
        """
    }

    res = requests.post(url, json=query, headers=headers, cookies=cookies)
    
    if res.status_code != 200:
        raise Exception(f"Failed to fetch problem: HTTP {res.status_code}")
    
    data = res.json()["data"]["activeDailyCodingChallengeQuestion"]
    q = data["question"]

    # Extract Java template
    java_template = ""
    for snip in q["codeSnippets"]:
        if snip["lang"] == "Java":
            java_template = snip["code"]

    return q["title"], q["titleSlug"], q["content"], java_template, data["date"]


def html_to_text(html):
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text()


# ---------------------------
# 2. Gemini Code Generation
# ---------------------------
def generate_code(problem_text, java_template):
    genai.configure(api_key=GEMINI_API_KEY)

    system_prompt = """
You are a competitive programming expert.
You must return ONLY valid Java code with STRICTLY NO COMMENTS.
Use the given Java template and fill in the solution logic.
"""

    final_prompt = f"""
{system_prompt}

Problem Description:
{problem_text}

Java Boilerplate:
{java_template}

Return only valid Java code, no comments, no explanations.
"""

    model = genai.GenerativeModel(
        "gemini-2.0-flash-exp",
        generation_config={
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
    )
    
    result = model.generate_content(final_prompt)
    code = result.text.strip()

    # Clean up markdown
    if code.startswith("```"):
        code = code.split("```")[1]
        if code.startswith("java"):
            code = code[len("java"):].strip()

    return code.strip()


# ---------------------------
# 3. Submit to LeetCode
# ---------------------------
def submit_solution(slug, code):
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update(headers)
    
    # Visit problem page
    problem_url = f"https://leetcode.com/problems/{slug}/"
    session.get(problem_url)
    
    time.sleep(2)
    
    # Submit
    submit_url = f"https://leetcode.com/problems/{slug}/submit/"
    payload = {
        "lang": "java",
        "question_id": slug,
        "typed_code": code
    }

    res = session.post(submit_url, json=payload)
    
    if res.status_code != 200:
        raise Exception(f"Submit failed: HTTP {res.status_code}")
    
    response_data = res.json()
    
    if "submission_id" in response_data:
        return response_data["submission_id"]
    elif "interpret_id" in response_data:
        return response_data["interpret_id"]
    else:
        raise Exception(f"No submission ID in response")


def check_status(submission_id):
    url = f"https://leetcode.com/submissions/detail/{submission_id}/check/"
    timeout = 60
    start_time = time.time()
    
    while True:
        if time.time() - start_time > timeout:
            return {"state": "TIMEOUT", "status_msg": "Timeout"}
            
        try:
            res = requests.get(url, headers=headers, cookies=cookies).json()
            if res["state"] == "SUCCESS":
                return res
        except:
            pass
            
        time.sleep(2)


# ---------------------------
# 4. Save and Commit
# ---------------------------
def save_solution(date_str, title, slug, code):
    date_obj = datetime.strptime(date_str.replace("-", ""), "%Y%m%d")
    formatted_date = date_obj.strftime("%b%d-%y")
    filename = SCRIPT_DIR / f"leetcode-{formatted_date}.java"
    
    with open(filename, "w") as f:
        f.write(code)
    
    # Git commit
    os.system(f"cd {SCRIPT_DIR} && git add {filename} && git commit -m 'Add accepted LeetCode solution: {title}' && git push")
    
    return str(filename)


# ---------------------------
# 5. Email
# ---------------------------
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT))
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Email failed: {e}")


# ---------------------------
# MAIN
# ---------------------------
def main():
    print("=" * 60)
    print("LeetCode Daily Auto Solver - Local Mac Version")
    print("=" * 60)
    
    # Check if we need to run today
    if not should_run_today():
        print("✓ Already completed today! Exiting.")
        return
    
    print("\n[1/6] Fetching daily challenge...")
    try:
        title, slug, html, java_template, date = get_daily_challenge()
        print(f"✓ Problem: {title}")
        print(f"✓ Date: {date}")
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        problem_text = html_to_text(html).strip()
        date_clean = date.replace("-", "")
        
        print(f"\n[2/6] Generating code...")
        code = generate_code(problem_text, java_template)
        print(f"✓ Code generated ({len(code)} chars)")
        
        print(f"\n[3/6] Submitting to LeetCode...")
        submission_id = submit_solution(slug, code)
        print(f"✓ Submission ID: {submission_id}")
        
        print(f"\n[4/6] Checking status...")
        result = check_status(submission_id)
        status = result.get("status_msg", "Unknown")
        print(f"Result: {status}")
        
        if status == "Accepted":
            print(f"\n[5/6] ✓ ACCEPTED! Saving solution...")
            filename = save_solution(date_clean, title, slug, code)
            print(f"✓ Saved as: {filename}")
            
            print(f"[6/6] Sending email...")
            send_email(
                f"✓ LeetCode Daily Accepted: {title}",
                f"Your solution for {title} was Accepted!\n\nSaved as {filename}."
            )
            
            # Mark as successful
            save_state(today, success=True)
            print("\n✓ SUCCESS! Marked as complete for today.")
        else:
            print(f"\n✗ {status} - Will retry on next Mac open")
            save_state(today, success=False)
            send_email(
                f"✗ LeetCode Daily Failed: {title}",
                f"Attempt failed with {status}. Will retry when Mac opens again."
            )
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("Will retry on next Mac open")
        today = datetime.now().strftime("%Y-%m-%d")
        save_state(today, success=False)


if __name__ == "__main__":
    main()


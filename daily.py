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


LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
LEETCODE_CSRF = os.environ.get("LEETCODE_CSRF", "")
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
EMAIL_TO = os.environ["EMAIL_TO"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = os.environ.get("SMTP_PORT", "587")


headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "Origin": "https://leetcode.com",
}

cookies = {
    "LEETCODE_SESSION": LEETCODE_SESSION,
    "csrftoken": LEETCODE_CSRF
}

# Add CSRF to headers if available
if LEETCODE_CSRF:
    headers["X-CSRFToken"] = LEETCODE_CSRF


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
              exampleTestcases
              difficulty
              stats
            }
          }
        }
        """
    }

    res = requests.post(url, json=query, headers=headers, cookies=cookies)
    data = res.json()["data"]["activeDailyCodingChallengeQuestion"]
    q = data["question"]

    # Extract Java template
    java_template = ""
    for snip in q["codeSnippets"]:
        if snip["lang"] == "Java":
            java_template = snip["code"]

    return q["title"], q["titleSlug"], q["content"], java_template, data["date"]


# Clean HTML → plain text
def html_to_text(html):
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text()


# ---------------------------
# 2. Gemini Code Generation (Using latest Gemini 2.0 Pro with Thinking)
# ---------------------------
def generate_code(problem_text, java_template):
    genai.configure(api_key=GEMINI_API_KEY)

    system_prompt = """
You are a competitive programming expert.
You must return ONLY valid Java code with STRICTLY NO COMMENTS.
Use this format:
- Use the given Java template
- Fill solve logic exactly
- Think deeply about edge cases and optimal solutions
- Return clean, efficient, working code
"""

    final_prompt = f"""
{system_prompt}

Problem Description:
{problem_text}

Java Boilerplate:
{java_template}

Constraints and Instructions:
Strictly no comments. Only valid Java code.
Analyze the problem carefully and provide an optimal solution.
"""

    # Use the latest Gemini 2.0 Pro model with thinking capabilities
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

    # Clean up markdown code blocks if present
    if code.startswith("```"):
        code = code.split("```")[1]
        if code.startswith("java"):
            code = code[len("java"):].strip()
        code = code.strip()
    
    # If there are multiple code blocks, take the last one
    if "```" in code:
        parts = code.split("```")
        for part in reversed(parts):
            if "class Solution" in part or "public" in part:
                code = part.strip()
                break

    return code.strip()


# ---------------------------
# 3. Submit to LeetCode
# ---------------------------
def submit_solution(slug, code):
    url = "https://leetcode.com/graphql"

    payload = {
        "query": """
        mutation submitSolution($input: SubmitInput!) {
          submitSolution(input: $input) {
            submissionId
          }
        }
        """,
        "variables": {
            "input": {
                "questionSlug": slug,
                "lang": "java",
                "code": code
            }
        }
    }

    res = requests.post(url, headers=headers, cookies=cookies, json=payload)
    
    # Debug: print response
    print(f"Response status: {res.status_code}")
    print(f"Response text: {res.text[:500]}")  # First 500 chars
    
    response_data = res.json()
    
    if "errors" in response_data:
        raise Exception(f"LeetCode API Error: {response_data['errors']}")
    
    if "data" not in response_data or response_data["data"] is None:
        raise Exception(f"Invalid response from LeetCode: {response_data}")
    
    return response_data["data"]["submitSolution"]["submissionId"]


# Poll result
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
# 4. Save solution on success
# ---------------------------
def save_solution(date_str, title, slug, code):
    # Format: leetcode-Dec08-25.java
    date_obj = datetime.strptime(date_str, "%Y%m%d")
    formatted_date = date_obj.strftime("%b%d-%y")
    filename = f"leetcode-{formatted_date}.java"
    
    with open(filename, "w") as f:
        f.write(code)
    
    return filename


# ---------------------------
# 5. Email Notification
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
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


# ---------------------------
# MAIN FLOW WITH RETRY
# ---------------------------
def main():
    print("=" * 60)
    print("LeetCode Daily Auto Solver - Starting")
    print("=" * 60)
    
    print("\n[1/6] Fetching daily challenge...")
    title, slug, html, java_template, date = get_daily_challenge()
    
    print(f"✓ Problem: {title}")
    print(f"✓ Slug: {slug}")
    print(f"✓ Date: {date}")

    problem_text = html_to_text(html).strip()
    date_clean = date.replace("-", "")

    print(f"\n[2/6] Generating code using Gemini 2.0 Pro with Thinking...")
    attempts = 0
    max_attempts = 5

    while attempts < max_attempts:
        attempts += 1
        print(f"\n--- Attempt {attempts}/{max_attempts} ---")

        try:
            code = generate_code(problem_text, java_template)
            print(f"✓ Code generated ({len(code)} chars)")
            
            print(f"[3/6] Submitting to LeetCode...")
            submission_id = submit_solution(slug, code)
            print(f"✓ Submission ID: {submission_id}")
            
            print(f"[4/6] Checking status...")
            result = check_status(submission_id)

            status = result.get("status_msg", "Unknown")
            print(f"Result: {status}")

            if status == "Accepted":
                print(f"\n[5/6] ✓ ACCEPTED! Saving solution...")
                filename = save_solution(date_clean, title, slug, code)
                print(f"✓ Saved as: {filename}")
                
                print(f"[6/6] Sending email notification...")
                send_email(
                    f"✓ LeetCode Daily Accepted: {title}",
                    f"Your solution for {title} ({slug}) was Accepted!\n\nSaved as {filename}.\n\nSubmission ID: {submission_id}"
                )
                
                print("\n" + "=" * 60)
                print("SUCCESS! Task completed.")
                print("=" * 60)
                return
            else:
                print(f"✗ {status} - Retrying...")
                
        except Exception as e:
            print(f"✗ Error: {e}")

    # After all attempts failed
    print(f"\n[6/6] Sending failure notification...")
    send_email(
        f"✗ LeetCode Daily FAILED: {title}",
        f"All {max_attempts} attempts failed for {title} ({slug}).\n\nPlease check the GitHub Actions logs for details."
    )
    
    print("\n" + "=" * 60)
    print("FAILED - All attempts exhausted")
    print("=" * 60)


if __name__ == "__main__":
    main()


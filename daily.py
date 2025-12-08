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
PROXY_API_KEY = os.environ.get("PROXY_API_KEY", "")  # ScraperAPI key (optional)


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "Origin": "https://leetcode.com",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

cookies = {
    "LEETCODE_SESSION": LEETCODE_SESSION,
    "csrftoken": LEETCODE_CSRF
}

# Add CSRF to headers if available
if LEETCODE_CSRF:
    headers["X-CSRFToken"] = LEETCODE_CSRF
    headers["x-csrftoken"] = LEETCODE_CSRF


# ---------------------------
# Proxy Configuration
# ---------------------------
def make_request_with_proxy(method, url, **kwargs):
    """Make request through ScraperAPI if key is available"""
    if PROXY_API_KEY:
        # Use ScraperAPI's correct format
        api_url = 'https://api.scraperapi.com/'
        params = kwargs.pop('params', {})
        params['api_key'] = PROXY_API_KEY
        params['url'] = url
        
        if method.upper() == 'GET':
            return requests.get(api_url, params=params, **kwargs)
        elif method.upper() == 'POST':
            # For POST, send data to the target URL via ScraperAPI
            params['method'] = 'POST'
            # ScraperAPI handles POST differently
            return requests.post(api_url, params=params, **kwargs)
    else:
        # No proxy, direct request
        if method.upper() == 'GET':
            return requests.get(url, **kwargs)
        elif method.upper() == 'POST':
            return requests.post(url, **kwargs)


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

    if PROXY_API_KEY:
        print("Using ScraperAPI...")
    
    res = make_request_with_proxy('POST', url, json=query, headers=headers, cookies=cookies)
    
    # Better error handling
    if res.status_code != 200:
        print(f"Error fetching problem: {res.status_code}")
        print(f"Response: {res.text[:500]}")
        raise Exception(f"Failed to fetch daily problem: HTTP {res.status_code}")
    
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
    # Create a session to maintain cookies
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update(headers)
    
    if PROXY_API_KEY:
        print("Using ScraperAPI for submission...")
    
    # First, visit the problem page to get fresh CSRF token
    problem_url = f"https://leetcode.com/problems/{slug}/"
    print(f"Visiting problem page: {problem_url}")
    
    page_response = make_request_with_proxy('GET', problem_url)
    
    if page_response.status_code != 200:
        print(f"Warning: Problem page returned {page_response.status_code}")
    
    # Extract CSRF token from cookies (get the most recent one)
    csrf_token = None
    for cookie in session.cookies:
        if cookie.name == 'csrftoken':
            csrf_token = cookie.value
            break
    
    if not csrf_token:
        csrf_token = LEETCODE_CSRF
    
    if csrf_token:
        session.headers['X-CSRFToken'] = csrf_token
        session.headers['Referer'] = problem_url
        print(f"Got CSRF token: {csrf_token[:20]}...")
    
    # Small delay to avoid rate limiting
    time.sleep(5)
    
    # Use the direct submission API endpoint
    submit_url = f"https://leetcode.com/problems/{slug}/submit/"
    
    payload = {
        "lang": "java",
        "question_id": slug,
        "typed_code": code
    }

    res = make_request_with_proxy('POST', submit_url, json=payload)
    
    # Debug: print response
    print(f"Response status: {res.status_code}")
    
    if res.status_code != 200:
        print(f"Response text: {res.text[:500]}")
        raise Exception(f"HTTP {res.status_code}: {res.text[:200]}")
    
    response_data = res.json()
    print(f"Response: {response_data}")
    
    if "submission_id" in response_data:
        return response_data["submission_id"]
    elif "interpret_id" in response_data:
        return response_data["interpret_id"]
    else:
        raise Exception(f"No submission ID in response: {response_data}")


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
    max_attempts = 3  # Reduce to avoid rate limiting

    while attempts < max_attempts:
        attempts += 1
        print(f"\n--- Attempt {attempts}/{max_attempts} ---")

        # Add delay between attempts
        if attempts > 1:
            wait_time = 15 * attempts
            print(f"Waiting {wait_time}s to avoid rate limit...")
            time.sleep(wait_time)

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


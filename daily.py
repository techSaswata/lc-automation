import requests
from google import genai
from google.genai import types
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


# Environment variables
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
LEETCODE_CSRF = os.environ.get("LEETCODE_CSRF", "")
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
EMAIL_TO = os.environ["EMAIL_TO"]
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = os.environ.get("SMTP_PORT", "587")


# Create session with cookies
session = requests.Session()
session.cookies.set('LEETCODE_SESSION', LEETCODE_SESSION, domain='leetcode.com')
if LEETCODE_CSRF:
    session.cookies.set('csrftoken', LEETCODE_CSRF, domain='leetcode.com')

# Headers based on working HAR file analysis
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',  # No brotli - Python handles gzip automatically
    'Content-Type': 'application/json',
    'Origin': 'https://leetcode.com',
    'Referer': 'https://leetcode.com',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
}

if LEETCODE_CSRF:
    headers['x-csrftoken'] = LEETCODE_CSRF


# ---------------------------
# 1. Fetch Daily Problem
# ---------------------------
def get_daily_challenge():
    """Fetch today's LeetCode daily challenge"""
    url = "https://leetcode.com/graphql"
    query = {
        "query": """
        query questionOfToday {
          activeDailyCodingChallengeQuestion {
            date
            question {
              questionId
              questionFrontendId
              title
              titleSlug
              content
              codeSnippets {
                lang
                code
              }
              exampleTestcases
              difficulty
            }
          }
        }
        """
    }

    print("Fetching daily challenge from LeetCode...")
    res = session.post(url, json=query, headers=headers)
    
    if res.status_code != 200:
        raise Exception(f"Failed to fetch daily problem: HTTP {res.status_code}")
    
    data = res.json()["data"]["activeDailyCodingChallengeQuestion"]
    q = data["question"]

    # Extract Java template
    java_template = ""
    for snip in q["codeSnippets"]:
        if snip["lang"] == "Java":
            java_template = snip["code"]
            break

    return {
        'title': q["title"],
        'slug': q["titleSlug"],
        'question_id': q["questionId"],
        'content': q["content"],
        'java_template': java_template,
        'date': data["date"]
    }


# Clean HTML → plain text
def html_to_text(html):
    """Convert HTML to plain text"""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text()


# ---------------------------
# 2. Gemini Code Generation (Using Gemini 2.0 Flash Exp with Thinking)
# ---------------------------
def generate_code(problem_text, java_template, previous_error=None):
    """Generate Java code using Gemini AI"""
    # Set API key as environment variable for the client
    os.environ['GEMINI_API_KEY'] = GEMINI_API_KEY
    
    try:
        client = genai.Client()
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        raise

    system_prompt = """
You are a competitive programming expert who specializes in writing highly optimized solutions.
You must return ONLY valid Java code with STRICTLY NO COMMENTS.

CRITICAL REQUIREMENTS:
- Give me the MOST OPTIMIZED CODE possible
- Use optimal time complexity algorithms
- Avoid nested loops where possible
- Use efficient data structures (HashMap, TreeSet, PriorityQueue, etc.)
- Think about edge cases carefully
- Return clean, efficient, bug-free code
- Use the given Java template exactly
- NO COMMENTS in the code
"""

    error_feedback = ""
    if previous_error:
        error_feedback = f"""

IMPORTANT - PREVIOUS ATTEMPT FAILED:
{previous_error}

You MUST fix this error and provide a DIFFERENT, MORE OPTIMIZED approach.
"""

    final_prompt = f"""
{system_prompt}

Problem Description:
{problem_text}

Java Boilerplate:
{java_template}
{error_feedback}

Constraints and Instructions:
- Strictly no comments. Only valid Java code.
- Provide the MOST OPTIMIZED solution with best time complexity.
- Make sure the code compiles and runs efficiently.
- Avoid Time Limit Exceeded by using optimal algorithms.
"""

    # Use Gemini 3 Pro Preview with proper settings for reasoning models
    MODEL_NAME = 'gemini-3-pro-preview'
    
    config = types.GenerateContentConfig(
        temperature=0.9,  # CRITICAL: High temperature for reasoning models to avoid repetition
        max_output_tokens=32768,  # Give room for thinking
    )
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=final_prompt,
            config=config
        )
        
        # Extract code from response - prioritize response.text
        code = None
        
        # Method 1: Try response.text first (most reliable)
        if hasattr(response, 'text') and response.text and response.text.strip():
            code = response.text.strip()
        
        # Method 2: If text is empty, try candidates
        if not code:
            if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                
                # Check finish reason first
                finish_reason = candidate.finish_reason if hasattr(candidate, 'finish_reason') else 'UNKNOWN'
                
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        if len(candidate.content.parts) > 0:
                            if hasattr(candidate.content.parts[0], 'text') and candidate.content.parts[0].text:
                                code = candidate.content.parts[0].text.strip()
                
                if not code:
                    print(f"Warning: Empty response from Gemini")
                    print(f"Finish reason: {finish_reason}")
                    print(f"Has usage_metadata: {hasattr(response, 'usage_metadata')}")
                    if hasattr(response, 'usage_metadata'):
                        print(f"Usage: {response.usage_metadata}")
                    raise Exception(f"Gemini returned empty response - finish_reason: {finish_reason}")
        
        if not code:
            raise Exception("Failed to extract code from Gemini response")
            
    except Exception as e:
        print(f"Error generating code: {e}")
        raise

    # Clean up markdown code blocks if present
    if code.startswith("```"):
        code = code.split("```")[1]
        if code.startswith("java"):
            code = code[len("java"):].strip()
        code = code.strip()
    
    # If there are multiple code blocks, take the one with the solution
    if "```" in code:
        parts = code.split("```")
        for part in reversed(parts):
            if "class Solution" in part or "public" in part:
                code = part.strip()
                break

    return code.strip()


# ---------------------------
# 3. Submit to LeetCode (Using Working Approach)
# ---------------------------
def submit_solution(slug, question_id, code):
    """Submit solution to LeetCode using the working direct endpoint"""
    url = f'https://leetcode.com/problems/{slug}/submit/'
    
    # Update referer for this specific problem
    submit_headers = headers.copy()
    submit_headers['Referer'] = f'https://leetcode.com/problems/{slug}/description/'
    
    # Exact payload format from HAR file
    payload = {
        "lang": "java",
        "question_id": question_id,
        "typed_code": code
    }
    
    print(f"Submitting to: {url}")
    response = session.post(url, json=payload, headers=submit_headers)
    
    if response.status_code != 200:
        raise Exception(f"Submission failed: HTTP {response.status_code} - {response.text[:500]}")
    
    data = response.json()
    submission_id = data.get('submission_id')
    
    if not submission_id:
        raise Exception(f"No submission_id in response: {data}")
    
    print(f"✓ Submission ID: {submission_id}")
    return submission_id


# Poll submission result
def check_status(submission_id):
    """Check submission status until complete"""
    url = f'https://leetcode.com/submissions/detail/{submission_id}/check/'
    
    print(f"Checking submission status...")
    max_attempts = 30
    
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"  Attempt {attempt}: HTTP {response.status_code}")
                time.sleep(2)
                continue
            
            data = response.json()
            state = data.get('state', 'UNKNOWN')
            
            if state == 'SUCCESS':
                return data
            elif state in ['PENDING', 'STARTED']:
                print(f"  Attempt {attempt}: {state}...")
                time.sleep(2)
            else:
                print(f"  Attempt {attempt}: Unknown state {state}")
                time.sleep(2)
                
        except Exception as e:
            print(f"  Attempt {attempt}: Exception - {e}")
            time.sleep(2)
    
    raise Exception(f"Timeout after {max_attempts} attempts")


# ---------------------------
# 4. Save solution to JavaYatra repo
# ---------------------------
def save_solution(date_str, title, code):
    """Save accepted solution to JavaYatra repository organized by month"""
    import subprocess
    
    # Parse date to get month and day
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    month = date_obj.strftime("%b")  # e.g., "Dec"
    day = date_obj.strftime("%d")     # e.g., "01", "10"
    
    # GitHub repo details
    REPO_URL = "https://github.com/techSaswata/JavaYatra.git"
    REPO_DIR = "JavaYatra"
    BASE_PATH = "leetcode_daily"
    
    # Get GitHub token
    GH_PAT = os.environ.get("GH_PAT", "")
    
    # Clone or update repo
    if not os.path.exists(REPO_DIR):
        print(f"Cloning JavaYatra repository...")
        if GH_PAT:
            auth_url = REPO_URL.replace("https://", f"https://{GH_PAT}@")
            subprocess.run(["git", "clone", auth_url, REPO_DIR], check=True)
        else:
            subprocess.run(["git", "clone", REPO_URL, REPO_DIR], check=True)
    else:
        print(f"Updating JavaYatra repository...")
        subprocess.run(["git", "-C", REPO_DIR, "pull"], check=True)
    
    # Create month folder if it doesn't exist
    month_folder = os.path.join(REPO_DIR, BASE_PATH, month)
    os.makedirs(month_folder, exist_ok=True)
    
    # Save file as MonthDay.java (e.g., Dec01.java, Dec10.java)
    filename = f"{month}{day}.java"
    filepath = os.path.join(month_folder, filename)
    
    with open(filepath, "w") as f:
        f.write(code)
    
    print(f"✓ Saved solution as: {BASE_PATH}/{month}/{filename}")
    
    # Commit and push
    try:
        # Configure git user
        subprocess.run(["git", "-C", REPO_DIR, "config", "user.name", "techSaswata"], check=True)
        subprocess.run(["git", "-C", REPO_DIR, "config", "user.email", "saswata.24bcs10248@sst.scaler.com"], check=True)
        
        # Add, commit, and push
        subprocess.run(["git", "-C", REPO_DIR, "add", "."], check=True)
        subprocess.run([
            "git", "-C", REPO_DIR, "commit", "-m",
            f"Add LeetCode solution: {title} ({month} {day})"
        ], check=True)
        subprocess.run(["git", "-C", REPO_DIR, "push"], check=True)
        print(f"✓ Pushed to JavaYatra repository")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Git operation failed: {e}")
        # Don't raise - email notification will still work
    
    return f"{BASE_PATH}/{month}/{filename}"


# ---------------------------
# 5. Email Notification
# ---------------------------
def send_email(subject, body):
    """Send email notification"""
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
        print("✓ Email sent successfully!")
    except Exception as e:
        print(f"✗ Failed to send email: {e}")


# ---------------------------
# MAIN FLOW WITH RETRY
# ---------------------------
def main():
    print("=" * 70)
    print("LEETCODE DAILY AUTO SOLVER")
    print("=" * 70)
    
    # Step 1: Fetch daily challenge
    print("\n[1/5] Fetching daily challenge...")
    problem = get_daily_challenge()
    
    print(f"✓ Problem: {problem['title']}")
    print(f"✓ Slug: {problem['slug']}")
    print(f"✓ Question ID: {problem['question_id']}")
    print(f"✓ Date: {problem['date']}")

    problem_text = html_to_text(problem['content']).strip()

    # Step 2: Generate and submit with retries
    max_attempts = 5
    attempts = 0
    previous_error = None  # Track previous error for feedback to Gemini

    while attempts < max_attempts:
        attempts += 1
        print(f"\n{'='*70}")
        print(f"ATTEMPT {attempts}/{max_attempts}")
        print(f"{'='*70}")

        try:
            # Generate code (with feedback from previous attempt)
            print(f"\n[2/5] Generating code using Gemini 3 Pro Preview (reasoning model)...")
            code = generate_code(problem_text, problem['java_template'], previous_error)
            print(f"✓ Code generated ({len(code)} chars)")
            
            # Submit
            print(f"\n[3/5] Submitting to LeetCode...")
            submission_id = submit_solution(problem['slug'], problem['question_id'], code)
            
            # Check status
            print(f"\n[4/5] Checking submission status...")
            result = check_status(submission_id)

            status = result.get("status_msg", "Unknown")
            runtime = result.get("status_runtime", "N/A")
            memory = result.get("status_memory", "N/A")
            
            print(f"\n{'='*70}")
            print(f"RESULT: {status}")
            print(f"{'='*70}")
            print(f"Runtime: {runtime}")
            print(f"Memory: {memory}")
            if 'total_testcases' in result:
                print(f"Test Cases: {result.get('total_correct', 0)}/{result.get('total_testcases', 0)}")
            print(f"{'='*70}")

            if status == "Accepted":
                # Save solution
                print(f"\n[5/5] ✓ ACCEPTED! Saving solution...")
                filename = save_solution(problem['date'], problem['title'], code)
                
                # Send success email
                send_email(
                    f"✓ LeetCode Daily Accepted: {problem['title']}",
                    f"Your solution for {problem['title']} ({problem['slug']}) was Accepted!\n\n"
                    f"Runtime: {runtime}\n"
                    f"Memory: {memory}\n"
                    f"Saved as: {filename}\n"
                    f"Submission ID: {submission_id}\n\n"
                    f"Date: {problem['date']}"
                )
                
                print("\n" + "🎉" * 35)
                print("SUCCESS! Task completed.")
                print("🎉" * 35)
                return
            else:
                # Build error feedback for next attempt
                print(f"\n✗ {status}")
                error_details = f"Status: {status}"
                
                if 'full_runtime_error' in result and result['full_runtime_error']:
                    runtime_error = result['full_runtime_error'][:500]
                    print(f"Runtime Error: {runtime_error}")
                    error_details += f"\nRuntime Error: {runtime_error}"
                
                if 'full_compile_error' in result and result['full_compile_error']:
                    compile_error = result['full_compile_error'][:500]
                    print(f"Compile Error: {compile_error}")
                    error_details += f"\nCompile Error: {compile_error}"
                
                if status == "Time Limit Exceeded":
                    test_cases = result.get('total_testcases', '?')
                    passed = result.get('total_correct', 0)
                    error_details += f"\nTime Limit Exceeded after {passed}/{test_cases} test cases"
                    error_details += "\nYou need a MORE EFFICIENT algorithm with better time complexity!"
                
                if status == "Wrong Answer":
                    if 'last_testcase' in result:
                        error_details += f"\nFailed on test case: {result['last_testcase'][:200]}"
                    if 'code_output' in result and 'expected_output' in result:
                        error_details += f"\nYour output: {result.get('code_output', '')[:100]}"
                        error_details += f"\nExpected: {result.get('expected_output', '')[:100]}"
                
                # Store error for next attempt
                previous_error = error_details
                
                print(f"\nWill regenerate code with error feedback...")
                print(f"Retrying in 10 seconds...")
                time.sleep(10)
                
        except Exception as e:
            print(f"\n✗ Submission Error: {e}")
            import traceback
            traceback.print_exc()
            
            # Store submission error for next attempt
            previous_error = f"Submission failed with error: {str(e)}"
            
            if attempts < max_attempts:
                print(f"\nWill regenerate code to fix submission error...")
                print(f"\nRetrying in 10 seconds...")
                time.sleep(10)

    # All attempts failed
    print(f"\n{'='*70}")
    print(f"FAILED - All {max_attempts} attempts exhausted")
    print(f"{'='*70}")
    
    send_email(
        f"✗ LeetCode Daily FAILED: {problem['title']}",
        f"All {max_attempts} attempts failed for {problem['title']} ({problem['slug']}).\n\n"
        f"Please check the logs for details.\n\n"
        f"Date: {problem['date']}"
    )


if __name__ == "__main__":
    main()

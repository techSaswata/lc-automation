You need to make a leetcode daily automatic question submitter.

Note: dont make readme.md - If anything needed from me, tell me in chat.

Note : In the following demo code, it can be written to use gemini older versions. But you have to use gemini most latest pro version with thinking.

✅ FEATURES INCLUDED
✔ Uses github actions
✔ Runs every day at 7 AM IST
✔ Fetches LeetCode daily problem
✔ Gets problem + constraints + code template
✔ Sends to Gemini with system prompt
✔ Generates Java code with NO comments
✔ Submits to LeetCode
✔ Retries until Accepted (configurable)
✔ Only after AC → creates file:

leetcode-Dec08-25.java

✔ Commits that file to your repository
✔ Sends email notification (via GitHub Action mailer)
🚀 Final Project Structure
.
├── .github
│   └── workflows
│       └── daily.yml
└── daily.py

🔐 REQUIRED SECRETS (Add in GitHub)
Secret Name	Value
GEMINI_KEY	Your Gemini API Key
LEETCODE_SESSION	Your full LEETCODE_SESSION cookie (JWT token)
MAIL_USERNAME	Email to send from (Gmail recommended)
MAIL_PASSWORD	App Password for Gmail
MAIL_TO	Your email address
📄 1. GitHub Action File (daily.yml)

Create:

.github/workflows/daily.yml


Paste this:

name: LeetCode Daily Auto Solver

on:
  schedule:
    - cron: "30 1 * * *"     # Runs at 7AM IST
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          pip install requests google-generativeai beautifulsoup4 lxml smtplib

      - name: Run Daily Script
        env:
          GEMINI_KEY: ${{ secrets.GEMINI_KEY }}
          LEETCODE_SESSION: ${{ secrets.LEETCODE_SESSION }}
          MAIL_USERNAME: ${{ secrets.MAIL_USERNAME }}
          MAIL_PASSWORD: ${{ secrets.MAIL_PASSWORD }}
          MAIL_TO: ${{ secrets.MAIL_TO }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python daily.py

      - name: Commit Results if Present
        run: |
          if [ -n "$(git status --porcelain)" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add .
            git commit -m "Add accepted LeetCode solution"
            git push
          fi

📌 2. The Main Script (daily.py)

Paste this entire file (fully rewritten and improved).

import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]
MAIL_PASSWORD = os.environ["MAIL_PASSWORD"]
MAIL_TO = os.environ["MAIL_TO"]


headers = {
    "User-Agent": "Mozilla/5.0"
}

cookies = {
    "LEETCODE_SESSION": LEETCODE_SESSION
}


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
# 2. Gemini Code Generation
# ---------------------------
def generate_code(problem_text, java_template):
    genai.configure(api_key=GEMINI_KEY)

    system_prompt = """
You are a competitive programming expert.
You must return ONLY valid Java code with STRICTLY NO COMMENTS.
Use this format:
- Use the given Java template
- Fill solve logic exactly
"""

    final_prompt = f"""
{system_prompt}

Problem Description:
{problem_text}

Java Boilerplate:
{java_template}

Constraints and Instructions:
Strictly no comments. Only valid Java code.
"""

    model = genai.GenerativeModel("gemini-1.5-flash")
    result = model.generate_content(final_prompt)

    code = result.text.strip()

    if code.startswith("```"):
        code = code.split("```")[1]
        if code.startswith("java"):
            code = code[len("java"):]

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
    return res.json()["data"]["submitSolution"]["submissionId"]


# Poll result
def check_status(submission_id):
    url = f"https://leetcode.com/submissions/detail/{submission_id}/check/"
    while True:
        res = requests.get(url, headers=headers, cookies=cookies).json()
        if res["state"] == "SUCCESS":
            return res
        time.sleep(2)


# ---------------------------
# 4. Save solution on success
# ---------------------------
def save_solution(date_str, slug, code):
    filename = f"leetcode-{date_str}.java"
    with open(filename, "w") as f:
        f.write(code)
    return filename


# ---------------------------
# 5. Email Notification
# ---------------------------
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = MAIL_USERNAME
    msg["To"] = MAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
    server.sendmail(MAIL_USERNAME, MAIL_TO, msg.as_string())
    server.quit()


# ---------------------------
# MAIN FLOW WITH RETRY
# ---------------------------
def main():
    print("Fetching daily challenge...")
    title, slug, html, java_template, date = get_daily_challenge()

    problem_text = html_to_text(html).strip()
    date_clean = date.replace("-", "")

    print("Generating code using Gemini...")
    attempts = 0
    max_attempts = 5

    while attempts < max_attempts:
        attempts += 1
        print(f"Attempt {attempts}...")

        code = generate_code(problem_text, java_template)
        submission_id = submit_solution(slug, code)
        result = check_status(submission_id)

        status = result.get("status_msg")

        print("Result:", status)

        if status == "Accepted":
            filename = save_solution(date_clean, slug, code)
            send_email(
                f"LeetCode Daily Accepted: {title}",
                f"Your solution for {title} ({slug}) was Accepted.\nSaved as {filename}."
            )
            print("Accepted! Saved & email sent.")
            return

        print("Failed. Retrying...")

    # After 5 failed attempts
    send_email(
        f"LeetCode Daily FAILED: {title}",
        f"All {max_attempts} attempts failed for {title} ({slug})."
    )
    print("All attempts failed. Email sent.")


if __name__ == "__main__":
    main()

🧠 What This System Now Does (In English)
⏰ 7 AM IST Daily

Gets the LeetCode daily question

Extracts:

Problem statement

Constraints

Java starter code

Sends to Gemini with system prompt

Gemini outputs Java code ONLY, no comments

Code is submitted to LeetCode

If ❌ Wrong Answer → retries (up to 5 times)

If ✔ Accepted:

Creates file:
leetcode-20251208.java

Commits to GitHub

Sends email notification

If all retries fail → sends failure email
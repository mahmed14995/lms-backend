from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import concurrent.futures
import os

app = Flask(__name__)
CORS(app) # Allow cross-origin requests

# =========================
# CONFIGURATION
# =========================
USERNAME = "15899"
PASSWORD = "73335317"
BASE_URL = "https://lms.kiet.edu.pk/kietlms"
LOGIN_URL = f"{BASE_URL}/login/index.php"

def get_lms_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    try:
        res = session.get(LOGIN_URL, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        token_tag = soup.find("input", {"name": "logintoken"})
        if not token_tag: return None
        token = token_tag.get("value")
        payload = {"username": USERNAME, "password": PASSWORD, "logintoken": token}
        post_res = session.post(LOGIN_URL, data=payload, timeout=15)
        if "login" in post_res.url.lower(): return None
        return session
    except:
        return None

def get_task_details(session, a_link, c_name):
    try:
        res = session.get(a_link, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        title_tag = soup.find("h2")
        title = title_tag.text.strip() if title_tag else "Assignment"
        table = soup.find("div", class_="submissionstatustable")
        status, deadline, timestamp = "Pending", "N/A", 0
        if table:
            rows = table.find_all("tr")
            for row in rows:
                th, td = row.find("th"), row.find("td")
                if not th or not td: continue
                key, value = th.text.strip().lower(), td.text.strip()
                if "submission status" in key: status = value
                if "due date" in key:
                    deadline = value
                    try:
                        dt = datetime.strptime(value, "%A, %d %B %Y, %I:%M %p")
                        timestamp = int(dt.timestamp() * 1000)
                    except: pass
        return {"title": title, "subject": c_name, "deadline": deadline, "timestamp": timestamp, "status": status, "link": a_link}
    except:
        return None

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    session = get_lms_session()
    if not session: return jsonify({"error": "LMS Login Failed"}), 401
    all_tasks = []
    try:
        res = session.get(f"{BASE_URL}/my/mycourses.php", timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        course_links = list(set([a["href"] for a in soup.find_all("a", href=True) if "course/view.php?id=" in a["href"]]))
        assign_list = []
        for c_link in course_links[:8]:
            try:
                c_res = session.get(c_link, timeout=10)
                c_soup = BeautifulSoup(c_res.text, "html.parser")
                c_name = c_soup.find("h1").text.strip() if c_soup.find("h1") else "Course"
                a_links = [a["href"] for a in c_soup.find_all("a", href=True) if "/mod/assign/view.php?id=" in a["href"]]
                for link in set(a_links): assign_list.append((link, c_name))
            except: continue
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_task_details, session, link, name) for link, name in assign_list]
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()
                if result:
                    result["id"] = i + 1
                    all_tasks.append(result)
        return jsonify(all_tasks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "Server is Running Successfully"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
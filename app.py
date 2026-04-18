from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import concurrent.futures
import os

app = Flask(__name__)

# =========================
# CONFIGURATION
# =========================
USERNAME = "15899"
PASSWORD = "73335317"
BASE_URL = "https://lms.kiet.edu.pk/kietlms"
LOGIN_URL = f"{BASE_URL}/login/index.php"


# =========================
# SAFE LMS LOGIN
# =========================
def get_lms_session():
    session = requests.Session()

    try:
        res = session.get(LOGIN_URL, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        token_tag = soup.find("input", {"name": "logintoken"})
        if not token_tag:
            print("Login token not found")
            return None

        token = token_tag.get("value")

        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "logintoken": token
        }

        post_res = session.post(LOGIN_URL, data=payload, timeout=10)

        if "login" in post_res.url.lower():
            print("Login failed")
            return None

        return session

    except Exception as e:
        print("Login error:", e)
        return None


# =========================
# FETCH SINGLE TASK
# =========================
def get_task_details(session, a_link, c_name):
    try:
        res = session.get(a_link, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        title_tag = soup.find("h2")
        title = title_tag.text.strip() if title_tag else "Assignment"

        table = soup.find("div", class_="submissionstatustable")

        status = "Pending"
        deadline = "N/A"
        timestamp = 0

        if table:
            rows = table.find_all("tr")

            for row in rows:
                th = row.find("th")
                td = row.find("td")

                if not th or not td:
                    continue

                key = th.text.strip().lower()
                value = td.text.strip()

                if "submission status" in key:
                    status = value

                if "time remaining" in key:
                    status += " " + value

                if "due date" in key:
                    deadline = value
                    try:
                        dt = datetime.strptime(value, "%A, %d %B %Y, %I:%M %p")
                        timestamp = int(dt.timestamp() * 1000)
                    except:
                        pass

        return {
            "title": title,
            "subject": c_name,
            "deadline": deadline,
            "timestamp": timestamp,
            "status": status,
            "link": a_link
        }

    except Exception as e:
        print("Task error:", e)
        return None


# =========================
# MAIN API ROUTE
# =========================
@app.route("/api/tasks", methods=["GET"])
def get_tasks():

    session = get_lms_session()
    if not session:
        return jsonify([])

    all_tasks = []

    try:
        res = session.get(f"{BASE_URL}/my/mycourses.php", timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        course_links = list(set([
            a["href"] for a in soup.find_all("a", href=True)
            if "course/view.php?id=" in a["href"]
        ]))

        assign_list = []

        for c_link in course_links[:8]:
            try:
                c_res = session.get(c_link, timeout=10)
                c_soup = BeautifulSoup(c_res.text, "html.parser")

                c_name_tag = c_soup.find("h1")
                c_name = c_name_tag.text.strip() if c_name_tag else "Course"

                a_links = [
                    a["href"] for a in c_soup.find_all("a", href=True)
                    if "/mod/assign/view.php?id=" in a["href"]
                ]

                for link in set(a_links):
                    assign_list.append((link, c_name))

            except:
                continue

        # Parallel fetching
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(get_task_details, session, link, name)
                for link, name in assign_list
            ]

            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()
                if result:
                    result["id"] = i + 1
                    all_tasks.append(result)

        print("Tasks found:", len(all_tasks))
        return jsonify(all_tasks)

    except Exception as e:
        print("API error:", e)
        return jsonify([])


# =========================
# HOME ROUTE
# =========================
@app.route("/")
def home():
    return "Server Running "


# =========================
# RUN (Railway compatible)
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import concurrent.futures

app = Flask(__name__)

# --- CONFIGURATION ---
USERNAME = "15899"
PASSWORD = "73335317" 
BASE_URL = "https://lms.kiet.edu.pk/kietlms"
LOGIN_URL = f"{BASE_URL}/login/index.php"

def get_lms_session():
    session = requests.Session()
    try:
        res = session.get(LOGIN_URL)
        token = BeautifulSoup(res.text, 'html.parser').find('input', {'name': 'logintoken'})['value']
        payload = {'username': USERNAME, 'password': PASSWORD, 'logintoken': token}
        post_res = session.post(LOGIN_URL, data=payload)
        return session if "login" not in post_res.url else None
    except: return None

def get_task_details(session, a_link, c_name):
    """Fetches details for a single assignment (Threaded)"""
    try:
        res = session.get(a_link)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.find('h2').text.strip() if soup.find('h2') else "Assignment"
        table = soup.find('div', class_='submissionstatustable')
        
        status, ts, deadline = "Pending", 0, "View in LMS"
        if table:
            for row in table.find_all('tr'):
                h = row.find('th').text.strip().lower() if row.find('th') else ""
                c = row.find('td').text.strip() if row.find('td') else ""
                if "submission status" in h: status = c
                if "time remaining" in h: status += " " + c
                if "due date" in h:
                    deadline = c
                    try:
                        dt = datetime.strptime(c, "%A, %d %B %Y, %I:%M %p")
                        ts = int(dt.timestamp() * 1000)
                    except: pass
        return {"title": title, "subject": c_name, "deadline": deadline, "timestamp": ts, "status": status, "link": a_link}
    except: return None

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    session = get_lms_session()
    if not session: return jsonify([])

    all_tasks = []
    try:
        res = session.get(f"{BASE_URL}/my/mycourses.php")
        soup = BeautifulSoup(res.text, 'html.parser')
        course_links = list(set([a['href'] for a in soup.find_all('a', href=True) if "course/view.php?id=" in a['href']]))
        
        # Gathering all assignment links from all courses
        assign_work_list = []
        for c_link in course_links[:8]: # Scan top 8 courses
            c_res = session.get(c_link)
            c_soup = BeautifulSoup(c_res.text, 'html.parser')
            c_name = c_soup.find('h1').text.strip() if c_soup.find('h1') else "Course"
            a_links = [a['href'] for a in c_soup.find_all('a', href=True) if "/mod/assign/view.php?id=" in a['href']]
            for link in set(a_links):
                assign_work_list.append((link, c_name))

        # Parallel Execution: Scan assignments in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_task_details, session, link, name) for link, name in assign_work_list]
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()
                if result:
                    result['id'] = i + 1
                    all_tasks.append(result)

        print(f"Sync complete. Found {len(all_tasks)} tasks.")
        return jsonify(all_tasks)
    except: return jsonify([])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
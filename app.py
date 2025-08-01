from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import base64
import numpy as np
import cv2
import os
import logging
import traceback
# ----------------------------------------------------------
# Project: Missing Child Identification System using DL & SVM
# Author: Varsha Guriyala | MCA Final Year Project | 2025
# GitHub: https://github.com/varsha-guriyala/missing-child-identification
# Note: Do not copy or redistribute without permission.
# ----------------------------------------------------------


# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'a8js29dn18snd29shd83kshd82h3skdh'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Dummy credentials (for testing)
user_credentials = {'user': 'userpass'}
authority_credentials = {'admin': 'adminpass'}

# --- DB Connection ---
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='varshadb@1',
        database='missing_child_db'
    )

# --- Login Logic ---
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        role = request.form.get('role')
        username = request.form.get('username')
        password = request.form.get('password')

        if role == 'user' and user_credentials.get(username) == password:
            session['username'] = username
            session['role'] = 'user'
            return redirect(url_for('user_upload'))

        elif role == 'authority' and authority_credentials.get(username) == password:
            session['username'] = username
            session['role'] = 'authority'
            return redirect(url_for('authority_dashboard'))

        else:
            return render_template('login.html', error="Invalid credentials")

    except Exception as e:
        logger.error(traceback.format_exc())
        return render_template('login.html', error="Login error")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- User Upload ---
@app.route('/user/upload', methods=['GET', 'POST'])
def user_upload():
    if session.get('role') != 'user':
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            child_name = request.form.get('child_name')
            phone = request.form.get('phone')
            address = request.form.get('address')
            email = request.form.get('email')
            aadhar_number = request.form.get('aadhar_number')
            image_file = request.files.get('image')

            if not all([child_name, phone, address, email, aadhar_number, image_file]):
                return render_template('user_upload.html', error="All fields are required")

            image_data = image_file.read()

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_requests (child_name, address, phone, email, `aadhar number`, image)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (child_name, address, phone, email, aadhar_number, image_data))
            conn.commit()
            cursor.close()
            conn.close()

            return render_template('user_upload.html', message="Upload successful", success=True)

        except Exception as e:
            logger.error(traceback.format_exc())
            return render_template('user_upload.html', error="Upload failed")

    return render_template('user_upload.html')

# --- Authority Dashboard ---
# --- Authority Dashboard ---
@app.route('/authority/dashboard')
def authority_dashboard():
    if session.get('role') != 'authority':
        return redirect(url_for('index'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, child_name, phone, address, email, `aadhar number`, image FROM user_requests")
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        requests = []
        for row in data:
            requests.append({
                'id': row[0],
                'child_name': row[1],
                'phone': row[2],
                'address': row[3],
                'email': row[4],
                'aadhar_number': row[5],
                'image': base64.b64encode(row[6]).decode() if row[6] else ''
            })

        return render_template('authority_dashboard.html', requests=requests)

    except Exception as e:
        logger.error(traceback.format_exc())
        return render_template('authority_dashboard.html', error="Failed to load data")

# --- Delete Request ---
@app.route('/authority/delete/<int:request_id>')
def delete_request(request_id):
    if session.get('role') != 'authority':
        return redirect(url_for('index'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM authority_cases WHERE child_name IN (SELECT child_name FROM user_requests WHERE id = %s)", (request_id,))
        cursor.execute("DELETE FROM user_requests WHERE id = %s", (request_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('authority_dashboard'))

    except Exception as e:
        logger.error(traceback.format_exc())
        return render_template('authority_dashboard.html', error="Failed to delete record")

# --- Authority Upload ---
@app.route('/authority/upload', methods=['GET', 'POST'])
def authority_upload_case():
    if session.get('role') != 'authority':
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            name = request.form.get('name')
            address = request.form.get('address')
            image_file = request.files.get('image')

            if not all([name, address, image_file]):
                return render_template('authority_upload.html', error="All fields required")

            image_data = image_file.read()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO authority_cases (child_name, address, image) VALUES (%s, %s, %s)",
                           (name, address, image_data))
            conn.commit()
            cursor.close()
            conn.close()

            return render_template('authority_upload.html', message="Case uploaded successfully!", success=True)

        except Exception as e:
            logger.error(traceback.format_exc())
            return render_template('authority_upload.html', error="Upload failed")

    return render_template('authority_upload.html')

# --- Find Missing Child ---
@app.route('/find-missing', methods=['GET', 'POST'])
def find_missing():
    if session.get('role') != 'authority':
        return redirect(url_for('index'))

    result = None
    message = ""

    if request.method == 'POST':
        try:
            image_data = request.files['image'].read()

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT child_name, address, image FROM authority_cases")
            cases = cursor.fetchall()
            conn.close()

            for name, address, stored_img in cases:
                if is_match(image_data, stored_img):
                    result = {
                        'name': name,
                        'address': address,
                        'image': base64.b64encode(stored_img).decode()
                    }
                    message = "Child Found"
                    break

            if not result:
                message = "No Match Found"

        except Exception as e:
            logger.error(traceback.format_exc())
            message = "Error in processing image"

    return render_template('find_missing.html', result=result, message=message)

# --- Face Matching Function ---
def is_match(image1, image2):
    try:
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        img1 = cv2.imdecode(np.frombuffer(image1, np.uint8), cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imdecode(np.frombuffer(image2, np.uint8), cv2.IMREAD_GRAYSCALE)

        faces1 = face_cascade.detectMultiScale(img1, 1.1, 5)
        faces2 = face_cascade.detectMultiScale(img2, 1.1, 5)

        if len(faces1) == 0 or len(faces2) == 0:
            return False

        x, y, w, h = faces1[0]
        face1 = cv2.resize(img1[y:y+h, x:x+w], (100, 100))

        x, y, w, h = faces2[0]
        face2 = cv2.resize(img2[y:y+h, x:x+w], (100, 100))

        hist1 = cv2.calcHist([face1], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([face2], [0], None, [256], [0, 256])
        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)

        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL) > 0.75

    except Exception as e:
        logger.error("Face match failed: " + str(e))
        return False

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)

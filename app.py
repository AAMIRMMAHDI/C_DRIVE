from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
import sqlite3
import os
import bcrypt
from datetime import datetime, timedelta
import logging
import uuid
import string
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'
BASE_UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    try:
        conn = sqlite3.connect('database.db', timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {str(e)}")
        raise

def generate_random_string(length=15):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))

def generate_symbolic_folder_name():
    # Use safe characters for folder names (avoid *, ^, <, >, ?, /, \, |)
    safe_chars = string.ascii_letters + string.digits + "-_!@#$"
    return ''.join(random.choice(safe_chars) for _ in range(10))

def check_folder_permissions(folder):
    try:
        os.makedirs(folder, exist_ok=True)
        test_file = os.path.join(folder, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except Exception as e:
        logging.error(f"Folder permission error for {folder}: {str(e)}")
        return False

def init_db():
    try:
        conn = get_db_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                storage_limit REAL NOT NULL DEFAULT 5120,
                user_folder TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                folder_id INTEGER,
                mime_type TEXT,
                symbolic_folder TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (folder_id) REFERENCES folders (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                parent_folder_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (parent_folder_id) REFERENCES folders (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS share_tokens (
                token TEXT PRIMARY KEY,
                file_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files (id)
            )
        ''')
        # Add symbolic_folder column if not exists
        try:
            conn.execute('ALTER TABLE files ADD COLUMN symbolic_folder TEXT NOT NULL DEFAULT "!@#$%^&*()"')
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Update existing users' storage_limit to 5120 MB
        conn.execute('UPDATE users SET storage_limit = 5120 WHERE storage_limit != 5120')
        conn.commit()
        logging.debug("Database initialized successfully, storage_limit set to 5120 MB")
    except sqlite3.Error as e:
        logging.error(f"Database initialization error: {str(e)}")
        raise
    finally:
        conn.close()

# Initialize database and check upload folder permissions
try:
    if not os.path.exists(BASE_UPLOAD_FOLDER):
        os.makedirs(BASE_UPLOAD_FOLDER)
    if not check_folder_permissions(BASE_UPLOAD_FOLDER):
        logging.error("Upload folder is not writable!")
        raise Exception("Upload folder is not writable")
    init_db()
except Exception as e:
    logging.error(f"Startup error: {str(e)}")
    raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        logging.debug(f"Attempting to register username: {username}")
        
        conn = get_db_connection()
        existing_users = conn.execute('SELECT username FROM users').fetchall()
        existing_usernames = [user['username'] for user in existing_users]
        logging.debug(f"Existing usernames: {existing_usernames}")
        
        if username in existing_usernames:
            flash('نام کاربری قبلاً استفاده شده است!', 'error')
            conn.close()
            return render_template('register.html')
        
        try:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            user_folder = generate_random_string(15)
            symbolic_folder = generate_symbolic_folder_name()
            user_upload_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder, symbolic_folder)
            
            logging.debug(f"Creating user folder: {user_upload_path}")
            if not check_folder_permissions(user_upload_path):
                flash('خطا در ایجاد پوشه کاربر! دسترسی‌ها را بررسی کنید.', 'error')
                conn.close()
                return render_template('register.html')
            
            conn.execute('INSERT INTO users (username, password, user_folder) VALUES (?, ?, ?)', 
                        (username, hashed, user_folder))
            conn.commit()
            logging.debug(f"User {username} registered with folder {user_folder}")
            flash('ثبت‌نام با موفقیت انجام شد!', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            logging.error(f"Database error during registration: {str(e)}")
            flash('خطا در ثبت‌نام! نام کاربری ممکن است قبلاً استفاده شده باشد.', 'error')
        except Exception as e:
            logging.error(f"Unexpected error during registration: {str(e)}")
            flash(f'خطای ناشناخته‌ای رخ داد: {str(e)}', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        logging.debug(f"Attempting to login username: {username}")
        
        try:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            
            if user:
                logging.debug(f"User found: {user['username']}, checking password...")
                if bcrypt.checkpw(password.encode('utf-8'), user['password']):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    logging.debug(f"Login successful for {username}")
                    flash('ورود با موفقیت انجام شد!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    logging.debug(f"Password incorrect for {username}")
                    flash('رمز عبور اشتباه است!', 'error')
            else:
                logging.debug(f"User not found: {username}")
                flash('نام کاربری یافت نشد!', 'error')
        except sqlite3.Error as e:
            logging.error(f"Database error during login for {username}: {str(e)}")
            flash(f'خطا در ورود: {str(e)}', 'error')
        except Exception as e:
            logging.error(f"Unexpected error during login for {username}: {str(e)}")
            flash(f'خطای ناشناخته: {str(e)}', 'error')
        finally:
            if 'conn' in locals():
                conn.close()
                logging.debug("Database connection closed")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('با موفقیت خارج شدید!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    folder_id = request.args.get('folder_id', type=int)
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')
    query = request.args.get('q', '')

    valid_sort_columns = ['original_filename', 'created_at', 'size']
    sort_by = sort_by if sort_by in valid_sort_columns else 'created_at'
    sort_order = sort_order if sort_order in ['asc', 'desc'] else 'desc'

    conn = get_db_connection()
    
    # Calculate storage used
    storage_used = conn.execute('SELECT SUM(size) FROM files WHERE user_id = ?', (user_id,)).fetchone()[0] or 0
    storage_used = storage_used / (1024 * 1024)  # Convert to MB
    storage_limit = conn.execute('SELECT storage_limit FROM users WHERE id = ?', (user_id,)).fetchone()['storage_limit']

    # Fetch parent folder ID
    parent_folder_id = None
    folder_name = None
    if folder_id:
        logging.debug(f"Fetching parent_folder_id for folder_id={folder_id}, user_id={user_id}")
        folder = conn.execute('SELECT parent_folder_id, name FROM folders WHERE id = ? AND user_id = ?', 
                            (folder_id, user_id)).fetchone()
        if folder:
            parent_folder_id = folder['parent_folder_id']
            folder_name = folder['name']
            logging.debug(f"Folder found: name={folder_name}, parent_folder_id={parent_folder_id}")
        else:
            logging.warning(f"Folder with id={folder_id} not found for user_id={user_id}")
            flash('پوشه یافت نشد!', 'error')
            conn.close()
            return redirect(url_for('dashboard'))

    # Fetch folders
    folder_query = '''
        SELECT id, name, created_at FROM folders 
        WHERE user_id = ? AND (parent_folder_id = ? OR (parent_folder_id IS NULL AND ? IS NULL))
    '''
    folders = conn.execute(folder_query, (user_id, folder_id, folder_id)).fetchall()
    logging.debug(f"Folders fetched: {[(f['id'], f['name']) for f in folders]}")

    # Fetch files
    file_query = '''
        SELECT id, original_filename, size, created_at, folder_id FROM files 
        WHERE user_id = ? AND (folder_id = ? OR (folder_id IS NULL AND ? IS NULL))
    '''
    if query:
        file_query += ' AND original_filename LIKE ?'
        files = conn.execute(file_query + f' ORDER BY {sort_by} {sort_order}', 
                           (user_id, folder_id, folder_id, f'%{query}%')).fetchall()
    else:
        files = conn.execute(file_query + f' ORDER BY {sort_by} {sort_order}', 
                           (user_id, folder_id, folder_id)).fetchall()
    logging.debug(f"Files fetched: {[(f['id'], f['original_filename']) for f in files]}")

    conn.close()

    return render_template('dashboard.html', 
                         username=session['username'], 
                         storage_used=storage_used, 
                         storage_limit=storage_limit, 
                         folders=folders, 
                         files=files, 
                         folder_id=folder_id, 
                         parent_folder_id=parent_folder_id,
                         folder_name=folder_name,
                         sort_by=sort_by, 
                         sort_order=sort_order, 
                         query=query)

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    files = request.files.getlist('file')
    folder_id = request.form.get('folder_id', type=int)
    user_id = session['user_id']
    
    logging.debug(f"Uploading files with folder_id={folder_id} for user_id={user_id}")
    
    if not files or all(f.filename == '' for f in files):
        flash('هیچ فایلی انتخاب نشده است!', 'error')
        logging.debug("No files selected for upload")
        return redirect(url_for('dashboard', folder_id=folder_id))
    
    conn = get_db_connection()
    user_folder = conn.execute('SELECT user_folder FROM users WHERE id = ?', (user_id,)).fetchone()['user_folder']
    symbolic_folder = generate_symbolic_folder_name()
    upload_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder, symbolic_folder)
    
    logging.debug(f"Creating upload path: {upload_path}")
    
    storage_used = conn.execute('SELECT SUM(size) FROM files WHERE user_id = ?', (user_id,)).fetchone()[0] or 0
    storage_limit = conn.execute('SELECT storage_limit FROM users WHERE id = ?', (user_id,)).fetchone()['storage_limit'] * 1024 * 1024
    
    try:
        os.makedirs(upload_path, exist_ok=True)
    except OSError as e:
        logging.error(f"Failed to create upload path {upload_path}: {str(e)}")
        flash(f'خطا در ایجاد مسیر آپلود: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('dashboard', folder_id=folder_id))
    
    for file in files:
        if file and file.filename:
            file_size = len(file.read())
            file.seek(0)
            if storage_used + file_size > storage_limit:
                flash('فضای ذخیره‌سازی کافی نیست!', 'error')
                logging.debug(f"Storage limit exceeded: used={storage_used}, file_size={file_size}, limit={storage_limit}")
                conn.close()
                return redirect(url_for('dashboard', folder_id=folder_id))
            
            original_filename = file.filename
            stored_filename = f"{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
            file_path = os.path.join(upload_path, stored_filename)
            file.save(file_path)
            
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            mime_type = file.content_type
            conn.execute('INSERT INTO files (original_filename, stored_filename, size, created_at, user_id, folder_id, mime_type, symbolic_folder) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (original_filename, stored_filename, file_size, created_at, user_id, folder_id, mime_type, symbolic_folder))
            storage_used += file_size
            logging.debug(f"File uploaded: {original_filename}, folder_id={folder_id}, size={file_size}")
    
    conn.commit()
    conn.close()
    flash('فایل‌ها با موفقیت آپلود شدند!', 'success')
    return redirect(url_for('dashboard', folder_id=folder_id))

@app.route('/create_folder', methods=['POST'])
def create_folder():
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    folder_name = request.form['folder_name']
    parent_folder_id = request.form.get('parent_folder_id', type=int)
    user_id = session['user_id']
    
    conn = get_db_connection()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('INSERT INTO folders (name, created_at, user_id, parent_folder_id) VALUES (?, ?, ?, ?)',
                (folder_name, created_at, user_id, parent_folder_id))
    conn.commit()
    conn.close()
    
    flash('پوشه با موفقیت ایجاد شد!', 'success')
    return redirect(url_for('dashboard', folder_id=parent_folder_id))

@app.route('/rename/<int:file_id>', methods=['POST'])
def rename(file_id):
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    new_name = request.form['new_name'].strip()
    folder_id = request.form.get('folder_id', type=int)
    
    if not new_name:
        flash('نام جدید نمی‌تواند خالی باشد!', 'error')
        logging.debug(f"Rename failed for file_id={file_id}: Empty new_name")
        return redirect(url_for('dashboard', folder_id=folder_id))
    
    try:
        conn = get_db_connection()
        file = conn.execute('SELECT id FROM files WHERE id = ? AND user_id = ?', 
                           (file_id, session['user_id'])).fetchone()
        if not file:
            flash('فایل یافت نشد!', 'error')
            logging.debug(f"Rename failed for file_id={file_id}: File not found")
            conn.close()
            return redirect(url_for('dashboard', folder_id=folder_id))
        
        conn.execute('UPDATE files SET original_filename = ? WHERE id = ? AND user_id = ?', 
                    (new_name, file_id, session['user_id']))
        conn.commit()
        logging.debug(f"File id={file_id} renamed to {new_name} for user_id={session['user_id']}")
        flash('نام فایل با موفقیت تغییر کرد!', 'success')
    except sqlite3.Error as e:
        logging.error(f"Database error during rename for file_id={file_id}: {str(e)}")
        flash(f'خطا در تغییر نام فایل: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('dashboard', folder_id=folder_id))

@app.route('/rename_folder/<int:folder_id>', methods=['POST'])
def rename_folder(folder_id):
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    new_name = request.form['new_name'].strip()
    
    if not new_name:
        flash('نام جدید نمی‌تواند خالی باشد!', 'error')
        logging.debug(f"Folder rename failed for folder_id={folder_id}: Empty new_name")
        return redirect(url_for('dashboard', folder_id=folder_id))
    
    try:
        conn = get_db_connection()
        folder = conn.execute('SELECT id FROM folders WHERE id = ? AND user_id = ?', 
                            (folder_id, session['user_id'])).fetchone()
        if not folder:
            flash('پوشه یافت نشد!', 'error')
            logging.debug(f"Folder rename failed for folder_id={folder_id}: Folder not found")
            conn.close()
            return redirect(url_for('dashboard', folder_id=folder_id))
        
        conn.execute('UPDATE folders SET name = ? WHERE id = ? AND user_id = ?', 
                    (new_name, folder_id, session['user_id']))
        conn.commit()
        logging.debug(f"Folder id={folder_id} renamed to {new_name} for user_id={session['user_id']}")
        flash('نام پوشه با موفقیت تغییر کرد!', 'success')
    except sqlite3.Error as e:
        logging.error(f"Database error during folder rename for folder_id={folder_id}: {str(e)}")
        flash(f'خطا در تغییر نام پوشه: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('dashboard', folder_id=folder_id))

@app.route('/delete/<int:file_id>')
def delete_file(file_id):
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    file = conn.execute('SELECT stored_filename, folder_id, user_id, symbolic_folder FROM files WHERE id = ? AND user_id = ?', 
                       (file_id, session['user_id'])).fetchone()
    if file:
        user_folder = conn.execute('SELECT user_folder FROM users WHERE id = ?', (file['user_id'],)).fetchone()['user_folder']
        file_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder, file['symbolic_folder'], file['stored_filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
        conn.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, session['user_id']))
        conn.commit()
        flash('فایل با موفقیت حذف شد!', 'success')
    else:
        flash('فایل یافت نشد!', 'error')
    conn.close()
    return redirect(url_for('dashboard', folder_id=file['folder_id'] if file else None))

@app.route('/delete_folder/<int:folder_id>')
def delete_folder(folder_id):
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    folder = conn.execute('SELECT parent_folder_id FROM folders WHERE id = ? AND user_id = ?', 
                        (folder_id, session['user_id'])).fetchone()
    if folder:
        conn.execute('DELETE FROM files WHERE folder_id = ? AND user_id = ?', (folder_id, session['user_id']))
        conn.execute('DELETE FROM folders WHERE id = ? AND user_id = ?', (folder_id, session['user_id']))
        conn.commit()
        flash('پوشه با موفقیت حذف شد!', 'success')
    else:
        flash('پوشه یافت نشد!', 'error')
    conn.close()
    return redirect(url_for('dashboard', folder_id=folder['parent_folder_id'] if folder else None))

@app.route('/download_file/<int:file_id>')
def download_file(file_id):
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    file = conn.execute('SELECT stored_filename, original_filename, user_id, symbolic_folder FROM files WHERE id = ? AND user_id = ?', 
                       (file_id, session['user_id'])).fetchone()
    if file:
        user_folder = conn.execute('SELECT user_folder FROM users WHERE id = ?', (file['user_id'],)).fetchone()['user_folder']
        file_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder, file['symbolic_folder'], file['stored_filename'])
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=file['original_filename'])
    flash('فایل یافت نشد!', 'error')
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/download_shared/<token>')
def download_shared(token):
    conn = get_db_connection()
    share = conn.execute('SELECT file_id, expires_at FROM share_tokens WHERE token = ?', (token,)).fetchone()
    if not share:
        flash('لینک اشتراک معتبر نیست!', 'error')
        conn.close()
        return redirect(url_for('index'))
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if share['expires_at'] < current_time:
        flash('لینک اشتراک منقضی شده است!', 'error')
        conn.execute('DELETE FROM share_tokens WHERE token = ?', (token,))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    file = conn.execute('SELECT stored_filename, original_filename, user_id, symbolic_folder FROM files WHERE id = ?', 
                       (share['file_id'],)).fetchone()
    if file:
        user_folder = conn.execute('SELECT user_folder FROM users WHERE id = ?', (file['user_id'],)).fetchone()['user_folder']
        file_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder, file['symbolic_folder'], file['stored_filename'])
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=file['original_filename'])
    flash('فایل یافت نشد!', 'error')
    conn.close()
    return redirect(url_for('index'))

@app.route('/preview/<int:file_id>')
def preview(file_id):
    if 'user_id' not in session:
        return {'error': 'لطفاً ابتدا وارد شوید!'}, 401
    
    conn = get_db_connection()
    file = conn.execute('SELECT original_filename, stored_filename, mime_type, user_id, symbolic_folder FROM files WHERE id = ? AND user_id = ?', 
                       (file_id, session['user_id'])).fetchone()
    if not file:
        conn.close()
        logging.error(f"File id={file_id} not found for preview")
        return {'error': 'فایل یافت نشد!'}, 404
    
    user_folder = conn.execute('SELECT user_folder FROM users WHERE id = ?', (file['user_id'],)).fetchone()['user_folder']
    file_path = os.path.join(BASE_UPLOAD_FOLDER, user_folder, file['symbolic_folder'], file['stored_filename'])
    
    logging.debug(f"Previewing file: id={file_id}, path={file_path}")
    if os.path.exists(file_path):
        return {
            'filename': file['original_filename'],
            'mime_type': file['mime_type'],
            'url': url_for('download_file', file_id=file_id, _external=True)
        }
    conn.close()
    logging.error(f"File path not found: {file_path}")
    return {'error': 'فایل یافت نشد!'}, 404

@app.route('/share/<int:file_id>')
def share(file_id):
    if 'user_id' not in session:
        return {'error': 'لطفاً ابتدا وارد شوید!'}, 401
    
    conn = get_db_connection()
    file = conn.execute('SELECT original_filename FROM files WHERE id = ? AND user_id = ?', 
                       (file_id, session['user_id'])).fetchone()
    if not file:
        conn.close()
        return {'error': 'فایل یافت نشد!'}, 404
    
    token = str(uuid.uuid4())
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    expires_at = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('INSERT INTO share_tokens (token, file_id, created_at, expires_at) VALUES (?, ?, ?, ?)',
                (token, file_id, created_at, expires_at))
    conn.commit()
    conn.close()
    
    share_link = url_for('download_shared', token=token, _external=True)
    return {'share_link': share_link}

@app.route('/search')
def search():
    if 'user_id' not in session:
        flash('لطفاً ابتدا وارد شوید!', 'error')
        return redirect(url_for('login'))
    
    query = request.args.get('q', '')
    folder_id = request.args.get('folder_id', type=int)
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')
    
    return redirect(url_for('dashboard', folder_id=folder_id, q=query, sort_by=sort_by, sort_order=sort_order))

@app.route('/move_file/<int:file_id>/<int:folder_id>', methods=['POST'])
def move_file(file_id, folder_id):
    if 'user_id' not in session:
        return {'error': 'لطفاً ابتدا وارد شوید!'}, 401
    
    conn = get_db_connection()
    conn.execute('UPDATE files SET folder_id = ? WHERE id = ? AND user_id = ?', 
                (folder_id, file_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return {'message': 'فایل با موفقیت جابه‌جا شد!'}

@app.route('/reset_db', methods=['GET'])
def reset_db():
    try:
        conn = sqlite3.connect('database.db', timeout=10)
        conn.close()
        if os.path.exists('database.db'):
            os.remove('database.db')
        init_db()
        logging.debug("Database reset successfully")
        flash('دیتابیس با موفقیت ریست شد!', 'success')
    except Exception as e:
        logging.error(f"Error resetting database: {str(e)}")
        flash(f'خطا در ریست دیتابیس: {str(e)}', 'error')
    return redirect(url_for('index'))

@app.route('/debug_users', methods=['GET'])
def debug_users():
    try:
        conn = get_db_connection()
        users = conn.execute('SELECT id, username, user_folder, storage_limit FROM users').fetchall()
        conn.close()
        users_list = [{'id': user['id'], 'username': user['username'], 'user_folder': user['user_folder'], 'storage_limit': user['storage_limit']} for user in users]
        logging.debug(f"Users in database: {users_list}")
        return jsonify({'users': users_list})
    except Exception as e:
        logging.error(f"Error fetching users: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug_files/<int:folder_id>', methods=['GET'])
def debug_files(folder_id):
    try:
        conn = get_db_connection()
        files = conn.execute('SELECT id, original_filename, folder_id FROM files WHERE folder_id = ?', (folder_id,)).fetchall()
        conn.close()
        files_list = [{'id': file['id'], 'original_filename': file['original_filename'], 'folder_id': file['folder_id']} for file in files]
        logging.debug(f"Files in folder_id={folder_id}: {files_list}")
        return jsonify({'files': files_list})
    except Exception as e:
        logging.error(f"Error fetching files for folder_id={folder_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
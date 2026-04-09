import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'ats.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS job_description (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            text_content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS candidate (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jd_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            candidate_name TEXT,
            candidate_email TEXT,
            resume_text TEXT,
            scores_json TEXT,
            application_score INTEGER DEFAULT 0,
            overall_summary TEXT,
            recommendation TEXT,
            red_flags TEXT,
            top_strengths TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (jd_id) REFERENCES job_description(id)
        );
    ''')
    conn.commit()
    conn.close()


def save_jd(filename, text_content):
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO job_description (filename, text_content) VALUES (?, ?)',
        (filename, text_content)
    )
    jd_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jd_id


def get_jd(jd_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM job_description WHERE id = ?', (jd_id,)).fetchone()
    conn.close()
    return row


def save_candidate(jd_id, filename, resume_text):
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO candidate (jd_id, filename, resume_text) VALUES (?, ?, ?)',
        (jd_id, filename, resume_text)
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def update_candidate_text(cid, resume_text):
    conn = get_db()
    conn.execute('UPDATE candidate SET resume_text = ? WHERE id = ?', (resume_text, cid))
    conn.commit()
    conn.close()


def update_candidate_scores(cid, data):
    conn = get_db()
    conn.execute('''
        UPDATE candidate SET
            candidate_name = ?,
            candidate_email = ?,
            scores_json = ?,
            application_score = ?,
            overall_summary = ?,
            recommendation = ?,
            red_flags = ?,
            top_strengths = ?,
            status = 'completed'
        WHERE id = ?
    ''', (
        data.get('candidate_name', 'Unknown'),
        data.get('candidate_email'),
        json.dumps(data.get('scores', {})),
        data.get('application_score', 0),
        data.get('overall_summary', ''),
        data.get('recommendation', ''),
        json.dumps(data.get('red_flags', [])),
        json.dumps(data.get('top_strengths', [])),
        cid
    ))
    conn.commit()
    conn.close()


def mark_candidate_failed(cid, error_message):
    conn = get_db()
    conn.execute(
        'UPDATE candidate SET status = ?, error_message = ? WHERE id = ?',
        ('failed', error_message, cid)
    )
    conn.commit()
    conn.close()


def get_candidates(jd_id):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM candidate WHERE jd_id = ? ORDER BY application_score DESC',
        (jd_id,)
    ).fetchall()
    conn.close()
    return rows


def get_candidate(cid):
    conn = get_db()
    row = conn.execute('SELECT * FROM candidate WHERE id = ?', (cid,)).fetchone()
    conn.close()
    return row


def get_processing_status(jd_id):
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM candidate WHERE jd_id = ?', (jd_id,)).fetchone()[0]
    done = conn.execute(
        "SELECT COUNT(*) FROM candidate WHERE jd_id = ? AND status != 'pending'",
        (jd_id,)
    ).fetchone()[0]
    conn.close()
    return {'total': total, 'done': done}

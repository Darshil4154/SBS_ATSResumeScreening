import os
import json
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session

from database import init_db, save_jd, get_jd, save_candidate, update_candidate_scores, \
    mark_candidate_failed, get_candidates, get_processing_status, get_db
from parser import extract_text
from evaluator import evaluate_resume, chat_answer, CRITERIA_ORDER, CRITERIA_LABELS
from exporter import export_to_excel

app = Flask(__name__)
app.secret_key = 'ats-tamu-2026-secret-key'

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
EXPORT_DIR = os.path.join(os.path.dirname(__file__), 'exports')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

init_db()


def process_candidates_bg(jd_id):
    try:
        jd = get_jd(jd_id)
        jd_text = jd['text_content']

        conn = get_db()
        rows = conn.execute(
            "SELECT id, filename, resume_text FROM candidate WHERE jd_id = ? AND status = 'pending'",
            (jd_id,)
        ).fetchall()
        conn.close()

        total = len(rows)
        print(f"\n=== Processing {total} candidates ===", flush=True)

        for i, row in enumerate(rows):
            cid, filename, resume_text = row['id'], row['filename'], row['resume_text']
            print(f"  [{i+1}/{total}] {filename}", flush=True)
            try:
                data = evaluate_resume(jd_text, resume_text)
                update_candidate_scores(cid, data)
                print(f"    -> {data.get('candidate_name','?')}: {data['application_score']}/140", flush=True)
            except Exception as e:
                print(f"    -> FAILED: {e}", flush=True)
                mark_candidate_failed(cid, str(e))
            time.sleep(1)

        print(f"=== All {total} done ===\n", flush=True)
    except Exception as e:
        print(f"BG ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()


@app.route('/health')
def health():
    key = os.environ.get('OPENROUTER_API_KEY', '')
    has_key = 'YES' if key else 'NO'
    key_preview = key[:10] + '...' if key else 'NOT SET'
    return jsonify({'status': 'ok', 'api_key_set': has_key, 'key_preview': key_preview})


@app.route('/')
def index():
    jd_id = session.get('jd_id')
    has_results = False
    if jd_id:
        s = get_processing_status(jd_id)
        has_results = s['done'] > 0
    return render_template('index.html', has_results=has_results)


@app.route('/upload-jd', methods=['GET', 'POST'])
def upload_jd():
    if request.method == 'GET':
        return redirect(url_for('index'))
    try:
        file = request.files.get('jd_file')
        if not file or file.filename == '':
            return redirect(url_for('index'))
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        file.save(filepath)
        text = extract_text(filepath)
        jd_id = save_jd(file.filename, text)
        session['jd_id'] = jd_id
        return redirect(url_for('upload_resumes'))
    except Exception as e:
        return render_template('index.html', error=f"Error: {e}")


@app.route('/upload-resumes')
def upload_resumes():
    if 'jd_id' not in session:
        return redirect(url_for('index'))
    jd_id = session['jd_id']
    status = get_processing_status(jd_id)
    return render_template('upload.html', jd_id=jd_id, done=status['done'], total=status['total'])


@app.route('/upload-resumes-submit', methods=['GET', 'POST'])
def upload_resumes_submit():
    if request.method == 'GET':
        return redirect(url_for('index'))
    jd_id = session.get('jd_id')
    if not jd_id:
        return redirect(url_for('index'))

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        files = request.files.getlist('resume_files')
        failed = []
        for f in files:
            if f.filename == '':
                continue
            filepath = os.path.join(UPLOAD_DIR, f.filename)
            f.save(filepath)
            try:
                text = extract_text(filepath)
                if not text.strip():
                    failed.append(f.filename)
                    continue
                save_candidate(jd_id, f.filename, text)
            except Exception:
                failed.append(f.filename)

        session['parse_failures'] = failed

        thread = threading.Thread(target=process_candidates_bg, args=(jd_id,))
        thread.daemon = True
        thread.start()

        return redirect(url_for('processing'))
    except Exception as e:
        print(f"UPLOAD ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return render_template('index.html', error=f"Upload error: {e}")


@app.route('/processing')
def processing():
    jd_id = session.get('jd_id')
    if not jd_id:
        return redirect(url_for('index'))
    return render_template('processing.html', jd_id=jd_id)


@app.route('/api/status/<int:jd_id>')
def api_status(jd_id):
    return jsonify(get_processing_status(jd_id))


@app.route('/dashboard')
def dashboard():
    jd_id = session.get('jd_id')
    if not jd_id:
        return redirect(url_for('index'))

    rows = get_candidates(jd_id)
    candidates = []
    for r in rows:
        c = dict(r)
        c['scores'] = json.loads(c['scores_json']) if c['scores_json'] else {}
        c['red_flags'] = json.loads(c['red_flags']) if c['red_flags'] else []
        c['top_strengths'] = json.loads(c['top_strengths']) if c['top_strengths'] else []
        candidates.append(c)

    parse_failures = session.pop('parse_failures', [])
    return render_template('dashboard.html', candidates=candidates,
                           criteria_order=CRITERIA_ORDER, criteria_labels=CRITERIA_LABELS,
                           parse_failures=parse_failures)


@app.route('/retry')
def retry_failed():
    jd_id = session.get('jd_id')
    if not jd_id:
        return redirect(url_for('index'))
    conn = get_db()
    conn.execute("UPDATE candidate SET status='pending', error_message=NULL WHERE jd_id=? AND status='failed'", (jd_id,))
    conn.commit()
    conn.close()
    thread = threading.Thread(target=process_candidates_bg, args=(jd_id,))
    thread.daemon = True
    thread.start()
    return redirect(url_for('processing'))


@app.route('/export')
def export():
    jd_id = session.get('jd_id')
    if not jd_id:
        return redirect(url_for('index'))
    rows = get_candidates(jd_id)
    filepath, filename = export_to_excel(rows, EXPORT_DIR)
    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route('/chat')
def chat_page():
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def api_chat():
    jd_id = session.get('jd_id')
    if not jd_id:
        return jsonify({'error': 'No evaluation data yet'}), 400

    question = request.json.get('question', '').strip()
    if not question:
        return jsonify({'error': 'Empty question'}), 400

    rows = get_candidates(jd_id)
    all_data = []
    for r in rows:
        if r['status'] != 'completed':
            continue
        all_data.append({
            'candidate_name': r['candidate_name'],
            'candidate_email': r['candidate_email'],
            'application_score': r['application_score'],
            'overall_summary': r['overall_summary'],
            'scores': json.loads(r['scores_json']) if r['scores_json'] else {},
            'red_flags': json.loads(r['red_flags']) if r['red_flags'] else [],
            'top_strengths': json.loads(r['top_strengths']) if r['top_strengths'] else [],
        })

    try:
        answer = chat_answer(question, all_data)
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, port=5000)

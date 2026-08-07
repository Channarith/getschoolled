"""Embedded Course Studio dashboard (review + teach)."""

from __future__ import annotations

STUDIO_CSS = """

  body { margin:0; font-family: Georgia, 'Times New Roman', serif; background:#14201a; color:#e8efe9; }
  header { padding:18px 22px; background:linear-gradient(120deg,#1b3a2f,#0f1c18 60%);
           border-bottom:1px solid #2f5a48; }
  header h1 { margin:0; font-size:28px; letter-spacing:0.02em; }
  header p { margin:6px 0 0; color:#a7c4b5; font-size:14px; max-width:52rem; }
  .layout { display:grid; grid-template-columns: 1.1fr 1fr; gap:14px; padding:14px; }
  @media (max-width: 980px) { .layout { grid-template-columns: 1fr; } }
  .panel { background:#18261f; border:1px solid #2f5a48; border-radius:10px; padding:12px; }
  .panel h2 { margin:0 0 8px; font-size:16px; color:#9fddc0; }
  .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:6px 0; }
  button, select, input, textarea { font: inherit; }
  button { background:#216b4f; color:#f4fff8; border:1px solid #3d9a74; border-radius:6px;
           padding:6px 10px; cursor:pointer; }
  button.secondary { background:#24352c; border-color:#3a5548; }
  button.danger { background:#6b2121; border-color:#9a3d3d; }
  select, input { background:#0f1a15; color:#e8efe9; border:1px solid #3a5548; border-radius:6px;
                  padding:5px 8px; }
  textarea { width:100%; min-height:72px; background:#0f1a15; color:#e8efe9;
             border:1px solid #3a5548; border-radius:6px; padding:8px; }
  .pill { font-size:11px; padding:2px 8px; border-radius:999px; border:1px solid #3a5548; background:#20332a; }
  .pill.good { background:#1d4d35; border-color:#3d9a74; }
  .pill.bad { background:#4d1d1d; border-color:#9a3d3d; }
  .pill.moderate { background:#4d3d1d; border-color:#9a7d3d; }
  .list { max-height:280px; overflow:auto; font-size:13px; }
  .item { padding:8px; border-bottom:1px solid #24362d; cursor:pointer; }
  .item:hover, .item.active { background:#21362c; }
  .item .meta { color:#9bb5a8; font-size:11px; margin-top:2px; }
  .pages { max-height:220px; overflow:auto; }
  .page { display:flex; gap:8px; align-items:flex-start; padding:6px 0; border-bottom:1px solid #24362d; }
  .page.rejected { opacity:0.55; text-decoration: line-through; }
  .comments { max-height:180px; overflow:auto; font-size:12px; }
  .comment { padding:6px 0; border-bottom:1px solid #24362d; }
    .teach-stage { min-height:220px; background:#0f1a15; border:1px solid #3a5548; border-radius:8px; padding:14px;
                   animation: fadeUp 0.65s ease; }
    .teach-stage.anim { animation: fadeUp 0.65s ease; }
    @keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:none; } }
    .teach-stage h3 { margin:0 0 8px; font-size:22px; }
    .teach-stage .body { font-size:15px; line-height:1.45; color:#d7e6dc; }
    .teach-stage .narr { margin-top:12px; color:#9fddc0; font-style:italic; }
    .quiz-box, .game-box { margin-top:10px; padding:10px; border:1px dashed #3a5548; border-radius:8px; background:#13201a; }
    .quiz-box button, .game-box button { display:block; width:100%; text-align:left; margin:4px 0; }
  .status { font-size:12px; color:#9bb5a8; min-height:16px; }
  .toast { position:fixed; right:14px; bottom:14px; background:#1b3a2f; border:1px solid #3d9a74;
           padding:10px 12px; border-radius:8px; display:none; max-width:360px; }
  .toast.show { display:block; }

"""

STUDIO_JS = """

    const $ = (id) => document.getElementById(id);
    let selectedSource = null;
    let selectedCourse = null;
    let teachSession = 'studio-teach-1';
    let pagesCache = [];

    function toast(msg) {
      const el = $('toast');
      el.textContent = msg;
      el.classList.add('show');
      setTimeout(() => el.classList.remove('show'), 3200);
    }
    function esc(s) {
      return String(s ?? '').replace(/[&<>"']/g, (c) => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
      })[c]);
    }
    function qualityPill(q) {
      const cls = ({good:'good', better:'good', bad:'bad', moderate:'moderate'}[q] || '');
      return `<span class="pill ${cls}">${esc(q)}</span>`;
    }

    async function api(path, opts) {
      const res = await fetch(path, opts);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText || 'request failed');
      return data;
    }

    async function refreshCorpus() {
      const data = await api('/api/studio/corpus');
      const box = $('corpus-list');
      box.innerHTML = (data.documents || []).map((d) => `
        <div class="item" data-id="${esc(d.source_id)}">
          <div><strong>${esc(d.title_guess || d.filename)}</strong> ${qualityPill(d.quality_label)}
            ${d.incorporate ? '<span class="pill good">incorporate</span>' : ''}</div>
          <div class="meta">${esc(d.category)} · ${esc(d.ext)} · ${esc(d.filename)}</div>
        </div>`).join('') || '<div class="item">No corpus yet — run training scan.</div>';
      box.querySelectorAll('.item[data-id]').forEach((el) => {
        el.onclick = () => selectSource(el.getAttribute('data-id'));
      });
      $('corpus-stats').textContent =
        `${data.count || 0} docs · incorporate ${data.incorporate_count || 0} · reject ${data.reject_count || 0}`;
    }

    async function selectSource(id) {
      selectedSource = id;
      $('corpus-list').querySelectorAll('.item').forEach((el) => {
        el.classList.toggle('active', el.getAttribute('data-id') === id);
      });
      const data = await api('/api/studio/sources/' + encodeURIComponent(id));
      $('source-title').textContent = data.document.title_guess || data.document.filename;
      $('source-meta').innerHTML = qualityPill(data.document.quality_label) +
        ` <span class="pill">${esc(data.document.category)}</span>`;
      pagesCache = data.pages || [];
      renderPages();
      renderComments(data.comments || []);
    }

    function renderPages() {
      const box = $('page-list');
      box.innerHTML = pagesCache.map((p) => `
        <div class="page ${p.marked_reject ? 'rejected' : ''}">
          <div style="flex:1">
            <div><strong>p${p.index + 1}</strong> ${esc(p.title)}</div>
            <div class="meta">${esc((p.text || '').slice(0, 160))}</div>
          </div>
          <button class="secondary" data-like="${p.index}">Keep</button>
          <button class="danger" data-reject="${p.index}">Reject ⌀</button>
        </div>`).join('') || '<div class="meta">No pages extracted (install pypdf / python-pptx).</div>';
      box.querySelectorAll('[data-like]').forEach((b) => b.onclick = () => markPage(+b.dataset.like, false));
      box.querySelectorAll('[data-reject]').forEach((b) => b.onclick = () => markPage(+b.dataset.reject, true));
    }

    async function markPage(pageIndex, reject) {
      if (!selectedSource) return;
      await api('/api/studio/pages/verdict', {
        method: 'POST', headers: {'content-type':'application/json'},
        body: JSON.stringify({ source_id: selectedSource, page_index: pageIndex, marked_reject: reject })
      });
      const p = pagesCache.find((x) => x.index === pageIndex);
      if (p) p.marked_reject = reject;
      renderPages();
      toast(reject ? 'Page marked reject (circle+line style)' : 'Page kept');
    }

    function renderComments(rows) {
      $('comment-list').innerHTML = rows.map((c) => `
        <div class="comment"><strong>${esc(c.author)}</strong>
          ${c.page_index != null ? ' · p'+(c.page_index+1) : ''}
          <div>${esc(c.body)}</div></div>`).join('') || '<div class="meta">No comments yet.</div>';
    }

    async function postComment() {
      if (!selectedSource) return toast('Select a source first');
      const body = $('comment-body').value.trim();
      if (!body) return;
      const pageRaw = $('comment-page').value.trim();
      const page_index = pageRaw === '' ? null : Math.max(0, parseInt(pageRaw, 10) - 1);
      await api('/api/studio/comments', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ source_id: selectedSource, body, page_index, author: 'reviewer' })
      });
      $('comment-body').value = '';
      const data = await api('/api/studio/sources/' + encodeURIComponent(selectedSource));
      renderComments(data.comments || []);
      toast('Comment saved for training');
    }

    async function runTraining() {
      $('train-status').textContent = 'Scanning corpus…';
      const data = await api('/api/studio/training/run', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ extract_text: true, seed_page_hints: true })
      });
      $('train-status').textContent =
        `Run ${data.run_id}: scanned ${data.documents_scanned}, incorporate ${data.incorporate_ids.length}, reject ${data.reject_ids.length}, review queue ${data.review_queue_ids.length}`;
      await refreshCorpus();
      await refreshCourses();
      toast('Training run complete');
    }

    async function runOfflineTrainer() {
      $('train-status').textContent = 'Offline trainer running (no network)…';
      const data = await api('/api/studio/training/offline', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ epochs: 25, run_scan: true, fit_passes: 2 })
      });
      $('train-status').textContent =
        `Offline ${data.run_id}: epochs ${data.epoch}, best ${Number(data.best_course_score || 0).toFixed(3)}, ${data.status}`;
      await refreshCourses();
      toast('Offline trainer finished — course builds now use the learned model');
    }

    async function buildCourse() {
      const category = $('build-category').value;
      const title = $('build-title').value.trim() || null;
      const data = await api('/api/studio/courses/build', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ category: category || null, title, max_slides: 20, only_incorporate: true })
      });
      selectedCourse = data.course_id;
      await refreshCourses();
      toast('Course built: ' + data.course_id);
    }

    async function refreshCourses() {
      const data = await api('/api/studio/courses');
      const box = $('course-list');
      box.innerHTML = (data.courses || []).map((c) => `
        <div class="item" data-cid="${esc(c.course_id)}">
          <div><strong>${esc(c.title)}</strong> <span class="pill">${esc(c.category)}</span></div>
          <div class="meta">${esc(c.course_id)} · ${c.slides.length} slides · ${esc(c.status)}</div>
        </div>`).join('') || '<div class="item">No courses yet.</div>';
      box.querySelectorAll('.item[data-cid]').forEach((el) => {
        el.onclick = () => { selectedCourse = el.getAttribute('data-cid'); startTeach(); };
      });
    }

    function profileFromForm() {
      return {
        engagement: +$('pf-engagement').value,
        literacy: +$('pf-literacy').value,
        attention: +$('pf-attention').value,
        fatigue: +$('pf-fatigue').value,
        confusion: +$('pf-confusion').value,
        pace_preference: +$('pf-pace').value,
        accessibility_need: +$('pf-access').value,
      };
    }

    async function startTeach() {
      if (!selectedCourse) return toast('Select or build a course first');
      const data = await api('/api/studio/teach/start', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          session_id: teachSession, course_id: selectedCourse, profile: profileFromForm(),
          focus_gaps: true, known_objective_ids: []
        })
      });
      renderTeach(data);
      toast('Theodore teaching session started (gap-focused path)');
    }

    async function nextSlide() {
      const data = await api('/api/studio/teach/advance', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      renderTeach(data);
    }

    async function applyProfile() {
      const data = await api('/api/studio/teach/profile', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession, profile: profileFromForm() })
      });
      renderTeach(data);
      toast('Profile adaptations applied');
    }

    let pendingPop = null;
    let pendingGame = null;

    async function popQuiz() {
      pendingPop = await api('/api/studio/teach/pop-quiz', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      const box = $('quiz-box');
      box.style.display = 'block';
      box.innerHTML = `<strong>${esc(pendingPop.prompt)}</strong>` +
        (pendingPop.choices || []).map((c, i) =>
          `<button type="button" data-i="${i}">${esc(c)}</button>`).join('');
      box.querySelectorAll('button[data-i]').forEach((b) => {
        b.onclick = async () => {
          const res = await api('/api/studio/teach/pop-answer', {
            method:'POST', headers:{'content-type':'application/json'},
            body: JSON.stringify({ session_id: teachSession, selected_index: +b.dataset.i })
          });
          toast(res.result.passed ? 'Pop quiz correct' : 'Pop quiz missed — path updated');
          box.style.display = 'none';
          renderTeach(res.turn);
        };
      });
    }

    async function summaryQuiz() {
      const quiz = await api('/api/studio/teach/summary-quiz', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      const answers = {};
      for (const q of (quiz.questions || [])) {
        const choice = window.prompt(q.prompt + '\\n\\n' + q.choices.map((c,i)=>`${i+1}. ${c}`).join('\\n'));
        const idx = Math.max(0, (parseInt(choice || '1', 10) || 1) - 1);
        answers[q.question_id] = idx;
      }
      const graded = await api('/api/studio/teach/summary-grade', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession, answers })
      });
      toast(graded.passed
        ? `Summary passed ${graded.correct}/${graded.total}`
        : `Summary needs work ${graded.correct}/${graded.total} — review weak points`);
    }

    async function playGame() {
      pendingGame = await api('/api/studio/teach/game', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      const box = $('game-box');
      box.style.display = 'block';
      const opts = (pendingGame.payload && pendingGame.payload.options) || [];
      box.innerHTML = `<strong>${esc(pendingGame.prompt)}</strong>` +
        opts.map((c, i) => `<button type="button" data-i="${i}">${esc(c)}</button>`).join('');
      box.querySelectorAll('button[data-i]').forEach((b) => {
        b.onclick = async () => {
          const res = await api('/api/studio/teach/game-grade', {
            method:'POST', headers:{'content-type':'application/json'},
            body: JSON.stringify({
              session_id: teachSession,
              challenge: pendingGame,
              response: { selected_index: +b.dataset.i }
            })
          });
          toast(res.feedback || (res.passed ? 'Game passed' : 'Try again'));
          box.style.display = 'none';
        };
      });
    }

    function renderTeach(payload) {
      const turn = payload.turn || payload;
      const stage = $('teach-stage');
      stage.classList.remove('anim');
      void stage.offsetWidth;
      stage.classList.add('anim');
      $('teach-title').textContent = turn.title || '—';
      $('teach-body').textContent = turn.display_body || '';
      $('teach-narr').textContent = 'Theodore: ' + (turn.narration || '');
      const adapt = (turn.adaptations_applied || []).join(', ') || 'no adaptations';
      const prog = payload.progress || {};
      const obj = payload.objective ? payload.objective.title : '';
      $('teach-adapt').textContent =
        `${adapt} · focus: ${esc(obj)} · known ${prog.known || 0} / gaps ${prog.gaps || 0}`;
      if (window.speechSynthesis && $('auto-speak').checked) {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(turn.narration || turn.display_body || '');
        window.speechSynthesis.speak(u);
      }
    }

    $('btn-train').onclick = () => runTraining().catch((e) => toast(String(e.message || e)));
    $('btn-offline').onclick = () => runOfflineTrainer().catch((e) => toast(String(e.message || e)));
    $('btn-comment').onclick = () => postComment().catch((e) => toast(String(e.message || e)));
    $('btn-build').onclick = () => buildCourse().catch((e) => toast(String(e.message || e)));
    $('btn-teach').onclick = () => startTeach().catch((e) => toast(String(e.message || e)));
    $('btn-next').onclick = () => nextSlide().catch((e) => toast(String(e.message || e)));
    $('btn-profile').onclick = () => applyProfile().catch((e) => toast(String(e.message || e)));
    $('btn-pop').onclick = () => popQuiz().catch((e) => toast(String(e.message || e)));
    $('btn-summary').onclick = () => summaryQuiz().catch((e) => toast(String(e.message || e)));
    $('btn-game').onclick = () => playGame().catch((e) => toast(String(e.message || e)));

    refreshCorpus().catch(() => {});
    refreshCourses().catch(() => {});

"""

def render_studio_page() -> str:
    return (
        """<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1" />\n  <title>Theodore Course Studio</title>\n  <style>\n"""
        + STUDIO_CSS
        + """</style>
</head>
<body>
  <header>
    <h1>Theodore Course Studio</h1>
    <p>Experiment lab for labeled corpus training (Good/Bad/Moderate), page-level reject marks,
       review comments, course generation, and Theodore teach/present with learner-profile scoring.
       Learnings here are meant to graduate into the main web/mobile app later.</p>
  </header>
  <div class="layout">
    <div class="panel">
      <h2>1. Labeled corpus</h2>
      <div class="row">
        <button id="btn-train" type="button">Run training scan</button>
        <button id="btn-offline" class="secondary" type="button">Offline long trainer</button>
        <span class="status" id="train-status"></span>
      </div>
      <div class="status" id="corpus-stats"></div>
      <div class="list" id="corpus-list"></div>

      <h2>2. Page review (circle+line = reject)</h2>
      <div id="source-title">Select a document</div>
      <div id="source-meta" class="row"></div>
      <div class="pages" id="page-list"></div>

      <h2>3. Training comments</h2>
      <div class="row">
        <label>Page # <input id="comment-page" style="width:4rem" placeholder="opt" /></label>
      </div>
      <textarea id="comment-body" placeholder="What should Theodore learn from this page or source?"></textarea>
      <div class="row"><button id="btn-comment" type="button">Save comment</button></div>
      <div class="comments" id="comment-list"></div>
    </div>

    <div class="panel">
      <h2>4. Build course from Good/Better</h2>
      <div class="row">
        <select id="build-category">
          <option value="">any category</option>
          <option value="communication">communication</option>
          <option value="leadership">leadership</option>
          <option value="sexual_harassment">sexual_harassment</option>
        </select>
        <input id="build-title" placeholder="Course title (optional)" style="min-width:14rem" />
        <button id="btn-build" type="button">Build course</button>
      </div>
      <div class="list" id="course-list"></div>

      <h2>5. Theodore teach / present</h2>
      <div class="teach-stage" id="teach-stage">
        <h3 id="teach-title">—</h3>
        <div class="body" id="teach-body">Build or select a course, then Start teach.</div>
        <div class="narr" id="teach-narr"></div>
        <div class="status" id="teach-adapt"></div>
        <div class="quiz-box" id="quiz-box" style="display:none"></div>
        <div class="game-box" id="game-box" style="display:none"></div>
      </div>
      <div class="row">
        <button id="btn-teach" type="button">Start teach</button>
        <button id="btn-next" class="secondary" type="button">Next slide</button>
        <button id="btn-pop" class="secondary" type="button">Pop quiz</button>
        <button id="btn-summary" class="secondary" type="button">Summary quiz</button>
        <button id="btn-game" class="secondary" type="button">Play game</button>
        <label class="pill"><input id="auto-speak" type="checkbox" checked /> auto speak</label>
      </div>
      <h2>Learner profile scoring</h2>
      <div class="row">
        <label>engage <input id="pf-engagement" type="number" min="0" max="1" step="0.05" value="0.7" style="width:4rem"/></label>
        <label>literacy <input id="pf-literacy" type="number" min="0" max="1" step="0.05" value="0.6" style="width:4rem"/></label>
        <label>attention <input id="pf-attention" type="number" min="0" max="1" step="0.05" value="0.7" style="width:4rem"/></label>
        <label>fatigue <input id="pf-fatigue" type="number" min="0" max="1" step="0.05" value="0.2" style="width:4rem"/></label>
        <label>confusion <input id="pf-confusion" type="number" min="0" max="1" step="0.05" value="0.2" style="width:4rem"/></label>
        <label>pace <input id="pf-pace" type="number" min="0" max="1" step="0.05" value="0.5" style="width:4rem"/></label>
        <label>access <input id="pf-access" type="number" min="0" max="1" step="0.05" value="0.3" style="width:4rem"/></label>
        <button id="btn-profile" class="secondary" type="button">Apply profile</button>
      </div>
    </div>
  </div>
  <div class="toast" id="toast"></div>
  <script>"""
        + STUDIO_JS
        + """\n</script>\n</body>\n</html>\n"""
    )

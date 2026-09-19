/* smauto testing console — vanilla JS, no build step */

const $ = (sel) => document.querySelector(sel);
let lastBody = '';
// ── DOM refs ─────────────────────────────────────────────────────────────
const els = {
  topic:        $('#topic'),
  generateBtn:  $('#generate-btn'),
  formCard:     $('#form-card'),

  statusCard:   $('#status-card'),
  spinner:      $('#spinner'),
  statusText:   $('#status-text'),
  progressBar:  $('#progress-bar'),
  runIdLine:    $('#run-id-line'),

  resultCard:   $('#result-card'),
  hook:         $('#hook'),
  postBody:     $('#post-body'),
  hashtags:     $('#hashtags'),
  hashtagsField:$('#hashtags-field'),
  imagesField:  $('#images-field'),
  images:       $('#images'),
  qaSummary:    $('#qa-summary'),

  approveBtn:   $('#approve-btn'),
  rejectBtn:    $('#reject-btn'),

  finalCard:    $('#final-card'),
  finalBody:    $('#final-body'),
  resetBtn:     $('#reset-btn'),

  errorCard:    $('#error-card'),
  errorText:    $('#error-text'),
  errorDismiss: $('#error-dismiss'),
    editBtn:      $('#edit-btn'),
  editPanel:    $('#edit-panel'),
  editFeedback: $('#edit-feedback'),
  applyEditBtn: $('#apply-edit-btn'),
  cancelEditBtn:$('#cancel-edit-btn'),
  editHint:     $('#edit-hint'),

  previousField: $('#previous-field'),
  previousBody:  $('#previous-body'),
};

// ── state ────────────────────────────────────────────────────────────────
let currentRunId = null;

// ── helpers ──────────────────────────────────────────────────────────────
function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function setStatus(text, progress, state = 'running') {
  els.statusText.textContent = text;
  els.progressBar.style.width = `${progress}%`;
  els.spinner.className = 'spinner';
  if (state === 'done')  els.spinner.classList.add('done');
  if (state === 'error') els.spinner.classList.add('error');
}

function showError(msg) {
  els.errorText.textContent = msg;
  show(els.errorCard);
  setStatus('Failed', 100, 'error');
}

async function api(path, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  // Add a cache-buster for GETs so the browser always hits the server
  const url = method === 'GET'
    ? path + (path.includes('?') ? '&' : '?') + '_t=' + Date.now()
    : path;

  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',           // ← the fix
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text.slice(0, 400)}`);
  }
  return res.json();
}

function platformOf(bodyKeys) {
  // bodyKeys is an array of platform names, e.g. ['facebook']
  return bodyKeys[0] || 'text';
}

function imageUrl(runId, path) {
  // path may be "runs\\abc\\images\\slide_00.png" or a POSIX variant
  const filename = path.split(/[/\\]/).pop();
  return `/runs/${runId}/images/${filename}`;
}

// ── flow ─────────────────────────────────────────────────────────────────

async function generate() {
  const topic = els.topic.value.trim();
  if (topic.length < 4) {
    showError('Please enter a longer topic (at least 4 characters).');
    return;
  }

  const contentType = document.querySelector('input[name=ctype]:checked').value;
  const platforms = Array.from(document.querySelectorAll('.checks input:checked'))
                         .map((c) => c.value);

  if (platforms.length === 0) {
    showError('Pick at least one platform.');
    return;
  }

  // reset UI
  hide(els.resultCard);
  hide(els.finalCard);
  hide(els.errorCard);
  show(els.statusCard);
  els.generateBtn.disabled = true;

  setStatus('Starting run…', 5);
  els.runIdLine.textContent = '';

  try {
    // Step 1 — create run (this blocks until the graph hits the approval pause)
    setStatus('Running pipeline… (this may take 1–3 minutes)', 15);

    const created = await api('/runs', {
      method: 'POST',
      body: JSON.stringify({
        request: topic,
        content_type: contentType,
        platforms: platforms,
      }),
    });

    currentRunId = created.run_id;
    els.runIdLine.textContent = `run_id: ${currentRunId}`;

    // Step 2 — fetch full state
    setStatus('Fetching result…', 80);

    const status = await api(`/runs/${currentRunId}`);

    // Step 3 — render result
    renderResult(currentRunId, status);

    if (status.status === 'awaiting_approval') {
      setStatus('Awaiting your approval', 100, 'done');
      show(els.resultCard);
    } else if (status.status === 'escalated') {
      setStatus('Run escalated (see QA below)', 100, 'error');
      show(els.resultCard);
    } else {
      setStatus('Run finished without approval step', 100, 'done');
      show(els.resultCard);
    }

  } catch (err) {
    console.error(err);
    showError(err.message);
  } finally {
    els.generateBtn.disabled = false;
  }
}

function renderResult(runId, status) {
  const state = status.state || {};
  const ts = state.text_state || {};
  const vs = state.video_state || {};
  const strategy = state.strategy || {};

  // hook
  const hook = strategy.hook || (ts.draft && ts.draft.hook) || '';
  els.hook.textContent = hook || '(no hook)';

  // post body — first platform body wins; fall back to video caption
  const bodies = ts.platform_bodies || {};
  const platformKeys = Object.keys(bodies);
  let body = '';
  if (platformKeys.length) {
    body = bodies[platformKeys[0]];
  } else if (vs.caption) {
    body = vs.caption;
  } else if (ts.draft) {
    const d = ts.draft;
    body = [d.hook, d.body, d.cta].filter(Boolean).join('\n\n');
  } else {
    body = '(no post content)';
  }
    // show the previous version, only if it differs
  if (lastBody && lastBody !== body) {
    els.previousBody.textContent = lastBody;
    show(els.previousField);
  } else {
    hide(els.previousField);
  }
  lastBody = body;
  els.postBody.textContent = body;

  // hashtags
  const tags = ts.hashtags || vs.hashtags || [];
  if (tags.length) {
    els.hashtags.textContent = tags.join(' ');
    show(els.hashtagsField);
  } else {
    hide(els.hashtagsField);
  }

  // images
  const imgs = (ts.image_paths || vs.thumbnail_paths || []);
if (imgs.length) {
  els.images.innerHTML = '';
  imgs.forEach((p) => {
    const img = document.createElement('img');
    const base = imageUrl(runId, p);                                 // ← NEW line 1
    img.src = base + '?v=' + Date.now();                             // ← CHANGED line A
    img.alt = 'generated';
    img.loading = 'lazy';
    img.onclick = () => window.open(base, '_blank');                 // ← CHANGED line B
    els.images.appendChild(img);
  });
  show(els.imagesField);
} else {
  hide(els.imagesField);
}
  // QA summary
  const qa = state.qa || {};
  const passed = qa.passed;
  const failures = qa.failures || [];
  let summary = passed
    ? `✅ Passed — ${state.revision_count || 0} revision(s)`
    : `⚠️ Failed — ${failures.length} issue(s)`;
  els.qaSummary.textContent = summary;
  els.qaSummary.style.color = passed ? 'var(--success)' : 'var(--danger)';

  // determine label used in the images alt / hook — useful for debugging
  document.title = `smauto — ${runId}`;
}

async function approve(status) {
  if (!currentRunId) return;

  els.approveBtn.disabled = true;
  els.rejectBtn.disabled = true;
  setStatus(status === 'approved' ? 'Publishing…' : 'Rejecting…', 90);

  try {
    const res = await api(`/runs/${currentRunId}/approve`, {
      method: 'POST',
      body: JSON.stringify({
        status: status,
        editor: 'web-ui',
        notes: '',
      }),
    });

    // fetch fresh state to see publish results
    const final = await api(`/runs/${currentRunId}`);
    renderFinal(status, final);

    hide(els.resultCard);
    show(els.finalCard);
    setStatus(status === 'approved' ? 'Published' : 'Rejected', 100, 'done');

  } catch (err) {
    console.error(err);
    showError(err.message);
  } finally {
    els.approveBtn.disabled = false;
    els.rejectBtn.disabled = false;
  }
}

function renderFinal(decision, statusResp) {
  const state = statusResp.state || {};
  const results = state.publish_results || [];

  if (decision === 'rejected') {
    els.finalBody.innerHTML = '<p>Post rejected. Nothing was published.</p>';
    return;
  }

  if (!results.length) {
    els.finalBody.innerHTML = '<p>Approved — no publish results returned.</p>';
    return;
  }

  const rows = results.map((r) => {
    const ok = r.status === 'ok';
    const icon = ok ? '✅' : '❌';
    const url = r.url ? `<a href="${r.url}" target="_blank">${r.url}</a>` : (r.error || '');
    return `<li>${icon} <strong>${r.platform}</strong> — ${url}</li>`;
  }).join('');

  els.finalBody.innerHTML = `<ul>${rows}</ul>`;
}

function reset() {
  currentRunId = null;
  els.topic.value = '';
  hide(els.resultCard);
  hide(els.statusCard);
  hide(els.finalCard);
  hide(els.errorCard);
  document.title = 'smauto — testing console';
}

// ── wire up ──────────────────────────────────────────────────────────────
els.generateBtn.addEventListener('click', generate);
els.approveBtn.addEventListener('click', () => approve('approved'));
els.rejectBtn.addEventListener('click', () => approve('rejected'));
els.resetBtn.addEventListener('click', reset);
els.errorDismiss.addEventListener('click', () => hide(els.errorCard));

// ── edit flow ─────────────────────────────────────────────────────────
els.editBtn.addEventListener('click', () => {
  show(els.editPanel);
  els.editFeedback.focus();
});

els.cancelEditBtn.addEventListener('click', () => {
  hide(els.editPanel);
  els.editFeedback.value = '';
  els.editHint.textContent = '';
});

els.applyEditBtn.addEventListener('click', async () => {
  const feedback = els.editFeedback.value.trim();
  if (feedback.length < 2) {
    els.editHint.textContent = 'Please describe what to change.';
    els.editHint.style.color = 'var(--danger)';
    return;
  }
  if (!currentRunId) return;

  els.applyEditBtn.disabled = true;
  els.editHint.style.color = 'var(--muted)';
  els.editHint.textContent = 'Applying your edit… (30–90 sec)';

  try {
    await api(`/runs/${currentRunId}/edit`, {
      method: 'POST',
      body: JSON.stringify({ feedback: feedback, editor: 'web-ui' }),
    });

    // fetch refreshed state
    const fresh = await api(`/runs/${currentRunId}`);

    // re-render the result card with the new post
    renderResult(currentRunId, fresh);

    hide(els.editPanel);
    els.editFeedback.value = '';
    els.editHint.textContent = '';

    if (fresh.status === 'awaiting_approval') {
      setStatus('Updated — awaiting your approval', 100, 'done');
      show(els.resultCard);
    } else {
      setStatus('Updated — QA did not pass; edit again or reject', 100, 'done');
      show(els.resultCard);
    }

  } catch (err) {
    console.error(err);
    els.editHint.style.color = 'var(--danger)';
    els.editHint.textContent = err.message;
  } finally {
    els.applyEditBtn.disabled = false;
  }
});
els.errorDismiss.addEventListener('click', () => hide(els.errorCard));

// ctrl+enter to generate
els.topic.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
});
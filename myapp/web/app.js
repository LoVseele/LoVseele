
(function () {
  'use strict';

  /** 全局状态 */
  const state = {
    problems: [],        // 当前展示的题目（最多 previewLimit 条）
    exerciseText: '',    // 完整题目文本（可能包含全部 n 道）
    answerText: '',      // 完整答案文本
    generatedCount: 0,
    showAnswers: false,
    graded: false,
  };

  const ANSWER_TYPE_COLORS = { '整数': '#4f46e5', '真分数': '#0d9488', '带分数': '#d97706' };
  const OPERATOR_COLORS = { '+': '#3b82f6', '-': '#0d9488', '×': '#d97706', '÷': '#e11d48' };

  const $ = (id) => document.getElementById(id);


  function toast(message) {
    const node = $('toast');
    node.textContent = message;
    node.hidden = false;
    requestAnimationFrame(() => node.classList.add('is-visible'));
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
      node.classList.remove('is-visible');
      setTimeout(() => { node.hidden = true; }, 220);
    }, 2000);
  }

  async function postJSON(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    let data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    if (!response.ok) {
      const message = (data && data.error) ? data.error : `请求失败（HTTP ${response.status}）`;
      throw new Error(message);
    }
    return data;
  }

  function setBusy(button, busy) {
    const spinner = button.querySelector('.spinner');
    if (spinner) { spinner.hidden = !busy; }
    button.disabled = busy;
  }

  function showAlert(id, message) {
    const node = $(id);
    if (!message) { node.hidden = true; node.textContent = ''; return; }
    node.textContent = message;
    node.hidden = false;
  }

  function params() {
    return {
      n: Math.max(1, parseInt($('input-count').value || '10', 10)),
      r: Math.max(1, parseInt($('input-range').value || '10', 10)),
      maxOperators: parseInt($('input-ops').value || '3', 10),
    };
  }


  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((item) => item.classList.remove('is-active'));
      document.querySelectorAll('.panel').forEach((item) => item.classList.remove('is-active'));
      tab.classList.add('is-active');
      $(`panel-${tab.dataset.tab}`).classList.add('is-active');
    });
  });


  document.querySelectorAll('.presets').forEach((group) => {
    group.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-value]');
      if (!button) { return; }
      $(group.dataset.target).value = button.dataset.value;
    });
  });


  $('button-generate').addEventListener('click', async () => {
    const button = $('button-generate');
    const p = params();
    showAlert('generate-error', '');
    showAlert('generate-warn', '');
    setBusy(button, true);
    button.querySelector('.label').textContent = '生成中…';

    try {
      const data = await postJSON('/api/generate', {
        n: p.n, r: p.r, maxOperators: p.maxOperators,
      });
      state.problems = data.problems || [];
      state.exerciseText = data.exerciseText || '';
      state.answerText = data.answerText || '';
      state.generatedCount = data.stats.count;
      state.graded = false;
      state.showAnswers = false;

      renderResult(data);
      $('result-area').hidden = false;
      $('empty-state').hidden = true;
      ['button-toggle-answers', 'button-self-grade', 'button-download-exercise',
        'button-download-answer'].forEach((id) => {
        $(id).disabled = false;
      });
      $('button-toggle-answers').textContent = '显示答案';

      if (data.stats.exhausted) {
        showAlert('generate-warn',
          `受 -r ${p.r} 限制，合法且互不重复的题目最多只能生成 ${data.stats.count} 道，少于请求的 ${p.n} 道。`);
      }
      toast(`已生成 ${data.stats.count} 道题目`);
    } catch (error) {
      showAlert('generate-error', error.message);
    } finally {
      setBusy(button, false);
      button.querySelector('.label').textContent = '生成题目';
    }
  });

  function renderResult(data) {
    const stats = data.stats;
    const totalOperators = Object.values(stats.operator_distribution)
      .reduce((sum, value) => sum + value, 0);

    const cards = [
      { label: '题目个数', value: stats.count, unit: '道' },
      { label: '平均运算符个数', value: stats.average_operators, unit: '个' },
      { label: '运算符总数', value: totalOperators, unit: '个' },
      { label: '去重后唯一题目', value: stats.count, unit: '道' },
      { label: '生成耗时', value: (data.elapsed * 1000).toFixed(1), unit: 'ms' },
    ];

    $('stat-grid').innerHTML = cards.map((card) => `
      <div class="stat-card">
        <span class="stat-card__label">${card.label}</span>
        <span class="stat-card__value">${card.value}<small>${card.unit}</small></span>
      </div>`).join('');

    renderOperatorChart(stats.operator_distribution, totalOperators);
    renderAnswerChart(stats.answer_type_distribution, stats.count);

    const rows = state.problems.map((item) => `
      <tr data-index="${item.index}">
        <td class="cell-index">${item.index}</td>
        <td class="cell-expression">${escapeHtml(item.display)}</td>
        <td><input class="answer-input" data-index="${item.index}" type="text"
                   placeholder="输入答案" autocomplete="off" spellcheck="false"></td>
        <td class="cell-answer" data-role="answer-cell" hidden>${escapeHtml(item.answer)}</td>
        <td class="verdict verdict--idle" data-role="verdict">—</td>
      </tr>`).join('');

    $('problem-tbody').innerHTML = rows;
    $('self-grade-summary').hidden = true;

    const shown = state.problems.length;
    $('table-hint').textContent = shown < state.generatedCount
      ? `当前展示前 ${shown} / ${state.generatedCount} 道（完整内容已写入文件）`
      : `共 ${shown} 道`;
    $('table-note').hidden = shown >= state.generatedCount;
    $('table-note').textContent = shown < state.generatedCount
      ? `为避免页面卡顿，表格只渲染前 ${shown} 道题目；Exercises.txt / Answers.txt 中包含完整的 ${state.generatedCount} 道。`
      : '';

    document.querySelectorAll('.answer-input').forEach((input) => {
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') { runSelfGrade(); }
      });
    });
  }

  function renderOperatorChart(distribution, total) {
    const entries = Object.entries(distribution);
    const max = Math.max(1, ...entries.map(([, value]) => value));
    $('chart-operators').innerHTML = entries.map(([op, count]) => {
      const percent = total ? ((count / total) * 100).toFixed(1) : '0.0';
      const width = (count / max) * 100;
      return `
        <div class="bar-row">
          <span class="bar-row__label" style="color:${OPERATOR_COLORS[op]}">${op}</span>
          <span class="bar-track">
            <span class="bar-fill" style="width:${width}%;background:${OPERATOR_COLORS[op]}"></span>
          </span>
          <span class="bar-row__value">${count} · ${percent}%</span>
        </div>`;
    }).join('');
  }

  function renderAnswerChart(distribution, total) {
    const entries = Object.entries(distribution);
    let accumulated = 0;
    const stops = entries.map(([name, count]) => {
      const start = total ? (accumulated / total) * 100 : 0;
      accumulated += count;
      const end = total ? (accumulated / total) * 100 : 0;
      return `${ANSWER_TYPE_COLORS[name]} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    });

    const legend = entries.map(([name, count]) => `
      <div class="legend__item">
        <span class="legend__dot" style="background:${ANSWER_TYPE_COLORS[name]}"></span>
        <span>${name}</span>
        <span class="legend__value">${count}</span>
      </div>`).join('');

    $('chart-answer-types').innerHTML = `
      <div class="donut" style="background:conic-gradient(${stops.join(',') || '#eef0f7 0% 100%'})">
        <div class="donut__center"><strong>${total}</strong><span>道题目</span></div>
      </div>
      <div class="legend">${legend}</div>`;
  }


  $('button-toggle-answers').addEventListener('click', () => {
    state.showAnswers = !state.showAnswers;
    document.querySelectorAll('[data-role="answer-cell"]').forEach((cell) => {
      cell.hidden = !state.showAnswers;
    });
    $('button-toggle-answers').textContent = state.showAnswers ? '隐藏答案' : '显示答案';
  });


  function collectMyAnswers() {
    return state.problems.map((item) => {
      const input = document.querySelector(`.answer-input[data-index="${item.index}"]`);
      return input ? input.value.trim() : '';
    });
  }

  $('button-self-grade').addEventListener('click', runSelfGrade);

  async function runSelfGrade() {
    if (!state.problems.length) { return; }
    const button = $('button-self-grade');
    setBusy(button, true);
    showAlert('generate-error', '');
    try {
      const exerciseLines = state.problems.map((item) => item.text);
      const data = await postJSON('/api/grade', {
        exercise: exerciseLines,
        answer: collectMyAnswers(),
      });
      applySelfGradeResult(data.result);
    } catch (error) {
      showAlert('generate-error', error.message);
    } finally {
      setBusy(button, false);
    }
  }

  function applySelfGradeResult(result) {
    const verdictMap = new Map();
    result.details.forEach((detail) => { verdictMap.set(detail.index, detail); });

    document.querySelectorAll('#problem-tbody tr').forEach((row) => {
      const index = parseInt(row.dataset.index, 10);
      const detail = verdictMap.get(index);
      const verdictCell = row.querySelector('[data-role="verdict"]');
      const input = row.querySelector('.answer-input');
      input.classList.remove('is-correct', 'is-wrong');

      if (!detail) { return; }
      if (detail.is_correct) {
        verdictCell.textContent = '正确';
        verdictCell.className = 'verdict verdict--correct';
        input.classList.add('is-correct');
      } else {
        verdictCell.textContent = detail.note || '错误';
        verdictCell.className = 'verdict verdict--wrong';
        input.classList.add('is-wrong');
      }
    });

    const summary = $('self-grade-summary');
    summary.hidden = false;
    summary.textContent = `${result.correct_line}　|　${result.wrong_line}`;

    if (!state.showAnswers) {
      document.querySelectorAll('[data-role="answer-cell"]').forEach((cell) => { cell.hidden = false; });
      state.showAnswers = true;
      $('button-toggle-answers').textContent = '隐藏答案';
    }
    state.graded = true;
    toast(`批改完成：正确 ${result.correct_count} 题，错误 ${result.wrong_count} 题`);
  }


  function download(name) {
    window.location.href = `/api/download?name=${encodeURIComponent(name)}`;
  }

  $('button-download-exercise').addEventListener('click', () => download('Exercises.txt'));
  $('button-download-answer').addEventListener('click', () => download('Answers.txt'));


  $('button-fill-generated').addEventListener('click', () => {
    if (!state.exerciseText) {
      showAlert('grade-error', '还没有生成题目，请先在「出题」面板生成。');
      return;
    }
    $('textarea-exercise').value = state.exerciseText;
    $('textarea-answer').value = state.answerText;
    showAlert('grade-error', '');
    toast('已填入刚生成的题目与答案');
  });

  $('button-clear-editors').addEventListener('click', () => {
    $('textarea-exercise').value = '';
    $('textarea-answer').value = '';
    $('grade-result').hidden = true;
    showAlert('grade-error', '');
  });

  $('button-grade').addEventListener('click', async () => {
    const button = $('button-grade');
    const exercise = $('textarea-exercise').value;
    const answer = $('textarea-answer').value;
    showAlert('grade-error', '');

    if (exercise.trim() === '') {
      showAlert('grade-error', '题目内容为空，请先生成题目或粘贴题目文本。');
      return;
    }

    setBusy(button, true);
    button.querySelector('.label').textContent = '批改中…';
    try {
      const data = await postJSON('/api/grade', { exercise, answer });
      renderGradeResult(data);
      $('button-download-grade').disabled = false;
      toast(`批改完成：正确 ${data.result.correct_count} 题`);
    } catch (error) {
      showAlert('grade-error', error.message);
      $('grade-result').hidden = true;
    } finally {
      setBusy(button, false);
      button.querySelector('.label').textContent = '开始批改';
    }
  });

  function renderGradeResult(data) {
    const result = data.result;
    $('grade-correct-count').textContent = result.correct_count;
    $('grade-correct-ids').textContent = `(${result.correct_ids.join(', ')})`;
    $('grade-wrong-count').textContent = result.wrong_count;
    $('grade-wrong-ids').textContent = `(${result.wrong_ids.join(', ')})`;
    $('grade-text').textContent = data.gradeText;

    const wrong = result.details.filter((detail) => !detail.is_correct);
    $('grade-detail-hint').textContent = wrong.length
      ? `共 ${wrong.length} 道错题`
      : '全部正确';

    $('grade-detail-tbody').innerHTML = wrong.length
      ? wrong.map((detail) => `
          <tr>
            <td class="cell-index">${detail.index}</td>
            <td class="cell-expression">${escapeHtml(detail.expression)}</td>
            <td class="cell-answer" style="color:#a8123a">${escapeHtml(detail.submitted || '（空）')}</td>
            <td class="cell-answer">${escapeHtml(detail.expected)}</td>
            <td class="verdict verdict--wrong">${escapeHtml(detail.note)}</td>
          </tr>`).join('')
      : '<tr><td colspan="5" style="color:#16794a;font-weight:600">全部答对，没有错题。</td></tr>';

    $('grade-result').hidden = false;
    $('grade-result').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  $('button-download-grade').addEventListener('click', () => download('Grade.txt'));


  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function checkHealth() {
    const node = $('health-indicator');
    try {
      const response = await fetch('/api/health');
      const data = await response.json();
      node.textContent = '已连接后端';
      node.className = 'health health--ok';
    } catch (error) {
      node.textContent = '未连接后端';
      node.className = 'health health--fail';
    }
  }

  /** URL 参数: ?n=20&r=10&auto=1 自动出题, 再加 &tab=grade 自动跳到批改 */
  function applyUrlParameters() {
    const search = new URLSearchParams(window.location.search);
    if (search.has('n')) { $('input-count').value = search.get('n'); }
    if (search.has('r')) { $('input-range').value = search.get('r'); }
    if (search.has('m')) { $('input-ops').value = search.get('m'); }

    const tab = search.get('tab');
    if (tab) {
      const target = document.querySelector(`.tab[data-tab="${tab}"]`);
      if (target) { setTimeout(() => target.click(), 40); }
    }

    if (search.get('auto') !== '1') { return; }
    setTimeout(() => $('button-generate').click(), 60);
    if (tab === 'grade') {
      setTimeout(() => $('button-fill-generated').click(), 900);
      setTimeout(() => $('button-grade').click(), 1400);
    }
  }

  applyUrlParameters();
  checkHealth();
})();

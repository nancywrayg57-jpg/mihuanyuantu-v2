/* Gemini Vision production detection + auto-redo. Browser fixtures are not model measurements. */
(function (root) {
  'use strict';
  const BASELINE = Object.freeze({
    engine: 'Gemini Vision',
    model: 'gemini-2.5-pro',
    version: 'GEMINI-DETECT-1.0',
    passScore: 75,
    defaultThreshold: 70,
    minCount: 1,
    maxCount: 5
  });
  const finiteInt = (value, min, max) => Number.isInteger(value) && value >= min && value <= max;
  const normalize = (raw = {}) => {
    const threshold = Number(raw.threshold);
    const maxCount = Number(raw.maxCount);
    return {
      enabled: raw.enabled === true,
      threshold: finiteInt(threshold, 0, 100) ? threshold : BASELINE.defaultThreshold,
      maxCount: finiteInt(maxCount, BASELINE.minCount, BASELINE.maxCount) ? maxCount : 1,
      version: BASELINE.version,
      engine: BASELINE.engine,
      savedAt: raw.savedAt || null
    };
  };
  const defaults = () => normalize({});
  const validReport = (report) => report?.engine === BASELINE.engine
    && Array.isArray(report.scores)
    && report.scores.length === 5
    && report.scores.every((score) => typeof score === 'number' && Number.isFinite(score))
    && typeof report.total === 'number'
    && Number.isFinite(report.total)
    && typeof report.passed === 'boolean';
  const passedGate = (report) => validReport(report) && report.passed === true && report.total >= BASELINE.passScore;
  const decide = ({ report, settings, used = 0, quality = true }) => {
    const chain = normalize(settings);
    if (!quality) return { eligible: false, code: 'QUALITY_FAILED', reason: '文件或保真检查未通过，不触发自动重做' };
    if (!validReport(report)) return { eligible: false, code: 'TECH_FAILED', reason: '检测无有效分数，按技术异常处理，不自动循环' };
    if (!chain.enabled) return { eligible: false, code: 'USER_DISABLED', reason: '用户未开启自动重做' };
    if (!Number.isInteger(used) || used < 0) return { eligible: false, code: 'STOP_LIMIT', reason: '追加次数记录无效' };
    if (used >= chain.maxCount) return { eligible: false, code: 'STOP_LIMIT', reason: `已达到追加次数上限 ${chain.maxCount}` };
    if (report.total < chain.threshold) return { eligible: true, code: 'REDO', reason: `总分 ${report.total} 低于阈值 ${chain.threshold}，进入自动重做` };
    return { eligible: false, code: 'ABOVE_THRESHOLD', reason: `总分 ${report.total} 不低于阈值 ${chain.threshold}` };
  };
  const fixtures = Object.freeze({
    pass: { scores: [90, 88, 86, 87, 89], total: 88, passed: true, reason: '五维均达到检测基线，结果可交付。' },
    low: { scores: [68, 66, 70, 67, 69], total: 68, passed: false, reason: '总分低于自动重做阈值。' },
    fail: { scores: [62, 58, 64, 61, 60], total: 61, passed: false, reason: '总分低于检测基线。' },
    highThreshold: { scores: [82, 80, 81, 83, 79], total: 81, passed: true, reason: '已过 75 基线，但可能低于用户阈值。' },
    allFail: { scores: [62, 65, 61, 66, 64], total: 64, passed: false, reason: '总分低于当前检测阈值。' },
    tech: { scores: null, total: null, passed: false, integrity: 'error', errors: ['Gemini 响应超时，未取得有效分数'] },
    unknown: { scores: [80, 78, null, 81, 79], total: null, passed: false, integrity: 'incomplete', errors: ['模型响应无法解析完整五维'] }
  });
  const fixture = (key) => {
    const body = fixtures[key] || fixtures.pass;
    return {
      engine: BASELINE.engine,
      model: BASELINE.model,
      version: BASELINE.version,
      integrity: 'complete',
      errors: [],
      ...body
    };
  };
  const api = Object.freeze({ BASELINE, defaults, normalize, validReport, passedGate, decide, fixture });
  if (typeof module === 'object' && module.exports) module.exports = api;
  else {
    root.GeminiRedoPolicy = api;
    root.CheckRedoPolicy = api;
  }
})(typeof window === 'undefined' ? globalThis : window);

(() => {
      'use strict';
      const STORAGE_KEY = 'mhy-v2-html-prototype';
      const CREDIT_PER_IMAGE = 10;
      const checkPolicy = window.GeminiRedoPolicy || window.CheckRedoPolicy;
      const demoNow = '2026-10-25 14:20';
      const statusLabels = {
        FILE_READY: '文件已就绪', REVIEW_REQUIRED: '风险待复核', DETECTION_UNKNOWN: '检测不完整', QUALITY_FAILED: '质量未通过', LEGACY_REVIEW: '旧任务待复核', DRAFT: '草稿', SUBMITTED: '已提交', PRE_REVIEW: '预审中', PRE_REVIEW_FAILED: '预审未通过', IMAGE_LOCKED: '图片已锁定', REJECTED: '已拒绝', GENERATING: '生成中', GENERATED: '已生成', FULL_PROCESSING: '五层处理中', DETECTION: '检测中', AUTO_REPROCESS_PENDING: '自动重做中', RETRY_PENDING: '等待手动重试', REPROCESS_PENDING: '等待重新处理', DELIVERED: '已交付', FAILED: '检测未通过', TECH_FAILED: '技术异常', CLOSED: '已关闭', EXPIRED: '已过期', DELETED: '已删除'
      };
      const taskStates = ['DRAFT', 'SUBMITTED', 'PRE_REVIEW', 'GENERATING', 'GENERATED', 'FULL_PROCESSING', 'DETECTION', 'AUTO_REPROCESS_PENDING', 'RETRY_PENDING', 'REPROCESS_PENDING', 'DELIVERED', 'FAILED', 'CLOSED', 'EXPIRED', 'DELETED'];
      const ledgerStates = ['RESERVED', 'CONSUMED', 'RELEASED', 'ADJUSTED'];
      const sourceLabels = { text: '文生图', image: '图生图', upload: '本地上传', import: 'URL导入', mixed: '混合来源' };
      const resourceSourceOrder = ['import', 'upload', 'text', 'image'];
      const resourceTabOrder = ['all', 'import', 'upload', 'text', 'image'];
      const processingSourceTabOrder = ['all', 'import', 'upload', 'text', 'image', 'mixed'];
      const resourceFileNameFields = ['name', 'seller', 'sku', 'asn', 'price', 'website', 'url'];
      const resourceFileNameRequired = ['name', 'sku', 'url'];
      const devicePresetSource = window.__mhyDevicePresetSource || { items: [], total: 0, capturedOn: 'unknown', sourceFile: 'unknown', reviewBuckets: {} };
      const deviceCategoryLabels = { phone: '手机', dslr: '单反', mirrorless: '无反', action: '运动相机' };
      const deviceFamilyLabels = { phone: '手机', legacy_dslr_pending_review: '原单反标签 · 待按型号复核', legacy_mirrorless_pending_review: '原微单标签 · 待按型号复核', action_camera: '运动相机', gimbal_camera_candidate: '云台相机候选', fixed_lens_candidate: '固定镜头相机候选', medium_format_candidate: '中画幅候选', panoramic_360_candidate: '全景 / 360 候选', rangefinder_candidate: '旁轴形态候选' };
      const deviceReviewLabels = { STRUCTURAL_CANDIDATE: '结构候选', QUARANTINE_REVIEW: '待复核' };
      const devicePresetDemoDefaults = [
        { id: 'PRESET-001', name: '无反相机 · 50mm', category: '无反', camera: 'Sony A7 IV', lens: 'FE 50mm F1.8', iso: 100, shutter: '1/125', aperture: 'f/4.0', ev: 0, gpsPolicy: '可选', visibility: '公共', status: '启用', version: 'v1.2', demo: true, parameterJson: { category: 'mirrorless', camera_make: 'Sony', camera_model: 'A7 IV', iso: 100, shutter_speed: '1/125', aperture: 4, focal_length: 50, focal_length_equiv: 50, white_balance: 'Daylight', metering_mode: 'Multi', sensor_size: 'Full Frame (36x24mm)', color_space: 'sRGB', stabilization: 'IBIS', lens_model: 'FE 50mm F1.8', software: 'Sony ILCE-7M4 1.0', gps_mode: 'none' } },
        { id: 'PRESET-002', name: '手机主摄 · 自然色', category: '手机', camera: 'iPhone 15 Pro', lens: '24mm 等效', iso: 50, shutter: '1/120', aperture: 'f/1.8', ev: 0, gpsPolicy: '可选', visibility: '公共', status: '启用', version: 'v1.1', demo: true, parameterJson: { category: 'phone', camera_make: 'Apple', camera_model: 'iPhone 15 Pro', iso: 50, shutter_speed: '1/120', aperture: 1.8, focal_length: 6.8, focal_length_equiv: 24, white_balance: 'Auto', metering_mode: 'Multi', sensor_size: '1/1.28"', color_space: 'Display P3', stabilization: 'OIS', lens_model: 'iPhone 15 Pro 6.8mm f/1.8', software: 'iOS 17.0', gps_mode: 'none' } },
        { id: 'PRESET-003', name: '单反 · 商业棚拍', category: '单反', camera: 'Canon EOS R5', lens: 'RF 85mm F2', iso: 200, shutter: '1/160', aperture: 'f/5.6', ev: 0, gpsPolicy: '关闭', visibility: '公共', status: '启用', version: 'v1.0', demo: true, parameterJson: { category: 'dslr', camera_make: 'Canon', camera_model: 'EOS R5', iso: 200, shutter_speed: '1/160', aperture: 5.6, focal_length: 85, focal_length_equiv: 85, white_balance: 'Daylight', metering_mode: 'Evaluative', sensor_size: 'Full Frame (36x24mm)', color_space: 'sRGB', stabilization: 'IBIS', lens_model: 'RF 85mm F2', software: 'Canon EOS R5 1.8.1', gps_mode: 'none' } }
      ];
      const makeImportedDevicePresets = () => devicePresetSource.items.map((raw) => {
        const meta = raw._meta || {};
        const reviewBucket = meta.reviewBucket || 'QUARANTINE_REVIEW';
        return {
          id: `LEGACY-${raw.id}`,
          name: raw.name,
          category: deviceCategoryLabels[raw.category] || raw.category || '待分类',
          familyHint: meta.familyHint || '',
          familyLabel: deviceFamilyLabels[meta.familyHint] || meta.familyHint || '待分类',
          camera: [raw.camera_make, raw.camera_model].filter(Boolean).join(' '),
          lens: [raw.lens_make, raw.lens_model].filter(Boolean).join(' '),
          iso: raw.iso,
          shutter: raw.shutter_speed,
          aperture: raw.aperture == null ? '' : `f/${raw.aperture}`,
          ev: raw.ev_value,
          gpsPolicy: raw.gps_mode || '未设置',
           visibility: meta.legacyVisibility || 'PRIVATE',
           sourceVisibility: meta.legacyVisibility || 'PRIVATE',
           status: reviewBucket === 'QUARANTINE_REVIEW' ? '待复核' : '未启用',
          version: `legacy-${meta.capturedOn || devicePresetSource.capturedOn}`,
          sourceId: raw.id,
          templateRef: meta.templateRef || `legacy-online-${raw.id}`,
          reviewBucket,
          reviewFlags: meta.reviewFlags || [],
           activationStatus: 'NOT_ACTIVATED',
           sourceActivationStatus: meta.activationStatus || 'NOT_ACTIVATED',
          classificationBasis: meta.classificationBasis || 'ADVISORY_NAME_RULE_NOT_VENDOR_VERIFIED',
           locked: false,
          parameterJson: raw
        };
      });
      const createDevicePresetDefaults = () => [...devicePresetDemoDefaults, ...makeImportedDevicePresets()];
       const mergeDevicePresets = (defaults, saved) => {
        const merged = new Map(defaults.map((item) => [String(item.id), item]));
         (saved || []).forEach((item) => {
           if (!item?.id) return;
           if (String(item.id).startsWith('LEGACY-')) {
             item = {
               ...item,
               locked: false,
               sourceVisibility: item.sourceVisibility || item.visibility || 'PRIVATE',
               sourceActivationStatus: item.sourceActivationStatus || item.parameterJson?._meta?.activationStatus || 'NOT_ACTIVATED',
               activationStatus: item.activationStatus || (item.status === '启用' ? 'ACTIVATED' : 'NOT_ACTIVATED')
             };
           }
           merged.set(String(item.id), item);
         });
        return [...merged.values()];
      };
       const roleMeta = {
         merchant: { userId: 'USR-001', label: '商家', desc: '提交图片任务、查看结果和积分流水', avatar: '商', scope: '本租户配置', tenantId: 'DEMO-01' },
         support: { userId: 'USR-002', label: '技术客服', desc: '处理冻结事件、技术失败和人工工单', avatar: '技', scope: '授权工单范围', tenantId: null },
         admin: { userId: 'USR-003', label: '平台管理员', desc: '查看运营指标、解冻与审计记录', avatar: '管', scope: '全平台配置与审计', tenantId: 'PLATFORM' }
       };
      const stageLabels = ['输入校验', '预审', '五层处理', 'Check 检测', '结果交付'];
      const generationStageLabels = ['生成请求', '生图中', '生成结果'];
      const layerLabels = ['像素物理化', '频域扰动', '指纹破坏', '设备与 EXIF', '编码特征'];
      const legacyScoreSets = {
        pass: [82, 91, 88, 86, 90],
        low: [66, 71, 64, 68, 70],
        highThreshold: [88, 79, 81, 84, 82],
        allFail: [62, 65, 61, 66, 64]

      };
      const validationCases = {
        pass: { label: '全部通过', errors: [] },
        partial: { label: '批量部分失败', errors: ['第 2 张：方向分辨率不足（实际 640 × 480，要求横图至少 1024 × 768）'] },
        format: { label: '格式错误', errors: ['不支持的文件格式 .webp；仅支持 JPG / JPEG / PNG'] },
        size: { label: '文件过大', errors: ['文件大小 24.6 MiB 超过单张 20 MiB 上限'] },
        pixel: { label: '像素超限', errors: ['像素总量 48 MP 超过单张 40 MP 上限'] },
        orientation: { label: '方向分辨率不足', errors: ['竖图实际 640 × 900，要求竖图至少 768 × 1024'] },
        decode: { label: '无法解码', errors: ['文件无法解码，未创建图片资产'] },
        unsafe: { label: '内容预审拒绝', errors: ['命中明确禁止项，规则版本 PREVIEW-2026.10；不进入五层处理'] }
      };
      const scenarioOptions = [
        ['pass','首轮通过'], ['fail','低于阈值 · 自动重做'], ['high-threshold','过基线但低于用户阈值'],
        ['quality-fail','质量未通过'], ['tech','检测超时'], ['duplicate','重复提交'],
        ['pre-review-fail','预审失败'], ['image-lock','同图二次预审失败锁定'], ['account-freeze','三图预审失败冻结']
      ];
      const generationScenarioOptions = [['pass','生成成功'], ['duplicate','重复点击']];
      const makeLegacyReport = (scores, passed, reason) => ({ scores, total: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length), passed, reason: reason || (passed ? '五维均达到检测基线，结果可交付。' : '总分低于当前检测阈值，结果保留但不收费。') });
      const makeLegacyRound = (roundNo, status, scoreKey, passed, trigger, reason, billing) => {
        const scores = legacyScoreSets[scoreKey] || legacyScoreSets.pass;
        return { roundNo, status, trigger, score: Math.round(scores.reduce((a,b) => a+b, 0) / scores.length), report: makeLegacyReport(scores, passed, reason), billing, layers: layerLabels.map((label, i) => ({ label, status: status === 'TECH_FAILED' && i >= 2 ? 'failed' : status === 'AUTO_REPROCESS_PENDING' && i >= 3 ? 'pending' : 'done' })), input: roundNo === 1 ? '原始输入 / 生成中间资产' : '上一轮已处理结果', output: passed ? 'sRGB JPEG' : '可预览结果 · 未收费' };
      };
      const seedHistory = [
        { id: 'CH-1028', title: '春日餐具 · 4 张', source: 'text', createdAt: '2026-10-25 13:58', status: 'DELIVERED', score: 88, threshold: 70, rounds: [makeLegacyRound(1, 'DELIVERED', 'pass', true, '首轮通过', '', 'CONSUMED · 40 积分')], billing: '已消费 40 积分（4 张）', consumedCredits: 40, chargeState: 'CONSUMED', preview: 'art-teal', stage: '结果已交付' },
        { id: 'CH-1024', title: '户外鞋细节 · 2 张', source: 'image', createdAt: '2026-10-25 12:41', status: 'DELIVERED', score: 86, threshold: 70, rounds: [makeLegacyRound(1, 'FAILED', 'low', false, '低于阈值 70，进入自动重做', '', '待结算'), makeLegacyRound(2, 'DELIVERED', 'pass', true, '沿用上一轮结果，仅重跑五层与检测', '', 'CONSUMED · 20 积分')], billing: '已消费 20 积分（2 张 · 自动轮次不叠加）', consumedCredits: 20, chargeState: 'CONSUMED', preview: 'art-coral', stage: '自动重做后交付' },
        { id: 'CH-1019', title: '玻璃瓶 · 高阈值任务', source: 'image', createdAt: '2026-10-25 11:26', status: 'AUTO_REPROCESS_PENDING', score: 82, threshold: 90, rounds: [makeLegacyRound(1, 'FAILED', 'highThreshold', false, '已过 75 基线，但低于用户阈值 90', '阈值高于检测基线，继续自动重做。', '待结算'), makeLegacyRound(2, 'AUTO_REPROCESS_PENDING', 'pass', false, '正在执行第 2 / 3 轮', '', '待结算')], billing: '冻结中 · 预计 10 积分（1 张）', reservedCredits: 10, chargeState: 'FROZEN', preview: 'art-purple', stage: '五层处理中' },
        { id: 'CH-1012', title: '秋季收纳盒 · 3 张', source: 'text', createdAt: '2026-10-24 18:05', status: 'FAILED', score: 64, threshold: 70, rounds: [makeLegacyRound(1, 'FAILED', 'allFail', false, '低于阈值 70', '', '释放'), makeLegacyRound(2, 'FAILED', 'allFail', false, '第 2 轮仍低于阈值', '', '释放')], billing: '未消费 · 已释放 30 积分（3 张）', consumedCredits: 0, chargeState: 'RELEASED', preview: 'art-coral', stage: '全部轮次未通过' },
        { id: 'CH-1008', title: '白色耳机 · 技术异常', source: 'text', createdAt: '2026-10-24 16:12', status: 'TECH_FAILED', score: null, threshold: 70, rounds: [makeLegacyRound(1, 'TECH_FAILED', 'pass', false, 'Gemini 响应超时，未取得有效分数', '技术异常不触发自动重做，等待手动重试或客服处理。', '待客服审计')], billing: '冻结中 · 待客服释放 10 积分（1 张）', reservedCredits: 10, chargeState: 'FROZEN', preview: 'art-teal', stage: '检测服务异常' },
        { id: 'CH-1004', title: '桌面灯 · 重复回调', source: 'image', createdAt: '2026-10-24 14:33', status: 'DELIVERED', score: 89, threshold: 70, rounds: [makeLegacyRound(1, 'DELIVERED', 'pass', true, '重复回调已去重', '', 'CONSUMED · 10 积分')], billing: '已消费 10 积分（1 张 · 幂等）', consumedCredits: 10, chargeState: 'CONSUMED', preview: 'art-purple', stage: '重复点击已拦截' },
        { id: 'CH-0997', title: '陶瓷杯 · 本地上传', source: 'upload', createdAt: '2026-10-24 11:03', status: 'DELIVERED', score: 84, threshold: 70, rounds: [makeLegacyRound(1, 'DELIVERED', 'pass', true, '直接上传 → 五层处理 → Gemini 检测', '', 'CONSUMED · 10 积分')], billing: '已消费 10 积分（1 张）', consumedCredits: 10, chargeState: 'CONSUMED', preview: 'art-amber', stage: '独立图片处理完成' },
        { id: 'CH-0991', title: '香薰瓶 · URL导入', source: 'import', createdAt: '2026-10-24 09:46', status: 'DELIVERED', score: 81, threshold: 70, rounds: [makeLegacyRound(1, 'DELIVERED', 'pass', true, 'URL 地址导入 → 五层处理 → Gemini 检测', '', 'CONSUMED · 10 积分')], billing: '已消费 10 积分（1 张）', consumedCredits: 10, chargeState: 'CONSUMED', preview: 'art-coral', stage: 'URL导入处理完成' }
      ];
      const seedMessages = [
        { id: 'MSG-24', type: 'success', title: '任务 CH-1028 已交付', body: '4 张结果已完成处理，可在任务详情中查看。', time: '12 分钟前', read: false },
        { id: 'MSG-23', type: 'warn', title: '自动重做正在进行', body: 'CH-1019 使用阈值 90，当前进入第 2 / 3 轮。', time: '1 小时前', read: false },
        { id: 'MSG-22', type: 'danger', title: '技术异常待处理', body: 'CH-1008 未获得有效分数，冻结积分等待客服审计。', time: '2 小时前', read: true },
        { id: 'MSG-21', type: 'success', title: '充值订单已确认', body: '订单 TOP-20261024-018 已到账 500 积分。', time: '昨天', read: true }
      ];
      const seedTransactions = [
        { time: '2026-10-25 13:58', type: '任务消费', ref: 'CH-1028 / 4 张按张结算', amount: -40, status: '已完成' },
        { time: '2026-10-25 12:41', type: '任务结算', ref: 'CH-1024 / 2 张 · 自动轮次不叠加', amount: -20, status: '已完成' },
        { time: '2026-10-24 18:05', type: '冻结释放', ref: 'CH-1012 / 3 张全部未通过', amount: 30, status: '已释放' },
        { time: '2026-10-24 15:44', type: '人工充值', ref: 'TOP-20261024-018', amount: 500, status: '客服已确认' }
      ];
      const seedTickets = [
        { id: 'TK-018', kind: '技术异常', tenant: '示例商家 · DEMO-01', ref: 'CH-1008', status: '待处理', owner: '技术客服', createdAt: '2026-10-24 16:12', note: 'Gemini 超时，冻结积分待审计释放。' },
        { id: 'TK-017', kind: '账号冻结', tenant: '海盐家居 · DEMO-03', ref: 'FRZ-003', status: '待解冻', owner: '平台管理员', createdAt: '2026-10-24 10:24', note: '三张不同图片连续预审失败。' },
        { id: 'TK-016', kind: '充值确认', tenant: '示例商家 · DEMO-01', ref: 'TOP-20261024-018', status: '已完成', owner: '订单客服', createdAt: '2026-10-24 15:44', note: '到账 500 积分，已确认入账。' }
      ];
      const seedPromptTemplates = [
        { id: 'PT-001', name: '电商主图 · 自然光', mode: 'text', prompt: '自然光下的米白色陶瓷餐具，浅木桌面，柔和阴影，电商主图留白，干净背景', negative: '文字、水印、畸变、过度锐化', scope: 'platform', ownerId: null, tenantId: 'PLATFORM', updatedAt: '2026-10-25 10:00' },
        { id: 'PT-002', name: '材质特写 · 图生图', mode: 'image', prompt: '保留参考图主体比例，提升材质细节与自然光质感，干净背景', negative: '文字、水印、畸变、过度锐化', scope: 'platform', ownerId: null, tenantId: 'PLATFORM', updatedAt: '2026-10-25 10:05' },
        { id: 'PT-003', name: '白底静物', mode: 'text', prompt: '纯白背景静物电商图，柔和顶光，产品居中，留白充足', negative: '文字、Logo、杂乱背景', scope: 'platform', ownerId: null, tenantId: 'PLATFORM', updatedAt: '2026-10-24 16:20' }
      ];
      const modelProviders = ['Gemini', 'GPT', 'Claude', 'Kimi', 'MiniMax', 'DeepSeek', '阿里千问', 'ChatGPT Image 2'];
      const modelPurposes = ['图片预审', '生图渠道', '提示词优化', '最终检测'];
      const MODEL_KEY_SLOT_MAX = 10;
      const maskApiKey = (raw) => {
        const value = String(raw || '').trim();
        if (!value) return '';
        if (value.length <= 4) return `${value[0] || ''}••••`;
        return `${value.slice(0, 2)}••••${value.slice(-2)}`;
      };
      const normalizeModelApiKeys = (item) => {
        if (Array.isArray(item?.apiKeys) && item.apiKeys.length) {
          return item.apiKeys
            .map((entry, index) => ({
              raw: String(entry.raw || '').trim(),
              masked: String(entry.masked || '').trim(),
              weight: Number.isInteger(Number(entry.weight)) ? Number(entry.weight) : index
            }))
            .filter((entry) => entry.raw || entry.masked)
            .sort((a, b) => a.weight - b.weight);
        }
        if (item?.masked || item?.raw) return [{ raw: String(item.raw || '').trim(), masked: String(item.masked || '').trim(), weight: 0 }];
        return [];
      };
      const modelKeyFormState = () => {
        const form = state.system.modelKeyForm || (state.system.modelKeyForm = { purpose: modelPurposes[0] });
        if (!modelPurposes.includes(form.purpose)) form.purpose = modelPurposes[0];
        return form;
      };
      const modelKeyRecordForPurpose = (purpose) => (state.system.modelKeys || []).find((item) => item.purpose === purpose);
      const draftForModelPurpose = (purpose) => {
        const drafts = state.system.modelKeyDrafts || (state.system.modelKeyDrafts = {});
        if (drafts[purpose] && Array.isArray(drafts[purpose].keys)) return drafts[purpose];
        const record = modelKeyRecordForPurpose(purpose);
        const keys = normalizeModelApiKeys(record).map((entry) => entry.raw || entry.masked || '');
        drafts[purpose] = {
          provider: record?.provider || modelProviders[0],
          model: record?.model || '',
          baseUrl: record?.baseUrl || '',
          keys: keys.length ? keys : ['']
        };
        return drafts[purpose];
      };
      const captureModelKeyForm = (form, purposeOverride) => {
        if (!form) return;
        const purpose = purposeOverride || String(form.querySelector('[name="purpose"]')?.value || modelKeyFormState().purpose);
        const keys = Array.from(form.querySelectorAll('[name^="key_"]')).map((input) => String(input.value || ''));
        const drafts = state.system.modelKeyDrafts || (state.system.modelKeyDrafts = {});
        drafts[purpose] = {
          provider: String(form.querySelector('[name="provider"]')?.value || ''),
          model: String(form.querySelector('[name="model"]')?.value || ''),
          baseUrl: String(form.querySelector('[name="base_url"]')?.value || ''),
          keys: keys.length ? keys : ['']
        };
      };
      const nextModelApiKey = (item) => {
        const keys = normalizeModelApiKeys(item);
        if (!keys.length) return null;
        const index = Number(item.pollIndex || 0) % keys.length;
        item.pollIndex = (index + 1) % keys.length;
        return keys[index];
      };
       const freshSystem = () => ({
        activeTab: 'auto',
        modelKeys: [
          { id: 'KEY-001', provider: 'Gemini', model: 'gemini-2.5-pro', purpose: '最终检测', baseUrl: 'https://generativelanguage.googleapis.com', apiKeys: [{ masked: 'gm••••9F', weight: 0 }], scope: '平台', status: '已启用', pollIndex: 0, updatedAt: '2026-10-25' },
          { id: 'KEY-002', provider: '阿里千问', model: 'qwen-vl-max', purpose: '图片预审', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', apiKeys: [{ masked: 'sk••••2A', weight: 0 }, { masked: 'sk••••7C', weight: 1 }], scope: '平台', status: '已启用', pollIndex: 0, updatedAt: '2026-10-24' },
          { id: 'KEY-003', provider: 'ChatGPT Image 2', model: 'gpt-image-2', purpose: '生图渠道', baseUrl: 'https://api.openai.com/v1', apiKeys: [{ masked: 'oa••••71', weight: 0 }], scope: '平台', status: '已停用', pollIndex: 0, updatedAt: '2026-10-20' }
        ],
        users: [
          { id: 'USR-001', username: 'merchant.demo', displayName: '示例商家', tenantId: 'DEMO-01', role: 'merchant', status: '启用', permissions: ['task.create', 'history.read', 'credits.read'] },
          { id: 'USR-002', username: 'support.demo', displayName: '技术客服', tenantId: '授权工单范围', role: 'support', status: '启用', permissions: ['ticket.read', 'account.unfreeze', 'user.manage'] },
          { id: 'USR-003', username: 'admin.demo', displayName: '平台管理员', tenantId: 'PLATFORM', role: 'admin', status: '启用', permissions: ['system.manage', 'user.manage', 'preset.manage', 'account.unfreeze'] },
          { id: 'USR-004', username: 'merchant.other', displayName: '海盐家居', tenantId: 'DEMO-03', role: 'merchant', status: '冻结', permissions: ['history.read', 'credits.read'] }
        ],
        devicePresets: createDevicePresetDefaults(),
        devicePresetView: { query: '', category: 'all', review: 'all', page: 1, pageSize: 20, detailId: null, activeTab: 'presets', editorId: null, formTab: 'basic' },
        modelKeyForm: { purpose: '图片预审' },
        modelKeyDrafts: {},
        audit: [
          { time: '2026-10-25 13:42', actor: '平台管理员', scope: 'PLATFORM', action: '查看系统管理', result: '允许' },
          { time: '2026-10-25 11:08', actor: '技术客服', scope: '授权工单范围', action: '尝试访问模型 API 配置', result: '拒绝' }
        ],
        userView: { page: 1, pageSize: 10 },
        userLogs: [],
        logView: { page: 1, pageSize: 20 }
      });
      const freshState = () => ({
        session: false, role: 'merchant', page: 'login', batchMode: 'text', selectedId: null,
        history: seedHistory, messages: seedMessages, transactions: seedTransactions, tickets: seedTickets,
        credits: { available: 286, frozen: 20 },
        auto: checkPolicy.defaults(),
        account: { status: 'ACTIVE', distinctFailures: [], imageFailures: {}, imageLocks: {}, freezeEvent: null },
        promptOptimization: { active: false, original: '', optimized: '', confirmed: false, status: 'idle', charged: 0 },
         batchDraft: null, inputDraft: null, directPresetId: 'PRESET-001', directPresetType: '', directPresetBrand: '', directPresetModel: '', directPresetName: '无反相机 · 50mm', directPresetPreviewOpen: false, copyGate: { active: false, tenantId: null, taskId: null },
        system: freshSystem(), historyFilter: { source: 'all', status: 'all', query: '' }, historyView: { page: 1, pageSize: 10 }, creditsView: { page: 1, pageSize: 5 }, supportView: { ticketPage: 1, ticketPageSize: 5, auditPage: 1, auditPageSize: 10 }, processing: null, lastScenario: 'pass', ticketViewId: null,
        resources: [], resourceVersion: 0,
        resourceView: { source: 'all', page: 1, pageSize: 20, selectedIds: [] },
        processResourceIds: [], jobs: [], historyTab: 'processing', historyTabs: {},
        promptTemplates: seedPromptTemplates.map((item) => ({ ...item })),
        promptTemplateView: { page: 1, pageSize: 10 },
        promptTemplateEditor: null
      });
      let state = freshState();
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
        if (saved) {
          const defaults = freshState();
          state = {
            ...defaults,
            ...saved,
            history: saved.history?.length ? saved.history : defaults.history,
            messages: Array.isArray(saved.messages) ? saved.messages : defaults.messages,
            transactions: saved.transactions?.length ? saved.transactions : defaults.transactions,
            tickets: saved.tickets?.length ? saved.tickets : defaults.tickets,
            credits: { ...defaults.credits, ...(saved.credits || {}) },
            auto: { ...defaults.auto, ...(saved.auto || {}) },
            account: { ...defaults.account, ...(saved.account || {}), imageFailures: { ...defaults.account.imageFailures, ...(saved.account?.imageFailures || {}) }, imageLocks: { ...defaults.account.imageLocks, ...(saved.account?.imageLocks || {}) } },
            promptOptimization: { ...defaults.promptOptimization, ...(saved.promptOptimization || {}) },
            inputDraft: { ...defaults.inputDraft, ...(saved.inputDraft || {}) },
            copyGate: { ...defaults.copyGate, ...(saved.copyGate || {}) },
            promptTemplates: Array.isArray(saved.promptTemplates) && saved.promptTemplates.length ? saved.promptTemplates : defaults.promptTemplates,
            promptTemplateView: { ...defaults.promptTemplateView, ...(saved.promptTemplateView || {}) },
            promptTemplateEditor: null,
            system: {
              ...defaults.system,
              ...(saved.system || {}),
              modelKeys: saved.system?.modelKeys?.length ? saved.system.modelKeys : defaults.system.modelKeys,
              users: saved.system?.users?.length ? saved.system.users : defaults.system.users,
              devicePresets: mergeDevicePresets(defaults.system.devicePresets, saved.system?.devicePresets),
               devicePresetView: { ...defaults.system.devicePresetView, ...(saved.system?.devicePresetView || {}) },
               modelKeyForm: { purpose: '图片预审', ...(saved.system?.modelKeyForm || {}) },
               modelKeyDrafts: saved.system?.modelKeyDrafts && typeof saved.system.modelKeyDrafts === 'object' ? saved.system.modelKeyDrafts : {},
               userView: { ...defaults.system.userView, ...(saved.system?.userView || {}) },
               userLogs: Array.isArray(saved.system?.userLogs) ? saved.system.userLogs : defaults.system.userLogs,
               logView: { ...defaults.system.logView, ...(saved.system?.logView || {}), pageSize: 20 },
              audit: saved.system?.audit?.length ? saved.system.audit : defaults.system.audit
            },
             historyFilter: { ...defaults.historyFilter, ...(saved.historyFilter || {}) },
             historyView: { ...defaults.historyView, ...(saved.historyView || {}) },
             creditsView: { ...defaults.creditsView, ...(saved.creditsView || {}) },
             supportView: { ...defaults.supportView, ...(saved.supportView || {}) },
             resources: Array.isArray(saved.resources) ? saved.resources : [],
             jobs: Array.isArray(saved.jobs) ? saved.jobs : [],
             resourceView: { ...defaults.resourceView, ...(saved.resourceView || {}), pageSize: 20 }
          };
        }
      } catch (_) { state = freshState(); }
      if (state.auto?.engine === 'Check_Aimage' || state.auto?.version === 'CHECK-REDO-1.0' || state.auto?.status === 'BLOCKED') state.auto = checkPolicy.defaults();
      else state.auto = checkPolicy.normalize(state.auto);
      if (!state.system.geminiDetectRestored) {
        state.system.modelKeys.filter((item) => item.purpose === '最终检测').forEach((item) => { item.status = '已启用'; });
        state.system.geminiDetectRestored = true;
      }
      state.jobs.filter((job) => !job.done && job.kind !== 'generation' && job.payload?.checkBaseline?.engine === 'Check_Aimage').forEach((job) => {
        job.done = true; job.outcome = 'LEGACY_REVIEW'; job.resultTitle = '研究策略任务已停止'; job.resultBody = 'Check 研究任务停止续跑，原账务和历史证据保留。';
        const item = state.history.find((entry) => entry.id === job.historyId && entry.tenantId === job.tenantId);
        if (item) { item.legacyStatus ||= item.status; item.legacyStage ||= item.stage; item.status = 'LEGACY_REVIEW'; item.stage = '研究策略任务停止，账务待复核'; }
        if (state.processing?.id === job.id) state.processing = job;
      });
      if (!scenarioOptions.some(([key]) => key === state.lastScenario)) state.lastScenario = 'pass';
      state.history.filter((item) => item.checkBaseline?.engine === 'Check_Aimage' && item.status === 'AUTO_REPROCESS_PENDING' && !state.jobs.some((job) => !job.done && job.historyId === item.id)).forEach((item) => { item.legacyStatus = item.status; item.status = 'LEGACY_REVIEW'; });
      if (state.historyFilter.source === 'default') { state.historyFilter.source = 'all'; state.historyView.page = 1; }
      let userDialog = null;
      let resultDialog = null;
      let resourceDialog = null;
      let idSequence = 0;
      const jobTimers = new Map();
      const uniqueId = (prefix) => `${prefix}-${Date.now()}-${++idSequence}`;
      const creditDecimal = window.Decimal.clone({ precision: 40 });
      state.system.users.forEach((user) => {
        if (user.credits == null) user.credits = user.id === 'USR-001' ? String(state.credits.available) : '0';
        if (user.role === 'support' && Array.isArray(user.permissions) && !user.permissions.includes('user.manage')) user.permissions = [...user.permissions, 'user.manage'];
      });
      if (location.hash && location.hash !== '#login') { state.page = location.hash.slice(1); state.session = true; }
      const persist = () => localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      const role = () => roleMeta[state.role] || roleMeta.merchant;
      const systemTabs = [
        ['auto', '自动重做', '租户可配置'],
        ['models', '模型 API', '仅平台管理员']
      ];
      const presetFormTabs = [
        ['basic', '基本信息'],
        ['shooting', '拍摄参数'],
        ['exif', 'EXIF增强'],
        ['copyright', '版权信息'],
        ['ai', 'AI提示词']
      ];
      const presetAspectRatios = [['4:3', 4, 3], ['3:2', 3, 2], ['16:9', 16, 9], ['1:1', 1, 1], ['4:5', 4, 5], ['9:16', 9, 16]];
      const englishPhotographerPool = {
        first: ['Mark', 'James', 'Emily', 'Sarah', 'Michael', 'David', 'Emma', 'Olivia', 'Daniel', 'Sophia', 'Ryan', 'Laura', 'Chris', 'Anna', 'Nathan', 'Grace', 'Ethan', 'Chloe'],
        last: ['Johnson', 'Smith', 'Williams', 'Brown', 'Miller', 'Davis', 'Wilson', 'Anderson', 'Taylor', 'Thomas', 'Moore', 'Martin', 'Clark', 'Lewis', 'Walker', 'Hall', 'Young', 'King']
      };
      const copyrightStudioPool = ['Crystal Imaging', 'Prism Creative Studios', 'Northlight Studio', 'Amber Frame Co', 'BlueHour Photos', 'Summit Lens Lab', 'Harbor Pixel Works', 'Canvas & Light'];
      const randomEnglishAuthor = () => `${englishPhotographerPool.first[Math.floor(Math.random() * englishPhotographerPool.first.length)]} ${englishPhotographerPool.last[Math.floor(Math.random() * englishPhotographerPool.last.length)]}`;
      const randomCopyrightNotice = () => `© ${new Date().getFullYear()} ${copyrightStudioPool[Math.floor(Math.random() * copyrightStudioPool.length)]}`;
      const displayRole = (value) => ({ merchant: '商家', support: '技术客服', admin: '平台管理员' }[value] || value);
      const canManageSystem = () => state.role === 'admin';
      const canManageUsers = () => state.role === 'admin' || state.role === 'support';
      const currentTenantId = () => role().tenantId || 'DEMO-01';

      const messageRecipient = (userId) => {
        const user = state.system.users.find((entry) => entry.id === userId);
        const meta = Object.values(roleMeta).find((entry) => entry.userId === userId);
        return userId && (user || meta) ? { recipientId: userId, tenantId: user?.tenantId || meta.tenantId || 'SUPPORT' } : null;
      };
      const currentMessageRecipient = () => messageRecipient(role().userId);
      const tenantMessageRecipient = (tenantId) => messageRecipient(state.system.users.find((user) => user.tenantId === tenantId && user.role === 'merchant')?.id || (tenantId === 'PLATFORM' ? roleMeta.admin.userId : null));
      const ticketMessageRecipient = (ticket) => {
        if (ticket.recipientId) return { recipientId: ticket.recipientId, tenantId: ticket.tenantId || messageRecipient(ticket.recipientId)?.tenantId };
        const tenantId = ticket.tenantId || ticket.freezeEvent?.tenantId || ticket.tenant?.split(' · ').pop();
        return tenantMessageRecipient(tenantId);
      };
      const sameAccountScope = (left, right) => !!(left?.recipientId && right?.recipientId && left.recipientId === right.recipientId && left.tenantId === right.tenantId);
      const ownsHistory = (item, recipient = currentMessageRecipient()) => sameAccountScope(item?.messageRecipient, recipient);
      const visibleHistory = () => {
        const recipient = currentMessageRecipient();
        return state.history.filter((item) => ownsHistory(item, recipient));
      };
      const findOwnedHistory = (id) => visibleHistory().find((item) => item.id === id);
      const visibleMessages = () => {
        const recipient = currentMessageRecipient();
        return state.messages.filter((message) => message.recipientId === recipient.recipientId && message.tenantId === recipient.tenantId);
      };
      const notifyAccount = (message, recipient = currentMessageRecipient()) => {
        if (!recipient?.recipientId || !recipient.tenantId) return;
        state.messages.unshift({ ...message, ...recipient });
      };
      const initializeMessages = () => {
        state.messages = state.messages.map((message) => {
          if (message.recipientId && message.tenantId) return message;
          const recipient = messageRecipient(message.recipientId || message.userId) || tenantMessageRecipient(message.tenantId || 'DEMO-01');
          return { ...message, recipientId: message.recipientId || recipient?.recipientId || 'LEGACY-UNASSIGNED', tenantId: message.tenantId || recipient?.tenantId || 'UNKNOWN' };
        });
        const merchantOwner = messageRecipient(roleMeta.merchant.userId) || { recipientId: 'USR-001', tenantId: 'DEMO-01' };
        state.history.forEach((item) => {
          item.tenantId ||= 'DEMO-01';
          if (!item.messageRecipient?.recipientId || !item.messageRecipient?.tenantId) {
            item.messageRecipient = tenantMessageRecipient(item.tenantId) || merchantOwner;
          }
        });
        state.jobs.forEach((job) => {
          job.payload.messageRecipient ||= state.history.find((item) => item.id === job.historyId)?.messageRecipient || tenantMessageRecipient(job.tenantId);
        });
      };
      const navigate = (page) => { userDialog = null; resultDialog = null; resourceDialog = null; page = ['batch','upload','import'].includes(page) ? 'resources' : page; state.page = page; state.selectedId = null; state.session = page !== 'login'; if (page === 'login') state.session = false; location.hash = page; persist(); render(); window.scrollTo({ top: 0, behavior: 'smooth' }); };
      const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
      const makePreviewDataUrl = (label, variant = 'teal') => {
        const palette = variant === 'coral' ? ['#ffd1c2', '#ee8066', '#3c2630'] : variant === 'purple' ? ['#d9d4ff', '#9a8be8', '#24273f'] : ['#d2efe8', '#1aa89a', '#233b4b'];
        const title = escapeHtml(String(label || '生成结果').replace(/\.[^.]+$/, '').slice(0, 24));
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${palette[0]}"/><stop offset=".52" stop-color="${palette[1]}"/><stop offset="1" stop-color="${palette[2]}"/></linearGradient></defs><rect width="1200" height="900" fill="url(#g)"/><circle cx="920" cy="180" r="230" fill="rgba(255,255,255,.18)"/><path d="M0 700 C260 540 420 820 680 650 S980 540 1200 690 V900 H0Z" fill="rgba(12,34,45,.32)"/><text x="64" y="116" font-family="Arial,sans-serif" font-size="30" font-weight="700" fill="rgba(255,255,255,.78)">HONEY BADGER</text><text x="64" y="790" font-family="Arial,sans-serif" font-size="38" font-weight="700" fill="#fff">${title}</text></svg>`;
        return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
      };
      const formatSource = (source) => sourceLabels[source] || source;
      const statusClass = (status) => ({ FILE_READY:'pill-blue', REVIEW_REQUIRED:'pill-amber', DETECTION_UNKNOWN:'pill-amber', QUALITY_FAILED:'pill-red', LEGACY_REVIEW:'pill-amber', GENERATED:'pill-green', GENERATING:'pill-blue', DELIVERED:'pill-green', AUTO_REPROCESS_PENDING:'pill-amber', FAILED:'pill-red', TECH_FAILED:'pill-red', PRE_REVIEW_FAILED:'pill-red', IMAGE_LOCKED:'pill-red', REJECTED:'pill-red', FULL_PROCESSING:'pill-blue', DETECTION:'pill-blue', PRE_REVIEW:'pill-blue', EXPIRED:'pill-gray', DELETED:'pill-gray' }[status] || 'pill-gray');
      const deviceStatusClass = (status) => ({ '启用': 'pill-green', '停用': 'pill-gray', '未启用': 'pill-gray', '待复核': 'pill-amber' }[status] || 'pill-gray');
      const devicePresetRows = () => {
        const view = state.system.devicePresetView || { query: '', category: 'all', review: 'all', page: 1, pageSize: 20, detailId: null };
        const query = String(view.query || '').trim().toLowerCase();
        const filtered = state.system.devicePresets.filter((preset) => {
          const matchesQuery = !query || [preset.name, preset.camera, preset.lens, preset.sourceId, preset.templateRef, preset.familyLabel].some((value) => String(value ?? '').toLowerCase().includes(query));
          const matchesCategory = view.category === 'all' || preset.category === view.category;
          const matchesReview = view.review === 'all' || (preset.demo ? view.review === 'demo' : preset.reviewBucket === view.review);
          return matchesQuery && matchesCategory && matchesReview;
        });
        const pageSize = Number(view.pageSize) || 20;
        const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
        const page = Math.min(Math.max(1, Number(view.page) || 1), pageCount);
        if (view.page !== page) view.page = page;
        return { filtered, items: filtered.slice((page - 1) * pageSize, page * pageSize), page, pageCount, pageSize };
      };
      const paginate = (items, view, pageSizeKey = 'pageSize') => {
        const pageSize = Number(view?.[pageSizeKey]) || 10;
        const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
        const page = Math.min(Math.max(1, Number(view?.page) || 1), pageCount);
        if (view) view.page = page;
        return { items: items.slice((page - 1) * pageSize, page * pageSize), page, pageCount, pageSize, total: items.length };
      };
      const renderPager = ({ page, pageCount, pageSize, total, prevAction, nextAction }) => `<div class="form-footer pager" style="margin-top:14px;"><span class="pager-summary" style="font-size:12px;color:var(--ink-soft);">第 ${page} / ${pageCount} 页 · 每页 ${pageSize} 条 · 共 ${total} 条</span><div style="display:flex;gap:8px;"><button class="btn btn-ghost btn-sm" data-action="${prevAction}" ${page <= 1 ? 'disabled' : ''}>上一页</button><button class="btn btn-ghost btn-sm" data-action="${nextAction}" ${page >= pageCount ? 'disabled' : ''}>下一页</button></div></div>`;
      const presetCategoryLabels = { phone: '手机', dslr: '单反', mirrorless: '无反', action: '运动相机', medium_format: '中画幅', fixed_lens: '固定镜头', panoramic_360: '全景 / 360', rangefinder: '旁轴' };
      const presetFieldSections = {
        basic: [
          { title: null, fields: [
            { name: 'name', label: '预设名称', required: true, placeholder: '输入预设名称' },
            { name: 'description', label: '描述', placeholder: '预设简要描述' },
            { name: 'category', label: '设备类别', required: true, placeholder: '选择设备类型', select: Object.entries(presetCategoryLabels) },
            { name: 'is_public', label: '平台公共预设', checkbox: true }
          ] }
        ],
        shooting: [
          { title: '基础拍摄参数', tone: '#3b82f6', fields: [
            { name: 'iso', label: 'ISO', type: 'number', placeholder: '400' },
            { name: 'shutter_speed', label: '快门速度', placeholder: '1/125' },
            { name: 'aperture', label: '光圈值 (f/)', type: 'number', step: '0.1', placeholder: '2.8' },
            { name: 'focal_length', label: '焦距 (mm)', type: 'number', step: '0.01', placeholder: '6.765' },
            { name: 'focal_length_equiv', label: '等效焦距 (mm)', type: 'number', step: '0.1', placeholder: '26' },
            { name: 'ev_value', label: 'EV 值', type: 'number', step: '0.1', placeholder: '0' },
            { name: 'white_balance', label: '白平衡', placeholder: 'Auto', select: [['Auto', 'Auto'], ['Daylight', 'Daylight'], ['Cloudy', 'Cloudy'], ['Tungsten', 'Tungsten'], ['Fluorescent', 'Fluorescent'], ['Shade', 'Shade']] },
            { name: 'metering_mode', label: '测光模式', placeholder: '--选择--', select: [['', '--选择--'], ['Multi-segment', 'Multi-segment'], ['Center-weighted', 'Center-weighted'], ['Spot', 'Spot'], ['Evaluative', 'Evaluative']] },
            { name: 'exposure_mode', label: '曝光模式', placeholder: '--选择--', select: [['', '--选择--'], ['Auto', 'Auto'], ['Program', 'Program'], ['Aperture Priority', 'Aperture Priority'], ['Shutter Priority', 'Shutter Priority'], ['Manual', 'Manual']] },
            { name: 'iso_range', label: 'ISO 范围', placeholder: '100-3200' },
            { name: 'shutter_type', label: '快门类型', placeholder: 'Mechanical / Electronic / EFCS', select: [['', '--选择--'], ['Mechanical', '机械'], ['Electronic', '电子'], ['EFCS', '电子前帘']] },
            { name: 'exposure_compensation', label: '曝光补偿', type: 'number', step: '0.1', placeholder: '0' },
            { name: 'focus_distance', label: '对焦距离', type: 'number', step: '0.1', placeholder: '0.3' },
            { name: 'color_temperature', label: '色温 (K)', type: 'number', placeholder: '5500' },
            { name: 'scene_mode', label: '场景模式', placeholder: 'Portrait / Landscape / Sports / Night' },
            { name: 'color_mode', label: '色彩模式', placeholder: 'Vivid / Natural / Monochrome' }
          ] },
          { title: '设备信息', tone: '#8b5cf6', fields: [
            { name: 'camera_make', label: '手机 / 相机品牌', required: true, placeholder: 'Apple / Huawei / Xiaomi / Canon...' },
            { name: 'camera_model', label: '手机 / 相机型号', required: true, placeholder: 'iPhone 15 Pro...' },
            { name: 'lens_model', label: '镜头型号', placeholder: '内置主摄...' },
            { name: 'lens_make', label: '镜头品牌', placeholder: 'Apple / Canon / Nikon / Sony' },
            { name: 'sensor_size', label: '传感器尺寸', placeholder: '1/1.28 inch...' },
            { name: 'sensor_type', label: '传感器类型', placeholder: 'CMOS BSI Stacked...' },
            { name: 'stabilization', label: '防抖类型', placeholder: 'OIS...' },
            { name: 'lens_max_aperture', label: '镜头最大光圈', type: 'number', step: '0.1', placeholder: '1.4' },
            { name: 'flash_mode', label: '闪光模式', placeholder: 'Off / Auto / Fill-in' },
            { name: 'ambient_light', label: '环境光', placeholder: 'Natural Light / Artificial / Mixed' },
            { name: 'lighting', label: '光线条件', placeholder: 'Natural / Studio / Backlight' },
            { name: 'background', label: '背景', placeholder: 'White / Black / Outdoor' }
          ] },
          { title: '图像属性', tone: '#22c55e', aspectRatio: true, fields: [
            { name: 'image_width', label: '图像宽度 (px)', type: 'number', placeholder: '4032' },
            { name: 'image_height', label: '图像高度 (px)', type: 'number', placeholder: '3024' },
            { name: 'color_depth', label: '色深 (bit)', type: 'number', placeholder: '请选择', select: [['', '请选择'], ['8', '8'], ['10', '10'], ['12', '12'], ['14', '14']] },
            { name: 'image_format', label: '图像格式', placeholder: 'JPEG', select: [['JPEG', 'JPEG'], ['HEIC', 'HEIC'], ['RAW', 'RAW'], ['PNG', 'PNG']] },
            { name: 'color_space', label: '色彩空间', placeholder: 'sRGB', select: [['sRGB', 'sRGB'], ['Display P3', 'Display P3'], ['AdobeRGB', 'AdobeRGB']] },
            { name: 'software', label: '后期软件', placeholder: 'Apple iOS 17 / Lightroom...' },
            { name: 'pixel_density', label: '像素密度', type: 'number', placeholder: '460 / 326 / 264' },
            { name: 'image_orientation', label: '图像方向', type: 'number', placeholder: '1 / 3 / 6 / 8' },
            { name: 'compression_ratio', label: '压缩比', type: 'number', step: '0.01', placeholder: '0.85 / 0.9 / 0.95' },
            { name: 'sharpening', label: '锐化', placeholder: 'Normal / Low / High / None' },
            { name: 'noise_reduction', label: '降噪', placeholder: 'Low / Normal / High / None' },
            { name: 'post_processing', label: '后期处理', placeholder: 'None / Basic / Advanced' },
            { name: 'image_description', label: '图像描述', placeholder: 'Product photo taken with iPhone 15 Pro' },
            { name: 'keywords', label: '关键词', placeholder: 'product,phone,iphone' }
          ] }
        ],
        exif: [
          { title: 'GPS 坐标配置', tone: '#22c55e', exifProgress: true, fields: [
            { name: 'gps_mode', label: 'GPS 生成模式', placeholder: '不写入 GPS', select: [['none', '不写入 GPS'], ['fixed', '固定坐标'], ['random_by_scene', '按场景随机']] },
            { name: 'scene_type', label: '场景类型（随机生成时使用）', placeholder: '城市', gpsModes: ['random_by_scene'], select: [['urban', '城市'], ['landscape', '风景'], ['beach', '海滩'], ['mountain', '山地'], ['street', '街拍'], ['indoor', '室内']] },
            { name: 'gps_latitude', label: 'GPS 纬度', type: 'number', step: '0.000001', placeholder: '39.9042 / 31.2304', gpsModes: ['fixed'] },
            { name: 'gps_longitude', label: 'GPS 经度', type: 'number', step: '0.000001', placeholder: '116.4074 / 121.4737', gpsModes: ['fixed'] },
            { name: 'gps_altitude', label: 'GPS 海拔 (m)', type: 'number', step: '0.1', placeholder: '50 / 100 / 200', gpsModes: ['fixed'] }
          ] },
          { title: 'MakerNote 模板', tone: '#8b5cf6', fields: [
            { name: 'maker_note_template', label: 'MakerNote 模板（可选，空则自动按相机品牌选择）', placeholder: '自动（根据相机品牌）', select: [['', '自动（根据相机品牌）'], ['apple_iphone15pro', 'Apple iPhone 15 Pro'], ['canon_eos_r5', 'Canon EOS R5'], ['nikon_z9', 'Nikon Z9'], ['sony_a7r5', 'Sony A7R V'], ['gopro_hero12', 'GoPro Hero 12']] },
            { name: 'focal_plane_x_res', label: 'FocalPlane X 分辨率', type: 'number', step: '0.01', placeholder: '4032' },
            { name: 'focal_plane_y_res', label: 'FocalPlane Y 分辨率', type: 'number', step: '0.01', placeholder: '3024' },
            { name: 'burst_sequence', label: '连拍序号', type: 'number', placeholder: '1' },
            { name: 'file_number', label: '文件编号', type: 'number', placeholder: '1' },
            { name: 'raw_version', label: 'RAW 版本', placeholder: '1.0' },
            { name: 'is_default', label: '是否默认', placeholder: '0 / 1', select: [['0', '否'], ['1', '是']] }
          ] }
        ],
        copyright: [
          { title: '版权信息（可选）', tone: '#f59e0b', fields: [
            { name: 'author', label: '作者', random: 'author', placeholder: 'Mark Johnson' },
            { name: 'copyright', label: '版权声明', random: 'copyright', placeholder: '© 2026 Crystal Imaging' }
          ] }
        ],
        ai: [
          { title: null, fields: [
            { name: 'prompt_template_id', label: 'AI 提示词模板', templateSelect: true },
            { name: 'ai_positive_prompt', label: 'AI 正向提示词', textarea: true, placeholder: '描述您想要生成的图片内容，例如：生成3张 a serene mountain landscape at sunset, photorealistic...' },
            { name: 'ai_negative_prompt', label: 'AI 负向提示词', textarea: true, placeholder: '描述不希望出现的内容，例如：blurry, low quality, watermark...' },
            { name: 'ai_strength', label: 'AI 强度', type: 'number', step: '0.01', min: '0.05', max: '0.5', placeholder: '0.15' },
            { name: 'ai_img2img_strength', label: '图生图强度', type: 'number', step: '0.01', min: '0.05', max: '1', placeholder: '0.20' }
          ] }
        ]
      };
      const presetFieldGroups = Object.fromEntries(Object.entries(presetFieldSections).map(([key, sections]) => [key, sections.flatMap((section) => section.fields)]));
      const presetFieldNames = Object.values(presetFieldGroups).flat().map((field) => field.name);
      const presetExifKeyFields = ['gps_mode', 'scene_type', 'maker_note_template', 'focal_plane_x_res', 'focal_plane_y_res', 'burst_sequence', 'file_number', 'raw_version', 'camera_make', 'camera_model', 'lens_model'];
      const presetFormValue = (preset, field) => {
        const raw = preset?.parameterJson || {};
        if (field.name === 'is_public') return preset?.visibility === '公共' || raw.is_public === 1 || raw.is_public === true;
        const value = raw[field.name] ?? preset?.[field.name] ?? '';
        return value == null ? '' : value;
      };
      const presetFormDefaults = (preset = null) => {
        const values = {};
        presetFieldNames.forEach((name) => { values[name] = presetFormValue(preset, { name }); });
        if (!values.category || !presetCategoryLabels[values.category]) values.category = preset?.parameterJson?.category || 'phone';
        if (!values.gps_mode) values.gps_mode = preset?.gpsPolicy || 'none';
        if (!values.scene_type) values.scene_type = 'urban';
        if (!values.image_format) values.image_format = 'JPEG';
        if (!values.color_space) values.color_space = 'sRGB';
        if (!values.ai_strength) values.ai_strength = '0.15';
        if (!values.ai_img2img_strength) values.ai_img2img_strength = '0.20';
        return values;
      };
      const renderPresetFieldLabel = (field) => {
        const required = field.required ? ' *' : '';
        if (!field.random) return `<label>${escapeHtml(field.label)}${required}</label>`;
        return `<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px;"><label style="margin:0;">${escapeHtml(field.label)}${required}</label><button type="button" class="table-link" data-action="preset-random" data-random="${escapeHtml(field.random)}" style="font-size:12px;font-weight:700;display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">↻ 随机生成</button></div>`;
      };
      const renderPresetField = (field, values) => {
        const value = presetFormValue({ parameterJson: values }, field);
        if (field.checkbox) return `<label class="check-field"><input type="checkbox" name="${field.name}" ${value ? 'checked' : ''} /><span>${field.label}</span></label>`;
        const placeholder = field.placeholder || `填写${field.label}`;
        const gpsModes = field.gpsModes || [];
        const gpsAttrs = gpsModes.length ? ` data-gps-mode-field="true" data-gps-modes="${gpsModes.join(',')}" style="${gpsModes.includes(String(values.gps_mode || 'none')) ? '' : 'display:none;'}"` : '';
        const labelHtml = renderPresetFieldLabel(field);
        if (field.templateSelect) {
          const options = (typeof visiblePromptTemplates === 'function' ? visiblePromptTemplates() : state.promptTemplates || []).map((item) => `<option value="${escapeHtml(item.id)}" ${String(value) === String(item.id) ? 'selected' : ''}>${escapeHtml(item.name)}${item.scope === 'platform' ? ' · 平台' : ' · 租户'}</option>`).join('');
          return `<div class="field full"${gpsAttrs}>${labelHtml}<select name="${field.name}" data-preset-prompt-template="true"><option value="">不使用模板</option>${options}</select></div>`;
        }
        if (field.select) return `<div class="field"${gpsAttrs}>${labelHtml}<select name="${field.name}">${field.select.map(([key, label]) => `<option value="${escapeHtml(key)}" ${String(value) === String(key) ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select></div>`;
        if (field.textarea) return `<div class="field full"${gpsAttrs}>${labelHtml}<textarea name="${field.name}" rows="4" placeholder="${escapeHtml(placeholder)}">${escapeHtml(value)}</textarea></div>`;
        const attrs = [field.type ? `type="${field.type}"` : 'type="text"', field.step ? `step="${field.step}"` : '', field.min ? `min="${field.min}"` : '', field.max ? `max="${field.max}"` : '', `placeholder="${escapeHtml(placeholder)}"`].filter(Boolean).join(' ');
        return `<div class="field"${gpsAttrs}>${labelHtml}<input ${attrs} name="${field.name}" value="${escapeHtml(value)}" /></div>`;
      };
      const renderPresetAspectPicker = () => `<div class="field full"><label>宽高比快速选择</label><div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:4px;">${presetAspectRatios.map(([label]) => `<button type="button" class="btn btn-ghost btn-sm" data-action="preset-aspect" data-ratio="${label}" style="min-width:52px;">${label}</button>`).join('')}</div></div>`;
      const renderPresetExifProgress = (values) => {
        const filled = presetExifKeyFields.filter((name) => {
          const raw = values?.[name];
          if (name === 'gps_mode') return raw && raw !== 'none';
          return raw !== undefined && raw !== null && String(raw).trim() !== '';
        }).length;
        const total = presetExifKeyFields.length;
        const rate = Math.round((filled / total) * 100);
        const barColor = rate >= 70 ? '#22c55e' : rate >= 40 ? '#f59e0b' : '#ef4444';
        return `<div style="margin-bottom:14px;padding:12px 14px;border-radius:12px;background:#f8fafc;border:1px solid #e8eef2;"><div style="display:flex;justify-content:space-between;gap:12px;align-items:center;"><strong style="font-size:13px;">EXIF字段完整度（手机标准）</strong><span class="tiny muted">${filled}/${total} · 预估通过率 ${rate}%</span></div><div style="margin-top:8px;height:8px;border-radius:999px;background:#e8eef2;overflow:hidden;"><div style="width:${rate}%;height:100%;background:${barColor};"></div></div></div>`;
      };
      const renderPresetSubhead = (title, tone) => title ? `<div style="display:flex;align-items:center;gap:8px;margin:4px 0 12px;"><span style="width:8px;height:8px;border-radius:50%;background:${tone || 'var(--teal)'};flex:0 0 auto;"></span><strong style="font-size:13px;font-weight:800;">${escapeHtml(title)}</strong></div>` : '';
      const syncPresetGpsFields = (form) => {
        const mode = String(form?.querySelector('[name="gps_mode"]')?.value || 'none');
        form?.querySelectorAll('[data-gps-mode-field]').forEach((field) => {
          const modes = String(field.dataset.gpsModes || '').split(',').filter(Boolean);
          field.style.display = modes.includes(mode) ? '' : 'none';
        });
      };
      const enabledDevicePresets = () => state.system.devicePresets.filter((preset) => preset.status === '启用');
      const presetOptions = (selected = '') => enabledDevicePresets().map((preset) => `<option value="${escapeHtml(preset.name)}" ${String(selected) === String(preset.name) ? 'selected' : ''}>${escapeHtml(preset.name)} · ${escapeHtml(preset.category)}</option>`).join('');
      const directPresetCatalog = () => state.system.devicePresets.filter((preset) => preset && preset.status === '启用');
      const directPresetRaw = (preset) => preset?.parameterJson || {};
      const directPresetType = (preset) => deviceCategoryLabels[directPresetRaw(preset).category] || preset?.category || '待分类';
      const directPresetBrand = (preset) => directPresetRaw(preset).camera_make || preset?.cameraMake || String(preset?.camera || '').trim().split(/\s+/)[0] || '未标注品牌';
      const directPresetModel = (preset) => {
        const raw = directPresetRaw(preset);
        if (raw.camera_model) return raw.camera_model;
        if (preset?.cameraModel) return preset.cameraModel;
        const camera = String(preset?.camera || '').trim();
        const brand = directPresetBrand(preset);
        return camera && camera.startsWith(brand) ? camera.slice(brand.length).trim() : camera || preset?.name || '未标注型号';
      };
      const directPresetValue = (preset, key, fallback = '—') => {
        const value = directPresetRaw(preset)[key] ?? preset?.[key];
        return value === null || value === undefined || value === '' ? fallback : value;
      };
      const directPresetOptions = (values, selected, placeholder) => [`<option value="">${placeholder}</option>`, ...values.map((value) => `<option value="${escapeHtml(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${escapeHtml(value)}</option>`)].join('');
      const directPresetSelection = () => {
        const catalog = directPresetCatalog();
        const byId = catalog.find((item) => String(item.id) === String(state.directPresetId));
        const byName = catalog.find((item) => String(item.name) === String(state.directPresetName));
        const remembered = byId || byName || catalog[0] || null;
        const types = [...new Set(catalog.map(directPresetType))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
        const type = types.includes(state.directPresetType) ? state.directPresetType : directPresetType(remembered);
        const typeItems = catalog.filter((item) => directPresetType(item) === type);
        const brands = [...new Set(typeItems.map(directPresetBrand))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
        const rememberedBrand = directPresetBrand(remembered);
        const brand = brands.includes(state.directPresetBrand) ? state.directPresetBrand : (brands.includes(rememberedBrand) ? rememberedBrand : (brands[0] || ''));
        const brandItems = typeItems.filter((item) => directPresetBrand(item) === brand);
        const models = [...new Set(brandItems.map(directPresetModel))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
        const rememberedModel = directPresetModel(remembered);
        const model = models.includes(state.directPresetModel) ? state.directPresetModel : (models.includes(rememberedModel) ? rememberedModel : (models[0] || ''));
        const exact = brandItems.find((item) => directPresetModel(item) === model) || brandItems[0] || typeItems[0] || remembered || catalog[0] || null;
        return { catalog, types, type, typeItems, brands, brand, brandItems, models, model, preset: exact };
      };
      const directSelectedPreset = () => directPresetSelection().preset;
      const directPresetExifRows = (preset) => {
        if (!preset) return [];
        const value = (key, fallback = '—') => directPresetValue(preset, key, fallback);
        const aperture = value('aperture');
        return [
          ['ISO', value('iso')], ['快门', value('shutter_speed')], ['光圈', aperture === '—' || String(aperture).startsWith('f/') ? aperture : `f/${aperture}`],
          ['焦距', value('focal_length') === '—' ? '—' : `${value('focal_length')}mm`], ['等效焦距', value('focal_length_equiv') === '—' ? '—' : `${value('focal_length_equiv')}mm`],
          ['白平衡', value('white_balance')], ['测光', value('metering_mode')], ['传感器', value('sensor_size')],
          ['色彩空间', value('color_space')], ['防抖', value('stabilization')], ['镜头', value('lens_model')], ['软件', value('software')]
        ].map(([label, display]) => `<span><small>${label}</small><strong>${escapeHtml(display)}</strong></span>`).join('');
      };
      const directPresetGpsSummary = (preset) => {
        const raw = preset?.parameterJson || {};
        const mode = raw.gps_mode || preset?.gpsPolicy || 'none';
        if (mode === 'fixed') return `固定坐标 · ${raw.gps_latitude || '—'}, ${raw.gps_longitude || '—'}${raw.gps_altitude ? ` · 海拔 ${raw.gps_altitude}m` : ''}`;
        if (mode === 'random_by_scene') return `按场景随机 · ${raw.scene_type || 'urban'}`;
        return '不写入 GPS';
      };
      const renderDirectExifPreset = () => {
        const selection = directPresetSelection();
        const preset = selection.preset;
        const currentName = preset?.name || '';
        const chooser = `<div class="field"><label>设备类型 <span>来源：设备预设</span></label><select data-direct-preset-field="type">${directPresetOptions(selection.types, selection.type, '请选择设备类型')}</select></div><div class="field"><label>设备品牌 <span>随设备类型变化</span></label><select data-direct-preset-field="brand">${directPresetOptions(selection.brands, selection.brand, '请选择设备品牌')}</select></div><div class="field"><label>设备型号 <span>随品牌变化</span></label><select data-direct-preset-field="model">${directPresetOptions(selection.models, selection.model, '请选择设备型号')}</select></div>`;
        const preview = preset ? `<div class="exif-preset-preview"><div class="split" style="align-items:center;gap:12px;"><div><div class="tiny muted">参数预览 · ${escapeHtml(currentName)}${preset.status && preset.status !== '启用' ? ` · ${escapeHtml(preset.status)}` : ''}</div><div class="tiny muted" style="margin-top:5px;">设备：${escapeHtml(directPresetBrand(preset))} ${escapeHtml(directPresetModel(preset))} · GPS：${escapeHtml(directPresetGpsSummary(preset))}</div></div><button type="button" class="btn btn-ghost btn-sm" data-action="toggle-direct-preview" aria-expanded="${state.directPresetPreviewOpen ? 'true' : 'false'}">${state.directPresetPreviewOpen ? '收起全部' : '查看全部'}</button></div>${state.directPresetPreviewOpen ? `<div class="exif-preset-preview-grid">${directPresetExifRows(preset)}</div>` : ''}</div>` : `<div class="empty" style="margin-top:14px;"><strong>暂无可用设备预设</strong><span>请先在设备预设中维护记录。</span></div>`;
        return `<section class="process-settings-block"><div class="split" style="align-items:center;gap:12px;flex-wrap:wrap;"><strong style="font-size:13px;">参数设置</strong></div><div class="form-grid three" style="margin-top:12px;align-items:end;">${chooser}</div>${preview}<input type="hidden" name="preset" value="${escapeHtml(currentName)}" /></section>`;
      };
      const renderDevicePresetDetail = (preset) => {
        if (!preset) return '';
        const params = preset.parameterJson || {};
        return `<section class="card card-pad" style="margin-top:18px;"><div class="section-head"><div><h3>参数详情 · ${escapeHtml(preset.name)}</h3><p class="tiny muted" style="margin-top:5px;">来源 ID ${escapeHtml(preset.sourceId || preset.id)} · ${escapeHtml(preset.templateRef || 'demo')} · ${escapeHtml(preset.version)} · ${escapeHtml(preset.activationStatus || 'DEMO')}</p></div><button class="btn btn-ghost btn-sm" data-action="close-preset-detail">关闭详情</button></div><div class="grid grid-3" style="margin-bottom:14px;"><div><div class="tiny muted">设备形态</div><strong>${escapeHtml(preset.familyLabel || preset.category)}</strong></div><div><div class="tiny muted">当前状态</div><span class="pill ${deviceStatusClass(preset.status)}">${escapeHtml(preset.status)}</span></div><div><div class="tiny muted">来源可见性</div><strong>${escapeHtml(preset.sourceVisibility || preset.visibility || '—')}</strong></div></div><div class="table-wrap"><table><thead><tr><th>参数字段</th><th>参数值</th></tr></thead><tbody>${Object.entries(params).map(([key, value]) => `<tr><td class="mono">${escapeHtml(key)}</td><td class="param-value">${escapeHtml(typeof value === 'object' ? JSON.stringify(value) : value == null ? 'null' : value)}</td></tr>`).join('')}</tbody></table></div></section>`;
      };
      const renderImportedDevicePresetSettings = () => {
        const view = state.system.devicePresetView;
        const result = devicePresetRows();
        const selected = state.system.devicePresets.find((preset) => String(preset.id) === String(view.detailId));
        const categories = [...new Set(state.system.devicePresets.map((preset) => preset.category).filter(Boolean))].sort();
        const rows = result.items.map((preset, index) => `<tr><td class="mono tiny">${(result.page - 1) * result.pageSize + index + 1}</td><td><button class="table-link" data-action="view-preset" data-id="${escapeHtml(preset.id)}">${escapeHtml(preset.name)}</button><div class="tiny muted">${escapeHtml(preset.sourceId ? `来源 ${preset.sourceId}` : preset.id)} · ${escapeHtml(preset.templateRef || '公共预设')}</div></td><td>${escapeHtml(preset.category)}<div class="tiny muted">${escapeHtml(preset.familyLabel || '')}</div></td><td>${escapeHtml(preset.camera)}<div class="tiny muted">${escapeHtml(preset.lens)}</div></td><td>${escapeHtml(preset.iso)}<div class="tiny muted">${escapeHtml(preset.shutter)} · ${escapeHtml(preset.aperture)}</div></td><td>${escapeHtml(preset.ev)}<div class="tiny muted">GPS ${escapeHtml(preset.gpsPolicy)}</div></td><td><span class="pill ${deviceStatusClass(preset.status)}">${escapeHtml(preset.status)}</span><div class="tiny muted">${escapeHtml(preset.visibility || '')}</div></td><td><button class="btn btn-ghost btn-sm" data-action="toggle-preset" data-id="${escapeHtml(preset.id)}">${preset.status === '启用' ? '停用' : '启用'}</button></td></tr>`).join('');
        return `<section class="card form-card"><div class="section-head"><div><h3>设备预设与完整参数目录</h3></div><span class="pill pill-amber">${devicePresetSource.status || 'NOT_ACTIVATED'}</span></div><form data-form="device-preset"><div class="form-grid"><div class="field"><label>预设名称</label><input name="name" placeholder="例如 中画幅 · 棚拍" /></div><div class="field"><label>设备类别</label><select name="category"><option>手机</option><option>无反</option><option>单反</option><option>运动相机</option><option>中画幅</option></select></div><div class="field"><label>相机型号</label><input name="camera" placeholder="例如 Fujifilm GFX100 II" /></div><div class="field"><label>镜头</label><input name="lens" placeholder="例如 GF 80mm F1.7" /></div><div class="field"><label>ISO</label><input name="iso" type="number" value="100" min="1" /></div><div class="field"><label>快门速度</label><input name="shutter" value="1/125" /></div><div class="field"><label>光圈</label><input name="aperture" value="f/4.0" /></div><div class="field"><label>EV 值</label><input name="ev" type="number" value="0" step="0.1" /></div><div class="field"><label>GPS 策略</label><select name="gpsPolicy"><option>可选</option><option>关闭</option><option>固定</option></select></div></div><div class="form-footer"><button class="btn btn-primary" type="submit">新增设备预设</button></div></form></section><section class="card card-pad" style="margin-top:18px;"><div class="section-head"><div><h3>预设版本列表</h3></div><span class="tiny muted">共 ${state.system.devicePresets.length} 条（含 3 条公共预设）</span></div><div class="filter-bar"><input id="device-preset-query" placeholder="搜索名称、相机、镜头、来源 ID" value="${escapeHtml(view.query)}" /><select id="device-preset-category"><option value="all">全部设备类别</option>${categories.map((category) => `<option value="${escapeHtml(category)}" ${view.category === category ? 'selected' : ''}>${escapeHtml(category)}</option>`).join('')}</select><select id="device-preset-review"><option value="all" ${view.review === 'all' ? 'selected' : ''}>全部复核状态</option><option value="demo" ${view.review === 'demo' ? 'selected' : ''}>公共预设</option><option value="STRUCTURAL_CANDIDATE" ${view.review === 'STRUCTURAL_CANDIDATE' ? 'selected' : ''}>结构候选</option><option value="QUARANTINE_REVIEW" ${view.review === 'QUARANTINE_REVIEW' ? 'selected' : ''}>待复核</option></select></div><div class="table-wrap"><table><thead><tr><th>#</th><th>预设 / 来源</th><th>类别 / 形态</th><th>相机 / 镜头</th><th>ISO / 曝光</th><th>EV / GPS</th><th>状态 / 可见性</th><th>操作</th></tr></thead><tbody>${rows || '<tr><td colspan="8"><div class="empty"><strong>没有符合条件的预设</strong><span>尝试清空搜索或切换复核状态。</span></div></td></tr>'}</tbody></table></div><div class="form-footer" style="margin-top:14px;"><div class="tiny muted">${result.page} / ${result.pageCount} 页 · 每页 ${result.pageSize} 条</div><div style="display:flex;gap:8px;"><button class="btn btn-ghost btn-sm" data-action="device-page-prev" ${result.page <= 1 ? 'disabled' : ''}>上一页</button><button class="btn btn-ghost btn-sm" data-action="device-page-next" ${result.page >= result.pageCount ? 'disabled' : ''}>下一页</button></div></div></section>${renderDevicePresetDetail(selected)}`;
      };
      const statusPill = (status) => `<span class="pill ${statusClass(status)}">${escapeHtml(statusLabels[status] || status)}</span>`;
      const scoreText = (score) => score == null ? '—' : `${score}`;
      const mockValidationOptions = (selected = 'pass') => Object.entries(validationCases).map(([key, value]) => `<option value="${key}" ${selected === key ? 'selected' : ''}>${value.label}</option>`).join('');
      const validateMockInput = (payload = {}) => {
        const key = payload.validationCase || 'pass';
        const issue = validationCases[key] || validationCases.pass;
        const requestedCount = Math.max(1, Math.min(10, Number(payload.quantity) || 1));
        const baseName = payload.fileName || 'demo-input.jpg';
        const sourceItems = payload.items?.length ? payload.items : Array.from({ length: requestedCount }, (_, i) => ({ name: requestedCount === 1 ? baseName : `${baseName.replace(/\.[^.]+$/, '')}-${String(i + 1).padStart(2, '0')}.jpg`, size: 2.8 * 1024 * 1024, type: 'image/jpeg' }));
        return sourceItems.slice(0, 10).map((item, index) => {
          const failed = key !== 'pass' && (key !== 'partial' || index === 1);
          return { ...item, index: index + 1, ok: !failed, errors: failed ? issue.errors : [] };
        });
      };
      const isAccountBlocked = () => state.role === 'merchant' && state.account?.status === 'FROZEN';
      const recordPreReviewFailure = (imageKey = 'demo-review-image.jpg', recipient = currentMessageRecipient()) => {
        const account = state.account;
        const count = Number(account.imageFailures?.[imageKey] || 0) + 1;
        account.imageFailures[imageKey] = count;
        if (count >= 2) account.imageLocks[imageKey] = true;
        if (!account.distinctFailures.includes(imageKey)) account.distinctFailures.push(imageKey);
        if (account.distinctFailures.length >= 3 && account.status !== 'FROZEN') {
          account.status = 'FROZEN';
          account.freezeEvent = { id: `FRZ-${Date.now()}`, tenantId: recipient?.tenantId || currentTenantId(), reason: '三张不同图片连续预审失败', time: demoNow };
          state.tickets.unshift({ id: `TK-${20 + state.tickets.length}`, kind: '账号冻结', ...recipient, tenant: `${state.system.users.find((user) => user.id === recipient?.recipientId)?.displayName || role().label} · ${recipient?.tenantId || currentTenantId()}`, ref: account.freezeEvent.id, status: '待解冻', owner: '技术客服', createdAt: demoNow, note: '三张不同图片连续预审失败，已生成客服工单。', freezeEvent: account.freezeEvent });
          notifyAccount({ id: `MSG-${40 + state.messages.length}`, type: 'danger', title: '账号已冻结', body: '三张不同图片连续预审失败，暂时禁止新建任务；历史结果仍可查看。', time: '刚刚', read: false }, recipient);
        }
        return { count, locked: !!account.imageLocks[imageKey], frozen: account.status === 'FROZEN' };
      };
      const recordPreReviewSuccess = () => { state.account.distinctFailures = []; };
      const makeItemResults = (chainId, payload, status, score, reason, count = 1) => {
        const names = payload.items?.length ? payload.items.map((x) => x.name) : Array.from({ length: count }, (_, i) => `${payload.fileName || 'result'}-${String(i + 1).padStart(2, '0')}.jpg`);
        const accessible = ['GENERATED','DELIVERED','FAILED','FILE_READY','REVIEW_REQUIRED','DETECTION_UNKNOWN'].includes(status);
        return names.slice(0, 10).map((name, index) => ({ id: `${chainId}-IMG-${String(index + 1).padStart(2, '0')}`, name, status, score, reason, resultAvailable: accessible, downloadable: accessible, resultUrl: accessible ? `https://demo.honeybadger.local/mock/results/${chainId}/${encodeURIComponent(name)}` : '', previewUrl: accessible ? makePreviewDataUrl(name, index % 3 === 1 ? 'coral' : index % 3 === 2 ? 'purple' : 'teal') : '', attempts: 1 }));
      };
      const makePartialResults = (chainId, payload, status, score, reason) => {
        const partial = payload.partialValidation;
        if (!partial?.length) return makeItemResults(chainId, payload, status, score, reason, Number(payload.quantity || payload.items?.length || 1));
        const validResults = makeItemResults(chainId, { ...payload, items: partial.filter((entry) => entry.ok).map((entry) => ({ name: entry.name })) }, status, score, reason, partial.filter((entry) => entry.ok).length);
        let validIndex = 0;
        return partial.map((entry, index) => {
          if (entry.ok) return { ...validResults[validIndex++], id: `${chainId}-IMG-${String(index + 1).padStart(2, '0')}`, name: entry.name };
          return { id: `${chainId}-IMG-${String(index + 1).padStart(2, '0')}`, name: entry.name, status: 'REJECTED', score: null, reason: entry.errors.join('；'), resultAvailable: false, downloadable: false, attempts: 1 };
        });
      };
      const makeMetadata = (payload = {}) => {
        const preset = payload.presetSnapshot || state.system.devicePresets.find((item) => item.name === payload.preset);
        const isGeneration = payload.taskType === 'generation' || (!payload.taskType && ['text','image'].includes(payload.mode || payload.source));
        return { width: payload.width || 1600, height: payload.height || 1200, fileSize: payload.fileSize || '2.8 MiB', devicePreset: isGeneration ? '未进行设备处理' : preset?.name || payload.preset || '—', exif: isGeneration ? '未进行 EXIF 处理' : '设备参数快照；来源线索另存检测报告', gps: isGeneration ? '未写入 GPS' : directPresetGpsSummary(preset), output: 'sRGB JPEG (.jpg)', retentionUntil: isGeneration ? '长期保留' : '2026-11-01 23:59', source: payload.source || 'mock' };
      };
      const historyResults = (item) => {
        if (!item) return [];
        const results = item.results?.length ? item.results : makeItemResults(item.id || 'CHAIN', { fileName: item.source === 'text' ? 'generated' : 'result' }, item.status || 'DELIVERED', item.score ?? null, item.status === 'FAILED' ? '检测未通过，结果保留但未收费。' : '', 1);
        const withPreview = results.map((result, index) => {
          const resource = result.resourceId && state.resources.find((entry) => entry.id === result.resourceId && entry.tenantId === item.tenantId);
          if (resource?.deletedAt) return { ...result, status: 'DELETED', reason: '原图已从图片资源删除', previewUrl: '', downloadable: false, resultAvailable: false };
          return { ...result, previewUrl: result.previewUrl || (result.resultAvailable !== false ? makePreviewDataUrl(result.name, index % 3 === 1 ? 'coral' : index % 3 === 2 ? 'purple' : 'teal') : '') };
        });
        return item.status === 'EXPIRED' || item.status === 'DELETED' ? withPreview.map((result) => ({ ...result, downloadable: false, resultAvailable: false })) : withPreview;
      };
      const canDownload = (item) => item && historyResults(item).some((result) => result.downloadable);
      const assetFileName = (asset, fallback = 'honeybadger-result.jpg') => {
        const raw = String(asset?.name || fallback).replace(/[^\w\u4e00-\u9fff.-]+/g, '-');
        return /\.[a-z0-9]{2,5}$/i.test(raw) ? raw : `${raw}.jpg`;
      };
      const assetBlob = async (asset) => {
        const response = await fetch(asset?.previewUrl || makePreviewDataUrl(asset?.name || '生成结果'));
        const contentType = response.headers.get('content-type') || '';
        if (!response.ok || !contentType.startsWith('image/')) throw new Error(`图片读取失败：HTTP ${response.status} (${contentType})`);
        const blob = await response.blob();
        if (!contentType.includes('svg+xml')) return blob;
        const url = URL.createObjectURL(blob);
        try {
          const image = new Image(); image.src = url; await image.decode();
          const canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
          const context = canvas.getContext('2d');
          if (!context) throw new Error('无法导出图片');
          context.drawImage(image, 0, 0);
          const type = /\.png$/i.test(assetFileName(asset)) ? 'image/png' : 'image/jpeg';
          return await new Promise((resolve, reject) => canvas.toBlob((file) => file ? resolve(file) : reject(new Error('图片编码失败')), type, .92));
        } finally { URL.revokeObjectURL(url); }
      };
      const triggerBrowserDownload = async (asset) => {
        const anchor = document.createElement('a');
        const url = URL.createObjectURL(await assetBlob(asset));
        anchor.href = url;
        anchor.download = assetFileName(asset);
        anchor.rel = 'noopener';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      };
      const saveAssetToUserPath = async (asset) => {
        const suggestedName = assetFileName(asset);
        if (typeof window.showSaveFilePicker === 'function') {
          const png = /\.png$/i.test(suggestedName);
          const handle = await window.showSaveFilePicker({ suggestedName, types: [{ description: png ? 'PNG 图片' : 'JPEG 图片', accept: png ? { 'image/png': ['.png'] } : { 'image/jpeg': ['.jpg', '.jpeg'] } }] });
          const writable = await handle.createWritable();
          await writable.write(await assetBlob(asset));
          await writable.close();
          return 'saved';
        }
        await triggerBrowserDownload(asset);
        return 'browser-download';
      };
      const saveAssetsToUserDirectory = async (assets) => {
        if (typeof window.showDirectoryPicker === 'function') {
          const directory = await window.showDirectoryPicker({ mode: 'readwrite' });
          const names = new Set();
          for (const asset of assets) {
            const base = assetFileName(asset); let name = base; let suffix = 1;
            while (names.has(name.toLowerCase())) name = base.replace(/(\.[^.]+)$/, `-${++suffix}$1`);
            names.add(name.toLowerCase());
            const handle = await directory.getFileHandle(name, { create: true });
            const writable = await handle.createWritable();
            await writable.write(await assetBlob(asset));
            await writable.close();
          }
          return 'directory';
        }
        for (const asset of assets) await triggerBrowserDownload(asset);
        return 'browser-download';
      };
      const resourceById = (id) => state.resources.find((entry) => entry.id === id && entry.tenantId === currentTenantId() && !entry.deletedAt);
      const visibleResources = () => state.resources.filter((entry) => entry.tenantId === currentTenantId() && !entry.deletedAt);
      const selectedResources = () => [...new Set(state.resourceView.selectedIds)].map(resourceById).filter(Boolean);
      const generateInternalSku = () => {
        let sku = '';
        do {
          sku = Array.from({ length: 16 }, () => Math.floor(Math.random() * 10)).join('');
        } while (state.resources.some((entry) => entry.sku === sku && !entry.deletedAt));
        return sku;
      };
      const allocateResourceSku = (preferred, asn = '', reserved = new Set(), selfId = null) => {
        const taken = (value) => reserved.has(value) || state.resources.some((entry) => entry.id !== selfId && !entry.deletedAt && entry.tenantId === currentTenantId() && entry.sku === value);
        let sku = String(preferred || '').trim();
        if (!sku) sku = generateInternalSku();
        if (!taken(sku)) { reserved.add(sku); return sku; }
        const withAsn = asn ? `${sku}-${String(asn).trim()}` : '';
        if (withAsn && !taken(withAsn)) { reserved.add(withAsn); return withAsn; }
        let next = generateInternalSku();
        while (taken(next)) next = generateInternalSku();
        reserved.add(next);
        return next;
      };
      const localDiskBaseName = (meta) => {
        const sku = String(meta.sku || '').trim() || generateInternalSku();
        const asn = String(meta.asn || '').trim();
        const base = asn ? `${sku}_${asn}` : sku;
        return base.replace(/[\\/:*?"<>|]+/g, '-');
      };
      const normalizeResourceMeta = (item = {}, index = 0, source = 'upload', reservedSkus = null) => {
        const url = String(item.url || item.resultUrl || item.originalUrl || '').trim() || (source === 'upload' ? `file://${String(item.name || item.fileName || 'image').trim()}` : `local://item-${index + 1}`);
        let name = String(item.name || item.fileName || '').trim();
        if (!name) {
          try {
            const pathName = decodeURIComponent(new URL(url).pathname.split('/').filter(Boolean).pop() || '');
            name = pathName ? pathName.replace(/\.[^.]+$/, '') : '';
          } catch (_) {}
          if (!name) name = source === 'import' ? 'url-item' : `image-${String(index + 1).padStart(2, '0')}`;
        }
        const asn = String(item.asn ?? '').trim();
        const reserved = reservedSkus || new Set();
        const sku = allocateResourceSku(item.sku, asn, reserved, item.id || null);
        const meta = { name, sku, url };
        resourceFileNameFields.filter((key) => !resourceFileNameRequired.includes(key)).forEach((key) => {
          const value = String(item[key] ?? '').trim();
          if (value) meta[key] = value;
        });
        meta.localName = item.localName || `${localDiskBaseName(meta)}.jpg`;
        return meta;
      };
      const formatResourceFileName = (resource) => {
        const meta = resourceFileNameFields.reduce((acc, key) => {
          const value = resource?.[key];
          if (value != null && String(value).trim() !== '') acc[key] = String(value).trim();
          return acc;
        }, {});
        if (!meta.name || !meta.sku || !meta.url) {
          const normalized = normalizeResourceMeta(resource, 0, resource?.source || 'upload');
          return resourceFileNameFields.map((key) => normalized[key]).filter((value) => value != null && String(value).trim() !== '').join('_');
        }
        return resourceFileNameFields.map((key) => meta[key]).filter(Boolean).join('_');
      };
      const addResources = (items, source, generationId = null, tenantId = currentTenantId()) => {
        const reservedSkus = new Set();
        const resources = items.map((item, index) => {
          const meta = normalizeResourceMeta(item, index, source, reservedSkus);
          return {
            id: uniqueId('RES'), tenantId, source, ...meta, createdAt: demoNow,
            size: item.size || 2.8 * 1024 * 1024, type: item.type || 'image/jpeg',
            previewUrl: item.previewUrl || makePreviewDataUrl(meta.localName || meta.name, ['teal', 'coral', 'purple'][index % 3]),
            originalUrl: meta.url, generationId, generationResultId: item.id || null, deletedAt: null
          };
        });
        state.resources.unshift(...resources);
        return resources;
      };
      const parseImportPayload = (rawText, jsonItems) => {
        if (Array.isArray(jsonItems) && jsonItems.length) {
          return jsonItems.map((entry, index) => {
            if (typeof entry === 'string') return { url: entry.trim(), name: '', sku: '' };
            const row = entry && typeof entry === 'object' ? entry : {};
            return {
              name: String(row.name || row.fileName || '').trim(),
              seller: String(row.seller || '').trim(),
              sku: String(row.sku || '').trim(),
              asn: String(row.asn || '').trim(),
              price: String(row.price ?? '').trim(),
              website: String(row.website || '').trim(),
              url: String(row.url || row.link || '').trim()
            };
          }).filter((entry) => entry.url);
        }
        const text = String(rawText || '').trim();
        if (!text) return [];
        if (/^[\[{]/.test(text)) {
          try {
            const parsed = JSON.parse(text);
            const list = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.items) ? parsed.items : [parsed];
            return parseImportPayload('', list);
          } catch (_) {
            throw new Error('JSON 格式无效，请检查字段后重试');
          }
        }
        return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((url) => {
          let name = '';
          let website = '';
          try {
            const parsed = new URL(url);
            website = parsed.hostname;
            const pathName = decodeURIComponent(parsed.pathname.split('/').filter(Boolean).pop() || '');
            if (pathName) name = pathName.replace(/\.[^.]+$/, '') || pathName;
          } catch (_) {}
          return { name, sku: '', url, website };
        });
      };
      const resourceIsRunning = (resource) => state.jobs.some((job) => !job.done && job.tenantId === resource.tenantId && job.payload.resourceIds?.includes(resource.id)) || state.history.some((item) => item.tenantId === resource.tenantId && item.resourceIds?.includes(resource.id) && ['SUBMITTED','PRE_REVIEW','FULL_PROCESSING','DETECTION','AUTO_REPROCESS_PENDING'].includes(item.status));
      const resourceStatus = (resource) => {
        if (resourceIsRunning(resource)) return ['处理中', 'pill-blue'];
        const latest = state.history.find((item) => item.taskType === 'processing' && item.tenantId === resource.tenantId && item.resourceIds?.includes(resource.id));
        if (!latest) return ['未处理', 'pill-gray'];
        const result = latest.results?.find((entry) => entry.inputResourceId === resource.id);
        const status = result?.status || latest.status;
        return ['DELIVERED','FILE_READY'].includes(status) ? ['已处理', 'pill-green'] : ['REVIEW_REQUIRED','DETECTION_UNKNOWN'].includes(status) ? ['待复核', 'pill-amber'] : ['处理失败', 'pill-red'];
      };
      const resourceRows = (view) => paginate(visibleResources().filter((entry) => view.source === 'all' || entry.source === view.source), view);
      const resourceSourceTabs = (view) => `<div class="filter-tabs resource-source-tabs">${resourceTabOrder.map((source) => `<button type="button" class="${view.source === source ? 'active' : ''}" data-action="resource-source" data-source="${source}">${source === 'all' ? '全部来源' : formatSource(source)}</button>`).join('')}</div>`;
      const renderResourceGrid = (items, ids, picker = false) => `<div class="table-wrap resource-table-wrap"><table class="resource-table"><thead><tr><th style="width:42px;"><span class="tiny muted">选</span></th><th style="width:64px;">缩略图</th><th>图片文件名</th><th style="width:88px;">操作</th></tr></thead><tbody>${items.map((resource) => {
        const fileName = formatResourceFileName(resource);
        return `<tr class="${ids.includes(resource.id) ? 'is-selected' : ''}" data-resource-id="${escapeHtml(resource.id)}"><td><input type="checkbox" data-resource-select="${picker ? 'picker' : 'main'}" value="${escapeHtml(resource.id)}" aria-label="选择 ${escapeHtml(fileName)}" ${ids.includes(resource.id) ? 'checked' : ''} /></td><td><img class="resource-table-thumb" loading="lazy" src="${escapeHtml(resource.previewUrl)}" alt="" /></td><td><div class="resource-table-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div><div class="tiny muted">${formatSource(resource.source)} · ${escapeHtml(resource.createdAt)}</div></td><td><button type="button" class="btn btn-ghost btn-sm" data-action="resource-preview" data-id="${escapeHtml(resource.id)}">查看</button></td></tr>`;
      }).join('')}</tbody></table></div>`;
      const renderResources = () => {
        const result = resourceRows(state.resourceView);
        const selected = selectedResources();
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>图片资源</h2></div><button class="btn btn-primary" data-action="resource-add" ${isAccountBlocked() ? 'disabled' : ''}>添加图片 <span>＋</span></button></div><section class="card card-pad">${resourceSourceTabs(state.resourceView)}<div class="resource-toolbar"><label><input type="checkbox" data-resource-page-select ${result.items.length && result.items.every((entry) => selected.some((item) => item.id === entry.id)) ? 'checked' : ''} ${result.items.length ? '' : 'disabled'} /> 选择本页</label><strong data-selected-count>已选 ${selected.length} 张</strong><button class="btn btn-ghost btn-sm" data-action="resource-clear" ${selected.length ? '' : 'disabled'}>清空选择</button><div class="resource-toolbar-actions"><button class="btn btn-ghost btn-sm" data-action="resource-download-batch" ${selected.length ? '' : 'disabled'}>批量下载</button><button class="btn btn-ghost btn-sm" data-action="resource-delete-batch" ${selected.length ? '' : 'disabled'}>批量删除</button><button class="btn btn-teal btn-sm" data-action="resource-process" ${selected.length && !isAccountBlocked() ? '' : 'disabled'}>去处理 <span>→</span></button></div></div>${result.items.length ? renderResourceGrid(result.items, selected.map((entry) => entry.id)) : '<div class="empty"><strong>暂无图片资源</strong></div>'}${renderPager({ ...result, prevAction: 'resource-page-prev', nextAction: 'resource-page-next' })}</section></div>`, '图片资源');
      };
      const captureResourceForm = () => {
        const form = document.querySelector('[data-form="batch"]');
        if (form && resourceDialog?.kind === 'add') { const data = new FormData(form); state.batchDraft = { ...(state.batchDraft || {}), ...Object.fromEntries(data) }; }
        const urls = document.querySelector('[data-form="resource-import"] textarea');
        if (urls && resourceDialog) resourceDialog.urls = urls.value;
      };
      const closeResourceDialog = () => {
        const previous = resourceDialog?.returnTo || null;
        resourceDialog = previous;
        render();
        document.querySelector('#modal-root .modal-close, [data-action="resource-add"]')?.focus();
      };
      const openResourcePicker = (purpose) => {
        captureResourceForm();
        const previous = purpose === 'reference' ? resourceDialog : null;
        resourceDialog = { kind: 'picker', purpose, returnTo: previous, view: { source: 'all', page: 1, pageSize: 20 }, selectedIds: purpose === 'reference' ? (state.batchDraft?.reference?.resourceId ? [state.batchDraft.reference.resourceId] : []) : [...state.processResourceIds] };
        render();
      };
      const requestResourceDelete = (ids) => {
        const resources = [...new Set(ids)].map(resourceById).filter(Boolean);
        if (!resources.length) { toast('请先选择可用图片', 'error'); return; }
        if (resources.some(resourceIsRunning)) { toast('所选图片仍有运行中的任务，暂不能删除，请调整选择', 'error'); return; }
        resourceDialog = { kind: 'delete', ids: resources.map((entry) => entry.id) }; render();
      };
      const deleteResources = (ids) => {
        const resources = ids.map(resourceById).filter(Boolean);
        if (resources.some(resourceIsRunning)) { toast('所选图片仍有运行中的任务，暂不能删除', 'error'); return false; }
        resources.forEach((entry) => { entry.deletedAt = demoNow; });
        state.resourceView.selectedIds = state.resourceView.selectedIds.filter((id) => !ids.includes(id));
        state.processResourceIds = state.processResourceIds.filter((id) => !ids.includes(id));
        return true;
      };
      const renderResourceDialog = () => {
        const dialog = resourceDialog;
        if (!dialog) return '';
        let title = '添加图片'; let body = ''; let wide = true;
        if (dialog.kind === 'preview') {
          const resource = resourceById(dialog.id);
          title = '图片预览'; body = resource ? `<div class="tiny muted" style="margin-bottom:12px;word-break:break-all;">${escapeHtml(formatResourceFileName(resource))}</div><img class="resource-large-preview" src="${escapeHtml(resource.previewUrl)}" alt="${escapeHtml(resource.name)}" />` : '<div class="empty"><strong>图片已删除</strong></div>';
        } else if (dialog.kind === 'delete') {
          title = '删除图片资源'; wide = false;
          body = `<p style="margin-top:18px;">确认删除所选 ${dialog.ids.length} 张原图？删除后无法预览和下载这些原图，历史记录和已产出的处理结果保留。</p><div class="form-footer"><button class="btn btn-ghost" data-action="resource-close">取消</button><button class="btn btn-primary" data-action="resource-confirm-delete">确认删除</button></div>`;
        } else if (dialog.kind === 'picker') {
          title = dialog.purpose === 'reference' ? '选择参考图' : '选择图片';
          const result = resourceRows(dialog.view);
          body = `${resourceSourceTabs(dialog.view)}<div class="resource-toolbar"><strong>已选 ${dialog.selectedIds.length} 张${dialog.purpose === 'reference' ? ' / 1' : ' / 10'}</strong><button class="btn btn-ghost btn-sm" data-action="resource-picker-clear">清空选择</button></div>${result.items.length ? renderResourceGrid(result.items, dialog.selectedIds, true) : '<div class="empty"><strong>暂无可选图片</strong></div>'}${renderPager({ ...result, prevAction: 'resource-page-prev', nextAction: 'resource-page-next' })}<div class="form-footer"><button class="btn btn-ghost" data-action="resource-close">取消</button><button class="btn btn-teal" data-action="resource-picker-confirm">确认选择</button></div>`;
        } else if (!dialog.mode) {
          const methodHints = { import: 'URL 行导入或 JSON（含元数据），最多 100 条', upload: '选择本地 JPG / PNG', text: '文生图生成后自动入库', image: '图生图生成后自动入库' };
          const methodIcons = { text: '✦', image: '▧', upload: '↥', import: '↗' };
          body = `<div class="resource-methods" style="display:flex;flex-direction:column;gap:12px;">${resourceSourceOrder.map((mode) => `<button type="button" class="resource-method" data-action="resource-method" data-mode="${mode}" style="width:100%;border:0;border-radius:16px;padding:18px 20px;display:flex;align-items:center;gap:16px;text-align:left;color:#12343a;background:linear-gradient(135deg,#f4fbf9 0%,#eef6ff 100%);box-shadow:inset 0 0 0 1px rgba(26,168,154,.22);cursor:pointer;"><span aria-hidden="true" style="width:42px;height:42px;border-radius:12px;display:grid;place-items:center;background:#17323c;color:#d9fff6;font-size:18px;flex:0 0 auto;">${methodIcons[mode]}</span><span style="display:block;min-width:0;"><strong style="display:block;font-size:15px;font-weight:800;">${formatSource(mode)}</strong><small style="display:block;margin-top:4px;color:#6f7a86;font-size:12px;font-weight:500;">${methodHints[mode]}</small></span></button>`).join('')}</div>`;
        } else {
          title = sourceLabels[dialog.mode];
          const back = '<button type="button" class="btn btn-ghost btn-sm" data-action="resource-method-back">← 更换添加方式</button>';
          if (['text','image'].includes(dialog.mode)) body = back + renderBatch();
          else if (dialog.mode === 'upload') body = `${back}<form data-form="resource-upload"><div class="upload-zone" style="margin-top:18px;"><label class="btn btn-ghost">选择本地图片<input id="resource-files" type="file" accept="image/jpeg,image/png" multiple hidden /></label><div class="tiny" style="margin-top:12px;">每次最多20张 · JPG / PNG · 单张不超过20 MiB</div></div><div class="file-list">${(dialog.files || []).map((file) => `<div class="file-row"><span class="resource-name">${escapeHtml(file.name)}</span><span class="tiny muted">${Math.round(file.size / 1024)} KiB</span></div>`).join('')}</div><div class="form-footer"><button class="btn btn-teal" type="submit">添加到图片资源</button></div></form>`;
          else body = `${back}<form data-form="resource-import"><div class="field" style="margin-top:18px;"><label for="resource-urls">URL / JSON</label><textarea id="resource-urls" name="urls" rows="8" placeholder="方式一：每行一个 HTTP/HTTPS 地址（最多100行）&#10;方式二：粘贴 JSON 数组，字段顺序 name → seller → sku → asn → price → website → url（必填 name/sku/url；sku 可空，系统会生成 16 位内部编号）">${escapeHtml(dialog.urls || '')}</textarea></div><div class="upload-zone" style="margin-top:12px;"><label class="btn btn-ghost">上传 JSON 文件<input id="resource-import-json" type="file" accept="application/json,.json" hidden /></label>${dialog.jsonName ? `<div class="tiny muted" style="margin-top:8px;">已载入：${escapeHtml(dialog.jsonName)} · ${dialog.jsonItems?.length || 0} 条</div>` : ''}</div><div class="form-footer"><button class="btn btn-teal" type="submit">添加到图片资源</button></div></form>`;
        }
        return `<div class="modal-backdrop"><div class="modal resource-modal ${wide ? 'modal-wide' : ''}" role="dialog" aria-modal="true" aria-labelledby="resource-modal-title" data-dialog-key="${escapeHtml([dialog.kind,dialog.mode,dialog.id].join('-'))}"><div class="modal-head"><h3 id="resource-modal-title">${title}</h3><button class="modal-close" data-action="resource-close" aria-label="关闭窗口">×</button></div><div style="margin-top:18px;">${body}</div></div></div>`;
      };
      const initializeResources = () => {
        const cleanPreview = (value) => typeof value === 'string' && value.startsWith('data:image/svg+xml') ? value.replace(encodeURIComponent('HONEY BADGER · MOCK PREVIEW'), 'HONEY%20BADGER') : value;
        state.resources.forEach((entry) => { entry.previewUrl = cleanPreview(entry.previewUrl); });
        state.history.forEach((item) => (item.results || []).forEach((result) => { result.previewUrl = cleanPreview(result.previewUrl); }));
        state.history.forEach((item) => { item.tenantId ||= 'DEMO-01'; item.taskType ||= ['GENERATED','GENERATING'].includes(item.status) ? 'generation' : 'processing'; });
        if (!state.resourceVersion) {
          state.history.forEach((item) => {
            const results = historyResults(item);
            const resources = addResources(results, item.source, item.taskType === 'generation' ? item.id : null, item.tenantId);
            if (item.taskType === 'generation') {
              item.results = results.map((result, index) => ({ ...result, resourceId: resources[index].id }));
              if (['DELETED','EXPIRED'].includes(item.status)) resources.forEach((entry) => { entry.deletedAt = demoNow; });
            } else {
              item.resourceIds = resources.map((entry) => entry.id);
              item.results = results.map((result, index) => ({ ...result, inputResourceId: resources[index].id, source: item.source }));
            }
          });
          state.resourceVersion = 1;
          state.historyFilter = { source: 'all', status: 'all', query: '' }; state.historyView = { page: 1, pageSize: 10 };
        }
        state.historyTabs ||= {};
        state.historyTab = ['generation','processing'].includes(state.historyTab) ? state.historyTab : 'processing';
        state.resources.forEach((entry, index) => {
          const meta = normalizeResourceMeta(entry, index, entry.source || 'upload');
          Object.assign(entry, meta);
          entry.originalUrl ||= meta.url;
        });
        state.resourceView.selectedIds ||= [];
        state.processResourceIds ||= [];
        state.processing = state.processing?.id ? state.jobs.find((job) => job.id === state.processing.id) || null : null;
        state.page = ['batch','upload','import'].includes(state.page) ? 'resources' : state.page;
      };
      const handleResourceAction = (el) => {
        const action = el.dataset.action;
        if (action === 'resource-add') {
          if (isAccountBlocked()) { toast('账号已冻结，暂不能添加图片', 'error'); return true; }
          state.batchDraft = null; state.promptOptimization = { active: false, original: '', optimized: '', confirmed: false, status: 'idle', charged: 0 };
          resourceDialog = { kind: 'add', mode: null, files: [] }; render();
        } else if (action === 'resource-close') closeResourceDialog();
        else if (action === 'resource-method' || action === 'resource-method-back') {
          captureResourceForm(); state.batchMode = el.dataset.mode || 'text';
          resourceDialog = { kind: 'add', mode: el.dataset.mode || null, files: [] };
          state.batchDraft = null; state.promptOptimization = { active: false, original: '', optimized: '', confirmed: false, status: 'idle', charged: 0 }; render();
        } else if (action === 'resource-source' || action === 'resource-page-prev' || action === 'resource-page-next') {
          const view = resourceDialog?.kind === 'picker' ? resourceDialog.view : state.resourceView;
          if (action === 'resource-source') { view.source = el.dataset.source; view.page = 1; }
          else view.page = Math.max(1, view.page + (action.endsWith('next') ? 1 : -1));
          persist(); render();
        } else if (action === 'resource-preview') {
          if (!resourceById(el.dataset.id)) return true;
          resourceDialog = { kind: 'preview', id: el.dataset.id, returnTo: resourceDialog }; render();
        } else if (action === 'resource-clear') { state.resourceView.selectedIds = []; persist(); render(); }
        else if (action === 'resource-process') {
          const resources = selectedResources();
          if (!resources.length || resources.length > 10) { toast('每次处理请选择1—10张图片，当前已选' + resources.length + '张', 'error'); return true; }
          state.processResourceIds = resources.map((entry) => entry.id); state.inputDraft = null; state.directPresetPreviewOpen = false; navigate('direct');
        } else if (action === 'resource-picker') openResourcePicker('process');
        else if (action === 'resource-reference') openResourcePicker('reference');
        else if (action === 'resource-picker-clear') { resourceDialog.selectedIds = []; render(); }
        else if (action === 'resource-picker-confirm') {
          const selected = resourceDialog.selectedIds.map(resourceById).filter(Boolean);
          const reference = resourceDialog.purpose === 'reference';
          if (!selected.length || selected.length > (reference ? 1 : 10)) { toast(reference ? '请选择1张参考图' : '请选择1—10张图片', 'error'); return true; }
          if (reference) state.batchDraft = { ...(state.batchDraft || {}), reference: { name: selected[0].name, resourceId: selected[0].id } };
          else state.processResourceIds = selected.map((entry) => entry.id);
          closeResourceDialog(); persist();
        } else if (action === 'resource-remove-process') { state.processResourceIds = state.processResourceIds.filter((id) => id !== el.dataset.id); persist(); render(); }
        else if (action === 'resource-download' || action === 'resource-download-batch') {
          const resources = action.endsWith('batch') ? selectedResources() : [resourceById(el.dataset.id)].filter(Boolean);
          if (!resources.length) { toast('请先选择可用图片', 'error'); return true; }
          (action.endsWith('batch') ? saveAssetsToUserDirectory(resources) : saveAssetToUserPath(resources[0])).then(() => toast(`已下载${resources.length}张图片`)).catch((error) => { if (error.name !== 'AbortError') toast('下载失败，请重试', 'error'); });
        } else if (action === 'resource-delete' || action === 'resource-delete-batch') requestResourceDelete(action.endsWith('batch') ? selectedResources().map((entry) => entry.id) : [el.dataset.id]);
        else if (action === 'resource-confirm-delete') {
          if (resourceDialog?.kind !== 'delete' || !deleteResources(resourceDialog.ids)) return true;
          resourceDialog = null; persist(); render(); toast('原图已删除，历史记录与处理结果保留');
        } else if (action === 'history-task-tab') {
          state.historyTabs[state.historyTab] = { filter: { ...state.historyFilter }, view: { ...state.historyView } };
          state.historyTab = el.dataset.tab;
          const previous = state.historyTabs[state.historyTab];
          state.historyFilter = previous?.filter || { source: 'all', status: 'all', query: '' };
          state.historyView = { ...(previous?.view || { page: 1 }), pageSize: 10 }; persist(); render();
        } else if (action === 'open-job') {
          const job = state.jobs.find((entry) => entry.id === el.dataset.id);
          if (job) { state.processing = job; render(); }
        } else return false;
        return true;
      };
      const renderNavItem = (page, icon, label) => `<button class="nav-item ${state.page === page ? 'active' : ''}" data-page="${page}"><span class="nav-icon">${icon}</span><span>${label}</span></button>`;
      const renderShell = (content, title) => {
        const unread = visibleMessages().filter((message) => !message.read).length;
         const supportNav = (state.role === 'support' || state.role === 'admin') ? renderNavItem('support', '⚙', '工单管理') : '';
         const deviceNav = state.role === 'admin' ? renderNavItem('devices', '▣', '设备预设') : '';
         const promptNav = renderNavItem('prompts', '✎', 'AI 提示词模板');
         const creditsNav = state.role === 'merchant' ? renderNavItem('credits', '◇', '积分与充值') : '';
         const userAdminNav = canManageUsers() ? renderNavItem('users', '♙', '用户管理') + renderNavItem('logs', '≡', '系统日志') : '';
         return `<div class="app-shell"><aside class="sidebar"><div class="brand"><div class="brand-mark">HB</div><div><h1>蜜獾原图</h1><small>image lab · v2</small></div></div><div class="nav-group"><div class="nav-label">workspace</div><div class="nav-list">${renderNavItem('dashboard','⌂','工作台')}${renderNavItem('resources','▧','图片资源')}${renderNavItem('direct','↥','批量原图')}${renderNavItem('history','◫','任务详情')}${deviceNav}${promptNav}${creditsNav}${supportNav}${userAdminNav}${renderNavItem('settings','◒','系统管理')}</div></div></aside><main class="main"><header class="topbar"><div class="crumb"><span>蜜獾原图 v2</span><span>/</span><strong>${escapeHtml(title)}</strong></div><div class="top-actions"><button class="icon-btn message-trigger" data-page="messages" aria-label="消息中心" title="消息中心"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg>${unread ? `<span class="message-badge">${unread > 9 ? '9+' : unread}</span>` : ''}</button><button class="role-switch" data-action="switch-role" title="切换角色"><span class="role-avatar">${role().avatar}</span><span>${role().label}</span><span class="tiny muted">⌄</span></button><button class="btn btn-ghost btn-sm" data-action="logout">退出</button></div></header>${content}</main></div>`;
      };
      const metric = (label, value, meta) => `<article class="card metric"><div class="metric-label"><i class="metric-accent"></i>${label}</div><div class="metric-value">${value}</div><div class="metric-meta">${meta}</div></article>`;
      const renderAdminOperationsSummary = () => {
        if (state.role !== 'admin') return '';
        const metrics = [
          ['可用余额', '286', '平台账户'], ['冻结积分', '20', '待终态结算'], ['队列任务', '3', '当前待处理'],
          ['失败率', '7.1%', '最近 30 天'], ['检测通过率', '84.6%', '检测报告'], ['模型调用量', '1,284', '本月'],
          ['模型成本', '待询价', '待配置'], ['存储占用', '18.4 GiB', '当前存储']
        ];
        return `<section class="card card-pad admin-operations-summary" style="margin-top:18px;"><div class="section-head"><h3>运营指标</h3><span class="pill pill-blue">平台管理</span></div><div class="grid grid-4">${metrics.map(([label,value,meta]) => metric(label,value,meta)).join('')}</div></section>`;
      };
      const renderDashboard = () => {
        const accountHistory = visibleHistory();
        const active = accountHistory.filter((x) => ['AUTO_REPROCESS_PENDING','FULL_PROCESSING','DETECTION','PRE_REVIEW'].includes(x.status)).length;
        const unread = visibleMessages().filter((x) => !x.read).length;
        const recent = accountHistory.slice(0, 4);
        const overview = state.role === 'admin' ? '' : `<div class="grid grid-4">${metric('可用积分', state.credits.available, `冻结 ${state.credits.frozen} · 永久有效`)}${metric('进行中任务', active, active ? '任务执行中' : '当前没有排队任务')}${metric('本月已完成', '42 条', '成功结果 39 · 免费失败 3')}${metric('未读消息', unread, unread ? '有任务需要你查看' : '全部已读')}</div>`;
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>今天，把结果<br>交给证据。</h2></div></div>${overview}${renderAdminOperationsSummary()}<div class="dashboard-grid"><section class="card card-pad"><div class="section-head"><h3>最近任务详情</h3><button class="btn btn-ghost btn-sm" data-page="history">全部任务</button></div>${recent.map((item) => `<div class="history-row"><div class="thumb ${item.preview.replace('art-','')}"></div><div><div class="row-title">${escapeHtml(item.title)}</div><div class="row-meta">${formatSource(item.source)} · ${item.createdAt} · ${escapeHtml(item.stage)}</div></div><div style="text-align:right;">${statusPill(item.status)}<div class="tiny muted" style="margin-top:5px;">${item.score == null ? '等待结果' : `总分 ${item.score}`}</div></div></div>`).join('')}</section><section class="card card-pad"><div class="section-head"><h3>需要你留意</h3><span class="tiny muted">${unread} 条未读</span></div>${visibleMessages().slice(0, 3).map((m) => `<div class="notice ${m.type === 'warn' ? 'warn' : m.type === 'danger' ? 'danger' : ''}"><div class="notice-icon">${m.type === 'danger' ? '!' : m.type === 'warn' ? '◌' : '✓'}</div><div><strong style="font-size:12px;">${escapeHtml(m.title)}</strong><div class="tiny muted" style="margin-top:3px;">${escapeHtml(m.body)}</div><div class="tiny muted" style="margin-top:5px;">${m.time}</div></div></div>`).join('')}<button class="btn btn-ghost btn-sm" style="margin-top:15px;" data-page="messages">打开消息中心</button></section></div></div>`, '工作台');
      };
      const renderDirectInput = () => {
        const resources = state.processResourceIds.map(resourceById).filter(Boolean);
        const canStart = resources.length && !isAccountBlocked() && !!directSelectedPreset();
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>批量原图</h2></div></div><section class="card form-card"><form data-form="process-resources"><div class="process-settings-bar"><div class="process-settings-main">${renderDirectExifPreset()}<div class="field" style="margin-top:14px;"><label for="process-validation">输入校验</label><select id="process-validation" name="validationCase">${mockValidationOptions(state.uploadValidationCase || 'pass')}</select></div></div><button class="btn btn-teal process-start" type="submit" ${canStart ? '' : 'disabled'}>开始处理 <span>→</span></button></div><div class="section-head" style="margin-top:18px;"><h3>待处理图片</h3><span class="pill pill-blue">${resources.length} / 10 张</span></div>${resources.length ? `<div class="process-resource-list">${resources.map((entry) => `<div class="process-resource-row"><img src="${escapeHtml(entry.previewUrl)}" alt="" /><div><strong title="${escapeHtml(formatResourceFileName(entry))}">${escapeHtml(formatResourceFileName(entry))}</strong><div class="tiny muted">${formatSource(entry.source)}</div></div><button class="btn btn-ghost btn-sm" data-action="resource-remove-process" data-id="${escapeHtml(entry.id)}">移除</button></div>`).join('')}</div>` : '<div class="empty"><strong>请选择图片资源</strong><button type="button" class="btn btn-ghost" data-action="resource-picker">选择图片</button></div>'}</form></section></div>`, '批量原图');
      };
      const visiblePromptTemplates = () => {
        const tenantId = currentTenantId();
        const userId = role().userId;
        return (state.promptTemplates || []).filter((item) => item.scope === 'platform' || item.tenantId === tenantId || item.ownerId === userId || state.role === 'admin');
      };
      const canEditPromptTemplate = (item) => {
        if (!item) return state.role === 'merchant' || state.role === 'admin';
        if (state.role === 'admin') return true;
        return item.scope !== 'platform' && (item.ownerId === role().userId || item.tenantId === currentTenantId());
      };
      const renderPromptTemplates = () => {
        const result = paginate(visiblePromptTemplates(), state.promptTemplateView || { page: 1, pageSize: 10 });
        const rows = result.items.map((item) => {
          const editable = canEditPromptTemplate(item);
          return `<tr><td><strong>${escapeHtml(item.name)}</strong><div class="tiny muted">${escapeHtml(item.id)} · ${item.mode === 'image' ? '图生图' : item.mode === 'text' ? '文生图' : '通用'}</div></td><td><span class="pill ${item.scope === 'platform' ? 'pill-blue' : 'pill-green'}">${item.scope === 'platform' ? '平台模板' : '我的模板'}</span></td><td class="tiny" style="max-width:360px;white-space:normal;">${escapeHtml(item.prompt)}</td><td class="tiny muted">${escapeHtml(item.updatedAt || '—')}</td><td><div style="display:flex;gap:6px;flex-wrap:wrap;"><button type="button" class="btn btn-ghost btn-sm" data-action="use-prompt-template" data-id="${escapeHtml(item.id)}">选用</button>${editable ? `<button type="button" class="btn btn-ghost btn-sm" data-action="edit-prompt-template" data-id="${escapeHtml(item.id)}">编辑</button><button type="button" class="btn btn-ghost btn-sm" data-action="delete-prompt-template" data-id="${escapeHtml(item.id)}">删除</button>` : '<span class="tiny muted">只读</span>'}</div></td></tr>`;
        }).join('');
        const editor = state.promptTemplateEditor;
        let editorModal = '';
        if (editor) {
          const current = editor.id === 'new' ? null : state.promptTemplates.find((item) => item.id === editor.id);
          const values = current || { name: '', mode: 'text', prompt: '', negative: '文字、水印、畸变、过度锐化', scope: state.role === 'admin' ? 'platform' : 'tenant' };
          editorModal = `<div class="modal-backdrop" data-modal-backdrop="prompt-template-editor"><div class="modal" role="dialog" aria-modal="true"><div class="modal-head"><div><h3>${current ? '编辑提示词模板' : '新建提示词模板'}</h3></div><button class="modal-close" type="button" data-action="close-prompt-template-editor" aria-label="关闭">×</button></div><form data-form="prompt-template" data-edit-id="${escapeHtml(editor.id)}" style="margin-top:16px;"><div class="form-grid"><div class="field"><label>模板名称</label><input name="name" required maxlength="64" value="${escapeHtml(values.name || '')}" /></div><div class="field"><label>适用模式</label><select name="mode"><option value="text" ${values.mode === 'text' ? 'selected' : ''}>文生图</option><option value="image" ${values.mode === 'image' ? 'selected' : ''}>图生图</option><option value="all" ${values.mode === 'all' ? 'selected' : ''}>通用</option></select></div>${state.role === 'admin' ? `<div class="field"><label>范围</label><select name="scope"><option value="platform" ${values.scope === 'platform' ? 'selected' : ''}>平台模板</option><option value="tenant" ${values.scope === 'tenant' ? 'selected' : ''}>租户模板</option></select></div>` : '<input type="hidden" name="scope" value="tenant" />'}<div class="field full"><label>正向提示词</label><textarea name="prompt" rows="5" required>${escapeHtml(values.prompt || '')}</textarea></div><div class="field full"><label>负向提示词</label><input name="negative" value="${escapeHtml(values.negative || '')}" /></div></div><div class="form-footer"><button type="button" class="btn btn-ghost" data-action="close-prompt-template-editor">取消</button><button class="btn btn-primary" type="submit">保存模板</button></div></form></div></div>`;
        }
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>AI 提示词模板</h2></div><button class="btn btn-primary" data-action="create-prompt-template">新建模板</button></div><section class="card card-pad"><div class="section-head"><h3>模板列表</h3><span class="pill pill-blue">${result.total} 条</span></div><div class="table-wrap"><table><thead><tr><th>模板</th><th>范围</th><th>正向提示词</th><th>更新时间</th><th>操作</th></tr></thead><tbody>${rows || '<tr><td colspan="5">暂无模板</td></tr>'}</tbody></table></div>${renderPager({ ...result, prevAction: 'prompt-templates-page-prev', nextAction: 'prompt-templates-page-next' })}</section>${editorModal}</div>`, 'AI 提示词模板');
      };
      const renderBatch = () => {
        const isText = state.batchMode === 'text';
        const draft = state.batchDraft || {};
        const prompt = draft.prompt ?? (isText ? '自然光下的米白色陶瓷餐具，浅木桌面，柔和阴影，电商主图留白' : '保留参考图主体比例，提升材质细节与自然光质感，干净背景');
        const p = state.promptOptimization;
        const reference = draft.reference;
        const selectableTemplates = visiblePromptTemplates().filter((item) => item.mode === 'all' || item.mode === (isText ? 'text' : 'image') || !item.mode);
        const templateOptions = `<option value="">不使用模板</option>${selectableTemplates.map((item) => `<option value="${escapeHtml(item.id)}" ${draft.templateId === item.id ? 'selected' : ''}>${escapeHtml(item.name)}${item.scope === 'platform' ? ' · 平台' : ' · 我的'}</option>`).join('')}`;
        const negative = draft.templateId ? (draft.negative ?? '') : (draft.negative ?? '文字、水印、畸变、过度锐化');
        return `<form data-form="batch"><div class="form-grid"><div class="field full"><label for="batch-prompt-template">AI 提示词模板</label><select id="batch-prompt-template" name="templateId">${templateOptions}</select></div>${!isText ? `<div class="field full"><label>参考图</label><div class="reference-picker">${reference ? `<strong>${escapeHtml(reference.name)}</strong>` : '<span>尚未选择参考图</span>'}<div class="resource-toolbar-actions"><button type="button" class="btn btn-ghost btn-sm" data-action="resource-reference">从图片资源选择</button><label class="btn btn-ghost btn-sm">上传本地参考图<input id="reference-file" type="file" accept="image/jpeg,image/png" hidden /></label></div></div></div>` : ''}<div class="field full"><label for="generation-prompt">正向提示词</label><textarea id="generation-prompt" name="prompt" data-prompt-source required>${escapeHtml(prompt)}</textarea></div><div class="field"><label>负向提示词</label><input name="negative" value="${escapeHtml(negative)}" /></div><div class="field"><label>生成数量</label><input name="quantity" type="number" min="1" max="10" required value="${escapeHtml(draft.quantity || (isText ? 4 : 2))}" /></div><div class="field"><label>输出尺寸</label><select name="size">${['1024 × 1024','1536 × 1024','1024 × 1536','2048 × 2048'].map((size) => `<option ${draft.size === size ? 'selected' : ''}>${size}</option>`).join('')}</select></div><div class="field"><label>随机种子</label><input name="seed" value="${escapeHtml(draft.seed ?? '20261025')}" /></div></div><div class="card card-pad" style="margin-top:18px;background:#f7fbfa;box-shadow:none;"><div class="section-head"><h3>提示词优化</h3><span class="pill ${p.active ? (p.confirmed ? 'pill-green' : 'pill-amber') : 'pill-gray'}">${p.active ? (p.confirmed ? '已确认' : '待确认') : '未调用'}</span></div>${p.active ? `<div class="grid grid-2"><div><strong class="tiny">原始版本</strong><p class="tiny" style="white-space:pre-wrap;">${escapeHtml(p.original)}</p></div><div><strong class="tiny">优化版本</strong><p class="tiny" style="white-space:pre-wrap;">${escapeHtml(p.optimized)}</p></div></div>` : ''}<div class="form-footer"><button type="button" class="btn btn-ghost btn-sm" data-action="optimize-prompt" ${isAccountBlocked() ? 'disabled' : ''}>调用提示词优化 · 成功1积分</button>${p.active ? '<button type="button" class="btn btn-teal btn-sm" data-action="confirm-prompt">确认采用优化版本</button>' : ''}</div></div><div class="form-footer"><button class="btn btn-primary" type="submit" ${isAccountBlocked() ? 'disabled' : ''}>提交${isText ? '文生图' : '图生图'}任务 <span>→</span></button></div></form>`;
      };
      const historyFiltered = () => {
        const f = state.historyFilter;
        return visibleHistory().filter((item) => {
          const sourceOk = f.source === 'all' || item.source === f.source || (item.source === 'mixed' && item.results?.some((entry) => entry.source === f.source));
          const query = String(f.query || '').trim().toLowerCase();
          return item.taskType === state.historyTab && sourceOk && (f.status === 'all' || item.status === f.status) && (!query || `${item.id} ${item.title} ${formatSource(item.source)}`.toLowerCase().includes(query));
        });
      };
      const renderHistory = () => {
        const f = state.historyFilter;
        const result = paginate(historyFiltered(), state.historyView);
        const generation = state.historyTab === 'generation';
        const sources = (generation ? ['all', 'text', 'image'] : processingSourceTabOrder).map((value) => [value, value === 'all' ? '全部来源' : formatSource(value)]);
        const statuses = generation ? ['GENERATING','GENERATED','TECH_FAILED','EXPIRED','DELETED'] : ['FILE_READY','REVIEW_REQUIRED','DETECTION_UNKNOWN','QUALITY_FAILED','LEGACY_REVIEW','PRE_REVIEW','FULL_PROCESSING','DETECTION','DELIVERED','AUTO_REPROCESS_PENDING','FAILED','TECH_FAILED','PRE_REVIEW_FAILED','IMAGE_LOCKED','REJECTED','EXPIRED','DELETED'];
        const rows = result.items.map((item) => {
          const thumb = historyResults(item).find((entry) => entry.previewUrl)?.previewUrl || makePreviewDataUrl(item.title, item.preview === 'art-coral' ? 'coral' : item.preview === 'art-purple' ? 'purple' : 'teal');
          return `<tr><td><img class="resource-table-thumb history-table-thumb" loading="lazy" src="${escapeHtml(thumb)}" alt="" /></td><td><strong>${escapeHtml(item.title)}</strong><div class="mono muted">${escapeHtml(item.id)}</div></td><td>${formatSource(item.source)}</td><td class="tiny muted">${escapeHtml(item.createdAt)}</td><td>${statusPill(item.status)}</td>${generation ? '' : `<td>${item.rounds?.length || 0}</td><td>${scoreText(item.score)}</td>`}<td class="tiny">${escapeHtml(item.billing || '—')}</td><td><button type="button" class="btn btn-ghost btn-sm" data-action="view-history" data-id="${escapeHtml(item.id)}">查看</button></td></tr>`;
        }).join('');
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>任务详情</h2></div><button class="btn btn-primary" data-page="${generation ? 'resources' : 'direct'}">${generation ? '图片资源' : '新建批量原图'} <span>→</span></button></div><section class="card card-pad"><div class="segmented history-task-tabs" role="tablist" aria-label="任务类型">${[['processing','图片处理任务'],['generation','生图任务']].map(([tab,label]) => `<button role="tab" aria-selected="${state.historyTab === tab}" class="${state.historyTab === tab ? 'active' : ''}" data-action="history-task-tab" data-tab="${tab}">${label}</button>`).join('')}</div><div class="filter-bar"><div class="filter-tabs">${sources.map(([value,label]) => `<button class="${f.source === value ? 'active' : ''}" data-history-source="${value}">${label}</button>`).join('')}</div><select id="history-status" aria-label="任务状态"><option value="all">全部状态</option>${statuses.map((status) => `<option value="${status}" ${f.status === status ? 'selected' : ''}>${statusLabels[status]}</option>`).join('')}</select><input id="history-query" placeholder="搜索任务编号 / 标题" value="${escapeHtml(f.query)}" /></div>${result.items.length ? `<div class="table-wrap"><table><thead><tr><th style="width:64px;">缩略图</th><th>任务</th><th>来源</th><th>提交时间</th><th>状态</th>${generation ? '' : '<th>轮次</th><th>检测结果</th>'}<th>计费</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty"><strong>暂无符合条件的任务</strong></div>'}${renderPager({ ...result, prevAction: 'history-page-prev', nextAction: 'history-page-next' })}</section></div>`, '任务详情');
      };
      const renderMessagesV2 = () => {
        const unread = visibleMessages().filter((item) => !item.read).length;
        const rows = visibleMessages().map((message) => '<div class="message-row ' + (message.read ? 'read' : 'unread') + '"><span class="message-dot ' + (message.type || 'success') + '">' + (message.type === 'danger' ? '!' : message.type === 'warn' ? '◌' : '✓') + '</span><div class="message-main"><strong>' + escapeHtml(message.title) + '</strong><span class="message-body">' + escapeHtml(message.body) + '</span></div><span class="message-time">' + escapeHtml(message.time) + '</span><span class="message-state">' + (message.read ? '已读' : '未读') + '</span>' + (message.type === 'danger' ? '<button class="btn btn-ghost btn-sm" data-action="retry-message" data-id="' + escapeHtml(message.id) + '">补发</button>' : '') + '</div>').join('');
        return renderShell('<div class="page"><div class="page-intro"><div><h2>消息中心</h2></div><button class="btn btn-ghost" data-action="mark-messages-read">全部标为已读</button></div><section class="card card-pad"><div class="message-list">' + (rows || '<div class="empty"><strong>暂无消息</strong></div>') + '</div></section></div>', '消息中心');
      };
      const renderSupportV2 = () => {
        const canProcess = state.role === 'support' || state.role === 'admin';
        if (!canProcess) return renderShell('<div class="page"><div class="empty"><strong>当前账号无权访问工单管理</strong><span>请联系技术客服或平台管理员。</span></div></div>', '工单管理');
        const selected = state.tickets.find((ticket) => ticket.id === state.ticketViewId);
        const statusLabel = (status) => '<span class="pill ' + (status === '已完成' || status === '已解冻' ? 'pill-green' : status === '维持冻结' ? 'pill-red' : 'pill-amber') + '">' + escapeHtml(status) + '</span>';
         const supportView = state.supportView || (state.supportView = { ticketPage: 1, ticketPageSize: 5, auditPage: 1, auditPageSize: 10 });
         const ticketResult = paginate(state.tickets, { page: supportView.ticketPage, pageSize: supportView.ticketPageSize });
         supportView.ticketPage = ticketResult.page;
         const rows = ticketResult.items.map((ticket) => '<tr><td><button class="table-link" data-action="view-ticket" data-id="' + escapeHtml(ticket.id) + '">' + escapeHtml(ticket.id) + '</button><div class="tiny muted">' + escapeHtml(ticket.createdAt) + '</div></td><td>' + escapeHtml(ticket.kind) + '</td><td>' + escapeHtml(ticket.tenant) + '<div class="mono muted">' + escapeHtml(ticket.ref) + '</div></td><td>' + statusLabel(ticket.status) + '</td><td class="tiny muted">' + escapeHtml(ticket.note || '') + '</td><td><button class="btn btn-ghost btn-sm" data-action="view-ticket" data-id="' + escapeHtml(ticket.id) + '">查看</button></td></tr>').join('');
        let detail = '';
        if (selected) {
          const evidence = selected.freezeEvent || state.account.freezeEvent || { id: selected.ref, reason: selected.note || '人工工单', time: selected.createdAt, tenantId: selected.tenant };
          const canEdit = selected.status !== '已完成' && selected.status !== '已解冻' && selected.status !== '维持冻结';
          const ticketReason = String(evidence.reason || selected.note || '—').replace(/[；;,]?\s*幂等键[^；;。]*/g, '').replace(/，?幂等确认已锁定/g, '').replace(/幂等[^\s；;。]*/g, '').trim() || '—';
          detail = '<div class="modal-backdrop" data-modal-backdrop="ticket-detail"><div class="modal modal-wide" role="dialog" aria-modal="true" aria-labelledby="ticket-detail-title"><div class="modal-head"><div><h3 id="ticket-detail-title">工单详情 · ' + escapeHtml(selected.id) + '</h3><p class="tiny muted" style="margin-top:5px;">' + escapeHtml(selected.kind) + ' · ' + escapeHtml(selected.tenant) + ' · ' + escapeHtml(selected.ref) + '</p></div><div style="display:flex;align-items:center;gap:9px;">' + statusLabel(selected.status) + '<button class="modal-close" type="button" data-action="close-ticket-modal" aria-label="关闭工单详情">×</button></div></div><div class="grid grid-3" style="margin-top:18px;"><div><div class="tiny muted">触发时间</div><strong>' + escapeHtml(evidence.time || selected.createdAt) + '</strong></div><div><div class="tiny muted">冻结/关联原因</div><strong>' + escapeHtml(ticketReason) + '</strong></div><div><div class="tiny muted">关联账号范围</div><strong>' + escapeHtml(evidence.tenantId || selected.tenant) + '</strong></div></div><div class="notice warn" style="margin-top:14px;"><div class="notice-icon">!</div><div><strong style="font-size:12px;">证据摘要</strong><div class="tiny muted" style="margin-top:4px;">连续失败图片：3 张不同图片 · 同图锁定：' + (state.account.imageLocks && Object.keys(state.account.imageLocks).length ? '有' : '按工单记录') + ' · 冻结积分：' + state.credits.frozen + ' · 关联历史任务可在任务详情中查看。</div></div></div>' + (canEdit ? '<form data-form="ticket-review" style="margin-top:16px;"><input type="hidden" name="ticketId" value="' + escapeHtml(selected.id) + '" /><div class="form-grid"><div class="field"><label>处理决定</label><select name="decision">' + (selected.kind === '账号冻结' ? '<option value="unfreeze">解冻账号</option><option value="keep_frozen">维持冻结</option>' : selected.kind === '充值确认' ? '<option value="confirm">确认到账</option>' : '<option value="release">释放冻结积分</option><option value="retry">建议手动重试</option><option value="close">关闭工单</option>') + '</select></div><div class="field full"><label>人工复核意见</label><textarea name="note" rows="3" placeholder="填写证据判断、处理原因和后续建议"></textarea></div></div><div class="form-footer"><button class="btn btn-primary" type="submit">提交处理结果</button></div></form>' : '<div class="notice" style="margin-top:16px;"><div class="notice-icon">✓</div><div class="tiny muted">处理意见：' + escapeHtml(selected.reviewNote || '暂无') + ' · 操作者：' + escapeHtml(selected.reviewedBy || '—') + '</div></div>') + '</div></div>';
        }
         return renderShell('<div class="page"><div class="page-intro"><div><h2>工单管理</h2></div><span class="pill pill-green">' + role().label + ' · 可复核</span></div><div class="grid grid-3">' + metric('待处理工单', state.tickets.filter((ticket) => !['已完成', '已解冻', '维持冻结'].includes(ticket.status)).length, '含技术异常、冻结和充值') + metric('冻结工单', state.tickets.filter((ticket) => ticket.kind === '账号冻结' && !['已解冻', '维持冻结'].includes(ticket.status)).length, '需要人工复核') + metric('本周完成', '18', '当前') + '</div><section class="card card-pad" style="margin-top:18px;"><div class="section-head"><h3>工单列表</h3></div><div class="table-wrap"><table><thead><tr><th>工单</th><th>类型</th><th>租户 / 关联</th><th>状态</th><th>说明</th><th>操作</th></tr></thead><tbody>' + rows + '</tbody></table></div>' + renderPager({ ...ticketResult, prevAction: 'tickets-page-prev', nextAction: 'tickets-page-next' }) + '</section>' + detail + '</div>', '工单管理');
      };
      const renderPresetEditorV2 = () => {
        const view = state.system.devicePresetView || {};
        if (!view.editorId) return '';
        if (view.formTab === 'image') view.formTab = 'shooting';
        const preset = view.editorId === 'new' ? null : state.system.devicePresets.find((item) => String(item.id) === String(view.editorId));
        const values = presetFormDefaults(preset);
        const active = presetFormTabs.some(([key]) => key === view.formTab) ? (view.formTab || 'basic') : 'basic';
        view.formTab = active;
        const sections = presetFormTabs.map(([key]) => {
          const blocks = (presetFieldSections[key] || []).map((block) => {
            const progress = block.exifProgress ? renderPresetExifProgress(values) : '';
            const aspect = block.aspectRatio ? renderPresetAspectPicker() : '';
            return `<div style="margin-bottom:18px;">${renderPresetSubhead(block.title, block.tone)}${progress}${aspect}<div class="form-grid">${block.fields.map((field) => renderPresetField(field, values)).join('')}</div></div>`;
          }).join('');
          return `<div data-preset-form-section="${key}" style="${active === key ? '' : 'display:none;'}">${blocks}</div>`;
        }).join('');
        const source = preset?.sourceId ? '来源 ' + preset.sourceId + ' · ' + (preset.sourceVisibility || 'PRIVATE') + ' · ' + (preset.sourceActivationStatus || 'NOT_ACTIVATED') : '';
        return `<div class="modal-backdrop" data-modal-backdrop="preset-editor"><div class="modal modal-wide preset-editor-modal" role="dialog" aria-modal="true" aria-labelledby="preset-editor-title"><div class="modal-head"><div><h3 id="preset-editor-title">${preset ? '编辑设备预设' : '新建设备预设'}</h3>${source ? `<p class="tiny muted" style="margin-top:5px;">${escapeHtml(source)}</p>` : ''}</div><button class="modal-close" type="button" data-action="close-preset-editor" aria-label="关闭设备预设表单">×</button></div><div class="filter-tabs preset-form-tabs" style="margin-top:14px;flex:0 0 auto;">${presetFormTabs.map(([key, label]) => `<button class="${active === key ? 'active' : ''}" type="button" data-preset-form-tab="${key}">${label}</button>`).join('')}</div><form data-form="device-preset-full" data-edit-id="${escapeHtml(preset?.id || 'new')}" style="display:flex;flex-direction:column;flex:1 1 auto;min-height:0;"><div class="preset-form-scroll">${sections}</div><div class="form-footer" style="flex-wrap:wrap;justify-content:flex-end;"><div style="display:flex;gap:8px;flex-wrap:wrap;"><button class="btn btn-ghost" type="button" data-action="close-preset-editor">取消</button><button class="btn btn-primary" type="submit">${preset ? '保存修改' : '新增设备预设'}</button></div></div></form></div></div>`;
      };
      const renderDevicePresetsV2 = () => {
        const view = state.system.devicePresetView || {};
         if (state.role !== 'admin') return renderShell('<div class="page"><div class="empty"><strong>当前账号无权访问设备预设</strong><span>设备预设由平台管理员维护。</span></div></div>', '设备预设');
        const result = devicePresetRows();
        const categories = [...new Set(state.system.devicePresets.map((preset) => preset.category).filter(Boolean))].sort();
        const rows = result.items.map((preset, index) => '<tr><td class="mono tiny">' + ((result.page - 1) * result.pageSize + index + 1) + '</td><td><button class="table-link" data-action="view-preset" data-id="' + escapeHtml(preset.id) + '">' + escapeHtml(preset.name) + '</button><div class="tiny muted">' + escapeHtml(preset.sourceId ? '来源 ' + preset.sourceId : preset.id) + '</div></td><td>' + escapeHtml(preset.category) + '<div class="tiny muted">' + escapeHtml(preset.familyLabel || '') + '</div></td><td>' + escapeHtml(preset.camera) + '<div class="tiny muted">' + escapeHtml(preset.lens) + '</div></td><td>' + escapeHtml(preset.iso) + '<div class="tiny muted">' + escapeHtml(preset.shutter) + ' · ' + escapeHtml(preset.aperture) + '</div></td><td>GPS ' + escapeHtml(preset.gpsPolicy) + '</td><td><span class="pill ' + deviceStatusClass(preset.status) + '">' + escapeHtml(preset.status) + '</span><div class="tiny muted">' + escapeHtml(preset.visibility || '') + '</div></td><td><button class="btn btn-ghost btn-sm" data-action="edit-preset" data-id="' + escapeHtml(preset.id) + '">编辑</button><button class="btn btn-ghost btn-sm" data-action="toggle-preset" data-id="' + escapeHtml(preset.id) + '" style="margin-left:6px;">' + (preset.status === '启用' ? '停用' : '启用') + '</button></td></tr>').join('');
         const list = '<section class="card form-card"><div class="section-head"><div><h3>设备预设目录</h3></div><div style="display:flex;gap:8px;align-items:center;"><span class="pill pill-amber">' + devicePresetSource.status + '</span><button class="btn btn-primary btn-sm" data-action="new-preset">新建设备预设</button></div></div><div class="filter-bar"><input id="device-preset-query" placeholder="搜索名称、相机、镜头、来源 ID" value="' + escapeHtml(view.query || '') + '" /><select id="device-preset-category"><option value="all">全部设备类别</option>' + categories.map((category) => '<option value="' + escapeHtml(category) + '" ' + (view.category === category ? 'selected' : '') + '>' + escapeHtml(category) + '</option>').join('') + '</select><select id="device-preset-review"><option value="all">全部复核状态</option><option value="demo" ' + (view.review === 'demo' ? 'selected' : '') + '>公共预设</option><option value="STRUCTURAL_CANDIDATE" ' + (view.review === 'STRUCTURAL_CANDIDATE' ? 'selected' : '') + '>结构候选</option><option value="QUARANTINE_REVIEW" ' + (view.review === 'QUARANTINE_REVIEW' ? 'selected' : '') + '>待复核</option></select></div><div class="table-wrap"><table><thead><tr><th>#</th><th>预设 / 来源</th><th>类别</th><th>相机 / 镜头</th><th>ISO / 曝光</th><th>GPS</th><th>状态</th><th>操作</th></tr></thead><tbody>' + (rows || '<tr><td colspan="8"><div class="empty"><strong>没有符合条件的预设</strong></div></td></tr>') + '</tbody></table></div><div class="form-footer"><div class="tiny muted">' + result.page + ' / ' + result.pageCount + ' 页 · 每页 ' + result.pageSize + ' 条</div><div><button class="btn btn-ghost btn-sm" data-action="device-page-prev" ' + (result.page <= 1 ? 'disabled' : '') + '>上一页</button><button class="btn btn-ghost btn-sm" data-action="device-page-next" ' + (result.page >= result.pageCount ? 'disabled' : '') + '>下一页</button></div></div></section>';
        const detail = state.system.devicePresets.find((item) => String(item.id) === String(view.detailId));
        return renderShell('<div class="page"><div class="page-intro"><div><h2>设备预设</h2></div><span class="pill pill-blue">平台管理员</span></div>' + list + renderPresetEditorV2() + renderDevicePresetDetail(detail) + '</div>', '设备预设');
      };

      const userRolePermissions = {
        merchant: ['task.create', 'history.read', 'credits.read'],
        support: ['ticket.read', 'account.unfreeze', 'user.manage'],
        admin: ['system.manage', 'user.manage', 'preset.manage', 'account.unfreeze']
      };
      const userPermissionLabels = { 'task.create': '创建图片任务', 'history.read': '查看任务详情', 'credits.read': '查看积分流水', 'ticket.read': '处理工单', 'account.unfreeze': '账号解冻', 'system.manage': '系统配置', 'user.manage': '用户管理', 'preset.manage': '设备预设管理' };
      const accountCredits = (user) => user.id === 'USR-001' ? String(state.credits.available) : String(user.credits || '0');
      const userSnapshot = (user) => ({ id: user.id, username: user.username, displayName: user.displayName, tenantId: user.tenantId, role: displayRole(user.role), permissions: [...user.permissions], status: user.status, credits: accountCredits(user), passwordVersion: user.passwordVersion || 0 });
      const recordUserAction = (action, user, before, after, reason) => {
        const time = new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai', hour12: false });
        const entry = { id: `UL-${crypto.randomUUID()}`, module: '用户管理', time, actor: role().label, actorId: role().userId, targetId: user.id, username: user.username, tenantId: user.tenantId, action, before, after, reason: reason || '', result: '成功' };
        state.system.userLogs.unshift(entry);
        state.system.logView.page = 1;
      };
      const recordAuditEvent = (action, scope = role().scope || 'PLATFORM', result = '允许') => {
        state.system.audit.unshift({ time: demoNow, actor: role().label, scope, action, result });
        state.system.logView.page = 1;
      };
      const unifiedSystemLogs = () => {
        const userRows = (state.system.userLogs || []).map((entry) => ({
          id: entry.id,
          time: entry.time,
          actor: entry.actor,
          actorId: entry.actorId || '',
          module: entry.module || '用户管理',
          scope: entry.tenantId || '—',
          target: entry.username || entry.targetId || '—',
          action: entry.action,
          detail: `${describeUserChange(entry)}${entry.reason ? `；原因：${entry.reason}` : ''}`,
          result: entry.result || '成功'
        }));
        const auditRows = (state.system.audit || []).map((entry, index) => ({
          id: `AUD-${index}-${entry.time}`,
          time: entry.time,
          actor: entry.actor,
          actorId: '',
          module: '系统审计',
          scope: entry.scope || '—',
          target: entry.scope || '—',
          action: entry.action,
          detail: '',
          result: entry.result || '—'
        }));
        return [...userRows, ...auditRows].sort((a, b) => String(b.time).localeCompare(String(a.time), 'en'));
      };
      const renderAccessDenied = (title) => renderShell(`<div class="page"><div class="page-intro"><h2>${title}</h2></div><section class="card card-pad"><div class="notice danger"><strong>当前账号无权访问此页面</strong></div></section></div>`, title);
      const renderUsers = () => {
        if (!canManageUsers()) return renderAccessDenied('用户管理');
        const result = paginate(state.system.users, state.system.userView);
        const rows = result.items.map((user) => {
          const protectedAccount = user.id === 'USR-003';
          const button = (kind, label, disabled = false) => `<button class="btn btn-ghost btn-sm" data-action="open-user-dialog" data-kind="${kind}" data-id="${escapeHtml(user.id)}" data-tenant-id="${escapeHtml(user.tenantId)}" ${disabled ? 'disabled title="当前管理员账号受保护"' : ''}>${label}</button>`;
          return `<tr><td><strong>${escapeHtml(user.displayName)}</strong><div class="tiny muted">${escapeHtml(user.username)} · ${escapeHtml(user.id)}</div></td><td class="mono">${escapeHtml(user.tenantId)}</td><td>${escapeHtml(displayRole(user.role))}</td><td><span class="pill ${user.status === '启用' ? 'pill-green' : 'pill-red'}">${escapeHtml(user.status)}</span></td><td class="mono">${escapeHtml(accountCredits(user))}</td><td><div style="display:flex;gap:6px;flex-wrap:wrap;min-width:260px;">${button('credits', '积分')}${button('permissions', '权限管理', protectedAccount)}${button('status', user.status === '启用' ? '停用' : '启用', protectedAccount)}${button('password', '重置密码')}${button('delete', '删除', protectedAccount)}</div></td></tr>`;
        }).join('');
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>用户管理</h2></div><button class="btn btn-primary" data-action="open-user-dialog" data-kind="create">创建账号</button></div><section class="card card-pad"><div class="section-head"><h3>账号列表</h3></div><div class="table-wrap"><table><thead><tr><th>账号</th><th>租户</th><th>角色</th><th>状态</th><th>可用积分</th><th>操作</th></tr></thead><tbody>${rows || '<tr><td colspan="6">暂无账号</td></tr>'}</tbody></table></div>${renderPager({ ...result, prevAction: 'users-page-prev', nextAction: 'users-page-next' })}</section></div>`, '用户管理');
      };
      const describeUserChange = (entry) => {
        const labels = { role: '角色', permissions: '权限', status: '状态', credits: '可用积分' };
        if (entry.action === '创建账号') return `账号：${entry.username}；角色：${entry.after.role}；状态：${entry.after.status}`;
        if (entry.action === '删除账号') return `账号 ${entry.username} 已删除`;
        if (entry.action === '重置密码') return '密码已重置';
        return Object.entries(labels).filter(([key]) => JSON.stringify(entry.before?.[key]) !== JSON.stringify(entry.after?.[key])).map(([key, label]) => {
          const display = (value) => Array.isArray(value) ? value.map((permission) => userPermissionLabels[permission] || permission).join('、') || '无' : String(value ?? '—');
          return `${label}：${display(entry.before?.[key])} → ${display(entry.after?.[key])}`;
        }).join('；');
      };
      const renderUserLogs = () => {
        if (!canManageUsers()) return renderAccessDenied('系统日志');
        const result = paginate(unifiedSystemLogs(), state.system.logView);
        const rows = result.items.map((entry) => `<tr><td class="tiny">${escapeHtml(entry.time)}</td><td>${escapeHtml(entry.actor)}${entry.actorId ? `<div class="tiny muted">${escapeHtml(entry.actorId)}</div>` : ''}</td><td>${escapeHtml(entry.module)}</td><td class="mono">${escapeHtml(entry.scope)}</td><td>${escapeHtml(entry.target)}</td><td>${escapeHtml(entry.action)}</td><td style="min-width:220px;white-space:normal;">${escapeHtml(entry.detail || '—')}</td><td><span class="pill ${entry.result === '拒绝' || entry.result === '失败' ? 'pill-red' : 'pill-green'}">${escapeHtml(entry.result)}</span></td></tr>`).join('');
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>系统日志</h2></div><span class="pill pill-blue">${result.total} 条</span></div><section class="card card-pad"><div class="section-head"><h3>全部操作记录</h3></div><div class="table-wrap"><table><thead><tr><th>操作时间</th><th>操作人</th><th>模块</th><th>范围</th><th>对象</th><th>操作</th><th>变更 / 说明</th><th>结果</th></tr></thead><tbody>${rows || '<tr><td colspan="8">暂无系统日志</td></tr>'}</tbody></table></div>${renderPager({ ...result, prevAction: 'logs-page-prev', nextAction: 'logs-page-next' })}</section></div>`, '系统日志');
      };
      const renderUserDialog = () => {
        if (!userDialog || !canManageUsers()) return '';
        const { kind, id, tenantId } = userDialog;
        const user = state.system.users.find((item) => item.id === id && item.tenantId === tenantId);
        if (kind !== 'create' && !user) return '';
        const titles = { create: '创建账号', credits: '调整积分', permissions: '权限管理', status: user?.status === '启用' ? '停用账号' : '启用账号', password: '重置密码', delete: '删除账号' };
        const roles = Object.entries(roleMeta).map(([value, meta]) => `<option value="${value}" ${value === (user?.role || 'merchant') ? 'selected' : ''}>${meta.label}</option>`).join('');
        let fields = '';
        if (kind === 'create') fields = `<div class="form-grid"><div class="field"><label>登录账号</label><input name="username" required maxlength="64" autocomplete="off" /></div><div class="field"><label>显示名称</label><input name="displayName" required maxlength="64" /></div><div class="field"><label>租户 ID</label><input name="tenantId" required maxlength="64" /></div><div class="field"><label>角色</label><select name="role">${roles}</select></div><div class="field full"><label>初始密码</label><input type="password" name="password" required minlength="8" autocomplete="new-password" /></div></div>`;
        if (kind === 'credits') fields = `<div class="setting-row"><strong>当前可用积分</strong><span class="mono">${escapeHtml(accountCredits(user))}</span></div><div class="form-grid" style="margin-top:16px;"><div class="field"><label>调整方向</label><select name="direction"><option value="increase">增加积分</option><option value="decrease">减少积分</option></select></div><div class="field"><label>调整额度</label><input name="amount" inputmode="numeric" pattern="[0-9]+" required placeholder="输入正整数" /></div><div class="field full"><label>调整原因</label><textarea name="reason" required maxlength="300" rows="3"></textarea></div></div>`;
        if (kind === 'permissions') fields = `<div class="field"><label>账号角色</label><select name="role" data-user-permission-role>${roles}</select></div><fieldset style="border:0;padding:0;margin:18px 0;"><legend style="font-weight:700;margin-bottom:12px;">功能权限</legend><div class="form-grid">${Object.entries(userPermissionLabels).map(([value, label]) => `<label style="display:flex;gap:8px;align-items:center;"><input type="checkbox" name="permissions" value="${value}" ${user.permissions.includes(value) ? 'checked' : ''} />${label}</label>`).join('')}</div></fieldset>`;
        if (kind === 'password') fields = `<div class="field"><label>新密码</label><input type="password" name="password" required minlength="8" autocomplete="new-password" /></div><div class="field" style="margin-top:16px;"><label>确认新密码</label><input type="password" name="confirmPassword" required minlength="8" autocomplete="new-password" /></div>`;
        if (kind === 'delete') fields = `<div class="notice danger"><strong>删除后该账号将无法登录。</strong></div><div class="field" style="margin-top:16px;"><label>输入登录账号以确认删除</label><input name="confirmUsername" required autocomplete="off" /></div>`;
        if (kind === 'status') fields = `<div class="notice ${user.status === '启用' ? 'warn' : ''}"><strong>${user.status === '启用' ? '停用后该账号将无法登录。' : '确认恢复该账号的使用权限。'}</strong></div><input type="hidden" name="expectedStatus" value="${escapeHtml(user.status)}" />`;
        if (['password', 'delete', 'status', 'permissions'].includes(kind)) fields += '<div class="field" style="margin-top:16px;"><label>操作原因</label><textarea name="reason" required maxlength="300" rows="2"></textarea></div>';
        return `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="user-dialog-title" data-dialog-key="${escapeHtml(`${kind}:${id || 'new'}:${tenantId || ''}`)}"><div class="modal-head"><h3 id="user-dialog-title">${titles[kind]}</h3><button type="button" class="modal-close" data-action="close-user-dialog" aria-label="关闭">×</button></div>${user ? `<div class="setting-row"><strong>${escapeHtml(user.displayName)}</strong><span>${escapeHtml(user.username)} · ${escapeHtml(user.tenantId)}</span></div>` : ''}<form data-form="user-action" data-kind="${kind}" data-id="${escapeHtml(id || '')}" data-tenant-id="${escapeHtml(tenantId || '')}">${fields}<div class="form-footer" style="margin-top:20px;"><button type="button" class="btn btn-ghost" data-action="close-user-dialog">取消</button><button type="submit" class="btn ${kind === 'delete' ? 'btn-amber' : 'btn-primary'}">${kind === 'create' ? '创建账号' : kind === 'permissions' ? '保存权限' : kind === 'delete' ? '确认删除' : '确认'}</button></div></form></section></div>`;
      };
      const handleUserAction = (form) => {
        if (!canManageUsers()) { toast('当前账号无权管理用户', 'error'); return; }
        const kind = form.dataset.kind;
        if (!['create', 'credits', 'permissions', 'status', 'password', 'delete'].includes(kind)) return;
        const data = new FormData(form);
        let user = state.system.users.find((item) => item.id === form.dataset.id && item.tenantId === form.dataset.tenantId);
        if (kind !== 'create' && !user) { toast('账号不存在或租户范围已变更', 'error'); return; }
        if (user?.id === 'USR-003' && ['permissions', 'status', 'delete'].includes(kind)) { toast('当前管理员账号受保护', 'error'); return; }
        const before = user ? userSnapshot(user) : null;
        const reason = String(data.get('reason') || '').trim();
        if (kind !== 'create' && !reason) { toast('请填写操作原因', 'error'); return; }
        let action;
        if (kind === 'create') {
          const username = String(data.get('username') || '').trim();
          const displayName = String(data.get('displayName') || '').trim();
          const tenantId = String(data.get('tenantId') || '').trim();
          const userRole = String(data.get('role') || '');
          if (!username || !displayName || !tenantId || !userRolePermissions[userRole]) { toast('请填写完整账号信息', 'error'); return; }
          if (String(data.get('password') || '').length < 8) { toast('初始密码至少 8 位', 'error'); return; }
          if (state.system.users.some((item) => item.username.toLowerCase() === username.toLowerCase())) { toast('登录账号已存在', 'error'); return; }
          user = { id: `USR-${crypto.randomUUID()}`, username, displayName, tenantId, role: userRole, status: '启用', permissions: [...userRolePermissions[userRole]], credits: '0', passwordVersion: 1 };
          state.system.users.unshift(user); state.system.userView.page = 1; action = '创建账号';
        } else if (kind === 'credits') {
          const amountText = String(data.get('amount') || '').trim();
          const direction = String(data.get('direction') || '');
          if (!/^\d+$/.test(amountText) || !['increase', 'decrease'].includes(direction)) { toast('额度必须是正整数', 'error'); return; }
          const amount = new creditDecimal(amountText);
          if (!amount.isPositive() || amount.gt(Number.MAX_SAFE_INTEGER)) { toast('请输入有效的正整数额度', 'error'); return; }
          const next = direction === 'increase' ? new creditDecimal(accountCredits(user)).plus(amount) : new creditDecimal(accountCredits(user)).minus(amount);
          if (next.isNegative()) { toast('可用积分不足，无法减少该额度', 'error'); return; }
          if (next.gt(Number.MAX_SAFE_INTEGER)) { toast('调整后余额超出支持范围', 'error'); return; }
          user.credits = next.toFixed(0);
          if (user.id === 'USR-001') state.credits.available = next.toNumber();
          action = direction === 'increase' ? '增加积分' : '减少积分';
          state.transactions.unshift({ time: new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }), type: action, ref: `${user.username} / ${user.tenantId}`, tenantId: user.tenantId, userId: user.id, amount: (direction === 'increase' ? amount : amount.negated()).toNumber(), status: '管理员已调整' });
        } else if (kind === 'permissions') {
          const userRole = String(data.get('role') || '');
          const permissions = [...new Set(data.getAll('permissions').map(String))];
          if (!userRolePermissions[userRole] || permissions.some((value) => !Object.hasOwn(userPermissionLabels, value))) { toast('无效的角色或权限', 'error'); return; }
          if (user.role === userRole && JSON.stringify([...user.permissions].sort()) === JSON.stringify([...permissions].sort())) { toast('权限未发生变更', 'error'); return; }
          user.role = userRole; user.permissions = permissions; action = '权限变更';
        } else if (kind === 'status') {
          if (String(data.get('expectedStatus')) !== user.status) { toast('账号状态已变化，请重新打开', 'error'); return; }
          user.status = user.status === '启用' ? '停用' : '启用'; action = `${user.status}账号`;
        } else if (kind === 'password') {
          const password = String(data.get('password') || '');
          if (password.length < 8 || password !== String(data.get('confirmPassword') || '')) { toast('新密码至少 8 位，且两次输入必须一致', 'error'); return; }
          user.passwordVersion = (user.passwordVersion || 0) + 1; action = '重置密码';
        } else if (kind === 'delete') {
          if (String(data.get('confirmUsername') || '').trim() !== user.username) { toast('输入的账号不一致', 'error'); return; }
          state.system.users = state.system.users.filter((item) => !(item.id === user.id && item.tenantId === user.tenantId)); action = '删除账号';
        }
        recordUserAction(action, user, before, kind === 'delete' ? null : userSnapshot(user), reason);
        form.reset(); userDialog = null; persist(); render(); toast(`${action}已完成`);
      };

      const renderSystemSettings = () => {
         const admin = canManageSystem();
        const requestedTab = state.system?.activeTab || 'auto';
         const tab = systemTabs.some(([value]) => value === requestedTab) && (admin || requestedTab === 'auto') ? requestedTab : 'auto';
        if (state.system) state.system.activeTab = tab;
        const scope = role().scope || (state.role === 'admin' ? '全平台配置与审计' : '本租户配置');
        const visibleTabs = admin ? systemTabs : systemTabs.filter(([value]) => value === 'auto');
        const tabs = visibleTabs.map(([value, label, hint]) => `<button class="${tab === value ? 'active' : ''}" data-system-tab="${value}" title="${hint}">${label}</button>`).join('');
         const gate = '';
        let body = '';
        if (tab === 'auto') {
          const autoOn = state.auto.enabled === true;
          body = `<section class="card card-pad" data-auto-settings><div class="section-head"><h3>自动重做</h3><span class="pill ${autoOn ? 'pill-green' : 'pill-gray'}">${autoOn ? '已开启' : '默认关闭'}</span></div><form data-form="settings"><div class="setting-row"><strong>启用自动重做</strong><button type="button" class="toggle${autoOn ? ' on' : ''}" data-action="toggle-auto" aria-label="切换自动重做" aria-checked="${autoOn}" role="switch"><i></i></button></div><div class="setting-row"><span>检测分数阈值</span><input name="threshold" type="number" min="0" max="100" step="1" value="${escapeHtml(String(state.auto.threshold))}" style="width:88px;" /></div><div class="setting-row"><span>追加次数</span><select name="maxCount" style="width:120px;">${[1,2,3,4,5].map((count) => `<option value="${count}" ${Number(state.auto.maxCount) === count ? 'selected' : ''}>${count} 次</option>`).join('')}</select></div><div class="form-footer"><button class="btn btn-primary" type="submit">保存设置</button></div></form></section>`;
        } else if (tab === 'models') {
          const purpose = modelKeyFormState().purpose;
          const draft = draftForModelPurpose(purpose);
          const slotCount = Math.min(MODEL_KEY_SLOT_MAX, Math.max(1, draft.keys.length));
          const keySlots = Array.from({ length: slotCount }, (_, index) => {
            const value = draft.keys[index] || '';
            const plus = index === slotCount - 1 && slotCount < MODEL_KEY_SLOT_MAX ? `<button type="button" class="btn btn-ghost model-key-add" data-action="model-key-add" aria-label="新增 API Key">＋</button>` : '';
            return `<div class="model-key-row"><input name="key_${index}" type="text" autocomplete="off" ${index === 0 ? 'required' : ''} value="${escapeHtml(value)}" placeholder="${index === 0 ? '必填' : '选填'}" />${plus}</div>`;
          }).join('');
          const modelRows = state.system.modelKeys.map((item) => {
            const keys = normalizeModelApiKeys(item);
            const keySummary = keys.length ? keys.map((entry) => entry.masked || maskApiKey(entry.raw)).filter(Boolean).join(' · ') : '—';
            return `<tr><td><strong>${escapeHtml(item.provider)}</strong><div class="tiny muted">${escapeHtml(item.model)}</div><div class="tiny muted">${escapeHtml(item.baseUrl || '—')}</div></td><td>${escapeHtml(item.purpose)}</td><td class="mono tiny" style="max-width:280px;white-space:normal;">${escapeHtml(keySummary)}</td><td><span class="pill ${item.status === '已启用' ? 'pill-green' : 'pill-gray'}">${item.status}</span></td><td>${escapeHtml(item.scope)}</td><td><button class="btn btn-ghost btn-sm" data-action="toggle-model-key" data-id="${item.id}">${item.status === '已启用' ? '停用' : '启用'}</button><button class="btn btn-ghost btn-sm" data-action="delete-model-key" data-id="${item.id}" style="margin-left:6px;">删除</button></td></tr>`;
          }).join('');
          body = `<section class="card card-pad"><div class="section-head"><h3>检测基线 · Gemini Vision</h3><span class="pill pill-green">生产</span></div><div class="tiny muted">${escapeHtml(checkPolicy.BASELINE.model)} · 通过标准 ${checkPolicy.BASELINE.passScore} 且 passed=true</div></section><section class="card form-card" style="margin-top:18px;"><div class="section-head"><div><h3>大模型 API Key 配置与管理</h3></div><span class="pill pill-blue">平台范围</span></div><form data-form="model-key"><div class="form-grid"><div class="field"><label>提供商</label><select name="provider">${modelProviders.map((name) => `<option ${draft.provider === name ? 'selected' : ''}>${escapeHtml(name)}</option>`).join('')}</select></div><div class="field"><label>模型版本</label><input name="model" value="${escapeHtml(draft.model)}" /></div><div class="field"><label>用途</label><select name="purpose" data-model-purpose="true">${modelPurposes.map((name) => `<option ${purpose === name ? 'selected' : ''}>${escapeHtml(name)}</option>`).join('')}</select></div><div class="field full"><label>Base URL</label><input name="base_url" placeholder="https://api.example.com/v1" value="${escapeHtml(draft.baseUrl)}" /></div></div><div class="section-head" style="margin-top:18px;"><h4>API Key</h4></div><div class="model-key-list">${keySlots}</div><div class="form-footer"><button class="btn btn-primary" type="submit">保存模型配置</button></div></form></section><section class="card card-pad" style="margin-top:18px;"><div class="section-head"><h3>已登记渠道</h3><span class="tiny muted">${state.system.modelKeys.length} 条</span></div><div class="table-wrap"><table><thead><tr><th>渠道 / 模型 / Base URL</th><th>用途</th><th>Keys</th><th>状态</th><th>范围</th><th>操作</th></tr></thead><tbody>${modelRows}</tbody></table></div></section>`;
        }
         return renderShell(`<div class="page"><div class="page-intro"><div><h2>系统管理</h2></div><div class="pill ${admin ? 'pill-blue' : 'pill-amber'}">${admin ? '平台管理员' : '租户范围'}</div></div>${gate}<section class="card card-pad"><div class="filter-tabs">${tabs}</div></section>${body}</div>`, '系统管理');
      };
       const renderCredits = () => {
         const view = state.creditsView || (state.creditsView = { page: 1, pageSize: 5 });
         const tenantTransactions = state.transactions.filter((entry) => (!entry.tenantId || entry.tenantId === currentTenantId()) && (!entry.userId || entry.userId === 'USR-001'));
         const transactionResult = paginate(tenantTransactions, view);
         const transactions = transactionResult.items;
         return renderShell(`<div class="page"><div class="page-intro"><div><h2>积分与充值</h2></div><div class="pill pill-green">账本可追溯</div></div><div class="grid grid-3"><div class="card metric"><div class="metric-label"><i class="metric-accent"></i>可用余额</div><div class="metric-value">${state.credits.available}</div><div class="metric-meta">积分 · 永久有效</div></div><div class="card metric"><div class="metric-label"><i class="metric-accent"></i>冻结中</div><div class="metric-value">${state.credits.frozen}</div><div class="metric-meta">处理任务预留，终态按张结算</div></div><div class="card metric"><div class="metric-label"><i class="metric-accent"></i>基础换算</div><div class="metric-value">1:10</div><div class="metric-meta">人民币 1 元 = 10 积分</div></div></div><div class="dashboard-grid"><section class="card form-card"><div class="section-head"><h3>提交人工充值订单</h3></div><form data-form="recharge"><div class="field"><label>充值档位</label><select name="amount"><option value="1000">1,000 积分 · ¥100</option><option value="3150">3,150 积分 · ¥300</option><option value="5500" selected>5,500 积分 · ¥500</option><option value="11500">11,500 积分 · ¥1,000</option><option value="36000">36,000 积分 · ¥3,000</option></select></div><div class="field" style="margin-top:15px;"><label>转账备注</label><input name="note" value="DEMO-TOPUP-20261025" /></div><div class="form-footer"><button class="btn btn-primary" type="submit">提交充值订单</button></div></form></section><section class="card card-pad"><div class="section-head"><h3>最近流水</h3></div><div class="table-wrap"><table style="min-width:0;"><thead><tr><th>时间</th><th>类型 / 引用</th><th>变动</th><th>状态</th></tr></thead><tbody>${transactions.map((t) => `<tr><td class="tiny muted">${t.time}</td><td><strong style="font-size:12px;">${t.type}</strong><div class="tiny muted">${t.ref}</div></td><td style="font-weight:800;color:${t.amount >= 0 ? 'var(--teal-deep)' : 'var(--danger)'};">${t.amount >= 0 ? '+' : ''}${t.amount}</td><td class="tiny">${t.status}</td></tr>`).join('')}</tbody></table></div>${renderPager({ ...transactionResult, prevAction: 'credits-page-prev', nextAction: 'credits-page-next' })}</section></div></div>`, '积分与充值');
       };
      const renderSupport = () => { const canUnfreeze = state.role === 'support' || state.role === 'admin'; return renderShell(`<div class="page"><div class="page-intro"><div><h2>客服 / 管理后台</h2></div><div class="pill ${canUnfreeze ? 'pill-green' : 'pill-red'}">${role().label} · ${canUnfreeze ? '可解冻' : '只读'}</div></div><div class="grid grid-4">${metric('待处理工单', state.tickets.filter(t=>t.status !== '已完成').length, '含技术异常与冻结事件')}${metric('待解冻', state.tickets.filter(t=>t.status === '待解冻').length, '需要授权操作者')}${metric('本周完成', '18', '工单与充值确认')}${metric('审计事件', '64', '含幂等和冻结记录')}</div><section class="card card-pad" style="margin-top:18px;"><div class="section-head"><h3>工单与冻结事件</h3></div><div class="table-wrap"><table><thead><tr><th>工单</th><th>类型</th><th>租户 / 关联</th><th>状态</th><th>说明</th><th>操作</th></tr></thead><tbody>${state.tickets.map((t) => `<tr><td><strong>${t.id}</strong><div class="tiny muted">${t.createdAt}</div></td><td>${t.kind}</td><td>${t.tenant}<div class="mono muted">${t.ref}</div></td><td>${t.status === '待解冻' ? '<span class="pill pill-amber">待解冻</span>' : t.status === '待处理' ? '<span class="pill pill-red">待处理</span>' : t.status === '待确认' ? '<span class="pill pill-amber">待确认</span>' : '<span class="pill pill-green">已完成</span>'}</td><td class="tiny muted">${t.note}</td><td>${t.status !== '已完成' && canUnfreeze ? `<button class="btn btn-teal btn-sm" data-action="resolve-ticket" data-id="${t.id}">${t.kind === '充值确认' ? '确认到账' : '解冻并记录'}</button>` : '<span class="tiny muted">无可用操作</span>'}</td></tr>`).join('')}</tbody></table></div></section></div>`, '客服 / 管理后台'); };
      const renderGeminiReport = (report, decision) => {
        const passed = report?.passed === true && Number(report.total) >= 75;
        return `<div class="notice ${passed ? '' : 'warn'}" data-gemini-report style="margin-top:12px;"><div class="notice-icon">${passed ? 'i' : '!'}</div><div style="flex:1;min-width:0;"><div class="split"><strong>Gemini Vision 检测报告</strong><span class="pill ${passed ? 'pill-green' : 'pill-amber'}">${passed ? '通过' : '未通过'} · ${scoreText(report?.total)} / 100</span></div><div style="font-size:12px;line-height:1.9;margin-top:8px;">${escapeHtml(report?.reason || '')}<br>自动重做：${escapeHtml(decision?.reason || '未触发')}</div>${report?.errors?.length ? `<div style="font-size:12px;margin-top:8px;overflow-wrap:anywhere;">${report.errors.map(escapeHtml).join('<br>')}</div>` : ''}<div class="score-grid">${['噪点颗粒','景深','光线曝光','色彩真实度','整体真实感'].map((label,i) => `<div class="score-card"><span>${label}</span><strong>${report?.scores?.[i] ?? '—'}</strong></div>`).join('')}</div></div></div>`;
      };
      const renderRetiredCheckNotice = () => `<div class="notice warn" data-check-retired style="margin-top:12px;"><div class="notice-icon">i</div><div style="flex:1;min-width:0;"><strong>历史研究夹具，已停用</strong><div class="tiny muted" style="margin-top:6px;">Check_Aimage 报告不再展示，不作为生产判定。</div></div></div>`;
      const renderRoundReport = (round) => round.report?.engine === 'Check_Aimage' ? renderRetiredCheckNotice() : renderGeminiReport(round.report, round.autoDecision);
      const renderDetail = () => {
        const item = findOwnedHistory(state.selectedId);
        if (!item) return renderHistory();
        const generation = item.taskType === 'generation';
        const results = historyResults(item);
        const expired = item.status === 'EXPIRED' || item.status === 'DELETED';
        const retryCount = Number(item.retryCount || 0);
        const downloadable = results.filter((result) => result.downloadable && !expired);
        const previewGrid = downloadable.length ? `<div class="generated-preview-grid">${results.filter((result) => result.downloadable && !expired).map((result) => `<label class="generated-preview-card"><input type="checkbox" data-result-select data-result-id="${escapeHtml(result.id)}" checked /><img src="${escapeHtml(result.previewUrl)}" alt="${escapeHtml(result.name)}" /><span>${escapeHtml(result.name)}</span></label>`).join('')}</div>` : '';
        const resultTable = `${results.length ? `<div class="table-wrap"><table><thead><tr><th>图片</th><th>状态</th><th>检测值</th><th>结果说明</th><th>操作</th></tr></thead><tbody>${results.map((result) => `<tr><td><strong>${escapeHtml(result.name)}</strong><div class="tiny muted">${result.id}</div></td><td>${result.status === 'GENERATED' ? '<span class="pill pill-green">已生成</span>' : result.status === 'DELETED' ? '<span class="pill pill-gray">原图已删除</span>' : result.status === 'DELIVERED' ? '<span class="pill pill-green">成功</span>' : result.status === 'PRE_REVIEW' ? '<span class="pill pill-green">校验通过</span>' : result.status === 'TECH_FAILED' ? '<span class="pill pill-red">技术异常</span>' : statusPill(result.status)}</td><td>${result.score == null ? '—' : `${result.score} / 100`}</td><td class="tiny muted">${escapeHtml(result.reason || '—')}</td><td><div style="display:flex;gap:8px;flex-wrap:wrap;"><button class="btn btn-ghost btn-sm" data-action="view-result-detail" data-id="${escapeHtml(item.id)}" data-result-id="${escapeHtml(result.id)}">查看详情</button>${result.downloadable && !expired ? `<button class="btn btn-ghost btn-sm" data-action="download-result" data-id="${item.id}" data-result-id="${result.id}">下载</button>` : '<span class="tiny muted">不可下载</span>'}</div></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty"><strong>暂无逐张结果</strong><span>该任务尚未生成有效文件。</span></div>'}`;
        const runningJob = state.jobs.find((job) => !job.done && job.historyId === item.id);
        const resultActions = `<div class="form-footer" style="margin-top:14px;"><div style="display:flex;gap:8px;flex-wrap:wrap;">${runningJob ? `<button class="btn btn-teal btn-sm" data-action="open-job" data-id="${escapeHtml(runningJob.id)}">查看运行进度</button>` : ''}${downloadable.length ? `<button type="button" class="btn btn-teal btn-sm" data-action="download-result-batch" data-id="${escapeHtml(item.id)}">选择目录并批量下载</button>` : ''}${!generation && !expired ? `<button class="btn btn-ghost btn-sm" data-action="copy-task" data-id="${escapeHtml(item.id)}">复制为新草稿</button><button class="btn btn-ghost btn-sm" data-action="reprocess-task" data-id="${escapeHtml(item.id)}">主动重新处理</button>` : ''}${item.status === 'TECH_FAILED' ? `<button class="btn btn-amber btn-sm" data-action="retry-tech" data-id="${escapeHtml(item.id)}">${retryCount >= 2 ? '已达 2 次上限' : `重试检测（${retryCount} / 2）`}</button>` : ''}</div></div>`;
        return renderShell(`<div class="page"><div class="page-intro"><div><h2>${escapeHtml(item.title)}</h2><p class="lede">${formatSource(item.source)} · ${item.createdAt} · ${escapeHtml(item.stage || '演示任务')} · 租户 ${escapeHtml(item.tenantId || currentTenantId())}</p></div><div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;align-items:center;">${statusPill(item.status)}<button class="btn btn-ghost btn-sm" data-page="history">返回任务详情</button></div></div>${!generation ? `<div class="grid grid-4">${metric('Gemini总分', scoreText(item.score), item.threshold != null ? `阈值 ${item.threshold}` : '检测基线 75')}${metric('处理轮次', item.rounds?.length || 0, item.rounds?.length > 1 ? '保留每一轮证据' : '首轮完成')}${metric('按张账务', item.consumedCredits || (item.chargeState === 'CONSUMED' || item.billing?.startsWith('已消费') ? (item.billing.match(/\d+/)?.[0] || '0') : '0'), item.billing || '未结算')}${metric('可下载结果', `${results.filter((x) => x.downloadable).length} / ${results.length || 0}`, expired ? '保留摘要，文件不可下载' : 'sRGB JPEG')}</div>` : ''}<section class="card card-pad" style="margin-top:18px;" data-results-preview><div class="section-head"><h3>结果预览</h3><span class="pill pill-green">${downloadable.length} 张可下载</span></div>${previewGrid}${resultTable}${resultActions}</section>${item.checkBaseline?.engine === 'Check_Aimage' ? `<section class="card card-pad" style="margin-top:18px;">${renderRetiredCheckNotice()}</section>` : ''}${!generation ? `<section class="card card-pad" style="margin-top:18px;"><div class="section-head"><h3>处理轮次时间线</h3><span class="tiny muted">检测报告在此展开</span></div><div class="timeline">${(item.rounds || []).map((round) => `<div class="timeline-item"><div class="timeline-dot ${round.status === 'TECH_FAILED' ? 'fail' : round.status === 'AUTO_REPROCESS_PENDING' ? 'pending' : ''}">${round.roundNo}</div><div class="timeline-content"><div class="timeline-head"><div><strong>${item.checkBaseline ? `R${round.roundNo}` : `旧版第 ${round.roundNo} 轮`} · ${statusLabels[round.status] || round.status}</strong><div class="tiny muted" style="margin-top:3px;">${escapeHtml(round.trigger)}</div></div><span class="tiny muted">${round.billing}</span></div><div class="layers">${round.layers.map((l) => `<div class="layer ${l.status === 'pending' ? 'pending' : l.status === 'failed' ? 'fail' : ''}">${l.label}<br><span style="font-size:9px;">${l.status === 'done' ? '完成' : l.status === 'pending' ? '排队' : '异常'}</span></div>`).join('')}</div>${renderRoundReport(round, item)}<div class="split tiny muted" style="margin-top:10px;"><span>输入：${escapeHtml(round.input)}</span><span>输出：${escapeHtml(round.output)}</span></div></div></div>`).join('')}</div></section>` : ''}</div>`, '任务详情');
      };
      const renderResultDialog = () => {
        if (!resultDialog || state.page !== 'detail') return '';
        const item = findOwnedHistory(resultDialog.historyId);
        const result = historyResults(item).find((entry) => entry.id === resultDialog.resultId);
        if (!item || !result) return '';
        const metadata = result.metadata || item.metadata || makeMetadata({ source: item.source });
        const expired = item.status === 'EXPIRED' || item.status === 'DELETED';
        return `<div class="modal-backdrop"><div class="modal result-detail-modal" style="width:min(820px,100%);" role="dialog" aria-modal="true" aria-labelledby="result-detail-title"><div class="modal-head"><div><h3 id="result-detail-title">图片详情</h3><strong style="display:block;margin-top:8px;overflow-wrap:anywhere;">${escapeHtml(result.name)}</strong><div class="tiny muted">${escapeHtml(result.id)}</div></div><button class="modal-close" data-action="close-result-detail" aria-label="关闭图片详情">×</button></div>${result.report ? renderRoundReport({ report: result.report, autoDecision: result.autoDecision }) : ''}${item.autoSnapshot ? `<details style="margin-top:14px;"><summary>自动重做快照</summary><div style="font-size:12px;overflow-wrap:anywhere;">${item.autoSnapshot.enabled ? '已开启' : '已关闭'} · 阈值 ${escapeHtml(String(item.autoSnapshot.threshold ?? '—'))} · 追加 ${escapeHtml(String(item.autoSnapshot.maxCount ?? '—'))} 次<br>策略：${escapeHtml(item.autoSnapshot.version || item.detectBaseline?.version || '')}<br>设备：${escapeHtml(item.presetSnapshot?.name || '—')}</div></details>` : ''}<div class="grid grid-2" style="margin-top:18px;"><div class="card card-pad"><div class="section-head"><h3 style="font-size:16px;">账务与幂等</h3><span class="pill pill-green">按张</span></div><div class="setting-row"><div class="tiny muted">预留</div><strong>${item.chargeState === 'FROZEN' ? `${item.reservedCredits || 0} 积分` : item.chargeState === 'COPY_NO_RESERVE' ? '复制免冻结' : item.billing?.includes('冻结') ? escapeHtml(item.billing) : '已结算 / 已释放'}</strong></div><div class="setting-row"><div class="tiny muted">消费</div><strong>${item.consumedCredits || (item.chargeState === 'CONSUMED' || item.billing?.startsWith('已消费') ? (item.billing.match(/\d+/)?.[0] || '0') : '0')} 积分</strong></div><div class="setting-row"><div class="tiny muted">留存至</div><strong>${metadata.retentionUntil}</strong></div><div class="setting-row"><div class="tiny muted">结果访问</div><strong>${expired ? '摘要可查 / 文件不可下载' : canDownload(item) ? '可预览和下载' : '等待客服审计'}</strong></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;">${!expired && item.taskType !== 'generation' ? `<button class="btn btn-ghost btn-sm" data-action="delete-result" data-id="${item.id}">主动删除</button><button class="btn btn-ghost btn-sm" data-action="expire-demo" data-id="${item.id}">标记到期</button>` : ''}</div></div><div class="card card-pad"><div class="section-head"><h3 style="font-size:16px;">处理快照</h3><span class="tiny muted">处理快照</span></div><div class="tiny muted" style="line-height:1.9;">尺寸：${metadata.width} × ${metadata.height}<br>文件大小：${metadata.fileSize}<br>设备：${escapeHtml(metadata.devicePreset)}<br>EXIF：${escapeHtml(metadata.exif)}<br>GPS：${escapeHtml(metadata.gps)}<br>色彩：${metadata.output}<br>保留期：${metadata.retentionUntil}<br></div></div></div><div class="form-footer" style="margin-top:16px;"><button class="btn btn-ghost" data-action="close-result-detail">关闭</button></div></div></div>`;
      };
      const renderResultOverlay = () => { document.getElementById('modal-root').innerHTML = stripAnnotationText(renderResultDialog()); };
      const closeResultDetail = () => { const target = resultDialog; resultDialog = null; renderResultOverlay(); [...document.querySelectorAll('[data-action="view-result-detail"]')].find((button) => button.dataset.id === target?.historyId && button.dataset.resultId === target?.resultId)?.focus(); };
      const renderLogin = () => `<div class="login-shell"><section class="login-visual"><div><h1>把每一张图，<br><span style="color:var(--amber);">送进证据链。</span></h1><p>蜜獾原图 v2 工作台，集中管理图片生成、处理、检测与积分。</p><div class="login-ribbon"><span>可追溯处理链</span><span>Gemini 检测报告</span><span>逐轮证据保留</span><span>四类来源历史</span></div></div><div class="tiny" style="color:#7f969d;position:relative;z-index:1;"></div></section><section class="login-form"><div class="brand"><div class="brand-mark">HB</div><div><h1>蜜獾原图</h1><small>image lab · v2</small></div></div><h2>进入工作台</h2><p class="lede">选择账号角色进入工作台。</p><div class="login-select"><label class="field"><span style="font-size:12px;font-weight:800;color:var(--ink-soft);">账号角色</span><select id="login-role"><option value="merchant">商家 · 提交和查看任务</option><option value="support">技术客服 · 处理冻结和异常</option><option value="admin">平台管理员 · 运营与审计</option></select></label></div><button class="btn btn-primary" style="width:100%;" data-action="login">进入工作台 <span>→</span></button><div class="role-grid">${Object.entries(roleMeta).map(([key,meta]) => `<button class="role-card" data-role-card="${key}"><span class="role-avatar">${meta.avatar}</span><strong>${meta.label}</strong><small>${meta.desc}</small></button>`).join('')}</div><p class="login-note"></p></section></div>`;
      const renderProcessingModal = () => {
         if (!state.processing) return '';
         const p = state.processing;
         const generated = p.historyId ? state.history.find((entry) => entry.id === p.historyId) : null;
         const modalStageLabels = p.kind === 'generation' ? generationStageLabels : stageLabels.map((label) => ({ '五层处理': '技术处理', 'Check 检测': '结果检测' }[label] || label));
         const generatedAssets = historyResults(generated).filter((result) => result.downloadable);
         const batchRows = p.batchItems?.length ? '<div class="table-wrap" style="margin-top:14px;"><table><thead><tr><th>图片</th><th>当前状态</th><th>原因</th></tr></thead><tbody>' + p.batchItems.map((item) => '<tr><td>' + escapeHtml(item.name) + '</td><td>' + (item.ok === false ? '<span class="pill pill-red">失败</span>' : p.done ? '<span class="pill pill-green">完成</span>' : '<span class="pill pill-blue">处理中</span>') + '</td><td class="tiny muted">' + escapeHtml(item.errors?.join('；') || (p.done ? '已写入历史' : '等待阶段推进')) + '</td></tr>').join('') + '</tbody></table></div>' : '';
                  const generatedLinks = p.done && p.kind === 'generation' && p.outcome === 'GENERATED' && generatedAssets.length ? '<section class="generated-assets"><div class="section-head"><div><h4>生成结果预览</h4><span class="tiny muted">本批次共 ' + generatedAssets.length + ' 张；点击图片可在线预览，下载时由用户选择保存路径。</span></div><span class="pill pill-green">' + generatedAssets.length + ' 张</span></div><div class="generated-preview-grid">' + generatedAssets.map((asset) => '<label class="generated-preview-card"><input type="checkbox" data-generated-select data-result-id="' + escapeHtml(asset.id) + '" checked /><img src="' + escapeHtml(asset.previewUrl || makePreviewDataUrl(asset.name)) + '" alt="' + escapeHtml(asset.name) + '" /><span>' + escapeHtml(asset.name) + '</span></label>').join('') + '</div><div class="form-footer" style="margin-top:14px;"><span class="tiny muted">批量下载不会生成 ZIP。</span><button type="button" class="btn btn-teal btn-sm" data-action="download-generated-batch" data-id="' + escapeHtml(p.historyId) + '">批量下载</button></div></section>' : '';
         const generationNextStep = p.done && p.kind === 'generation' && generatedAssets.length ? '<div class="form-footer"><button class="btn btn-amber" data-action="continue-generated" data-id="' + escapeHtml(p.historyId) + '">前往图片资源 <span>→</span></button></div>' : '';
         const continueAction = '';
         return '<div class="modal-backdrop"><div class="modal"><div class="modal-head"><div><h3 style="font-family:var(--display);font-size:24px;">' + (p.done ? (p.kind === 'generation' ? '生图完成' : '处理完成') : (p.kind === 'generation' ? '正在生成图片' : '任务正在进入证据链')) + '</h3></div>' + '<button class="modal-close" data-action="close-processing" aria-label="关闭任务进度">×</button>' + '</div><p class="tiny muted">' + escapeHtml(p.message) + '</p><div class="progress-line" style="margin-top:16px;"><span style="width:' + p.progress + '%;"></span></div><div class="processing-rail">' + modalStageLabels.map((label, i) => '<div class="processing-step ' + (i < p.step ? 'done' : i === p.step && !p.done ? 'active' : '') + '"><span class="step-dot">' + (i < p.step ? '✓' : i + 1) + '</span><span>' + label + '</span></div>').join('') + '</div>' + batchRows + generatedLinks + generationNextStep + (p.done ? '<div class="notice ' + (p.outcome === 'TECH_FAILED' ? 'danger' : p.outcome === 'FAILED' || p.outcome === 'REJECTED' || p.outcome === 'IMAGE_LOCKED' ? 'warn' : '') + '"><div class="notice-icon">' + (p.outcome === 'TECH_FAILED' ? '!' : p.outcome === 'FAILED' || p.outcome === 'REJECTED' || p.outcome === 'IMAGE_LOCKED' ? '◌' : '✓') + '</div><div><strong style="font-size:12px;">' + escapeHtml(p.resultTitle) + '</strong><div class="tiny muted" style="margin-top:4px;">' + escapeHtml(p.resultBody) + '</div></div></div><div class="form-footer" style="margin-top:16px;">' + continueAction + '<button class="btn btn-ghost" data-action="close-processing">稍后查看</button>' + (p.historyId ? '<button class="btn btn-primary" data-action="open-result" data-id="' + escapeHtml(p.historyId) + '">打开任务详情 <span>→</span></button>' : '<button class="btn btn-primary" data-action="open-last-result">打开任务详情 <span>→</span></button>') + '</div>' : '<div class="form-footer"><button class="btn btn-ghost" data-action="close-processing">后台运行</button></div>') + '</div></div>';
       };
       const stripAnnotationText = (markup) => { const template = document.createElement('template'); template.innerHTML = markup; template.content.querySelectorAll('.lede, p.tiny.muted, .micro-note, .field > label > span, .field > .tiny.muted, .section-head > div > p.tiny.muted, .section-head > div > span.tiny.muted, .section-head > span.tiny.muted, .form-footer > .tiny.muted, .metric-meta, .card[style*="background:#f7fbfa"] > .tiny.muted, form[data-form="settings"] .setting-row .tiny.muted, .history-note, .annotation-note, [data-gps-mode-hint], .process-settings-block > .tiny.muted, .notice[style*="background:#eff7ff"] .split > .tiny.muted, .notice[style*="background:#eff7ff"] > div > .tiny.muted').forEach((node) => node.remove()); return template.innerHTML; };
       const render = () => {
        captureResourceForm();
        const app = document.getElementById('app');
        const modalRoot = document.getElementById('modal-root');
        const previousKey = modalRoot.querySelector('.resource-modal')?.dataset.dialogKey;
        const active = document.activeElement;
        const attributes = ['id','name','data-action','data-id','data-source','data-resource-select','value'].filter((key) => active?.hasAttribute(key)).map((key) => [key,active.getAttribute(key)]);
        const cursor = active?.tagName === 'TEXTAREA' || (active?.tagName === 'INPUT' && active.type === 'text') ? active.selectionStart : null;
        if (!state.session || state.page === 'login') app.innerHTML = stripAnnotationText(renderLogin());
        else {
          const content = state.page === 'dashboard' ? renderDashboard() : state.page === 'resources' ? renderResources() : state.page === 'direct' ? renderDirectInput() : state.page === 'devices' ? renderDevicePresetsV2() : state.page === 'prompts' ? renderPromptTemplates() : state.page === 'history' ? renderHistory() : state.page === 'settings' ? renderSystemSettings() : state.page === 'users' ? renderUsers() : state.page === 'logs' ? renderUserLogs() : state.page === 'credits' ? (state.role === 'merchant' ? renderCredits() : renderAccessDenied('积分与充值')) : state.page === 'messages' ? renderMessagesV2() : state.page === 'support' ? renderSupportV2() : state.page === 'detail' ? renderDetail() : renderDashboard();
          app.innerHTML = stripAnnotationText(content);
        }
        modalRoot.innerHTML = stripAnnotationText(renderUserDialog() || renderResultDialog() || renderResourceDialog() || renderProcessingModal());
        app.inert = !!modalRoot.children.length;
        const dialog = modalRoot.querySelector('.resource-modal');
        if (dialog && previousKey !== dialog.dataset.dialogKey) dialog.querySelector('.modal-close')?.focus({ preventScroll: true });
        else if (attributes.length) {
          const scope = dialog || app;
          const target = [...scope.querySelectorAll('button,input,textarea,select')].find((node) => node.tagName === active?.tagName && attributes.every(([key,value]) => node.getAttribute(key) === value));
          target?.focus({ preventScroll: true });
          if (target && cursor != null) target.setSelectionRange(cursor,cursor);
        }
       };
      const toast = (message, type = 'success') => { const node = document.createElement('div'); node.className = `toast ${type === 'error' ? 'error' : ''}`; node.textContent = message; document.getElementById('toast-root').appendChild(node); setTimeout(() => node.remove(), 3600); };
      const selectScenario = (key) => { state.lastScenario = key; persist(); render(); toast(`已选择场景：${Object.fromEntries(scenarioOptions)[key] || key}`); };
      const scenarioConfig = (key) => ({
        pass: { geminiKey:'pass', nextKey:'pass', message:'首轮五维报告已保留。' },
        fail: { geminiKey:'low', nextKey:'pass', message:'总分低于阈值，按快照进入自动重做。' },
        'high-threshold': { geminiKey:'highThreshold', nextKey:'pass', message:'已过 75 基线，但仍可能低于用户阈值。' },
        'quality-fail': { geminiKey:'pass', qualityFailed:true, message:'文件或保真检查失败。' },
        tech: { geminiKey:'tech', message:'Gemini 检测超时，不自动循环。' },
        duplicate: { geminiKey:'pass', message:'重复提交已去重。', idempotencyKey:'DEMO-DUPLICATE-CHAIN' },
        'pre-review-fail': { preReview:true, validationCase:'unsafe', message:'预审命中明确禁止项，未进入技术处理。', resultTitle:'预审未通过', resultBody:'未冻结积分。' },
        'image-lock': { preReview:true, imageKey:'same-demo-image.jpg', forceLock:true, message:'同一图片第二次预审失败。', resultTitle:'图片已锁定', resultBody:'可提交客服工单。' },
        'account-freeze': { preReview:true, imageKey:'different-demo-image-', forceFreeze:true, message:'三张不同图片连续预审失败。', resultTitle:'账号已冻结', resultBody:'新建任务被拦截。' }
      }[key] || { geminiKey:'pass', nextKey:'pass', message:'首轮五维报告已保留。' });
      const finalizeGenerationOnly = (payload, scenario) => {
        const source = payload.mode === 'image' ? 'image' : 'text';
        const itemId = payload.taskId;
        const previous = state.history.find((entry) => entry.id === itemId && entry.tenantId === payload.tenantId);
        const results = makeItemResults(itemId, { ...payload, fileName: 'result' }, 'GENERATED', null, '生图完成，尚未进入 EXIF 处理', payload.quantity || 1);
        const reserved = Number(previous?.reservedCredits || payload.reservedCredits || 0);
        const consumedUnits = billableResultCount(results, 'GENERATED');
        const billing = settleTaskCredits(itemId, reserved, consumedUnits * CREDIT_PER_IMAGE, '生图结算');
        const item = { id: itemId, title: payload.title || (source === 'text' ? '文生图 · 新任务' : '图生图 · 新任务'), source, createdAt: demoNow, status: 'GENERATED', score: null, threshold: null, rounds: [], billing, preview: source === 'text' ? 'art-teal' : 'art-coral', stage: '生图完成 · 已加入图片资源', results, metadata: makeMetadata({ ...payload, source }), tenantId: payload.tenantId, retentionUntil: '2026-11-01 23:59', copiedFrom: payload.copyOf || null, reprocessOf: payload.reprocessOf || null, idempotencyKey: payload.idempotencyKey || null, idempotent: !!scenario.idempotencyKey, retryCount: 0, chargeState: consumedUnits ? 'CONSUMED' : 'RELEASED', reservedCredits: 0, consumedCredits: consumedUnits * CREDIT_PER_IMAGE, prompt: payload.prompt || '' };
        item.generatedAssets = results.filter((result) => result.downloadable && result.resultUrl).map((result) => ({ id: result.id, name: result.name, url: result.resultUrl }));
        const resources = addResources(results, source, item.id, payload.tenantId);
        item.results = results.map((result, index) => ({ ...result, resourceId: resources[index].id }));
        recordTask(item, payload);
        state.selectedId = item.id;
        if (payload.copyOf) state.copyGate = { active: false, tenantId: null, taskId: null };
        notifyAccount({ id: uniqueId('MSG'), type: 'success', title: '生图完成', body: `${item.generatedAssets.length} 张图片已加入图片资源；${billing}。`, time: '刚刚', read: false }, payload.messageRecipient);
        state.processing = { ...state.processing, step: generationStageLabels.length, progress: 100, done: true, outcome: 'GENERATED', historyId: item.id, resultTitle: '生图完成 · 已加入图片资源', resultBody: `已将${item.generatedAssets.length}张图片加入资源库；${billing}。` };
        persist(); render(); toast(`生图完成，${billing}`);
      };
      const adjustTaskCredits = (available, frozen = 0) => {
        const nextAvailable = new creditDecimal(state.credits.available).plus(available);
        const nextFrozen = new creditDecimal(state.credits.frozen).plus(frozen);
        if (nextAvailable.isNegative() || nextFrozen.isNegative()) throw new Error('积分余额不足');
        state.credits.available = nextAvailable.toNumber(); state.credits.frozen = nextFrozen.toNumber();
      };
      const reserveTaskCredits = (taskId, quantity, label) => {
        const amount = Math.max(0, Number(quantity) || 0) * CREDIT_PER_IMAGE;
        if (!amount) return { amount: 0, billing: '未冻结' };
        if (state.copyGate.active) return { amount: 0, billing: '复制任务 · 暂缓冻结' };
        try { adjustTaskCredits(-amount, amount); }
        catch (_) { throw new Error(`积分不足：需冻结 ${amount} 积分（${quantity} 张 × ${CREDIT_PER_IMAGE}）`); }
        state.transactions.unshift({ time: demoNow, type: label || '任务预留', ref: taskId, amount: -amount, status: `冻结中 · 预计 ${amount} 积分`, tenantId: currentTenantId(), userId: 'USR-001' });
        return { amount, billing: `冻结中 · 预计 ${amount} 积分` };
      };
      const settleTaskCredits = (taskId, reserved, consumed, label) => {
        const hold = Math.max(0, Number(reserved) || 0);
        const take = Math.max(0, Math.min(hold, Number(consumed) || 0));
        const release = hold - take;
        if (hold) {
          try { adjustTaskCredits(release, -hold); }
          catch (_) { state.credits.frozen = Math.max(0, state.credits.frozen - hold); state.credits.available += release; }
        }
        if (take) state.transactions.unshift({ time: demoNow, type: label || '任务结算', ref: taskId, amount: -take, status: `已消费 ${take} 积分`, tenantId: currentTenantId(), userId: 'USR-001' });
        else if (release) state.transactions.unshift({ time: demoNow, type: label || '任务释放', ref: taskId, amount: release, status: `已释放 ${release} 积分`, tenantId: currentTenantId(), userId: 'USR-001' });
        return take ? `已消费 ${take} 积分` : (hold ? '已释放预留 · 不消费' : '未冻结 · 不消费');
      };
      const billableResultCount = (results = [], status) => {
        if (status === 'GENERATED') return results.filter((entry) => entry.status === 'GENERATED' || entry.downloadable).length;
        return results.filter((entry) => entry.status === 'DELIVERED').length;
      };
      const recordTask = (item, payload) => {
        item.taskType = payload.taskType;
        item.messageRecipient = payload.messageRecipient;
        item.resourceIds = [...(payload.resourceIds || [])];
        item.runId = payload.runId;
        if (payload.taskType === 'processing') { item.presetSnapshot = payload.presetSnapshot; item.autoSnapshot = { ...payload.autoSnapshot }; item.detectBaseline = { ...(payload.detectBaseline || checkPolicy.BASELINE) }; }
        if (item.taskType === 'processing') item.results = item.results.map((result, index) => ({ ...result, inputResourceId: result.inputResourceId || payload.resourceIds?.[index] || null, source: result.source || payload.originalItems?.[index]?.source || item.source }));
        const index = state.history.findIndex((entry) => entry.id === item.id && entry.tenantId === item.tenantId);
        if (index < 0) state.history.unshift(item); else state.history[index] = item;
      };
      const inJobContext = (job, callback) => {
        const foreground = state.processing;
        const selected = state.selectedId;
        state.processing = job;
        callback();
        Object.assign(job, state.processing);
        if (job.done && state.copyGate.taskId === job.payload.taskId) state.copyGate = { active: false, tenantId: null, taskId: null };
        state.processing = foreground?.id === job.id ? job : foreground;
        if (foreground?.id !== job.id) state.selectedId = selected;
        persist(); render();
      };
      const scheduleJob = (job) => {
        if (job.done || jobTimers.has(job.id)) return;
        jobTimers.set(job.id, setTimeout(() => {
          jobTimers.delete(job.id);
          if (job.done) return;
          const generation = job.kind === 'generation';
          const steps = generation ? 3 : 5;
          if (job.kind === 'retry') job.step = 4;
          if (job.kind === 'auto-redo' && job.step < 2) job.step = 2;
          job.step += 1;
          if (job.step >= steps) {
            inJobContext(job, () => generation ? finalizeGenerationOnly(job.payload, job.scenario) : finalizeFlow(job.kind, job.payload, job.scenario));
            return;
          }
          job.progress = generation ? [8,48,86][job.step] : [8,22,40,67,88][job.step];
          job.message = generation ? ['','已接收生图请求，正在生成图片…','图片生成完成，正在准备结果…'][job.step] : ['','基础校验通过，正在执行预审…','预审通过，开始技术处理…','技术处理完成，开始结果检测…','检测结果已返回，正在准备交付…'][job.step];
          const status = generation ? 'GENERATING' : job.step < 2 ? 'PRE_REVIEW' : job.step < 4 ? 'FULL_PROCESSING' : 'DETECTION';
          job.batchItems = job.batchItems.map((entry) => ({ ...entry, status: entry.ok === false ? 'REJECTED' : status }));
          const item = state.history.find((entry) => entry.id === job.historyId && entry.tenantId === job.tenantId);
          if (item) { item.status = status; item.stage = job.message; }
          persist();
          if (state.processing?.id === job.id && !resourceDialog) render();
          scheduleJob(job);
        }, 700));
      };
      const startFlow = (kind, input = {}) => {
        if (isAccountBlocked()) { toast('账号已冻结，禁止新建任务；历史仍可查看', 'error'); return; }
        if (state.copyGate.active && !input.copyOf) { toast('复制任务执行期间，其他扣分和冻结暂缓', 'error'); return; }
        const generation = kind === 'generation';
        const taskType = generation ? 'generation' : 'processing';
        const retry = kind === 'retry' ? findOwnedHistory(input.retryOf) : null;
        if (kind === 'retry' && (!ownsHistory(retry) || retry.status !== 'TECH_FAILED' || Number(retry.retryCount || 0) >= 2 || state.jobs.some((job) => !job.done && job.historyId === retry.id))) { toast('该任务不存在或正在重试中', 'error'); return; }
        const scenario = { ...scenarioConfig(state.lastScenario) };
        const payload = { ...input, idempotencyKey: input.idempotencyKey || scenario.idempotencyKey || null, presetSnapshot: retry?.presetSnapshot || input.presetSnapshot, tenantId: retry?.tenantId || currentTenantId(), messageRecipient: retry?.messageRecipient || currentMessageRecipient(), taskType, taskId: retry?.id || uniqueId('CH'), runId: uniqueId('RUN'), autoSnapshot: retry?.autoSnapshot || checkPolicy.normalize({ ...state.auto, savedAt: state.auto.savedAt }), detectBaseline: retry?.detectBaseline || { ...checkPolicy.BASELINE }, resourceIds: [...(retry?.resourceIds || input.resourceIds || [])] };
        if (retry && retry.resourceIds?.some((id) => !state.resources.some((entry) => entry.id === id && entry.tenantId === retry.tenantId && !entry.deletedAt))) { toast('原图已删除，无法重试，请重新选择图片', 'error'); return; }
        if (!generation && !retry) {
          const resources = payload.resourceIds.map(resourceById).filter(Boolean);
          if (!resources.length || resources.length > 10 || resources.length !== payload.resourceIds.length) { toast('请选择1—10张可用图片资源', 'error'); return; }
          payload.items = resources.map((entry) => ({ name: entry.name, size: entry.size, type: entry.type, source: entry.source, resourceId: entry.id }));
          payload.originalItems = [...payload.items]; payload.quantity = resources.length;
          const sources = [...new Set(resources.map((entry) => entry.source))]; payload.source = sources.length === 1 ? sources[0] : 'mixed';
        } else payload.source = retry?.source || (input.mode === 'image' ? 'image' : 'text');
        if (payload.idempotencyKey && state.history.some((entry) => entry.tenantId === payload.tenantId && entry.idempotencyKey === payload.idempotencyKey && entry.taskType === taskType)) { toast('该请求已提交，请在任务详情中查看', 'error'); return; }
        const validation = generation ? Array.from({ length: payload.quantity }, (_, index) => ({ name: `生成结果-${index + 1}.jpg`, ok: true, errors: [] })) : validateMockInput({ ...payload, validationCase: payload.validationCase || scenario.validationCase || 'pass' });
        const preflightFailure = !generation && !retry && (scenario.preReview || validation.every((entry) => !entry.ok));
        if (!generation && validation.some((entry) => !entry.ok) && validation.some((entry) => entry.ok)) {
          payload.partialValidation = validation; payload.items = validation.filter((entry) => entry.ok); payload.quantity = payload.items.length;
        }
        if (payload.copyOf) state.copyGate = { active: true, tenantId: payload.tenantId, taskId: payload.taskId };
        let reservedCredits = 0;
        let billingLabel = generation ? '未冻结' : '未冻结';
        if (!retry && !payload.copyOf && !preflightFailure) {
          const qty = generation ? Number(payload.quantity || 0) : Number(payload.quantity || payload.resourceIds?.length || 0);
          try {
            const reserved = reserveTaskCredits(payload.taskId, qty, generation ? '生图预留' : '图片处理预留');
            reservedCredits = reserved.amount;
            billingLabel = reserved.billing;
            payload.reservedCredits = reservedCredits;
          } catch (error) {
            toast(error.message || '积分不足', 'error');
            if (payload.copyOf) state.copyGate = { active: false, tenantId: null, taskId: null };
            return;
          }
        }
        const job = { id: payload.runId, kind, tenantId: payload.tenantId, historyId: payload.taskId, payload, scenario, step: 0, progress: 8, message: generation ? '已提交，正在准备生图请求…' : retry ? '仅重试检测，图像保持不变…' : '已提交，正在校验图片…', done: false, batchItems: validation };
        state.jobs.unshift(job); state.processing = job;
        if (!retry) recordTask({ id: payload.taskId, title: payload.title || '图片处理任务', source: payload.source, tenantId: payload.tenantId, createdAt: demoNow, status: generation ? 'GENERATING' : 'PRE_REVIEW', score: null, threshold: null, rounds: [], billing: billingLabel, reservedCredits, chargeState: reservedCredits ? 'FROZEN' : 'NONE', preview: 'art-teal', stage: job.message, results: makeItemResults(payload.taskId, { ...payload, items: validation }, generation ? 'GENERATING' : 'PRE_REVIEW', null, '', validation.length), metadata: makeMetadata(payload), idempotencyKey: payload.idempotencyKey }, payload);
        if (preflightFailure) inJobContext(job, () => scenario.preReview ? finalizePreReview(kind, payload, scenario) : finalizeValidationFailure(kind, payload, scenario, validation));
        else { persist(); render(); scheduleJob(job); }
        if (!generation && !retry) { state.processResourceIds = []; state.resourceView.selectedIds = []; state.inputDraft = null; persist(); }
      };
      const finalizeValidationFailure = (kind, payload, scenario, validation) => { const id = payload.taskId; const previous = state.history.find((entry) => entry.id === id && entry.tenantId === payload.tenantId); const failed = validation.filter((entry) => !entry.ok); const reason = failed.flatMap((entry) => entry.errors).join('；') || '逐张校验完成。'; const source = payload.source || (payload.mode === 'image' ? 'image' : 'text'); const results = validation.map((entry, index) => ({ id: `${id}-IMG-${String(index + 1).padStart(2, '0')}`, name: entry.name, status: entry.ok ? 'PRE_REVIEW' : 'REJECTED', score: null, reason: entry.ok ? '基础校验通过；因同批其他图片失败，未进入后续处理。' : entry.errors.join('；'), resultAvailable: false, downloadable: false, attempts: 1 })); const billing = settleTaskCredits(id, previous?.reservedCredits || payload.reservedCredits || 0, 0, '输入校验释放'); const item = { id, title: payload.title || '输入校验失败 · 任务', source, createdAt: demoNow, status: 'REJECTED', score: null, threshold: null, rounds: [], billing, reservedCredits: 0, chargeState: 'RELEASED', preview: 'art-amber', stage: '输入校验失败', results, metadata: makeMetadata(payload), tenantId: payload.tenantId, retentionUntil: '2026-11-01 23:59' }; recordTask(item, payload); state.selectedId = id; state.processing = { ...state.processing, step: 2, progress: 40, done: true, outcome: 'REJECTED', historyId: id, resultTitle: '输入校验未通过 · 已释放预留', resultBody: reason }; persist(); render(); toast('已保留逐张校验结果'); };
      const finalizePreReview = (kind, payload, scenario) => { const id = payload.taskId; const previous = state.history.find((entry) => entry.id === id && entry.tenantId === payload.tenantId); let status = 'PRE_REVIEW_FAILED'; let note = scenario.message; if (scenario.forceFreeze) { for (let i = 1; i <= 3; i += 1) recordPreReviewFailure(`${scenario.imageKey}${i}`, payload.messageRecipient); status = 'REJECTED'; } else { const key = scenario.imageKey || 'demo-review-image.jpg'; if (scenario.forceLock) { recordPreReviewFailure(key, payload.messageRecipient); recordPreReviewFailure(key, payload.messageRecipient); } else { recordPreReviewFailure(key, payload.messageRecipient); } const result = { locked: !!state.account.imageLocks[key] }; status = result.locked ? 'IMAGE_LOCKED' : 'PRE_REVIEW_FAILED'; if (result.locked) note = '同一图片第二次失败，已锁定该图片。'; } const source = payload.source || (payload.mode === 'image' ? 'image' : 'text'); const billing = settleTaskCredits(id, previous?.reservedCredits || payload.reservedCredits || 0, 0, '预审释放'); const item = { id, title: payload.title || '预审事件 · 图片', source, createdAt: demoNow, status, score: null, threshold: null, rounds: [], billing, reservedCredits: 0, chargeState: 'RELEASED', preview: 'art-coral', stage: status === 'IMAGE_LOCKED' ? '图片已锁定' : state.account.status === 'FROZEN' ? '账号已冻结' : '预审未通过', results: makeItemResults(id, payload, status, null, note, payload.quantity || 1), metadata: makeMetadata(payload), tenantId: payload.tenantId, retentionUntil: '2026-11-01 23:59' }; recordTask(item, payload); state.selectedId = id; state.processing = { ...state.processing, step: 2, progress: 40, done: true, outcome: status, historyId: id, resultTitle: scenario.resultTitle, resultBody: state.account.status === 'FROZEN' ? '账号冻结工单已生成；历史仍可查看。' : note }; persist(); render(); toast(state.account.status === 'FROZEN' ? '账号已冻结并生成客服工单' : '预审失败已写入历史'); };
      const finalizeFlow = (kind, payload, scenario) => {
        const previous = state.history.find((entry) => entry.id === payload.taskId && entry.tenantId === payload.tenantId);
        if (previous?.completedRunIds?.includes(payload.runId)) return;
        const extraUsed = previous?.rounds?.length || 0;
        const fixtureKey = payload.geminiKey || scenario.geminiKey || 'pass';
        const report = checkPolicy.fixture(fixtureKey);
        const quality = !scenario.qualityFailed;
        const decision = checkPolicy.decide({ report, settings: payload.autoSnapshot, used: extraUsed, quality });
        const passed = checkPolicy.passedGate(report);
        const status = !quality ? 'QUALITY_FAILED' : !checkPolicy.validReport(report) ? 'TECH_FAILED' : decision.eligible ? 'AUTO_REPROCESS_PENDING' : passed ? 'DELIVERED' : 'FAILED';
        const score = Number.isFinite(report.total) ? report.total : null;
        const threshold = payload.autoSnapshot?.threshold;
        let results = makePartialResults(payload.taskId, payload, status, score, `${scenario.message || ''} ${decision.reason}`);
        if (kind === 'retry') results = previous.results.map((result) => result.status === 'REJECTED' ? result : { ...result, status, score, reason: decision.reason, attempts: Number(result.attempts || 1) + 1 });
        results = results.map((result) => result.status === 'REJECTED' ? result : { ...result, report: { ...report }, autoDecision: { ...decision }, downloadable: quality && checkPolicy.validReport(report), resultAvailable: quality && checkPolicy.validReport(report), qualityStatus: quality ? 'ok' : 'failed' });
        const isRetry = kind === 'retry';
        const continueRedo = decision.eligible && !isRetry;
        const consumedUnits = isRetry || continueRedo ? 0 : billableResultCount(results, status);
        const billing = isRetry ? (previous?.billing || '重试检测 · 不另计费') : continueRedo ? (previous?.billing || '冻结中 · 自动重做') : settleTaskCredits(payload.taskId, Number(previous?.reservedCredits || payload.reservedCredits || 0), consumedUnits * CREDIT_PER_IMAGE, '图片处理结算');
        const roundNo = isRetry ? (previous?.rounds?.length || 1) : (previous?.rounds?.length || 0) + 1;
        const round = { roundNo, status, trigger: isRetry ? '仅重试检测，不重新处理图片' : kind === 'auto-redo' ? `自动重做第 ${extraUsed + 1} 次` : (decision.eligible ? '低于阈值，进入自动重做' : (passed ? '首轮通过' : '未通过且不再追加')), score, report, autoDecision: decision, billing, layers: layerLabels.map((label) => ({ label, status: quality ? 'done' : 'failed' })), input: kind === 'auto-redo' ? '上一轮已处理结果' : '原图及设备预设快照', output: passed ? 'sRGB JPEG' : (quality ? '可预览结果' : '质量失败诊断件') };
        const rounds = isRetry ? (previous?.rounds || [round]) : [...(previous?.rounds || []), round];
        if (isRetry && rounds.length) rounds[rounds.length - 1] = { ...rounds[rounds.length - 1], status, score, report, autoDecision: decision, billing };
        const extraRounds = kind === 'auto-redo' ? extraUsed + 1 : extraUsed;
        const item = { ...previous, id: payload.taskId, title: payload.title || '图片处理任务', source: payload.source, createdAt: previous?.createdAt || demoNow, status, score, threshold, report, autoDecision: decision, extraRounds, rounds, billing, chargeState: isRetry || continueRedo ? (previous?.chargeState || 'FROZEN') : (consumedUnits ? 'CONSUMED' : (previous?.reservedCredits || payload.reservedCredits ? 'RELEASED' : 'NONE')), reservedCredits: continueRedo ? Number(previous?.reservedCredits || payload.reservedCredits || 0) : 0, consumedCredits: isRetry || continueRedo ? Number(previous?.consumedCredits || 0) : consumedUnits * CREDIT_PER_IMAGE, stage: statusLabels[status], results, metadata: previous?.metadata || makeMetadata(payload), tenantId: payload.tenantId, retryCount: isRetry ? Number(previous.retryCount || 0) + 1 : Number(previous?.retryCount || 0), retentionUntil:'2026-11-01 23:59', copiedFrom:payload.copyOf || previous?.copiedFrom || null, reprocessOf:payload.reprocessOf || previous?.reprocessOf || null, idempotencyKey:payload.idempotencyKey || null, completedRunIds:[...(previous?.completedRunIds || []), payload.runId], detectBaseline: payload.detectBaseline || previous?.detectBaseline || { ...checkPolicy.BASELINE }, autoSnapshot: payload.autoSnapshot || previous?.autoSnapshot };
        item.detectionAttempts = [...(previous?.detectionAttempts || []), { report, decision, runId: payload.runId }];
        recordTask(item, payload); state.selectedId = item.id;
        if (payload.copyOf) state.copyGate = { active:false, tenantId:null, taskId:null };
        const title = statusLabels[status];
        notifyAccount({ id:uniqueId('MSG'), type:status === 'DELIVERED' ? 'success' : 'warn', title, body:`${decision.reason} ${billing}`, time:'刚刚', read:false }, payload.messageRecipient);
        state.processing = { ...state.processing, step:5, progress:100, done:true, outcome:status, historyId:item.id, resultTitle:title, resultBody:`${decision.reason} ${billing}（每张成功 ${CREDIT_PER_IMAGE} 积分）。` };
        persist(); render();
        toast(`${title} · ${billing}`);
        if (continueRedo) {
          const nextRunId = uniqueId('RUN');
          const nextPayload = { ...payload, runId: nextRunId, geminiKey: scenario.nextKey || 'pass', reservedCredits: 0 };
          const nextJob = { id: nextRunId, kind: 'auto-redo', tenantId: payload.tenantId, historyId: payload.taskId, payload: nextPayload, scenario, step: 2, progress: 40, message: '自动重做：沿用上一轮结果，重跑五层与检测…', done: false, batchItems: item.results || [] };
          state.jobs.unshift(nextJob);
          if (state.processing?.historyId === item.id) state.processing = nextJob;
          persist();
          scheduleJob(nextJob);
        }
      };
      const handleSubmit = (form) => { const data = new FormData(form); const type = form.dataset.form;
        if (['batch','process-resources'].includes(type) && isAccountBlocked()) { toast('账号已冻结，禁止新建任务；历史仍可查看', 'error'); return; }
        if (type === 'batch') {
          if (state.promptOptimization.active && !state.promptOptimization.confirmed) { toast('请先确认提示词优化版本，或清除优化状态后再生成', 'error'); return; }
          const mode = state.batchMode; const copy = state.batchDraft || {};
          if (mode === 'image' && !copy.reference) { toast('请先选择或上传参考图', 'error'); return; }
          const quantity = Number(data.get('quantity'));
          if (!Number.isInteger(quantity) || quantity < 1 || quantity > 10) { toast('生图数量须为1—10张', 'error'); return; }
          if (copy.reference?.resourceId && !resourceById(copy.reference.resourceId)) { toast('参考图已删除，请重新选择', 'error'); return; }
          const payload = { mode, title: `${mode === 'text' ? '文生图' : '图生图'} · ${data.get('quantity')} 张`, quantity, reference: copy.reference || null, prompt: String(data.get('prompt') || ''), negative: String(data.get('negative') || ''), size: String(data.get('size') || ''), seed: String(data.get('seed') || ''), copyOf: copy.copyOf || null, reprocessOf: copy.reprocessOf || null, idempotencyKey: state.lastScenario === 'duplicate' ? 'DEMO-DUPLICATE-CHAIN' : null };
          if (state.promptOptimization.active) payload.prompt = state.promptOptimization.optimized;
          resourceDialog = null; state.batchDraft = null; startFlow('generation', payload);
        } else if (type === 'process-resources') {
          const preset = directSelectedPreset();
          if (!preset || preset.status !== '启用') { toast('请选择启用的设备预设', 'error'); return; }
          state.uploadValidationCase = String(data.get('validationCase') || 'pass');
          const draft = state.inputDraft || {};
          startFlow('processing', { title: `图片处理 · ${state.processResourceIds.length}张`, resourceIds: [...state.processResourceIds], preset: preset.name, presetSnapshot: JSON.parse(JSON.stringify(preset)), validationCase: state.uploadValidationCase, copyOf: draft.copyOf || null, reprocessOf: draft.reprocessOf || null });
        } else if (type === 'resource-upload' || type === 'resource-import') {
          if (isAccountBlocked()) { toast('账号已冻结，暂不能添加图片', 'error'); return; }
          let items;
          const source = type === 'resource-upload' ? 'upload' : 'import';
          if (source === 'upload') {
            items = (resourceDialog?.files || []).map((file, index) => ({ ...file, sku: file.sku || `SKU-UP-${String(index + 1).padStart(2, '0')}`, url: file.url || `file://${file.name}` }));
          } else {
            let parsed;
            try {
              const text = String(data.get('urls') || '').trim();
              parsed = text ? parseImportPayload(text, null) : parseImportPayload('', resourceDialog?.jsonItems || null);
            } catch (error) {
              toast(error.message || '导入内容解析失败', 'error');
              return;
            }
            if (!parsed.length) { toast('请填写 URL、粘贴 JSON，或上传 JSON 文件', 'error'); return; }
            if (parsed.length > 100) { toast('每次最多导入 100 条', 'error'); return; }
            if (parsed.some((entry) => { try { return !['http:','https:'].includes(new URL(entry.url).protocol); } catch (_) { return true; } })) {
              toast('请填写有效的 HTTP/HTTPS 地址（JSON 的 url 字段或每行一个 URL）', 'error');
              return;
            }
            items = parsed.map((entry) => ({
              ...entry,
              website: entry.website || (() => { try { return new URL(entry.url).hostname; } catch (_) { return ''; } })()
            }));
          }
          if (!items.length || items.length > (source === 'import' ? 100 : 20)) { toast(source === 'import' ? '每次请导入 1—100 条' : '每次请选择或填写1—20张图片', 'error'); return; }
          const added = addResources(items, source);
          state.resourceView.source = 'all'; state.resourceView.page = 1; resourceDialog = null;
          persist(); render(); toast(source === 'import' ? `已导入 ${added.length} 条；落盘命名按 sku${added.some((entry) => entry.asn) ? '/asn' : ''}，列表文件名为字段拼接` : `已添加${items.length}张图片，等待勾选处理`);
        } else if (type === 'settings') {
          const threshold = Number(data.get('threshold'));
          const maxCount = Number(data.get('maxCount'));
          if (!Number.isInteger(threshold) || threshold < 0 || threshold > 100) { toast('阈值须为 0—100 的整数', 'error'); return; }
          if (!Number.isInteger(maxCount) || maxCount < 1 || maxCount > 5) { toast('追加次数须为 1—5', 'error'); return; }
          state.auto = checkPolicy.normalize({ enabled: state.auto.enabled === true, threshold, maxCount, savedAt: demoNow });
          persist(); render(); toast('自动重做设置已保存');
        } else if (type === 'model-key') {
          if (!canManageSystem()) { toast('当前账号无权管理模型 API Key', 'error'); return; }
          const purpose = String(data.get('purpose') || modelKeyFormState().purpose);
          if (!modelPurposes.includes(purpose)) { toast('请选择有效用途', 'error'); return; }
          const rawKeys = [];
          for (let index = 0; index < MODEL_KEY_SLOT_MAX; index += 1) {
            rawKeys.push(String(data.get(`key_${index}`) || ''));
          }
          const filled = rawKeys.map((value) => value.trim()).filter(Boolean);
          if (!String(rawKeys[0] || '').trim()) { toast('请填写 API Key', 'error'); return; }
          const apiKeys = filled.map((raw, weight) => ({ raw, masked: maskApiKey(raw), weight }));
          const provider = String(data.get('provider') || '未命名渠道');
          const model = String(data.get('model') || '');
          const baseUrl = String(data.get('base_url') || '').trim();
          const existing = modelKeyRecordForPurpose(purpose);
          if (existing) {
            existing.provider = provider;
            existing.model = model;
            existing.baseUrl = baseUrl;
            existing.apiKeys = apiKeys;
            existing.masked = apiKeys[0].masked;
            existing.pollIndex = 0;
            existing.updatedAt = demoNow;
          } else {
            state.system.modelKeys.unshift({ id: `KEY-${String(state.system.modelKeys.length + 1).padStart(3, '0')}`, provider, model, purpose, baseUrl, apiKeys, masked: apiKeys[0].masked, scope: '平台', status: '已启用', pollIndex: 0, updatedAt: demoNow });
          }
          const drafts = state.system.modelKeyDrafts || (state.system.modelKeyDrafts = {});
          drafts[purpose] = { provider, model, baseUrl, keys: filled };
          modelKeyFormState().purpose = purpose;
          state.system.audit.unshift({ time: demoNow, actor: role().label, scope: 'PLATFORM', action: `保存 ${purpose} API（${apiKeys.length} Key）`, result: '允许' });
          persist(); render(); toast(`${purpose} 已保存`); } else if (type === 'device-preset-full') {
          if (!canManageSystem()) { toast('当前账号无权管理公共设备预设', 'error'); return; }
          const editId = String(form.dataset.editId || 'new');
          const raw = {};
          const numericFields = new Set(Object.values(presetFieldGroups).flat().filter((field) => field.type === 'number').map((field) => field.name));
          presetFieldNames.forEach((name) => {
            if (name === 'is_public') raw[name] = data.get(name) ? 1 : 0;
            else {
              const value = String(data.get(name) ?? '').trim();
              raw[name] = numericFields.has(name) && value !== '' ? Number(value) : value;
            }
          });
          if (!raw.name) { toast('请填写预设名称', 'error'); return; }
          const categoryLabel = presetCategoryLabels[raw.category] || raw.category || '待分类';
          if (editId === 'new') {
            const newId = 'PRESET-' + String(state.system.devicePresets.length + 1).padStart(3, '0');
            state.system.devicePresets.unshift({ id: newId, name: raw.name, category: categoryLabel, familyLabel: categoryLabel, camera: [raw.camera_make, raw.camera_model].filter(Boolean).join(' '), lens: [raw.lens_make, raw.lens_model].filter(Boolean).join(' '), iso: raw.iso, shutter: raw.shutter_speed, aperture: raw.aperture ? 'f/' + raw.aperture : '', ev: raw.ev_value, gpsPolicy: raw.gps_mode, visibility: raw.is_public ? '公共' : '平台私有', sourceVisibility: 'PLATFORM', sourceActivationStatus: 'PLATFORM_CREATED', activationStatus: 'ACTIVATED', status: '启用', version: 'v1.0', versionHistory: [], parameterJson: { ...raw, category: raw.category } });
            state.system.audit.unshift({ time: demoNow, actor: role().label, scope: 'PLATFORM', action: '新增设备预设 ' + raw.name, result: '允许' });
          } else {
            const target = state.system.devicePresets.find((item) => String(item.id) === editId);
            if (!target) { toast('设备预设不存在', 'error'); return; }
            target.versionHistory = [...(target.versionHistory || []), { version: target.version || 'legacy', savedAt: demoNow, snapshot: JSON.parse(JSON.stringify(target.parameterJson || {})) }];
            target.parameterJson = { ...(target.parameterJson || {}), ...raw, category: raw.category };
            target.name = raw.name; target.category = categoryLabel; target.familyLabel = categoryLabel; target.camera = [raw.camera_make, raw.camera_model].filter(Boolean).join(' '); target.lens = [raw.lens_make, raw.lens_model].filter(Boolean).join(' '); target.iso = raw.iso; target.shutter = raw.shutter_speed; target.aperture = raw.aperture ? 'f/' + raw.aperture : ''; target.ev = raw.ev_value; target.gpsPolicy = raw.gps_mode; target.version = 'v' + (target.versionHistory.length + 1) + '.0';
            state.system.audit.unshift({ time: demoNow, actor: role().label, scope: 'PLATFORM', action: '编辑设备预设 ' + raw.name, result: '允许' });
          }
          state.system.devicePresetView.editorId = null; state.system.devicePresetView.detailId = null; persist(); render(); toast(editId === 'new' ? '设备预设已新增（已保存）' : '设备预设已保存，已生成版本快照');
       } else if (type === 'device-preset') {
          if (!canManageSystem()) { toast('当前账号无权管理公共设备预设', 'error'); return; }
          const name = String(data.get('name') || '').trim();
          if (!name) { toast('请填写预设名称', 'error'); return; }
          state.system.devicePresets.unshift({ id: `PRESET-${String(state.system.devicePresets.length + 1).padStart(3, '0')}`, name, category: String(data.get('category') || ''), camera: String(data.get('camera') || ''), lens: String(data.get('lens') || ''), iso: Number(data.get('iso')) || 100, shutter: String(data.get('shutter') || ''), aperture: String(data.get('aperture') || ''), ev: Number(data.get('ev')) || 0, gpsPolicy: String(data.get('gpsPolicy') || '可选'), visibility: '公共', status: '启用', version: 'v1.0' });
          state.system.audit.unshift({ time: demoNow, actor: role().label, scope: 'PLATFORM', action: `新增设备预设 ${name}`, result: '允许' });
          persist(); render(); toast('设备预设已新增（已保存）'); } else if (type === 'prompt-template') {
          const editId = String(form.dataset.editId || 'new');
          const name = String(data.get('name') || '').trim();
          const prompt = String(data.get('prompt') || '').trim();
          const negative = String(data.get('negative') || '').trim();
          const mode = String(data.get('mode') || 'text');
          const scope = state.role === 'admin' ? String(data.get('scope') || 'platform') : 'tenant';
          if (!name || !prompt) { toast('请填写模板名称和正向提示词', 'error'); return; }
          if (editId === 'new') {
            state.promptTemplates.unshift({ id: uniqueId('PT'), name, prompt, negative, mode, scope, ownerId: role().userId, tenantId: scope === 'platform' ? 'PLATFORM' : currentTenantId(), updatedAt: demoNow });
          } else {
            const item = state.promptTemplates.find((entry) => entry.id === editId);
            if (!item || !canEditPromptTemplate(item)) { toast('无权编辑该模板', 'error'); return; }
            Object.assign(item, { name, prompt, negative, mode, scope: state.role === 'admin' ? scope : item.scope, updatedAt: demoNow });
          }
          state.promptTemplateEditor = null; persist(); render(); toast('提示词模板已保存');
        } else if (type === 'recharge') { const amount = Math.max(1, Math.round(Number(data.get('amount')) || 0)); const orderId = String(data.get('note') || `DEMO-TOPUP-${Date.now()}`); const ticket = { id: `TK-${20 + state.tickets.length}`, kind: '充值确认', ...currentMessageRecipient(), tenant: `${role().label} · ${currentTenantId()}`, ref: orderId, status: '待确认', owner: '订单客服', createdAt: demoNow, note: `待确认到账 ${amount} 积分`, amount, idempotencyKey: orderId }; state.tickets.unshift(ticket); state.transactions.unshift({ time: demoNow, type: '充值订单提交', ref: orderId, amount: 0, status: `待客服确认 · ${amount} 积分`, orderId, idempotencyKey: orderId }); notifyAccount({ id: `MSG-${30 + state.transactions.length}`, type: 'warn', title: '充值订单已提交', body: `订单 ${orderId} 待客服确认，预计到账 ${amount} 积分。`, time: '刚刚', read: false }); persist(); render(); toast('充值订单已提交，等待客服确认'); } };
      const handleTicketReview = (form) => {
        if (!(state.role === 'support' || state.role === 'admin')) { toast('当前账号无权处理工单', 'error'); return; }
        const data = new FormData(form);
        const ticket = state.tickets.find((item) => item.id === String(data.get('ticketId') || ''));
        if (!ticket) { toast('工单不存在', 'error'); return; }
        const decision = String(data.get('decision') || 'close');
        ticket.reviewNote = String(data.get('note') || '').trim() || '按固定证据完成复核。';
        ticket.reviewedBy = role().label; ticket.reviewedAt = demoNow;
        if (ticket.kind === '账号冻结') {
          if (decision === 'unfreeze') { ticket.status = '已解冻'; state.account.status = 'ACTIVE'; state.account.freezeEvent = null; state.account.distinctFailures = []; notifyAccount({ id: 'MSG-' + (60 + state.messages.length), type: 'success', title: '账号冻结工单已解冻', body: ticket.ref + ' 已完成人工复核，账号恢复新建任务权限。', time: '刚刚', read: false }, ticketMessageRecipient(ticket)); }
          else { ticket.status = '维持冻结'; state.account.status = 'FROZEN'; notifyAccount({ id: 'MSG-' + (60 + state.messages.length), type: 'danger', title: '账号继续冻结', body: ticket.ref + ' 复核后维持冻结状态。', time: '刚刚', read: false }, ticketMessageRecipient(ticket)); }
        } else if (ticket.kind === '充值确认' && decision === 'confirm') {
          const duplicate = state.transactions.some((tx) => tx.type === '人工充值' && tx.idempotencyKey === ticket.idempotencyKey);
          if (!duplicate) { state.credits.available += Math.round(ticket.amount || 0); state.transactions.unshift({ time: demoNow, type: '人工充值', ref: ticket.ref, amount: Math.round(ticket.amount || 0), status: '客服已确认 · 幂等完成', idempotencyKey: ticket.idempotencyKey }); }
          ticket.status = '已完成';
        } else if (decision === 'release') { ticket.status = '已完成'; state.credits.available += state.credits.frozen; state.credits.frozen = 0; }
        else { ticket.status = '已完成'; }
        state.system.audit.unshift({ time: demoNow, actor: role().label, scope: role().scope, action: ticket.kind + ' ' + ticket.ref + ' · ' + decision, result: '允许' });
        state.ticketViewId = ticket.id; persist(); render(); toast('工单处理结果已保存（已保存）');
      };
      document.addEventListener('click', (event) => {
        const el = event.target.closest('[data-page],[data-action],[data-system-tab],[data-device-tab],[data-preset-form-tab],[data-scenario],[data-history-source],[data-history-id],[data-role-card]'); if (!el) return;
        if (el.dataset.page) { navigate(el.dataset.page); return; }
        if (el.dataset.systemTab) { if (!canManageSystem() && el.dataset.systemTab !== 'auto') { toast('当前账号无权访问该系统管理', 'error'); return; } state.system.activeTab = el.dataset.systemTab; persist(); render(); return; }
        if (el.dataset.deviceTab) { if (!canManageSystem() && el.dataset.deviceTab === 'presets') { toast('设备预设由平台管理员维护', 'error'); return; } state.system.devicePresetView.activeTab = el.dataset.deviceTab; state.system.devicePresetView.editorId = null; persist(); render(); return; }
         if (el.dataset.presetFormTab) {
          const tab = el.dataset.presetFormTab === 'image' ? 'shooting' : el.dataset.presetFormTab;
          state.system.devicePresetView.formTab = tab;
          const modal = el.closest('.modal') || document;
          modal.querySelectorAll('[data-preset-form-tab]').forEach((btn) => btn.classList.toggle('active', btn.dataset.presetFormTab === tab));
          modal.querySelectorAll('[data-preset-form-section]').forEach((sec) => { sec.style.display = sec.dataset.presetFormSection === tab ? '' : 'none'; });
          persist();
          return;
        }
        if (el.dataset.scenario) { selectScenario(el.dataset.scenario); return; }
        if (el.dataset.historySource) { state.historyFilter.source = el.dataset.historySource; state.historyView.page = 1; persist(); render(); return; }
        if (el.dataset.historyId) { const item = findOwnedHistory(el.dataset.historyId); if (!item) { toast('无权查看其他账号的任务', 'error'); return; } state.selectedId = item.id; state.page = 'detail'; persist(); render(); return; }
        if (el.dataset.roleCard) { const select = document.getElementById('login-role'); if (select) select.value = el.dataset.roleCard; return; }
        const action = el.dataset.action;
        if (handleResourceAction(el)) return;
        if (action === 'view-result-detail') { resultDialog = { historyId: el.dataset.id, resultId: el.dataset.resultId }; renderResultOverlay(); document.querySelector('.result-detail-modal .modal-close')?.focus(); return; }
        if (action === 'close-result-detail') { closeResultDetail(); return; }
        if (action === 'login') { const select = document.getElementById('login-role'); state.role = select?.value || 'merchant'; state.session = true; state.page = 'dashboard'; location.hash = 'dashboard'; persist(); render(); toast(`已进入${role().label}工作台`); }
        else if (action === 'logout') navigate('login');
        else if (action === 'history-page-prev' || action === 'history-page-next') { state.historyView.page = Math.max(1, Number(state.historyView.page || 1) + (action === 'history-page-next' ? 1 : -1)); persist(); render(); }
        else if (action === 'credits-page-prev' || action === 'credits-page-next') { state.creditsView.page = Math.max(1, Number(state.creditsView.page || 1) + (action === 'credits-page-next' ? 1 : -1)); persist(); render(); }
        else if (action === 'tickets-page-prev' || action === 'tickets-page-next') { state.supportView.ticketPage = Math.max(1, Number(state.supportView.ticketPage || 1) + (action === 'tickets-page-next' ? 1 : -1)); persist(); render(); }
        else if (action === 'view-history') { const item = findOwnedHistory(el.dataset.id); if (!item) { toast('无权查看其他账号的任务', 'error'); return; } state.selectedId = item.id; state.page = 'detail'; persist(); render(); }
        else if (action === 'create-prompt-template') { state.promptTemplateEditor = { id: 'new' }; persist(); render(); }
        else if (action === 'edit-prompt-template') { const item = state.promptTemplates.find((entry) => entry.id === el.dataset.id); if (!item || !canEditPromptTemplate(item)) { toast('无权编辑该模板', 'error'); return; } state.promptTemplateEditor = { id: item.id }; persist(); render(); }
        else if (action === 'close-prompt-template-editor') { state.promptTemplateEditor = null; persist(); render(); }
        else if (action === 'delete-prompt-template') { const item = state.promptTemplates.find((entry) => entry.id === el.dataset.id); if (!item || !canEditPromptTemplate(item)) { toast('无权删除该模板', 'error'); return; } if (item.scope === 'platform' && state.role !== 'admin') { toast('平台模板不可删除', 'error'); return; } state.promptTemplates = state.promptTemplates.filter((entry) => entry.id !== item.id); persist(); render(); toast('模板已删除'); }
        else if (action === 'use-prompt-template') {
          const item = state.promptTemplates.find((entry) => entry.id === el.dataset.id);
          if (!item) return;
          state.batchMode = item.mode === 'image' ? 'image' : 'text';
          state.batchDraft = { ...(state.batchDraft || {}), templateId: item.id, prompt: item.prompt, negative: item.negative || '' };
          state.promptOptimization = { active: false, original: '', optimized: '', confirmed: false, status: 'idle', charged: 0 };
          navigate('resources');
          resourceDialog = { kind: 'add', mode: state.batchMode, files: [] };
          persist(); render();
          toast(`已选用模板「${item.name}」，可继续提交生图`);
        }
        else if (action === 'prompt-templates-page-prev' || action === 'prompt-templates-page-next') { state.promptTemplateView = state.promptTemplateView || { page: 1, pageSize: 10 }; state.promptTemplateView.page = Math.max(1, Number(state.promptTemplateView.page || 1) + (action === 'prompt-templates-page-next' ? 1 : -1)); persist(); render(); }
        else if (action === 'logs-page-prev' || action === 'logs-page-next') { if (!canManageUsers()) return; state.system.logView.page = Math.max(1, Number(state.system.logView.page || 1) + (action === 'logs-page-next' ? 1 : -1)); persist(); render(); }
        else if (action === 'open-user-dialog') { if (!canManageUsers()) { toast('当前账号无权管理用户', 'error'); return; } userDialog = { kind: el.dataset.kind, id: el.dataset.id, tenantId: el.dataset.tenantId }; render(); document.querySelector('form[data-form="user-action"] input:not([type=hidden]), form[data-form="user-action"] select')?.focus(); }
        else if (action === 'close-user-dialog') { userDialog = null; render(); }
        else if (action === 'users-page-prev' || action === 'users-page-next') { if (!canManageUsers()) return; state.system.userView.page = Math.max(1, Number(state.system.userView.page || 1) + (action === 'users-page-next' ? 1 : -1)); persist(); render(); }
        else if (action === 'toggle-direct-preview') { state.directPresetPreviewOpen = !state.directPresetPreviewOpen; persist(); render(); }
        else if (action === 'switch-role') { userDialog = null; resourceDialog = null; state.processing = null; state.processResourceIds = []; state.resourceView.selectedIds = []; const keys = Object.keys(roleMeta); state.role = keys[(keys.indexOf(state.role) + 1) % keys.length]; persist(); render(); toast(`已切换为${role().label}`); }
        else if (action === 'toggle-auto') { state.auto.enabled = !state.auto.enabled; persist(); render(); toast(state.auto.enabled ? '已开启自动重做' : '已关闭自动重做'); }
         else if (action === 'optimize-prompt') { const input = document.querySelector('[data-form="batch"] textarea[name="prompt"]'); const original = String(input?.value || '').trim(); if (!original) { toast('请先填写原始提示词', 'error'); return; } if (state.credits.available < 1) { toast('积分不足，无法调用提示词优化', 'error'); return; } captureResourceForm(); adjustTaskCredits(-1); state.promptOptimization = { active: true, original, optimized: `${original}；补充材质层次、自然光方向和电商构图约束`, confirmed: false, status: 'success', charged: 1 }; state.transactions.unshift({ time: demoNow, type: '提示词优化', ref: `PROMPT-${state.history.length + 1}`, amount: -1, status: '已完成 · 成功 1 积分' }); persist(); render(); toast('优化成功，已扣除 1 积分；请确认版本'); }
        else if (action === 'confirm-prompt') { if (state.promptOptimization.active) { state.promptOptimization.confirmed = true; persist(); render(); toast('已确认采用优化提示词'); } }
        else if (action === 'toggle-model-key') { if (!canManageSystem()) { toast('无权修改模型渠道', 'error'); return; } const item = state.system.modelKeys.find((x) => x.id === el.dataset.id); if (item) { item.status = item.status === '已启用' ? '已停用' : '已启用'; state.system.audit.unshift({ time: demoNow, actor: role().label, scope: 'PLATFORM', action: `${item.status === '已启用' ? '启用' : '停用'} ${item.provider} API Key`, result: '允许' }); persist(); render(); toast('模型渠道状态已更新'); } }
        else if (action === 'model-key-add') {
          const form = el.closest('form[data-form="model-key"]');
          captureModelKeyForm(form);
          const purpose = modelKeyFormState().purpose;
          const draft = draftForModelPurpose(purpose);
          if (draft.keys.length >= MODEL_KEY_SLOT_MAX) return;
          draft.keys.push('');
          persist(); render();
          return;
        }
        else if (action === 'delete-model-key') { if (!canManageSystem()) { toast('无权删除模型渠道', 'error'); return; } const item = state.system.modelKeys.find((x) => x.id === el.dataset.id); if (item?.purpose && state.system.modelKeyDrafts) delete state.system.modelKeyDrafts[item.purpose]; state.system.modelKeys = state.system.modelKeys.filter((x) => x.id !== el.dataset.id); state.system.audit.unshift({ time: demoNow, actor: role().label, scope: 'PLATFORM', action: `删除 ${item?.provider || '模型'} API Key`, result: '允许' }); persist(); render(); toast('模型渠道已删除'); }

         else if (action === 'view-ticket') { state.ticketViewId = el.dataset.id; persist(); render(); }
         else if (action === 'close-ticket-modal') { state.ticketViewId = null; persist(); render(); }
        else if (action === 'continue-generated') { state.processing = null; state.resourceView.source = 'all'; state.resourceView.page = 1; navigate('resources'); }
        else if (action === 'view-preset') { if (!canManageSystem()) { toast('无权查看平台设备预设详情', 'error'); return; } state.system.devicePresetView.detailId = el.dataset.id; persist(); render(); }
         else if (action === 'new-preset') { if (!canManageSystem()) { toast('无权新建设备预设', 'error'); return; } state.system.devicePresetView.activeTab = 'presets'; state.system.devicePresetView.editorId = 'new'; state.system.devicePresetView.formTab = 'basic'; persist(); render(); }
         else if (action === 'edit-preset') { if (!canManageSystem()) { toast('无权编辑设备预设', 'error'); return; } state.system.devicePresetView.activeTab = 'presets'; state.system.devicePresetView.editorId = el.dataset.id; state.system.devicePresetView.formTab = 'basic'; persist(); render(); }
         else if (action === 'preset-random') {
          const form = el.closest('form[data-form="device-preset-full"]');
          const kind = el.dataset.random;
          const input = form?.querySelector(kind === 'author' ? '[name="author"]' : '[name="copyright"]');
          if (!input) return;
          input.value = kind === 'author' ? randomEnglishAuthor() : randomCopyrightNotice();
          toast(kind === 'author' ? `已生成英文作者：${input.value}` : `已生成版权声明：${input.value}`);
          return;
        }
        else if (action === 'preset-aspect') {
          const form = el.closest('form[data-form="device-preset-full"]');
          const found = presetAspectRatios.find(([label]) => label === el.dataset.ratio);
          if (!form || !found) return;
          const [, rw, rh] = found;
          const widthInput = form.querySelector('[name="image_width"]');
          const heightInput = form.querySelector('[name="image_height"]');
          const base = Number(widthInput?.value) || 4032;
          if (widthInput) widthInput.value = String(base);
          if (heightInput) heightInput.value = String(Math.max(1, Math.round(base * rh / rw)));
          form.querySelectorAll('[data-action="preset-aspect"]').forEach((btn) => {
            const on = btn.dataset.ratio === el.dataset.ratio;
            btn.style.background = on ? 'rgba(26,168,154,.12)' : '';
            btn.style.borderColor = on ? 'var(--teal)' : '';
            btn.style.color = on ? 'var(--teal-deep)' : '';
          });
          toast(`已套用宽高比 ${el.dataset.ratio}`);
          return;
        }
        else if (action === 'close-preset-editor') { state.system.devicePresetView.editorId = null; persist(); render(); }
        else if (action === 'close-preset-detail') { state.system.devicePresetView.detailId = null; persist(); render(); }
        else if (action === 'device-page-prev' || action === 'device-page-next') { const view = state.system.devicePresetView; view.page = Math.max(1, Number(view.page || 1) + (action === 'device-page-next' ? 1 : -1)); view.detailId = null; persist(); render(); }
        else if (action === 'toggle-preset') { if (!canManageSystem()) { toast('无权管理公共设备预设', 'error'); return; } const preset = state.system.devicePresets.find((x) => x.id === el.dataset.id); if (preset) { preset.status = preset.status === '启用' ? '停用' : '启用'; preset.activationStatus = preset.status === '启用' ? 'ACTIVATED' : 'NOT_ACTIVATED'; state.system.audit.unshift({ time: demoNow, actor: role().label, scope: 'PLATFORM', action: `${preset.status === '启用' ? '启用' : '停用'}设备预设 ${preset.name}`, result: '允许' }); persist(); render(); toast('设备预设状态已更新'); } }
        else if (action === 'mark-messages-read') { visibleMessages().forEach((message) => { message.read = true; }); persist(); render(); toast('消息已全部标为已读'); }
        else if (action === 'retry-message') { const message = visibleMessages().find((m) => m.id === el.dataset.id); if (message) { message.read = true; message.time = '刚刚补发'; persist(); render(); toast('消息补发成功，不会重跑任务'); } }
        else if (action === 'resolve-ticket') { const ticket = state.tickets.find((x) => x.id === el.dataset.id); if (ticket) { if (ticket.kind === '充值确认') { const duplicate = state.transactions.some((tx) => tx.type === '人工充值' && tx.idempotencyKey === ticket.idempotencyKey); if (!duplicate) { state.credits.available += Math.round(ticket.amount || 0); state.transactions.unshift({ time: demoNow, type: '人工充值', ref: ticket.ref, amount: Math.round(ticket.amount || 0), status: '客服已确认 · 幂等完成', idempotencyKey: ticket.idempotencyKey }); } ticket.status = '已完成'; } else if (ticket.kind === '账号冻结') { ticket.status = '已完成'; state.account.status = 'ACTIVE'; state.account.freezeEvent = null; state.account.distinctFailures = []; notifyAccount({ id: `MSG-${50 + state.messages.length}`, type: 'success', title: '账号已解冻', body: '平台管理员/技术客服已完成冻结审核，允许新建任务。', time: '刚刚', read: false }, ticketMessageRecipient(ticket)); } else { ticket.status = '已完成'; const frozen = state.credits.frozen; state.credits.available += frozen; state.credits.frozen = 0; } state.system.audit.unshift({ time: demoNow, actor: role().label, scope: role().scope, action: `${ticket.kind} ${ticket.ref} 已处理`, result: '允许' }); persist(); render(); toast(`${ticket.id} 已完成，重复确认不会重复入账`); } }
        else if (action === 'download-generated' || action === 'download-result') { const item = findOwnedHistory(el.dataset.id || state.selectedId); const asset = historyResults(item).find((result) => result.id === el.dataset.resultId && result.downloadable); if (!asset) { toast('结果文件已过期/删除或不可下载', 'error'); return; } saveAssetToUserPath(asset).then((mode) => toast(mode === 'saved' ? `已保存 ${asset.name}` : `已触发 ${asset.name} 下载；浏览器将使用默认下载目录`)).catch((error) => { if (error?.name !== 'AbortError') toast('保存失败，请重试', 'error'); }); }
        else if (action === 'download-generated-batch' || action === 'download-result-batch') { const item = findOwnedHistory(el.dataset.id || state.selectedId); if (!canDownload(item)) { toast('结果文件已过期/删除或没有可下载图片', 'error'); return; } const selector = action === 'download-generated-batch' ? '[data-generated-select]:checked' : '[data-result-select]:checked'; const selections = [...document.querySelectorAll(selector.replace(':checked', ''))]; const selectedIds = selections.filter((input) => input.checked).map((input) => input.dataset.resultId); const assets = historyResults(item).filter((result) => result.downloadable && (!selections.length || selectedIds.includes(result.id))); if (!assets.length) { toast('请至少选择一张可下载图片', 'error'); return; } saveAssetsToUserDirectory(assets).then((mode) => toast(mode === 'directory' ? `已保存 ${assets.length} 张图片到所选目录` : `已触发 ${assets.length} 个图片下载；浏览器将使用默认下载目录`)).catch((error) => { if (error?.name !== 'AbortError') toast('批量保存失败，请重试', 'error'); }); }
        else if (action === 'delete-result' || action === 'expire-demo') { const item = findOwnedHistory(el.dataset.id); if (item) { resultDialog = null; item.status = action === 'delete-result' ? 'DELETED' : 'EXPIRED'; item.deletedAt = demoNow; item.results = (item.results || []).map((result) => ({ ...result, downloadable: false, resultAvailable: false })); item.stage = action === 'delete-result' ? '已主动删除' : '保留期已到期'; persist(); render(); toast(action === 'delete-result' ? '结果文件已删除，摘要仍可查' : '已标记到期，摘要仍可查'); } }
        else if (action === 'copy-task' || action === 'reprocess-task') {
          const item = findOwnedHistory(el.dataset.id);
          if (!item || item.taskType === 'generation' || ['EXPIRED','DELETED'].includes(item.status)) return;
          const copy = action === 'copy-task';
          const draft = { copyOf: copy ? item.id : null, reprocessOf: copy ? null : item.id };
          const ids = item.resourceIds || [];
          const resources = ids.map(resourceById).filter(Boolean);
          if (!resources.length || resources.length !== ids.length) { toast('原图已删除或不在当前租户资源范围，请重新选择图片', 'error'); return; }
          state.processResourceIds = resources.map((entry) => entry.id); state.inputDraft = draft;
          const preset = enabledDevicePresets().find((entry) => entry.name === item.metadata?.devicePreset);
          if (preset) { state.directPresetId = preset.id; state.directPresetType = directPresetType(preset); state.directPresetBrand = directPresetBrand(preset); state.directPresetModel = directPresetModel(preset); }
          state.directPresetPreviewOpen = false; navigate('direct');
          persist(); toast(copy ? '已复制为新草稿' : '已载入原图，请确认设备参数后提交');
        }
        else if (action === 'retry-tech') { const item = findOwnedHistory(el.dataset.id); if (!item || item.status !== 'TECH_FAILED') return; const used = Number(item.retryCount || 0); if (used >= 2) { toast('已达到检测重试上限 2 次，请转客服工单', 'error'); navigate('support'); return; } state.lastScenario = 'pass'; startFlow('retry', { retryOf: item.id, title: item.title, retryCount: used }); }
        else if (action === 'close-processing') { state.processing = null; persist(); render(); }
        else if (action === 'open-result') { const item = findOwnedHistory(el.dataset.id); if (!item) { toast('无权查看其他账号的任务', 'error'); return; } state.processing = null; state.selectedId = item.id; state.page = 'detail'; persist(); render(); }
        else if (action === 'open-last-result') { const last = visibleHistory()[0]; state.processing = null; state.selectedId = last?.id; state.page = 'detail'; persist(); render(); }
      });
      document.addEventListener('keydown', (event) => { if (!resultDialog) return; const dialog = document.querySelector('.result-detail-modal'); if (!dialog) return; if (event.key === 'Escape') { event.preventDefault(); closeResultDetail(); } else if (event.key === 'Tab') { const controls = [...dialog.querySelectorAll('button:not([disabled])')]; const first = controls[0]; const last = controls[controls.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); } } });
      document.addEventListener('keydown', (event) => {
        if (!resourceDialog) return;
        if (event.key === 'Escape') { event.preventDefault(); closeResourceDialog(); }
        else if (event.key === 'Tab') {
          const controls = [...document.querySelectorAll('.resource-modal button:not([disabled]), .resource-modal input:not([hidden]), .resource-modal select, .resource-modal textarea')].filter((entry) => entry.getClientRects().length);
          const first = controls[0]; const last = controls[controls.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
      });
      document.addEventListener('change', (event) => {
        const input = event.target;
        if (input.matches('[data-resource-select]')) {
          const picker = input.dataset.resourceSelect === 'picker';
          const dialog = picker ? resourceDialog : null;
          if (picker && dialog?.kind !== 'picker') return;
          let ids = picker ? dialog.selectedIds : state.resourceView.selectedIds;
          const single = picker && dialog.purpose === 'reference';
          ids = single ? [] : ids.filter((id) => id !== input.value);
          if (input.checked) ids.push(input.value);
          if (picker && ids.length > (single ? 1 : 10)) { input.checked = false; toast('每次最多选择10张图片', 'error'); return; }
          if (picker) dialog.selectedIds = ids; else state.resourceView.selectedIds = ids;
          persist(); render();
        } else if (input.matches('[data-resource-page-select]')) {
          const ids = resourceRows(state.resourceView).items.map((entry) => entry.id);
          state.resourceView.selectedIds = input.checked ? [...new Set([...state.resourceView.selectedIds, ...ids])] : state.resourceView.selectedIds.filter((id) => !ids.includes(id));
          persist(); render();
        } else if (input.id === 'resource-files' || input.id === 'reference-file') {
          const files = [...input.files];
          const limit = input.id === 'reference-file' ? 1 : 20;
          if (!files.length) return;
          if (files.length > limit || files.some((file) => !['image/jpeg','image/png'].includes(file.type) || file.size > 20 * 1024 * 1024)) {
            input.value = ''; toast(`最多${limit}张JPG/PNG图片，单张不能超过20 MiB`, 'error'); return;
          }
          const metadata = files.map((file) => ({ name: file.name, size: file.size, type: file.type }));
          captureResourceForm();
          if (input.id === 'reference-file') state.batchDraft = { ...(state.batchDraft || {}), reference: metadata[0] };
          else if (resourceDialog?.kind === 'add') resourceDialog.files = metadata;
          render();
        } else if (input.id === 'resource-import-json') {
          const file = input.files?.[0];
          if (!file || !resourceDialog || resourceDialog.mode !== 'import') return;
          const reader = new FileReader();
          reader.onload = () => {
            try {
              const parsed = JSON.parse(String(reader.result || ''));
              const list = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.items) ? parsed.items : [parsed];
              const items = parseImportPayload('', list);
              if (!items.length) throw new Error('JSON 中没有可用的 url');
              if (items.length > 100) throw new Error('JSON 最多 100 条');
              captureResourceForm();
              resourceDialog.jsonName = file.name;
              resourceDialog.jsonItems = items;
              resourceDialog.urls = JSON.stringify(items, null, 2);
              render();
              toast(`已载入 JSON：${items.length} 条`);
            } catch (error) {
              input.value = '';
              toast(error.message || 'JSON 解析失败', 'error');
            }
          };
          reader.onerror = () => toast('读取 JSON 文件失败', 'error');
          reader.readAsText(file);
        } else if (input.id === 'process-validation') { state.uploadValidationCase = input.value; persist(); }
      });
      document.addEventListener('submit', (event) => { const form = event.target.closest('form[data-form]'); if (!form) return; event.preventDefault(); if (form.dataset.form === 'user-action') { handleUserAction(form); return; } if (form.dataset.form === 'ticket-review') { handleTicketReview(form); return; } handleSubmit(form); });
       document.addEventListener('change', (event) => { if (event.target.matches('[data-model-purpose]')) { const form = event.target.form; const next = String(event.target.value || modelPurposes[0]); captureModelKeyForm(form, modelKeyFormState().purpose); modelKeyFormState().purpose = next; persist(); render(); return; } if (event.target.matches('[data-user-permission-role]')) { const defaults = userRolePermissions[event.target.value] || []; event.target.form.querySelectorAll('[name="permissions"]').forEach((input) => { input.checked = defaults.includes(input.value); }); } if (event.target.matches('form[data-form="device-preset-full"] [name="gps_mode"]')) { syncPresetGpsFields(event.target.form); } if (event.target.matches('[data-direct-preset-field]')) { const field = event.target.dataset.directPresetField; if (field === 'type') { state.directPresetType = event.target.value; state.directPresetBrand = ''; state.directPresetModel = ''; } if (field === 'brand') { state.directPresetBrand = event.target.value; state.directPresetModel = ''; } if (field === 'model') state.directPresetModel = event.target.value; const selection = directPresetSelection(); state.directPresetType = selection.type; state.directPresetBrand = selection.brand; state.directPresetModel = selection.model; state.directPresetId = selection.preset?.id || ''; state.directPresetName = selection.preset?.name || ''; persist(); render(); } if (event.target.id === 'history-status') { state.historyFilter.status = event.target.value; state.historyView.page = 1; persist(); render(); } if (event.target.id === 'device-preset-category' || event.target.id === 'device-preset-review') { const view = state.system.devicePresetView; if (event.target.id === 'device-preset-category') view.category = event.target.value; if (event.target.id === 'device-preset-review') view.review = event.target.value; view.page = 1; view.detailId = null; persist(); render(); } if (event.target.id === 'batch-prompt-template') { const template = state.promptTemplates.find((entry) => entry.id === event.target.value); const kept = { ...(state.batchDraft || {}) }; if (template) { state.batchDraft = { ...kept, templateId: template.id, prompt: template.prompt, negative: template.negative || '' }; state.promptOptimization = { active: false, original: '', optimized: '', confirmed: false, status: 'idle', charged: 0 }; } else { state.batchDraft = { ...kept, templateId: '', prompt: undefined, negative: undefined }; } persist(); render(); } if (event.target.matches('[data-preset-prompt-template]')) { const form = event.target.form; const template = state.promptTemplates.find((entry) => entry.id === event.target.value); const positive = form?.querySelector('[name="ai_positive_prompt"]'); const negative = form?.querySelector('[name="ai_negative_prompt"]'); if (template) { if (positive) positive.value = template.prompt || ''; if (negative) negative.value = template.negative || ''; toast(`已套用模板「${template.name}」`); } else { if (positive) positive.value = ''; if (negative) negative.value = ''; } } });
       document.addEventListener('input', (event) => { if (event.target.id === 'history-query') { state.historyFilter.query = event.target.value; state.historyView.page = 1; persist(); const cursor = event.target.selectionStart; render(); const input = document.getElementById('history-query'); if (input) { input.focus(); input.setSelectionRange(cursor, cursor); } } if (event.target.id === 'device-preset-query') { state.system.devicePresetView.query = event.target.value; state.system.devicePresetView.page = 1; state.system.devicePresetView.detailId = null; persist(); const cursor = event.target.selectionStart; render(); const input = document.getElementById('device-preset-query'); if (input) { input.focus(); input.setSelectionRange(cursor, cursor); } } });
      window.addEventListener('hashchange', () => { const page = location.hash.slice(1) || 'login'; if (page !== state.page) { userDialog = null; resultDialog = null; resourceDialog = null; state.page = ['batch','upload','import'].includes(page) ? 'resources' : page; state.session = page !== 'login'; render(); } });
      initializeResources();
      initializeMessages();
      state.jobs.filter((job) => !job.done).forEach(scheduleJob);
      persist();
      render();
    })();

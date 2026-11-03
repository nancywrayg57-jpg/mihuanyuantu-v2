# 2026-10-28 图片资源与处理任务原型上下文

范围：经用户逐项确认后实施的离线HTML交互更新；不接真实OSS或后端，不生成ZIP。本文替代旧交接中“AI生图一级菜单”“整批继续EXIF”“批量原图内上传/URL导入”的描述，其余管理、设备、整数积分和结果详情口径沿用。

- 导航：`#resources` 为图片资源，取代AI生图；统一添加窗口选择文生图/图生图/本地上传/URL导入。旧 `#batch/#upload/#import` 兼容转到资源页，不再暴露旧处理入口。
- 获取：本地/URL每次1—20张；URL每行一个HTTP/HTTPS，仅校验文本。生图1—10张，成功即入库，保留结果预览和统一批量下载，“前往图片资源”只导航。图生图参考图可选资源或临时上传，临时参考图不入库。
- 资源：单一图片卡片网格，20张/页，默认全部来源、仅按来源筛选；跨页/筛选保留勾选。查看只放大；可单张及批量下载/删除。同名文件在同一次批量保存中加后缀避免覆盖。删除前确认，不生成ZIP。
- 处理：`#direct` 只选择已有资源；资源页“去处理”或页面“选择图片”弹窗，每次1—10张，可混选来源，整批统一一套启用设备预设。参数预览默认折叠。提交后独立任务运行，关闭窗口或刷新仍继续；同图可并行、多次处理，输出不入资源库。
- 删除：任何关联处理任务运行时阻止单张/整批删除；完成后允许。删除仅模拟原图失效，生图历史按资源墓碑禁止原图预览下载，保留历史摘要及既有处理输出。原图删除后不允许通过历史重新提交处理，不将输出伪装成原图。
- 历史：生图任务/图片处理任务双标签，各10条/页，分别保存来源、查询、状态、页码。处理任务复制/重新处理回原资源选择；后续增量已删除生图复制/重新处理、四张概览卡及时间线，详见 `2026-10-28-prototype-account-messages-generation-detail.md`。旧混合链归处理任务，旧GENERATED归生图任务；资源迁移由版本标记只执行一次。

本地Schema（仅前端演示数据，不是生产API契约）：

```text
resources[]: id, tenantId, source(text|image|upload|import), name,
  createdAt, size, type, previewUrl, originalUrl,
  generationId?, generationResultId?, deletedAt?
resourceView: source, page, pageSize=20, selectedIds[]
processResourceIds[]
jobs[]: id, kind(generation|processing|retry), tenantId, historyId,
  payload(resourceIds[], originalItems[], presetSnapshot?, autoSnapshot,
          taskType, taskId, runId, reserved?), scenario, step, progress,
  message, done, batchItems[]
history[]: taskType(generation|processing), resourceIds[], runId,
  generationParams? / presetSnapshot?, results[]
generation results[].resourceId -> resources.id
processing results[].inputResourceId -> resources.id
processing results[].source retains per-image provenance
historyTab, historyTabs{generation|processing: filter, view}
```

- 新增/查找/处理/删除资源均校验本地tenantId。任务提交时锁定输入、设备及自动重做快照；独立定时器按runId推进，以taskId替换运行中记录，避免重复历史、重复冻结与重复结算。积分使用已有decimal.js进行整数运算。这些仅为浏览器模拟，不证明真实并发、账本或后端权限。
- 原型仍只读取本地文件元数据、生成固定预览，URL不联网；未上传、下载或删除真实OSS文件。下载的是原型图片；SVG预览在保存前以Canvas编码成对应PNG/JPEG，保存类型与扩展名一致，浏览器下载降级也使用编码后内容。文件/目录选择器测试使用浏览器替身。
- 92项定向检查通过：`output/playwright/image-resources-{acquisition,processing,edge,history-layout,form-scroll,export}-check.js` 和对应 `*-result.txt`。包含实际浏览器交互、并行时钟测试、刷新恢复、删除传播、分页、键盘及390px布局；原生系统选择器与file://直开本轮未重验。
- 三份主脚本必须同步：`prototype/prototype.js`、`prototype/index.html` 内嵌脚本、`output/prototype-inline-check.js`。本轮未创建或重打ZIP；收尾时原型目录中未找到ZIP文件，旧包哈希仅为历史记录。README及主交接的SHA以最终文件为准。

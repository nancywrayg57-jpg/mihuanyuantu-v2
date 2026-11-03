/**
 * 用户 CSV 批量导入页语言包（回流自下游分支，2026-08-27）。键前缀 `userImport.*`。
 */
import { registerLocaleMessages } from '../registry'

const zhCN: Record<string, string> = {
  "userImport.chooseFile": "选择 CSV 文件",
  "userImport.column.line": "行号",
  "userImport.column.message": "说明",
  "userImport.column.status": "结果",
  "userImport.column.username": "账号",
  "userImport.commit": "确认执行",
  "userImport.contentLabel": "CSV 内容",
  "userImport.contentPlaceholder": "把 CSV 内容粘贴到这里，或用上面的按钮选择文件",
  "userImport.description": "用 CSV 一次建好试点小组的账号，并同时分配团队和角色。",
  "userImport.downloadTemplate": "下载模板",
  "userImport.dryRun": "预演",
  "userImport.dryRunBadge": "本次为预演，未写入",
  "userImport.passwordHint": "离开本页后无处可查。请复制下来线下转交，并提醒他们首次登录后修改。",
  "userImport.passwordTitle": "初始密码只显示这一次",
  "userImport.permissionDenied": "需要「创建用户」权限。",
  "userImport.status.created": "已创建",
  "userImport.status.error": "失败",
  "userImport.status.skipped": "已跳过",
  "userImport.step1": "第一步：准备文件",
  "userImport.step1Hint": "表头用中文或英文都行；「序号」「入职日期」这类多余的列会被忽略。团队和角色填名字，不用填 ID。",
  "userImport.step2": "第二步：先预演，再执行",
  "userImport.step2Hint": "预演会走完全部校验并给出逐行结论，但一行都不写库。确认没问题再执行。",
  "userImport.summary": "共 {total} 行：可建 {created}、跳过 {skipped}、失败 {failed}",
  "userImport.title": "批量导入用户",
}

const enUS: Record<string, string> = {
  "userImport.chooseFile": "Choose CSV file",
  "userImport.column.line": "Line",
  "userImport.column.message": "Detail",
  "userImport.column.status": "Result",
  "userImport.column.username": "Username",
  "userImport.commit": "Commit",
  "userImport.contentLabel": "CSV content",
  "userImport.contentPlaceholder": "Paste CSV here, or pick a file above",
  "userImport.description": "Create the whole pilot team from a CSV, with teams and roles assigned in one pass.",
  "userImport.downloadTemplate": "Download template",
  "userImport.dryRun": "Dry run",
  "userImport.dryRunBadge": "dry run, nothing written",
  "userImport.passwordHint": "They cannot be retrieved after you leave this page. Copy them, hand them over offline, and ask users to change them at first login.",
  "userImport.passwordTitle": "Initial passwords are shown once",
  "userImport.permissionDenied": "Requires the user:create permission.",
  "userImport.status.created": "Created",
  "userImport.status.error": "Failed",
  "userImport.status.skipped": "Skipped",
  "userImport.step1": "Step 1: prepare the file",
  "userImport.step1Hint": "Headers may be Chinese or English. Extra columns are ignored. Use team and role names, not IDs.",
  "userImport.step2": "Step 2: dry run, then commit",
  "userImport.step2Hint": "The dry run validates everything and reports row by row without writing anything.",
  "userImport.summary": "{total} rows: {created} to create, {skipped} skipped, {failed} failed",
  "userImport.title": "Bulk import users",
}

const esES: Record<string, string> = {
  "userImport.chooseFile": "Elegir archivo CSV",
  "userImport.column.line": "Línea",
  "userImport.column.message": "Detalle",
  "userImport.column.status": "Resultado",
  "userImport.column.username": "Usuario",
  "userImport.commit": "Confirmar",
  "userImport.contentLabel": "Contenido CSV",
  "userImport.contentPlaceholder": "Pega el CSV aquí o elige un archivo arriba",
  "userImport.description": "Crea todo el equipo piloto desde un CSV, asignando equipos y roles a la vez.",
  "userImport.downloadTemplate": "Descargar plantilla",
  "userImport.dryRun": "Simular",
  "userImport.dryRunBadge": "simulación, no se escribió nada",
  "userImport.passwordHint": "No se pueden recuperar al salir de esta página. Cópialas, entrégalas fuera de línea y pide que las cambien al iniciar sesión.",
  "userImport.passwordTitle": "Las contraseñas iniciales se muestran una sola vez",
  "userImport.permissionDenied": "Requiere el permiso user:create.",
  "userImport.status.created": "Creado",
  "userImport.status.error": "Error",
  "userImport.status.skipped": "Omitido",
  "userImport.step1": "Paso 1: prepara el archivo",
  "userImport.step1Hint": "Las cabeceras pueden ir en chino o inglés. Las columnas extra se ignoran. Usa nombres de equipo y rol, no IDs.",
  "userImport.step2": "Paso 2: simula y luego confirma",
  "userImport.step2Hint": "La simulación valida todo y detalla fila por fila sin escribir nada.",
  "userImport.summary": "{total} filas: {created} a crear, {skipped} omitidas, {failed} con error",
  "userImport.title": "Importar usuarios en lote",
}

registerLocaleMessages('zh-CN', zhCN)
registerLocaleMessages('en-US', enUS)
registerLocaleMessages('es-ES', esES)

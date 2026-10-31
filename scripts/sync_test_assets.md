# 从本机同步测试图到 Cloud Agent 工作区

本机源目录（用户确认）：

```text
D:\workspace\蜜獾原图v2\测试用
├─ 测试图\
├─ 测试图_处理后\
├─ 测试图_二次处理后\
├─ 测试图_三次处理后\
└─ 校准图\          ← 不要同步（Q6 不纳入）
```

Cloud 目标目录：

```text
/workspace/data/测试用/
├─ 测试图/
├─ 测试图_处理后/
├─ 测试图_二次处理后/
└─ 测试图_三次处理后/
```

> Cloud Agent **无法直接读取** Windows 盘符 `D:\`。必须把文件送进当前 git 工作区或上传给本 Agent。

## 推荐方式 A：本机打包上传到对话

在 PowerShell：

```powershell
cd D:\workspace\蜜獾原图v2
# 排除校准图，打 zip（约数百 MB～数 GB，视图片而定）
Compress-Archive -Path `
  "测试用\测试图","测试用\测试图_处理后","测试用\测试图_二次处理后","测试用\测试图_三次处理后" `
  -DestinationPath "$env:TEMP\mihuan-test-assets.zip"
```

然后把 `mihuan-test-assets.zip` **拖进本 Agent 对话**上传。上传完成后回复「已上传」，Agent 会解压到 `data/测试用/` 并继续 792 图次评测。

## 推荐方式 B：推到 GitHub（LFS）

```powershell
cd D:\path\to\mihuanyuantu-v2   # 本仓库 clone
git lfs install
git lfs track "data/测试用/**/*.jpg"
git lfs track "data/测试用/**/*.jpeg"
git lfs track "data/测试用/**/*.png"
# 复制四组目录到 data\测试用\...
git add .gitattributes data/测试用
git commit -m "Add MH-YT test assets (198×4)"
git push
```

然后在 Cloud Agent 对话回复「已 push」，Agent `git pull` 后继续。

## 同步后 Agent 侧命令

```bash
python -m eval.build_manifest
python -m eval.run_eval --detectors lynote_univfd,nonescape_onnx,community_forensics
python -m eval.metrics
```

# 接口契约模板（API Contract）

## 1) 基本信息

- 模块/资源：
- 前端页面：
- API 前缀：`/api/v1/...`

## 2) 统一响应

- success: boolean
- code: string
- message: string
- data: any

## 3) 列表接口（分页）

- Method/Path：
- 权限码：
- Request（示例）：
- Response（示例：必须含 `list/total/pageSize/currentPage`）：
- 错误码（业务错误）：

## 4) 创建/更新/删除

- 创建：
  - Method/Path：
  - 权限码：
- 更新：
  - Method/Path：
  - 权限码：
- 删除：
  - Method/Path：
  - 权限码：

## 5) 演示模式注意事项

- 是否存在“读语义 POST（分页查询）”：
- 是否需要 allowlist：


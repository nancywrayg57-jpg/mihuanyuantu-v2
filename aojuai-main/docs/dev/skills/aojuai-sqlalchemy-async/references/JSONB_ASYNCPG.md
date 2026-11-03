# JSONB + asyncpg 注意事项

## 为什么 `::jsonb` 不行

当你使用 `sqlalchemy.text()` + asyncpg 驱动时，参数占位符是 `:param`，而 `:param::jsonb` 不是 asyncpg 支持的参数语法。

## 正确写法

```python
import json
from sqlalchemy import text

await db.execute(
    text(
        "INSERT INTO t (config) VALUES (cast(:config as jsonb))"
    ),
    {"config": json.dumps({"key": "value"})},
)
```

## 空对象默认值

```sql
cast('{}' as jsonb)
```

## 相关参考

- `backend/scripts/seed_data.py`（大量 JSONB 插入示例）


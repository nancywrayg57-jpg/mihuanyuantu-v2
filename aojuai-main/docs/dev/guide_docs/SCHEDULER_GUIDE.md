# AOJU Backend - 定时任务使用指南

## 概述

本项目使用 APScheduler 实现定时任务调度功能。支持间隔任务（Interval）和 Cron 任务两种模式。

## 目录结构

```
backend/app/
├── core/
│   └── scheduler.py      # 调度器核心模块
└── tasks/
    ├── __init__.py       # 任务包初始化
    └── example_task.py   # 示例任务
```

## 快速开始

### 1. 创建任务文件

在 `app/tasks/` 目录下创建任务文件：

```python
# app/tasks/my_task.py
from datetime import datetime
from app.core.logger import get_logger

logger = get_logger(__name__)

async def my_sync_task() -> None:
    """我的同步任务"""
    try:
        # 执行任务逻辑
        logger.info("my_sync_task_started")
        
        # TODO: 添加实际业务逻辑
        
        logger.info("my_sync_task_completed")
    except Exception as e:
        logger.error("my_sync_task_failed", error=str(e))
```

### 2. 注册任务

在 `backend/app/core/scheduler.py` 的 `register_tasks()` 函数中注册任务：

```python
def register_tasks() -> None:
    """注册所有定时任务"""
    from app.tasks.my_task import my_sync_task
    
    # 方式1: 使用间隔触发器（每30分钟执行一次）
    scheduler.add_job(
        my_sync_task,
        trigger=IntervalTrigger(minutes=30),
        id='my_sync_task_job',
        name='我的同步任务',
        replace_existing=True
    )
    
    # 方式2: 使用 Cron 触发器（每天凌晨2点执行）
    scheduler.add_job(
        my_daily_task,
        trigger=CronTrigger(hour=2, minute=0),
        id='my_daily_task_job',
        name='每日任务',
        replace_existing=True
    )
```

## 任务类型

### 间隔任务 (IntervalTrigger)

适用于需要固定间隔执行的任务：

```python
from apscheduler.triggers.interval import IntervalTrigger

# 每10分钟执行
trigger = IntervalTrigger(minutes=10)

# 每2小时执行
trigger = IntervalTrigger(hours=2)

# 每30秒执行
trigger = IntervalTrigger(seconds=30)

# 组合使用
trigger = IntervalTrigger(hours=1, minutes=30)
```

### Cron 任务 (CronTrigger)

适用于需要在特定时间点执行的任务：

```python
from apscheduler.triggers.cron import CronTrigger

# 每天凌晨2点执行
trigger = CronTrigger(hour=2, minute=0)

# 每周一凌晨3点执行
trigger = CronTrigger(day_of_week='mon', hour=3, minute=0)

# 每月1号凌晨1点执行
trigger = CronTrigger(day=1, hour=1, minute=0)

# 每5分钟执行（Cron方式）
trigger = CronTrigger(minute='*/5')
```

## 辅助函数

`scheduler.py` 提供了便捷的辅助函数：

### add_interval_task

```python
from app.core.scheduler import add_interval_task

add_interval_task(
    func=my_task,
    task_id='my_task_id',
    task_name='我的任务',
    minutes=30  # 每30分钟执行
)
```

### add_cron_task

```python
from app.core.scheduler import add_cron_task

add_cron_task(
    func=my_task,
    task_id='my_task_id',
    task_name='我的任务',
    hour=2,
    minute=0  # 每天凌晨2点执行
)
```

### remove_task

```python
from app.core.scheduler import remove_task

remove_task('my_task_id')
```

### get_all_jobs

```python
from app.core.scheduler import get_all_jobs

jobs = get_all_jobs()
# 返回: [{"id": "...", "name": "...", "next_run_time": "...", "trigger": "..."}]
```

## 任务中使用数据库

如果任务需要访问数据库，需要创建独立的数据库会话：

```python
from app.infrastructure.database import get_async_session
from app.domain.users.service import UserService

async def my_db_task() -> None:
    """需要数据库访问的任务"""
    async for session in get_async_session():
        try:
            service = UserService(session)
            users = await service.get_list(page_size=100)
            
            # 处理用户数据...
            
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("task_failed", error=str(e))
```

## 错误处理

建议在任务中使用 try-except 捕获异常，避免任务失败影响其他任务：

```python
async def my_task() -> None:
    try:
        # 任务逻辑
        pass
    except Exception as e:
        logger.error("my_task_failed", error=str(e), exc_info=True)
        # 可选：发送告警通知
```

## 日志规范

任务执行时应记录关键日志：

```python
async def my_task() -> None:
    logger.info("task_started", task_name="my_task")
    
    try:
        # 执行业务逻辑
        result = await do_something()
        
        logger.info(
            "task_completed",
            task_name="my_task",
            processed_count=result.count,
            duration_ms=result.duration
        )
    except Exception as e:
        logger.error(
            "task_failed",
            task_name="my_task",
            error=str(e),
            exc_info=True
        )
```

## 生命周期

1. **应用启动时**：自动调用 `start_scheduler()` 注册并启动所有定时任务
2. **应用运行中**：调度器在后台运行，按计划执行任务
3. **应用关闭时**：自动调用 `stop_scheduler()` 优雅停止所有任务

## 测试环境

在 pytest 测试中，调度器不会自动启动，避免测试时执行定时任务。

## 注意事项

1. **任务函数必须是异步函数**（`async def`）
2. **任务ID必须唯一**，重复的ID会替换旧任务
3. **任务执行时间不宜过长**，长时间任务可能影响其他任务调度
4. **避免在任务中使用全局状态**，每次执行应独立
5. **数据库操作需要创建独立会话**，不要共享会话

## 常见问题

### Q: 任务没有执行？

1. 检查任务是否正确注册（查看启动日志）
2. 检查任务ID是否正确
3. 检查触发器配置是否正确

### Q: 任务执行失败？

1. 检查任务函数是否是异步函数
2. 检查是否正确处理了异常
3. 查看错误日志获取详细信息

### Q: 如何动态添加/移除任务？

使用 `add_interval_task()` / `add_cron_task()` / `remove_task()` 函数。

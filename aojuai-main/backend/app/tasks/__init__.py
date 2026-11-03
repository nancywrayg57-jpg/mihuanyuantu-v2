"""
AOJU Backend - Scheduled Tasks Package

定时任务目录，存放所有定时任务的实现。

目录结构：
- __init__.py: 包初始化，导出任务注册函数
- example_task.py: 示例任务（可删除）
- your_task.py: 自定义任务

添加新任务步骤：
1. 在此目录下创建任务文件（如 my_task.py）
2. 实现异步任务函数
3. 在 app/core/scheduler.py 的 register_tasks() 中注册任务
"""

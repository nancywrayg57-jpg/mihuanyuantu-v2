"""
AOJU Backend - Example Scheduled Task

示例定时任务，展示如何创建定时任务。
可以删除此文件或作为模板参考。
"""
from datetime import datetime

from app.core.logger import get_logger

logger = get_logger(__name__)


async def example_task() -> None:
    """
    示例定时任务

    这是一个简单的示例任务，每次执行时记录一条日志。
    实际任务可以执行数据同步、清理、报告生成等操作。
    """
    logger.info(
        "example_task_executed",
        timestamp=datetime.now().isoformat(),
        message="示例定时任务执行成功"
    )

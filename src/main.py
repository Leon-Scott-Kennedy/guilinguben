# ===== 路径修正（必须放在所有导入之前） =====
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
# ===========================================

"""应用入口。根据环境变量决定启动模式：web / eval / cli"""
from langchain_core.globals import set_debug
from src.config.settings import settings


def run_evaluation():
    """评估模式占位入口：保持项目在 eval 模式时不会直接崩溃。"""
    print("Evaluation mode is enabled. No evaluation run configured yet.")


def main():
    if settings.app_mode == "web":
        from src.ui.app import run_ui
        run_ui()
    elif settings.app_mode == "eval":
        run_evaluation()
    else:
        print("Unknown app_mode. Use: web | eval")


# 开启 LangChain 调试日志
set_debug(True)

if __name__ == "__main__":
    main()
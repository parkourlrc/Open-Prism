from ..aient.aient.plugins import register_tool

@register_tool()
def save_screenshot_to_file(save_path):
    """
    截取当前屏幕并保存到指定路径

    参数:
        save_path: 截图保存的完整路径，包括文件名和扩展名

    返回:
        成功返回True，失败返回False
    """
    try:
        import os
        import pyautogui

        # 确保目标目录存在
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # 截取屏幕
        screenshot = pyautogui.screenshot()
        img_width, img_height = pyautogui.size()

        # 保存截图到指定路径
        screenshot.save(save_path)
        return f"截图成功保存，尺寸: {img_width}x{img_height}，保存路径: {save_path}"

    except ImportError:
        return "请安装所需库: pip install Pillow pyautogui"
    except Exception as e:
        return f"截取屏幕或保存图像时出错: {e}"
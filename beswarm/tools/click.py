import io
import os
import re
import json
import time
import base64
import pyperclip # 新增：用于操作剪贴板
import platform  # 新增：用于检测操作系统
from PIL import Image, ImageDraw
from ..aient.aient.plugins import register_tool

from ..aient.aient.models import chatgpt
from ..aient.aient.core.utils import get_image_message, get_text_message

def display_image_with_bounding_boxes_and_masks_py(
    original_image,
    box_and_mask_data,
    output_overlay_path="overlay_image.png",
    output_compare_dir="comparison_outputs"
):
    """
    在原始图像上绘制边界框和掩码，并生成裁剪区域与掩码的对比图。

    Args:
        original_image (str): 原始图像的文件路径。
        box_and_mask_data (list): extract_box_and_mask_py 的输出列表。
        output_overlay_path (str): 保存带有叠加效果的图像的路径。
        output_compare_dir (str): 保存对比图像的目录路径。
    """
    try:
        # 修改：直接使用传入的 PIL Image 对象，并确保是 RGBA
        img_original = original_image.convert("RGBA")
        img_width, img_height = img_original.size
    # except FileNotFoundError: # 移除：不再需要从文件加载
    #     print(f"Error: Original image not found at {original_image}")
    #     return
    except Exception as e:
        # 修改：更新错误消息
        print(f"Error processing original image object: {e}")
        return

    # 创建一个副本用于绘制叠加效果
    img_overlay = img_original.copy()
    draw = ImageDraw.Draw(img_overlay, "RGBA") # 使用 RGBA 模式以支持透明度

    # 定义颜色列表
    colors_hex = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF']
    # 将十六进制颜色转换为 RGBA 元组 (用于绘制)
    colors_rgba = []
    for hex_color in colors_hex:
        h = hex_color.lstrip('#')
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        colors_rgba.append(rgb + (255,)) # (R, G, B, Alpha) - 边框完全不透明

    # 创建输出目录（如果不存在）
    import os
    os.makedirs(output_compare_dir, exist_ok=True)

    print(f"Found {len(box_and_mask_data)} box/mask pairs to process.")

    for i, data in enumerate(box_and_mask_data):
        box_0_1000 = data['box'] # [ymin, xmin, ymax, xmax] in 0-1000 range
        mask_b64 = data['mask_base64']
        color_index = i % len(colors_rgba)
        outline_color = colors_rgba[color_index]
        # 叠加掩码时使用半透明颜色
        mask_fill_color = outline_color[:3] + (int(255 * 0.7),) # 70% Alpha

        # --- 1. 坐标转换与验证 ---
        # 将 0-1000 坐标转换为图像像素坐标 (left, top, right, bottom)
        # 假设 box 是 [ymin, xmin, ymax, xmax]
        try:
            ymin_norm, xmin_norm, ymax_norm, xmax_norm = [c / 1000.0 for c in box_0_1000]

            left   = int(xmin_norm * img_width)
            top    = int(ymin_norm * img_height)
            right  = int(xmax_norm * img_width)
            bottom = int(ymax_norm * img_height)

            # 确保坐标在图像范围内且有效
            left = max(0, left)
            top = max(0, top)
            right = min(img_width, right)
            bottom = min(img_height, bottom)

            box_width_px = right - left
            box_height_px = bottom - top

            if box_width_px <= 0 or box_height_px <= 0:
                print(f"Skipping box {i+1} due to zero or negative dimensions after conversion.")
                continue

        except Exception as e:
            print(f"Error processing coordinates for box {i+1}: {box_0_1000}. Error: {e}")
            continue

        print(f"Processing Box {i+1}: Pixels(L,T,R,B)=({left},{top},{right},{bottom}) Color={colors_hex[color_index]}")

        # --- 2. 在叠加图像上绘制边界框 ---
        try:
            draw.rectangle([left, top, right, bottom], outline=outline_color, width=5)
        except Exception as e:
             print(f"Error drawing rectangle for box {i+1}: {e}")
             continue

        # --- 3. 处理并绘制掩码 ---
        try:
            # 解码 Base64 掩码数据
            mask_bytes = base64.b64decode(mask_b64)
            mask_img_raw = Image.open(io.BytesIO(mask_bytes)).convert("RGBA")

            # 将掩码图像缩放到边界框的像素尺寸
            mask_img_resized = mask_img_raw.resize((box_width_px, box_height_px), Image.Resampling.NEAREST)

            # 创建一个纯色块，应用掩码的 alpha 通道
            color_block = Image.new('RGBA', mask_img_resized.size, mask_fill_color)

            # 将带有透明度的颜色块粘贴到叠加图像上，使用掩码的 alpha 通道作为粘贴蒙版
            # mask_img_resized.split()[-1] 提取 alpha 通道
            img_overlay.paste(color_block, (left, top), mask=mask_img_resized.split()[-1])

        except base64.binascii.Error:
             print(f"Error: Invalid Base64 data for mask {i+1}.")
             continue
        except Exception as e:
             print(f"Error processing or drawing mask for box {i+1}: {e}")
             continue

        # --- 4. 生成对比图 ---
        try:
            # 从原始图像中裁剪出边界框区域
            img_crop = img_original.crop((left, top, right, bottom))

            # 准备掩码预览图（使用原始解码后的掩码，调整大小以匹配裁剪区域）
            # 这里直接使用缩放后的 mask_img_resized 的 RGB 部分可能更直观
            mask_preview = mask_img_resized.convert("RGB") # 转换为 RGB 以便保存为常见格式

            # 保存裁剪图和掩码预览图
            crop_filename = os.path.join(output_compare_dir, f"compare_{i+1}_crop.png")
            mask_filename = os.path.join(output_compare_dir, f"compare_{i+1}_mask.png")
            img_crop.save(crop_filename)
            mask_preview.save(mask_filename)
            print(f" - Saved comparison: {crop_filename}, {mask_filename}")

        except Exception as e:
            print(f"Error creating or saving comparison images for box {i+1}: {e}")

    # --- 5. 保存最终的叠加图像 ---
    try:
        img_overlay.save(output_overlay_path)
        print(f"\nOverlay image saved to: {output_overlay_path}")
        print(f"Comparison images saved in: {output_compare_dir}")
    except Exception as e:
        print(f"Error saving the final overlay image: {e}")

def get_json_from_text(text):
    regex_pattern = r'({\"box_2d\".+?})' # 匹配包含至少一个对象的数组
    # regex_pattern = r'(\[\s*\{.*?\}\s*\])' # 匹配包含至少一个对象的数组

    # 使用 re.search 查找第一个匹配项，re.MULTILINE 使点号能匹配换行符
    match = re.search(regex_pattern, text, re.MULTILINE)


    if match:
        # 提取匹配到的整个 JSON 数组字符串 (group 1 因为模式中有括号)
        json_string = match.group(1)
        # print(f"匹配到的 JSON 字符串: {json_string}")

        try:
            # 使用 json.loads() 解析字符串
            parsed_data = json.loads(json_string)
            # 使用 json.dumps 美化打印输出
            # print(json.dumps(parsed_data, indent=2, ensure_ascii=False))

            # 例如，获取第一个元素的 label
            if isinstance(parsed_data, list) and len(parsed_data) > 0:
                first_item = parsed_data[0]
                if isinstance(first_item, dict):
                    label = first_item.get('label')
                    print(f"\n第一个元素的 label 是: {label}")
                return first_item

            return parsed_data

        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            print(f"出错的字符串是: {json_string}")
    else:
        print("在文本中未找到匹配的 JSON 数组。")


@register_tool()
async def find_and_click_element(target_element, input_text=None):
    """
在当前屏幕截图中查找目标 UI 元素，并在屏幕上点击其中心点。

此函数首先截取当前屏幕，然后将截图和目标元素的描述 (`target_element`) 发送给配置好的大语言模型 (LLM)。
LLM 被要求识别出目标元素，并返回其在截图中的边界框 (bounding box) 和掩码 (mask) 信息（通常以 JSON 格式）。
函数接着解析 LLM 的响应，提取出边界框坐标。
（可选）为了调试和验证，函数可以根据 LLM 返回的数据在截图副本上绘制边界框和掩码，并将结果保存为图像文件。
最后，函数计算边界框的中心点像素坐标，并使用 `pyautogui` 库在该屏幕坐标上模拟鼠标点击。如果提供了 `input_text`，则会在点击后尝试输入该文本。

Args:
    target_element (str): 需要查找和点击的 UI 元素的文本描述 (例如 "登录按钮", "用户名输入框")。LLM 将使用此描述来定位元素。
    input_text (str, optional): 在点击元素后需要输入的文本。如果为 None 或空字符串，则只执行点击操作。默认为 None。

Returns:
    str: 如果成功找到元素、计算坐标并执行点击（以及可能的输入），则返回表示成功的字符串消息 (例如 "点击成功!", "点击并输入 '...' 成功!")。
         如果在任何步骤中失败（例如截图失败、LLM 未返回有效坐标、点击失败），则返回 False。
         如果点击成功但输入失败，则返回包含错误信息的字符串。
    """

    click_agent_config = {
        "api_key": os.getenv("API_KEY"),
        "api_url": os.getenv("BASE_URL"),
        "engine": "gemini-2.5-pro",
        "system_prompt": "you are a professional UI test engineer, now you need to find the specified screen element.",
        # "system_prompt": "你是一个专业的UI测试工程师，现在需要你找到指定屏幕元素。",
        "print_log": True,
        "temperature": 0.7,
        "use_plugins": False,
    }

    # 工作agent初始化
    click_agent = chatgpt(**click_agent_config)
    # https://developers.googleblog.com/en/conversational-image-segmentation-gemini-2-5/
    prompt = f"Give the segmentation masks for the {target_element}. Output a JSON list of segmentation masks where each entry contains the 2D bounding box in \"box_2d\" (format: ymin, xmin, ymax, xmax) and the mask in \"mask\". Only output the one that meets the criteria the most."

    print("正在截取当前屏幕...")
    try:
        import pyautogui
        # 使用 pyautogui 截取屏幕，返回 PIL Image 对象
        screenshot = pyautogui.screenshot()
        # img_width, img_height = screenshot.size # 获取截图尺寸
        img_width, img_height = pyautogui.size()
        print(f"截图成功，尺寸: {img_width}x{img_height}")

        # 将 PIL Image 对象转换为 Base64 编码的 PNG 字符串
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        base64_encoded_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
        IMAGE_MIME_TYPE = "image/png" # 截图格式为 PNG

    except ImportError:
         # Pillow 也是 pyautogui 的依赖，但以防万一单独处理
        print("\n❌ 请安装所需库: pip install Pillow pyautogui")
        return False
    except Exception as e:
        print(f"\n❌ 截取屏幕或处理图像时出错: {e}")
        return False

    engine_type = "gpt"
    message_list = []
    text_message = await get_text_message(prompt, engine_type)
    image_message = await get_image_message(f"data:{IMAGE_MIME_TYPE};base64," + base64_encoded_image, engine_type)
    message_list.append(text_message)
    message_list.append(image_message)

    result = await click_agent.ask_async(message_list)
    if result.strip() == '':
        print("\n❌ click智能体回复为空，请重新生成指令。")
        return False
    first_item = get_json_from_text(result)
    if not first_item or "box_2d" not in first_item:
        print("\n❌ 未能从模型响应中提取有效的 box_2d。")
        return False


    box_0_1000 = first_item.get("box_2d") # 假设格式为 [ymin, xmin, ymax, xmax]，范围 0-1000
    mask_data_uri = first_item.get("mask") # 假设格式为 "data:image/png;base64,..."

    if not box_0_1000 or not isinstance(box_0_1000, list) or len(box_0_1000) != 4:
        print(f"\n❌ 未能从模型响应中提取有效的 box_2d: {box_0_1000}")
        return False
    if not mask_data_uri or not isinstance(mask_data_uri, str) or not mask_data_uri.startswith("data:image/png;base64,"):
        print(f"\n❌ 未能从模型响应中提取有效的 mask data URI: {mask_data_uri}")
        # 如果找不到蒙版，可以选择是失败返回还是继续点击（这里选择继续）
        mask_b64 = None # 没有有效的蒙版
    else:
        # 提取 Base64 部分
        mask_b64 = mask_data_uri.split(',')[-1]

    print(f"✅ click智能体回复 (box_2d 范围 0-1000): {box_0_1000}")
    # ----------------------------------------------

    # --- 新增：调用 display 函数进行可视化 ---
    if box_0_1000: # 仅在有蒙版数据时才尝试绘制
        try:
            print("尝试生成可视化叠加图像...")
            box_and_mask_data_for_display = [{
                "box": box_0_1000,
                "mask_base64": mask_b64
            }]
            display_image_with_bounding_boxes_and_masks_py(
                original_image=screenshot, # 传递 PIL Image 对象
                box_and_mask_data=box_and_mask_data_for_display,
                output_overlay_path=f"click_overlay_{time.strftime('%Y%m%d_%H%M%S')}.png", # 可以自定义输出文件名
                output_compare_dir="click_compare"      # 可以自定义输出目录
            )
        except Exception as e:
            print(f"⚠️ 生成可视化图像时出错: {e}") # 出错不影响点击逻辑继续
    else:
        print("⚠️ 未找到有效的坐标数据，跳过可视化。")

    try:

        # 检查 box_0_1000 格式是否正确
        if not (isinstance(box_0_1000, list) and len(box_0_1000) == 4 and all(isinstance(c, int) for c in box_0_1000)):
             print(f"\n❌ 无效的 box_2d 格式或类型: {box_0_1000}，期望是包含4个整数的列表。")
             return False

        # 坐标转换 (0-1000 范围到 0.0-1.0 范围)
        ymin_norm, xmin_norm, ymax_norm, xmax_norm = [c / 1000.0 for c in box_0_1000]

        # 计算相对于截图的像素坐标
        left   = int(xmin_norm * img_width)
        top    = int(ymin_norm * img_height)
        right  = int(xmax_norm * img_width)
        bottom = int(ymax_norm * img_height)

        # 确保坐标在截图范围内且有效
        left = max(0, left)
        top = max(0, top)
        right = min(img_width, right)
        bottom = min(img_height, bottom)

        # 检查边界框是否有效
        if left >= right or top >= bottom:
            print(f"\n❌ 计算出的边界框无效: left={left}, top={top}, right={right}, bottom={bottom}")
            return False

        # 计算点击的中心点 (相对于截图的坐标)
        # **注意**: 这个坐标现在是相对于截图左上角的像素坐标。
        # 如果截图是全屏的，那么这个坐标也就是屏幕坐标。
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2

        print(f"截图尺寸: width={img_width}, height={img_height}")
        print(f"计算出的像素坐标 (相对于截图): left={left}, top={top}, right={right}, bottom={bottom}")
        print(f"计算出的点击中心点 (屏幕坐标): x={center_x}, y={center_y}")

        # 执行点击操作
        print(f"尝试在屏幕坐标 ({center_x}, {center_y}) 点击...")
        # 使用 pyautogui 在电脑屏幕上点击
        pyautogui.click(center_x, center_y)
        pyautogui.click(center_x, center_y)
        print(f"✅ 在 ({center_x}, {center_y}) 点击成功。")
        # input_text = "123456"
        if input_text:
            try:
                print(f"尝试通过剪贴板输入文本: '{input_text}'")
                # 保存当前剪贴板内容
                original_clipboard_content = pyperclip.paste()
                pyperclip.copy(input_text) # 将文本复制到剪贴板

                # 根据操作系统执行粘贴操作
                if platform.system() == "Darwin":  # macOS
                    pyautogui.hotkey('command', 'v')
                else:  # Windows, Linux, etc.
                    pyautogui.hotkey('ctrl', 'v')

                time.sleep(0.1) # 给粘贴操作一点时间，确保文本已粘贴

                # 恢复原始剪贴板内容
                # 如果不希望恢复，可以注释掉下面这行
                pyperclip.copy(original_clipboard_content)

                print(f"✅ 通过剪贴板输入文本成功。")
                return f"点击并输入 '{input_text}' 成功!"
            except ImportError:
                print("\n❌ pyperclip 库未安装。请运行 'pip install pyperclip' 以支持通过剪贴板输入中文。")
                print(f"将尝试使用 pyautogui.typewrite (可能无法正确输入中文): '{input_text}'")
                try:
                    pyautogui.typewrite(input_text, interval=0.1) # 尝试原始方法作为备选
                    print(f"✅ (备用 typewrite) 已尝试输入文本。")
                    return f"点击并尝试输入 '{input_text}' (使用 typewrite，中文可能失败)!"
                except Exception as e_typewrite:
                    print(f"\n❌ 使用 pyautogui.typewrite 输入文本时也发生错误: {e_typewrite}")
                    return f"点击成功，但输入文本 '{input_text}' (typewrite) 失败: {e_typewrite}"
            except Exception as e:
                print(f"\n❌ 通过剪贴板输入文本时发生错误: {e}")
                # 即使输入失败，点击也算成功了
                return f"点击成功，但输入文本 '{input_text}' (剪贴板) 失败: {e}"
        else:
            # 如果没有提供 input_text，只返回点击成功
            return "点击成功!"

    # except FileNotFoundError:
    #     print(f"错误：找不到图片文件 '{image_path}' 用于获取尺寸。")
    #     return False
    except ImportError:
        print("\n❌ 请安装所需库: pip install Pillow pyautogui")
        return False
    # 移除 AdbError 捕获
    except Exception as e:
        # 添加 pyautogui 可能抛出的异常类型，如果需要更精细的处理
        print(f"\n❌ 处理点击时发生意外错误: {e}")
        return False


@register_tool()
async def scroll_screen(direction: str = "down"):
    """
    控制屏幕向上或向下滑动固定的距离。

    Args:
        direction (str, optional): 滚动的方向。可以是 "up" 或 "down"。
                                   默认为 "down"。

    Returns:
        str: 如果成功执行滚动，则返回相应的成功消息。
             如果方向无效或发生错误，则返回错误信息。
    """
    scroll_offset = 20
    actual_scroll_amount = 0

    if direction == "down":
        actual_scroll_amount = -scroll_offset  # 向下滚动为负值
        print(f"尝试向下滚动屏幕，固定偏移量: {scroll_offset}...")
    elif direction == "up":
        actual_scroll_amount = scroll_offset   # 向上滚动为正值
        print(f"尝试向上滚动屏幕，固定偏移量: {scroll_offset}...")
    else:
        error_msg = f"错误：无效的滚动方向 '{direction}'。请使用 'up' 或 'down'。"
        print(f"\n❌ {error_msg}")
        return error_msg

    try:
        import pyautogui
        pyautogui.scroll(actual_scroll_amount)
        success_msg = f"✅ 屏幕向 {direction} 滑动 {scroll_offset} 成功。"
        print(success_msg)
        return success_msg
    except ImportError:
        print("\n❌ pyautogui 库未安装。请运行 'pip install pyautogui'。")
        return "错误：pyautogui 库未安装。"
    except Exception as e:
        error_msg = f"错误：屏幕滚动时发生: {e}"
        print(f"\n❌ {error_msg}")
        return error_msg


if __name__ == "__main__":
    import asyncio
    IMAGE_PATH = os.environ.get("IMAGE_PATH")
    import time
    time.sleep(2)
    # asyncio.run(find_and_click_element("Write a message...", "你好"))
    # asyncio.run(find_and_click_element("搜索框"))
    # print(get_json_from_text(text))

    # 测试滚动功能
    asyncio.run(scroll_screen("down")) # 向下滚动
    time.sleep(2) # 等待2秒观察效果
    asyncio.run(scroll_screen("up"))   # 向上滚动
    # asyncio.run(scroll_screen("sideways")) # 测试无效方向

# python -m beswarm.tools.click
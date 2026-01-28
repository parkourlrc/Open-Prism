import os
import re
import difflib
from ..aient.aient.plugins import register_tool
from ..aient.aient.utils.scripts import unescape_html

@register_tool()
def edit_file(file_path, diff_content, match_precision=0.9):
    """
使用diff模式编辑代码文件。**重要：此函数每次调用只能对文件进行一处修改。**

你需要提供一个diff块来指定要修改的内容，格式如下：
<<<<<<< SEARCH
要被替换的原始代码
=======
新的代码
>>>>>>> REPLACE

**使用规则:**
1.  **单次修改:** `diff_content`参数中**必须只包含一个** `<<<<<<< SEARCH ... >>>>>>> REPLACE` 块。如果检测到多个块，函数将返回错误。
2.  **上下文:** `SEARCH`块中的原始代码应包含足够的上下文，以确保在文件中能够唯一地定位到修改点，但也要尽量简洁。
3.  **精确性:** `SEARCH`块中的内容需要与文件中的代码精确匹配（包括缩进和换行符）。如果无法精确匹配，函数会尝试模糊匹配。

参数:
    file_path: 要编辑的文件路径。
    diff_content: 包含单次修改信息的diff字符串，格式必须符合上述要求。
    match_precision: 匹配精度 (0.0-1.0)，值越高要求匹配越精确，默认为0.9。当完全精确匹配失败时，此参数生效。

返回:
    编辑结果的状态信息，包括成功或错误信息。
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"<tool_error>文件 '{file_path}' 不存在</tool_error>"

        # 检查是否为文件
        if not os.path.isfile(file_path):
            return f"<tool_error>文件 '{file_path}' 不是一个文件</tool_error>"

        # 尝试读取文件的前几个字节来检测是否为二进制文件
        with open(file_path, 'rb') as file:
            data = file.read(1024)
            # 快速检查是否可能是二进制文件
            if b'\x00' in data:
                return f"<tool_error>文件 '{file_path}' 可能是二进制文件，编码无法解析</tool_error>"

        # 读取原文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # 解析diff内容中的搜索和替换块
        diff_blocks = re.findall(r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE', diff_content, re.DOTALL)

        if not diff_blocks:
            return f"<tool_error>无效的diff格式，未找到搜索和替换块</tool_error>"
        if len(diff_blocks) > 1:
            return f"<tool_error>只支持单次修改，`diff_content`参数中**必须只包含一个** `<<<<<<< SEARCH ... >>>>>>> REPLACE` 块，但找到了 {len(diff_blocks)} 个修改块</tool_error>"

        # 记录修改次数和行数变化
        edits_count = 0
        total_original_lines = 0
        total_new_lines = 0

        # 应用每个diff块
        new_content = content
        for search_block, replace_block in diff_blocks:
            search_block = unescape_html(search_block)
            replace_block = unescape_html(replace_block)
            # 检查搜索块是否为空
            if not search_block.strip():
                return f"<tool_error>搜索块不能为空</tool_error>"

            if search_block in new_content:
                # 直接替换完全匹配的块
                new_content = new_content.replace(search_block, replace_block, 1)
                edits_count += 1

                # 计算行数
                original_lines = search_block.count('\n') + 1
                new_lines = replace_block.count('\n') + 1
                total_original_lines += original_lines
                total_new_lines += new_lines
            else:
                # 尝试进行更宽松的匹配
                search_lines = search_block.splitlines()
                content_lines = new_content.splitlines()

                # 避免空搜索块
                if len(search_lines) == 0:
                    return f"<tool_error>搜索块不能为空</tool_error>"

                # 尝试找到最佳匹配位置
                best_match_index = -1
                best_match_score = 0

                for i in range(len(content_lines) - len(search_lines) + 1):
                    # 计算当前位置的匹配分数
                    match_score = 0
                    lines_compared = 0

                    for j in range(len(search_lines)):
                        search_line = search_lines[j]
                        content_line = content_lines[i + j]

                        # 使用 difflib 计算行相似度，该算法对插入和删除更具鲁棒性
                        line_match = difflib.SequenceMatcher(None, search_line, content_line).ratio()
                        match_score += line_match
                        lines_compared += 1

                    # 计算整体匹配分数
                    match_score = match_score / lines_compared

                    # 如果使用高精度匹配 (>0.95)，我们需要更严格地检查匹配结果
                    if match_precision > 0.95:
                        # 字符串长度差异也要考虑
                        search_text = '\n'.join(search_lines)
                        potential_match_text = '\n'.join(content_lines[i:i + len(search_lines)])
                        length_diff_ratio = abs(len(search_text) - len(potential_match_text)) / max(len(search_text), 1)

                        # 如果长度差异太大，降低匹配分数
                        if length_diff_ratio > 0.1:  # 允许10%的长度差异
                            match_score *= (1 - length_diff_ratio)

                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_index = i

                # 使用匹配精度作为阈值
                if best_match_score >= match_precision and best_match_index >= 0:
                    # 提取找到的实际文本
                    matched_lines = content_lines[best_match_index:best_match_index + len(search_lines)]
                    actual_search_block = '\n'.join(matched_lines)

                    # 替换找到的匹配项
                    new_content = new_content.replace(actual_search_block, replace_block, 1)
                    edits_count += 1

                    # 计算行数
                    original_lines = len(matched_lines)
                    new_lines = replace_block.count('\n') + 1
                    total_original_lines += original_lines
                    total_new_lines += new_lines
                else:
                    error_message = f"<tool_error>在文件中未找到足够匹配的代码块，最佳匹配分数为 {best_match_score:.2f}，但要求为 {match_precision:.2f}。</tool_error>"
                    if best_match_index != -1:
                        start_index = max(0, best_match_index - len(search_lines))
                        end_index = min(len(content_lines), best_match_index + 2 * len(search_lines))
                        context_lines = content_lines[start_index:end_index]
                        context_block = '\n'.join(context_lines)
                        error_message += f"\n\nSEARCH块在原文件最佳匹配范围内的原文如下 (上下文已扩展)，放在在 <real_file_content>...</real_file_content> 之间，请根据原文内容修正 diff_content 参数:\n<real_file_content>\n{context_block}\n</real_file_content>"
                    return error_message

        # 如果没有进行任何编辑，返回错误
        if edits_count == 0:
            return f"<tool_error>未能应用任何diff编辑</tool_error>"

        # 写入修改后的内容
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)

        return f"成功: 文件 '{file_path}' 已更新。应用了 {edits_count} 处编辑，替换了 {total_original_lines} 行代码为 {total_new_lines} 行。"

    except PermissionError:
        return f"<tool_error>没有权限修改文件 '{file_path}'</tool_error>"
    except UnicodeDecodeError:
        return f"<tool_error>文件 '{file_path}' 不是文本文件或编码不是UTF-8，无法进行编码解析</tool_error>"
    except Exception as e:
        print(f"content: {content}")
        print(f"file_path: {file_path}")
        print(f"diff_content: {diff_content}")
        import traceback
        traceback.print_exc()
        return f"<tool_error>编辑文件时发生错误: {e}</tool_error>"

if __name__ == "__main__":
    edit_str = """
<<<<<<< SEARCH
    parser.add_argument('--dataset',type=str,default='cifar10', choices=['cifar10', 'cifar100', 'imagenet'],help="Dataset to use.")
=======
    parser.add_argument('--dataset', type=str, default='cifar10', choices=['cifar10', 'cifar100', 'imagenet', 'tinyimagenet'], help="Dataset to use.")
>>>>>>> REPLACE
"""

    file_path = "train.py"
# 编辑文件时发生错误: '>' not supported between instances of 'str' and 'float'
    print(edit_file(file_path, edit_str))

# python -m beswarm.tools.edit_file

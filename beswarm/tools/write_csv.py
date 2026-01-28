import csv
import ast
import os
from ..aient.aient.plugins import register_tool

@register_tool()
def append_row_to_csv(file_path: str, data: list):
    """
    将一行数据安全地追加到CSV文件中。
    此工具会自动处理包含逗号、引号等特殊字符的字段，确保CSV格式的正确性。

    Args:
        file_path (str): 目标CSV文件的路径。
        data (list): 一个代表单行数据的列表，列表中的每个元素对应CSV的一列。
                     例如: ['1911.00484v4', 'irrelevant', '这段文本,可以包含逗号', 0.0]

    Returns:
        str: 操作成功或失败的提示信息。
    """
    try:
        # 使用 'a+' 模式，以便在写入前检查文件末尾
        with open(file_path, 'a+', newline='', encoding='utf-8') as file:
            file.seek(0, os.SEEK_END)  # 移动到文件末尾
            # 如果文件非空，且最后一个字符不是换行符，则添加一个
            if file.tell() > 0:
                file.seek(file.tell() - 1, os.SEEK_SET)
                if file.read(1) != '\n':
                    file.write('\n')

            writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(ast.literal_eval(data) if isinstance(data, str) else data)

        return f"已成功将一行数据追加到 {file_path}"
    except Exception as e:
        return f"<tool_error>写入CSV文件 {file_path} 时发生错误: {e}</tool_error>"

#!/usr/bin/env python3

from __future__ import annotations

import os
import sys

from beswarm.tools import register_tool


@register_tool()
async def capture_html_to_png(html_file_path: str, output_png_path: str) -> tuple[str, str]:
    """
    使用 Playwright 将指定的 HTML 文件截图为 PNG。

    注意：打包版 OceanS_Paper 默认不包含 Playwright；如果缺少依赖会返回错误信息而不是崩溃。
    """
    error_output = ""

    if not os.path.exists(html_file_path):
        return f"错误: 输入 HTML 文件未找到 - {html_file_path}", error_output

    output_dir = os.path.dirname(output_png_path)
    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            return f"错误: 创建输出目录失败 '{output_dir}' - {e}", error_output

    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ModuleNotFoundError as e:
        return (
            "错误: Playwright 未安装或未打包到应用中，无法执行 HTML -> PNG 截图。",
            str(e),
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            abs_html_path = os.path.abspath(html_file_path)
            if sys.platform == "win32":
                file_url = f"file:///{abs_html_path.replace(os.sep, '/')}"
            else:
                file_url = f"file://{abs_html_path}"

            await page.goto(file_url)
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=output_png_path, full_page=True)
            await browser.close()

        if os.path.exists(output_png_path):
            return f"成功: 截图已保存到: {output_png_path}", error_output
        return f"错误: Playwright 执行完成但输出文件未创建: {output_png_path}", error_output

    except Exception as e:
        error_output = str(e)
        return f"错误: 处理 '{html_file_path}' 时发生异常 - {e}", error_output


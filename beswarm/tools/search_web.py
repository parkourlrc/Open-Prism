import re
import os
import csv
import time
import json
import httpx
import threading
import urllib.parse
from pathlib import Path

from ..aient.aient.plugins import register_tool, get_url_content # Assuming a similar plugin structure
from ..core import current_work_dir

class ThreadWithReturnValue(threading.Thread):
    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self):
        super().join()
        return self._return

@register_tool()
async def search_web(query: str):
    """
获取 Google 搜索结果。
搜索结果将保存在 csv 文件到 .beswarm/cache 目录下

参数:
    query (str): 要在 Google 上搜索的查询字符串。

返回:
    dict: 包含搜索结果的字典，如果发生错误则包含错误信息。
    """
    thordata_key = (os.environ.get("THORDATA_KEY") or "").strip()

    def _truthy(v: str) -> bool:
        return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}

    def _extract_urls(obj) -> list[str]:
        urls: list[str] = []
        if obj is None:
            return urls
        if isinstance(obj, str):
            return [obj]
        if isinstance(obj, list):
            for item in obj:
                urls.extend(_extract_urls(item))
            return urls
        if isinstance(obj, dict):
            for key in ("url", "link", "href"):
                v = obj.get(key)
                if isinstance(v, str) and v:
                    urls.append(v)
            for key in ("data", "items", "results", "organic"):
                if key in obj:
                    urls.extend(_extract_urls(obj.get(key)))
            return urls
        return urls

    if not thordata_key:
        # Fallback mode: OpenAI-compatible search endpoint on the same host as BASE_URL.
        if not _truthy(os.environ.get("OCEANS_SEARCH_MODE", "")):
            raise ValueError("THORDATA_KEY is not set in environment variables (and OCEANS_SEARCH_MODE is disabled)")

        api_key = (os.environ.get("API_KEY") or "").strip()
        base_url = (os.environ.get("BASE_URL") or "").strip()
        if not api_key or not base_url:
            return {"error": "搜索模式需要先配置 API_KEY 与 BASE_URL。", "code": 400}

        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            return {"error": f"BASE_URL 非法: {base_url}", "code": 400}

        v1_root = f"{parsed.scheme}://{parsed.netloc}"
        if "/v1" in parsed.path:
            v1_root += parsed.path.split("/v1", 1)[0] + "/v1"
        else:
            v1_root += "/v1"
        search_url = v1_root.rstrip("/") + "/search"

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    search_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"q": query},
                )
            if response.status_code >= 400:
                return {"error": f"搜索接口返回错误: {response.status_code} - {response.text}", "code": 400}
            payload = response.json()
        except Exception as e:
            return {"error": f"搜索模式请求失败: {e}", "code": 400}

        urls = []
        for u in _extract_urls(payload):
            u = (u or "").strip()
            if u.startswith(("http://", "https://")):
                urls.append(u.rstrip("/"))
        urls = sorted(set(urls))
        results = {"organic": [{"link": u} for u in urls], "code": 200}
    else:
        api_key = thordata_key

        api_url = "https://scraperapi.thordata.com/request"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {api_key}"  # 请注意：硬编码的 API 密钥
        }
        payload = {
            "engine": "google",
            "q": query,
            "json": "1",
        }
        results = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, headers=headers, data=payload)
                response.raise_for_status()  # 如果状态码是 4xx 或 5xx，则引发 HTTPStatusError
                # The API can return either a JSON object or a string containing JSON.
                # This handles both cases to avoid a TypeError.
                decoded_response = response.json()
                if isinstance(decoded_response, str):
                    results = json.loads(decoded_response)
                else:
                    results = decoded_response
        except httpx.HTTPStatusError as e:
            return {
                "error": f"HTTP error occurred: {e.response.status_code} - {e.response.text}",
                "status_code": e.response.status_code,
                "code": 400
            }
        except httpx.RequestError as e:
            return {
                "error": f"An error occurred while requesting {e.request.url!r}: {e}",
                "request_url": str(e.request.url),
                "code": 400
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to decode JSON response from the API.",
                "response_text": response.text if 'response' in locals() else "No response text available",
                "code": 400
            }
        except Exception as e:
            return {
                "error": f"An unexpected error occurred: {str(e)}",
                "code": 400
            }

    unique_urls = []
    if "error" in results or results.get("code", 200) != 200:
        # print(f"Error fetching search results for '{query}':")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        raise Exception(f"Error fetching search results for '{query}':")
    else:
        # print(f"Search results for '{query}':")
        html_content = results
        # print(json.dumps(results, indent=2, ensure_ascii=False))
        if "Your search did not match any documents" in html_content:
            return "Your search did not match any documents"
        if html_content:
            # 使用正则表达式查找所有 URL
            # 导入 html 和 urllib.parse 模块
            import html

            # 1. 初步提取潜在的 URL 字符串
            #    使用更宽容的正则，允许末尾有非URL字符，后续清理
            # candidate_urls = re.findall(r'https?://[^\s"]+|www\.[^\s"]+', html_content)
            candidate_urls = [url["link"] for url in html_content.get("organic", [])]

            processed_urls = []
            for url_str in candidate_urls:
                # 2. 解码十六进制表示 (例如 \x26 -> &)
                try:
                    def replace_hex(match):
                        return chr(int(match.group(1), 16))
                    url_str = re.sub(r'\\x([0-9a-fA-F]{2})', replace_hex, url_str)
                except ValueError:
                    pass

                # 2.5. 解码 Unicode 转义序列 (例如 \u003d -> =)
                try:
                    def replace_unicode(match):
                        return chr(int(match.group(1), 16))
                    # 只查找和替换 \uXXXX 格式的序列
                    url_str = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, url_str)
                except (ValueError, TypeError):
                    # 如果转换失败（例如，格式错误的序列），则忽略
                    print(f"Error decoding Unicode escape sequence in URL: {url_str}")
                    pass

                # 3. 解码 HTML 实体 (例如 & -> &)
                url_str = html.unescape(url_str)

                # 4. 解码 URL 百分号编码 (例如 %3F -> ?, %3D -> =)
                url_str = urllib.parse.unquote(url_str)

                # 5. 精确截断已知的非 URL 参数或模式
                #    截断 ved= 参数
                if 'ved=' in url_str:
                    url_str = url_str.split('ved=', 1)[0]
                    url_str = url_str.rstrip('&?') # 移除可能残留的末尾 & 或 ?

                # 6. 迭代移除末尾的 HTML 标签
                #    例如 </cite>, <div...>, </span></span>
                old_url_len = -1
                while old_url_len != len(url_str): # 循环直到字符串不再变短
                    old_url_len = len(url_str)
                    # 移除末尾的完整闭合标签, e.g., </div>
                    url_str = re.sub(r'</[^>]+>$', '', url_str)
                    # 移除末尾的开始标签或不完整标签, e.g., <cite or <div
                    # (包括 < 开头到结尾的所有内容)
                    url_str = re.sub(r'<[^>]*$', '', url_str)
                    # 移除末尾的 > 单独字符，如果标签移除后残留
                    url_str = url_str.rstrip('>')


                # 7. 移除末尾的常见非URL字符 (引号，特定标点)
                #    注意顺序，这个应该在HTML标签移除后
                url_str = url_str.rstrip('\'";,.?!<>()[]{}') # '<' 也在这里再次检查

                # 8. 移除末尾单独的 '&' 字符 (在所有其他清理之后)
                url_str = url_str.rstrip('&')
                url_str = url_str.split("#:~:")[0]

                if url_str: #确保URL不为空
                    processed_urls.append(url_str)

            # 定义要过滤的域名列表
            excluded_domains = [
                "www.w3.org",
                "www.google.com",
                "translate.google.com",
                "id.google.com",
                "lens.google.com",
                "ssl.gstatic.com",
                "www.googleadservices.com",
                "gstatic.com",
                "schema.org",
                "maps.google.com",
                "clients6.google.com",
                "ogs.google.com",
                "policies.google.com",
                "support.google.com",
                "tpc.googlesyndication.com",
                "adssettings.google.com",
            ]

            full_excluded_urls = [
                "https://google.com",
                "https://patents.google.com",
                "https://patentpc.com",
                "https://www.mdpi.com",
                "https://trackobit.com",
                "https://www.researchgate.net",
                "https://www.sciencedirect.com",
                "https://rosap.ntl.bts.gov",
                "https://portal.unifiedpatents.com",
                "https://ieeexplore.ieee.org",
                "https://files-backend.assets.thrillshare.com",
                "https://patentimages.storage.googleapis.com",
            ]

            final_urls_before_dedup = []
            for url in processed_urls:
                if not url:
                    continue
                if not any(excluded_domain in url for excluded_domain in excluded_domains):
                    # 9. 进一步规范化
                    # 9a. 移除末尾的 /
                    normalized_url = url.rstrip('/')

                    # 9b. 添加默认协议 (https) 如果缺失
                    if normalized_url and not normalized_url.startswith(('http://', 'https://')):
                        normalized_url = 'https://' + normalized_url

                    if normalized_url and normalized_url not in full_excluded_urls:
                         final_urls_before_dedup.append(normalized_url)

            # 10. 去重
            temp_unique_urls_set = set(final_urls_before_dedup)
            temp_unique_urls_set.discard("https://baike.baidu.com")
            temp_unique_urls_set.discard("https://zhuanlan.zhihu.com")
            unique_urls = sorted(list(temp_unique_urls_set))

    results = unique_urls
    if not results:
        return "No search results returned or results list is empty."

    web_contents_raw = []
    if results and isinstance(results, list) and len(results) > 0:
        # print(f"Fetching content for {len(results)} URLs...")

        threads_with_links = []
        for i, link in enumerate(results):
            print(f"Processing URL {i + 1}/{len(results)}: {link}")
            # Assuming get_url_content is synchronous and returns a string or None
            # content_text = get_url_content(link)
            url_search_thread = ThreadWithReturnValue(target=get_url_content, args=(link,))
            url_search_thread.start()
            threads_with_links.append((url_search_thread, link))

        for thread, link in threads_with_links:
            content_text = thread.join()
            # content_text = thread.get_result()
            if content_text and len(content_text.split("\n\n")) > 10: # Ensure content_text is not None or empty before adding
                web_contents_raw.append({"url": link, "content": str(content_text)}) # Ensure content is string
            else:
                print(f"Warning: Failed to get content or content was empty for URL: {link}")
    elif not results or (isinstance(results, list) and len(results) == 0) :
        print("No search results returned or results list is empty.")
    else:
        print(f"Search results in unexpected format: {type(results)}")

    # print(f"Fetched {len(web_contents_raw)} web contents with text.")

    if not web_contents_raw:
        return "No web content"
    # if not web_contents_raw:
    #     print("No web content with text to process for similarity.")
    #     output_filename = "web_content_filtered.json"
    #     with open(output_filename, "w", encoding="utf-8") as f:
    #         json.dump([], f, indent=2, ensure_ascii=False)
    #     print(f"Empty list saved to {output_filename}")
    #     return

    # output_filename = "web_content.json"
    # with open(output_filename, "w", encoding="utf-8") as f:
    #     json.dump(web_contents_raw, f, indent=2, ensure_ascii=False)

    n = len(web_contents_raw)
    to_keep_flags = [True] * n  # Flags to mark which items to keep

    # print("Starting similarity comparison...")
    # start_time = time.time()
    for i in range(n):
        if not to_keep_flags[i]:  # Skip if item i is already marked for discard
            continue

        content_i = web_contents_raw[i].get('content', "")
        if not isinstance(content_i, str):
            content_i = str(content_i) # Fallback, though str(content_text) above should handle it

        for j in range(i + 1, n):
            if not to_keep_flags[j]:  # Skip if item j is already marked for discard
                continue

            content_j = web_contents_raw[j].get('content', "")
            if not isinstance(content_j, str):
                content_j = str(content_j) # Fallback

            similarity = calculate_similarity(content_i, content_j)
            # print(f"Similarity between {web_contents_raw[i]['url']} and {web_contents_raw[j]['url']}: {similarity:.4f}")

            if similarity > 0.5:
                # print(f"Similarity > 0.9 ({similarity:.4f}) between content from '{web_contents_raw[i]['url']}' and '{web_contents_raw[j]['url']}'. Discarding the latter.")
                to_keep_flags[j] = False  # Discard the second item (item j)

    final_web_content = [web_contents_raw[i] for i in range(n) if to_keep_flags[i]]
    # print(f"Number of items after filtering: {len(final_web_content)}")
    # end_time = time.time()
    # print(f"Time taken: {end_time - start_time:.2f} seconds")
    # output_filename = "web_content_filtered.json"
    # with open(output_filename, "w", encoding="utf-8") as f:
    #     json.dump(final_web_content, f, indent=2, ensure_ascii=False)
    # print(f"Filtered web content saved to {output_filename}")

    if final_web_content:
        work_dir = current_work_dir.get()
        if work_dir:
            output_path = Path(work_dir) / ".beswarm" / "cache"
        else:
            output_path = Path(".")

        output_path.mkdir(parents=True, exist_ok=True)

        # 使用时间戳生成唯一的文件名
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        csv_filename = f"web_content_{timestamp}.csv"
        csv_filepath = output_path / csv_filename

        with open(csv_filepath, "w", newline="", encoding="utf-8") as csvfile:
            # 根据字典中的键定义字段名
            fieldnames = ["query", "url", "content"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # 写入标题行
            writer.writeheader()

            # 写入数据行
            for item in final_web_content:
                item['query'] = query
                if 'content' in item and isinstance(item['content'], str):
                    item['content'] = item['content'].replace('\r', '\\r').replace('\n', '\\n')
                writer.writerow(item)
        return f"已将筛选后的网页内容保存到 {csv_filepath.absolute()}"
    return "No web content"


    # for item in final_web_content:
    #     final_result += item["content"]
    #     final_result += "\n\n"
    # if not final_result:
    #     return "No web content"
    # return final_result

import difflib


def calculate_similarity(string1: str, string2: str) -> float:
    """
    根据您的最终反馈，整合了多级筛选策略来优化性能，且所有修改均在函数内部。

    优化思路:
    1.  长度筛选: 使用“min/max比例法”进行快速检查。如果difflib相似度的
        数学上限已经低于主循环中使用的阈值(0.5)，则直接退出。
    2.  分块筛选: 采纳您提出的分块思想。我们将较短的字符串切分为20个块，
        并快速计算有多少块也出现在另一个字符串中。这是一个成本远低于difflib的内容预筛选。
        - 如果重合度很高 (>80%)，可以提前判断为相似。
        - 如果重合度很低 (<20%)，可以提前判断为不相似。
    3.  最终精确计算: 只有当相似度处于“中间地带”，前两级筛选无法确定时，
        我们才动用最精确但最耗时的difflib进行最终裁决。
    """
    len1, len2 = len(string1), len(string2)

    # 第一级筛选: 长度检查 (非常廉价)
    # 2.0 * min(len1, len2) / (len1 + len2) 是 difflib.ratio() 的数学上限。
    # 这里的阈值0.5必须与主循环中的 `if similarity > 0.5:` 保持一致。
    # print(len1, len2, (2.0 * min(len1, len2) / (len1 + len2)))
    if not len1 or not len2 or (2.0 * min(len1, len2) / (len1 + len2)) < 0.5:
        return 0.0

    # 对于短字符串，分块没有意义，直接比较
    if len1 < 40 or len2 < 40:
        return difflib.SequenceMatcher(None, string1, string2).ratio()

    # 第二级筛选: 分块检查 (中等成本)
    shorter_str, longer_str = (string1, string2) if len1 < len2 else (string2, string1)

    num_chunks = 1000
    chunk_size = len(shorter_str) // num_chunks

    # 因为上面已经有len < 40的检查，这里的chunk_size不可能为0，所以之前的if chunk_size == 0是冗余的。
    matching_chunks = 0
    for i in range(num_chunks):
        start = i * chunk_size
        chunk = shorter_str[start:start+chunk_size]
        if chunk in longer_str:
            matching_chunks += 1

    match_ratio = matching_chunks / num_chunks
    # print(matching_chunks, match_ratio)

    # 根据分块匹配率进行判断，这些阈值是基于经验的启发式规则。
    if match_ratio > 0.8:  # 超过80%的块匹配，几乎可以肯定是高度相似
        return match_ratio # 返回一个确保能通过主循环判断的高值
    if match_ratio < 0.2: # 少于20%的块匹配，几乎不可能相似
        return match_ratio

    # 第三级：最终精确计算 (高成本)
    return difflib.SequenceMatcher(None, string1, string2).ratio()

if __name__ == '__main__':
    import asyncio
    import re

    async def main():
        # 示例用法
        # search_query = "美国"
        # search_query = "machine learning models for higher heating value prediction using proximate vs ultimate analysis"
        # search_query = "patent driver cognitive load monitoring micro-expression thermal imaging fusion"
        search_query = "deep learning models for siRNA activity"
        print(f"Performing web search for: '{search_query}'")
        results = await search_web(search_query)  # results is a list of URLs

        print(results)

    asyncio.run(main())
    # print(get_url_content("https://www.ces.org.cn/res/ces/2308/69c936072d86b5161d7cca95c30ea832.pdf"))

# python -m beswarm.tools.search_web

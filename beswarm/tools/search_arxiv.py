import requests
import csv
from datetime import datetime
from ..aient.aient.plugins import register_tool

@register_tool()
def search_arxiv(query, max_results=5, sort_by='relevance', sort_order='descending',
                categories=None, date_range=None, authors=None, include_abstract=True):
    """
使用关键词搜索arXiv论文，并返回相关论文的信息。

此工具允许你通过关键词、类别、日期范围和作者等条件搜索arXiv上的学术论文。
你可以指定排序方式和返回结果数量，获取最相关或最新的研究论文信息。

如果要查询具体架构，直接查询架构名称即可。

for example:

correct:
<search_arxiv>
<query>
NoProp
</query>
</search_arxiv>

incorrect:
<search_arxiv>
<query>
NoProp: Training Neural Networks without Back-propagation or Forward-propagation
</query>
</search_arxiv>

参数:
    query: 搜索关键词，支持AND, OR, NOT等布尔操作符和引号精确匹配（如："quantum computing"）
    max_results: 返回结果的最大数量，默认为5篇论文
    sort_by: 排序方式，可选值为'relevance'（相关性）或'lastUpdatedDate'（最后更新日期），默认为'relevance'
    sort_order: 排序顺序，可选值为'ascending'（升序）或'descending'（降序），默认为'descending'
    categories: arXiv类别限制，可以是单个类别或类别列表（如：'cs.CV'或['cs.AI', 'cs.CL']）
    date_range: 日期范围限制，格式为字典{'from': 'YYYY-MM-DD', 'to': 'YYYY-MM-DD'}
    authors: 作者限制，可以是单个作者名称或作者列表
    include_abstract: 是否包含论文摘要，默认为True

返回:
    包含搜索结果的字典列表，每个字典包含论文的标题、作者、摘要、发布日期、最后更新日期、arXiv ID、类别和PDF链接等信息
    """
    try:
        base_url = "https://export.arxiv.org/api/query"

        # 构建查询参数
        search_query = query
        # search_query = f"all:{query}"

        # 添加类别过滤
        if categories:
            if isinstance(categories, list):
                cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
                search_query += f" AND ({cat_query})"
            else:
                search_query += f" AND cat:{categories}"

        # 添加作者过滤
        if authors:
            if isinstance(authors, list):
                author_query = " OR ".join([f"au:\"{author}\"" for author in authors])
                search_query += f" AND ({author_query})"
            else:
                search_query += f" AND au:\"{authors}\""

        print(search_query)

        # 添加日期过滤
        # arXiv API不直接支持日期范围过滤，需要在结果中过滤

        params = {
            "search_query": search_query,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order
        }

        # 发送请求
        response = requests.get(base_url, params=params)

        if response.status_code != 200:
            return f"<tool_error>API请求失败，状态码 {response.status_code}</tool_error>"

        # 解析结果（arXiv API返回的是Atom XML格式）
        # 这里使用简化的解析方式，在实际使用中可能需要更复杂的XML解析
        import xml.etree.ElementTree as ET

        root = ET.fromstring(response.content)

        # 定义arXiv命名空间
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }

        results = []

        # 解析每个条目
        for entry in root.findall('.//atom:entry', ns):
            published = entry.find('./atom:published', ns).text
            updated = entry.find('./atom:updated', ns).text

            # 应用日期过滤
            if date_range:
                pub_date = datetime.strptime(published.split('T')[0], '%Y-%m-%d')

                if 'from' in date_range and datetime.strptime(date_range['from'], '%Y-%m-%d') > pub_date:
                    continue

                if 'to' in date_range and datetime.strptime(date_range['to'], '%Y-%m-%d') < pub_date:
                    continue

            # 获取论文ID
            id_url = entry.find('./atom:id', ns).text
            arxiv_id = id_url.split('/abs/')[-1]

            # 获取标题和去除多余空格
            title = ' '.join(entry.find('./atom:title', ns).text.split())

            # 获取作者
            authors_list = []
            for author in entry.findall('./atom:author/atom:name', ns):
                authors_list.append(author.text)

            # 获取分类
            categories_list = []
            for category in entry.findall('./arxiv:primary_category', ns):
                categories_list.append(category.get('term'))
            for category in entry.findall('./atom:category', ns):
                cat_term = category.get('term')
                if cat_term not in categories_list:
                    categories_list.append(cat_term)

            # 应用严格的类别过滤，确保论文的所有类别都符合用户的要求
            if categories:
                user_specified_categories = categories if isinstance(categories, list) else [categories]

                allowed_prefixes = []
                for pattern in user_specified_categories:
                    if pattern.endswith('*'):
                        allowed_prefixes.append(pattern[:-1])
                    else:
                        allowed_prefixes.append(pattern)

                all_paper_categories_match = True
                for paper_cat in categories_list:
                    # 检查当前论文的每个分类是否至少匹配一个用户指定的模式前缀
                    if not any(paper_cat.startswith(prefix) for prefix in allowed_prefixes):
                        all_paper_categories_match = False
                        break

                if not all_paper_categories_match:
                    continue  # 如果有任何一个分类不匹配，就跳过这篇论文

            # 获取摘要
            abstract = ""
            if include_abstract:
                abstract_elem = entry.find('./atom:summary', ns)
                if abstract_elem is not None and abstract_elem.text:
                    abstract = ' '.join(abstract_elem.text.split())

            # 获取PDF链接
            pdf_link = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            paper_info = {
                "title": title,
                "authors": authors_list,
                "abstract": abstract if include_abstract else "",
                "published_date": published.split('T')[0],
                "last_updated": updated.split('T')[0],
                "arxiv_id": arxiv_id,
                "categories": categories_list,
                "pdf_url": pdf_link,
                "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}"
            }

            results.append(paper_info)

        if not results:
            return f"<tool_error>未找到与查询'{query}'匹配的论文</tool_error>"

        return results

    except Exception as e:
        return f"<tool_error>搜索arXiv论文时发生错误: {str(e)}</tool_error>"

if __name__ == '__main__':
    # 简单的测试用例
    # python -m beswarm.tools.search_arxiv
    test_query = "NoProp"
    test_query = '"Attention Is All You Need"'
    test_query = '(all:"sparse autoencoders" OR all:"sparse autoencoder" OR (all:SAE AND NOT au:SAE))'

    print(f"使用关键词 '{test_query}' 测试搜索...")

    search_results = search_arxiv(query=test_query, max_results=1000, categories='cs*', sort_by='lastUpdatedDate')

    if isinstance(search_results, str):
        # 如果返回的是错误信息字符串，则打印错误
        print(search_results)
    elif isinstance(search_results, list):
        if search_results:
            print("\n搜索结果:")
            for i, paper in enumerate(search_results):
                print(f"--- 论文 {i+1} ---")
                print(f"  标题: {paper['title']}")
                print(f"  作者: {', '.join(paper['authors'])}")
                print(f"  发布日期: {paper['published_date']}")
                print(f"  arXiv ID: {paper['arxiv_id']}")
                print(f"  领域: {paper['categories']}")
                print(f"  PDF链接: {paper['pdf_url']}")
                print(f"  摘要: {paper['abstract'][:150]}...") # 打印摘要前150个字符
                print("-" * 20)

            # 将结果保存到CSV文件
            csv_filename = 'arxiv_search_results.csv'
            print(f"\n正在将 {len(search_results)} 条结果保存到 {csv_filename}...")

            try:
                with open(csv_filename, mode='w', newline='', encoding='utf-8') as csv_file:
                    # 使用第一个数据项的键作为CSV文件的标题
                    fieldnames = search_results[0].keys()
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                    writer.writeheader()
                    for paper in search_results:
                        # 转换列表为字符串以便写入CSV
                        paper_for_csv = paper.copy()
                        if 'authors' in paper_for_csv and isinstance(paper_for_csv['authors'], list):
                            paper_for_csv['authors'] = ', '.join(paper_for_csv['authors'])
                        if 'categories' in paper_for_csv and isinstance(paper_for_csv['categories'], list):
                            paper_for_csv['categories'] = ', '.join(paper_for_csv['categories'])

                        writer.writerow(paper_for_csv)

                print(f"结果已成功保存到 {csv_filename}")

            except IOError as e:
                print(f"错误：无法写入文件 {csv_filename}: {e}")

        else:
            print("未找到相关论文。")
    else:
        print("返回了未知格式的结果。")

    # # 测试带有分类过滤的搜索
    # print("\n使用关键词 'computer vision' 和分类 'cs.CV' 测试搜索...")
    # cv_results = search_arxiv(query="computer vision", categories='cs.CV', max_results=2)
    # if isinstance(cv_results, str):
    #     print(cv_results)
    # elif isinstance(cv_results, list):
    #      if cv_results:
    #         print("\n搜索结果:")
    #         for i, paper in enumerate(cv_results):
    #             print(f"--- 论文 {i+1} ---")
    #             print(f"  标题: {paper['title']}")
    #             print(f"  链接: {paper['arxiv_url']}")
    #             print("-" * 20)
    #      else:
    #         print("未找到相关论文。")
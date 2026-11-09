import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

def clean_text(text):
    """清理文本,移除多余的空白字符"""
    if text:
        return re.sub(r'\s+', ' ', text).strip()
    return ''

def scrape_thesis_metadata(url):
    """抓取论文元数据"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 找到目标表格
        metadata = {}
        
        # 查找所有表格头部，从format_0_table到format_0_table_th_22
        for i in range(23):  # 0到22
            th_id = f"format_0_table_th_{i}" if i > 0 else "format_0_table"
            th_element = soup.find('th', id=th_id)
            
            if th_element:
                # 获取标题（th的文本）
                key = clean_text(th_element.get_text())
                
                # 获取对应的数据（td的文本）
                # 通常td在th的下一个兄弟元素
                td_element = th_element.find_next('td')
                if td_element:
                    value = clean_text(td_element.get_text())
                    
                    # 只保存有效的键值对
                    if key and value:
                        metadata[key] = value
        # 查找所有 class="stdncl2" 的td元素
        td_elements = soup.find_all('td', class_='stdncl2')
        for td in td_elements:
            # 获取对应的th元素
            th = td.find_previous('th')
            if th:
                key = clean_text(th.get_text())
                value = clean_text(td.get_text())
                if key and value:
                    metadata[key] = value
        
        # 转换为DataFrame
        df = pd.DataFrame([metadata])
        
        # 保存为CSV
        df.to_csv('thesis_metadata.csv', index=False, encoding='utf-8-sig')
        print("数据已保存到 thesis_metadata.csv")
        
        return metadata
        
    except Exception as e:
        print(f"抓取失败: {str(e)}")
        return None

if __name__ == "__main__":
    url = "https://hdl.handle.net/11296/g2fmfa"
    metadata = scrape_thesis_metadata(url)
    if metadata:
        print("成功抓取以下数据:")
        for key, value in metadata.items():
            print(f"{key}: {value}")

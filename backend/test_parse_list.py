"""
Test parsing the list array from Mail.ru Cloud
"""
import sys
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

url = "https://cloud.mail.ru/public/ZVeV/Mq5HoaFGX"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

response = session.get(url, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

scripts = soup.find_all('script')
for script in scripts:
    if script.string and 'weblink' in script.string.lower() and 'list' in script.string.lower():
        script_content = script.string
        
        # Find the list array
        start_idx = script_content.find('"list"')
        if start_idx != -1:
            array_start = script_content.find('[', start_idx)
            if array_start != -1:
                bracket_count = 1
                array_end = array_start + 1
                for i in range(array_start + 1, len(script_content)):
                    if script_content[i] == '[':
                        bracket_count += 1
                    elif script_content[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            array_end = i + 1
                            break
                
                array_str = script_content[array_start:array_end]
                list_data = json.loads(array_str)
                
                print(f"Found {len(list_data)} items in list:")
                print("=" * 80)
                
                for item in list_data:
                    print(f"Name: {item.get('name')}")
                    print(f"Type: {item.get('type')} / Kind: {item.get('kind')}")
                    print(f"Weblink: {item.get('weblink')}")
                    print(f"Count: folders={item.get('count', {}).get('folders')}, files={item.get('count', {}).get('files')}")
                    print(f"Size: {item.get('size')}")
                    print("-" * 80)


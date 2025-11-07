"""
Extract and parse JSON from Mail.ru Cloud page
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
print(f"Found {len(scripts)} script tags\n")

for i, script in enumerate(scripts):
    if script.string and 'weblink' in script.string.lower():
        print(f"Script {i}:")
        print("-" * 80)
        
        # Try to find JSON object
        # Look for window.__INITIAL_STATE__ or similar
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
            r'window\.__DATA__\s*=\s*(\{.*?\});',
            r'var\s+__INITIAL_STATE__\s*=\s*(\{.*?\});',
            r'const\s+__INITIAL_STATE__\s*=\s*(\{.*?\});',
        ]
        
        found_json = False
        for pattern in json_patterns:
            match = re.search(pattern, script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    print(f"Found JSON with pattern: {pattern}")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
                    found_json = True
                    break
                except:
                    pass
        
        if not found_json:
            # Look for "list" array
            list_match = re.search(r'"list"\s*:\s*(\[.*?\])', script.string, re.DOTALL)
            if list_match:
                try:
                    # Try to extract the full array
                    list_str = list_match.group(1)
                    # Find the complete array (might be nested)
                    bracket_count = 0
                    start_idx = script.string.find('"list"')
                    if start_idx != -1:
                        array_start = script.string.find('[', start_idx)
                        if array_start != -1:
                            array_end = array_start
                            bracket_count = 1
                            for j in range(array_start + 1, len(script.string)):
                                if script.string[j] == '[':
                                    bracket_count += 1
                                elif script.string[j] == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        array_end = j + 1
                                        break
                            
                            array_str = script.string[array_start:array_end]
                            print(f"Found list array:")
                            print(array_str[:1000])
                            
                            # Try to parse items
                            items = re.findall(r'\{[^}]*"name"[^}]*\}', array_str)
                            print(f"\nFound {len(items)} items:")
                            for item_str in items[:5]:
                                print(f"  {item_str[:100]}")
                            
                except Exception as e:
                    print(f"Error parsing: {e}")
        
        print("\n" + "=" * 80 + "\n")


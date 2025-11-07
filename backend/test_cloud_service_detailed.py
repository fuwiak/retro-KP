"""
Detailed test script for Mail.ru Cloud folder parsing
Shows HTML structure and tries to find files
"""
import sys
import json
import re
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

import requests
from bs4 import BeautifulSoup

def test_mailru_folder_detailed():
    """Detailed test of Mail.ru Cloud folder HTML structure"""
    url = "https://cloud.mail.ru/public/ZVeV/Mq5HoaFGX"
    
    print("=" * 80)
    print("DETAILED TEST: Mail.ru Cloud Folder HTML Structure")
    print("=" * 80)
    print(f"URL: {url}")
    print()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    })
    
    try:
        print("1. Fetching page...")
        response = session.get(url, timeout=10)
        response.raise_for_status()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Content length: {len(response.text)} bytes")
        print()
        
        print("2. Parsing HTML...")
        soup = BeautifulSoup(response.text, 'html.parser')
        print()
        
        print("3. Looking for script tags with data...")
        scripts = soup.find_all('script')
        print(f"   Found {len(scripts)} script tags")
        
        json_data_found = []
        for i, script in enumerate(scripts):
            if script.string:
                # Look for JSON patterns
                json_patterns = [
                    r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
                    r'window\.__DATA__\s*=\s*(\{.*?\});',
                    r'var\s+data\s*=\s*(\{.*?\});',
                    r'const\s+data\s*=\s*(\{.*?\});',
                    r'"files"\s*:\s*\[(.*?)\]',
                    r'"items"\s*:\s*\[(.*?)\]',
                    r'"list"\s*:\s*\[(.*?)\]',
                ]
                
                for pattern in json_patterns:
                    matches = re.findall(pattern, script.string, re.DOTALL)
                    if matches:
                        print(f"   ✓ Script {i}: Found JSON pattern!")
                        json_data_found.append((i, pattern, matches[0][:500] if len(matches[0]) > 500 else matches[0]))
        
        if json_data_found:
            print(f"   Found {len(json_data_found)} potential JSON data sources")
            for idx, pattern, data in json_data_found[:3]:  # Show first 3
                print(f"   Script {idx}, pattern: {pattern[:50]}...")
                print(f"   Data preview: {data[:200]}...")
        else:
            print("   ⚠️  No JSON data found in script tags")
        print()
        
        print("4. Looking for links to files...")
        links = soup.find_all('a', href=True)
        print(f"   Found {len(links)} links total")
        
        file_links = []
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Check for file extensions
            if any(ext in href.lower() for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp']):
                file_links.append({
                    'href': href,
                    'text': text,
                    'full_url': href if href.startswith('http') else f"https://cloud.mail.ru{href}" if href.startswith('/') else f"{url}/{href}"
                })
        
        print(f"   Found {len(file_links)} potential file links:")
        for i, file_link in enumerate(file_links[:10], 1):  # Show first 10
            print(f"   {i}. {file_link['text'] or file_link['href']}")
            print(f"      URL: {file_link['full_url']}")
        print()
        
        print("5. Looking for data attributes...")
        elements_with_data = soup.find_all(attrs={'data-name': True})
        print(f"   Found {len(elements_with_data)} elements with data-name")
        for elem in elements_with_data[:5]:
            print(f"   - data-name: {elem.get('data-name')}")
            print(f"     href: {elem.get('href', 'N/A')}")
        print()
        
        print("6. Looking for div/span elements that might contain file info...")
        file_containers = soup.find_all(['div', 'span'], class_=re.compile(r'file|item|entry|list', re.I))
        print(f"   Found {len(file_containers)} potential file containers")
        for container in file_containers[:5]:
            classes = ' '.join(container.get('class', []))
            print(f"   - Classes: {classes}")
            print(f"     Text: {container.get_text(strip=True)[:50]}")
            link = container.find('a', href=True)
            if link:
                print(f"     Link: {link.get('href')}")
        print()
        
        print("7. Checking for API endpoints in page...")
        # Look for API URLs in the page
        api_patterns = [
            r'api/v2/folder[^"\']*',
            r'weblink[^"\']*',
            r'token[^"\']*',
        ]
        for pattern in api_patterns:
            matches = re.findall(pattern, response.text, re.I)
            if matches:
                print(f"   Found API pattern: {pattern}")
                for match in set(matches[:5]):
                    print(f"     - {match[:100]}")
        print()
        
        print("8. Full page structure summary:")
        print(f"   - Title: {soup.title.string if soup.title else 'N/A'}")
        print(f"   - Meta tags: {len(soup.find_all('meta'))}")
        print(f"   - Script tags: {len(soup.find_all('script'))}")
        print(f"   - Link tags: {len(soup.find_all('link'))}")
        print(f"   - Div tags: {len(soup.find_all('div'))}")
        print(f"   - Span tags: {len(soup.find_all('span'))}")
        print()
        
        print("9. Sample of page content (looking for 'file', 'pdf', 'png'):")
        content_lower = response.text.lower()
        keywords = ['file', 'pdf', 'png', 'jpg', 'download', 'folder', 'list']
        for keyword in keywords:
            count = content_lower.count(keyword)
            print(f"   - '{keyword}': {count} occurrences")
        
        # Show context around first occurrence of 'pdf'
        if 'pdf' in content_lower:
            idx = content_lower.find('pdf')
            context = response.text[max(0, idx-100):idx+200]
            print(f"   - Context around 'pdf':")
            print(f"     {context[:300]}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mailru_folder_detailed()


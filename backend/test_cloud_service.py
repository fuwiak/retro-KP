"""
Test script for Mail.ru Cloud folder parsing
"""
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.cloud_service import CloudService

def test_mailru_folder():
    """Test parsing Mail.ru Cloud folder"""
    url = "https://cloud.mail.ru/public/ZVeV/Mq5HoaFGX"
    
    print("=" * 80)
    print("TEST: Mail.ru Cloud Folder Parsing")
    print("=" * 80)
    print(f"URL: {url}")
    print()
    
    cloud_service = CloudService()
    
    try:
        print("1. Fetching folder page...")
        result = cloud_service.parse_mailru_folder(url)
        
        print(f"✓ Successfully fetched folder")
        print()
        
        print("2. Parsed data:")
        print(f"   Folder URL: {result.get('folder_url', 'N/A')}")
        print(f"   Files found: {len(result.get('files', []))}")
        print()
        
        if result.get('files'):
            print("3. Files list:")
            for i, file in enumerate(result.get('files', []), 1):
                print(f"   {i}. {file.get('name', 'N/A')}")
                print(f"      URL: {file.get('url', 'N/A')}")
                print(f"      Download URL: {file.get('download_url', 'N/A')}")
                print(f"      Path: {file.get('path', 'N/A')}")
                print()
        else:
            print("3. ⚠️  No files found!")
            print()
            print("Debugging information:")
            print("   - Trying to fetch raw HTML...")
            
            # Try to get raw response
            import requests
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            print(f"   - Status code: {response.status_code}")
            print(f"   - Content length: {len(response.text)} bytes")
            print(f"   - First 500 chars of HTML:")
            print("   " + "-" * 76)
            print("   " + response.text[:500].replace('\n', '\n   '))
            print("   " + "-" * 76)
        
        print()
        print("4. Full JSON response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print()
        print("Exception details:")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_mailru_folder()


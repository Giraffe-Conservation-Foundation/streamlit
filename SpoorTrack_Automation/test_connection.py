#!/usr/bin/env python3
"""
Test EarthRanger connection and find correct API endpoint
"""

import requests

def test_earthranger_connection():
    """Test various EarthRanger endpoints to find the right one"""
    
    base_url = "https://twiga.pamdas.org"
    
    print(f"Testing EarthRanger connection to: {base_url}")
    print("=" * 50)
    
    # Test different possible endpoints
    endpoints_to_test = [
        "/",
        "/api/",
        "/api/v1.0/",
        "/api/v1/",
        "/api/v2.0/",
        "/admin/",
        "/accounts/login/"
    ]
    
    for endpoint in endpoints_to_test:
        url = f"{base_url}{endpoint}"
        try:
            print(f"Testing: {url}")
            response = requests.get(url, timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  SUCCESS! Found working endpoint")
                # Try to see if it's an API endpoint
                if 'api' in endpoint:
                    try:
                        json_data = response.json()
                        print(f"  JSON Response: {str(json_data)[:100]}...")
                    except:
                        print(f"  HTML Response (not API)")
                else:
                    print(f"  HTML Response")
            elif response.status_code == 401:
                print(f"  AUTHENTICATION REQUIRED (API endpoint found!)")
            elif response.status_code == 403:
                print(f"  FORBIDDEN (server reachable, may need auth)")
            elif response.status_code == 404:
                print(f"  Not found")
            else:
                print(f"  Other response")
                
        except requests.exceptions.Timeout:
            print(f"  TIMEOUT")
        except requests.exceptions.ConnectionError:
            print(f"  CONNECTION ERROR")
        except Exception as e:
            print(f"  ERROR: {e}")
        
        print()
    
    print("=" * 50)
    print("RECOMMENDATIONS:")
    print("1. If you see 401/403 responses, the server is working")
    print("2. If you see 200 responses with JSON, that's your API endpoint")
    print("3. If all endpoints fail, check the server URL with your admin")
    print("4. Common URLs: https://yourorg.pamdas.org/api/v1.0/")

if __name__ == "__main__":
    test_earthranger_connection()

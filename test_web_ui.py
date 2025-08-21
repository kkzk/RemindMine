"""Test script for RemindMine Web UI functionality."""

import asyncio
import aiohttp
import json
from datetime import datetime


class WebUITester:
    """Test class for Web UI endpoints."""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_health_check(self):
        """Test health check endpoint."""
        print("🔍 Testing health check...")
        async with self.session.get(f"{self.base_url}/health") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Health check passed: {data['status']}")
                return True
            else:
                print(f"❌ Health check failed: {response.status}")
                return False
    
    async def test_web_dashboard(self):
        """Test web dashboard access."""
        print("🌐 Testing web dashboard...")
        async with self.session.get(f"{self.base_url}/") as response:
            if response.status == 200:
                content = await response.text()
                if "RemindMine AI Agent" in content:
                    print("✅ Web dashboard loaded successfully")
                    return True
                else:
                    print("❌ Web dashboard content invalid")
                    return False
            else:
                print(f"❌ Web dashboard failed to load: {response.status}")
                return False
    
    async def test_issues_api(self):
        """Test issues API endpoint."""
        print("📋 Testing issues API...")
        async with self.session.get(f"{self.base_url}/api/web/issues") as response:
            if response.status == 200:
                data = await response.json()
                issues_count = len(data.get('issues', []))
                print(f"✅ Issues API returned {issues_count} issues")
                return True
            else:
                print(f"❌ Issues API failed: {response.status}")
                return False
    
    async def test_projects_api(self):
        """Test projects API endpoint."""
        print("🏗️ Testing projects API...")
        async with self.session.get(f"{self.base_url}/api/web/projects") as response:
            if response.status == 200:
                data = await response.json()
                projects_count = len(data)
                print(f"✅ Projects API returned {projects_count} projects")
                return True
            else:
                print(f"❌ Projects API failed: {response.status}")
                return False
    
    async def test_settings_api(self):
        """Test settings API endpoints."""
        print("⚙️ Testing settings API...")
        
        # Test GET settings
        async with self.session.get(f"{self.base_url}/api/web/settings") as response:
            if response.status == 200:
                settings = await response.json()
                print(f"✅ Settings GET successful: auto_advice={settings.get('auto_advice_enabled')}")
                
                # Test POST settings (toggle auto-advice)
                new_state = not settings.get('auto_advice_enabled', True)
                async with self.session.post(
                    f"{self.base_url}/api/web/settings/auto-advice",
                    json={"enabled": new_state}
                ) as post_response:
                    if post_response.status == 200:
                        result = await post_response.json()
                        print(f"✅ Settings POST successful: auto_advice={result.get('enabled')}")
                        
                        # Restore original state
                        await self.session.post(
                            f"{self.base_url}/api/web/settings/auto-advice",
                            json={"enabled": settings.get('auto_advice_enabled', True)}
                        )
                        return True
                    else:
                        print(f"❌ Settings POST failed: {post_response.status}")
                        return False
            else:
                print(f"❌ Settings GET failed: {response.status}")
                return False
    
    async def test_static_files(self):
        """Test static file serving."""
        print("📁 Testing static files...")
        
        # Test CSS
        async with self.session.get(f"{self.base_url}/static/css/style.css") as response:
            if response.status == 200:
                print("✅ CSS file loaded successfully")
            else:
                print(f"❌ CSS file failed to load: {response.status}")
                return False
        
        # Test JavaScript
        async with self.session.get(f"{self.base_url}/static/js/app.js") as response:
            if response.status == 200:
                print("✅ JavaScript file loaded successfully")
                return True
            else:
                print(f"❌ JavaScript file failed to load: {response.status}")
                return False
    
    async def run_all_tests(self):
        """Run all tests and report results."""
        print("🚀 Starting RemindMine Web UI Tests")
        print("=" * 50)
        
        tests = [
            ("Health Check", self.test_health_check),
            ("Web Dashboard", self.test_web_dashboard),
            ("Issues API", self.test_issues_api),
            ("Projects API", self.test_projects_api),
            ("Settings API", self.test_settings_api),
            ("Static Files", self.test_static_files),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = await test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
                results.append((test_name, False))
            print()
        
        # Summary
        print("=" * 50)
        print("📊 Test Results Summary")
        print("=" * 50)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status:10} {test_name}")
        
        print("=" * 50)
        print(f"Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Web UI is working correctly.")
        else:
            print("⚠️ Some tests failed. Please check the issues above.")
        
        return passed == total


async def main():
    """Main test runner."""
    print(f"🕐 Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    async with WebUITester() as tester:
        success = await tester.run_all_tests()
    
    if success:
        print("\n🏆 RemindMine Web UI is ready for use!")
        print("Access it at: http://localhost:8000")
    else:
        print("\n💡 Please ensure RemindMine server is running before testing.")
        print("Start server with: uv run python main.py")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Test the fixed journal retrieval methods."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from remindmine.redmine_client import RedmineClient
from remindmine.config import config

def test_fixed_methods():
    """Test the fixed journal retrieval methods."""
    
    client = RedmineClient(
        base_url=config.redmine_url,
        api_key=config.redmine_api_key,
        disable_proxy=config.disable_proxy,
        ssl_verify=config.ssl_verify
    )
    
    print("=== Testing fixed get_all_issues_with_journals (limited test) ===")
    # Test with a small subset to avoid long execution
    # We'll simulate the method with just a few issues
    issues_list = client.get_issues(limit=3)
    print(f"Found {len(issues_list)} issues")
    
    issues_with_journals = []
    for issue in issues_list:
        issue_id = issue['id']
        detailed_issue = client.get_issue(issue_id)
        if detailed_issue:
            print(f"Issue #{issue_id}: {'✅ Has journals' if 'journals' in detailed_issue else '❌ No journals'}")
            if 'journals' in detailed_issue:
                print(f"   Journal count: {len(detailed_issue['journals'])}")
            issues_with_journals.append(detailed_issue)
    
    print(f"\nSuccessfully retrieved {len(issues_with_journals)} issues with journals")
    
    print("\n=== Testing get_issues_since without journals ===")
    from datetime import datetime, timedelta
    since_time = datetime.now() - timedelta(days=30)  # Last 30 days
    recent_issues = client.get_issues_since(since_time, include_journals=False)
    print(f"Found {len(recent_issues)} recent issues (without journals)")
    
    if recent_issues:
        issue = recent_issues[0]
        print(f"First issue has journals: {'journals' in issue}")
    
    print("\n=== Testing get_issues_since with journals ===")
    if recent_issues:
        # Test with just the first issue to avoid long execution
        single_issue_id = recent_issues[0]['id']
        single_issue_since = client.get_issues_since(since_time, include_journals=True)
        if single_issue_since:
            issue = single_issue_since[0]
            print(f"First issue has journals: {'journals' in issue}")
            if 'journals' in issue:
                print(f"Journal count: {len(issue['journals'])}")

if __name__ == "__main__":
    try:
        test_fixed_methods()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

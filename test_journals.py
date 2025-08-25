#!/usr/bin/env python3
"""Test script to verify if journals are being fetched correctly."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from remindmine.redmine_client import RedmineClient
from remindmine.config import config
import json

def test_journals():
    """Test if journals are being fetched correctly."""
    
    client = RedmineClient(
        base_url=config.redmine_url,
        api_key=config.redmine_api_key,
        disable_proxy=config.disable_proxy,
        ssl_verify=config.ssl_verify
    )
    
    print("=== Testing get_issues method ===")
    # Get a few issues to test
    issues = client.get_issues(limit=3)
    
    if not issues:
        print("No issues found")
        return
    
    print(f"Retrieved {len(issues)} issues")
    
    for i, issue in enumerate(issues, 1):
        print(f"\n--- Issue #{issue['id']} ---")
        print(f"Subject: {issue['subject']}")
        
        # Check if journals key exists
        if 'journals' in issue:
            journals = issue['journals']
            print(f"Journals count: {len(journals)}")
            
            # Show details of each journal
            for j, journal in enumerate(journals):
                print(f"  Journal {j+1}:")
                print(f"    ID: {journal.get('id', 'N/A')}")
                print(f"    User: {journal.get('user', {}).get('name', 'N/A')}")
                print(f"    Created: {journal.get('created_on', 'N/A')}")
                print(f"    Notes: {journal.get('notes', 'N/A')[:100]}...")
                if 'details' in journal and journal['details']:
                    print(f"    Details: {len(journal['details'])} items")
        else:
            print("❌ No 'journals' key found in issue data")
            print("Available keys:", list(issue.keys()))
    
    print("\n=== Testing get_issue method (single issue) ===")
    if issues:
        issue_id = issues[0]['id']
        single_issue = client.get_issue(issue_id)
        
        if single_issue:
            print(f"Single issue #{single_issue['id']}")
            if 'journals' in single_issue:
                print(f"Journals count: {len(single_issue['journals'])}")
                print("✅ Journals successfully retrieved from get_issue")
            else:
                print("❌ No 'journals' key found in single issue data")
                print("Available keys:", list(single_issue.keys()))
        else:
            print(f"❌ Failed to retrieve issue #{issue_id}")

def test_raw_api():
    """Test raw API call to see what Redmine returns."""
    print("\n=== Testing raw API response ===")
    
    import requests
    session = requests.Session()
    session.headers.update({
        'X-Redmine-API-Key': config.redmine_api_key,
        'Content-Type': 'application/json'
    })
    
    # Test with explicit include parameter
    url = f"{config.redmine_url}/issues.json"
    params = {
        'limit': 1,
        'include': 'journals'
    }
    
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        print(f"Raw API response keys: {list(data.keys())}")
        
        if 'issues' in data and data['issues']:
            issue = data['issues'][0]
            print(f"Issue keys: {list(issue.keys())}")
            
            if 'journals' in issue:
                print(f"✅ Journals found in raw API response: {len(issue['journals'])} journals")
                # Show first journal structure
                if issue['journals']:
                    first_journal = issue['journals'][0]
                    print(f"First journal keys: {list(first_journal.keys())}")
            else:
                print("❌ No journals in raw API response")
        
    except Exception as e:
        print(f"❌ Raw API test failed: {e}")

if __name__ == "__main__":
    try:
        test_journals()
        test_raw_api()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

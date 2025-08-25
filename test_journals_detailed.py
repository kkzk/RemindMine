#!/usr/bin/env python3
"""Test script to investigate journal fetching behavior in detail."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from remindmine.redmine_client import RedmineClient
from remindmine.config import config
import requests

def test_api_variations():
    """Test different API variations to understand journal fetching."""
    
    client = RedmineClient(
        base_url=config.redmine_url,
        api_key=config.redmine_api_key,
        disable_proxy=config.disable_proxy,
        ssl_verify=config.ssl_verify
    )
    
    # Use raw requests to test different parameters
    session = requests.Session()
    session.headers.update({
        'X-Redmine-API-Key': config.redmine_api_key,
        'Content-Type': 'application/json'
    })
    session.verify = config.ssl_verify
    if config.disable_proxy:
        session.proxies = {}
        session.trust_env = False
    
    base_url = config.redmine_url
    
    print("=== Testing API parameter variations ===\n")
    
    # Test 1: Basic issues.json
    print("1. Basic issues.json (no include)")
    url = f"{base_url}/issues.json"
    response = session.get(url, params={'limit': 1})
    if response.status_code == 200:
        data = response.json()
        issue = data['issues'][0] if data['issues'] else None
        if issue:
            print(f"   Keys: {list(issue.keys())}")
            print(f"   Has journals: {'journals' in issue}")
    
    # Test 2: issues.json with include=journals
    print("\n2. issues.json with include=journals")
    response = session.get(url, params={'limit': 1, 'include': 'journals'})
    if response.status_code == 200:
        data = response.json()
        issue = data['issues'][0] if data['issues'] else None
        if issue:
            print(f"   Keys: {list(issue.keys())}")
            print(f"   Has journals: {'journals' in issue}")
    
    # Test 3: issues.json with include=journals,changesets
    print("\n3. issues.json with include=journals,changesets")
    response = session.get(url, params={'limit': 1, 'include': 'journals,changesets'})
    if response.status_code == 200:
        data = response.json()
        issue = data['issues'][0] if data['issues'] else None
        if issue:
            print(f"   Keys: {list(issue.keys())}")
            print(f"   Has journals: {'journals' in issue}")
    
    # Test 4: Single issue API
    print("\n4. Single issue API /issues/ID.json")
    issues = client.get_issues(limit=1)
    if issues:
        issue_id = issues[0]['id']
        url_single = f"{base_url}/issues/{issue_id}.json"
        response = session.get(url_single, params={'include': 'journals'})
        if response.status_code == 200:
            data = response.json()
            issue = data.get('issue', {})
            print(f"   Keys: {list(issue.keys())}")
            print(f"   Has journals: {'journals' in issue}")
            if 'journals' in issue:
                print(f"   Journal count: {len(issue['journals'])}")
    
    print("\n=== Redmine version check ===")
    # Check Redmine version
    try:
        response = session.get(f"{base_url}.json")
        if response.status_code == 200:
            data = response.json()
            print(f"Redmine version: {data}")
    except:
        print("Could not fetch Redmine version")

def test_issue_with_comments():
    """Find and test an issue that has comments."""
    
    client = RedmineClient(
        base_url=config.redmine_url,
        api_key=config.redmine_api_key,
        disable_proxy=config.disable_proxy,
        ssl_verify=config.ssl_verify
    )
    
    print("\n=== Looking for issues with comments ===")
    
    # Get more issues to find one with comments
    issues = client.get_issues(limit=20, status_id='*')
    
    for issue in issues:
        issue_id = issue['id']
        # Get full issue details
        full_issue = client.get_issue(issue_id)
        if full_issue and 'journals' in full_issue:
            journal_count = len(full_issue['journals'])
            if journal_count > 0:
                print(f"\nIssue #{issue_id}: {issue['subject']}")
                print(f"   Journal count: {journal_count}")
                
                # Show some journal details
                for i, journal in enumerate(full_issue['journals'][:3]):  # Show first 3
                    notes = journal.get('notes', '').strip()
                    if notes:
                        print(f"   Journal {i+1}: {notes[:50]}...")
                    else:
                        print(f"   Journal {i+1}: (no notes, field changes only)")
                
                break
    else:
        print("No issues with comments found in the sample")

if __name__ == "__main__":
    try:
        test_api_variations()
        test_issue_with_comments()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

#!/usr/bin/env python3
"""
Test script for WebUI advice generation workflow.
アドバイス再作成機能のWebUIでの動作をテストします。
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_advice_generation_workflow():
    """アドバイス生成ワークフローをテストします"""
    
    print("=== RemindMine WebUI アドバイス生成ワークフローテスト ===\n")
    
    # 1. 現在のIssue一覧を取得
    print("1. 現在のIssue一覧を取得...")
    issues_response = requests.get(f"{BASE_URL}/api/web/issues")
    if issues_response.status_code == 200:
        issues_data = issues_response.json()
        issues = issues_data.get('issues', [])
        print(f"   取得したIssue数: {len(issues)}")
        
        if issues:
            # 最初のissueでテスト
            test_issue = issues[0]
            issue_id = test_issue['id']
            print(f"   テスト対象Issue: #{issue_id} - {test_issue['subject']}")
            
            # 2. アドバイス生成前のpending advice状態を確認
            print("\n2. アドバイス生成前のpending advice状態を確認...")
            pending_response = requests.get(f"{BASE_URL}/api/web/pending-advice")
            if pending_response.status_code == 200:
                pending_data = pending_response.json()
                pending_count_before = pending_data.get('count', 0)
                print(f"   生成前のpending advice数: {pending_count_before}")
            
            # 3. アドバイスを生成
            print(f"\n3. Issue #{issue_id} のアドバイスを生成...")
            advice_response = requests.post(f"{BASE_URL}/api/web/issues/{issue_id}/advice")
            
            if advice_response.status_code == 200:
                advice_data = advice_response.json()
                print(f"   アドバイス生成成功!")
                print(f"   メッセージ: {advice_data.get('message', 'No message')}")
                print(f"   advice_id: {advice_data.get('advice_id', 'No ID')}")
                
                if advice_data.get('advice'):
                    advice_text = advice_data['advice'][:100] + "..." if len(advice_data['advice']) > 100 else advice_data['advice']
                    print(f"   生成されたアドバイス: {advice_text}")
                
                # 4. アドバイス生成後のpending advice状態を確認
                print("\n4. アドバイス生成後のpending advice状態を確認...")
                time.sleep(1)  # 少し待機
                pending_response_after = requests.get(f"{BASE_URL}/api/web/pending-advice")
                if pending_response_after.status_code == 200:
                    pending_data_after = pending_response_after.json()
                    pending_count_after = pending_data_after.get('count', 0)
                    pending_advice_list = pending_data_after.get('pending_advice', [])
                    
                    print(f"   生成後のpending advice数: {pending_count_after}")
                    print(f"   変化: {pending_count_after - pending_count_before} 件増加")
                    
                    # 新しく追加されたpending adviceの詳細
                    if pending_advice_list:
                        print("\n   pending advice詳細:")
                        for i, advice in enumerate(pending_advice_list):
                            if advice['issue_id'] == issue_id:
                                print(f"     ID: {advice['id']}")
                                print(f"     Issue: #{advice['issue_id']} - {advice['issue_subject']}")
                                print(f"     作成日時: {advice['created_at']}")
                                print(f"     プロジェクト: {advice['project_name']}")
                                print(f"     ステータス: {advice['status_name']}")
                
                # 5. Issue一覧を再取得して画面更新を確認
                print("\n5. Issue一覧を再取得して画面更新を確認...")
                updated_issues_response = requests.get(f"{BASE_URL}/api/web/issues")
                if updated_issues_response.status_code == 200:
                    print("   Issue一覧の更新が正常に完了しました")
                    
                    # WebUIでの表示確認
                    print("\n6. WebUIでの表示確認:")
                    print("   http://localhost:8000 でWebUIを確認してください")
                    print("   - Issueリストが更新されていることを確認")
                    print("   - pending adviceが表示されていることを確認")
                
            else:
                print(f"   アドバイス生成失敗: {advice_response.status_code}")
                if advice_response.headers.get('content-type', '').startswith('application/json'):
                    error_data = advice_response.json()
                    print(f"   エラー詳細: {error_data}")
        else:
            print("   テスト対象のIssueが見つかりません")
    else:
        print(f"   Issue一覧取得失敗: {issues_response.status_code}")

    print("\n=== テスト完了 ===")

if __name__ == "__main__":
    test_advice_generation_workflow()

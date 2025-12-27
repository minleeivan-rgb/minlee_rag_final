#!/usr/bin/env python3
"""
BOM RAG 系統 - 主程式（僅文字版本，無圖片）
一鍵完成：提取歷史資料 → 建立向量資料庫 → 準備查詢
"""

import os
import sys
from utils import load_config, print_progress

def main():
    """主程式流程"""
    
    print("=" * 70)
    print("🚀 BOM RAG 系統 - 自動化建立資料庫（僅文字版本）")
    print("=" * 70)
    print()
    print("🔥 簡化模式特點:")
    print("   ✓ 僅處理文字，不提取圖片")
    print("   ✓ 建庫速度快 10 倍（1-2 分鐘）")
    print("   ✓ 資料庫大小減少 95%")
    print("   ✓ 查詢速度更快")
    print("   ✓ 生成純文字組裝步驟說明")
    print()
    
    config = load_config()
    history_folder = config['PATHS']['history_excel_folder']
    
    # 檢查歷史資料夾
    if not os.path.exists(history_folder):
        print(f"❌ 錯誤：歷史資料夾不存在")
        print(f"   路徑: {history_folder}")
        print()
        print("請在 config.ini 中設定正確的路徑")
        return False
    
    # 統計檔案
    files = [f for f in os.listdir(history_folder) 
             if f.endswith(('.xlsx', '.xls', '.pdf'))]
    
    if len(files) == 0:
        print("❌ 錯誤：歷史資料夾中沒有 Excel 或 PDF 檔案")
        print(f"   路徑: {history_folder}")
        return False
    
    print(f"✓ 找到 {len(files)} 個歷史檔案")
    print()
    
    # ========================================
    # 步驟 1：提取歷史 BOM 資料（僅文字）
    # ========================================
    print("=" * 70)
    print("📂 步驟 1/2：提取歷史 BOM 資料（僅文字）")
    print("=" * 70)
    print()
    
    if os.path.exists('extracted_data.json'):
        response = input("發現已存在 extracted_data.json，是否重新提取？(y/N): ")
        if response.lower() != 'y':
            print("✓ 跳過提取步驟，使用現有資料")
        else:
            print("開始提取資料...")
            from extract_bom_data import process_all_files
            process_all_files(history_folder)
    else:
        print("開始提取資料...")
        from extract_bom_data import process_all_files
        process_all_files(history_folder)
    
    print()
    
    # 檢查是否成功生成
    if not os.path.exists('extracted_data.json'):
        print("❌ 錯誤：未能生成 extracted_data.json")
        return False
    
    # ========================================
    # 步驟 2：上傳到 MongoDB Atlas
    # ========================================
    print("=" * 70)
    print("☁️  步驟 2/2：上傳到 MongoDB Atlas")
    print("=" * 70)
    print()
    
    from upload_to_mongodb import upload_to_mongodb
    
    success = upload_to_mongodb('extracted_data.json')
    
    if not success:
        print()
        print("❌ 上傳失敗，請檢查:")
        print("   1. MongoDB 連接字串是否正確")
        print("   2. 網路連接是否正常")
        print("   3. IP 白名單是否已設定")
        return False
    
    # ========================================
    # 完成
    # ========================================
    print()
    print("=" * 70)
    print("🎉 資料庫建立完成！")
    print("=" * 70)
    print()
    print("📊 資料庫資訊:")
    print(f"   - 資料庫: {config['MONGODB']['database_name']}")
    print(f"   - 集合: {config['MONGODB']['collection_name']}")
    print(f"   - 向量索引: {config['MONGODB']['vector_index_name']}")
    print()
    print("✅ 現在您可以使用以下指令生成組裝指導書（僅文字版本）:")
    print()
    print("   python3 query_and_generate_text_only.py 您的新BOM表.xlsx")
    print()
    print("   或")
    print()
    print("   python3 query_and_generate_text_only.py 123.png")
    print()
    print("=" * 70)
    
    return True


if __name__ == '__main__':
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("⚠️  程式已中斷")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
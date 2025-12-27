#!/usr/bin/env python3
"""
將提取的資料上傳到 MongoDB Atlas
"""

import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from utils import load_config, print_progress


def create_vector_search_index(collection, index_name, vector_dimension=1536):
    """創建向量搜尋索引
    
    Args:
        collection: MongoDB collection
        index_name: 索引名稱
        vector_dimension: 向量維度
    """
    # MongoDB Atlas Vector Search 索引定義
    index_definition = {
        "name": index_name,
        "type": "vectorSearch",
        "definition": {
            "fields": [
                {
                    "type": "vector",
                    "path": "vector",
                    "numDimensions": vector_dimension,
                    "similarity": "cosine"
                }
            ]
        }
    }
    
    try:
        # 檢查索引是否已存在
        existing_indexes = list(collection.list_search_indexes())
        index_exists = any(idx.get('name') == index_name for idx in existing_indexes)
        
        if not index_exists:
            collection.create_search_index(index_definition)
            print(f"✓ 向量搜尋索引 '{index_name}' 創建成功")
            print("  注意：索引可能需要幾分鐘才能完全建立")
        else:
            print(f"✓ 向量搜尋索引 '{index_name}' 已存在")
            
    except Exception as e:
        print(f"創建索引時發生錯誤: {e}")
        print("請確認您的 MongoDB Atlas 方案支援 Vector Search（需要 M10 以上）")


def upload_to_mongodb(json_file='extracted_data.json'):
    """上傳資料到 MongoDB Atlas
    
    Args:
        json_file: JSON 資料檔案路徑
    """
    config = load_config()
    verbose = config['SETTINGS'].getboolean('verbose')
    
    # MongoDB 設定
    connection_string = config['MONGODB']['connection_string']
    database_name = config['MONGODB']['database_name']
    collection_name = config['MONGODB']['collection_name']
    index_name = config['MONGODB']['vector_index_name']
    
    # 檢查連接字串
    if '您的用戶名' in connection_string or '您的密碼' in connection_string:
        print("錯誤：請在 config.ini 中填入正確的 MongoDB Atlas 連接字串")
        return False
    
    print_progress("連接到 MongoDB Atlas...", verbose)
    
    try:
        # 連接 MongoDB
        client = MongoClient(connection_string)
        
        # 測試連接
        client.admin.command('ping')
        print("✓ MongoDB 連接成功")
        
        # 選擇資料庫和集合
        db = client[database_name]
        collection = db[collection_name]
        
        # 載入資料
        print_progress(f"載入資料從 {json_file}", verbose)
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"準備上傳 {len(data)} 筆資料")
        
        # 清空現有資料（可選）
        response = input("是否清空現有資料？(y/N): ")
        if response.lower() == 'y':
            result = collection.delete_many({})
            print(f"已刪除 {result.deleted_count} 筆舊資料")
        
        # 插入資料
        print_progress("上傳資料到 MongoDB...", verbose)
        
        if len(data) > 0:
            result = collection.insert_many(data)
            print(f"✓ 成功上傳 {len(result.inserted_ids)} 筆資料")
        else:
            print("❌ 沒有資料可上傳")
            return False
        
        # 創建向量搜尋索引
        print_progress("設定向量搜尋索引...", verbose)
        create_vector_search_index(collection, index_name)
        
        # 顯示統計
        total_docs = collection.count_documents({})
        primary_docs = collection.count_documents({"is_primary": True})
        multi_part_docs = collection.count_documents({"total_parts": {"$gt": 1}, "is_primary": True})
        
        print(f"\n資料庫統計:")
        print(f"  - 總文件數: {total_docs}")
        print(f"  - 原始 BOM 檔案數: {primary_docs}")
        if multi_part_docs > 0:
            print(f"  - 分片檔案數: {multi_part_docs}")
            print(f"  - 分片文件數: {total_docs - primary_docs}")
        print(f"  - 資料庫: {database_name}")
        print(f"  - 集合: {collection_name}")
        
        print("\n✓ 上傳完成！")
        return True
        
    except ConnectionFailure:
        print("❌ MongoDB 連接失敗")
        print("請檢查:")
        print("  1. 連接字串是否正確")
        print("  2. 網路連接是否正常")
        print("  3. MongoDB Atlas IP 白名單設定")
        return False
        
    except OperationFailure as e:
        print(f"❌ 操作失敗: {e}")
        print("請檢查資料庫權限設定")
        return False
        
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if 'client' in locals():
            client.close()
            print_progress("MongoDB 連接已關閉", verbose)


if __name__ == '__main__':
    success = upload_to_mongodb()
    if not success:
        exit(1)
import requests
import json
import configparser
import os
import re

class AzureOpenAIAPI:
    """處理 Azure OpenAI Embeddings (向量化)"""
    
    def __init__(self, config_path='config.ini'):
        self.config = load_config(config_path)
        
    def get_embedding(self, text):
        """將文字轉換為向量"""
        # 檢查輸入是否有效
        if text is None:
            print("⚠️  [Azure] 輸入文字是 None，跳過")
            return None
        if not isinstance(text, str):
            print(f"⚠️  [Azure] 輸入不是字串，類型：{type(text)}，跳過")
            return None
        if len(text.strip()) == 0:
            print("⚠️  [Azure] 輸入文字為空，跳過")
            return None
            
        try:
            api_key = self.config['AZURE_OPENAI']['api_key']
            endpoint = self.config['AZURE_OPENAI']['endpoint']
            api_version = self.config['AZURE_OPENAI']['api_version']
            deployment = self.config['AZURE_OPENAI']['embedding_deployment']
            
            url = f"{endpoint}openai/deployments/{deployment}/embeddings?api-version={api_version}"
            headers = {"api-key": api_key, "Content-Type": "application/json"}
            
            # 確保輸入不超過長度限制
            text = text.replace("\n", " ")[:8000]
            payload = {"input": text}
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()['data'][0]['embedding']
        except Exception as e:
            print(f"❌ [Azure] Embedding Error: {e}")
            return None

class GeminiAPI:
    """處理 Gemini 生成與 JSON 解析"""
    
    def __init__(self):
        config = load_config()
        self.api_key = config['GEMINI']['api_key']
        self.model = config['GEMINI']['model']
    
    def generate_text(self, prompt, max_tokens=8192):
        """呼叫 Gemini 生成內容，已開到最大 8192 tokens"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0, # 絕對零度，確保內容不偏移
                "maxOutputTokens": max_tokens
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            # 檢查回傳格式是否正確
            if 'candidates' not in result:
                print(f"⚠️  [Gemini] 回傳格式異常：沒有 candidates")
                return None
            if len(result['candidates']) == 0:
                print(f"⚠️  [Gemini] 回傳格式異常：candidates 為空")
                return None
            
            candidate = result['candidates'][0]
            
            # 檢查是否被安全過濾器擋住
            if 'content' not in candidate:
                finish_reason = candidate.get('finishReason', 'UNKNOWN')
                print(f"⚠️  [Gemini] 內容被過濾，原因：{finish_reason}")
                return None
            
            if 'parts' not in candidate['content']:
                print(f"⚠️  [Gemini] 回傳格式異常：沒有 parts")
                return None
            
            if len(candidate['content']['parts']) == 0:
                print(f"⚠️  [Gemini] 回傳格式異常：parts 為空")
                return None
                
            return candidate['content']['parts'][0]['text']
        except requests.exceptions.Timeout:
            print(f"❌ [Gemini] API 超時")
            return None
        except Exception as e:
            print(f"❌ [Gemini] API 錯誤: {e}")
            return None

    def enhance_bom_text(self, raw_text):
        """【優化搜尋關鍵】強化提取產品型號"""
        # 如果輸入是空的，直接返回
        if not raw_text or len(raw_text.strip()) == 0:
            print("⚠️  [enhance_bom_text] 輸入文字為空")
            return ""
        
        # ===== 方法 1：正則表達式直接提取（更可靠）=====
        # 常見型號格式：T-323、L-604、BP-27、BP-22 等
        
        # 嘗試匹配「品名：XXX」格式
        match = re.search(r'品名[：:]\s*([A-Za-z]+-?\d+)', raw_text)
        if match:
            model = match.group(1)
            print(f"[DEBUG] 正則表達式提取到型號: {model}")
            return model
        
        # 嘗試匹配其他常見格式
        match = re.search(r'([A-Za-z]+-\d{2,4})', raw_text)
        if match:
            model = match.group(1)
            print(f"[DEBUG] 正則表達式提取到型號: {model}")
            return model
        
        # ===== 方法 2：用 Gemini 提取（備用）=====
        prompt = f"""你是一位工業 BOM 資料分析師。請從以下原始文字中提取出完整的『產品型號(Model Number)』。

【重要規則】：
1. 產品型號通常是英文字母+數字的組合，例如：T-323、L-604、BP-27、BP-22
2. 請提取完整型號，不要只提取部分
3. 如果看到「品名：T-323 系列」，請回答「T-323」
4. 只輸出型號，不要有任何其他文字

原始文字：
{raw_text[:3000]}

請回答完整的產品型號："""
        result = self.generate_text(prompt, max_tokens=100)
        
        # 如果 Gemini 回傳 None 或太短，返回原始文字的前 100 字作為備用
        if result is None or len(result.strip()) < 2:
            print("⚠️  [enhance_bom_text] Gemini 無回應，使用原始文字")
            return raw_text[:100]
        
        result = result.strip()
        print(f"[DEBUG] Gemini 提取到型號: {result}")
        
        return result

    def generate_assembly_steps(self, input_bom, reference_bom):
        """核心：分批呼叫 LLM 生成完整組裝步驟"""
        
        input_items = "\n".join([f"{i.get('number','')} {i.get('full_text','')}" for i in input_bom.get('bom_items', [])])
        ref_items = "\n".join([f"{i.get('number','')} {i.get('full_text','')}" for i in reference_bom.get('bom_items', [])])
        ref_guide = reference_bom.get('full_text', '無參考內容')
        
        # ===== 第 1 步：判斷總共需要幾個步驟 =====
        print("[INFO] 第 1 次呼叫 LLM：分析參考模板，判斷總步驟數...")
        total_steps = self._get_total_steps(ref_guide)
        
        if total_steps is None or total_steps < 1:
            print("⚠️  無法判斷步驟數，預設為 13 步")
            total_steps = 13
        
        print(f"✅ 判斷出需要生成 {total_steps} 個步驟")
        
        # ===== 第 2 步：分批生成步驟（每批 4 個）=====
        all_steps = []
        batch_size = 4
        batch_num = 1
        
        for start in range(1, total_steps + 1, batch_size):
            end = min(start + batch_size - 1, total_steps)
            
            print(f"[INFO] 第 {batch_num + 1} 次呼叫 LLM：生成步驟 {start}-{end}...")
            
            batch_steps = self._generate_steps_batch(
                input_items, ref_items, ref_guide, 
                start, end, total_steps
            )
            
            if batch_steps:
                all_steps.extend(batch_steps)
                print(f"✅ 成功生成步驟 {start}-{end}（本批 {len(batch_steps)} 個）")
            else:
                print(f"⚠️  步驟 {start}-{end} 生成失敗，跳過")
            
            batch_num += 1
        
        print(f"\n🎉 全部完成！共生成 {len(all_steps)} 個步驟")
        return all_steps
    
    def _get_total_steps(self, ref_guide):
        """第一次呼叫：判斷參考模板總共有幾個步驟"""
        prompt = f"""你是工廠SOP分析專家。請分析以下參考模板內容，判斷總共有幾個組裝步驟。

【參考模板內容】：
{ref_guide}

請只回覆一個數字，例如：13
不要有任何其他文字。"""
        
        response = self.generate_text(prompt, max_tokens=50)
        
        if response:
            # 提取數字
            match = re.search(r'\d+', response)
            if match:
                return int(match.group())
        return None
    
    def _generate_steps_batch(self, input_items, ref_items, ref_guide, start, end, total):
        """分批生成步驟"""
        prompt = f"""你是工廠SOP編輯專家。請參考模板，為新產品生成第 {start} 到第 {end} 步的組裝步驟。

【重要規則】：
1. 只生成步驟 {start} 到 {end}（共 {end - start + 1} 個步驟）
2. 參考模板總共有 {total} 步，請對應生成相應位置的步驟
3. 保留原本的敘述口吻和細節
4. 將舊零件名稱替換為新BOM中的零件名稱
5. 只輸出JSON，不要任何其他文字

【新產品 BOM】：
{input_items}

【參考模板 BOM】：
{ref_items}

【參考模板內容】：
{ref_guide}

請輸出 JSON 陣列，格式如下：
[
  {{"step_number": {start}, "title": "步驟名稱", "description": "詳細操作說明", "notes": "注意事項"}}
]"""
        
        response = self.generate_text(prompt)
        
        # DEBUG 輸出
        print(f"\n{'='*40}")
        print(f"🔍 [DEBUG] 步驟 {start}-{end} 的 Gemini 回傳：")
        print(f"{'='*40}")
        if response:
            # 只印前 500 字，避免太長
            print(response[:500] + "..." if len(response) > 500 else response)
        print(f"{'='*40}\n")
        
        return self._parse_json_safely(response)

    def _parse_json_safely(self, text):
        """強化版 JSON 解析（含自動修復被截斷的 JSON）"""
        # ===== DEBUG: 檢查輸入 =====
        if text is None:
            print("❌ [DEBUG] Gemini 回傳是 None，可能是 API 呼叫失敗")
            return None
        # ===== DEBUG END =====
        
        try:
            # 移除 markdown 程式碼區塊標記
            cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
            
            # 嘗試找到 JSON 陣列
            match = re.search(r'\[.*', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(0)
            
            # 第一次嘗試：直接解析
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
            
            # ===== 自動修復被截斷的 JSON =====
            print("⚠️  [DEBUG] JSON 可能被截斷，嘗試自動修復...")
            
            # 找到最後一個完整的物件（以 }, 或 } 結尾）
            # 策略：找到最後一個 "notes": "..." } 的位置
            last_complete = re.findall(r'\{[^{}]*"notes"\s*:\s*"[^"]*"\s*\}', cleaned, re.DOTALL)
            
            if last_complete:
                # 找到最後一個完整物件的結束位置
                last_obj = last_complete[-1]
                last_pos = cleaned.rfind(last_obj) + len(last_obj)
                
                # 截取到最後一個完整物件，並加上 ]
                fixed = cleaned[:last_pos] + ']'
                
                try:
                    result = json.loads(fixed)
                    print(f"✅ [DEBUG] 自動修復成功！已解析 {len(result)} 個步驟")
                    return result
                except json.JSONDecodeError:
                    pass
            
            # 備用策略：暴力修復，補上可能缺少的 }, ]
            for suffix in [']', '}]', '"}]', '""}]', '":""}]']:
                try:
                    result = json.loads(cleaned + suffix)
                    print(f"✅ [DEBUG] 備用修復成功！已解析 {len(result)} 個步驟")
                    return result
                except json.JSONDecodeError:
                    continue
            
            print(f"❌ [JSON Parse Error] 無法修復被截斷的 JSON")
            return None
            
        except Exception as e:
            print(f"❌ [JSON Parse Error] AI 回傳格式不對。")
            print(f"❌ [DEBUG] 錯誤詳情: {e}")
            return None

def load_config(config_path='config.ini'):
    """載入設定檔，並確保資料夾存在"""
    import os
    
    # 取得程式所在目錄（不是執行目錄）
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_full_path = os.path.join(base_dir, config_path)
    
    # 如果在程式目錄找不到，就在當前目錄找
    if not os.path.exists(config_full_path):
        config_full_path = config_path
    
    config = configparser.ConfigParser()
    config.read(config_full_path, encoding='utf-8')
    
    # 自動建立 PATHS 中的資料夾
    if 'PATHS' in config:
        for key in config['PATHS']:
            path = config['PATHS'][key]
            # 如果是相對路徑，轉換成絕對路徑
            if path.startswith('./'):
                path = os.path.join(base_dir, path[2:])
                config['PATHS'][key] = path
            # 建立資料夾（如果不存在）
            if 'folder' in key and not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
                print(f"[INFO] 自動建立資料夾: {path}")
    
    return config

def print_progress(message, verbose=True):
    if verbose:
        print(f"[INFO] {message}")
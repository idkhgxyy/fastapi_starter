import httpx
import sys

BASE_URL = "http://localhost:8000/api"

def main():
    print("=== 启动 RAG 功能实时端到端测试 ===")
    
    # 1. 注册或登录以获取 Token
    print("\n1. 尝试登录 (获取 JWT Token)...")
    login_data = {
        "username": "admin@example.com",
        "password": "password123"
    }
    
    with httpx.Client() as client:
        response = client.post(f"{BASE_URL}/auth/login", data=login_data)
        if response.status_code != 200:
            # 如果登录失败，可能是用户不存在，我们先注册
            print("   登录失败，尝试先注册一个测试用户...")
            reg_response = client.post(f"{BASE_URL}/users/", json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "password123",
                "full_name": "Test Admin"
            })
            if reg_response.status_code not in (200, 201):
                print(f"   注册失败: {reg_response.text}")
                sys.exit(1)
            # 再次登录
            response = client.post(f"{BASE_URL}/auth/login", data=login_data)
        
        token_info = response.json()
        access_token = token_info.get("access_token")
        if not access_token:
            print(f"   无法获取 Token！详细信息: {token_info}")
            sys.exit(1)
        
        print("   ✅ 获取 Token 成功！")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 2. 上传测试文档
        print("\n2. 上传知识库文档 (sample_knowledge.txt)...")
        file_path = "sample_knowledge.txt"
        try:
            with open(file_path, "rb") as f:
                files = {"file": ("sample_knowledge.txt", f, "text/plain")}
                upload_resp = client.post(f"{BASE_URL}/rag/upload", headers=headers, files=files)
                
            if upload_resp.status_code == 200:
                upload_data = upload_resp.json()
                print(f"   ✅ 上传成功！文档ID: {upload_data['id']}, 被切分为 {upload_data['chunks_count']} 块。")
            else:
                print(f"   ❌ 上传失败: {upload_resp.text}")
                sys.exit(1)
        except Exception as e:
            print(f"   读取文件失败: {e}")
            sys.exit(1)

        # 3. 检索与问答
        print("\n3. 进行 RAG 知识库问答测试...")
        query_text = "这个项目的开发代号和紧急覆写指令分别是什么？"
        print(f"   🗣️  提问: {query_text}")
        
        query_payload = {"query": query_text, "top_k": 2}
        
        # 增加超时时间，因为大模型生成可能需要一些时间
        query_resp = client.post(
            f"{BASE_URL}/rag/query", 
            headers=headers, 
            json=query_payload,
            timeout=120.0
        )
        
        if query_resp.status_code == 200:
            result = query_resp.json()
            print("\n   🤖 AI 回答:")
            print("-" * 50)
            print(result['answer'])
            print("-" * 50)
            print("\n   📚 召回的原文片段:")
            for idx, chunk in enumerate(result['source_chunks'], 1):
                print(f"     片段 {idx}: {chunk.strip()}")
            print("\n✅ 端到端测试圆满成功！")
        else:
            print(f"   ❌ 问答请求失败: {query_resp.text}")

if __name__ == "__main__":
    main()

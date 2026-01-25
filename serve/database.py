import os
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client
load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
print(url, key)
supabase: Client = create_client(url, key)

def fetchdata():
    response = (
        supabase.table("users")
        .select("*")
        .execute()
    )
    print(response.data)

def get_or_create_user(provider_id: str, name: str):
    try:
        # 1. Kiểm tra xem user đã tồn tại chưa
        existing_user = (
            supabase.table("users")
            .select("*")
            .eq("name", name)
            .eq("provider_id", provider_id)
            .execute()
        )

        # 2. Nếu đã tồn tại, trả về user đó luôn
        if existing_user.data:
            print(f"Welcome back, {name}!")
            return existing_user.data[0]

        # 3. Nếu chưa có, tiến hành tạo mới
        print(f"New user detected! Creating account for {name}...")
        new_uuid = str(uuid.uuid4())
        new_user_data = {
            "id": new_uuid,
            "name": name,
            "provider_id": provider_id,
            # Bạn có thể lưu thêm name nếu muốn (cần thêm cột trong DB)
        }
        
        response = supabase.table("users").insert(new_user_data).execute()
        return response.data[0]
    except Exception as e:
        print(f"Lỗi khi tạo user: {e}")
        return None
    
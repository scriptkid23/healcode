import os
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client
load_dotenv()

url: str | None = os.getenv("SUPABASE_URL")
key: str | None = os.getenv("SUPABASE_KEY")
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
    
def create_repositorie(user_id: str, git_url: str, local_path: str):
    """
    Lưu thông tin repository vào bảng 'repositories'.
    Kiểm tra nếu repo đã tồn tại dựa trên user_id và git_url thì trả về dữ liệu cũ.
    """
    try:
        # 1. Kiểm tra xem repository này của user đã được lưu chưa
        existing_repo = (
            supabase.table("repositories")
            .select("*")
            .eq("user_id", user_id)
            .eq("git_url", git_url)
            .execute()
        )

        if existing_repo.data:
            print(f"Repository {git_url} already exists for this user.")
            return existing_repo.data[0]

        # 2. Nếu chưa có, tạo mới bản ghi
        print(f"Adding new repository: {git_url}")
        new_repo_id = str(uuid.uuid4())
        new_repo_data = {
            "id": new_repo_id,
            "user_id": user_id,
            "git_url": git_url,
            "local_path": local_path,
            # "created_at": "now()" # Tùy thuộc vào thiết lập DB của bạn
        }

        response = supabase.table("repositories").insert(new_repo_data).execute()
        
        if response.data:
            return response.data[0]
        return None

    except Exception as e:
        print(f"Lỗi khi lưu repository: {e}")
        return None
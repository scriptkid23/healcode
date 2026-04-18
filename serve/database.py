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
        # 1. Check whether the user already exists
        existing_user = (
            supabase.table("users")
            .select("*")
            .eq("name", name)
            .eq("provider_id", provider_id)
            .execute()
        )

        # 2. Return existing user if found
        if existing_user.data:
            print(f"Welcome back, {name}!")
            print(existing_user.data[0])
            return existing_user.data[0]

        # 3. Create a new user if missing
        print(f"New user detected! Creating account for {name}...")
        new_uuid = str(uuid.uuid4())
        new_user_data = {
            "id": new_uuid,
            "name": name,
            "provider_id": provider_id,
            # You can store additional fields if needed (requires DB columns)
        }
        
        response = supabase.table("users").insert(new_user_data).execute()
        return response.data[0]
    except Exception as e:
        print(f"Error while creating user: {e}")
        return None
    
def create_repositorie(user_id: str, git_url: str, local_path: str):
    """
    Save repository metadata into the 'repositories' table.
    Return existing data when a record with user_id and git_url already exists.
    """
    try:
        # 1. Check whether this repository is already saved for the user
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

        # 2. Insert a new record if missing
        print(f"Adding new repository: {git_url}")
        new_repo_data = {
            "user_id": user_id,
            "git_url": git_url,
            "local_path": local_path,
            # "created_at": "now()" # Depends on your DB setup
        }

        response = supabase.table("repositories").insert(new_repo_data).execute()
        
        if response.data:
            return response.data[0]
        return None

    except Exception as e:
        print(f"Error while saving repository: {e}")
        return None
    
def get_local_path_by_id(user_id: str, repo_url: str):
    # Query the local_path field from repositories by user and repo
    try:
        response = (
            supabase.table("repositories")
            .select("local_path")
            .eq("user_id", user_id)
            .eq("git_url", repo_url)
            .execute()
        )
        print(response)
        
        # Return local_path when a matching record exists
        if response.data:
            return response.data[0].get("local_path") # type: ignore
            
        # No matching record found
        return None
        
    except Exception as e:
        # Log query errors and return None
        print(f"Error while fetching local_path: {e}")
        return None

def get_username_by_id(user_id: str):
    # Query the local_path field from repositories by user and repo
    try:
        response = (
            supabase.table("users")
            .select("name")
            .eq("id", user_id)
            .execute()
        )
        
        # Return local_path when a matching record exists
        print(response)
        if response.data:
            return response.data[0].get("name") # type: ignore
            
        # No matching record found
        return None
        
    except Exception as e:
        # Log query errors and return None
        print(f"Error while fetching local_path: {e}")
        return None
    
def get_repo_by_id(user_id: str):
    try:
        response = (
            supabase.table("repositories")
            .select("git_url")
            .eq("user_id", user_id)
            .execute()
        )
        print(response)
        
        # Return local_path when a matching record exists
        if response.data:
            return list(map(lambda x: x["git_url"], response.data)) # type: ignore
            
        # No matching record found
        return None
        
    except Exception as e:
        # Log query errors and return None
        print(f"Error while fetching local_path: {e}")
        return None
    
def get_repo_current(user_id: str):
    try:
        response = (
            supabase.table("users")
            .select("current_repo_url")
            .eq("id", user_id)
            .execute()
        )
        if response.data:
            return response.data[0].get("current_repo_url") # type: ignore
            
        # No matching record found
        return None
        
    except Exception as e:
        # Log query errors and return None
        print(f"Error while fetching local_path: {e}")
        return None

def set_repo_current(user_id: str, repo: str):
    try:
        response = (
            supabase.table("users")
            .update({"current_repo_url": repo})
            .eq("id", user_id)
            .execute()
        )
        
        if response.data:
            print(f"Successfully updated current_repo_url to: {repo}")
            return response.data[0]
            
        return None
        
    except Exception as e:
        print(f"Error while setting current repo: {e}")
        return None
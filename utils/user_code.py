import random
import string
from supabase_client import supabase

def generate_user_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_unique_user_code():
    while True:
        code = generate_user_code()
        result = supabase.table("users").select("id").eq("user_code", code).execute()
        if not result.data:
            return code

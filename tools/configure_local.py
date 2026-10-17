"""Create local-only staff credentials and enable daily source checks. Never prints the key."""
from pathlib import Path
import re
import secrets

root=Path(__file__).resolve().parents[1]
path=root/".env"
content=path.read_text(encoding="utf-8") if path.exists() else ""
values={"SOURCE_REFRESH_ENABLED":"true","SOURCE_REFRESH_SECONDS":"86400"}
existing=re.search(r"^ADMIN_TOKEN=(.*)$",content,re.M)
if not existing or existing.group(1).strip() in {"","change-me"}:
    values["ADMIN_TOKEN"]=secrets.token_urlsafe(32)
for key,value in values.items():
    pattern=r"^"+key+r"=.*$"
    if re.search(pattern,content,re.M):content=re.sub(pattern,key+"="+value,content,flags=re.M)
    else:content=content.rstrip()+"\n"+key+"="+value+"\n"
path.write_text(content,encoding="utf-8")
print("Local setup saved in ignored .env. Staff key is not printed. Restart the backend.")

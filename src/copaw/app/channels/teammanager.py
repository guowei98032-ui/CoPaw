
import asyncio
import json

class TeamManager:
    """Owns queues and consumer loops; channels define how to consume via
    consume_one(). Enqueue via enqueue(channel_id, payload) (thread-safe).
    """

    def __init__(self, workspace):
       
       self._lock = asyncio.Lock()
       team_dir = workspace.workspace_dir / "team"
       team_dir.mkdir(parents=True, exist_ok=True)
       self._path = team_dir / "team.json"
       try:
            with open(self._path, "r", encoding="utf-8", errors="surrogatepass") as f:
                self._repo = json.load(f)
       except FileNotFoundError:
            # 文件不存在时的处理逻辑
            self._repo = {}  # 使用默认值
            print(f"⚠️  文件不存在")
       except json.JSONDecodeError:
            # JSON 格式错误时的处理
            self._repo = {}
            print(f"⚠️  JSON 格式错误")

    async def get_team_sys_prompt(self,room_id,user_id):
        async with self._lock:
            if room_id is not None:
                team_prompt = self._repo.get(f"{room_id}","无")
                if user_id is not None:
                    user_prompt = self._repo.get(f"{room_id}:{user_id}","无")
                else:
                    user_prompt = "无"
                sys_prompt = f"""
                    环境：多Agent协作模式
                    协作提示：
                    {team_prompt}
                    自己情况提示：
                    {user_prompt}
                    """
                return sys_prompt
            else:
                sys_prompt = f"""
                    环境：单Agent模式
                    协作提示：
                    {team_prompt}
                    自己情况提示：
                    {user_prompt}
                    """
                return sys_prompt

    async def upsert_team_sys_prompt(self,room_id,user_id,prompt):
        async with self._lock:
            if prompt is not None:
                if user_id is None:              
                    self._repo[f"{room_id}"] = prompt
                else:
                    self._repo[f"{room_id}:{user_id}"] = prompt
                try:
                    with open(self._path, "w", encoding="utf-8") as f:
                        json.dump(self._repo,f,ensure_ascii=False,indent=2)
                except Exception:
                    print(f"⚠️  JSON 保存错误")

    async def start(self) -> None:
        
        pass

    async def stop(self) -> None:
        
        pass
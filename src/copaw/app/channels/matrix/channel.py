# -*- coding: utf-8 -*-
"""Matrix channel implementation using matrix-nio."""

import asyncio
import json
import logging
import mimetypes
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import uuid
import markdown
import pymdownx.tasklist
import aiohttp
import re
from typing import List, Tuple
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    AudioContent,
    ContentType,
    FileContent,
    ImageContent,
    MessageType,
    RunStatus,
    TextContent,
    VideoContent,
)
from nio import (
    Api,
    AsyncClient,
    InviteEvent,
    JoinResponse,
    MatrixRoom,
    RoomMessageAudio,
    RoomMessageFile,
    RoomMessageImage,
    RoomMessageText,
    RoomMessageVideo,
    RoomSendError,
    UploadError,
)

from copaw.app.channels.schema import DEFAULT_CHANNEL
from copaw.app.multi_agent_manager import MultiAgentManager
from copaw.app.runner.models import ChatSpec
from copaw.app.workspace.workspace import Workspace
from copaw.constant import DEFAULT_MEDIA_DIR

from ....config.config import MatrixConfig
from ..base import (
    BaseChannel,
    OnReplySent,
    OutgoingContentPart,
    ProcessHandler,
)

logger = logging.getLogger(__name__)


class MatrixChannel(BaseChannel):
    channel = "matrix"
    uses_manager_queue = True

    def __init__(
        self,
        process: ProcessHandler,
        enabled: bool,
        homeserver: str,
        user_id: str,
        access_token: str,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
        bot_prefix: str = "",
        dm_policy: str = "open",
        group_policy: str = "open",
        allow_from: Optional[list] = None,
        deny_message: str = "",
        require_mention: bool = False,
        workspace_dir: Path = None,
        workspace: Workspace = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            process=process,
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
            dm_policy=dm_policy,
            group_policy=group_policy,
            allow_from=allow_from,
            deny_message=deny_message,
            require_mention=require_mention,
        )
        self.enabled = enabled
        self.homeserver = homeserver.rstrip("/")
        self.user_id = user_id
        self.access_token = access_token
        self.bot_prefix = bot_prefix
        self.client: Optional[AsyncClient] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._http: Optional[aiohttp.ClientSession] = None
        self._workspace_dir = (
            Path(workspace_dir).expanduser() if workspace_dir else None
        )
        if self._workspace_dir:
            self._media_dir = self._workspace_dir / "media"
        else:
            self._media_dir = DEFAULT_MEDIA_DIR
        self._media_dir.mkdir(parents=True, exist_ok=True)

        token_store_path = self._workspace_dir / "matrix"
        self._token_store_path = Path(token_store_path)
        self._token_store_path.mkdir(parents=True, exist_ok=True)
        self._token_store_path = self._token_store_path / "token.json"
        self._device_id = user_id

        self._workspace = workspace
        
     # ========== Token 持久化 ==========
    def _load_sync_token(self) -> Optional[str]:
        """从文件加载上次同步的 token"""
        if self._token_store_path.exists():
            try:
                data = json.loads(self._token_store_path.read_text())
                token = data.get("next_batch")
                if token:
                    logger.info(f"恢复 sync token: {token[:30]}...")
                    return token
            except Exception as e:
                logger.warning(f"加载 token 失败：{e}")
        return None
    
    def _save_sync_token(self, token: str) -> None:
        """保存同步 token 到文件"""
        try:
            self._token_store_path.write_text(
                json.dumps({"next_batch": token, "device_id": self._device_id})
            )
        except Exception as e:
            logger.error(f"保存 token 失败：{e}")
    
    def _mxc_to_http(self, mxc_url: str) -> str:
        """Convert mxc://server/media_id to an authenticated HTTP URL."""
        if not mxc_url.startswith("mxc://"):
            return mxc_url
        rest = mxc_url[len("mxc://") :]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            return mxc_url
        server, media_id = parts
        return (
            f"{self.homeserver}/_matrix/client/v1/media/download/"
            f"{server}/{media_id}"
            f"?access_token={self.access_token}"
        )

    def _check_allowlist(
        self,
        sender_id: str,
        is_group: bool = False,
    ) -> tuple:
        policy = self.group_policy if is_group else self.dm_policy
        if policy == "open":
            return True, ""
        if self.allow_from and sender_id in self.allow_from:
            return True, ""
        return False, self.deny_message

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "MatrixChannel":
        raise NotImplementedError(
            "Matrix channel must be configured via config file.",
        )


    def clone(self, config) -> "BaseChannel":
        """Clone a new channel instance with updated config, cloning
        process and on_reply_sent from self.

        Subclasses must implement from_config(process, config, on_reply_sent).

        show_tool_details is global config (not in channel config), so we
        preserve from self. filter_tool_messages and filter_thinking are
        per-channel config, so we read from new config.
        """
        return self.__class__.from_config(
            process=self._process,
            config=config,
            on_reply_sent=self._on_reply_sent,
            show_tool_details=getattr(self, "_show_tool_details", True),
            filter_tool_messages=getattr(
                config,
                "filter_tool_messages",
                False,
            ),
            filter_thinking=getattr(
                config,
                "filter_thinking",
                False,
            ),
            workspace_dir= self._workspace_dir,
            workspace=self._workspace,
        )
    
    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: MatrixConfig,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
        workspace_dir: Path = None,
        workspace: Workspace = None,
    ) -> "MatrixChannel":
        return cls(
            process=process,
            enabled=config.enabled,
            homeserver=config.homeserver,
            user_id=config.user_id,
            access_token=config.access_token,
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
            bot_prefix=config.bot_prefix,
            dm_policy=config.dm_policy,
            group_policy=config.group_policy,
            allow_from=config.allow_from,
            deny_message=config.deny_message,
            require_mention=config.require_mention,
            workspace_dir = workspace_dir,
            workspace = workspace,
        )

    def build_agent_request_from_native(
        self,
        native_payload: Any,
    ) -> AgentRequest:
        
        payload = native_payload if isinstance(native_payload, dict) else {}
        meta = dict(payload.get("meta") or {})
     
        room_id = meta.get("room_id") or ""
        sender_id = meta.get("sender_id") or ""
        content_parts = payload.get("content_parts") or []

        if not content_parts:
            body = payload.get("body", "")
            content_parts = [TextContent(type=ContentType.TEXT, text=body)]

        session_id = self.resolve_session_id(room_id)
        request = self.build_agent_request_from_user_content(
            channel_id=self.channel,
            sender_id=sender_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta={"room_id": room_id},
        )

        if not payload['meta']['bot_mentioned']:
            request.no_reply = True

        return request

    def get_to_handle_from_request(self, request: AgentRequest) -> str:
        session_id = getattr(request, "session_id", "") or ""
        if session_id.startswith("matrix:"):
            return session_id[len("matrix:") :]
        meta = getattr(request, "channel_meta", {}) or {}
        return meta.get("room_id", getattr(request, "user_id", ""))

    def get_debounce_key(self, payload: Any) -> str:
        """
        Key for time debounce (same key = same conversation).
        Delegates to ``resolve_session_id`` so every channel gets
        session-scoped isolation automatically.
        """
        if isinstance(payload, dict):
            room_id = payload.get("room_id") or ""
            meta = payload.get("meta") or {}
            is_command = meta.get("is_stop_command") or False
            if is_command:
                return f"{str(uuid.uuid4())}"
            else:
                return f"{self.channel}:{self.user_id}:{room_id}"
        return super().get_debounce_key(payload)

    async def _run_process_loop(
        self,
        request: "AgentRequest",
        to_handle: str,
        send_meta: Dict[str, Any],
    ) -> None:
        """
        Run _process and send events. Override to use channel-specific
        loop (e.g. DingTalk _process_one_request with webhook sends).
        """
        last_response = None
        try:
            receiver_id = self.user_id.split(":")[0].lstrip("@")
            name = "New Chat"

            existing = await self._repo.get_chat_by_id(
                request.session_id,
                request.user_id,
                request.channel,
            )
            chat_id = str(uuid.uuid4())
            if existing:
                chat_id = existing.id
            
            spec = ChatSpec(
                id=chat_id,
                name=name,
                session_id=request.session_id,
                user_id=request.user_id,
                channel=request.channel,
                meta={'room_id':send_meta['room_id'],'receiver_id':receiver_id}
            )
            await self._workspace.chat_manager.create_chat(spec)

            tracker = self._workspace.task_tracker
            queue, _ = await tracker.attach_or_start(
                chat_id,
                request,
                self._process,
            )

            #self._workspace.task_tracker.attach_or_start(chat.id)
            async for event in tracker.stream_from_queue(queue):
                obj = getattr(event, "object", None)
                status = getattr(event, "status", None)
                if obj == "message" and status == RunStatus.Completed:
                    await self.on_event_message_completed(
                        request,
                        to_handle,
                        event,
                        send_meta,
                    )
                elif obj == "response":
                    last_response = event
                    await self.on_event_response(request, event)
            err_msg = self._get_response_error_message(last_response)
            if err_msg:
                await self._on_consume_error(
                    request,
                    to_handle,
                    f"Error: {err_msg}",
                )
            if self._on_reply_sent:
                args = self.get_on_reply_sent_args(request, to_handle)
                self._on_reply_sent(self.channel, *args)
        except Exception:
            logger.exception("channel consume_one failed")
            await self._on_consume_error(
                request,
                to_handle,
                "An error occurred while processing your request.",
            )
    
    async def _handle_event(
        self,
        room: MatrixRoom,
        sender: str,
        content_parts: List[Any],
        bot_mentioned: bool = False,
    ) -> None:
        """Apply access control and enqueue a payload."""
        is_group = len(room.users) > 2
        meta = {
            "room_id": room.room_id,
            "is_group": is_group,
            "bot_mentioned": bot_mentioned,
            "sender_id":sender,
        }

        allowed, deny_msg = self._check_allowlist(sender, is_group=is_group)
        if not allowed:
            if deny_msg:
                await self.send(room.room_id, deny_msg)
            return

        if not self._check_group_mention(is_group, meta):
            return
        
        payload = {
            "room_id": room.room_id,
            "sender_id": sender,
            "content_parts": content_parts,
            "meta": meta,
        }
        if self._enqueue:
            self._enqueue(payload)

    def parse_command(self,input_str: str) -> Tuple[str, List[str]]:
        """
        解析命令输入，处理各种空格情况
        返回：(命令名，参数列表)
        """
        if not input_str.startswith("/"):
             return "", []
                                
        # 1. 去除首尾空格和 '/' 前缀
        content = input_str.strip().lstrip('/')
        
        # 2. 正则匹配：命令 + 任意空格 + 参数
        # \w+ 匹配命令名，\s* 匹配任意空格，.+ 匹配参数部分
        match = re.match(r'^(\w+)\s*(.*)$', content)
        
        if not match:
            return "", []
        
        command = match.group(1).lower()  # 命令转小写
        args_str = match.group(2).strip()
        
        # 3. 解析参数列表：按逗号分割，去除每个参数的空格
        if not args_str:
            return command, []
        
        # 按逗号分割，每个参数去除首尾空格，过滤空字符串
        args = [arg.strip() for arg in args_str.split(',') if arg.strip()]
        
        return command, args

    async def _message_callback(
        self,
        room: MatrixRoom,
        event: RoomMessageText,
    ) -> None:
        if event.sender == self.user_id:
            return

        logger.info(
            "Matrix received text from %s in %s: %s",
            event.sender,
            room.room_id,
            event.body,
        )

        # Detect @-mention for require_mention support
        localpart = self.user_id.split(":")[0].lstrip("@")
        send_user_id = event.sender.split(":")[0].lstrip("@")
        localpart = "@" + localpart
        bot_mentioned = localpart in event.body
        command,args = self.parse_command(event.body)
        if command == "stop":
            #user_id: Optional[str] = None,
            manager :MultiAgentManager = getattr(self._workspace.runner, "_manager", None)
            agent_ids = manager.list_loaded_agents()
            for agent_id in agent_ids:
                agent_workspace = await manager.get_agent(agent_id)
                chats = await agent_workspace.chat_manager.list_chats(channel=self.channel)
                for chat in chats:                    
                    room_id = chat.meta.get("room_id","")
                    if room_id != room.room_id:
                        continue
                    receiver_id = chat.meta.get("receiver_id","")
                    if len(args) == 0:
                        await self._workspace.task_tracker.request_stop(chat.id)
                    else:
                        if receiver_id in args:
                            await self._workspace.task_tracker.request_stop(chat.id)
            return 
        
        send_text = f"\n{send_user_id}发送如下消息)：\n" + event.body
        #bot_mentioned = self.user_id in event.body# or localpart in event.body
        content_parts = [TextContent(type=ContentType.TEXT, text=send_text)]
        await self._handle_event(
            room,
            event.sender,
            content_parts,
            bot_mentioned=bot_mentioned,
        )

    async def _download_image_resource(
        self,
        message_id: str,
        url: str,
    ) -> Optional[str]:
        """Download image to media_dir; return local path or None."""
        try:
            async with self._http.get(
                url
            ) as resp:
                if resp.status >= 400:
                    logger.warning(
                        "matrix image download failed status=%s",
                        resp.status,
                    )
                    return None
                data = await resp.read()
                content_type = (
                    resp.headers.get("Content-Type", "").split(";")[0].strip()
                )
            ext = (mimetypes.guess_extension(content_type) or ".jpg").lstrip(
                ".",
            )
            path = self._media_dir / f"{message_id}.{ext}"
            path.write_bytes(data)
            return str(path)
        except Exception:
            logger.exception("feishu _download_image_resource failed")
            return None
        
    async def _media_callback(
        self,
        room: MatrixRoom,
        event: Any,
    ) -> None:
        if event.sender == self.user_id:
            return

        mxc_url = getattr(event, "url", "") or ""
        filename = getattr(event, "body", "file") or "file"
        http_url = self._mxc_to_http(mxc_url) if mxc_url else ""

        logger.info(
            "Matrix received media from %s in %s: %s",
            event.sender,
            room.room_id,
            filename,
        )

        content_parts: List[Any] = []
        if isinstance(event, RoomMessageImage):
            local_file_path = await self._download_image_resource(event.event_id,http_url)
            if local_file_path is not None:
                content_parts.append(
                    ImageContent(type=ContentType.IMAGE, image_url=local_file_path),
                )
        elif isinstance(event, RoomMessageVideo):
            content_parts.append(
                VideoContent(type=ContentType.VIDEO, video_url=http_url),
            )
        elif isinstance(event, RoomMessageAudio):
            content_parts.append(
                AudioContent(type=ContentType.AUDIO, data=http_url),
            )
        else:
            content_parts.append(
                FileContent(type=ContentType.FILE, file_url=http_url),
            )

        await self._handle_event(room, event.sender, content_parts)

    async def send_content_parts(
        self,
        to_handle: str,
        parts: List[OutgoingContentPart],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        media_types = {
            ContentType.IMAGE,
            ContentType.VIDEO,
            ContentType.AUDIO,
            ContentType.FILE,
        }
        text_parts = [
            p
            for p in (parts or [])
            if getattr(p, "type", None) not in media_types
        ]
        media_parts = [
            p for p in (parts or []) if getattr(p, "type", None) in media_types
        ]
        if text_parts:
            await super().send_content_parts(to_handle, text_parts, meta)
        for m in media_parts:
            await self.send_media(to_handle, m, meta)

    async def send_media(  # pylint: disable=too-many-branches
        self,
        to_handle: str,
        part: OutgoingContentPart,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Upload a file to the homeserver and send it as a room message."""
        if not self.client:
            logger.error("Matrix client not initialized, cannot send media")
            return
        self.client
        url = (
            getattr(part, "image_url", None)
            or getattr(part, "video_url", None)
            or getattr(part, "data", None)
            or getattr(part, "file_url", None)
        )
        if not url:
            return

        ctype = getattr(part, "type", None)
        if ctype == ContentType.IMAGE:
            msgtype = "m.image"
        elif ctype == ContentType.VIDEO:
            msgtype = "m.video"
        elif ctype == ContentType.AUDIO:
            msgtype = "m.audio"
        else:
            msgtype = "m.file"

        temp_path = None
        try:
            if url.startswith("file://"):
                file_path = Path(url[7:])
                mime = (
                    mimetypes.guess_type(str(file_path))[0]
                    or "application/octet-stream"
                )
                filename = file_path.name
                data = file_path.read_bytes()
            elif url.startswith(("http://", "https://")):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            logger.warning(
                                "Matrix send_media: download failed"
                                " status=%d url=%s",
                                resp.status,
                                url[:80],
                            )
                            return
                        data = await resp.read()
                        mime = (
                            resp.content_type
                            or mimetypes.guess_type(
                                urlparse(url).path,
                            )[0]
                            or "application/octet-stream"
                        )
                parsed_path = urlparse(url).path
                filename = Path(parsed_path).name or "file"
            else:
                logger.warning(
                    "Matrix send_media: unsupported URL scheme: %s",
                    url[:40],
                )
                return

            suffix = Path(filename).suffix or (
                mimetypes.guess_extension(mime) or ""
            )
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as tmp:
                tmp.write(data)
                temp_path = tmp.name

            with open(temp_path, "rb") as f:
                upload_resp, _ = await self.client.upload(
                    f,
                    content_type=mime,
                    filename=filename,
                    filesize=len(data),
                )

            if isinstance(upload_resp, UploadError):
                logger.error("Matrix upload failed: %s", upload_resp)
                return

            content = {
                "msgtype": msgtype,
                "body": filename,
                "url": upload_resp.content_uri,
                "info": {"mimetype": mime, "size": len(data)},
            }
            send_resp = await self.client.room_send(
                room_id=to_handle,
                message_type="m.room.message",
                content=content,
            )
            if isinstance(send_resp, RoomSendError):
                logger.error(
                    "Matrix room_send media failed: %s",
                    send_resp,
                )

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Matrix send_media error: %s", e, exc_info=True)
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    async def _on_invite(self, room: MatrixRoom, event: InviteEvent):
        """收到邀请时自动加入"""
        room_id = room.room_id
        print(f"📨 收到邀请：{room.name}")
        print(f"   邀请人：{event.sender}")

        try:
            # # 自动加入房间
            method, path = Api.join(self.access_token, room_id)
            response = await self.client._send(JoinResponse, method, path,data="{}")
            if response.transport_response.status != 200:
                print(f"❌ 加入失败")
            else:
                print(f"✅ 已加入房间")
                
                # 可选：加入后发送欢迎消息
                user_id = self.user_id.split(":")[0].lstrip("@")
                await self.client.room_send(
                    room_id=room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": f"{user_id}已加入！有什么可以帮你的？"
                    }
                )
        except Exception as e:
            print(f"❌ 异常：{e}")
            
    async def start(self) -> None:
        if (
            not self.enabled
            or not self.homeserver
            or not self.user_id
            or not self.access_token
        ):
            logger.info(
                "Matrix channel not configured or disabled. Skipping start.",
            )
            return

        self.client = AsyncClient(self.homeserver, self.user_id)
        self.client.access_token = self.access_token
        if self._http is None:
            self._http = aiohttp.ClientSession()
        
        self.client.add_event_callback(
            self._on_invite,
            InviteEvent)
        
        self.client.add_event_callback(
            self._message_callback,
            RoomMessageText,
        )
        self.client.add_event_callback(
            self._media_callback,
            RoomMessageImage,
        )
        self.client.add_event_callback(
            self._media_callback,
            RoomMessageVideo,
        )
        self.client.add_event_callback(
            self._media_callback,
            RoomMessageAudio,
        )
        self.client.add_event_callback(
            self._media_callback,
            RoomMessageFile,
        )

        logger.info(
            "Starting Matrix client for %s on %s",
            self.user_id,
            self.homeserver,
        )

        async def sync_loop() -> None:
            
            since = self._load_sync_token()

            while True:
                try:
                    # ✅ 1. 执行单次同步（而非 sync_forever）
                    response = await self.client.sync(timeout=30000, since=since)
                    
                    # ✅ 2. 同步成功后，立即更新并保存 Token
                    since = response.next_batch
                    self._save_sync_token(since)  # ← 关键：每次成功都保存

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(
                        "Matrix sync loop error: %s",
                        e,
                        exc_info=True,
                    )

        self._sync_task = asyncio.create_task(sync_loop())

    async def stop(self) -> None:
        if self._sync_task:
            self._sync_task.cancel()
        if self.client:
            await self.client.close()
        logger.info("Matrix channel stopped.")

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.client:
            logger.error("Matrix client not initialized, cannot send message")
            return

        if not text:
            return

        logger.info(
            "Matrix sending to room=%s text_len=%d",
            to_handle,
            len(text),
        )
        html_body = markdown.markdown(
            text,
            extensions=['fenced_code', 'tables', 'pymdownx.tasklist']
        )
        resp = await self.client.room_send(
            room_id=to_handle,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": text,
                "format": "org.matrix.custom.html",
                "formatted_body": html_body
            },
        )
        if isinstance(resp, RoomSendError):
            logger.error("Matrix room_send failed: %s", resp)

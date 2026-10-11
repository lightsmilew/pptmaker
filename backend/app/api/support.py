"""Authenticated support, bounded image uploads and live in-app notifications."""
import asyncio
import io
import json
import re
import uuid
import warnings
import hashlib
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Form, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from .auth import require_session, check_origin
from .admin import require_admin, ordinary_user
from ..config import settings
from ..storage.auth_repository import AuthRepository, SESSION_COOKIE, ADMIN_COOKIE
from ..storage.admin_repository import AdminRepository
from ..storage.support_repository import SupportRepository

router = APIRouter(prefix="/api/v1/support", tags=["Support"])
admin_router = APIRouter(prefix="/api/v1/admin/support", tags=["Support administration"])
MAX_IMAGE_SIZE = 5*1024*1024
MAX_FILE_SIZE = 10*1024*1024


def view(uid, current, admin=False, before=None):
    repo = SupportRepository()
    thread = repo.conversation(uid,current["user_id"],admin)
    if not thread:
        raise HTTPException(404,"会话不存在")
    messages = repo.messages(uid,before)
    prefix = "/api/v1/admin/support" if admin else "/api/v1/support"
    for item in messages["items"]:
        for img in item["images"]:
            img["url"] = prefix+"/images/"+img["id"]
            img["thumbnail_url"] = img["url"]+"/thumbnail"
        for file in item["files"]:
            file["url"] = prefix+"/files/"+file["id"]
    return dict(conversation=thread,messages=messages)


@router.get("")
async def mine(before: int | None = Query(None,ge=1), current=Depends(require_session)):
    return view(current["user_id"],current,before=before)


@admin_router.get("")
async def inbox(q: str = Query("",max_length=200),page: int = Query(1,ge=1), current=Depends(require_admin)):
    return SupportRepository().inbox(current["user_id"],q,page)


async def stream(request, current, admin):
    check_origin(request)
    cookie = request.cookies.get(ADMIN_COOKIE if admin else SESSION_COOKIE)
    auth = AuthRepository()
    repo = SupportRepository()

    async def events():
        signature = None
        while not await request.is_disconnected():
            session = await asyncio.to_thread(auth.session,cookie)
            if not session or session["user_id"] != current["user_id"] or session["scope"] != ("admin" if admin else "user"):
                yield 'event: expired\ndata: {}\n\n'
                return
            snapshot = await asyncio.to_thread(repo.notifications,current["user_id"],admin)
            data = json.dumps(snapshot,ensure_ascii=False)
            if data != signature:
                yield "event: support\ndata: "+data+"\n\n"
                signature = data
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control":"no-store", "X-Accel-Buffering":"no"})


@router.get("/events")
async def user_events(request: Request, current=Depends(require_session)):
    return await stream(request,current,False)


@admin_router.get("/events")
async def admin_events(request: Request, current=Depends(require_admin)):
    return await stream(request,current,True)


def thumbnail_bytes(image):
    preview = image.copy()
    preview.thumbnail((480,480))
    output = io.BytesIO()
    preview.save(output,format="WEBP",quality=78,method=4)
    return output.getvalue()


def encode_image(data, filename):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"PNG","JPEG","WEBP"} or image.width*image.height>16000000:
                    raise ValueError()
                image.load()
                image = ImageOps.exif_transpose(image).convert("RGBA")
                background = Image.new("RGB",image.size,"white")
                background.paste(image,mask=image.getchannel("A"))
                image = background
                image.thumbnail((2400,2400))
                output = io.BytesIO()
                image.save(output,format="JPEG",quality=84,optimize=True)
                return output.getvalue(), dict(id="img_"+uuid.uuid4().hex,filename=Path(filename or "image").name[:100],width=image.width,height=image.height,size=len(output.getvalue())), thumbnail_bytes(image)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422,"请选择有效的 PNG、JPEG 或 WebP 图片（不超过1600万像素）")


async def send(uid,current,text,request_id,images,files=()):
    ordinary_user(uid)
    if not re.fullmatch(r"[a-zA-Z0-9_-]{12,80}",request_id):
        raise HTTPException(422,"消息标识无效")
    text = text.strip()
    if len(text)>4000 or len(images)+len(files)>3 or not (text or images or files):
        raise HTTPException(422,"每条消息需包含文字或附件，最多4000字、3个附件")
    repo = SupportRepository()
    existing = repo.existing(current["user_id"],request_id)
    if existing:
        if existing["user_id"] != uid:
            raise HTTPException(409,"消息标识已使用")
        return existing
    if not AuthRepository().throttle("support:"+current["user_id"],90):
        raise HTTPException(429,"发送较频繁，请稍后再试")
    encoded = []; attachments = []
    # Classify on the server too: forged multipart fields cannot bypass image limits.
    for upload in [*images,*files]:
        is_image = upload in images or (upload.content_type or '').startswith('image/') or Path(upload.filename or '').suffix.lower() in {'.png','.jpg','.jpeg','.webp'}
        limit = MAX_IMAGE_SIZE if is_image else MAX_FILE_SIZE
        data = await upload.read(limit+1)
        if len(data)>limit:
            raise HTTPException(413,"图片最大5 MiB，其他文件最大10 MiB")
        if is_image:
            encoded.append(await asyncio.to_thread(encode_image,data,upload.filename))
        else:
            filename = re.sub(r'[\x00-\x1f\x7f]', '', (upload.filename or 'attachment').replace('\\','/').split('/')[-1])[:150] or 'attachment'
            attachments.append((data,dict(id='file_'+uuid.uuid4().hex,filename=filename,size=len(data))))
    root = Path(settings.storage_path)/"support"
    root.mkdir(parents=True,exist_ok=True)
    paths = []
    try:
        for data,img,preview in encoded:
            path = root/(img["id"]+".jpg")
            path.write_bytes(data)
            paths.append(path)
            thumbnail = root/(img["id"]+".thumb.webp")
            thumbnail.write_bytes(preview)
            paths.append(thumbnail)
        for data,file in attachments:
            path = root/(file['id']+'.bin')
            path.write_bytes(data)
            paths.append(path)
        result,created = repo.send(uid,current["user_id"],current["role"],text,request_id,[img for _,img,_ in encoded],[file for _,file in attachments])
        if not created:
            for path in paths:
                path.unlink(missing_ok=True)
            if result["user_id"] != uid:
                raise HTTPException(409,"消息标识已使用")
    except Exception:
        for path in paths:
            path.unlink(missing_ok=True)
        raise
    # Message commit owns its images. A later audit failure must never remove them.
    if created:
        AdminRepository().record("admin" if current["role"] == "admin" else "usage",current["user_id"],"support.sent",uid,{"images":len(encoded),"files":len(attachments)})
    return result


@router.post("/messages",status_code=201)
async def user_send(text: str = Form(""),request_id: str = Form(...),images: list[UploadFile] = File(default=[]),files: list[UploadFile] = File(default=[]),current=Depends(require_session)):
    return await send(current["user_id"],current,text,request_id,images,files)


class ReadReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_id: int = Field(ge=0)


def mark_read(uid,current,data):
    ordinary_user(uid)
    try:
        SupportRepository().read(uid,current["user_id"],data.last_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    return {"ok":True}


@router.post("/read")
async def user_read(data: ReadReceipt,current=Depends(require_session)):
    return mark_read(current["user_id"],current,data)


def image_response(image_id,current,request,admin=False,thumbnail=False):
    img = SupportRepository().image(image_id)
    if not img or (not admin and img["user_id"] != current["user_id"]):
        raise HTTPException(404,"图片不存在")
    path = Path(settings.storage_path)/"support"/(img["id"]+".jpg")
    if not path.is_file():
        raise HTTPException(404,"图片不存在")
    if thumbnail:
        small = path.with_suffix('.thumb.webp')
        if not small.is_file():
            # Older messages get a derivative on first authorized access.
            with Image.open(path) as image:
                data = thumbnail_bytes(image)
            temp = small.with_name(small.name+'.'+uuid.uuid4().hex+'.tmp')
            try:
                temp.write_bytes(data)
                temp.replace(small)
            finally:
                temp.unlink(missing_ok=True)
        path = small
    stat = path.stat()
    etag = '"'+hashlib.sha256(f'{stat.st_mtime_ns}:{stat.st_size}'.encode()).hexdigest()+'"'
    headers = {"Cache-Control":"private, no-cache", "Vary":"Cookie", "ETag":etag, "X-Content-Type-Options":"nosniff"}
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304,headers=headers)
    return FileResponse(path,media_type="image/webp" if thumbnail else "image/jpeg",headers=headers,stat_result=stat)


@router.api_route("/images/{image_id}",methods=["GET","HEAD"])
async def user_image(image_id: str,request: Request,current=Depends(require_session)):
    return await asyncio.to_thread(image_response,image_id,current,request)


@admin_router.api_route("/images/{image_id}",methods=["GET","HEAD"])
async def admin_image(image_id: str,request: Request,current=Depends(require_admin)):
    return await asyncio.to_thread(image_response,image_id,current,request,True)


@router.api_route("/images/{image_id}/thumbnail",methods=["GET","HEAD"])
async def user_thumbnail(image_id: str,request: Request,current=Depends(require_session)):
    return await asyncio.to_thread(image_response,image_id,current,request,False,True)


@admin_router.api_route("/images/{image_id}/thumbnail",methods=["GET","HEAD"])
async def admin_thumbnail(image_id: str,request: Request,current=Depends(require_admin)):
    return await asyncio.to_thread(image_response,image_id,current,request,True,True)


def attachment_response(file_id,current,admin=False):
    file = SupportRepository().attachment(file_id)
    if not file or (not admin and file['user_id'] != current['user_id']):
        raise HTTPException(404,'附件不存在')
    path = Path(settings.storage_path)/'support'/(file['id']+'.bin')
    if not path.is_file():
        raise HTTPException(404,'附件不存在')
    return FileResponse(path,media_type='application/octet-stream',filename=file['filename'],
                        headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})


@router.api_route('/files/{file_id}',methods=['GET','HEAD'])
async def user_file(file_id: str,current=Depends(require_session)):
    return attachment_response(file_id,current)


@admin_router.api_route('/files/{file_id}',methods=['GET','HEAD'])
async def admin_file(file_id: str,current=Depends(require_admin)):
    return attachment_response(file_id,current,True)


@admin_router.get("/{uid}")
async def admin_thread(uid: str,before: int | None = Query(None,ge=1),current=Depends(require_admin)):
    return view(uid,current,True,before)


@admin_router.post("/{uid}/messages",status_code=201)
async def admin_send(uid: str,text: str = Form(""),request_id: str = Form(...),images: list[UploadFile] = File(default=[]),files: list[UploadFile] = File(default=[]),current=Depends(require_admin)):
    return await send(uid,current,text,request_id,images,files)


@admin_router.post("/{uid}/read")
async def admin_read(uid: str,data: ReadReceipt,current=Depends(require_admin)):
    return mark_read(uid,current,data)


class ConversationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["open","closed"]


@admin_router.patch("/{uid}")
async def admin_status(uid: str,data: ConversationPatch,current=Depends(require_admin)):
    if not SupportRepository().conversation(uid,current["user_id"],True) or not SupportRepository().messages(uid)["items"]:
        raise HTTPException(404,"会话不存在")
    SupportRepository().status(uid,data.status)
    AdminRepository().record("admin",current["user_id"],"support.status_changed",uid,{"status":data.status})
    return {"ok":True}

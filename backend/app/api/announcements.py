"""Authenticated notices with administrator publishing and daily user opt-out."""
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field,field_validator
from .auth import require_session
from .admin import require_admin
from ..storage.announcement_repository import AnnouncementRepository,display_day
from ..storage.admin_repository import AdminRepository

router=APIRouter(prefix='/api/v1/announcements',tags=['Announcements'])
admin_router=APIRouter(prefix='/api/v1/admin/announcements',tags=['Announcement administration'])


class NoticeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=120)
    body:str=Field(min_length=1,max_length=6000)
    duration_days:int | None=Field(default=None,ge=1,le=365)

    @field_validator('title','body')
    @classmethod
    def nonblank(cls,value):
        if not value.strip(): raise ValueError('公告内容不能为空')
        return value.strip()


class DismissInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)


@router.get('')
async def active(current=Depends(require_session)):
    return dict(items=AnnouncementRepository().active(current['user_id']),day=display_day(),timezone='Asia/Shanghai')


@router.post('/{aid}/dismiss')
async def dismiss(aid:str,data:DismissInput,current=Depends(require_session)):
    if not AnnouncementRepository().dismiss(current['user_id'],aid,data.revision):
        raise HTTPException(404,'公告已更新或结束，请刷新')
    return dict(ok=True,day=display_day())


@admin_router.get('')
async def notices(status:Literal['all','draft','published','withdrawn']='all',page:int=Query(1,ge=1),current=Depends(require_admin)):
    return AnnouncementRepository().list(status,page)


@admin_router.post('',status_code=201)
async def create(data:NoticeInput,current=Depends(require_admin)):
    result=AnnouncementRepository().save(**data.model_dump())
    AdminRepository().record('admin',current['user_id'],'announcement.created',result['id'])
    return result


@admin_router.patch('/{aid}')
async def update(aid:str,data:NoticeInput,current=Depends(require_admin)):
    if not AnnouncementRepository().get(aid): raise HTTPException(404,'公告不存在')
    try: result=AnnouncementRepository().save(**data.model_dump(),aid=aid)
    except ValueError as error: raise HTTPException(409,str(error)) from error
    AdminRepository().record('admin',current['user_id'],'announcement.updated',aid)
    return result


@admin_router.post('/{aid}/{action}')
async def transition(aid:str,action:Literal['publish','withdraw'],current=Depends(require_admin)):
    result=AnnouncementRepository().publish(aid,action=='publish')
    if not result: raise HTTPException(404,'公告不存在')
    AdminRepository().record('admin',current['user_id'],'announcement.'+action,aid)
    return result

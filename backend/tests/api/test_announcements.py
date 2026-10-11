from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.storage.announcement_repository import AnnouncementRepository
from app.storage import announcement_repository as module
from .test_admin import clients


def test_admin_publish_user_daily_dismiss_revision_and_permissions(clients, monkeypatch):
    admin,user,aid,uid=clients
    clock=datetime(2026,10,10,15,59,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'now',lambda:clock)
    endpoint='/api/v1/admin/announcements'
    body=dict(title='秋日创作提醒',body='支持自动配图。\n欢迎提出建议。',duration_days=None)
    assert user.post(endpoint,json=body).status_code==401
    draft=admin.post(endpoint,json=body).json(); nid=draft['id']
    assert draft['status']=='draft' and user.get('/api/v1/announcements').json()['items']==[]
    assert admin.post(endpoint+'/'+nid+'/publish',headers={'X-CSRF-Token':'bad'}).status_code==403
    published=admin.post(endpoint+'/'+nid+'/publish').json()
    assert published['revision']==1
    assert admin.patch(endpoint+'/'+nid,json=body).status_code==409
    result=user.get('/api/v1/announcements').json()
    assert result['day']=='2026-10-10' and result['timezone']=='Asia/Shanghai'
    assert result['items'][0]['body']==body['body'] and 'duration_days' not in result['items'][0]
    assert user.post('/api/v1/announcements/'+nid+'/dismiss',json={'revision':9}).status_code==404
    assert user.post('/api/v1/announcements/'+nid+'/dismiss',json={'revision':1}).status_code==200
    assert AnnouncementRepository().active(uid)==[]  # Recreated repository, durable.
    assert len(AnnouncementRepository().active('another-user'))==1
    assert admin.post(endpoint+'/'+nid+'/publish').json()['revision']==1  # Double submission.
    assert AnnouncementRepository().active(uid)==[]
    clock+=timedelta(minutes=2)
    assert user.get('/api/v1/announcements').json()['day']=='2026-10-11'
    assert len(AnnouncementRepository().active(uid))==1
    admin.post(endpoint+'/'+nid+'/withdraw')
    assert user.get('/api/v1/announcements').json()['items']==[]
    admin.patch(endpoint+'/'+nid,json={**body,'body':'新的公告内容'})
    assert admin.post(endpoint+'/'+nid+'/publish').json()['revision']==2
    assert len(AnnouncementRepository().active(uid))==1
    with TestClient(app) as public:
        assert public.get('/api/v1/announcements').status_code==401


def test_notice_expiry_validation_and_pagination(clients,monkeypatch):
    admin,user,_,uid=clients
    clock=datetime(2026,10,10,tzinfo=timezone.utc); monkeypatch.setattr(module,'now',lambda:clock)
    path='/api/v1/admin/announcements'
    for body in ({'title':' ','body':'text'},{'title':'x','body':'x'*6001},{'title':'x','body':'x','duration_days':0},{'title':'x','body':'x','status':'published'}):
        assert admin.post(path,json=body).status_code==422
    record=admin.post(path,json={'title':'One day','body':'text','duration_days':1}).json()
    admin.post(path+'/'+record['id']+'/publish')
    assert len(AnnouncementRepository().active(uid))==1
    clock+=timedelta(days=1)
    assert not AnnouncementRepository().active(uid)
    assert not AnnouncementRepository().dismiss(uid,record['id'],1)
    for i in range(22): AnnouncementRepository().save(str(i),'message',None)
    page=admin.get(path+'?status=draft&page=2').json()
    assert page['total']==22 and len(page['items'])==2
    assert admin.patch(path+'/missing',json={'title':'a','body':'b'}).status_code==404
    assert admin.post(path+'/missing/publish').status_code==404

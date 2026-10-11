import io
import asyncio
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from starlette.requests import Request

from .test_admin import clients
from app.config import settings
from app.api.support import stream
from app.storage.auth_repository import AuthRepository, SESSION_COOKIE
from app.storage.support_repository import SupportRepository
from app.storage.memory import memory_store
from app.api.websocket import WorkflowRunner


def image_bytes():
    result=io.BytesIO()
    Image.new('RGB',(120,80),'green').save(result,format='PNG')
    return result.getvalue()


@pytest.fixture
def support_clients(clients,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'storage_path',str(tmp_path/'assets'))
    return clients


def test_support_offline_history_images_permissions_receipts_and_status(support_clients):
    admin,user,aid,uid=support_clients
    assert user.get('/api/v1/support').json()['messages']['items']==[]
    assert admin.get('/api/v1/admin/support').json()['total']==0
    result=user.post('/api/v1/support/messages',data={'text':'预览排版问题','request_id':'support-request-0001'},files=[('images',('example.png',image_bytes(),'image/png'))])
    assert result.status_code==201,result.text
    mid=result.json()['id']
    repo=SupportRepository()
    assert repo.notifications(aid,True)['unread']==1
    inbox=admin.get('/api/v1/admin/support').json()
    assert inbox['total']==1 and inbox['items'][0]['unread']==1
    record=user.get('/api/v1/support').json()['messages']['items'][0]
    assert record['text']=='预览排版问题' and 'author_id' not in record
    url=record['images'][0]['url']
    assert user.get(url).headers['content-type']=='image/jpeg'
    assert user.get('/api/v1/admin/support').status_code==401
    other_id=AuthRepository().register('other-support@example.test','Other-password-123','Other')
    other_token,_,_=AuthRepository().create_session(other_id)
    assert user.get(url,headers={'Cookie':f'{SESSION_COOKIE}={other_token}'}).status_code==404
    admin_view=admin.get(f'/api/v1/admin/support/{uid}').json()
    assert admin.get(admin_view['messages']['items'][0]['images'][0]['url']).status_code==200
    assert admin.post(f'/api/v1/admin/support/{uid}/read',json={'last_id':mid+500}).status_code==422
    assert admin.post(f'/api/v1/admin/support/{uid}/read',json={'last_id':mid}).status_code==200
    assert repo.notifications(aid,True)['unread']==0
    assert admin.post(f'/api/v1/admin/support/{uid}/messages',data={'text':'请补充页面编号，我们会处理。','request_id':'support-reply-00001'}).status_code==201
    assert repo.notifications(uid)['unread']==1
    latest=user.get('/api/v1/support').json()['messages']['items'][-1]
    assert latest['author_role']=='admin'
    user.post('/api/v1/support/read',json={'last_id':latest['id']})
    assert repo.notifications(uid)['unread']==0
    admin.patch(f'/api/v1/admin/support/{uid}',json={'status':'closed'})
    assert user.get('/api/v1/support').json()['conversation']['status']=='closed'
    user.post('/api/v1/support/messages',data={'text':'还有一个问题','request_id':'support-request-0002'})
    assert SupportRepository().conversation(uid,aid,True)['status']=='open'
    assert len(SupportRepository().messages(uid)['items'])==3  # Fresh repository / durable history.


def test_support_thumbnails_are_small_authorized_cached_and_regenerated(support_clients):
    from pathlib import Path
    admin,user,aid,uid = support_clients
    output = io.BytesIO()
    Image.effect_noise((3000,2000),40).convert('RGB').save(output,format='JPEG',quality=90)
    original = output.getvalue()
    assert len(original)<5*1024*1024
    sent = user.post('/api/v1/support/messages',data={'request_id':'thumbnail-request-0001'},files={'images':('large.jpg',original,'image/jpeg')})
    assert sent.status_code==201,sent.text
    img = user.get('/api/v1/support').json()['messages']['items'][0]['images'][0]
    large = user.get(img['url']); small = user.get(img['thumbnail_url'])
    assert small.status_code==200 and small.headers['content-type']=='image/webp'
    assert len(small.content)<len(large.content)/10
    with Image.open(io.BytesIO(small.content)) as picture:
        assert picture.size==(480,320)
    with Image.open(io.BytesIO(large.content)) as picture:
        assert picture.size==(2400,1600)
    assert small.headers['cache-control']=='private, no-cache'
    assert 'cookie' in {value.strip().lower() for value in small.headers['vary'].split(',')}
    etag = small.headers['etag']
    assert user.get(img['thumbnail_url'],headers={'If-None-Match':etag}).status_code==304
    assert user.head(img['thumbnail_url']).status_code==200
    other = AuthRepository().register('other-thumbnail@example.test','Other-password-123','Other')
    token,_,_ = AuthRepository().create_session(other)
    assert user.get(img['thumbnail_url'],headers={'Cookie':f'{SESSION_COOKIE}={token}','If-None-Match':etag}).status_code==404
    admin_img = admin.get(f'/api/v1/admin/support/{uid}').json()['messages']['items'][0]['images'][0]
    assert admin.get(admin_img['thumbnail_url']).status_code==200
    path = Path(settings.storage_path)/'support'/(img['id']+'.thumb.webp')
    path.unlink()
    assert user.get(img['thumbnail_url']).status_code==200 and path.is_file()
    user.cookies.clear()
    assert user.get(img['thumbnail_url'],headers={'If-None-Match':etag}).status_code==401


def test_transparent_support_images_use_paper_background(support_clients):
    admin,user,_,_ = support_clients
    output = io.BytesIO(); Image.new('RGBA',(20,20),(0,0,0,0)).save(output,format='PNG')
    assert user.post('/api/v1/support/messages',data={'request_id':'transparent-request1'},files={'images':('transparent.png',output.getvalue(),'image/png')}).status_code==201
    img = user.get('/api/v1/support').json()['messages']['items'][0]['images'][0]
    with Image.open(io.BytesIO(user.get(img['url']).content)) as picture:
        assert min(picture.getpixel((10,10)))>245


def test_support_input_csrf_pagination_and_idempotency(support_clients):
    admin,user,aid,uid=support_clients
    endpoint='/api/v1/support/messages'
    body={'text':'hello','request_id':'same-request-00001'}
    first=user.post(endpoint,data=body).json()
    assert user.post(endpoint,data=body).json()==first
    assert len(SupportRepository().messages(uid)['items'])==1
    assert user.post(endpoint,data=body,headers={'X-CSRF-Token':'bad'}).status_code==403
    assert user.post(endpoint,data={'request_id':'empty-message-0001'}).status_code==422
    assert user.post(endpoint,data={'text':'x'*4001,'request_id':'long-message-0001'}).status_code==422
    assert user.post(endpoint,data={'request_id':'invalid-image-0001'},files={'images':('image.svg',b'<svg/>','image/svg+xml')}).status_code==422
    assert user.post(endpoint,data={'request_id':'oversize-image-001'},files={'images':('big.png',b'x'*(5*1024*1024+1),'image/png')}).status_code==413
    for i in range(45):
        SupportRepository().send(uid,uid,'user',str(i),'pagination-request-'+str(i),[])
    newest=user.get('/api/v1/support').json()['messages']
    assert len(newest['items'])==40 and newest['has_more']
    old=user.get('/api/v1/support?before='+str(newest['before'])).json()['messages']
    assert len(old['items'])==6 and not old['has_more']
    assert old['items'][-1]['id']<newest['items'][0]['id']


def test_support_generic_files_are_durable_private_downloads(support_clients):
    admin,user,_,uid=support_clients
    body={'request_id':'support-file-request01'}
    payload=b'%PDF-1.7 test attachment'
    upload={'files':('../reference.pdf',payload,'application/pdf')}
    first=user.post('/api/v1/support/messages',data=body,files=upload)
    assert first.status_code==201,first.text
    assert user.post('/api/v1/support/messages',data=body,files=upload).json()==first.json()
    record=user.get('/api/v1/support').json()['messages']['items'][0]
    file=record['files'][0]; assert file['filename']=='reference.pdf' and file['size']==len(payload)
    response=user.get(file['url'])
    assert response.content==payload and response.headers['content-type']=='application/octet-stream'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert response.headers['x-content-type-options']=='nosniff'
    assert user.head(file['url']).status_code==200
    assert len(SupportRepository().messages(uid)['items'])==1
    other=AuthRepository().register('other-file@example.test','Other-password-123','Other')
    token,_,_=AuthRepository().create_session(other)
    assert user.get(file['url'],headers={'Cookie':f'{SESSION_COOKIE}={token}'}).status_code==404
    admin_file=admin.get(f'/api/v1/admin/support/{uid}').json()['messages']['items'][0]['files'][0]
    assert admin.get(admin_file['url']).content==payload
    assert user.get(admin_file['url']).status_code==401
    assert user.post('/api/v1/support/messages',data={'request_id':'too-many-files-0001'},files=[('files',('file.txt',b'x','text/plain'))]*4).status_code==422
    assert user.post('/api/v1/support/messages',data={'request_id':'too-large-file-0001'},files={'files':('big.txt',b'x'*(10*1024*1024+1),'text/plain')}).status_code==413
    # Images sent in the generic field still use image validation and image limits.
    assert user.post('/api/v1/support/messages',data={'request_id':'forged-image-file1'},files={'files':('bad.png',b'not an image','application/octet-stream')}).status_code==422


def test_committed_images_survive_later_audit_error_and_retry(support_clients,monkeypatch):
    from app.storage.admin_repository import AdminRepository
    _,user,_,uid=support_clients
    def failure(*args,**kwargs):
        raise RuntimeError('isolated audit failure')
    monkeypatch.setattr(AdminRepository,'record',failure)
    body={'text':'已提交的消息','request_id':'audit-failure-request1'}
    with pytest.raises(RuntimeError,match='isolated audit failure'):
        user.post('/api/v1/support/messages',data=body,files={'images':('example.png',image_bytes(),'image/png')})
    messages=user.get('/api/v1/support').json()['messages']['items']
    assert len(messages)==1
    assert user.get(messages[0]['images'][0]['url']).status_code==200
    retry=user.post('/api/v1/support/messages',data=body)
    assert retry.status_code==201 and retry.json()['id']==messages[0]['id']
    assert len(SupportRepository().messages(uid)['items'])==1


@pytest.mark.asyncio
async def test_support_event_stream_revalidates_revoked_sessions(support_clients):
    admin,user,aid,uid=support_clients
    token=user.cookies.get(SESSION_COOKIE)
    request=Request({'type':'http','method':'GET','path':'/api/v1/support/events','headers':[(b'cookie',f'{SESSION_COOKIE}={token}'.encode())]})
    request.is_disconnected=AsyncMock(return_value=False)
    current=AuthRepository().session(token)
    response=await stream(request,current,False)
    iterator=response.body_iterator
    assert 'event: support' in await anext(iterator)
    AuthRepository().revoke(token)
    assert 'event: expired' in await anext(iterator)
    await iterator.aclose()
    assert response.headers['x-accel-buffering']=='no'


def test_admin_generation_detail_preview_download_are_private_and_audited(support_clients,tmp_path):
    from pathlib import Path
    admin,user,aid,uid=support_clients
    project=WorkflowRunner.create_project({'topic':'安全预览','style':'科技风'},owner_id=uid)
    pid=project['id']; root=Path(settings.storage_path)
    image=root/'previews'/pid/'page-01'/'iteration-1.png'; image.parent.mkdir(parents=True)
    image.write_bytes(image_bytes()); (root/(pid+'.pptx')).write_bytes(b'test-pptx')
    memory_store.update_project(pid,{'status':'completed','pages':[{'page_id':'page-01','content':{'title':'标题','bullet_points':['信息']},'preview':{'image_path':str(image)}}]})
    base=f'/api/v1/admin/generations/{pid}'
    assert user.get(base).status_code==401
    detail=admin.get(base)
    assert detail.status_code==200,detail.text
    data=detail.json(); assert data['email']=='writer@example.test'
    assert 'uploaded_files' not in data and 'owner_id' not in data
    assert admin.get(data['pages'][0]['preview_url']).status_code==200
    assert admin.get(data['download_url']).content==b'test-pptx'
    assert user.get(data['pages'][0]['preview_url']).status_code==401
    assert admin.get('/storage/'+pid+'.pptx').status_code==401
    actions=admin.get('/api/v1/admin/records?kind=admin').json()['items']
    assert {'presentation.viewed','presentation.downloaded'}<={a['action'] for a in actions}
    outside=tmp_path/'outside.png'; outside.write_bytes(image_bytes())
    memory_store.update_project(pid,{'pages':[{'page_id':'page-01','preview':{'image_path':str(outside)}}]})
    assert admin.get(base+'/preview/page-01').status_code==404
    assert admin.get('/api/v1/admin/generations/proj_missing').status_code==404

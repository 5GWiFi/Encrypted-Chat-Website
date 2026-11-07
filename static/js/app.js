const $ = id => document.getElementById(id);
let activeId = null, activeConversation = null, poller = null, myId = null;
async function api(url, options={}) {
  const res = await fetch(url,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.error || '操作失敗');
  return data;
}
function notice(text){$('authNotice').textContent=text;$('authNotice').classList.remove('hidden')}
function showApp(me){
  $('auth').classList.add('hidden');$('app').classList.remove('hidden');$('logout').classList.remove('hidden');
  $('displayName').textContent=me.name;$('myPublic').textContent=me.public_code;
  loadConversations();
}
document.querySelectorAll('.tab').forEach(btn=>btn.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));btn.classList.add('active');
  $('registerPane').classList.toggle('hidden',btn.dataset.tab!=='register');$('loginPane').classList.toggle('hidden',btn.dataset.tab!=='login');
});
$('register').onclick=async()=>{
  try{const d=await api('/api/register',{method:'POST',body:JSON.stringify({name:$('name').value})});
    notice(`帳戶已建立！<br>私人 KAY（登入用）：<br><b>${d.private_code}</b><br><br>公共 KAY（讓別人聯絡你）：<br><b>${d.public_code}</b><br><br>${d.warning}<br>請先抄下私人編碼。`);
    showApp({name:d.name,public_code:d.public_code});
  }catch(e){notice(e.message)}
};
$('login').onclick=async()=>{try{const d=await api('/api/login',{method:'POST',body:JSON.stringify({private_code:$('privateCode').value})});showApp(d)}catch(e){notice(e.message)}};
$('logout').onclick=async()=>{await api('/api/logout',{method:'POST'});location.reload()};
$('copyMyCode').onclick=()=>navigator.clipboard.writeText($('myPublic').textContent);
$('refresh').onclick=loadConversations;
function openModal(title,html,submit){
  $('modalTitle').textContent=title;$('modalBody').innerHTML=html;$('modal').classList.remove('hidden');
  $('modalSubmit')?.addEventListener('click',submit);
}
$('closeModal').onclick=()=>$('modal').classList.add('hidden');
$('modal').onclick=e=>{if(e.target===$('modal'))$('modal').classList.add('hidden')};
$('newDM').onclick=()=>openModal('使用公共 KAY 開啟私訊',`<label>對方的公共 KAY 編碼</label><input id="modalCode" placeholder="KAY-..."><button id="modalSubmit" class="primary">開始私訊</button>`,async()=>{
  try{const d=await api('/api/direct',{method:'POST',body:JSON.stringify({public_code:$('modalCode').value})});$('modal').classList.add('hidden');await loadConversations();selectConversation(d.conversation_id)}catch(e){alert(e.message)}
});
$('join').onclick=()=>openModal('加入群組／頻道',`<label>群組或頻道公共 KAY</label><input id="modalCode" placeholder="KAY-..."><button id="modalSubmit" class="primary">加入</button>`,async()=>{
  try{const d=await api('/api/join',{method:'POST',body:JSON.stringify({public_code:$('modalCode').value})});$('modal').classList.add('hidden');await loadConversations();selectConversation(d.id)}catch(e){alert(e.message)}
});
function createRoom(kind){
  const label=kind==='group'?'群組':'頻道';
  openModal(`建立${label}`,`<label>${label}名稱</label><input id="roomName" maxlength="40" placeholder="輸入${label}名稱"><button id="modalSubmit" class="primary">建立${label}</button>`,async()=>{
    try{const d=await api('/api/conversations',{method:'POST',body:JSON.stringify({kind,name:$('roomName').value})});
      $('modalBody').innerHTML=`<div class="notice">已建立${label}！<br>私人管理 KAY：<b>${d.private_code}</b><br>公共 KAY：<b>${d.public_code}</b><br>${d.warning}</div><button id="doneRoom" class="primary">完成</button>`;
      $('doneRoom').onclick=async()=>{$('modal').classList.add('hidden');await loadConversations();selectConversation(d.id)};
    }catch(e){alert(e.message)}
  });
}
$('newGroup').onclick=()=>createRoom('group');$('newChannel').onclick=()=>createRoom('channel');
async function loadConversations(){
  try{const d=await api('/api/conversations');$('conversationList').innerHTML='';
    d.items.forEach(c=>{const b=document.createElement('button');b.className='conv'+(c.id===activeId?' active':'');b.innerHTML=`<b>${escapeHtml(c.name)}</b><small>${c.kind==='direct'?'私訊':c.kind==='group'?'群組':'頻道'} · ${escapeHtml(c.last_message||'尚未有訊息')}</small>`;b.onclick=()=>selectConversation(c.id,c);$('conversationList').appendChild(b)});
  }catch(e){console.error(e)}
}
async function selectConversation(id,known){
  activeId=id;activeConversation=known||null;$('empty').classList.add('hidden');$('chatPanel').classList.remove('hidden');
  await loadConversations();await loadMessages();
  if(poller)clearInterval(poller);poller=setInterval(loadMessages,2500);
}
async function loadMessages(){
  if(!activeId)return;
  try{const d=await api(`/api/messages/${activeId}`);const box=$('messages');box.innerHTML='';
    d.items.forEach(m=>{const el=document.createElement('div');el.className='msg';el.innerHTML=`<b>${escapeHtml(m.display_name)}</b><p>${escapeHtml(m.body)}</p><time>${new Date(m.created_at*1000).toLocaleString()}</time>`;box.appendChild(el)});
    box.scrollTop=box.scrollHeight;
    const list=await api('/api/conversations');const c=list.items.find(x=>x.id===activeId);
    if(c){$('chatName').textContent=c.name;$('chatKind').textContent=c.kind==='direct'?'私訊':c.kind==='group'?'群組':'頻道';activeConversation=c}
  }catch(e){console.error(e)}
}
$('sendForm').onsubmit=async e=>{e.preventDefault();const body=$('messageInput').value.trim();if(!body||!activeId)return;
  try{await api(`/api/messages/${activeId}`,{method:'POST',body:JSON.stringify({body})});$('messageInput').value='';await loadMessages();await loadConversations()}catch(err){alert(err.message)}
};
$('copyRoom').onclick=()=>{if(activeConversation?.public_code)navigator.clipboard.writeText(activeConversation.public_code);else alert('請重新選擇對話')};
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
(async()=>{try{const me=await api('/api/me');showApp(me)}catch(_){}})();

import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowUpRight, Check, ChevronRight, Copy, Filter, Search, ShieldCheck, Sparkles, X } from 'lucide-react';
import { api, useResource } from './api';
import type { Incident } from './types';
import { categoryIcons, categoryNames, Empty, handlingNames, SafetyNote, SeverityBadge, time } from './ui';

export function Incidents({onChanged}:{onChanged:()=>void}) {
  const [q,setQ]=useState('');const [severity,setSeverity]=useState('');const [category,setCategory]=useState('');const [state,setState]=useState('firing');
  const [page,setPage]=useState(1);const [selected,setSelected]=useState<string|null>(null);
  const params=new URLSearchParams({q,severity,category,state,page:String(page)});
  const {data,error,refresh}=useResource<{items:Incident[];total:number}>('/incidents?'+params);
  useEffect(()=>{setPage(1);},[q,severity,category,state]);
  const items=data?.items||[];
  return <>
    <div className="section-heading"><div><h2>Лента событий <span className="count">{data?.total??'—'}</span></h2><p>Всё, что требует вашего внимания, в одном месте</p></div><span className="live-label"><i/>Автообновление · 5 сек</span></div>
    <div className="workspace">
      <section className="event-panel">
        <div className="filters"><label className="search"><Search size={17}/><input aria-label="Поиск событий" placeholder="Событие или хост…" value={q} onChange={e=>setQ(e.target.value)}/></label>
          <div className="filter-row"><Filter size={15}/><select aria-label="Тип события" value={severity} onChange={e=>setSeverity(e.target.value)}><option value="">Все типы</option><option value="critical">Критические</option><option value="warning">Предупреждения</option><option value="info">Информационные</option></select>
          <select aria-label="Категория" value={category} onChange={e=>setCategory(e.target.value)}><option value="">Все категории</option>{Object.entries(categoryNames).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
          <select aria-label="Состояние событий" value={state} onChange={e=>setState(e.target.value)}><option value="firing">Активные</option><option value="resolved">Восстановленные</option><option value="">Все события</option></select></div>
        </div>
        {error&&<div className="error" role="alert">{error}<button onClick={refresh}>Повторить</button></div>}
        {!data&&!error&&<div className="loading">Получаем события…</div>}
        {data&&items.length===0&&<Empty title="Здесь спокойно" description="Событий по выбранным условиям нет. Измените фильтры или дождитесь обновления мониторинга."/>}
        <div className="event-list">{items.map(item=>{const Icon=categoryIcons[item.category];return <button className={'event-row '+(selected===item.id?'selected':'')} key={item.id} onClick={()=>setSelected(item.id)}>
          <span className={'event-marker '+item.severity}/><span className="event-content"><span className="event-top"><SeverityBadge value={item.severity}/><span className={'priority '+item.priority.toLowerCase()}>{item.priority}</span><time>{time(item.first_seen)}</time></span><strong>{item.title}</strong><span className="event-meta"><span><Icon size={13}/>{item.host}</span><span>{categoryNames[item.category]}</span><span className={'handling '+item.handling}>{handlingNames[item.handling]}</span></span></span><ChevronRight size={17}/>
        </button>;})}</div>
        {data&&data.total>50&&<div className="pagination"><button disabled={page===1} onClick={()=>setPage(p=>p-1)}>Назад</button><span>Страница {page}</span><button disabled={page*50>=data.total} onClick={()=>setPage(p=>p+1)}>Далее</button></div>}
        <div className="panel-footer"><span><ShieldCheck size={14}/> Ни одно действие не выполняется автоматически</span></div>
      </section>
      <aside className={'detail-panel '+(selected?'has-selection':'')}>
        {selected?<Detail id={selected} onClose={()=>setSelected(null)} onChanged={()=>{refresh();onChanged();}}/>:<div className="detail-placeholder"><span className="sparkle-circle"><Sparkles size={28}/></span><h3>От сигнала к решению</h3><p>Выберите событие, чтобы увидеть разбор и подходящие инструкции.</p><div><span>01</span> Классификация события</div><div><span>02</span> Поиск проверенного регламента</div><div><span>03</span> Ваше решение и ручное действие</div><small>ИИ помогает разобраться. Контроль остаётся у вас.</small></div>}
      </aside>
    </div>
  </>;
}

function Detail({id,onClose,onChanged}:{id:string;onClose:()=>void;onChanged:()=>void}) {
  const {data:item,error,refresh}=useResource<Incident>('/incidents/'+id);
  const [comment,setComment]=useState('');const [busy,setBusy]=useState(false);const [message,setMessage]=useState('');const [copied,setCopied]=useState(false);
  useEffect(()=>{setComment('');setMessage('');},[id]);
  async function action(name:string){setBusy(true);setMessage('');try{await api('/incidents/'+id+'/actions',{method:'POST',body:JSON.stringify({action:name,comment})});refresh();onChanged();setMessage('Решение записано. Инфраструктурные команды не запускались.');}catch(err){setMessage((err as Error).message);}finally{setBusy(false);}}
  async function copy(steps:string[]){try{await navigator.clipboard.writeText(steps.map((s,i)=>`${i+1}. ${s}`).join('\n'));setCopied(true);}catch{setMessage('Копирование недоступно. Выделите текст инструкции вручную.');}}
  if(error)return <div className="error">{error}</div>;
  if(!item)return <div className="loading">Разбираем событие…</div>;
  return <div className="detail-content"><div className="detail-toolbar"><span><Sparkles size={15}/> Разбор события</span><button aria-label="Закрыть событие" className="icon-button" onClick={onClose}><X size={19}/></button></div>
    <div className="detail-title"><SeverityBadge value={item.severity}/><h2>{item.title}</h2><p>{item.description}</p><div className="detail-facts"><span>Хост<strong>{item.host}</strong></span><span>Категория<strong>{categoryNames[item.category]}</strong></span><span>Приоритет<strong>{item.priority}</strong></span><span>Состояние<strong>{item.lifecycle==='firing'?'Активно':'Восстановлено'}</strong></span></div></div>
    <div className="classification-note"><span className="eyebrow">КЛАССИФИКАЦИЯ</span><p>{item.rationale}</p><span className={'confidence '+(item.needs_review?'low':'')}>{item.needs_review?'Нужна ручная проверка':'Оценка модели'} · {Math.round(item.confidence*100)}%</span><small>Оценка модели не гарантирует правильность решения.</small></div>
    <div className="recommendation-heading"><h3><Sparkles size={17}/> Рекомендации</h3><span>{item.recommendations.length}</span></div>
    {item.recommendation_status==='pending'&&<div className="hint">Ищем подходящие регламенты. При первом запуске загружается локальная модель.</div>}
    {item.recommendation_status==='ready'&&!item.recommendations.length&&<div className="hint">Близких инструкций нет. Проверьте событие вручную или добавьте регламент в базу знаний.</div>}
    {item.recommendations.map((rec,index)=><article className="recommendation" key={rec.id}><div className="rec-top"><span>{index===0?'ЛУЧШЕЕ СОВПАДЕНИЕ':'ПОХОЖИЙ РЕГЛАМЕНТ'}</span><span>{Math.round(rec.similarity*100)}% сходства</span></div><h4>{rec.title}</h4><ol>{rec.steps.map((step,i)=><li key={i}>{step}</li>)}</ol>{rec.cautions&&<div className="caution">{rec.cautions}</div>}<footer><span>Источник: {rec.source} · ред. {rec.revision}</span><button className="icon-button" aria-label="Скопировать инструкцию" onClick={()=>void copy(rec.steps)}>{copied?<Check size={16}/>:<Copy size={16}/>}</button></footer></article>)}
    <div className="manual-controls"><h3>Решение инженера</h3><p className="current-state">{handlingNames[item.handling]}</p><label>Комментарий<textarea placeholder="Что проверили или планируете сделать…" maxLength={2000} value={comment} onChange={e=>setComment(e.target.value)}/></label>
      <div className="actions">{item.handling==='new'&&<button className="primary" disabled={busy} onClick={()=>void action('accept')}><Check size={16}/>Принято к ручному выполнению</button>}{item.handling==='accepted'&&<button className="primary" disabled={busy} onClick={()=>void action('complete')}><Check size={16}/>Выполнено вручную</button>}{['new','accepted'].includes(item.handling)&&<button className="secondary" disabled={busy} onClick={()=>void action('dismiss')}>Отклонить</button>}</div>{message&&<div className="hint" role="status">{message}</div>}<SafetyNote/></div>
    <button className="back-link" onClick={onClose}><ArrowLeft size={14}/> К списку событий <ArrowUpRight size={13}/></button>
  </div>;
}

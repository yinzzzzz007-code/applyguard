export type IconName = 'brand' | 'upload' | 'folder' | 'briefcase' | 'layers' | 'file' | 'shield' | 'window' | 'check' | 'compass' | 'library' | 'history' | 'lock' | 'chevron' | 'down' | 'menu' | 'arrow' | 'spark' | 'search' | 'plus' | 'close' | 'refresh' | 'pin' | 'back'
const paths: Record<IconName,React.ReactNode> = {
  search:<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  plus:<path d="M12 5v14M5 12h14"/>,
  close:<path d="m6 6 12 12M18 6 6 18"/>,
  refresh:<path d="M20 7v5h-5M4 17v-5h5M5.5 7a7.5 7.5 0 0 1 12-2L20 8M4 16l2.5 3a7.5 7.5 0 0 0 12-2"/>,
  pin:<><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/></>,
  back:<path d="M20 12H4m6-6-6 6 6 6"/>,
  brand:<><path d="M12 3 4.5 6v5.6c0 4.5 3.3 7.7 7.5 9.4 4.2-1.7 7.5-4.9 7.5-9.4V6L12 3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></>,
  upload:<path d="M12 15V3m-4 4 4-4 4 4M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/>,
  folder:<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3V7Z"/>,
  briefcase:<><rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V3h8v4M3 12c6 4 12 4 18 0m-9 1v3"/></>,
  layers:<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>,
  file:<path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8m-8 4h6"/>,
  shield:<><path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/></>,
  window:<><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.1m3 0h.1M7 13h4m-4 3h8"/></>,
  check:<path d="m5 12 4 4L19 6"/>,
  compass:<><circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6 6-2Z"/></>,
  library:<path d="M3 4h4v16H3zm6 0h4v16H9zm6 1 4-1 3 15-4 1-3-15Z"/>,
  history:<path d="M3 11a9 9 0 1 1 2.6 7M3 4v7h7m2-4v6l4 2"/>,
  lock:<><rect x="6" y="10" width="12" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/></>,
  chevron:<path d="m9 5 7 7-7 7"/>,down:<path d="m6 9 6 6 6-6"/>,
  menu:<path d="M4 6h16M4 12h16M4 18h16"/>,arrow:<path d="M4 12h16m-6-6 6 6-6 6"/>,
  spark:<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z"/>,
}
export function Icon({name,className=''}:{name:IconName;className?:string}) {
  return <svg className={`ui-icon ${className}`} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

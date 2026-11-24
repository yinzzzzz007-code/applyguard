export function createOperationLock() {
  let locked=false
  const listeners=new Set<(busy:boolean)=>void>()
  const notify=()=>listeners.forEach(listener=>listener(locked))
  return {
    acquire():boolean { if(locked)return false;locked=true;notify();return true },
    release():void {if(locked){locked=false;notify()}},
    isLocked():boolean {return locked},
    subscribe(listener:(busy:boolean)=>void):()=>void {listeners.add(listener);return ()=>{listeners.delete(listener)}},
  }
}
export const resumePolishOperationLock=createOperationLock()

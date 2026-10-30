import type { ReelProject } from './reel'
export interface KineticRenderer { draw(time: number, still?: boolean): void; dispose(): void }
export function createKineticReel(canvas: HTMLCanvasElement, projects: ReelProject[], options?: {compact?: boolean}): Promise<KineticRenderer>

import { Component, type ReactNode } from 'react'

export class RouteBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (!this.state.failed) return this.props.children
    return <section className="state-panel state-error" role="alert">
      <h2>这个页面暂时无法打开</h2>
      <p>可以先从侧栏切换到其他页面。若刚更新过应用，请刷新后重试。</p>
      <button type="button" className="btn secondary" onClick={() => window.location.reload()}>刷新页面</button>
    </section>
  }
}

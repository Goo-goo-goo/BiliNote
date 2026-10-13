import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import Notes from './pages/Notes'
import NoteDetail from './pages/NoteDetail'
import Collections from './pages/Collections'
import Settings from './pages/Settings'
import {
  BrandMark,
  IconClock,
  IconFolder,
  IconGear,
  IconHome,
  IconNote,
} from './components/icons'
import { ErrorBoundary } from './components/ui'

const NAV = [
  { to: '/', label: '工作台', end: true, icon: IconHome },
  { to: '/tasks', label: '任务', icon: IconClock },
  { to: '/notes', label: '笔记', icon: IconNote },
  { to: '/collections', label: '合集', icon: IconFolder },
  { to: '/settings', label: '设置', icon: IconGear },
]

// 页名与导航用同一套词（工作台/任务/笔记/…），内容区标题另起物名（笔记库/…）
const TITLES: Record<string, string> = {
  '/': '工作台',
  '/tasks': '任务',
  '/notes': '笔记',
  '/collections': '合集',
  '/settings': '设置',
}

export default function App() {
  const location = useLocation()
  const title =
    TITLES[location.pathname] ||
    (location.pathname.startsWith('/notes/') ? '笔记' : 'BiliNote')

  return (
    <div className="app">
      <nav className="rail">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">BiliNote</span>
        </div>
        <div className="rail-nav">
          {NAV.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? 'rail-item active' : 'rail-item')}
              >
                <Icon size={18} />
                <span className="rail-label">{item.label}</span>
              </NavLink>
            )
          })}
        </div>
      </nav>

      <main className="main">
        <div className="topbar">
          <h1>{title}</h1>
        </div>

        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/notes" element={<Notes />} />
            <Route path="/notes/:taskId" element={<NoteDetail />} />
            <Route path="/collections" element={<Collections />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}
